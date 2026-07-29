"""
manage.py verify_rag_index
==========================

Phase 2 (2026-07-29). Read-only health probe for the legacy RAG
SQLite store at `chroma_db/rag_store.sqlite3`.

This command:
  * Opens the existing DB (creates nothing, writes nothing).
  * Runs `PRAGMA integrity_check`.
  * Counts rows in `chunks` and `idf_cache`.
  * Reports chunk count, distinct books, distinct source files,
    DB size, top 20 books, integrity verdict.
  * Exits 0 if HEALTHY, 2 if DEGRADED/CORRUPT, 3 if EMPTY.

NEVER rebuilds, NEVER overwrites, NEVER modifies the index file.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Verify the legacy rag_store.sqlite3 (chroma_db/) is healthy "
        "and report stats. Read-only; never rebuilds or overwrites."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero on DEGRADED status (not just CORRUPT).",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Minimal mode for CI: only print a one-line summary.",
        )

    def handle(self, *args, **options):
        try:
            from ai_engine.rag_pipeline import RAGPipeline
        except Exception as e:
            raise CommandError(f"Cannot import RAGPipeline: {e}")

        # Use the static health probe so this command works even when
        # DISABLE_RAG=1 is set (e.g. operator just wants to verify
        # the DB file is intact before re-enabling RAG).
        health = RAGPipeline.health_check_static()

        if options["check"]:
            # Minimal one-line summary for CI logs
            self.stdout.write(
                f"[RAG HEALTH] status={health['status']} "
                f"chunks={health['chunks']} "
                f"books={health['distinct_books']} "
                f"integrity={health['integrity']} "
                f"db_size_bytes={health['db_size_bytes']}"
            )
        else:
            self._print_full(health)

        # Exit code logic
        status = health["status"]
        if status == "healthy":
            return  # exit 0
        if status == "empty":
            raise CommandError("RAG index is empty. Run `manage.py train_ai` to populate.")
        if status == "corrupt":
            raise CommandError(
                f"RAG index is CORRUPT (integrity={health['integrity']}). "
                "Manual recovery required."
            )
        if status in ("degraded", "error"):
            if options["strict"]:
                raise CommandError(f"RAG index is {status.upper()}: {health.get('error')}")
            self.stderr.write(self.style.WARNING(
                f"RAG index status={status} (continuing; use --strict to fail)"
            ))
            return

    def _print_full(self, health: dict) -> None:
        """Pretty multi-line output for human operators."""
        self.stdout.write(self.style.MIGRATE_HEADING("RAG Index Health Report"))
        self.stdout.write("")
        rows = [
            ("Status", health["status"]),
            ("Backend", health["backend"]),
            ("DB path", health["db_path"]),
            ("DB size", f"{health['db_size_bytes']:,} bytes"),
            ("Integrity", health["integrity"]),
            ("Chunks", f"{health['chunks']:,}"),
            ("Distinct books", f"{health['distinct_books']:,}"),
            ("Distinct source files", f"{health['distinct_source_files']:,}"),
            ("IDF cache terms", f"{health['idf_cache_terms']:,}"),
        ]
        if health["last_indexed_at"]:
            import datetime
            ts = datetime.datetime.fromtimestamp(health["last_indexed_at"])
            rows.append(("Last index mtime", ts.isoformat()))
        if health.get("error"):
            rows.append(("Error", health["error"]))

        for label, value in rows:
            self.stdout.write(f"  {label:<24} {value}")

        if health.get("book_distribution"):
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Top 20 books by chunk count"))
            self.stdout.write("")
            for book, count in list(health["book_distribution"].items())[:20]:
                self.stdout.write(f"  {count:>6}  {book}")

        self.stdout.write("")
        # Final one-line summary (matches --check format)
        self.stdout.write(
            f"[RAG HEALTH] status={health['status']} "
            f"chunks={health['chunks']} "
            f"books={health['distinct_books']} "
            f"integrity={health['integrity']} "
            f"db_size_bytes={health['db_size_bytes']}"
        )
