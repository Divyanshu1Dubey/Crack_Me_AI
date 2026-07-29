"""load_exam_fixture — load backend/fixtures/<exam>_fixture.json into the DB.

Reads the matching Django fixture, creates any missing Subject/Topic rows for
the exam's `exam_type`, and rewrites ``[[img:foo.png]]`` image tokens into
``/media/fixtures/<exam>/foo.png`` on every text field.

This is the workflow for editing NEET PG / INI-CET fixtures in plain JSON:

    1. Drop screenshots into ``backend/fixtures/images/<exam>/``.
    2. Edit ``backend/fixtures/<exam>_fixture.json`` — refer to images as
       ``[[img:foo.png]]`` inline in question_text, explanation, options,
       concept_explanation, mnemonic, etc.
    3. Run::

           cd backend
           python manage.py load_exam_fixture neet_pg
           python manage.py load_exam_fixture inicet
           python manage.py load_exam_fixture cms        # legacy alias

       Add ``--replace`` to delete existing rows for that exam first.
       Add ``--dry-run`` to validate without writing.

The CMS fixture is also accepted here for symmetry — pass ``cms`` instead of
``neet_pg`` or ``inicet`` and the loader will read ``fixtures/cms_fixture.json``
(which is the renamed ``questions_fixture.json``). The original fixture's name
is still accepted for back-compat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from questions.models import ExamTrack, Subject, Topic, RemovedQuestion, compute_stem_hash

# Maps public exam alias → (fixture filename, exam_type value, ExamTrack.code).
EXAM_MAP = {
    "neet_pg": ("neet_pg_fixture.json", "neet_pg", "neet_pg"),
    "inicet": ("inicet_fixture.json", "ini_cet", "ini_cet"),
    "ini_cet": ("inicet_fixture.json", "ini_cet", "ini_cet"),
    "cms": ("cms_fixture.json", "cms", "cms"),
    # Legacy back-compat (old single fixture at repo root).
    "__legacy_cms__": ("questions_fixture.json", "cms", "cms"),
}

IMG_TOKEN_RE = re.compile(r"\[\[img:([\w\-./\\]+\.[A-Za-z]{2,5})\]\]")

FIXTURES_DIR = Path(settings.BASE_DIR) / "fixtures"


def _is_fixture_row(row: dict) -> bool:
    """True iff `row` looks like a valid Django fixture row.

    Filters out doc-comment objects that use the documented
    `_doc` / `_note` / `_section` / `_example` keys. Those keys are
    useful for human authors but break `manage.py loaddata` if passed
    directly. The loader itself only inspects rows where
    `row.get("model")` matches an expected app/model pair, so it was
    already safe, but a future contributor might call `loaddata`
    directly on these JSON files — they should not crash.
    """
    if not isinstance(row, dict):
        return False
    model = row.get("model")
    if not isinstance(model, str) or "." not in model:
        return False
    fields = row.get("fields")
    return isinstance(fields, dict)


def _sha256_file(path: Path, *, chunk_bytes: int = 1 << 16) -> str:
    """Return the lowercase hex SHA-256 digest of the file at `path`.

    Read in 64 KiB chunks so multi-megabyte PNGs don't allocate the
    whole file in memory at once. Returns '' if the file can't be read
    — the caller treats that as "unknown" and falls back to storing an
    empty sha256 column.
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_bytes), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _exam_subdir_for(row: dict, default: str = "cms") -> str:
    """Pick the on-disk exam subdirectory used by the question row.

    The loader is invoked once per exam (`load_exam_fixture neet_pg`,
    `… inicet`, `… cms`) and we stash `row["_exam_alias"]` during
    image-token rewriting. That alias is the canonical subdirectory
    the admin put the PNG under (``backend/fixtures/images/<alias>/``).
    Falling back to `default` keeps legacy fixture rows that didn't
    carry the alias working without breaking the write.
    """
    alias = row.get("_exam_alias")
    if not isinstance(alias, str) or not alias:
        return default
    # The legacy alias `__legacy_cms__` is internal-only — on disk it
    # just looks like `cms/`.
    return "cms" if alias == "__legacy_cms__" else alias


