"""Move answer keys and explanations that imports left in the public text.

Some imports glued the answer key or the explanation into the stem or an
option (``questions.answer_leak``): option D ``"I and IV only Correct Answer:
A. I, II and IV only"``, stems ending in ``"Explanation: ..."``, NEET PG
recall rows whose option D carries the answer-key table and the worked
solutions of the whole paper, and pasted pages of questions with their
``"Ans: (b) ..."`` lines. The stem and the options are public, so that text
gave the answer away. The API now cuts it for viewers who may not read the
answer; this command repairs the rows themselves.

Per active question (``answer_leak.plan_repair``):

* an answer label in an option is cut off; its letter becomes the key when
  the stored key is empty and the label repeats that option's text (a stored
  key is never changed -- a disagreement is reported as a conflict);
* a correctness flag on an option ("Conjunctival xerosis ✔ (...)",
  "(correct)", "[wrong]") or on an option the stem lists ("A. Schwannoma
  ✅") is dropped, its reason moves to ``explanation``; a single option
  flagged correct fills an empty key. A flag naming another option than the
  stored key (or a stored key whose option is flagged wrong) is a key
  conflict: the stored key is kept and the row is listed under "Key
  conflicts" for review -- re-score the attempts on it once the key is
  settled;
* an answer-key table / set solutions after an option are cut off;
* explanation text in the stem or an option moves to ``explanation``;
* a row that cannot be repaired -- a stem holding answer labels (a pasted
  page of other questions and their answers), or a stem / an option that is
  nothing but a label -- is deactivated for manual review, text untouched.

Every changed row gets ``needs_review=True`` and a revision snapshot of its
previous state (``QuestionRevisionSnapshot``), so the admin editor's "undo
last revision" restores it. Rows citing a "Reference:" with no label are
listed for manual review only (their stem may hold an unlabelled
explanation).

Dry run by default; check the report on a copy of production (crack_local)
first::

    python manage.py fix_answer_label_leaks                    # report only
    python manage.py fix_answer_label_leaks --json-report plan.json
    python manage.py fix_answer_label_leaks --apply            # write
    python manage.py fix_answer_label_leaks --ids 19522,26233  # limit scope
"""
from __future__ import annotations

import json
import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from questions.answer_leak import PREFILTER_WORDS, PUBLIC_TEXT_FIELDS, plan_repair, row_has_answer_label
from questions.content_hashes import stem_hash
from questions.content_hooks import on_question_changed
from questions.editorial import change_answer_key
from questions.models import Question, QuestionRevisionSnapshot

# SQL pre-filter: a row can only carry a label or a correctness flag if one
# of these words / ticks / crosses occurs.
_PREFILTER_WORDS = PREFILTER_WORDS
_REFERENCE_RE = re.compile(r"(?<![A-Za-z])(?i:reference)\s*:")
SNAPSHOT_REASON = 'Before fix_answer_label_leaks'
KEY_REASON = 'Empty key filled from the answer label printed in the imported text (fix_answer_label_leaks).'


def _snapshot_state(question) -> dict:
    """Same shape as QuestionViewSet._serialize_revision_state, so the admin
    editor's revision diff / undo handle it."""
    from questions.views import QuestionViewSet

    return QuestionViewSet()._serialize_revision_state(question)


