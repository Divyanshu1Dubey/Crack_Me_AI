"""`python manage.py neetpg_scan --source-dir <path>`

Walk the source dir, fingerprint every PDF, classify per-page, and
print a summary. Does NOT extract questions.
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...config import get_config
from ... import fingerprints as fp_mod, pdf_reader, classifier as cls_mod


class Command(BaseCommand):
    help = "Scan NEET PG / INI-CET recall PDFs and report page/image stats."

    def add_arguments(self, parser):
        parser.add_argument("--source-dir", type=Path, required=True)

    def handle(self, *args, **opts):
        source_dir: Path = opts["source_dir"]
        if not source_dir.exists():
            raise CommandError(f"source dir not found: {source_dir}")

        cfg = get_config()
        cfg.ensure_dirs()

        pdfs = sorted(source_dir.glob("*.pdf"))
        self.stdout.write(self.style.SUCCESS(f"Found {len(pdfs)} PDFs in {source_dir}"))

        for p in pdfs:
            try:
                doc = pdf_reader.open_pdf(p)
            except pdf_reader.PdfBackendUnavailable as e:
                self.stdout.write(self.style.WARNING(f"  SKIP {p.name}: {e}"))
                continue

            enc = pdf_reader.is_encrypted(doc)
            if enc:
                self.stdout.write(self.style.WARNING(f"  SKIP {p.name}: encrypted"))
                continue

            pages = pdf_reader.page_count(doc)
            meta = pdf_reader.metadata(doc)
            fp = fp_mod.compute_fingerprint(p, pages, enc, meta)
            feats = []
            for page in pdf_reader.iter_pages(doc):
                feats.append(cls_mod.features_for(page.page_number, page.text, page.image_count))
            agg = cls_mod.aggregate(feats)
            self.stdout.write(
                f"  {p.name:55s} pages={pages:4d}  digital={agg['pages_digital']:3d}  "
                f"scanned={agg['pages_scanned']:3d}  hybrid={agg['pages_hybrid']:3d}  "
                f"sha16={fp.pdf_sha256_short}"
            )