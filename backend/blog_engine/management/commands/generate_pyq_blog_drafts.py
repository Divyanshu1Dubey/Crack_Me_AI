"""Blog drafts from the question bank (blog_engine/pyq_drafts.py): one per UPSC CMS paper and one per clinical term
UPSC CMS asks often. Unpublished, marked "not reviewed"; an editor reviews and publishes them at /admin/blog. A slug is
created once: a draft an editor deleted is not created again. Dry run unless --apply; a release step.

  python manage.py generate_pyq_blog_drafts             # what would be created
  python manage.py generate_pyq_blog_drafts --apply
"""
from django.core.management.base import BaseCommand

from blog_engine.pyq_drafts import MIN_QUESTIONS, build_drafts, save_drafts


class Command(BaseCommand):
    help = 'Create unpublished blog drafts (paper analyses, topic-wise PYQs) from the question bank.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='create the drafts (default: dry run)')
        parser.add_argument('--min-questions', type=int, default=MIN_QUESTIONS,
                            help='a topic draft needs at least this many questions')

    def handle(self, *args, **opts):
        drafts = build_drafts(min_questions=max(1, opts['min_questions']))
        stats = save_drafts(drafts, apply=opts['apply'])
        mode = 'applied' if opts['apply'] else 'dry run'
        self.stdout.write(f'generate_pyq_blog_drafts ({mode}): {len(drafts)} draft(s) built; '
                          + ', '.join(f'{k} {v}' for k, v in sorted(stats.items())))
