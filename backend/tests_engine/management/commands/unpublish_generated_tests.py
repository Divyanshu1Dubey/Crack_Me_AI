"""List, and on request unpublish, practice tests an admin generated while
generated tests were still published.

Until 2026-11 /generate/, /generate-adaptive/ and /pyq-simulation/ created
published tests, so an admin's own practice runs ("Practice Test — 20
Questions", "AI Adaptive Test — 30 Questions", "UPSC CMS 2019 — Combined
Simulation") still sit in every student's library. Generated tests are now
private to their creator; this finds the old ones by their generator
signature:

  * published and created by an admin / superuser;
  * test_type daily, mixed, adaptive or pyq_year;
  * a generated title ("... — N Questions" or "... Simulation");
  * no curated description (empty, or the generated PYQ-simulation text).

Dry run by default: it only prints the candidates. Review the list, then
re-run with --apply, optionally with --ids to unpublish only the tests you
checked. Unpublishing is reversible (Django admin or the tests "publish"
action) and does not touch attempts or their reviews.

    python manage.py unpublish_generated_tests
    python manage.py unpublish_generated_tests --apply --ids 12,15
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from tests_engine.models import Test

GENERATED_TYPES = ('daily', 'mixed', 'adaptive', 'pyq_year')
GENERATED_TITLE = re.compile(r'( — \d+ Questions| Simulation)$')
GENERATED_DESCRIPTION = re.compile(r'^Full .+ examination simulation with actual PYQ questions\.$')


def generated_library_tests():
    """Published, admin-created tests that look generated, oldest first."""
    candidates = (
        Test.objects.filter(is_published=True, test_type__in=GENERATED_TYPES)
        .filter(Q(created_by__role='admin') | Q(created_by__is_superuser=True))
        .select_related('created_by')
        .order_by('pk')
    )
    found = []
    for test in candidates:
        description = (test.description or '').strip()
        if not GENERATED_TITLE.search((test.title or '').strip()):
            continue
        if description and not GENERATED_DESCRIPTION.match(description):
            continue
        found.append(test)
    return found


class Command(BaseCommand):
    help = 'List (dry run) or unpublish (--apply) admin-generated practice tests left in the student library.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Unpublish the listed tests. Without it nothing is changed.')
        parser.add_argument('--ids', default='',
                            help='Comma-separated test ids: act only on these candidates.')

    def handle(self, *args, **options):
        tests = generated_library_tests()
        if options['ids']:
            try:
                wanted = {int(part) for part in options['ids'].split(',') if part.strip()}
            except ValueError:
                raise CommandError('--ids must be comma-separated test ids')
            unknown = wanted - {test.pk for test in tests}
            if unknown:
                raise CommandError(f'Not generated library tests: {sorted(unknown)}')
            tests = [test for test in tests if test.pk in wanted]

        for test in tests:
            creator = getattr(test.created_by, 'username', '?')
            self.stdout.write(
                f'{test.pk}\t{test.test_type}\t{test.title}\t(by {creator}, {test.created_at:%Y-%m-%d})'
            )
        if not options['apply']:
            self.stdout.write(
                f'{len(tests)} candidate(s). Dry run: nothing changed. '
                'Re-run with --apply (optionally --ids) to unpublish them.'
            )
            return

        updated = Test.objects.filter(pk__in=[test.pk for test in tests], is_published=True).update(
            is_published=False, version=F('version') + 1, updated_at=timezone.now(),
        )
        self.stdout.write(self.style.SUCCESS(f'Unpublished {updated} test(s).'))
