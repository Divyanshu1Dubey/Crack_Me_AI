"""relink_neetpg_images.py — Phase 7 image persistence repair.

After Phase 6 the QuestionImage table has 2,959 rows pointing at sha256
keys but no `file` URL — Django storage had no MEDIA_ROOT to write to.
We now (a) reactivate every QuestionImage, (b) locate the matching
extracted bytes under importers/neetpg/_output/images/<sha>/, (c) copy
them into MEDIA_ROOT/recall_images/<sha[:2]>/<sha>.<ext>, and (d) call
file.save() so the FileField records the relative path.

Run::

    cd backend
    python relink_neetpg_images.py

Idempotent — re-running is safe (overwrites + resets the file link).
"""
from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.files import File  # noqa: E402

from questions.models import QuestionImage  # noqa: E402

LOG = logging.getLogger("neetpg.relink")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
SOURCE_ROOT = Path("importers/neetpg/_output/images")


def _bytes_for_image(pdf_sha16: str, page_number: int, image_index: int, ext_hint: str) -> Path | None:
    """Locate the extracted image at <out>/<pdfsha>/pNNNN_iNN.<ext>.

    The extractor writes `p{page:04d}_i{idx:02d}.{ext}` (image_extractor.py:78),
    so we can find the file deterministically from the (pdf_sha, page, index)
    tuple. We try the hint extension first, then fall back to png/jpg/jpeg/webp.
    """
    if not SOURCE_ROOT.exists():
        return None
    pdf_dir = SOURCE_ROOT / pdf_sha16
    if not pdf_dir.exists():
        return None
    extensions = [ext_hint, "png", "jpg", "jpeg", "webp"]
    for ext in extensions:
        if not ext:
            continue
        candidate = pdf_dir / f"p{int(page_number):04d}_i{int(image_index):02d}.{ext}"
        if candidate.exists() and candidate.is_file():
            return candidate
    # Last resort: any file matching the page+index pattern
    matches = list(pdf_dir.glob(f"p{int(page_number):04d}_i{int(image_index):02d}.*"))
    for m in matches:
        if m.is_file():
            return m
    return None


def relink_one(qi: QuestionImage) -> bool:
    # Skip rows missing the (page, index) coordinates we need.
    if not qi.recall_source_id or qi.page_number is None or qi.image_index_in_page is None:
        return False
    # Find the recall source's PDF sha so we know which directory to look in.
    pdf_sha = getattr(qi.recall_source, "pdf_sha256_short", "") or ""
    if not pdf_sha:
        return False
    mime = qi.mime or "image/png"
    ext_hint = mime.split("/")[-1].lower() if "/" in mime else "png"
    src = _bytes_for_image(pdf_sha, qi.page_number, qi.image_index_in_page, ext_hint)
    if not src:
        return False
    ext = src.suffix.lstrip(".") or "png"
    rel = Path("recall_images") / qi.sha256_short[:2] / f"{qi.sha256_short}.{ext}"
    full = MEDIA_ROOT / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    if not full.exists():
        with open(src, "rb") as r, open(full, "wb") as w:
            w.write(r.read())
    # Drop any prior file then save fresh — idempotent.
    if qi.file:
        try:
            qi.file.delete(save=False)
        except Exception as e:  # pragma: no cover
            LOG.warning("could not drop prior file for QI %s: %s", qi.id, e)
    with open(full, "rb") as f:
        qi.file.save(str(rel).replace("\\", "/"), File(f), save=True)
    qi.is_active = True
    qi.save(update_fields=["is_active", "file"])
    return True


def main() -> int:
    qs = QuestionImage.objects.filter(sha256_short__gt="").order_by("id")
    total = qs.count()
    LOG.info("Relinking %d QuestionImage rows", total)
    linked = 0
    skipped = 0
    for i, qi in enumerate(qs, start=1):
        if relink_one(qi):
            linked += 1
        else:
            skipped += 1
        if i % 200 == 0:
            LOG.info("Progress %d/%d linked=%d skipped=%d", i, total, linked, skipped)
    LOG.info("Done. linked=%d skipped=%d of total=%d", linked, skipped, total)
    return 0


if __name__ == "__main__":
    sys.exit(main())