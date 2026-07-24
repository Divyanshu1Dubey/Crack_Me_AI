"""ingestion_purge_old_artefacts — Phase 7 cold-storage stub.

Phase 1 ships this as a no-op so the management interface is
frozen. When Phase 7 lands, the body will:
  1. List <INGESTION_ARTEFACT_ROOT>/<sha16>/ directories.
  2. For each older than ``--max-age-days``: tar + upload to cold
     storage; remove local copies; keep ImportArtifact rows.

Until then it just prints what it would do.
"""
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Phase 7 stub: list candidate artefact directories eligible for cold-storage."

    def add_arguments(self, parser):
        parser.add_argument("--max-age-days", type=int, default=90)

    def handle(self, *args, **opts):
        root = Path(getattr(settings, "INGESTION_ARTEFACT_ROOT",
                            Path(settings.BASE_DIR) / "_artifacts_ingestion"))
        if not root.exists():
            self.stdout.write(f"No artefact root at {root}; nothing to do.")
            return
        cutoff = time.time() - opts["max_age_days"] * 86400
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            mtime = child.stat().st_mtime
            if mtime < cutoff:
                self.stdout.write(self.style.WARNING(
                    f"[stub] would purge {child} (age {(time.time()-mtime)/86400:.1f} days)"
                ))
            else:
                self.stdout.write(f"[keep] {child}")
