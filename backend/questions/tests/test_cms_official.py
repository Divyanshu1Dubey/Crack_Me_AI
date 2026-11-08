"""UPSC CMS 2018-2025 made to match the official papers (questions.cms_official, migration 0047).

The plan is written for rows as they were found: a row that changed since is left alone (all its operations), a
second run changes nothing, a snapshot is stored before a row changes, nothing is deleted, key changes are
recorded as AnswerKeyChange with the official key as evidence, and formatting-only rewrites keep the hashes that
tie an explanation and the audit to the question.
"""
import copy
import io

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from questions import cms_official
from questions.content_hashes import stem_hash, valid_key
from questions.models import AnswerKeyChange, Question, QuestionRevisionSnapshot, Subject, Topic

SOURCE = {'title': 'UPSC CMS 2009-2025 with Answer Key.pdf', 'sha256': 'f' * 64, 'series': 'A'}


def _apply(data):
    return cms_official.apply_plan(question_model=Question, snapshot_model=QuestionRevisionSnapshot,
                                   key_change_model=AnswerKeyChange, subject_model=Subject, data=data)


def _guard(q):
    return {'stem_hash': stem_hash(q), 'key': valid_key(q.correct_answer), 'active': q.is_active,
            'cur_paper': q.paper, 'year': q.year}


class ApplyPlanTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.surgery = Subject.objects.create(name='General Surgery', code='GS-T')
        cls.psm = Subject.objects.create(name='Community Medicine', code='CM-T')
        Subject.objects.create(name='General Medicine', code='GM-T')
        cls.psm_topic = Topic.objects.create(subject=cls.psm, name='Epidemiology')
        cls.surgery_topic = Topic.objects.create(subject=cls.surgery, name='Epidemiology')

    def _q(self, text='The commonest site of pressure sore is:', key='B', paper=2, year=2025, active=True, **kw):
        for field, value in (('option_a', 'Heel'), ('option_b', 'Sacrum'), ('option_c', 'Ischium'),
                             ('option_d', 'Occiput'), ('subject', self.surgery)):
            kw.setdefault(field, value)
        return Question.objects.create(year=year, paper=paper, exam_type='cms', question_text=text,
                                       correct_answer=key, is_active=active, **kw)

    def _data(self, ops, letter_map=None):
        return {'source': SOURCE, 'key_pages': {'2025_P2': 65}, 'keys': {}, 'letter_map': letter_map or {},
                'ops': ops}

    def test_key_change_is_recorded_with_the_official_key_as_evidence_and_the_explanation_marked_stale(self):
        q = self._q(explanation='Sacrum is the commonest site.', explanation_for_key='B')
        op = {'op': 'key', 'id': q.pk, 'from': 'B', 'to': 'C', 'official': 'C', 'off': '2025_P2', 'n': 11,
              'key_page': 65, **_guard(q)}
        results = _apply(self._data([op]))
        self.assertEqual(results['key applied'], 1)
        q.refresh_from_db()
        self.assertEqual(q.correct_answer, 'C')
        self.assertEqual(q.explanation_status, 'stale')
        change = AnswerKeyChange.objects.get(question=q)
        self.assertEqual((change.old_key, change.new_key, change.source), ('B', 'C', 'official_key'))
        self.assertEqual(change.evidence[0]['kind'], 'official_key')
        self.assertEqual(change.evidence[0]['page_start'], 65)
        self.assertEqual(change.evidence[0]['supports_option'], 'C')
        self.assertTrue(QuestionRevisionSnapshot.objects.filter(question=q).exists())

    def test_an_explanation_written_for_the_official_key_is_not_marked_stale(self):
        q = self._q(explanation='Ischium.', explanation_for_key='C', explanation_status='ai_generated')
        op = {'op': 'key', 'id': q.pk, 'from': 'B', 'to': 'C', 'official': 'C', 'off': '2025_P2', 'n': 11,
              'key_page': 65, **_guard(q)}
        _apply(self._data([op]))
        q.refresh_from_db()
        self.assertEqual(q.explanation_status, 'ai_generated')

    def test_a_row_edited_since_the_plan_is_left_alone_with_all_its_operations(self):
        q = self._q()
        guard = _guard(q)
        Question.objects.filter(pk=q.pk).update(question_text='An admin rewrote this stem meanwhile')
        ops = [{'op': 'place', 'id': q.pk, 'to_paper': 2, 'to_n': 11, 'off': '2025_P2', 'n': 11, **guard},
               {'op': 'key', 'id': q.pk, 'from': 'B', 'to': 'C', 'official': 'C', 'off': '2025_P2', 'n': 11,
                'key_page': 65, **guard}]
        results = _apply(self._data(ops))
        self.assertEqual(results['place skipped: stem or options changed'], 1)
        self.assertEqual(results['key skipped: stem or options changed'], 1)
        q.refresh_from_db()
        self.assertEqual((q.correct_answer, q.display_number), ('B', None))
        self.assertFalse(AnswerKeyChange.objects.filter(question=q).exists())

    def test_a_duplicate_is_hidden_only_while_its_kept_copy_is_unchanged(self):
        keep = self._q(text='Commonest site of pressure sore')
        dup = self._q(paper=0)
        ops = [{'op': 'hide', 'id': dup.pk, 'keep': keep.pk, 'reason': 'duplicate', **_guard(dup)},
               {'op': 'place', 'id': keep.pk, 'to_paper': 2, 'to_n': 11, 'off': '2025_P2', 'n': 11, **_guard(keep)}]
        Question.objects.filter(pk=keep.pk).update(correct_answer='D')  # the kept copy changed meanwhile
        results = _apply(self._data(ops))
        self.assertEqual(results['hide skipped: kept copy changed since the plan'], 1)
        dup.refresh_from_db()
        self.assertTrue(dup.is_active)

    def test_hide_restore_place_and_dropped(self):
        dup = self._q(paper=0)
        keep = self._q(text='Pressure sores: the commonest site is')
        hidden = self._q(text='A restored question', key='', active=False, is_dropped=True)
        ops = [
            {'op': 'hide', 'id': dup.pk, 'keep': keep.pk, 'reason': 'duplicate', **_guard(dup)},
            {'op': 'restore', 'id': hidden.pk, 'off': '2025_P2', 'n': 12, **_guard(hidden)},
            {'op': 'place', 'id': hidden.pk, 'to_paper': 2, 'to_n': 12, 'off': '2025_P2', 'n': 12, **_guard(hidden)},
            {'op': 'key', 'id': hidden.pk, 'from': '', 'to': 'A', 'official': 'A', 'off': '2025_P2', 'n': 12,
             'key_page': 65, **_guard(hidden)},
            {'op': 'dropped', 'id': keep.pk, 'off': '2025_P2', 'n': 11, **_guard(keep)},
        ]
        _apply(self._data(ops))
        dup.refresh_from_db()
        hidden.refresh_from_db()
        keep.refresh_from_db()
        self.assertFalse(dup.is_active)
        self.assertTrue(hidden.is_active)
        self.assertFalse(hidden.is_dropped)
        self.assertEqual((hidden.paper, hidden.display_number, hidden.correct_answer), (2, 12, 'A'))
        self.assertTrue(keep.is_dropped and keep.is_active)
        self.assertEqual(Question.objects.filter(pk__in=[dup.pk, keep.pk, hidden.pk]).count(), 3)  # nothing deleted

    def test_add_creates_the_official_question_with_its_key_and_section_subject(self):
        text = {'question_text': 'Which drug is a long acting local anaesthetic agent?', 'option_a': 'Lignocaine',
                'option_b': 'Bupivacaine', 'option_c': 'Prilocaine', 'option_d': 'Ropivacaine'}
        ops = [{'op': 'add', 'year': 2023, 'paper': 2, 'n': 35, 'text': text, 'off': '2023_P2', 'key_page': 189},
               {'op': 'key', 'id': None, 'from': '', 'to': 'B', 'official': 'B', 'off': '2023_P2', 'n': 35,
                'key_page': 189}]
        results = _apply(self._data(ops))
        self.assertEqual(results['add applied'], 1)
        q = Question.objects.get(year=2023, paper=2, display_number=35)
        self.assertEqual((q.correct_answer, q.subject.name, q.exam_type), ('B', 'General Surgery', 'cms'))
        again = _apply(self._data(ops))
        self.assertEqual(again['add skipped: already in the bank'], 1)
        self.assertEqual(Question.objects.filter(year=2023, display_number=35).count(), 1)

    def test_subject_moves_with_a_topic_of_the_same_name(self):
        q = self._q(year=2018, topic=self.surgery_topic)
        op = {'op': 'subject', 'id': q.pk, 'to_subject': 'Community Medicine', 'off': '2018_P2', 'n': 1, **_guard(q)}
        _apply(self._data([op]))
        q.refresh_from_db()
        self.assertEqual((q.subject_id, q.topic_id), (self.psm.pk, self.psm_topic.pk))

    def test_format_and_mojibake_keep_the_explanation_attached(self):
        q = self._q(text='Which of the following are correct?\nFirst\nSecond\nSelect the correct answer:',
                    explanation='FEV1 Γåô and TLC Γåæ', option_a='1 only', option_b='2 only', option_c='Both 1 and 2',
                    option_d='Neither 1 nor 2')
        Question.objects.filter(pk=q.pk).update(explanation_stem_hash=stem_hash(q))
        q.refresh_from_db()
        numbered = 'Which of the following are correct?\n1. First\n2. Second\nSelect the correct answer:'
        ops = [{'op': 'format', 'id': q.pk, 'fields': {'question_text': numbered}, 'reason': 'numbered',
                'off': '2025_P2', 'n': 5, **_guard(q)},
               {'op': 'mojibake', 'id': q.pk, 'fields': ['explanation'], 'stem_hash': stem_hash(q)}]
        results = _apply(self._data(ops))
        self.assertEqual((results['format applied'], results['mojibake applied']), (1, 1))
        q.refresh_from_db()
        self.assertEqual(q.question_text, numbered)
        self.assertEqual(q.explanation, 'FEV1 ↓ and TLC ↑')
        self.assertEqual(q.explanation_stem_hash, stem_hash(q))  # still attached to the (renumbered) stem

    def test_a_second_run_changes_nothing(self):
        q = self._q()
        ops = [{'op': 'place', 'id': q.pk, 'to_paper': 2, 'to_n': 11, 'off': '2025_P2', 'n': 11, **_guard(q)},
               {'op': 'key', 'id': q.pk, 'from': 'B', 'to': 'C', 'official': 'C', 'off': '2025_P2', 'n': 11,
                'key_page': 65, **_guard(q)}]
        data = self._data(ops)
        _apply(copy.deepcopy(data))
        snapshots = QuestionRevisionSnapshot.objects.count()
        again = _apply(copy.deepcopy(data))
        self.assertFalse([k for k in again if k.endswith(' applied')])
        self.assertEqual(QuestionRevisionSnapshot.objects.count(), snapshots)
        self.assertEqual(AnswerKeyChange.objects.filter(question=q).count(), 1)


