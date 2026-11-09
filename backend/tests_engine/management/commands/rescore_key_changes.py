"""Score past test attempts again after answer-key changes and UPSC-dropped questions (dry run unless --apply).

Every pending ``questions.AnswerKeyChange`` (an admin's key change, an official UPSC key from questions.0047 ...)
and every question UPSC dropped from evaluation (``is_dropped`` on an active question) is applied to the completed
test attempts it touches (tests_engine.scoring): an answer is marked against the current key, a dropped question
is left out of the score and of the total. Only what changed is written: the attempt's figures, an
``AttemptRescore`` row with the old and the new figures and each answer whose verdict changed, and the attempt's
first score in ``original_score`` / ``original_total_marks``. The question-bank answers (each student's latest
pick) of the changed questions are marked against the current key too, and each pending key change is marked done
with what it affected. XP already earned is left as it is. A second run changes nothing.

  python manage.py rescore_key_changes              # dry run: counts and the attempts that would change
  python manage.py rescore_key_changes --apply
"""
from django.core.management.base import BaseCommand

from tests_engine.scoring import rescore_pending_key_changes


class Command(BaseCommand):
    help = 'Score past test attempts again after answer-key changes and UPSC-dropped questions (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
        parser.add_argument('--limit', type=int, default=0, help='check at most this many attempts')
        parser.add_argument('--verbose-attempts', action='store_true', help='list every attempt that changes')

    def handle(self, *args, **opts):
        lines = []
        stats = rescore_pending_key_changes(apply=opts['apply'], limit=opts['limit'] or None, log=lines.append)
        if opts['verbose_attempts']:
            for line in lines:
                self.stdout.write('  ' + line)
        mode = 'applied' if opts['apply'] else 'dry run'
        self.stdout.write(f'rescore_key_changes ({mode}): ' + ', '.join(f'{k} {v}' for k, v in stats.items()))
        if not opts['apply'] and stats.get('attempts rescored'):
            self.stdout.write('  nothing was written; run again with --apply to re-score')
