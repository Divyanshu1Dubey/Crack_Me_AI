"""
fix_embedded_options — One-shot data fix for the 2026-07-30 parser bug
where 6 questions in cms_fixture.json pk 6359..6438 have their options
embedded into question_text and option_a..d blank.

DRY-RUN by default. Pass --apply to commit the change.

Idempotent: rows with non-blank option_a are skipped.

Usage:
    python manage.py fix_embedded_options              # dry-run
    python manage.py fix_embedded_options --apply      # commit
"""
from django.core.management.base import BaseCommand
from questions.models import Question


class Command(BaseCommand):
    help = "Repair questions whose options are embedded into question_text."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Commit changes (default: dry-run).')
        parser.add_argument('--pks', type=int, nargs='*', help='Restrict to these Question pks.')

    def handle(self, *args, apply=False, pks=None, **options):
        qs = Question.objects.filter(option_a='', option_b='')
        if pks:
            qs = qs.filter(pk__in=pks)
        else:
            qs = qs.filter(pk__in=[6359, 6366, 6418, 6436, 6437, 6438])

        fixed = 0
        for q in qs:
            lines = [l.strip() for l in (q.question_text or '').split('\n') if l.strip()]
            if len(lines) < 5:
                continue
            stem, opts = lines[:-4], lines[-4:]
            if not all(3 <= len(o) <= 80 for o in opts):
                continue
            self.stdout.write(f'pk={q.pk}  stem={lines[0][:80]!r}  opts={opts}')
            if apply:
                q.question_text = '\n'.join(stem).rstrip(': \n') + '?'
                q.option_a, q.option_b, q.option_c, q.option_d = opts
                q.save(update_fields=['question_text', 'option_a', 'option_b', 'option_c', 'option_d'])
                fixed += 1
        verb = 'Fixed' if apply else 'Would fix'
        self.stdout.write(self.style.SUCCESS(f'{verb} {fixed} question(s).'))
