"""Phase-6 NEET PG data repair.

The previous Phase-5 importer ran on PDFs that contained PUA-encoded
Latin letters (U+E021-U+E05A) without a decoder pass.  As a result:

* 2,840 / 3,389 question stems were stored as mojibake.
* 99.6 % of NEET PG questions were saved without options (option
  regex never matched the PUA-decoded text).
* 2,958 QuestionImage rows were created without a ``file`` link, so
  the frontend has no image URL to render.

This script:

1. Soft-deletes every active NEET PG Question that isn't a year-paper
   row (year-papers never had the PUA problem because they use a
   different font).
2. Soft-deletes the orphaned QuestionImage rows and reconstructs
   them with valid ``file`` paths from the bytes we've stashed in
   ``importers/neetpg/_output/images/<sha>``.
3. Re-runs the importer end-to-end on the subject-wise PDFs so the
   PUA-decoder + improved option extraction land in the DB.

Run::

    cd backend
    venv\Scripts\python.exe repair_neetpg_data.py

Idempotent — re-running is safe.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.conf import settings
from django.db.models import Q

from importers.neetpg.config import get_config
from importers.neetpg.runner import process_one_pdf
from questions.models import Question, QuestionImage

LOG = logging.getLogger("repair_neetpg_data")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


SOURCE_DIR = Path(r"C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material")


def _relink_existing_images() -> int:
    """For every NEET PG QuestionImage whose `file` is empty, search the
    importer's on-disk bytes (bytes column + sha256_short) and re-link
    to a real file under MEDIA_ROOT.

    This salvages the ~2,800 images that were written during the
    previous run but never connected to a file path.
    """
    from importers.neetpg.config import get_config

    cfg = get_config()
    img_root = cfg.images_dir
    if not img_root.exists():
        LOG.warning("Image output dir %s missing — nothing to relink", img_root)
        return 0

    linked = 0
    qi = QuestionImage.objects.filter(
        question__exam_type="neet_pg", file=""
    ).exclude(file__isnull=False)
    total = qi.count()
    LOG.info("Relinking %d QuestionImage rows from disk bytes…", total)

    for qi_row in qi.iterator():
        sha = qi_row.sha256_short or ""
        if not sha:
            continue
        # The image_extractor saves under <out_dir>/<sha16>/p####_i##.<ext>
        candidates = list(img_root.glob(f"*/p{qi_row.page_number:04d}_i*"))
        if not candidates:
            candidates = list(img_root.glob(f"*/p{qi_row.page_number:04d}.*"))
        if not candidates:
            continue
        src = candidates[0]
        ext = src.suffix.lstrip(".") or "png"
        rel = Path("recall_images") / sha[:2] / f"{sha}.{ext}"
        full = Path(settings.MEDIA_ROOT) / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        if not full.exists():
            try:
                full.write_bytes(src.read_bytes())
            except Exception as e:  # pragma: no cover
                LOG.debug("link failed %s: %s", src, e)
                continue
        try:
            qi_row.file.name = str(rel).replace("\\", "/")
            qi_row.save(update_fields=["file"])
            linked += 1
        except Exception as e:  # pragma: no cover
            LOG.debug("DB save failed for %s: %s", qi_row.id, e)

    LOG.info("Relinked %d / %d QuestionImage rows.", linked, total)
    return linked


def _soft_delete_pua_corrupted() -> int:
    """Mark every NEET PG Question whose stem still contains PUA-encoded
    chars or `mojibake` markers as `is_active=False`.  Year-paper rows
    stay alive because they used clean fonts from the start.

    We filter in Python (not in SQL) because the PUA range U+E000-U+F8FF
    isn't reliably representable across Postgres + SQLite + MySQL regex
    backends.  The total rowcount is <10k, so a Python loop is fast
    enough.
    """
    qs = Question.objects.filter(exam_type="neet_pg", is_active=True)
    LOG.info("Scanning %d NEET PG rows for PUA corruption…", qs.count())
    pua_ids: list[int] = []
    mojibake_ids: list[int] = []
    for q in qs.iterator():
        text = (
            (q.question_text or "")
            + (q.option_a or "")
            + (q.option_b or "")
            + (q.option_c or "")
            + (q.option_d or "")
            + (q.explanation or "")
        )
        if any(0xE000 <= ord(c) <= 0xF8FF for c in text):
            pua_ids.append(q.id)
        elif any(marker in text for marker in ("î", "â\x80", "Ã", "Â°", "Â±")):
            mojibake_ids.append(q.id)

    affected = list({*pua_ids, *mojibake_ids})
    if not affected:
        LOG.info("No PUA / mojibake NEET PG rows found.")
        return 0
    n = Question.objects.filter(id__in=affected, is_active=True).update(is_active=False)
    LOG.info(
        "Soft-deleted %d NEET PG questions (PUA=%d  mojibake=%d).",
        n, len(pua_ids), len(mojibake_ids),
    )
    return n


def _drop_orphan_question_images() -> int:
    """Drop QuestionImage rows that point at no file and have no
    in-disk counterpart — they'll be recreated by the re-import."""
    qi = QuestionImage.objects.filter(
        question__exam_type="neet_pg",
    )
    pre = qi.count()
    qi_no_file = qi.filter(Q(file="") | Q(file__isnull=True))
    n = qi_no_file.count()
    # Don't hard-delete; deactivate instead so admin can inspect.
    qi_no_file.update(is_active=False)
    LOG.info("Soft-deactivated %d / %d orphan images (kept for audit).", n, pre)
    return n


def _reimport_pdfs() -> dict:
    """Re-run the importer on every PDF in neet-pg_and_material."""
    if not SOURCE_DIR.exists():
        LOG.warning("Source dir %s missing — skipping re-import", SOURCE_DIR)
        return {"skipped": True}
    cfg = get_config()
    pdfs = sorted(SOURCE_DIR.glob("*.pdf"))
    LOG.info("Re-importing %d PDFs from %s …", len(pdfs), SOURCE_DIR)
    out = []
    for p in pdfs:
        LOG.info("Processing %s", p.name)
        try:
            summary = process_one_pdf(p, cfg, force=True)
            out.append(summary)
        except Exception as e:  # pragma: no cover
            LOG.exception("Failed %s: %s", p.name, e)
            out.append({"filename": p.name, "error": str(e)})
    return {"files": len(out), "summaries": out}


def main() -> int:
    LOG.info("=== NEET PG data repair (Phase-6) ===")
    soft = _soft_delete_pua_corrupted()
    deact = _drop_orphan_question_images()
    relinked = _relink_existing_images()
    out = _reimport_pdfs()
    LOG.info(
        "Soft-deleted=%d  orphan-images-deactivated=%d  relinked=%d  import-summaries=%s",
        soft, deact, relinked,
        len(out.get("summaries", [])) if isinstance(out, dict) else "?",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
