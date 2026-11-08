"""AI explanations for the questions that have none (questions/explanation_batch.py, docs/EXPLANATION_BATCH.md).

  python manage.py generate_explanations --count                      # how many need one, by exam (writes nothing)
  python manage.py generate_explanations --create [--exam cms] [--years 2018,2019] [--no-stale] [--limit 500]
  python manage.py generate_explanations --run 3 [--max 200] [--sleep 1.5]   # process (resumable, any time)
  python manage.py generate_explanations --status 3

Explanations are saved only when the AI's own answer is the stored key, without any citation the model made up,
as "AI-generated, not yet reviewed" (the admin review queue at /admin/explanations). Needs the AI provider keys;
refuses to run with AI_OFFLINE_MODE on.
"""
from django.core.management.base import BaseCommand, CommandError

from questions import explanation_batch as batch


class Command(BaseCommand):
    help = 'Batch AI explanations for questions without one (resumable; saved for review).'

    def add_arguments(self, parser):
        parser.add_argument('--count', action='store_true', help='count the questions that need one')
        parser.add_argument('--create', action='store_true', help='create a run of the questions that need one')
        parser.add_argument('--exam', default='', help='exam_type (cms, neet_pg, ini_cet ...)')
        parser.add_argument('--years', default='', help='comma-separated years')
        parser.add_argument('--no-stale', action='store_true', help='leave explanations written for another key')
        parser.add_argument('--limit', type=int, default=0, help='at most this many questions in the run')
        parser.add_argument('--note', default='')
        parser.add_argument('--run', type=int, default=0, help='process this run')
        parser.add_argument('--max', type=int, default=0, help='process at most this many questions now')
        parser.add_argument('--sleep', type=float, default=1.0, help='seconds between questions (provider limits)')
        parser.add_argument('--status', type=int, default=0, help='show this run')

    def handle(self, *args, **opts):
        from questions.models import ExplanationBatchRun

        years = [int(y) for y in opts['years'].split(',') if y.strip()] if opts['years'] else None
        if opts['count']:
            by_exam = batch.needed_by_exam(exam_type=opts['exam'] or None, years=years,
                                           include_stale=not opts['no_stale'])
            self.stdout.write(f"questions needing an explanation: {sum(by_exam.values())} {by_exam}")
            return
        if opts['create']:
            run = batch.create_run(exam_type=opts['exam'] or None, years=years, include_stale=not opts['no_stale'],
                                   limit=opts['limit'] or None, note=opts['note'])
            self.stdout.write(f'run {run.pk}: {run.items.count()} question(s) queued')
            return
        if opts['run']:
            run = ExplanationBatchRun.objects.filter(pk=opts['run']).first()
            if run is None:
                raise CommandError(f"no run {opts['run']}")
            stats = batch.run_batch(run, max_items=opts['max'] or None, sleep_seconds=max(0.0, opts['sleep']),
                                    log=lambda line: self.stdout.write('  ' + line))
            self.stdout.write(f'run {run.pk}: ' + ', '.join(f'{k} {v}' for k, v in stats.items()))
            self.stdout.write(f"  now: {batch.run_summary(run)['counts']}")
            return
        if opts['status']:
            run = ExplanationBatchRun.objects.filter(pk=opts['status']).first()
            if run is None:
                raise CommandError(f"no run {opts['status']}")
            self.stdout.write(str(batch.run_summary(run)))
            return
        raise CommandError('Use --count, --create, --run ID or --status ID (see --help).')
