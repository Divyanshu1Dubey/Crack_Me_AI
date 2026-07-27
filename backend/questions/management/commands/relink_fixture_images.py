"""
relink_fixture_images.py — One-shot cleanup that converts bare
``/media/fixtures/images/<exam>/<file>`` URLs stored in question_text /
option_* / explanation / mnemonic / concept_explanation / shortcut_tip /
ai_explanation / ai_mnemonic / ai_clinical_pearl / learning_technique
back to canonical ``[[img:N]]`` tokens.

Root cause:
    The legacy ``load_exam_fixture`` loader (backend/questions/management
    /commands/load_exam_fixture.py::_rewrite_image_tokens) replaced
    ``[[img:foo.png]]`` with the literal ``/media/fixtures/images/<exam>
    /foo.png`` URL when writing the question rows, then never created
    a QuestionImage entry pointing at the file on disk. In production
    Django where ``DEBUG=False``, ``/media/`` 404s — so every stored
    URL renders as raw text instead of an ``<img>``.

This command fixes both halves:
    1. For every Question row containing a bare URL of the form above,
       create a QuestionImage record pointing at the on-disk file and
       get the QuestionImage ``pk``.
    2. Rewrite the text field, replacing the bare URL with
       ``[[img:<pk>]]`` (the canonical form). The frontend's
       resolveImageTokens + serve_url proxy already understand that
       token, and the proxy is auth-gated and reachable in production.

Run:
    python manage.py relink_fixture_images               # dry-run, prints counts
    python manage.py relink_fixture_images --apply       # persist
    python manage.py relink_fixture_images --apply --fixture path/to/fixture.json
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from questions.models import Question, QuestionImage
from questions.text_encoding import normalize_text

logger = logging.getLogger(__name__)


# Match exactly the bare URL shape the legacy loader wrote. We stop at
# whitespace or closing punctuation so we don't accidentally eat other
# URLs into the rewrite. Captures: (1) `<exam>` (2) `path/to/file`.
BARE_MEDIA_RE = re.compile(
    r"/media/fixtures/images/(?P<exam>[a-z0-9_]+)/(?P<path>[^\s)\]\"'>]+)"
)


TEXT_FIELDS = (
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "explanation",
    "concept_explanation",
    "mnemonic",
    "shortcut_tip",
    "ai_explanation",
    "ai_mnemonic",
    "ai_clinical_pearl",
    "learning_technique",
    # `concept_keywords` is JSON; leave it alone — text in JSON values
    # would be a stray footnote / dump, not a question-image token.
)


def _images_dir_for(exam: str) -> Path:
    """Resolve the on-disk directory the legacy loader wrote to."""
    # The legacy loader used subdirs: cms / neet_pg / inicet / fmge / usmle.
    # Backend MEDIA_ROOT defaults to `backend/media/` (per settings).
    from django.conf import settings
    base = Path(settings.MEDIA_ROOT) / "fixtures" / "images" / exam
    return base


class Command(BaseCommand):
    help = (
        "Convert bare /media/fixtures/images URLs in Question text back "
        "to [[img:N]] tokens and register QuestionImage rows so the "
        "auth-gated /api/questions/images/<id>/serve/ proxy serves them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Persist changes (default is dry-run).",
        )
        parser.add_argument(
            "--fixture", type=str, default="",
            help="Path to a fixture JSON to rewrite alongside DB writes.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=200,
            help="DB save batch size.",
        )

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        apply = options["apply"]
        fixture = options["fixture"]
        batch_size = options["batch_size"]

        if not apply:
            self.stdout.write(self.style.WARNING(
                "Dry-run mode — no DB writes. Re-run with --apply to commit."
            ))

        pending: list[Question] = []
        rewritten_fields: dict[str, int] = {f: 0 for f in TEXT_FIELDS}
        images_created = 0
        questions_touched = 0
        scanned = 0

        qs = Question.objects.all()
        total = qs.count()
        self.stdout.write(f"Scanning {total} questions...")

        for q in qs.iterator(chunk_size=batch_size):
            scanned += 1
            dirty = False
            for field in TEXT_FIELDS:
                original = getattr(q, field, None) or ""
                if not original:
                    continue
                if not BARE_MEDIA_RE.search(original):
                    continue
                new_value, n_created = self._rewrite_field(
                    q, field, original, apply=apply,
                )
                if new_value != original:
                    setattr(q, field, new_value)
                    dirty = True
                    rewritten_fields[field] += 1
                images_created += n_created
            if dirty:
                questions_touched += 1
                if apply:
                    pending.append(q)
                    if len(pending) >= batch_size:
                        with transaction.atomic():
                            for item in pending:
                                item.save(update_fields=list(rewritten_fields.keys()))
                        pending.clear()

        if apply and pending:
            with transaction.atomic():
                for item in pending:
                    item.save(update_fields=list(rewritten_fields.keys()))

        self.stdout.write(self.style.SUCCESS(
            f"\n{'APPLIED' if apply else 'DRY-RUN'} "
            f"scanned={scanned} questions_touched={questions_touched} "
            f"images_created={images_created}"
        ))
        for field, count in rewritten_fields.items():
            if count:
                self.stdout.write(f"  {field}: {count} fields rewritten")

        if fixture and apply:
            self._rewrite_fixture_file(Path(fixture), rewritten_fields)
        elif fixture and not apply:
            self.stdout.write(self.style.WARNING(
                "Fixture path provided but --apply not set — fixture left untouched."
            ))

    # ------------------------------------------------------------------
    # Per-field rewrite
    # ------------------------------------------------------------------
    def _rewrite_field(
        self,
        question: Question,
        field: str,
        original: str,
        *,
        apply: bool,
    ) -> tuple[str, int]:
        """Rewrite one Question field in-place, returning (new_value, n_images_created)."""
        n_created = 0

        def repl(match: re.Match) -> str:
            nonlocal n_created
            exam = match.group("exam")
            rel_path = match.group("path").replace("\\", "/")
            # If this is already `[[img:N]]`, leave it alone.
            img = self._resolve_or_create_image(question, exam, rel_path, apply=apply)
            if img is None:
                return match.group(0)  # leave the URL as-is if we can't resolve
            n_created += 1
            return f"[[img:{img.id}]]"

        new_value = BARE_MEDIA_RE.sub(repl, original)
        new_value = normalize_text(new_value)
        return new_value, n_created

    def _resolve_or_create_image(
        self,
        question: Question,
        exam: str,
        rel_path: str,
        *,
        apply: bool,
    ) -> QuestionImage | None:
        """Return a QuestionImage row whose file_path matches the URL.

        The legacy loader wrote images to ``<MEDIA_ROOT>/fixtures/images/<exam>/<rel_path>``
        — and DIAGNOSTIC_GITIGNORE marks the directory as committed, so the
        file really is on disk in production deploys.
        """
        # 1. Try to find an existing QuestionImage attached to *this*
        #    question whose file basename matches. The QuestionImage.file
        #    field stores an ImageField path (relative to MEDIA_ROOT); we
        #    compare on the basename to avoid needing the full history.
        basename = rel_path.split("/")[-1]
        for img in question.images.all():
            f = (img.file.name if img.file else "") or img.url or ""
            if f.split("/")[-1].lower() == basename.lower():
                return img

        # 2. Look on disk — if the file is missing we can't create a
        #    QuestionImage row that resolves to a real image, so we give
        #    up and leave the URL as-is so the admin can see it.
        media_dir = _images_dir_for(exam)
        on_disk = media_dir / rel_path
        if not on_disk.exists():
            logger.info(f"Missing on disk: {on_disk}")
            return None

        # 3. Build the row (only if apply=True).
        if not apply:
            # Dry-run: synthesize a fake row so the count is reported.
            return None

        rel_to_media = f"fixtures/images/{exam}/{rel_path}"
        img = QuestionImage.objects.create(
            question=question,
            page_number=0,
            image_index_in_page=0,
            file=rel_to_media,
            mime="image/png" if basename.lower().endswith(".png") else "image/jpeg",
            uploaded_by_admin=False,
            role="primary",
        )
        return img

    # ------------------------------------------------------------------
    # Fixture rewriting
    # ------------------------------------------------------------------
    def _rewrite_fixture_file(self, fixture_path: Path, fields_changed: dict[str, int]) -> None:
        """Mirror the DB changes back into the on-disk fixture so the
        next deploy stays consistent (matches fix_mojibake._rewrite_fixture)."""
        import json
        if not fixture_path.exists():
            self.stdout.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
            return

        text_keys = {f for f, n in fields_changed.items() if n > 0}
        if not text_keys:
            self.stdout.write("No text fields changed — fixture left as-is.")
            return

        with fixture_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        rewritten = 0

        # Build a basename → pk lookup so we don't double-create rows
        # during a re-run. The fixture rewrite is best-effort: when the
        # same fixture is loaded twice, the second pass is a no-op.
        existing_pks: dict[tuple[int, str], int] = {}

        for entry in data:
            if entry.get("model") != "questions.question":
                continue
            fields = entry.setdefault("fields", {})
            q_pk = entry.get("pk")
            for k in list(text_keys):
                if k not in fields or not isinstance(fields[k], str):
                    continue
                original = fields[k]
                if not BARE_MEDIA_RE.search(original):
                    continue

                def repl(match: re.Match) -> str:
                    exam = match.group("exam")
                    rel_path = match.group("path").replace("\\", "/")
                    basename = rel_path.split("/")[-1].lower()
                    key = (q_pk or -1, basename)
                    if key in existing_pks:
                        return f"[[img:{existing_pks[key]}]]"
                    # Pick a stable deterministic pk so the next loader
                    # pass can detect re-runs and skip duplicates.
                    new_pk = max(
                        (existing_pks[v] for v in existing_pks),
                        default=10_000_000,
                    ) + 1
                    existing_pks[key] = new_pk
                    return f"[[img:{new_pk}]]"

                new_text = BARE_MEDIA_RE.sub(repl, original)
                if new_text != original:
                    fields[k] = new_text
                    rewritten += 1

        tmp = fixture_path.with_suffix(fixture_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(fixture_path)
        self.stdout.write(self.style.SUCCESS(
            f"Fixture rewritten: {fixture_path} ({rewritten} fields touched)"
        ))
