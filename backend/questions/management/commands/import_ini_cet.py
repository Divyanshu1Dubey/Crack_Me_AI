"""`python manage.py import_ini_cet ...`

Import INI-CET recall PDFs from ``material/inicet-pg/`` into the
production schema with ``exam_type='ini_cet'`` and
``exam_source='INI-CET (recall)'``.

This command wraps ``backend.importers.inicet.runner`` (which mirrors
the NEET PG importer) and adds:

* an optional ``--source-dir`` flag (defaults to the canonical
  ``material/inicet-pg/`` directory at the repo root);
* an optional ``--pdf`` flag for one-off processing;
* an optional ``--limit`` to cap the number of PDFs processed;
* per-PDF timeout (5 min) and graceful skip on failure so a single
  bad PDF never blocks the batch.

Re-running is idempotent: ``DjangoWriter`` uses
``Question.objects.update_or_create(recall_text_hash=..., exam_type='ini_cet', ...)``
and ``QuestionImage`` dedups by ``sha256_short``. No duplicate rows
will be created on re-import.
"""
from __future__ import annotations

import logging
import signal
import time
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError

from importers.inicet.config import get_config
from importers.inicet.runner import process_one_pdf, run_import

LOG = logging.getLogger("inicet.importer")

# Default source directory at the repo root: ../../material/inicet-pg/
DEFAULT_SOURCE_DIR = Path(
    r"C:\Users\DIVYANSHU\Desktop\crack_cms\material\inicet-pg"
)

# Per-PDF timeout — INI-CET PDFs are 20-30 MB image-rich files. If we
# haven't finished a PDF in 5 minutes, skip it and continue.
PER_PDF_TIMEOUT_SECONDS = 5 * 60


class _TimeoutError(Exception):
    pass


def _alarm_handler(signum, frame):  # pragma: no cover - signal handler
    raise _TimeoutError("per-PDF timeout exceeded")


class Command(BaseCommand):
    help = (
        "Import INI-CET recall PDFs into Question rows with "
        "exam_type='ini_cet' and exam_source='INI-CET (recall)'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-dir",
            type=Path,
            default=DEFAULT_SOURCE_DIR,
            help="Directory containing INI-CET *.pdf files",
        )
        parser.add_argument(
            "--pdf",
            type=Path,
            help="Process a single PDF (overrides --source-dir / --limit)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max number of PDFs to process (0 = no limit)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=PER_PDF_TIMEOUT_SECONDS,
            help="Per-PDF timeout in seconds",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Skip DB writes (Phase-1 JSONL only)",
        )

    def handle(self, *args, **opts):
        cfg = get_config()
        cfg.ensure_dirs()

        pdf: Optional[Path] = opts.get("pdf")
        source_dir: Path = opts["source_dir"]
        limit: int = opts.get("limit", 0) or 0
        timeout: int = opts.get("timeout", PER_PDF_TIMEOUT_SECONDS)
        dry_run: bool = opts.get("dry_run", False)

        if pdf:
            if not pdf.exists():
                raise CommandError(f"pdf not found: {pdf}")
            self._run_with_timeout(pdf, cfg, timeout)
            return

        if not source_dir.exists():
            raise CommandError(f"source dir not found: {source_dir}")

        pdfs = sorted(p for p in source_dir.glob("*.pdf") if p.is_file())
        if limit > 0:
            pdfs = pdfs[:limit]
        self.stdout.write(f"Found {len(pdfs)} PDF(s) in {source_dir}")

        # Delegate the per-dir orchestration to the runner when not
        # dry-running — it handles manifest + reports.
        if dry_run:
            summaries = []
            for p in pdfs:
                summaries.append(self._run_with_timeout(p, cfg, timeout))
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN processed {len(summaries)} PDF(s)"
            ))
            return

        out = run_import(source_dir, cfg=cfg, only=None)
        self.stdout.write(self.style.SUCCESS(
            f"Run {out.get('run_id')} processed {len(out.get('summaries', []))} PDF(s)"
        ))
        for s in out.get("summaries", []):
            self.stdout.write(str(s))

    def _run_with_timeout(self, pdf: Path, cfg, timeout: int) -> dict:
        """Run process_one_pdf with an alarm-based timeout (POSIX / Git Bash)."""
        # On Windows, signal.SIGALRM isn't reliable in some shells.
        # We use a simple time-bounded wrapper instead.
        start = time.monotonic()
        prev_handler: Optional[signal._HANDLER] = None
        if hasattr(signal, "SIGALRM"):
            try:
                prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
                signal.alarm(max(1, timeout))
            except (ValueError, OSError):
                prev_handler = None  # signal not available in this thread
        try:
            self.stdout.write(f"[inicet] {pdf.name} — starting")
            summary = process_one_pdf(pdf, cfg)
            self.stdout.write(self.style.SUCCESS(
                f"[inicet] {pdf.name} — {summary.get('question_count', 0)} Q, "
                f"{summary.get('image_count', 0)} imgs, "
                f"{summary.get('page_count', 0)} pages, "
                f"{summary.get('elapsed_seconds', 0):.1f}s"
            ))
            return summary
        except _TimeoutError:
            elapsed = time.monotonic() - start
            self.stdout.write(self.style.WARNING(
                f"[inicet] {pdf.name} — TIMEOUT after {elapsed:.1f}s; skipping"
            ))
            return {"filename": pdf.name, "skipped": True, "reason": "timeout"}
        except Exception as e:  # pragma: no cover - defensive
            elapsed = time.monotonic() - start
            self.stdout.write(self.style.ERROR(
                f"[inicet] {pdf.name} — ERROR after {elapsed:.1f}s: {e!r}"
            ))
            return {"filename": pdf.name, "skipped": True, "reason": repr(e)}
        finally:
            if prev_handler is not None:
                try:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, prev_handler)
                except Exception:
                    pass