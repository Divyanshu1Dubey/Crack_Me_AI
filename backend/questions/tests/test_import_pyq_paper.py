"""manage.py import_pyq_paper: a previous-year paper file into the bank (fixtures/pyq/*.json).

The 2026 UPSC CMS papers came as unofficial solution PDFs: stems, options and printed keys were taken
from them, never their explanations. The import must be a dry run by default, complete (a year's paper
is imported whole for the simulator), idempotent, honour admin removals, record each printed key as a
secondary-source signal (key_audit.SourceKey) and run the key audit, which never marks such a key verified.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from key_audit.models import SourceKey
from questions.content_hashes import stem_hash
from questions.management.commands.import_pyq_paper import load_paper
from questions.models import Question, RemovedQuestion, Subject, Topic, compute_stem_hash

CMS_2026 = Path(settings.BASE_DIR) / 'fixtures' / 'pyq' / 'cms_2026.json'


def _question(paper, number, subject='MED', key='A', topic='Cardiology', stem=None):
    return {
        'paper': paper, 'number': number, 'page': number, 'subject_code': subject,
        'chapter': 'Cardiology / Heart failure', 'topic': topic, 'subtopic': 'x',
        'question_text': stem or f'Stem of paper {paper} question {number}: which drug is first line?',
        'option_a': f'Alpha {number}', 'option_b': f'Beta {number}', 'option_c': f'Gamma {number}',
        'option_d': f'Delta {number}', 'correct_answer': key,
    }


def _paper(questions):
    return {
        'format': 'pyq-paper/1', 'exam_type': 'cms', 'exam_source': 'UPSC CMS', 'year': 2026, 'series': 'C',
        'sources': {
            '1': {'file': 'Example solution paper 1.pdf', 'sha256': 'a' * 64, 'publisher': 'Example'},
            '2': {'file': 'Example solution paper 2.pdf', 'sha256': 'b' * 64, 'publisher': 'Example'},
        },
        'questions': questions,
    }


class ImportPyqPaperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.med = Subject.objects.create(name='General Medicine', code='MED')
        cls.ped = Subject.objects.create(name='Paediatrics', code='PED')
        cls.existing_topic = Topic.objects.create(subject=cls.med, name='Cardiology', importance=5)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pyq-paper-')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _file(self, data):
        path = Path(self.tmp) / 'paper.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return str(path)

    def _run(self, data, *args):
        out = io.StringIO()
        call_command('import_pyq_paper', self._file(data), *args, stdout=out)
        return out.getvalue()

    def _three(self):
        return _paper([_question(1, 1), _question(1, 2, subject='PED', key='C', topic='Neonatology'),
                       _question(2, 1, key='D', topic='cardiology')])

    def test_a_dry_run_writes_nothing(self):
        out = self._run(self._three())
        self.assertIn('to create 3', out)
        self.assertIn('Dry run', out)
        self.assertFalse(Question.objects.exists())
        self.assertFalse(SourceKey.objects.exists())

    def test_apply_creates_the_paper_with_numbers_subjects_topics_keys_and_source_keys(self):
        out = self._run(self._three(), '--apply')
        self.assertIn('Created 3 questions', out)
        rows = {(q.paper, q.display_number): q for q in Question.objects.all()}
        self.assertEqual(set(rows), {(1, 1), (1, 2), (2, 1)})
        first = rows[(1, 1)]
        self.assertEqual((first.exam_type, first.exam_source, first.year, first.correct_answer),
                         ('cms', 'UPSC CMS', 2026, 'A'))
        self.assertEqual(first.subject, self.med)
        self.assertEqual(rows[(1, 2)].subject, self.ped)
        # An existing topic is reused, case-insensitively; a new name makes a new topic.
        self.assertEqual(first.topic, self.existing_topic)
        self.assertEqual(rows[(2, 1)].topic, self.existing_topic)
        self.assertEqual(rows[(1, 2)].topic.name, 'Neonatology')
        self.assertEqual(Topic.objects.filter(subject=self.med).count(), 1)
        # No explanation is written: nothing of the solution's own writing.
        self.assertTrue(all(q.explanation == '' and q.explanation_status == 'none' for q in rows.values()))
        source = SourceKey.objects.get(question=rows[(1, 2)])
        self.assertEqual((source.method, source.located, source.option_order), ('inline_answer', True, 'same'))
        self.assertEqual((source.printed_letter, source.letter, source.question_number), ('C', 'C', 2))
        self.assertEqual((source.source_file, source.source_year, source.source_exam),
                         ('Example solution paper 1.pdf', 2026, 'CMS'))
        self.assertEqual(source.stem_hash, stem_hash(rows[(1, 2)]))
        # The key audit ran; one unofficial printed key never makes a key verified.
        for q in Question.objects.all():
            self.assertNotIn(q.answer_key_status, ('unaudited', 'verified'), q.pk)
        self.assertRegex(out, r'answer-key audit: \w+ \d+')

    def test_a_second_run_changes_nothing(self):
        self._run(self._three(), '--apply')
        out = self._run(self._three(), '--apply')
        self.assertIn('already imported 3', out)
        self.assertIn('Nothing to create', out)
        self.assertEqual(Question.objects.count(), 3)
        self.assertEqual(SourceKey.objects.count(), 3)

    def test_a_copy_elsewhere_in_the_bank_is_listed_and_the_paper_stays_whole(self):
        data = self._three()
        copy = Question.objects.create(year=0, subject=self.med, **{
            k: data['questions'][0][k] for k in ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')})
        out = self._run(data, '--apply')
        self.assertIn(f'paper 1 no. 1: same stem and options as question(s) {copy.pk}', out)
        self.assertEqual(Question.objects.filter(year=2026).count(), 3)

    def test_a_stem_an_admin_removed_is_not_imported(self):
        data = self._three()
        RemovedQuestion.objects.create(exam_source='UPSC CMS', year=0,
                                       question_text_hash=compute_stem_hash(data['questions'][1]['question_text']))
        out = self._run(data, '--apply')
        self.assertIn('removed by an admin 1', out)
        self.assertIn('paper 1 no. 2: removed by an admin', out)
        self.assertFalse(Question.objects.filter(paper=1, display_number=2).exists())

    def test_a_question_that_needs_its_figure_is_created_hidden(self):
        data = self._three()
        data['questions'][2]['needs_figure'] = True
        out = self._run(data, '--apply')
        self.assertIn('1 need their figure from the official paper and are created hidden: P2 Q1', out)
        hidden = Question.objects.get(paper=2, display_number=1)
        self.assertEqual((hidden.is_active, hidden.needs_review, hidden.is_image_based), (False, True, True))
        shown = Question.objects.get(paper=1, display_number=1)
        self.assertEqual((shown.is_active, shown.needs_review, shown.is_image_based), (True, False, False))

    def test_a_bad_file_or_a_missing_subject_is_refused_before_writing(self):
        bad = self._three()
        bad['questions'][0]['option_c'] = ' '
        bad['questions'][1]['correct_answer'] = 'E'
        with self.assertRaisesRegex(CommandError, 'an option is empty'):
            self._run(bad, '--apply')
        unknown = _paper([_question(1, 1, subject='XYZ')])
        with self.assertRaisesRegex(CommandError, 'Subjects missing in this database'):
            self._run(unknown, '--apply')
        self.assertFalse(Question.objects.exists())


class Cms2026FileTests(SimpleTestCase):
    """The shipped file itself: both papers complete, valid keys, no solution text."""

    def test_both_papers_are_complete_and_valid(self):
        data = load_paper(CMS_2026)
        self.assertEqual((data['exam_type'], data['year'], data['series']), ('cms', 2026, 'C'))
        for paper in (1, 2):
            numbers = sorted(q['number'] for q in data['questions'] if q['paper'] == paper)
            self.assertEqual(numbers, list(range(1, 121)), paper)
        sections = {(q['paper'], q['subject_code']) for q in data['questions']}
        self.assertEqual(sections, {(1, 'MED'), (1, 'PED'), (2, 'PSM'), (2, 'OBG'), (2, 'SUR')})
        for paper, source in data['sources'].items():
            self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$', paper)

    def test_no_explanation_text_of_the_solution_is_included(self):
        data = load_paper(CMS_2026)
        allowed = {'paper', 'number', 'page', 'subject_code', 'chapter', 'topic', 'subtopic', 'question_text',
                   'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'needs_figure'}
        # The solution's own section labels (UPSC's "Select the correct answer using the code" is fine).
        leak = re.compile(r'Detailed Explanation|Distractor Explanation|Clinical Pearl|Trap / Common|'
                          r'Correct Answer\s*:|Reference Standard|Salaah', re.I)
        for q in data['questions']:
            self.assertLessEqual(set(q), allowed, q['number'])
            for field in ('question_text', 'option_a', 'option_b', 'option_c', 'option_d'):
                self.assertIsNone(leak.search(q[field]), (q['paper'], q['number'], field))

    def test_figures_the_solution_only_described_are_marked_and_the_descriptions_removed(self):
        # The solution writes its own bracketed description where the paper had a figure ("(Image shows
        # ... fusion of the lower poles of both kidneys ...)"): their writing, and it names the answer.
        data = load_paper(CMS_2026)
        needs = {(q['paper'], q['number']) for q in data['questions'] if q.get('needs_figure')}
        self.assertEqual(needs, {(1, 17), (1, 109), (1, 110), (2, 84), (2, 88), (2, 92), (2, 94), (2, 95),
                                 (2, 97), (2, 101), (2, 106), (2, 108), (2, 109), (2, 118)})
        description = re.compile(r'\((?:image|images|ct image|diagram|line diagram|figure)\b', re.I)
        for q in data['questions']:
            self.assertIsNone(description.search(q['question_text']), (q['paper'], q['number']))
        # The text of P1 Q74 states the whole case (its figure only illustrated it): it stays visible.
        q74 = next(q for q in data['questions'] if (q['paper'], q['number']) == (1, 74))
        self.assertFalse(q74.get('needs_figure'))
        self.assertTrue(q74['question_text'].endswith('This is a manifestation of:'))

    def test_match_the_list_questions_carry_their_table(self):
        data = load_paper(CMS_2026)
        by_key = {(q['paper'], q['number']): q for q in data['questions']}
        for key in ((1, 24), (1, 113), (1, 115), (2, 64), (2, 68)):
            self.assertIn('|---|---|', by_key[key]['question_text'], key)
        self.assertIn('| B. Enoxaparin | 2. Antiplatelet |', by_key[(1, 24)]['question_text'])