class FigureTests(TestCase):
    """Figures cropped from an official paper (the 2026 plan): attached, and a question hidden only for its
    missing figure made live."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='General Surgery', code='GS-F')

    def setUp(self):
        import hashlib
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name) / 'figs'
        folder.mkdir()
        self.blob = b'\xff\xd8\xff\xe0 test figure \xff\xd9'
        (folder / 'cms2026_p2_q8.jpg').write_bytes(self.blob)
        self.fig = {'file': 'cms2026_p2_q8.jpg', 'sha256': hashlib.sha256(self.blob).hexdigest(), 'width': 10,
                    'height': 8, 'page': 3}

    def _q(self, active):
        return Question.objects.create(
            subject=self.subject, year=2026, paper=2, exam_type='cms', is_active=active, correct_answer='C',
            question_text='The typical ulcer as shown in the following diagram is seen in', option_a='syphilis',
            option_b='squamous cell carcinoma', option_c='tuberculosis', option_d='basal cell carcinoma')

    def _apply(self, ops):
        from questions.models import QuestionImage
        data = {'_dir': self.tmp.name, 'figures_dir': 'figs', 'source': SOURCE, 'ops': ops}
        return cms_official.apply_plan(question_model=Question, snapshot_model=QuestionRevisionSnapshot,
                                       key_change_model=AnswerKeyChange, subject_model=Subject,
                                       image_model=QuestionImage, data=data)

    def test_the_figure_is_attached_and_the_hidden_question_made_live(self):
        q = self._q(active=False)
        results = self._apply([{'op': 'figure', 'id': q.pk, 'figures': [self.fig], 'activate': True,
                                'off': '2026_P2', 'n': 8, **_guard(q)}])
        self.assertEqual(results['figure applied (question made live)'], 1)
        q.refresh_from_db()
        self.assertTrue(q.is_active)
        image = q.images.get()
        self.assertEqual((image.role, image.url), ('primary', '/media/question_figures/official/cms2026_p2_q8.jpg'))
        self.assertEqual(image.sha256, self.fig['sha256'])

    def test_a_question_that_has_its_figure_is_left_alone(self):
        q = self._q(active=True)
        op = {'op': 'figure', 'id': q.pk, 'figures': [self.fig], 'off': '2026_P2', 'n': 8, **_guard(q)}
        self._apply([op])
        again = self._apply([op])
        self.assertEqual(again['figure skipped: already has its figure'], 1)
        self.assertEqual(q.images.count(), 1)

    def test_a_figure_file_that_does_not_match_its_checksum_is_refused(self):
        q = self._q(active=False)
        bad = dict(self.fig, sha256='0' * 64)
        results = self._apply([{'op': 'figure', 'id': q.pk, 'figures': [bad], 'activate': True, 'off': '2026_P2',
                                'n': 8, **_guard(q)}])
        self.assertEqual(results['figure skipped: figure file does not match its checksum'], 1)
        q.refresh_from_db()
        self.assertFalse(q.is_active)


class Data2026FileTests(SimpleTestCase):

    def test_every_official_number_is_placed_once_and_every_figure_file_is_present(self):
        import hashlib
        from collections import Counter
        from pathlib import Path
        data = cms_official.load_data(cms_official.DATA_2026)
        places = Counter((op['to_paper'], op['to_n']) for op in data['ops'] if op['op'] == 'place')
        for paper in (1, 2):
            self.assertEqual(sorted(n for p, n in places if p == paper), list(range(1, 121)), paper)
        self.assertEqual(max(places.values()), 1)
        folder = Path(data['_dir']) / data['figures_dir']
        figures = [fig for op in data['ops'] if op['op'] == 'figure' for fig in op['figures']]
        self.assertEqual(len(figures), 16)
        for fig in figures:
            self.assertEqual(hashlib.sha256((folder / fig['file']).read_bytes()).hexdigest(), fig['sha256'])
        self.assertFalse([op for op in data['ops'] if op['op'] == 'key'])  # no official 2026 key: keys untouched


class MojibakeTests(SimpleTestCase):

    def test_utf8_read_as_cp437_is_decoded(self):
        self.assertEqual(cms_official.repair_mojibake('500ΓÇô1,000 ΓåÆ 10 ┬░C, 3├ù, ╬▓-blocker, ΓëÑ 2'),
                         '500–1,000 → 10 °C, 3×, β-blocker, ≥ 2')

    def test_real_greek_and_accents_are_left_alone(self):
        for text in ('α-fetoprotein', 'Ménière disease', 'Γ-globulin', '37 °C', 'café'):
            self.assertEqual(cms_official.repair_mojibake(text), text)


class SectionSubjectTests(SimpleTestCase):

    def test_sections(self):
        self.assertEqual(cms_official.subject_name(1, 96), 'General Medicine')
        self.assertEqual(cms_official.subject_name(1, 97), 'Paediatrics')
        self.assertEqual(cms_official.subject_name(2, 40), 'General Surgery')
        self.assertEqual(cms_official.subject_name(2, 41), 'Obstetrics & Gynaecology')
        self.assertEqual(cms_official.subject_name(2, 81), 'Community Medicine')

    def test_the_2018_paper_two_runs_psm_first(self):
        self.assertEqual(cms_official.subject_name(2, 1, 2018), 'Community Medicine')
        self.assertEqual(cms_official.subject_name(2, 81, 2018), 'General Surgery')


class DataFileTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = cms_official.load_data()

    def test_every_paper_has_its_120_official_keys(self):
        self.assertEqual(len(self.data['keys']), 16)
        for paper, keys in self.data['keys'].items():
            self.assertEqual(sorted(map(int, keys)), list(range(1, 121)), paper)
            for n, key in keys.items():
                self.assertRegex(key, r'^([ABCD](/[ABCD])?|X)$', f'{paper} Q{n}')
            self.assertIn(paper, self.data['key_pages'])

    def test_operations_are_complete(self):
        for op in self.data['ops']:
            self.assertIn(op['op'], cms_official.OP_ORDER)
            if op['op'] == 'add':
                self.assertTrue(op['text']['question_text'].strip())
                self.assertTrue(all(op['text'][f'option_{l}'].strip() for l in 'abcd'), op)
            if op['op'] == 'key':
                self.assertIn(op['to'], 'ABCD')
            if op.get('id') is not None:
                self.assertRegex(op['stem_hash'], r'^[0-9a-f]{64}$')

    def test_operations_of_one_row_share_one_guard(self):
        seen = {}
        for op in self.data['ops']:
            if op.get('id') is None:
                continue
            guard = {k: op.get(k) for k in ('stem_hash', 'key', 'active', 'cur_paper') if k in op}
            first = seen.setdefault(op['id'], guard)
            for k in set(first) & set(guard):
                self.assertEqual(first[k], guard[k], (op['id'], k))


class RecordOfficialKeysTests(TestCase):

    def test_a_dry_run_on_an_empty_bank_records_nothing(self):
        out = io.StringIO()
        call_command('record_official_cms_keys', stdout=out)
        self.assertIn('0 question(s) found', out.getvalue())

    def test_the_official_key_is_recorded_once(self):
        from key_audit.models import QuestionAudit
        subject = Subject.objects.create(name='General Surgery', code='GS-R')
        q = Question.objects.create(  # CMS 2025 Paper II Q11: official key C
            subject=subject, year=2025, paper=2, display_number=11, exam_type='cms',
            question_text='The commonest site of pressure sore is:', option_a='Heel', option_b='Sacrum',
            option_c='Ischium', option_d='Occiput', correct_answer='C')
        call_command('record_official_cms_keys', apply=True, stdout=io.StringIO())
        reviews = QuestionAudit.objects.get(question=q).reviews
        official = [r for r in reviews if r.get('reviewer') == 'official_key']
        self.assertEqual(len(official), 1)
        self.assertEqual((official[0]['best_option'], official[0]['verdict']), ('C', 'agree'))
        out = io.StringIO()
        call_command('record_official_cms_keys', apply=True, stdout=out)
        self.assertIn('1 already recorded, 0 to record', out.getvalue())
