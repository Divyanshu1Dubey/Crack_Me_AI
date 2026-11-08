"""Record UPSC's official answer key of CMS 2009-2025 in the answer-key audit (dry run unless --apply).

The key of every question of the 34 papers is in questions/data/cms_official_2018_2025.json,
cms_official_2014_2017.json and cms_official_2009_2013.json (questions.0047, 0049 and 0051 made the bank match them:
year, paper, display_number = the official number, key). Each active question found by year, paper and number gets an ``official_key`` review
(key_audit.reviews) through ``key_audit.importers.import_review_signals``, so the audit shows it as verified
against the official key and flags any later change away from it. A question UPSC dropped gets no review, nor
does a key the data file holds for review (``needs_review``: printed unreadably); for a question with two
accepted answers the review names the accepted letter the bank holds; where the bank lists the options in another
order the review names the bank's letter for the official answer (``letter_map``). Questions whose audit already
holds the same review are left alone, so the release step can run it on every deploy. 2026 has no official key
yet: nothing is recorded for it.

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

# data file -> the reviewer reference its reviews carry
OFFICIAL_KEY_FILES = (
    (cms_official.DATA, 'cms_official_2018_2025'),
    (cms_official.DATA_2014_2017, 'cms_official_2014_2017'),
    (cms_official.DATA_2009_2013, 'cms_official_2009_2013'),
)


class Command(BaseCommand):
    help = "Record UPSC's official CMS 2014-2025 keys as official_key reviews in the answer-key audit."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='write the reviews (default: dry run)')

    def handle(self, *args, **opts):
        try:
            from key_audit.importers import import_review_signals
            from key_audit.models import QuestionAudit
        except ImportError:  # pragma: no cover - key_audit not installed
            self.stdout.write('key_audit is not installed: nothing to do')
            return
        batches, found, current, held = [], 0, 0, 0
        for path, reviewer_ref in OFFICIAL_KEY_FILES:
            data = cms_official.load_data(path)
            lines = []
            for paper_key, keys in data['keys'].items():
                year, paper = int(paper_key[:4]), int(paper_key[-1])
                rows = {q.display_number: q for q in Question.objects.filter(
                    exam_type='cms', year=year, paper=paper, is_active=True, display_number__isnull=False)}
                for n, official in keys.items():
                    q = rows.get(int(n))
                    if q is None or official == 'X':
                        continue
                    found += 1
                    if f'{paper_key}:{n}' in data.get('needs_review', {}):
                        held += 1
                        continue
                    letters = official.split('/')
                    stored = valid_key(q.correct_answer)
                    best = (data.get('letter_map', {}).get(f'{paper_key}:{n}')
                            or (stored if stored in letters else letters[0]))
                    content = stem_hash(q)
                    audit = QuestionAudit.objects.filter(question_id=q.pk).only('reviews').first()
                    if audit and any(isinstance(r, dict) and r.get('reviewer') == 'official_key'
                                     and r.get('reviewer_ref') == reviewer_ref and r.get('best_option') == best
                                     and r.get('stem_hash') == content for r in (audit.reviews or [])):
                        current += 1
                        continue
                    paper_name = 'I' if paper == 1 else 'II'
                    lines.append({
                        'question_id': q.pk, 'stem_hash': content, 'reviewer': 'official_key', 'pass': 1,
                        'reviewer_id': reviewer_ref, 'best_option': best, 'stored_key': stored,
                        'official_source': (f"UPSC answer key, CMS {year} Paper {paper_name} (Series A), Q{n}: "
                                            f"{official}; {data['source']['title']} "
                                            f"p.{data['key_pages'][paper_key]}"),
                        'reason': f'Official UPSC answer key: {official}', 'at': timezone.now().isoformat(),
                    })
            if lines:
                batches.append((reviewer_ref, lines))
        to_record = sum(len(lines) for _ref, lines in batches)
        self.stdout.write(f'official keys: {found} question(s) found, {current} already recorded, '
                          f'{to_record} to record' + (f', {held} held for review' if held else ''))
        for reviewer_ref, lines in batches:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / f'{reviewer_ref}.jsonl'
                path.write_text('\n'.join(json.dumps(line) for line in lines), encoding='utf-8')
                report, _reviews = import_review_signals(path, apply=opts['apply'], source=reviewer_ref)
            result = report.as_dict()
            self.stdout.write(f"  {reviewer_ref} {'recorded' if opts['apply'] else 'dry run'}: {result['valid']} "
                              f"valid review(s) for {result['questions']} question(s)"
                              + (f"; skipped {dict(result['skipped'])}" if result['skipped'] else ''))
