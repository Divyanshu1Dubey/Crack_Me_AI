"""Report which question figures this server can serve (questions.image_health). Read-only.

Run it where the media volume is mounted (the web container), e.g. ``railway ssh`` then
``python manage.py image_health``. Prints counts and image / question ids only.
"""
import json

from django.core.management.base import BaseCommand

from questions.image_health import SOURCES, image_health_report


class Command(BaseCommand):
    help = "Report which question figures this server can serve (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Missing figures to list (default 50)")
        parser.add_argument("--json", action="store_true", help="Print the full report as JSON")

    def handle(self, *args, **options):
        report = image_health_report(sample_limit=max(0, options["limit"]))
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return
        self.stdout.write(
            f"figures: {report['total']} | servable: {report['servable']} | missing: {report['missing']} "
            f"| on other hosts (not checked): {report['external_unchecked']} "
            f"| questions with a missing figure: {report['questions_with_missing_figures']} "
            f"| storage mirror configured: {report['mirror_configured']}"
        )
        for source in SOURCES:
            entry = report["by_source"][source]
            if entry["total"]:
                self.stdout.write(f"  {source:<16} {entry['total']:>6} figures, {entry['missing']:>6} missing")
        for row in report["missing_sample"]:
            self.stdout.write(f"  missing: image {row['image_id']} (question {row['question_id']}, {row['source']})")
        style = self.style.SUCCESS if report["missing"] == 0 else self.style.WARNING
        self.stdout.write(style("No missing figures." if report["missing"] == 0 else
                                f"{report['missing']} figure(s) cannot be served; re-upload them in the editor."))
