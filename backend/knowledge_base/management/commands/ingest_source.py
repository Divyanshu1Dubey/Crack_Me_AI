"""
python manage.py ingest_source <connector> [kwargs...]

Examples:
  python manage.py ingest_source internal-notes
  python manage.py ingest_source ncbi-bookshelf --query "hypertension" --max 25
  python manage.py ingest_source openstax-microbiology
  python manage.py ingest_source upsc
  python manage.py ingest_source user-uploads
"""

from django.core.management.base import BaseCommand, CommandError

from knowledge_base.services.ingestion import IngestionService
from knowledge_base.connectors.internal import InternalNotesConnector
from knowledge_base.connectors.ncbi import (
    NCBIBookshelfConnector,
    OpenStaxConnector,
    OpenStaxMicrobiologyConnector, OpenStaxPsychologyConnector,
    UPSCConnector, NHMConnector, MoHFWConnector, ICMRConnector, NMCConnector,
)
from knowledge_base.connectors.user_uploads import UserUploadsConnector


CONNECTORS = {
    "internal-notes": (InternalNotesConnector, {}),
    "ncbi-bookshelf": (NCBIBookshelfConnector, {"query": "", "max_records": 25, "db": "books"}),
    "openstax-anatomy": (
        OpenStaxConnector,
        {"max_chapters": 50},
    ),
    "openstax-microbiology": (
        OpenStaxMicrobiologyConnector,
        {"max_chapters": 50},
    ),
    "openstax-psychology": (
        OpenStaxPsychologyConnector,
        {"max_chapters": 50},
    ),
    "upsc": (UPSCConnector, {}),
    "nhm-india": (NHMConnector, {}),
    "mohfw-india": (MoHFWConnector, {}),
    "icmr": (ICMRConnector, {}),
    "nmc-india": (NMCConnector, {}),
    "user-uploads": (UserUploadsConnector, {}),
}


class Command(BaseCommand):
    help = "Run a knowledge-base connector and ingest its chunks."

    def add_arguments(self, parser):
        parser.add_argument("connector", choices=sorted(CONNECTORS.keys()))
        parser.add_argument("--query", default=None)
        parser.add_argument("--max", type=int, default=None,
                            help="Cap number of chunks written")
        parser.add_argument("--max-records", type=int, default=25)
        parser.add_argument("--max-chapters", type=int, default=50)
        parser.add_argument("--db", default="books",
                            choices=["books", "pmc"])

    def handle(self, *args, **opts):
        name = opts["connector"]
        cls, defaults = CONNECTORS[name]
        kwargs = dict(defaults)
        if opts.get("query") is not None:
            kwargs["query"] = opts["query"]
        if opts.get("max_records") and "max_records" in kwargs:
            kwargs["max_records"] = opts["max_records"]
        if opts.get("max_chapters") and "max_chapters" in kwargs:
            kwargs["max_chapters"] = opts["max_chapters"]
        if "db" in kwargs and opts.get("db"):
            kwargs["db"] = opts["db"]

        connector = cls()
        service = IngestionService(connector)
        try:
            result = service.run(max_chunks=opts.get("max"), **kwargs)
        except Exception as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f"Ingested {result.source_slug}: "
            f"+{result.chunks_added} added, "
            f"~{result.chunks_updated} updated, "
            f"-{result.chunks_rejected} rejected, "
            f"status={result.status}"
        ))