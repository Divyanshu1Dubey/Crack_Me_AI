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
    python manage.py relink_fixture_images --apply --mark-missing

Safety (it runs with --apply on every deploy):
    * A URL whose image file is not on disk is LEFT UNTOUCHED by default and
      reported as unresolved — a fresh container has no fixture images, and
      rewriting every URL there destroyed the references before the images
      could be uploaded. ``--mark-missing`` replaces such a URL with the
      reversible marker ``[image unavailable: <exam>/<path>]``; a later run
      relinks the marker once the file exists.
    * The fixture mirror writes only ``[[img:N]]`` ids of QuestionImage rows
      created / found in THIS run for the same question (it used to invent
      ids from 10,000,001 upwards). A relative ``--fixture`` path is looked
      up in the current directory, then the backend dir, then the repo root.
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

# Reversible marker written by --mark-missing (keeps exam + path so a later
# run can relink it). The old lossy "[image unavailable: <basename>]" marker
# does not match (it has no exam/ prefix) and is left alone.
MISSING_MARKER_RE = re.compile(
    r"\[image unavailable: (?P<exam>[a-z0-9_]+)/(?P<path>[^\]\s]+)\]"
)


def _missing_marker(exam: str, rel_path: str) -> str:
    return f"[image unavailable: {exam}/{rel_path}]"


def _resolve_fixture_path(raw: str) -> Path:
    """Find a relative fixture path from cwd, the backend dir, or the repo root."""
    from django.conf import settings
    p = Path(raw)
    if p.is_absolute():
        return p
    base = Path(settings.BASE_DIR)
    for candidate in (Path.cwd() / p, base / p, base.parent / p):
        if candidate.exists():
            return candidate
    return Path.cwd() / p


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
    """Return the canonical on-disk images directory for `exam`.

    Two candidate locations exist in this codebase:

      1. ``<MEDIA_ROOT>/fixtures/images/<exam>/`` — the path the
         QuestionImage.file ImageField expects (Django-managed
         MEDIA_ROOT). The relink command historically pointed here
         only, which silently failed when legacy import paths wrote
         to the second location instead.
      2. ``<BASE_DIR>/fixtures/images/<exam>/`` — the directory the
         legacy ``load_exam_fixture`` loader wrote to. Files live
         here for any image shipped with the bundled fixtures
         (``backend/fixtures/images/...``), and Django's
         collectstatic never copies them into MEDIA_ROOT because
         they're tracked in git LFS / fixture data, not user
         uploads.

    Returned as a Path for compatibility with the existing
    ``exists()`` checks. Callers that need to *search* both should
    use ``find_image_on_disk()`` instead of just reading this.
    """
    from django.conf import settings
    return Path(settings.MEDIA_ROOT) / "fixtures" / "images" / exam