class Command(BaseCommand):
    help = (
        "Repair questions whose stem / options carry the answer key or the "
        "explanation (dry run unless --apply). See the module docstring."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the changes (default: dry run).')
        parser.add_argument('--ids', type=str, default='', help='Comma-separated question ids to limit the run to.')
        parser.add_argument('--examples', type=int, default=5, help='Examples printed per category.')
        parser.add_argument('--json-report', type=str, default='', help='Write the full plan to this JSON file.')

    def handle(self, *args, **opts):
        apply = bool(opts.get('apply'))
        ids = []
        if opts.get('ids'):
            try:
                ids = [int(part) for part in opts['ids'].split(',') if part.strip()]
            except ValueError as exc:
                raise CommandError('--ids must be comma-separated integers') from exc

        prefilter = Q()
        for name in PUBLIC_TEXT_FIELDS:
            for word in (*_PREFILTER_WORDS, 'reference'):
                prefilter |= Q(**{f'{name}__icontains': word})
        qs = Question.objects.filter(is_active=True)
        if ids:
            qs = qs.filter(pk__in=ids)
        candidates = qs.filter(prefilter).order_by('id')

        plans = []
        reference_only = []
        for question in candidates.iterator(chunk_size=500):
            if row_has_answer_label(question):
                plan = plan_repair(question)
                if plan.needed:
                    plans.append((question, plan))
            elif any(_REFERENCE_RE.search(getattr(question, name) or '') for name in PUBLIC_TEXT_FIELDS):
                reference_only.append(question.pk)

        self._report(plans, reference_only, opts.get('examples') or 0)
        if opts.get('json_report'):
            self._write_json(opts['json_report'], plans, reference_only)

        if not apply:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] nothing written. Re-run with --apply to write.'))
            return

        changed = held = 0
        for question, plan in plans:
            with transaction.atomic():
                row = Question.objects.select_for_update().get(pk=question.pk)
                # Re-plan on the locked row: it may have changed since the scan.
                plan = plan_repair(row)
                if not plan.needed:
                    continue
                old_key, old_hash = row.correct_answer or '', stem_hash(row)
                QuestionRevisionSnapshot.objects.create(
                    question=row, changed_by=None, reason=SNAPSHOT_REASON, snapshot=_snapshot_state(row),
                )
                update_fields = ['needs_review']
                row.needs_review = True
                changes = dict(plan.changes)
                # A key read from the label fills an EMPTY key only (plan_repair never changes a stored
                # key); it goes through the one key writer so it has an AnswerKeyChange record.
                new_key = '' if plan.deactivate else changes.pop('correct_answer', '')
                if plan.deactivate:
                    row.is_active = False
                    update_fields.append('is_active')
                    held += 1
                else:
                    for name, value in changes.items():
                        setattr(row, name, value)
                        update_fields.append(name)
                    changed += 1
                row.save(update_fields=update_fields)
                if new_key:
                    change_answer_key(
                        row, new_key, actor=None, source='management_command', reason=KEY_REASON,
                        evidence=[{'kind': 'note', 'text': 'Answer label printed in the imported question text '
                                                           '(fix_answer_label_leaks).'}],
                    )
                    Question.objects.filter(pk=row.pk).update(needs_review=True)   # still to be reviewed
                if not plan.deactivate:
                    transaction.on_commit(lambda row=row, old_key=old_key, old_hash=old_hash: on_question_changed(
                        row, old_key=old_key, old_stem_hash=old_hash, reason='answer-label repair'))
        self.stdout.write(self.style.SUCCESS(
            f'\nApplied: {changed} repaired, {held} deactivated for review '
            f'(revision snapshots: "{SNAPSHOT_REASON}").'
        ))

    # -- output ---------------------------------------------------------------

    def _report(self, plans, reference_only, examples):
        held = [(q, p) for q, p in plans if p.deactivate]
        repaired = [(q, p) for q, p in plans if not p.deactivate]
        categories = Counter(p.category or 'other' for _, p in plans)
        self.stdout.write(f'Questions with a label in the stem / options: {len(plans)}')
        for category, count in categories.most_common():
            self.stdout.write(f'  {category}: {count}')
        self.stdout.write(
            f'Repair: {len(repaired)} '
            f'(key set from the label: {sum(1 for _, p in repaired if "correct_answer" in p.changes)}, '
            f'explanation set / extended: {sum(1 for _, p in repaired if "explanation" in p.changes)}, '
            f'key conflicts kept for review: {sum(1 for _, p in repaired if p.conflict)})'
        )
        self.stdout.write(f'Deactivate for manual review: {len(held)}')
        if held:
            self.stdout.write('  ids: ' + ', '.join(str(q.pk) for q, _ in held))
        conflicts = [(q, p) for q, p in repaired if p.conflict]
        if conflicts:
            self.stdout.write('Key conflicts (stored key kept): ' + ', '.join(str(q.pk) for q, _ in conflicts))
            for question, plan in conflicts:
                details = '; '.join(plan.conflicts) or 'the label names no usable key'
                self.stdout.write(f'  Q{question.pk} (stored key {question.correct_answer or "-"}): {details}')
        if reference_only:
            self.stdout.write(
                f'"Reference:" in the public text but no label (manual review, unchanged): '
                f'{len(reference_only)} -- ids: ' + ', '.join(map(str, sorted(reference_only)))
            )
        shown = Counter()
        for question, plan in plans:
            key = plan.category or 'other'
            if shown[key] >= examples:
                continue
            shown[key] += 1
            self.stdout.write(f'\n--- Q{question.pk} [{key}]' + (' HOLD' if plan.deactivate else ''))
            for reason in plan.reasons:
                self.stdout.write(f'    hold: {reason}')
            for action in plan.actions:
                self.stdout.write(f'    * {action}')
            for name, value in plan.changes.items():
                before = getattr(question, name) or ''
                self.stdout.write(f'    {name}: {before[-120:]!r}')
                self.stdout.write(f'      -> {(value or "")[-120:]!r}')

    def _write_json(self, path, plans, reference_only):
        payload = {
            'questions': [
                {
                    'id': question.pk,
                    'category': plan.category,
                    'deactivate': plan.deactivate,
                    'reasons': plan.reasons,
                    'conflict': plan.conflict,
                    'conflicts': plan.conflicts,
                    'stored_key': question.correct_answer or '',
                    'actions': plan.actions,
                    'before': {name: getattr(question, name) for name in plan.changes},
                    'after': plan.changes,
                }
                for question, plan in plans
            ],
            'reference_only_ids': sorted(reference_only),
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.stdout.write(f'\nWrote {path}')
