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
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from questions.models import ExamTrack, Subject, Topic

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
        """Replace [[img:foo.png]] with /media/fixtures/images/<exam>/foo.png.

        Only writes on rows we will import (questions.question and
        questions.topic). question_text and the option_* / explanation /
        mnemonic / concept_explanation / shortcut_tip / ai_explanation /
        ai_mnemonic / ai_clinical_pearl / learning_technique fields are
        walked; similar array fields (concept_tags etc.) are left intact.
        """
        exam_subdir = "cms" if exam_alias == "__legacy_cms__" else exam_alias
        if exam_subdir == "ini_cet":
            exam_subdir = "inicet"
        url_prefix = f"/media/fixtures/images/{exam_subdir}/"

        def rewrite(value: str) -> str:
            return IMG_TOKEN_RE.sub(
                lambda m: f"{url_prefix}{m.group(1).replace(chr(92), '/')}",
                value,
            )

        for row in raw:
            fields = row.get("fields", {})
            for k, v in list(fields.items()):
                if isinstance(v, str) and IMG_TOKEN_RE.search(v):
                    fields[k] = rewrite(v)

    # ---- questions -----------------------------------------------------
    def _upsert_questions(self, raw, subj_map, topic_map, exam_track) -> int:
        from questions.models import Question

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
            # Strip any *_code aliases from fields and FK pks (resolved below)
            clean = {
                k: v for k, v in f.items()
                if k not in ("subject", "topic", "subject_code", "topic_name", "exam_track")
            }
            clean["exam_track"] = exam_track
            if pk is not None:
                Question.objects.update_or_create(pk=pk, defaults=clean)
            else:
                # Idempotent dedup — match by (exam_type, content fingerprint)
                # so re-running the loader never duplicates a Question whose
                # stem didn't change. We compute the hash fresh for the lookup
                # because the model's recall_text_hash field is empty for
                # non-recall rows.
                stem = (clean.get("question_text") or "").strip()
                stem_hash = hashlib.sha256(stem.encode("utf-8")).hexdigest()
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
                    if hashlib.sha256(
                        (sib.question_text or "").strip().encode("utf-8")
                    ).hexdigest() == stem_hash:
                        existing = sib
                        break
                if existing is not None:
                    for k, v in clean.items():
                        setattr(existing, k, v)
                    existing.save()
                else:
                    clean["recall_text_hash"] = stem_hash
                    Question.objects.create(
                        subject_id=subj_pk, topic_id=topic_pk, **clean,
                    )
            n += 1
        return n


# Convenience: lets `python manage.py load_exam_fixture` print usage cleanly
# when run with no args.
if __name__ == "__main__":
    pass  # pragma: no cover