def find_image_on_disk(exam: str, rel_path: str) -> Path | None:
    """Search every plausible on-disk location for `rel_path` under
    `exam`. Returns the first hit, or None if the file is missing
    everywhere.

    Bug 2026-07-28 — the audit surfaced ``radiograph_sign_287.png``
    and other recall images whose ``question_text`` contained a bare
    ``/media/...`` URL but whose file existed only at
    ``<BASE_DIR>/fixtures/images/<exam>/...`` (not MEDIA_ROOT). The
    legacy loader wrote the file there; the relink command looked
    in MEDIA_ROOT only and gave up silently. We now probe both
    locations so the QuestionImage row + ``[[img:N]]`` rewrite
    succeeds.
    """
    from django.conf import settings
    rel_path = rel_path.replace("\\", "/")
    for base in (Path(settings.MEDIA_ROOT), Path(settings.BASE_DIR)):
        candidate = base / "fixtures" / "images" / exam / rel_path
        if candidate.exists():
            return candidate
    return None


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
        parser.add_argument(
            "--mark-missing", action="store_true",
            help="Replace URLs whose file is missing with the reversible "
                 "'[image unavailable: <exam>/<path>]' marker (default: leave them).",
        )

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        apply = options["apply"]
        fixture = options["fixture"]
        batch_size = options["batch_size"]
        self.mark_missing = bool(options.get("mark_missing"))
        # (question pk, exam, rel_path) → QuestionImage pk resolved this run;
        # the only ids the fixture mirror may write.
        self.relinked: dict[tuple[int, str, str], int] = {}
        self.unresolved = 0

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
                if not (BARE_MEDIA_RE.search(original) or MISSING_MARKER_RE.search(original)):
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
            f"images_created={images_created} unresolved_missing_on_disk={self.unresolved}"
        ))
        for field, count in rewritten_fields.items():
            if count:
                self.stdout.write(f"  {field}: {count} fields rewritten")
        if self.unresolved and not self.mark_missing:
            self.stdout.write(self.style.WARNING(
                f"  {self.unresolved} URL(s) point at images that are not on disk; "
                "left unchanged (upload the images, or re-run with --mark-missing)."
            ))

        if fixture and apply:
            self._rewrite_fixture_file(_resolve_fixture_path(fixture), rewritten_fields)
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
            img = self._resolve_or_create_image(question, exam, rel_path, apply=apply)
            if img is None:
                # The image is not on disk (or this is a dry run). Never
                # destroy the reference: keep the URL / marker as it is,
                # unless --mark-missing asks for the visible, reversible
                # "[image unavailable: <exam>/<path>]" marker, which keeps
                # the full path so a later run can relink it. (This used to
                # write "[image unavailable: <basename>]" unconditionally on
                # every deploy, losing the path for good.)
                if apply and find_image_on_disk(exam, rel_path) is None:
                    self.unresolved += 1
                    if self.mark_missing:
                        return _missing_marker(exam, rel_path)
                return match.group(0)
            n_created += 1
            self.relinked[(question.pk, exam, rel_path)] = img.id
            return f"[[img:{img.id}]]"

        new_value = BARE_MEDIA_RE.sub(repl, original)
        new_value = MISSING_MARKER_RE.sub(repl, new_value)
        if new_value == original:
            return original, n_created
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
        #    QuestionImage row that resolves to a real image.
        on_disk = find_image_on_disk(exam, rel_path)
        if on_disk is None:
            logger.info(f"Missing on disk (no candidate found): "
                        f"<BASE_DIR or MEDIA_ROOT>/fixtures/images/"
                        f"{exam}/{rel_path}")
            # The caller keeps the original text (or, with --mark-missing,
            # writes the reversible "[image unavailable: <exam>/<path>]"
            # marker) so the reference is never lost.
            return None

        # 3. Build the row (only if apply=True).
        if not apply:
            # Dry-run: synthesize a fake row so the count is reported.
            return None

        rel_to_media = f"fixtures/images/{exam}/{rel_path}"
        from django.conf import settings
        media_copy = Path(settings.MEDIA_ROOT) / rel_to_media
        if not media_copy.exists():
            # Found only under BASE_DIR: the ImageField path is relative to
            # MEDIA_ROOT, so copy the file there or the new row would 404.
            import shutil
            media_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(on_disk, media_copy)
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

        # Only ids of QuestionImage rows created / found in this run for the
        # same question are written; anything else keeps its original text.
        # (This used to invent ids from 10,000,001 upwards — tokens that point
        # at no image at all.)
        for entry in data:
            if entry.get("model") != "questions.question":
                continue
            fields = entry.setdefault("fields", {})
            q_pk = entry.get("pk")
            for k in list(text_keys):
                if k not in fields or not isinstance(fields[k], str):
                    continue
                original = fields[k]
                if not (BARE_MEDIA_RE.search(original) or MISSING_MARKER_RE.search(original)):
                    continue

                def repl(match: re.Match) -> str:
                    exam = match.group("exam")
                    rel_path = match.group("path").replace("\\", "/")
                    img_id = self.relinked.get((q_pk, exam, rel_path))
                    return f"[[img:{img_id}]]" if img_id else match.group(0)

                new_text = BARE_MEDIA_RE.sub(repl, original)
                new_text = MISSING_MARKER_RE.sub(repl, new_text)
                if new_text != original:
                    fields[k] = new_text
                    rewritten += 1

        if not rewritten:
            self.stdout.write("No fixture rows matched an image relinked in this run — fixture left as-is.")
            return

        tmp = fixture_path.with_suffix(fixture_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(fixture_path)
        self.stdout.write(self.style.SUCCESS(
            f"Fixture rewritten: {fixture_path} ({rewritten} fields touched)"
        ))
