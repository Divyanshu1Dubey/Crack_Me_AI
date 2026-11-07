"""The one-time data migrations of the 2026-11-07 release: they run on a live bank only and never fail a deploy.

0043 imports the UPSC CMS 2026 papers (fixtures/pyq/cms_2026.json) and 0044 opens the scholarship
challenge with the reviewed pool (fixtures/scholarship_pool.json), so merging the release needs no manual
production step for either. A test or fresh database (no live CMS bank, none of the pool's questions) is
left as it is; an error is printed, never raised.
"""
from __future__ import annotations

import importlib
import io
import json
import shutil
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.test import TestCase

from key_audit.models import SourceKey
from questions.content_hashes import stem_hash
from questions.models import Question, Subject

import_migration = importlib.import_module('questions.migrations.0043_import_cms_2026_papers')
pool_migration = importlib.import_module('questions.migrations.0044_scholarship_pool')


def _paper_question(number, key='B'):
    return {'paper': 1, 'number': number, 'page': number, 'subject_code': 'RELMED', 'chapter': 'x', 'topic': 'Cardiology',
            'question_text': f'Release paper question {number}: which one is first line?', 'option_a': f'a{number}',
            'option_b': f'b{number}', 'option_c': f'c{number}', 'option_d': f'd{number}', 'correct_answer': key}


def _run(forward):
    out = io.StringIO()
    with redirect_stdout(out):
        forward(apps, None)
    return out.getvalue()


class ReleaseDataMigrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Release Medicine', code='RELMED')
        cls.bank = Question.objects.create(question_text='A live bank question?', option_a='1', option_b='2',
                                           option_c='3', option_d='4', correct_answer='A', year=2024,
                                           subject=cls.subject, exam_type='cms')

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='release-migrations-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _file(self, name, data):
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    # ── 0043: CMS 2026 papers ────────────────────────────────────────────
    def _paper(self):
        return self._file('paper.json', {
            'format': 'pyq-paper/1', 'exam_type': 'cms', 'exam_source': 'UPSC CMS', 'year': 2026,
            'sources': {'1': {'file': 'Example solution paper 1.pdf', 'sha256': 'a' * 64}},
            'questions': [_paper_question(1), _paper_question(2, key='D')]})

    def test_the_import_skips_a_database_without_a_live_bank(self):
        with mock.patch.object(import_migration, 'PAPER', self._paper()):
            self.assertEqual(_run(import_migration.forward), '')     # 1 CMS question < LIVE_BANK_MIN
        self.assertFalse(Question.objects.filter(year=2026).exists())

    def test_the_import_runs_once_on_a_live_bank_and_never_raises(self):
        with mock.patch.object(import_migration, 'PAPER', self._paper()), \
                mock.patch.object(import_migration, 'LIVE_BANK_MIN', 1):
            self.assertIn('2 questions created', _run(import_migration.forward))
            self.assertEqual(Question.objects.filter(year=2026, exam_type='cms').count(), 2)
            self.assertEqual(SourceKey.objects.filter(question__year=2026).count(), 2)
            self.assertIn('0 questions created', _run(import_migration.forward))   # idempotent
        bad = self._file('bad.json', {'format': 'nope'})
        with mock.patch.object(import_migration, 'PAPER', bad), mock.patch.object(import_migration, 'LIVE_BANK_MIN', 1):
            self.assertIn('NOT imported', _run(import_migration.forward))
        self.assertEqual(Question.objects.filter(year=2026).count(), 2)

    def test_the_shipped_paper_file_is_the_one_the_migration_reads(self):
        self.assertTrue(import_migration.PAPER.is_file())

    # ── 0044: scholarship pool ───────────────────────────────────────────
    def _pool_questions(self):
        return [Question.objects.create(question_text=f'Pool question {n}?', option_a=f'a{n}', option_b=f'b{n}',
                                        option_c=f'c{n}', option_d=f'd{n}', correct_answer='C', year=2022,
                                        subject=self.subject, exam_type='cms') for n in range(6)]

    def _pool(self, questions, **override):
        rows = [{'id': q.pk, 'key': q.correct_answer, 'stem_hash': stem_hash(q)} for q in questions]
        rows.extend(override.get('extra', []))
        return self._file('pool.json', {'format': 'scholarship-pool/1', 'status': 'proposed', 'questions': rows})

    def test_the_pool_is_applied_once_and_skips_what_changed(self):
        questions = self._pool_questions()
        changed = {'id': questions[5].pk, 'key': 'A', 'stem_hash': stem_hash(questions[5])}   # key differs
        rows = questions[:5]
        with mock.patch.object(pool_migration, 'POOL', self._pool(rows, extra=[changed])):
            out = _run(pool_migration.forward)
        self.assertIn('5 questions added, 5 in the challenge', out)
        self.assertIn(f'{questions[5].pk} (key_changed)', out)
        self.assertEqual(set(Question.objects.filter(is_scholarship_eligible=True).values_list('id', flat=True)),
                         {q.pk for q in rows})
        self.assertEqual(Question.objects.get(pk=questions[5].pk).correct_answer, 'C')   # never rewritten

    def test_the_pool_leaves_a_database_without_its_questions_alone(self):
        missing = self._file('pool.json', {'format': 'scholarship-pool/1', 'questions': [
            {'id': 987654, 'key': 'A', 'stem_hash': 'a' * 64}]})
        with mock.patch.object(pool_migration, 'POOL', missing):
            self.assertEqual(_run(pool_migration.forward), '')
        bad = self._file('bad-pool.json', {'format': 'nope'})
        with mock.patch.object(pool_migration, 'POOL', bad):
            self.assertIn('NOT applied', _run(pool_migration.forward))
        self.assertFalse(Question.objects.filter(is_scholarship_eligible=True).exists())

    def test_the_shipped_pool_file_is_the_one_the_migration_reads(self):
        self.assertTrue(pool_migration.POOL.is_file())
