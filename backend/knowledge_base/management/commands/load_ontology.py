"""
python manage.py load_ontology [--reset]
"""
from django.core.management.base import BaseCommand

from knowledge_base.ontology.loader import load_ontology


class Command(BaseCommand):
    help = "Load the curated UPSC-CMS ontology + whitelisted sources into the KB."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing entities/relations before loading.")

    def handle(self, *args, **opts):
        result = load_ontology(reset=opts["reset"])
        self.stdout.write(self.style.SUCCESS(
            f"Loaded ontology: +{result['entities_added']} entities, "
            f"+{result['relations_added']} relations, "
            f"+{result['sources_added']} sources"
        ))
        self.stdout.write(
            f"Totals: {result['total_entities']} entities, "
            f"{result['total_relations']} relations, "
            f"{result['total_sources']} sources"
        )