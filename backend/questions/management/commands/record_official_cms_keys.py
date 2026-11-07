"""Record UPSC's official answer key of CMS 2018-2025 in the answer-key audit (dry run unless --apply).

The key of every question of the 16 papers is in questions/data/cms_official_2018_2025.json (questions.0047 made
the bank match it: paper, display_number = the official number, key). Each active question found by year, paper
and number gets an ``official_key`` review (key_audit.reviews) through ``key_audit.importers.import_review_signals``,
so the audit shows it as verified against the official key and flags any later change away from it. A question
UPSC dropped gets no review; for a question with two accepted answers the review names the accepted letter the
bank holds; where the bank lists the options in another order the review names the bank's letter for the
official answer (``letter_map``). Questions whose audit already holds the same review are left alone, so the
release step can run it on every deploy.

  python manage.py record_official_cms_keys            # dry run
  python manage.py record_official_cms_keys --apply
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from questions import cms_official
from questions.content_hashes import stem_hash, valid_key
from questions.models import Question

REVIEWER_REF = 'cms_official_2018_2025'


class Command(BaseCommand):
    help = "Record UPSC's official CMS 2018-2025 keys as official_key reviews in the answer-key audit."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='write the reviews (default: dry run)')

    def handle(self, *args, **opts):
        try:
            from key_audit.importers import import_review_signals
            from key_audit.models import QuestionAudit
        except ImportError:  # pragma: no cover - key_audit not installed
            self.stdout.write('key_audit is not installed: nothing to do')
            return
        data = cms_official.load_data()
        lines, found, current = [], 0, 0
        for paper_key, keys in data['keys'].items():
            year, paper = int(paper_key[:4]), int(paper_key[-1])
            rows = {q.display_number: q for q in Question.objects.filter(
                exam_type='cms', year=year, paper=paper, is_active=True, display_number__isnull=False)}
            for n, official in keys.items():
                q = rows.get(int(n))
                if q is None or official == 'X':
                    continue
                found += 1
                letters = official.split('/')
                stored = valid_key(q.correct_answer)
                best = data.get('letter_map', {}).get(f'{paper_key}:{n}') or (stored if stored in letters else letters[0])
                content = stem_hash(q)
                audit = QuestionAudit.objects.filter(question_id=q.pk).only('reviews').first()
                if audit and any(isinstance(r, dict) and r.get('reviewer') == 'official_key'
                                 and r.get('reviewer_ref') == REVIEWER_REF and r.get('best_option') == best
                                 and r.get('stem_hash') == content for r in (audit.reviews or [])):
                    current += 1
                    continue
                paper_name = 'I' if paper == 1 else 'II'
                lines.append({
                    'question_id': q.pk, 'stem_hash': content, 'reviewer': 'official_key', 'pass': 1,
                    'reviewer_id': REVIEWER_REF, 'best_option': best, 'stored_key': stored,
                    'official_source': (f"UPSC answer key, CMS {year} Paper {paper_name} (Series A), Q{n}: {official}; "
                                        f"{data['source']['title']} p.{data['key_pages'][paper_key]}"),
                    'reason': f'Official UPSC answer key: {official}', 'at': timezone.now().isoformat(),
                })
        self.stdout.write(f'official keys: {found} question(s) found, {current} already recorded, '
                          f'{len(lines)} to record')
        if not lines:
            return
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f'{REVIEWER_REF}.jsonl'
            path.write_text('\n'.join(json.dumps(line) for line in lines), encoding='utf-8')
            report, _reviews = import_review_signals(path, apply=opts['apply'], source=REVIEWER_REF)
        result = report.as_dict()
        self.stdout.write(f"  {'recorded' if opts['apply'] else 'dry run'}: {result['valid']} valid review(s) for "
                          f"{result['questions']} question(s)"
                          + (f"; skipped {dict(result['skipped'])}" if result['skipped'] else ''))
