"""The answer-key audit signals shipped with the code are imported once per file version, then every question is
audited (``manage.py import_bundled_key_audit``, run by start_web.sh); they never change a key."""
import io
import json
import re
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from key_audit.management.commands.import_bundled_key_audit import DATA_DIR, FILES
from key_audit.models import BundledSignalImport, QuestionAudit, SourceKey
from questions.content_hashes import stem_hash
from questions.models import Question, Subject

HEX64 = re.compile(r'^[0-9a-f]{64}$')


class BundledSignalImportTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Bundle Medicine', code='BUN-M')
        self.q = Question.objects.create(question_text='Bundled stem about a drug', option_a='alpha', option_b='beta',
                                         option_c='gamma', option_d='delta', correct_answer='A', year=2025,
                                         exam_type='neet_pg', subject=subject)
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.hash = stem_hash(self.q)
        self.write('pass1b_reviews_hashed.jsonl', [self.review('disagree')])
        self.write('source_keys_v2.jsonl', [{
            'question_id': self.q.id, 'stem_hash': self.hash, 'source_file': 'Recall answers.pdf', 'located': True,
            'printed_letter': 'C', 'letter': 'C', 'option_order': 'same', 'method': 'answer_key_table',
            'question_page': 3, 'answer_page': 9, 'question_number': 8, 'recovery_version': 'v2-2026-11-03',
            'recovered_at': '2026-11-03T00:00:00+00:00'}])

    def review(self, verdict, stem=None):
        return {'question_id': self.q.id, 'pass': 1, 'reviewer': 'claude-subagent (review signal)',
                'verdict': verdict, 'best_option': 'C', 'confidence': 'high', 'explanation_check': 'absent',
                'issues': [], 'reason': 'Gamma is the drug of choice.', 'stored_key': 'A',
                'stem_hash': stem or self.hash}

    def write(self, name, rows):
        with open(self.dir / name, 'w', encoding='utf-8') as fh:
            for row in rows:
                fh.write(json.dumps(row) + '\n')

    def run_command(self, *extra):
        out = io.StringIO()
        call_command('import_bundled_key_audit', '--data-dir', str(self.dir), *extra, stdout=out)
        return out.getvalue()

    def ai_verdicts(self):
        audit = QuestionAudit.objects.get(question=self.q)
        return [r['verdict'] for r in audit.reviews if r.get('reviewer') == 'claude-subagent (review signal)']

    def test_a_dry_run_writes_nothing(self):
        text = self.run_command()
        self.assertIn('pass1b_reviews_hashed.jsonl: 1 line(s), 1 valid for 1 question(s)', text)
        self.assertIn('pass1_reviews_hashed.jsonl: not shipped', text)
        self.assertIn('Dry run', text)
        self.assertFalse(BundledSignalImport.objects.exists())
        self.assertFalse(SourceKey.objects.exists())
        self.assertFalse(QuestionAudit.objects.filter(question=self.q).exists())

    def test_each_file_is_imported_once_per_version_then_audited_and_no_key_changes(self):
        text = self.run_command('--apply')
        self.assertIn('Audit applied', text)
        self.assertEqual(self.ai_verdicts(), ['disagree'])
        self.assertEqual(SourceKey.objects.filter(question=self.q).count(), 1)
        self.assertEqual(set(BundledSignalImport.objects.values_list('name', flat=True)),
                         {'pass1b_reviews_hashed.jsonl', 'source_keys_v2.jsonl'})
        self.assertEqual(Question.objects.get(pk=self.q.pk).correct_answer, 'A')  # a signal, never a key change

        again = self.run_command('--apply')
        self.assertIn('pass1b_reviews_hashed.jsonl: already imported', again)
        self.assertIn('Nothing new', again)
        self.assertEqual(BundledSignalImport.objects.count(), 2)

        self.write('pass1b_reviews_hashed.jsonl', [self.review('uncertain')])  # a new version of the file
        third = self.run_command('--apply')
        self.assertIn('pass1b_reviews_hashed.jsonl: 1 line(s)', third)
        self.assertIn('source_keys_v2.jsonl: already imported', third)
        self.assertEqual(self.ai_verdicts(), ['uncertain'])  # the same reviewer's review replaced, not added
        self.assertEqual(BundledSignalImport.objects.filter(name='pass1b_reviews_hashed.jsonl').count(), 2)

    def test_a_line_made_for_other_content_is_skipped(self):
        self.write('pass1b_reviews_hashed.jsonl', [self.review('disagree', stem='0' * 64)])
        text = self.run_command('--apply')
        self.assertIn('pass1b_reviews_hashed.jsonl: 1 line(s), 0 valid', text)
        self.assertIn('skipped', text)
        audit = QuestionAudit.objects.filter(question=self.q).first()
        self.assertFalse(audit and [r for r in audit.reviews if r.get('reviewer') == 'claude-subagent (review signal)'])


class ShippedFilesTests(SimpleTestCase):
    def test_the_shipped_files_carry_a_question_id_and_a_content_hash_on_every_line(self):
        counts = {}
        for _kind, name in FILES:
            path = DATA_DIR / name
            self.assertTrue(path.is_file(), name)
            with open(path, encoding='utf-8') as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
            counts[name] = len(rows)
            for row in rows:
                self.assertIsInstance(row.get('question_id'), int, name)
                self.assertRegex(row.get('stem_hash', ''), HEX64, name)
        self.assertEqual(counts, {'source_keys_v2.jsonl': 6490, 'pass1_reviews_hashed.jsonl': 2634,
                                  'pass1b_reviews_hashed.jsonl': 5828})

    def test_the_review_files_are_ai_signals_only(self):
        for _kind, name in FILES[1:]:
            with open(DATA_DIR / name, encoding='utf-8') as fh:
                reviewers = {json.loads(line).get('reviewer') for line in fh if line.strip()}
            self.assertEqual(reviewers, {'claude-subagent (review signal)'}, name)
