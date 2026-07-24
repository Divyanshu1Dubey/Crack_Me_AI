"""Post-import image-fix for ALL 2021 NEET PG questions (v2).

Walk ``QuestionSource`` rows for the 2021 PDF (sha16
"8ebea8995a4ade79") instead of the Question table itself. Each
``QuestionSource`` links precisely (recall_source, page_number,
question_number_in_pdf) → Question — that's the join we need to attach
MCE ``image_ids`` to the correct Question + RecallSource.

Idempotent. Usage::

    cd backend && python _fix_neetpg2021_images_v2.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")

import django

django.setup()

from django.conf import settings

from ingestion.models import ImportJob
from questions.models import Question, QuestionImage, QuestionSource, RecallSource

JOB_ID = 1
SHA16 = "8ebea8995a4ade79"
ARTEFACT_ROOT = Path(settings.BASE_DIR) / "_artifacts_ingestion" / SHA16
IMAGES_SRC = ARTEFACT_ROOT / "03_images"
MEDIA_DIR = Path(settings.MEDIA_ROOT)
RECALL_IMAGES_DIR = MEDIA_DIR / "recall_images" / "2026" / "07"
RECALL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _stage7_payloads(artefact_root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    sd = artefact_root / "07_structured"
    if not sd.exists():
        return out
    for f in sorted(sd.glob("p*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for q in data.get("questions") or []:
            if isinstance(q, dict) and q.get("id"):
                out[q["id"]] = q
    return out


def _find_image_file(image_id: str) -> Path | None:
    if not image_id:
        return None
    for ext in ("png", "jpeg", "jpg"):
        cand = IMAGES_SRC / f"{image_id}.{ext}"
        if cand.exists():
            return cand
    parts = image_id.split("_")
    if len(parts) >= 3:
        prefix = "_".join(parts[:2])
        for ext in ("png", "jpeg", "jpg"):
            cand = IMAGES_SRC / f"{prefix}.{ext}"
            if cand.exists():
                return cand
    return None


def _dest_path(image_id: str, src: Path) -> Path:
    suffix = src.suffix.lower()
    safe_id = "".join(c if c.isalnum() else "_" for c in image_id)
    return RECALL_IMAGES_DIR / f"{safe_id}{suffix}"


def _rel_url(p: Path) -> str:
    return str(p.relative_to(MEDIA_DIR)).replace("\\", "/")


def main() -> None:
    job = ImportJob.objects.filter(id=JOB_ID).select_related("material_asset").first()
    if job is None:
        raise SystemExit(f"ImportJob#{JOB_ID} not found.")
    asset = job.material_asset

    rs = RecallSource.objects.filter(pdf_sha256=asset.sha256).first()
    if rs is None:
        rs = RecallSource.objects.create(
            pdf_filename=asset.original_filename,
            pdf_path=asset.storage_path,
            pdf_sha256=asset.sha256,
            pdf_sha256_short=asset.sha256_short,
            pdf_size_bytes=asset.file_size,
            page_count=asset.page_count or 0,
            scan_type="digital",
            recall_status="recall",
            is_active=True,
        )

    s7 = _stage7_payloads(ARTEFACT_ROOT)
    print(f"Stage 7 payloads: {len(s7)}")

    # Build (page_number, question_number_in_pdf) → payload index
    payload_by_pk: dict[tuple[int, int], dict] = {}
    for qid, payload in s7.items():
        pg = int(payload.get("page_number") or 0)
        qno = int(payload.get("question_number_in_pdf") or 0)
        if pg and qno:
            payload_by_pk[(pg, qno)] = payload

    # All QuestionSource rows for this PDF
    qsrcs = QuestionSource.objects.filter(recall_source=rs).select_related("question")
    print(f"QuestionSource rows for 2021 PDF: {qsrcs.count()}")

    n_total = qsrcs.count()
    n_with_images = 0
    n_files_copied = 0
    n_qimages_created = 0
    n_qimages_existing = 0
    n_questions_marked = 0
    n_missing = 0

    for qsrc in qsrcs:
        payload = payload_by_pk.get((qsrc.page_number, qsrc.question_number_in_pdf or 0))
        if payload is None:
            continue
        img_ids = list(payload.get("image_ids") or [])
        for o in (payload.get("options") or []):
            if isinstance(o, dict):
                for oid in (o.get("image_ids") or []):
                    if oid not in img_ids:
                        img_ids.append(oid)
        if not img_ids:
            continue
        n_with_images += 1
        question = qsrc.question

        primary_dest: Path | None = None
        for idx, img_id in enumerate(img_ids):
            src = _find_image_file(img_id)
            if src is None:
                n_missing += 1
                continue
            dest = _dest_path(img_id, src)
            if not dest.exists():
                shutil.copy2(src, dest)
                n_files_copied += 1
            rel = _rel_url(dest)
            try:
                file_size = dest.stat().st_size
                sha = hashlib.sha256(dest.read_bytes()).hexdigest()
            except OSError:
                continue

            existing = QuestionImage.objects.filter(
                question=question, sha256_short=sha[:16],
            ).first()
            if existing is not None:
                n_qimages_existing += 1
                if idx == 0 and not question.page_screenshot:
                    primary_dest = Path(settings.MEDIA_ROOT) / existing.file.name
                continue
            try:
                qi = QuestionImage.objects.create(
                    question=question,
                    recall_source=rs,
                    page_number=qsrc.page_number,
                    image_index_in_page=idx,
                    file=rel,
                    mime="image/png" if dest.suffix.lower() == ".png" else "image/jpeg",
                    bytes=file_size,
                    sha256=sha,
                    sha256_short=sha[:16],
                    role="primary" if idx == 0 else "illustration",
                    modality="other",
                    is_active=True,
                )
                n_qimages_created += 1
            except Exception as e:
                print(f"  [WARN] failed to create QuestionImage for Q{question.id} img={img_id}: {e}")
                continue
            if idx == 0 and primary_dest is None:
                primary_dest = dest

        changed = []
        if not question.is_image_based:
            question.is_image_based = True
            changed.append("is_image_based")
        if primary_dest is not None and not question.page_screenshot:
            question.page_screenshot = _rel_url(primary_dest)
            changed.append("page_screenshot")
        if changed:
            question.save(update_fields=changed + ["updated_at"])
            n_questions_marked += 1

    print()
    print(f"=== Summary (v2 — via QuestionSource) ===")
    print(f"  QuestionSource rows scanned:       {n_total}")
    print(f"  With image_ids:                    {n_with_images}")
    print(f"  Files copied to media/:            {n_files_copied}")
    print(f"  QuestionImage rows created:        {n_qimages_created}")
    print(f"  QuestionImage rows already linked: {n_qimages_existing}")
    print(f"  Questions marked is_image_based:   {n_questions_marked}")
    print(f"  Image artefacts missing on disk:   {n_missing}")
    total_img = Question.objects.filter(exam_type="neet_pg", is_image_based=True).count()
    total_qimg = QuestionImage.objects.filter(recall_source=rs).count()
    print(f"\n[after-fix] is_image_based=True count: {total_img}")
    print(f"[after-fix] QuestionImage rows for 2021: {total_qimg}")


if __name__ == "__main__":
    main()
