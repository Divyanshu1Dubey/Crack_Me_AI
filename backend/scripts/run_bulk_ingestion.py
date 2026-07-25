"""run_bulk_ingestion.py

This script scans the `material/inicet-pg` and `material/neet-pg` directories,
uploads the PDFs into the backend as `MaterialAsset` entries, and then queues
them up as BatchRuns in the ingestion pipeline.

Usage:
  python manage.py shell < scripts/run_bulk_ingestion.py
  (or `python scripts/run_bulk_ingestion.py` if Django is bootstrapped)
"""

import os
import sys
import hashlib
from pathlib import Path
import django
from django.conf import settings

# Bootstrap Django if run as a standalone script
if not settings.configured:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
    django.setup()

from ingestion.models import MaterialAsset, BatchRun, ImportJob, _default_config
from ingestion.views import _page_count
from ingestion.tasks import dispatch_job

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def ingest_directory(directory_path: Path, exam_hint: str):
    if not directory_path.exists():
        print(f"Directory {directory_path} does not exist.")
        return

    pdfs = list(directory_path.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {directory_path}")
        return

    media_root = Path(settings.MEDIA_ROOT)
    upload_dir = media_root / "ingestion_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    materials = []
    print(f"Processing {len(pdfs)} PDFs in {directory_path} for exam {exam_hint}...")

    for pdf in pdfs:
        print(f"  -> Hashing {pdf.name}...")
        full_hash = _sha256_file(pdf)
        sha16 = full_hash[:16]
        
        final_dir = upload_dir / sha16
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / pdf.name

        if not final_path.exists():
            import shutil
            shutil.copy2(pdf, final_path)

        page_count = _page_count(final_path)

        asset, created = MaterialAsset.objects.update_or_create(
            sha256=full_hash,
            defaults={
                "sha256_short": sha16,
                "original_filename": pdf.name,
                "storage_path": str(final_path),
                "file_size": final_path.stat().st_size,
                "page_count": page_count,
                "exam_hint": exam_hint,
                "is_active": True,
            },
        )
        if created:
            print(f"     [NEW] Created MaterialAsset for {pdf.name} (sha16: {sha16})")
        else:
            print(f"     [EXISTS] Found existing MaterialAsset for {pdf.name} (sha16: {sha16})")
        
        materials.append(asset)
    
    # Create BatchRun
    batch_name = f"Bulk Import - {exam_hint.upper()} - {len(materials)} files"
    batch = BatchRun.objects.create(
        name=batch_name,
        status="running",
        total_jobs=len(materials),
        completed_jobs=0,
        failed_jobs=0,
    )
    print(f"\nCreated BatchRun {batch.id}: {batch_name}")

    # Create ImportJobs and dispatch
    for material in materials:
        config = _default_config()
        # Ensure extraction force if needed, but default is auto-pr-only
        job = ImportJob.objects.create(
            batch_run=batch,
            material_asset=material,
            config=config,
            status="queued"
        )
        task_id = dispatch_job(job.id)
        
        job.summary = {"q_task_id": task_id, "dispatched_at": str(django.utils.timezone.now())}
        job.save(update_fields=["summary"])
        print(f"  -> Queued Job {job.id} for {material.original_filename}")
        
    print(f"Finished queuing {len(materials)} jobs for {exam_hint}.\n")


def main():
    base_dir = Path(r"C:\Users\DIVYANSHU\Desktop\crack_cms\material")
    
    # 1. INI-CET
    inicet_dir = base_dir / "inicet-pg"
    ingest_directory(inicet_dir, "inicet")

    # 2. NEET PG
    neetpg_dir = base_dir / "neet-pg"
    ingest_directory(neetpg_dir, "neetpg")


if __name__ == "__main__":
    main()
