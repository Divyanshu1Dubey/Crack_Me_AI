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
        for r in result["results"][:5]:
            mark = "✓" if r["ok"] else "✗"
            self.stdout.write(
                f"  {mark} [{r['confidence']}] {r['query'][:70]}\n"
                f"     sources={r['source_hits']} keywords={r['keyword_hits']}"
            )