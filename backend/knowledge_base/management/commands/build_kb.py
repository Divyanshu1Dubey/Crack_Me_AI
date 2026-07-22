"""
python manage.py build_kb [--max N] [--model NAME] [--skip-extract]

Full knowledge-base build:
1. Load ontology + whitelisted sources
2. Ingest internal notes
3. Backfill embeddings
4. (optional) Run KG extractor

Idempotent. Designed to run after `migrate` on first deploy.
"""

from django.core.management.base import BaseCommand

from knowledge_base.ontology.loader import load_ontology
from knowledge_base.services.ingestion import IngestionService
from knowledge_base.connectors.internal import InternalNotesConnector
from knowledge_base.services.indexer import EmbeddingIndexer


class Command(BaseCommand):
    help = "Build the knowledge base end-to-end (ontology + internal notes + embeddings)."

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=2000,
                            help="Cap chunks per ingestion run")
        parser.add_argument("--model", default="bge-small-en-v1.5",
                            help="Embedding model")
        parser.add_argument("--skip-extract", action="store_true")
        parser.add_argument("--skip-internal", action="store_true")

    def handle(self, *args, **opts):
        self.stdout.write("→ Loading ontology…")
        result = load_ontology()
        self.stdout.write(self.style.SUCCESS(
            f"  +{result['entities_added']} entities, "
            f"+{result['relations_added']} relations, "
            f"+{result['sources_added']} sources  "
            f"(total: {result['total_entities']} entities, "
            f"{result['total_relations']} relations, "
            f"{result['total_sources']} sources — "
            f"0+ means data already present, not failure)"
        ))

        if not opts["skip_internal"]:
            self.stdout.write("→ Ingesting internal notes…")
            service = IngestionService(InternalNotesConnector())
            r = service.run(max_chunks=opts["max"])
            self.stdout.write(self.style.SUCCESS(
                f"  +{r.chunks_added} added, "
                f"~{r.chunks_updated} updated, "
                f"-{r.chunks_rejected} rejected"
            ))

        self.stdout.write(f"→ Indexing embeddings (model={opts['model']})…")
        try:
            indexed = EmbeddingIndexer().index_pending(
                max_chunks=opts["max"], model=opts["model"],
            )
            self.stdout.write(self.style.SUCCESS(f"  +{indexed} chunks embedded"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  embedding step failed: {e}"))

        if not opts["skip_extract"]:
            self.stdout.write("→ Extracting knowledge-graph relations…")
            try:
                from knowledge_base.retrieval.kg_extractor import KGExtractor
                r = KGExtractor().extract_all()
                self.stdout.write(self.style.SUCCESS(
                    f"  +{r['new_entities']} entities, +{r['new_relations']} relations"
                ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  KG extraction failed: {e}"))

        self.stdout.write(self.style.SUCCESS("Done."))