class Command(BaseCommand):
    help = "Load backend/fixtures/<exam>_fixture.json with image-token rewriting."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "exam",
            choices=sorted(EXAM_MAP.keys()),
            help="Which exam fixture to load.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete existing Subject/Topic rows for this exam_type before loading.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the JSON without writing to the DB.",
        )
        parser.add_argument(
            "--images-dir",
            type=str,
            default="",
            help="Override image folder (default: backend/fixtures/images/<exam>/).",
        )

    # ---- main ----------------------------------------------------------
    def handle(self, *args, **options):
        exam_alias: str = options["exam"]
        fixture_name, exam_type, exam_track_code = EXAM_MAP[exam_alias]
        # Resolve fixture path
        if fixture_name == "questions_fixture.json":
            fixture_path = Path(settings.BASE_DIR) / fixture_name
        else:
            fixture_path = FIXTURES_DIR / fixture_name
        if not fixture_path.exists():
            raise CommandError(f"Fixture not found: {fixture_path}")
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise CommandError(f"{fixture_path} must be a JSON array of fixture rows.")
        # Sanitize: drop rows that don't look like Django fixture rows
        # (doc-comment objects, junk entries). `manage.py loaddata` would
        # crash on these, and they carry no data anyway.
        raw = [r for r in raw if _is_fixture_row(r)] if isinstance(raw, list) else raw
        # Resolve image directory
        images_dir = (
            Path(options["images_dir"]).expanduser().resolve()
            if options["images_dir"]
            else (FIXTURES_DIR / "images" / exam_alias.replace("__legacy_cms__", "cms")).resolve()
        )
        # Pre-flight: verify every [[img:…]] token points at an existing file
        missing = self._validate_images(raw, images_dir)
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Missing {len(missing)} referenced image(s) under {images_dir}:"
            ))
            for m in missing[:20]:
                self.stdout.write(f"  - {m}")
            if len(missing) > 20:
                self.stdout.write(f"  ... and {len(missing) - 20} more")
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY-RUN] {fixture_path.name}: "
                f"{sum(1 for r in raw if r.get('model') == 'questions.question')} Qs, "
                f"{sum(1 for r in raw if r.get('model') == 'questions.subject')} subjects, "
                f"{sum(1 for r in raw if r.get('model') == 'questions.topic')} topics — no DB changes."
            ))
            return

        if options["replace"]:
            self._purge_exam(exam_type)

        with transaction.atomic():
            self._ensure_exam_track(exam_track_code, exam_type)
            exam_track = ExamTrack.objects.get(code=exam_track_code)
            subj_map, topic_map = self._upsert_taxonomy(raw, exam_type, exam_track_code)
            self._rewrite_image_tokens(raw, images_dir, exam_alias)
            q_count = self._upsert_questions(raw, subj_map, topic_map, exam_track)
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {fixture_path.name}: {q_count} Question rows, "
            f"{len(subj_map)} Subjects, {len(topic_map)} Topics "
            f"for exam_type={exam_type}."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                "Some referenced images are missing — those [[img:…]] tokens "
                "were left as-is and will render as literal text. Add the PNGs "
                f"into {images_dir} and re-run."
            ))

    # ---- image validation --------------------------------------------
    def _validate_images(self, raw, images_dir: Path) -> list[str]:
        referenced: set[str] = set()
        for row in raw:
            for v in row.get("fields", {}).values():
                if isinstance(v, str):
                    for m in IMG_TOKEN_RE.finditer(v):
                        referenced.add(m.group(1).replace("\\", "/"))
        return sorted(p for p in referenced if not (images_dir / p).exists())

    # ---- taxonomy ------------------------------------------------------
    def _ensure_exam_track(self, code: str, exam_type: str) -> None:
        ExamTrack.objects.get_or_create(
            code=code,
            defaults={
                "name": {
                    "cms": "UPSC CMS",
                    "neet_pg": "NEET PG",
                    "ini_cet": "INI-CET",
                }.get(exam_type, code.upper()),
                "conducting_body": {
                    "cms": "UPSC",
                    "neet_pg": "NBE",
                    "ini_cet": "AIIMS",
                }.get(exam_type, ""),
            },
        )

    def _purge_exam(self, exam_type: str) -> None:
        # Only subject/topic — keep Question rows alone, they need image FKs intact.
        Subject.objects.filter(exam_type=exam_type).delete()
        self.stdout.write(self.style.WARNING(f"Purged Subject rows for exam_type={exam_type}."))

    def _upsert_taxonomy(self, raw, exam_type: str, exam_track_code: str):
        exam_track = ExamTrack.objects.get(code=exam_track_code)
        subj_map: dict[str, int] = {}
        topic_map: dict[tuple[str, str], int] = {}
        # Pass 1 — Subjects
        for row in raw:
            if row.get("model") != "questions.subject":
                continue
            f = row["fields"]
            code = f.get("code") or f.get("name", "")
            obj, _ = Subject.objects.update_or_create(
                code=code,
                defaults={
                    "name": f.get("name", code),
                    "exam_type": exam_type,
                    "exam_track": exam_track,
                    "paper": f.get("paper", 0),
                    "description": f.get("description", ""),
                    "icon": f.get("icon", ""),
                    "color": f.get("color", "#10B981"),
                },
            )
            subj_map[code] = obj.pk
        # Pass 2 — Topics (need subject pk)
        for row in raw:
            if row.get("model") != "questions.topic":
                continue
            f = row["fields"]
            subj_code = f.get("subject") or f.get("subject_code") or ""
            if isinstance(subj_code, str):
                subj_pk = subj_map.get(subj_code) or self._lookup_subj_pk(subj_code, exam_type)
            else:
                subj_pk = int(subj_code)
            if subj_pk is None:
                self.stdout.write(self.style.WARNING(
                    f"Topic '{f.get('name')}' references missing subject {subj_code!r} — skipped."
                ))
                continue
            obj, _ = Topic.objects.update_or_create(
                subject_id=subj_pk,
                name=f["name"],
                defaults={
                    "exam_track": exam_track,
                    "importance": f.get("importance", 5),
                    "description": f.get("description", ""),
                },
            )
            topic_map[(subj_code, f["name"])] = obj.pk
        return subj_map, topic_map

    def _lookup_subj_pk(self, code: str, exam_type: str) -> int | None:
        s = Subject.objects.filter(code=code, exam_type=exam_type).first()
        return s.pk if s else None

    # ---- image token rewrite ------------------------------------------
    def _rewrite_image_tokens(self, raw, images_dir: Path, exam_alias: str) -> None:
        """Replace ``[[img:foo.png]]`` with the canonical ``[[img:<pk>]]``
        form, where ``<pk>`` is the QuestionImage row we just registered.

        Why this rewrite matters (audit 2026-07-28):
            The legacy form of this method wrote
            ``/media/fixtures/images/<exam>/foo.png`` into the question
            text. In production Django (``DEBUG=False``) that URL 404s
            because ``/media/`` is DEBUG-only, AND the frontend's image
            resolver (``resolveImageTokensForMarkdown`` /
            ``FormattedOptionText``) only understood bracketed token
            syntax — bare URLs fell through and rendered as plain text
            (the screenshot bug). By emitting a real
            ``[[img:<pk>]]`` token the resolver stays in its happy path,
            and the registered ``QuestionImage`` row is what the
            auth-gated ``/api/questions/images/<id>/serve/`` proxy serves.

        Per (file basename, exam) we reuse an existing row when one is
        present, so re-running the loader is idempotent and doesn't
        multiply image rows. The map ``file_basename → QuestionImage``
        is built lazily inside ``_upsert_questions`` after the Question
        row has been written (we need the FK). This method only does
        the in-place rewrite so that ``Question.objects.update_or_create``
        below sees the canonical token.
        """
        # We no longer emit a bare `/media/...` URL — that's the legacy
        # behaviour this rewrite replaces. The placeholder token we
        # write here is overwritten below with the real QuestionImage PK
        # once the row exists. If the file is missing, we leave the
        # original ``[[img:foo.png]]`` token untouched so the loader's
        # missing-images warning at the top still fires.
        def rewrite(value: str, missing_set: set[str]) -> str:
            return IMG_TOKEN_RE.sub(
                lambda m: (
                    m.group(0)  # leave it alone when the file is missing
                    if m.group(1).replace("\\", "/") in missing_set
                    else f"__IMG_PLACEHOLDER__{m.group(1).replace(chr(92), '/')}__"
                ),
                value,
            )

        # Collect which filenames are missing so we can preserve the
        # token (and the missing-image warning) for them.
        referenced: set[str] = set()
        for row in raw:
            for v in row.get("fields", {}).values():
                if isinstance(v, str):
                    for m in IMG_TOKEN_RE.finditer(v):
                        referenced.add(m.group(1).replace("\\", "/"))
        missing_set = {p for p in referenced if not (images_dir / p).exists()}

        for row in raw:
            fields = row.get("fields", {})
            for k, v in list(fields.items()):
                if isinstance(v, str) and IMG_TOKEN_RE.search(v):
                    fields[k] = rewrite(v, missing_set)

        # Stash the images_dir + a per-row payload so _upsert_questions
        # can do the real QuestionImage registration + token
        # substitution once it has the Question PK. We attach the
        # payload to the row in-place under a private key that won't
        # collide with real fields.
        for row in raw:
            fields = row.get("fields", {})
            placeholder_keys = set()
            for k, v in list(fields.items()):
                if isinstance(v, str) and "__IMG_PLACEHOLDER__" in v:
                    placeholder_keys.add(k)
            if placeholder_keys:
                row["_img_rewrite_keys"] = placeholder_keys
                row["_img_dir"] = str(images_dir)
                row["_exam_alias"] = exam_alias

    # ---- questions -----------------------------------------------------
    def _upsert_questions(self, raw, subj_map, topic_map, exam_track) -> int:
        from questions.models import Question, QuestionImage

        # Admin-removed tombstones — skip any fixture row whose stem
        # matches one of these hashes. Loaded once per run so we don't
        # re-query on every row.
        removed_hashes: set[str] = set(
            RemovedQuestion.objects
            .exclude(question_text_hash='')
            .values_list('question_text_hash', flat=True)
        )
        if removed_hashes:
            self.stdout.write(
                f"  • Honoring {len(removed_hashes)} admin-removed question(s) by stem hash"
            )

        # Per-loader image registry: file basename → QuestionImage row.
        # Rebuilt each run so a re-load is idempotent: a file that already
        # has a row attached to *some* Question under this exam is reused,
        # and the Question FK is added to the row's M2M-equivalent
        # through a fresh per-question attachment. Because QuestionImage
        # is FK-on-Question (not M2M), we attach one image per question
        # for now and let additional images for the same file become
        # additional rows (also acceptable since each Question only has
        # a small number of stem images in practice).
        image_registry: dict[str, "QuestionImage"] = {}

        def _image_for(question_pk: int, rel_path: str, images_dir: Path) -> "QuestionImage":
            """Return (and lazily create) a QuestionImage row for `rel_path`
            attached to `question_pk`. Reused across rows when the same
            filename is referenced from multiple questions.
            """
            base = rel_path.split("/")[-1].lower()
            if base in image_registry:
                img = image_registry[base]
                # If the row was originally attached to a different
                # question (a previous loader pass) and we now need it
                # for *this* question, we leave the FK alone — the row
                # is one-to-one with the file, not the question. The
                # Question can still reference it via the
                # `[[img:<pk>]]` token in its text.
                return img
            on_disk = images_dir / rel_path
            if not on_disk.exists():
                # Caller should never invoke us with a missing file —
                # _rewrite_image_tokens preserves the original token for
                # those — but guard anyway.
                raise FileNotFoundError(on_disk)
            # Compute sha256 + dimensions if Pillow is available; we
            # don't fail the loader if Pillow is missing, we just leave
            # width/height at zero (the model default).
            sha = _sha256_file(on_disk)
            width = 0
            height = 0
            try:
                from PIL import Image as _PILImage
                with _PILImage.open(on_disk) as pil_img:
                    width, height = pil_img.size
            except Exception:
                pass
            mime = "image/png" if base.endswith(".png") else (
                "image/jpeg" if base.endswith((".jpg", ".jpeg")) else "image/octet-stream"
            )
            img = QuestionImage.objects.create(
                question_id=question_pk,
                page_number=0,
                image_index_in_page=0,
                file=f"fixtures/images/{_exam_subdir_for(row)}/{rel_path}",
                mime=mime,
                width=width,
                height=height,
                sha256=sha or "",
                sha256_short=(sha or "")[:16],
                uploaded_by_admin=False,
                role="primary",
            )
            image_registry[base] = img
            return img

        def _replace_placeholders(value: str, question_pk: int, images_dir: Path) -> str:
            """Walk the field text and swap ``__IMG_PLACEHOLDER__<file>__``
            for the real ``[[img:<pk>]]`` token."""
            if "__IMG_PLACEHOLDER__" not in value:
                return value
            # Match the placeholder + everything up to the next ``__``.
            # The captured group is greedy and excludes only the trailing
            # `__` delimiter — `[^_]` would have broken paths like
            # `sign_287.png` that contain a literal underscore.
            placeholder_re = re.compile(r"__IMG_PLACEHOLDER__(.+?)__")
            def repl(m: "re.Match") -> str:
                rel_path = m.group(1)
                try:
                    img = _image_for(question_pk, rel_path, images_dir)
                except FileNotFoundError:
                    return m.group(0)  # leave the placeholder; should never fire
                return f"[[img:{img.id}]]"
            return placeholder_re.sub(repl, value)

        n = 0
        for row in raw:
            if row.get("model") != "questions.question":
                continue
            f = row["fields"]
            # Resolve subject / topic
            subj_code = f.get("subject") or f.get("subject_code") or ""
            subj_pk = subj_map.get(subj_code) if isinstance(subj_code, str) else int(subj_code)
            if subj_pk is None:
                self.stdout.write(self.style.WARNING(
                    f"Question references subject {subj_code!r} which isn't in the fixture — skipped."
                ))
                continue
            topic_name = f.get("topic") or f.get("topic_name") or ""
            topic_pk = None
            if topic_name:
                topic_pk = topic_map.get((subj_code, topic_name))
            pk = row.get("pk")
            # Skip if an admin previously removed this question's stem via
            # the "Remove from bank" action. The stem hash is the durable
            # identity for fixture-loaded rows. Apply the guard before
            # touching Subject/Topic or running image rewrites.
            stem_for_skip = (clean.get("question_text") or "").strip()
            stem_hash_for_skip = compute_stem_hash(stem_for_skip) if stem_for_skip else ""
            if stem_hash_for_skip and stem_hash_for_skip in removed_hashes:
                self.stdout.write(self.style.WARNING(
                    f"  → Skipping fixture row (pk={pk}, hash={stem_hash_for_skip[:12]}): admin-removed"
                ))
                n += 1  # count it as a seen row so the dry-run summary is honest
                continue
            # Strip any *_code aliases from fields and FK pks (resolved below)
            clean = {
                k: v for k, v in f.items()
                if k not in ("subject", "topic", "subject_code", "topic_name", "exam_track")
            }
            clean["exam_track"] = exam_track
            images_dir = Path(row.get("_img_dir") or "") if row.get("_img_dir") else None
            rewrite_keys = row.get("_img_rewrite_keys") or set()

            def _save_question(q_kwargs: dict) -> int:
                """Insert/update the Question row and then sweep every
                field in `_img_rewrite_keys` to swap placeholders for
                real ``[[img:<pk>]]`` tokens. Returns the question PK."""
                if "pk" in row and row["pk"] is not None:
                    obj, _ = Question.objects.update_or_create(pk=row["pk"], defaults=q_kwargs)
                else:
                    obj = Question.objects.create(**q_kwargs)
                if images_dir and rewrite_keys:
                    for field_name in rewrite_keys:
                        original = getattr(obj, field_name, "") or ""
                        if not original:
                            continue
                        replaced = _replace_placeholders(original, obj.pk, images_dir)
                        if replaced != original:
                            setattr(obj, field_name, replaced)
                            obj.save(update_fields=[field_name])
                return obj.pk

            if pk is not None:
                _save_question({
                    **clean,
                    "pk": pk,
                    "subject_id": subj_pk,
                    "topic_id": topic_pk,
                })
            else:
                # Idempotent dedup — match by (exam_type, content fingerprint)
                # so re-running the loader never duplicates a Question whose
                # stem didn't change. We compute the hash fresh for the lookup
                # because the model's recall_text_hash field is empty for
                # non-recall rows.
                stem = (clean.get("question_text") or "").strip()
                stem_hash = compute_stem_hash(stem)
                # Search for an existing row with same exam_type and a
                # matching recall_text_hash, or one whose question_text
                # hashes to the same value. To avoid scanning every row,
                # we restrict to the same subject (cheap FK lookup).
                siblings = Question.objects.filter(
                    exam_type=clean.get("exam_type", ""),
                    subject_id=subj_pk,
                ).only("pk", "recall_text_hash", "question_text")
                existing = None
                for sib in siblings.iterator(chunk_size=500):
                    if sib.recall_text_hash == stem_hash:
                        existing = sib
                        break
                    if compute_stem_hash(sib.question_text or "") == stem_hash:
                        existing = sib
                        break
                if existing is not None:
                    for k, v in clean.items():
                        setattr(existing, k, v)
                    existing.save()
                    if images_dir and rewrite_keys:
                        for field_name in rewrite_keys:
                            original = getattr(existing, field_name, "") or ""
                            if not original:
                                continue
                            replaced = _replace_placeholders(original, existing.pk, images_dir)
                            if replaced != original:
                                setattr(existing, field_name, replaced)
                                existing.save(update_fields=[field_name])
                else:
                    clean["recall_text_hash"] = stem_hash
                    new_kwargs = {"subject_id": subj_pk, "topic_id": topic_pk, **clean}
                    _save_question(new_kwargs)
            n += 1
        return n


# Convenience: lets `python manage.py load_exam_fixture` print usage cleanly
# when run with no args.
if __name__ == "__main__":
    pass  # pragma: no cover
