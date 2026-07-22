"""One-shot wrapper that:
1. Runs the NEET PG importer synchronously (not via django_q task).
2. Prints summary so stdout is enough to verify.

Usage: venv/Scripts/python.exe run_neetpg_import.py <source_dir>
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from pathlib import Path

from importers.neetpg.runner import process_one_pdf
from importers.neetpg.config import get_config
from questions.models import QuestionImportJob


def main(source_dir: str):
    src = Path(source_dir).absolute()
    if not src.exists():
        raise SystemExit(f"source dir not found: {src}")

    job = QuestionImportJob.objects.create(
        job_type="pdf",
        status="running",
        source_filename=src.name,
        stored_file_path=str(src),
        summary={"source_dir": str(src), "triggered_via": "one-shot script"},
    )
    print(f"Created QuestionImportJob id={job.id}")

    cfg = get_config()
    pdfs = sorted(src.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {src}")
    total = {"questions": 0, "images": 0, "sources": 0, "errors": 0}

    for pdf in pdfs:
        try:
            result = process_one_pdf(pdf, cfg, import_job_id=job.id, force=True)
            q = result.get("question_count", 0)
            i = result.get("image_count", 0)
            total["questions"] += q
            total["images"] += i
            if "db" in result and result["db"].get("sources_created", 0) > 0:
                total["sources"] += 1
            print(f"  [{q:5} Q, {i:3} I] {pdf.name}  ({result.get('elapsed_seconds', 0):.1f}s)")
        except Exception as e:
            total["errors"] += 1
            print(f"  [ERROR      ] {pdf.name}: {type(e).__name__}: {e}")

    job.status = "completed"
    job.summary = dict(job.summary or {}, completed=True, totals=total)
    job.save(update_fields=["status", "summary"])
    print()
    print(f"=== DONE ===")
    print(f"Questions created: {total['questions']}")
    print(f"Images  created : {total['images']}")
    print(f"Sources created : {total['sources']}")
    print(f"Errors          : {total['errors']}")
    print(f"Job id          : {job.id}")
    print(f"Track via       : python manage.py neetpg_status --job-id {job.id}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../neet-pg_and_material")
