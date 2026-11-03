"""Audit the answer keys of the question bank (docs/audit/MEDICAL_ACCURACY_DESIGN.md, phase 3).

Classifies every selected question (``key_audit.classify``) from what the database holds: printed
source keys, AI reviews and official keys, human decisions, student reports, duplicates, answer labels,
images, the exam / year key distribution. NEVER changes ``Question.correct_answer``.

Dry run by default: prints what the audit would record. ``--apply`` writes ``QuestionAudit`` rows (the
stored reviews are kept) and mirrors the status into ``Question.answer_key_status``.

  python manage.py audit_answer_keys                      # dry run, every active question
  python manage.py audit_answer_keys --exam neet_pg --apply
  python manage.py audit_answer_keys --ids 12,40 --run-evidence --apply
  python manage.py audit_answer_keys --stale-only --apply  # questions edited since their audit
"""
from __future__ import annotations

import json
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from key_audit.models import QuestionAudit
from key_audit.services import _run_evidence, audit_questions, key_skew
from questions.models import Question


class Command(BaseCommand):
    help = 'Audit answer keys against the recorded signals (dry run unless --apply). Never changes a key.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='write QuestionAudit rows (default: dry run)')
        parser.add_argument('--exam', default='', help='only this exam_type (e.g. cms, neet_pg, ini_cet)')
        parser.add_argument('--ids', default='', help='comma-separated question ids')
        parser.add_argument('--limit', type=int, default=0, help='at most this many questions (by id)')
        parser.add_argument('--stale-only', action='store_true', help='only questions with no audit or a stale one')
        parser.add_argument('--include-inactive', action='store_true', help='also inactive questions')
        parser.add_argument('--run-evidence', action='store_true',
                            help='record a reference-corpus evidence decision first (needs REFERENCE_STORE_PATH)')
        parser.add_argument('--top', type=int, default=15, help='list this many highest-priority question ids')
        parser.add_argument('--json', action='store_true', help='print the summary as JSON')

    def handle(self, *args, **opts):
        qs = Question.objects.all() if opts['include_inactive'] else Question.objects.filter(is_active=True)
        if opts['exam']:
            qs = qs.filter(exam_type=opts['exam'])
        if opts['ids']:
            try:
                ids = [int(part) for part in opts['ids'].split(',') if part.strip()]
            except ValueError:
                raise CommandError('--ids takes comma-separated integers') from None
            qs = qs.filter(pk__in=ids)
        if opts['stale_only']:
            fresh = QuestionAudit.objects.filter(is_stale=False).values('question_id')
            qs = qs.exclude(pk__in=fresh)
        qs = qs.order_by('pk')
        if opts['limit']:
            qs = qs[:opts['limit']]
        questions = list(qs)
        apply = opts['apply']

        if opts['run_evidence']:
            if not apply:
                raise CommandError('--run-evidence records EvidenceRun rows: use it together with --apply')
            for question in questions:
                _run_evidence(question)

        before = dict(QuestionAudit.objects.filter(question_id__in=[q.pk for q in questions])
                      .values_list('question_id', 'status'))
        skew = key_skew()
        prepared = audit_questions(questions, save=apply, skew=skew)

        status = Counter(p.fields['status'] for p in prepared)
        reasons = Counter((p.fields['status'], p.fields['status_reason']) for p in prepared)
        live = [s for p in prepared for s in p.fields['signals'] if not s.get('settled_by_review')]
        opening = Counter(s['code'] for s in live if s.get('opens_review'))
        info = Counter(s['code'] for s in live if not s.get('opens_review'))
        transitions = Counter((before.get(p.question.pk, '(none)'), p.fields['status']) for p in prepared
                              if before.get(p.question.pk) != p.fields['status'])
        suggested = sum(1 for p in prepared if p.fields['suggested_key'])
        by_from = Counter(p.fields['evidence_summary'].get('suggested_from') for p in prepared if p.fields['suggested_key'])
        top = sorted(prepared, key=lambda p: (-p.fields['priority'], p.question.pk))[:max(opts['top'], 0)]
        summary = {
            'mode': 'apply' if apply else 'dry-run',
            'questions': len(prepared),
            'status': dict(status.most_common()),
            'reasons': {f'{s}/{r}': n for (s, r), n in reasons.most_common()},
            'review_signals': dict(opening.most_common()),
            'info_signals': dict(info.most_common()),
            'with_suggested_key': suggested,
            'suggested_from': dict(by_from.most_common()),
            'status_changes': {f'{a} -> {b}': n for (a, b), n in transitions.most_common()},
            'skewed_groups': {f'{exam} {year}': v for (exam, year), v in sorted(skew.items(), key=str)},
            'top_priority': [{'id': p.question.pk, 'priority': p.fields['priority'], 'status': p.fields['status'],
                              'reason': p.fields['status_reason'], 'stored': p.fields['stored_key'],
                              'suggested': p.fields['suggested_key']} for p in top],
        }
        if opts['json']:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=False))
            return
        self._print(summary)

    def _print(self, s):
        write = self.stdout.write
        write(f"Answer-key audit ({s['mode']}): {s['questions']} question(s)")
        write('Status:')
        for name, n in s['status'].items():
            pct = n / s['questions'] * 100 if s['questions'] else 0
            write(f'  {name:24s} {n:6d}  {pct:5.1f} %')
        write('Status / reason:')
        for name, n in list(s['reasons'].items())[:25]:
            write(f'  {name:56s} {n:6d}')
        write('Signals that open a review (a question can have several):')
        for name, n in s['review_signals'].items():
            write(f'  {name:40s} {n:6d}')
        write('Other signals (shown to the reviewer, no effect on the status):')
        for name, n in s['info_signals'].items():
            write(f'  {name:40s} {n:6d}')
        write(f"Suggested key (never applied): {s['with_suggested_key']} {s['suggested_from']}")
        if s['skewed_groups']:
            write('Skewed key distributions (exam year: letter share of n):')
            for name, v in s['skewed_groups'].items():
                write(f"  {name:16s} {v['letter']} {v['share']:.1%} of {v['n']}")
        if s['status_changes']:
            write('Status changes against the stored audits:')
            for name, n in list(s['status_changes'].items())[:20]:
                write(f'  {name:52s} {n:6d}')
        if s['top_priority']:
            write('Highest priority:')
            for row in s['top_priority']:
                write(f"  Q{row['id']:<6} {row['priority']:6.1f} {row['status']:22s} {row['reason']:32s} "
                      f"{row['stored'] or '-'} -> {row['suggested'] or '-'}")
        if s['mode'] == 'dry-run':
            write('Dry run: nothing written. Run again with --apply to record the audit.')
