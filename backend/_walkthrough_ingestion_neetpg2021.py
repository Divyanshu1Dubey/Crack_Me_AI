"""End-to-end visual-integration walkthrough for Phase 1.

Run this script while the dev server (runserver) and Q-cluster (qcluster)
are running. It will:

1. Upload the NEET PG 2021 benchmark PDF via the production MaterialAsset
   code path (sha256 + page_count + storage_path).
2. Create an ImportJob (queue via django-q2).
3. Wait for the orchestrator to run end-to-end.
4. Print the PR/NR/EF verdicts + persisted counts that the user can then
   inspect in the browser at /admin/ingestion/jobs/<id>/.

Usage:
    python _walkthrough_ingestion_neetpg2021.py
"""
import os
import sys
import time
import hashlib
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
import django
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from ingestion.models import MaterialAsset, BatchRun, ImportJob, ImportJobStage, ImportLog, ImportCheckpoint, StagedQuestion
from ingestion.tasks import dispatch_job
from importers.neetpg.pdf_reader import open_pdf, page_count


PDF = Path(r"C:\Users\DIVYANSHU\Desktop\crack_cms\material\neet-pg\NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def get_admin():
    User = get_user_model()
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        raise SystemExit("No superuser found. Run createsuperuser first.")
    return admin


def step(label):
    print(f"\n{'=' * 60}\n  {label}\n{'=' * 60}")


def main():
    if not PDF.exists():
        raise SystemExit(f"PDF not found: {PDF}")

    step("STEP 1: Compute sha256 + page count for the NEET PG 2021 benchmark PDF")
    sha = sha256_file(PDF)
    sha16 = sha[:16]
    print(f"sha256:      {sha}")
    print(f"sha256_short:{sha16}")
    print(f"file size:   {PDF.stat().st_size:,} bytes")

    doc = open_pdf(str(PDF))
    try:
        pages = int(page_count(doc))
    finally:
        doc.close()
    print(f"page count:  {pages}")

    step("STEP 2: Create MaterialAsset (idempotent on sha256)")
    storage_path = str(PDF)
    asset, created = MaterialAsset.objects.update_or_create(
        sha256=sha,
        defaults={
            'sha256_short': sha16,
            'original_filename': PDF.name,
            'storage_path': storage_path,
            'file_size': PDF.stat().st_size,
            'page_count': pages,
            'exam_hint': 'neet_pg',
            'is_active': True,
        },
    )
    print(f"MaterialAsset id={asset.id}  created={created}  sha16={asset.sha256_short}")

    step("STEP 3: Create ImportJob (config: auto-pr-only, conservative gate)")
    admin = get_admin()
    job = ImportJob.objects.create(
        material_asset=asset,
        parent_exam='neet_pg',
        status='queued',
        version=1,
        total_pages=pages,
        config={'strategy': 'auto-pr-only', 'force': False},
        created_by=admin,
    )
    print(f"ImportJob id={job.id}  status={job.status}  parent_exam={job.parent_exam}")

    step("STEP 4: Dispatch to django-q2 (ingestion.tasks.run_import_job)")
    task_id = dispatch_job(job.id)
    print(f"Q-cluster task id={task_id}")

    step("STEP 5: Poll orchestrator status (max 10 min)")
    t0 = time.time()
    last_status = None
    while time.time() - t0 < 600:
        job.refresh_from_db()
        if job.status != last_status:
            print(f"  [{int(time.time()-t0)}s] status={job.status}  stage={job.current_stage}  page={job.current_page}/{job.total_pages}  progress={job.progress_pct:.1f}%")
            last_status = job.status
        if job.status in ('completed', 'failed', 'crashed', 'cancelled'):
            break
        time.sleep(5)

    job.refresh_from_db()
    print(f"\nFinal status: {job.status}")
    print(f"current_stage: {job.current_stage}")
    print(f"progress_pct:  {job.progress_pct}")
    print(f"PR pct:        {job.qa_v2_production_ready_pct}")
    print(f"NR pct:        {job.qa_v2_needs_review_pct}")
    print(f"EF pct:        {job.qa_v2_extraction_failure_pct}")
    print(f"qa_v2 total:   {job.qa_v2_total_questions}")
    print(f"questions_imported (PR): {job.questions_imported}")
    print(f"questions_staged_nr:     {job.questions_staged_nr}")
    print(f"questions_staged_ef:     {job.questions_staged_ef}")

    step("STEP 6: Per-stage timeline (ImportJobStage rows)")
    for s in ImportJobStage.objects.filter(job=job).order_by('started_at'):
        print(f"  {s.stage_name:<28} {s.status:<10} pages={s.pages_processed}/{s.pages_skipped}  artefacts={s.artefacts_written}  warnings={len(s.warnings or [])}")

    step("STEP 7: Latest checkpoint")
    ck = ImportCheckpoint.objects.filter(job=job).order_by('-version').first()
    if ck:
        print(f"  version={ck.version}  last_completed_stage={ck.last_completed_stage}  last_processed_page={ck.last_processed_page}  current_page={ck.current_page}  artifact_root={ck.artifact_root}")

    step("STEP 8: Staged questions (NR + EF)")
    n_n = StagedQuestion.objects.filter(job=job, qa_status='Needs Review').count()
    n_e = StagedQuestion.objects.filter(job=job, qa_status='Extraction Failure').count()
    print(f"  Needs Review (NR):     {n_n}")
    print(f"  Extraction Failure (EF): {n_e}")

    step("STEP 9: Recent logs")
    for log in ImportLog.objects.filter(job=job).order_by('-created_at')[:10]:
        print(f"  [{log.level}] {log.stage_name or '':32} {log.message[:120]}")

    step("STEP 10: Print URLs the user can open in the browser")
    print(f"  http://localhost:3000/admin/ingestion/jobs/{job.id}/")
    print(f"  http://localhost:3000/admin/ingestion/jobs/{job.id}/stages/")
    print(f"  http://localhost:3000/admin/ingestion/jobs/{job.id}/logs/")
    print(f"  http://localhost:3000/admin/ingestion/jobs/{job.id}/checkpoints/")


if __name__ == '__main__':
    main()
