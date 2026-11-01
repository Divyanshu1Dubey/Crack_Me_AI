"""
python manage.py evaluate_kb [--max N]
"""
from django.core.management.base import BaseCommand

from knowledge_base.eval.harness import run_evaluation


class Command(BaseCommand):
    help = "Run the knowledge-base golden test-set evaluation."

    def add_arguments(self, parser):
        parser.add_argument("--max", type=int, default=None)

    def handle(self, *args, **opts):
        result = run_evaluation(max_cases=opts["max"])
        self.stdout.write(self.style.SUCCESS(
            f"Eval #{result['eval_run_id']}: "
            f"R@5={result['recall_at_5']:.2f} "
            f"R@10={result['recall_at_10']:.2f} "
            f"MRR={result['mrr']:.2f} "
            f"CiteAcc={result['citation_accuracy']:.2f} "
            f"(N={result['testcases_total']})"
        ))
        if result.get("errors"):
            self.stdout.write(self.style.WARNING(
                f"  {result['errors']} case(s) had no AI answer (provider outage or "
                f"AI_OFFLINE_MODE); they count as failures above."
            ))
        for r in result["results"][:5]:
            mark = "✓" if r["ok"] else "✗"
            note = f" ({r['error']})" if r.get("error") else ""
            self.stdout.write(
                f"  {mark} [{r['confidence']}] {r['query'][:70]}{note}\n"
                f"     sources={r['source_hits']} keywords={r['keyword_hits']}"
            )