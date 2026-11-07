"""Put the questions of a pool file into the scholarship challenge (2026-11-07).

    python manage.py apply_scholarship_pool                      # dry run (default): what would change
    python manage.py apply_scholarship_pool --apply              # flag the questions
    python manage.py apply_scholarship_pool --revoke --apply     # take the file's questions out again
    python manage.py apply_scholarship_pool path/to/pool.json    # another pool file

The default file is ``fixtures/scholarship_pool.json``. A question joins only while it still holds the
key and the stem/options the file was reviewed for, and passes ``questions.scholarship_pool.pool_refusal``
(text only, four options, not free showcase, not disputed ...); otherwise it is skipped and named. Only
``is_scholarship_eligible`` is written -- never a key, an explanation or any other field. Prints counts
and question ids only. Admins add or remove single questions in the admin questions editor.
"""
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from questions import scholarship_pool as pool

DEFAULT_FILE = Path(settings.BASE_DIR) / 'fixtures' / 'scholarship_pool.json'


class Command(BaseCommand):
    help = 'Flag the questions of a scholarship pool file as scholarship-challenge questions (dry run by default).'

    def add_arguments(self, parser):
        parser.add_argument('pool_file', nargs='?', default=str(DEFAULT_FILE))
        parser.add_argument('--apply', action='store_true', help='write (default: dry run)')
        parser.add_argument('--revoke', action='store_true', help="take the file's questions out of the challenge")

    def handle(self, *args, **opts):
        from accounts.views import SCHOLARSHIP_QUESTION_COUNT

        try:
            data = pool.load_pool(opts['pool_file'])
        except (OSError, ValueError) as exc:
            raise CommandError(f'pool file: {exc}') from exc
        entries = data['questions']
        mode = 'apply' if opts['apply'] else 'dry run'
        self.stdout.write(f'scholarship pool: {len(entries)} questions in the file ({mode}'
                          f'{", revoke" if opts["revoke"] else ""}); status: {data.get("status") or "-"}')
        before = pool.eligible_count()

        if opts['revoke']:
            from questions.models import Question

            flagged = Question.objects.filter(pk__in=[row['id'] for row in entries], is_scholarship_eligible=True)
            ids = list(flagged.order_by('id').values_list('id', flat=True))
            self.stdout.write(f'  in the challenge now: {len(ids)}')
            if opts['apply']:
                self.stdout.write(f'  removed: {pool.set_eligible(ids, False)}')
                self._report_total(pool.eligible_count(), SCHOLARSHIP_QUESTION_COUNT)
            else:
                self._report_total(before - flagged.filter(is_active=True).count(), SCHOLARSHIP_QUESTION_COUNT, would=True)
                self.stdout.write('  nothing written (dry run); re-run with --apply')
            return

        plan = pool.plan_pool(entries)
        by_action = Counter(row['action'] for row in plan)
        self.stdout.write(f"  to add: {by_action['add']} | already in: {by_action['already']} | skipped: {by_action['skip']}")
        skipped = [row for row in plan if row['action'] == 'skip']
        for reason, count in Counter(row['reason'] for row in skipped).most_common():
            ids = ', '.join(str(row['id']) for row in skipped if row['reason'] == reason)
            text = pool.FILE_SKIPS.get(reason) or pool.REFUSALS.get(reason, reason)
            self.stdout.write(f'  skipped ({reason}, {count}): {ids} -- {text}')
        if opts['apply']:
            changed = pool.set_eligible([row['id'] for row in plan if row['action'] == 'add'], True)
            self.stdout.write(f'  added: {changed}')
            self._report_total(pool.eligible_count(), SCHOLARSHIP_QUESTION_COUNT)
        else:
            self._report_total(before + by_action['add'], SCHOLARSHIP_QUESTION_COUNT, would=True)
            self.stdout.write('  nothing written (dry run); re-run with --apply')

    def _report_total(self, total, needed, would=False):
        verb = 'would be' if would else 'is'
        state = 'can start' if total >= needed else f'stays closed (it needs at least {needed})'
        self.stdout.write(f'  scholarship challenge pool {verb} {total} active questions: the challenge {state}')
