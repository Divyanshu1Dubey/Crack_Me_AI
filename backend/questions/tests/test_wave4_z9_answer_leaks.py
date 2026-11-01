"""Wave-4 Z9 (questions app): answer keys / explanations that imports left in
the public stem / option text (questions.answer_leak) -- the detector, the
serving guard on every list / detail / search payload, the repair command
and the import_mocktests gate.

No AI provider, Supabase or network call is made.
"""
from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions import answer_leak as al
from questions.models import Question, QuestionBookmark, QuestionRevisionSnapshot, Subject
from questions.serializers import QuestionDetailSerializer, QuestionListSerializer

User = get_user_model()

# Shapes taken from the restored production bank.
OPTION_LEAK = 'I and IV only Correct Answer: A. I, II and IV only'
STEM_LEAK = (
    "Consider the following features of De Quervain's disease:\n\n"
    "1. Tenosynovitis of 1st dorsal extensor compartment\n"
    "2. Predominantly seen in middle-aged females\n"
    "3. Associated with pregnancy\n"
    "4. Positive Phalen's test is diagnostic\n"
    "Explanation: De Quervain's involves the 1st extensor compartment. "
    "Finkelstein's test (not Phalen's) is the diagnostic test."
)
STEM_CLEAN = STEM_LEAK.split('\nExplanation:')[0]
PASTED_PAGE = (
    "23. The risk of disease is measured by\n(a) Prevalence Rate\n(b) Incidence Rate\n"
    "(c) Attrition Rate\n(d) Fatality Rate\nAns: (b) Incidence Rate\n"
    "The risk of disease is measured by the incidence rate.\n24. Which of the following ..."
)
ANSWER_KEY_OPTION = (
    'Cavernous sinus thrombosis\nAnswer Key\nQuestion No. Correct Option\n1 b\n2 d\n3 b\n'
    'Detailed Explanations\nSolution to Question 1:\nThe hydration of the cornea ...'
)


def _premium(username):
    user = User.objects.create_user(username=username, email=f'{username}@example.com', password='unused-pw-1')
    Subscription.objects.create(user=user, plan='1_year', status='active',
                                expires_at=timezone.now() + timedelta(days=365))
    return user


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


# ── Detector ─────────────────────────────────────────────────────────────

class DetectorTests(SimpleTestCase):
    def test_option_answer_label_is_cut_at_the_label(self):
        labels = al.find_labels(OPTION_LEAK)
        self.assertEqual([(lab.kind, lab.letter) for lab in labels], [(al.ANSWER, 'A')])
        self.assertEqual(al.cut_at_answer_label(OPTION_LEAK), 'I and IV only')

    def test_stem_explanation_and_pasted_answers_are_cut(self):
        self.assertEqual(al.cut_at_answer_label(STEM_LEAK), STEM_CLEAN)
        cut = al.cut_at_answer_label(PASTED_PAGE)
        self.assertNotIn('Ans:', cut)
        self.assertNotIn('measured by the incidence rate', cut)
        self.assertEqual(al.cut_at_answer_label(ANSWER_KEY_OPTION), 'Cavernous sinus thrombosis')

    def test_other_label_shapes(self):
        for text, head in (
            ('Meningitis\n\nAns. is b i.e. Temporal lobe abscess\nExplanation\nTemporal lobe ...', 'Meningitis'),
            ("Osteopetrosis\n\nAns. is 'a' i.e. Ankylosing Spondylitis", 'Osteopetrosis'),
            ('Glaucoma\n\nAnswer <B: Exposure Keratitis', 'Glaucoma'),
            ('... endoscopy Answer ( a ) Early skilled endoscopy is must', '... endoscopy'),
            ('A scaphoid abdomen Trap Explanation: In GOO the vomitus lacks bile.', 'A scaphoid abdomen'),
            ('4. Chronic reduction in RBC survival.\n5. Explanation: Anemia in CKD is multifactorial.',
             '4. Chronic reduction in RBC survival.'),
            ('IV. Asymptomatic fibroids are managed conservatively.\nWhy: Statement II is incorrect.',
             'IV. Asymptomatic fibroids are managed conservatively.'),
            ('The correct answer is (a) 1, 2 and 3.', 'The'),
        ):
            self.assertTrue(al.has_answer_label(text), text)
            self.assertEqual(al.cut_at_answer_label(text), head, text)

    def test_prompts_and_ordinary_wording_are_not_labels(self):
        for text in (
            'Select the correct answer using the code given below:',
            'Which are causes of oliguria?\nSelect the correct answer:\n(a) 1 and 2 only\n(b) 1, 2 and 3 only',
            'Choose the correct answer - (a) Gamma (b) Delta',
            'Both A and R are true, and R is the correct explanation of A',
            'The correct answer is a combination of gamma and delta',
            'Explanation',
            'Deficiency of vitamin D.',
            'ANS: autonomic nervous system involvement',
            'Correct answer is:',
            'Transient answers to plans',
        ):
            self.assertFalse(al.has_answer_label(text), text)
            self.assertEqual(al.cut_at_answer_label(text), text)

    def test_image_tokens_of_the_cut_part_are_kept(self):
        text = 'Identify the lesion.\n\nExplanation: It is a keloid.\n\n[[img:12]]\n[[img:13]]'
        self.assertEqual(al.cut_at_answer_label(text), 'Identify the lesion.\n\n[[img:12]]\n[[img:13]]')

    def test_redact_public_text_and_hold_reasons(self):
        row = {'question_text': STEM_LEAK, 'option_a': 'x', 'option_d': OPTION_LEAK, 'explanation': 'kept'}
        self.assertTrue(al.redact_public_text(row))
        self.assertEqual((row['question_text'], row['option_d'], row['explanation']),
                         (STEM_CLEAN, 'I and IV only', 'kept'))
        self.assertFalse(al.redact_public_text(row))
        self.assertEqual(al.label_hold_reasons(STEM_LEAK, ['x', OPTION_LEAK]),
                         ['answer_label_in_public_text', 'explanation_label_in_public_text'])
        self.assertEqual(al.label_hold_reasons('Clean stem?', ['a', 'b', 'c', 'd']), [])


class PlanRepairTests(SimpleTestCase):
    BASE = dict(question_text='Which statements are correct?', option_a='I, II and IV only',
                option_b='I, II, III and IV', option_c='II, III and IV only', option_d=OPTION_LEAK,
                correct_answer='', explanation='')

    def _plan(self, **kw):
        return al.plan_repair({**self.BASE, **kw})

    def test_option_label_sets_an_empty_key_and_cuts_the_option(self):
        plan = self._plan()
        self.assertFalse(plan.deactivate)
        self.assertEqual(plan.changes, {'option_d': 'I and IV only', 'correct_answer': 'A'})

    def test_a_stored_key_is_never_changed(self):
        self.assertEqual(self._plan(correct_answer='A').changes, {'option_d': 'I and IV only'})
        plan = self._plan(correct_answer='C')
        self.assertTrue(plan.conflict)
        self.assertNotIn('correct_answer', plan.changes)
        locked = self._plan(lock_answer=True)
        self.assertNotIn('correct_answer', locked.changes)

    def test_label_that_does_not_repeat_its_option_is_not_applied(self):
        plan = self._plan(option_d='I and IV only Correct Answer: A. Something else entirely')
        self.assertTrue(plan.conflict)
        self.assertEqual(plan.changes, {'option_d': 'I and IV only'})

    def test_text_after_the_named_option_moves_to_the_explanation(self):
        plan = self._plan(option_d='I and IV only Ans: (a) I, II and IV only Why: Statement III is wrong.')
        self.assertEqual(plan.changes['correct_answer'], 'A')
        self.assertEqual(plan.changes['explanation'], 'Statement III is wrong.')

    def test_stem_explanation_moves_to_the_explanation(self):
        plan = al.plan_repair({**self.BASE, 'option_d': 'I and IV only', 'correct_answer': 'A',
                               'question_text': STEM_LEAK})
        self.assertEqual(plan.changes['question_text'], STEM_CLEAN)
        self.assertTrue(plan.changes['explanation'].startswith("De Quervain's involves"))
        # An explanation that is only a copy of an option (import artefact)
        # is replaced; a real one keeps its text and gets the moved part.
        copy = al.plan_repair({**self.BASE, 'option_d': 'I and IV only', 'question_text': STEM_LEAK,
                               'explanation': 'I, II and IV only'})
        self.assertTrue(copy.changes['explanation'].startswith("De Quervain's"))
        real = al.plan_repair({**self.BASE, 'option_d': 'I and IV only', 'question_text': STEM_LEAK,
                               'explanation': 'Curated text.'})
        self.assertTrue(real.changes['explanation'].startswith('Curated text.\n\nDe Quervain'))
        locked = al.plan_repair({**self.BASE, 'option_d': 'I and IV only', 'question_text': STEM_LEAK,
                                 'explanation': 'Curated text.', 'lock_explanation': True})
        self.assertNotIn('explanation', locked.changes)
        self.assertEqual(locked.changes['question_text'], STEM_CLEAN)

    def test_answer_key_tables_are_dropped(self):
        plan = self._plan(option_d=ANSWER_KEY_OPTION, correct_answer='A')
        self.assertEqual(plan.changes, {'option_d': 'Cavernous sinus thrombosis'})
        self.assertEqual(plan.category, 'option_answer_key')

    def test_unrepairable_rows_are_held_untouched(self):
        for kw, category in (
            ({'question_text': PASTED_PAGE}, 'pasted_page'),
            ({'option_a': 'Explanation: Functional cysts are usually under 7 cm.'}, 'option_is_label'),
            ({'option_d': 'Answer Key\n3437'}, 'option_is_label'),
            ({'question_text': 'Explanation: only an explanation here.'}, 'stem_is_label'),
        ):
            plan = self._plan(**kw)
            self.assertTrue(plan.deactivate, kw)
            self.assertEqual(plan.category, category, kw)
            self.assertEqual(plan.changes, {}, kw)

    def test_clean_rows_need_nothing(self):
        plan = al.plan_repair({**self.BASE, 'option_d': 'I and IV only', 'correct_answer': 'A'})
        self.assertFalse(plan.needed)


# ── Serving guard ────────────────────────────────────────────────────────

class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Z9 Wave4 Subject', code='Z9W4')
        cls.free = User.objects.create_user(username='z9w4-free', email='z9w4-free@example.com',
                                            password='unused-pw-2')
        cls.premium = _premium('z9w4-premium')
        cls.admin = User.objects.create_user(username='z9w4-admin', password='unused-pw-3', role='admin')
        common = dict(option_a='I, II and IV only', option_b='I, II, III and IV',
                      option_c='II, III and IV only', year=2024, subject=cls.subject)
        cls.locked = Question.objects.create(question_text=STEM_LEAK, option_d=OPTION_LEAK,
                                             correct_answer='A', **common)
        cls.showcase = Question.objects.create(question_text=STEM_LEAK + ' (showcase)', option_d=OPTION_LEAK,
                                               correct_answer='A', **common)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        # Saving normalises the text; compare against the stored values.
        cls.locked.refresh_from_db()
        cls.showcase.refresh_from_db()

    def setUp(self):
        cache.clear()

    def assert_cut(self, row):
        self.assertEqual(row['option_d'], 'I and IV only')
        self.assertNotIn('Correct Answer', json.dumps(row, default=str))
        self.assertNotIn('Finkelstein', json.dumps(row, default=str))
        self.assertTrue(row['question_text'].startswith("Consider the following features of De Quervain's"))
        self.assertTrue(row['question_text'].endswith("Positive Phalen's test is diagnostic"))

    def assert_full(self, row, question):
        self.assertEqual(row['option_d'], question.option_d)
        self.assertEqual(row['question_text'], question.question_text)


class ServingGuardTests(_Base):
    def _list_row(self, user, question, **params):
        res = _client(user).get('/api/questions/', {'question_id': question.id, **params})
        self.assertEqual(res.status_code, 200, res.data)
        return res.data['results'][0]

    def test_anonymous_and_free_list_rows_are_cut(self):
        self.assert_cut(self._list_row(None, self.locked))
        self.assert_cut(self._list_row(self.free, self.locked))
        # The finding's probe: ?search=Explanation matched the hidden text.
        # It no longer matches inside the cut part (wave 4b,
        # questions.locked_text_search); the showcase row's answer is free.
        res = _client().get('/api/questions/', {'search': 'Explanation'})
        rows = {row['id']: row for row in res.data['results']}
        self.assertNotIn(self.locked.id, rows)
        self.assert_full(rows[self.showcase.id], self.showcase)
        # Text the viewer sees still finds the row, cut.
        res = _client().get('/api/questions/', {'search': 'Quervain'})
        rows = {row['id']: row for row in res.data['results']}
        self.assert_cut(rows[self.locked.id])

    def test_entitled_viewers_keep_the_stored_text(self):
        self.assert_full(self._list_row(self.premium, self.locked), self.locked)
        self.assert_full(self._list_row(self.admin, self.locked), self.locked)
        self.assert_full(self._list_row(None, self.showcase), self.showcase)
        self.assert_full(self._list_row(self.free, self.showcase), self.showcase)

    def test_detail_is_cut_for_anonymous_viewers_only(self):
        res = _client().get(f'/api/questions/{self.locked.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['answer_locked'])
        self.assert_cut(res.data)
        for user in (self.premium, self.admin):
            res = _client(user).get(f'/api/questions/{self.locked.id}/')
            self.assert_full(res.data, self.locked)
        self.assert_full(_client(self.free).get(f'/api/questions/{self.showcase.id}/').data, self.showcase)

    def test_recall_search_rows_are_cut(self):
        # The finding's probe: an anonymous keyword match on the label text.
        # It no longer returns the locked row (wave 4b,
        # questions.locked_text_search); the showcase row keeps its text.
        res = _client().get('/api/questions/recall_search/', {'drug': 'Correct Answer', 'page_size': 100})
        self.assertEqual(res.status_code, 200)
        rows = {row['id']: row for row in res.data['results']}
        self.assertNotIn(self.locked.id, rows)
        self.assert_full(rows[self.showcase.id], self.showcase)
        # A keyword the viewer sees finds it, cut.
        res = _client().get('/api/questions/recall_search/', {'drug': 'I and IV only', 'page_size': 100})
        rows = {row['id']: row for row in res.data['results']}
        self.assert_cut(rows[self.locked.id])
        res = _client(self.premium).get('/api/questions/recall_search/', {'drug': 'Correct Answer'})
        rows = {row['id']: row for row in res.data['results']}
        self.assert_full(rows[self.locked.id], self.locked)

    def test_bookmarks_and_serializer_callers_without_a_request(self):
        QuestionBookmark.objects.create(user=self.free, question=self.locked)
        res = _client(self.free).get('/api/questions/bookmarks/')
        self.assertEqual(res.status_code, 200, res.data)
        rows = res.data if isinstance(res.data, list) else res.data.get('results', res.data)
        self.assert_cut(rows[0]['question_detail'])
        # tests_engine's /start/ payload: the list serializer with
        # viewer_full_access in the context.
        locked = QuestionListSerializer(self.locked, context={'viewer_full_access': False}).data
        self.assert_cut(locked)
        full = QuestionListSerializer(self.locked, context={'viewer_full_access': True}).data
        self.assert_full(full, self.locked)
        detail = QuestionDetailSerializer(self.locked, context={'viewer_full_access': False}).data
        self.assert_cut(detail)

    def test_related_pyqs_stems_are_cut(self):
        other = Question.objects.create(
            question_text="De Quervain's disease features compared", option_a='a', option_b='b',
            option_c='c', option_d='d', correct_answer='A', year=2024, subject=self.subject,
        )
        Question.objects.filter(pk__in=[self.locked.pk, other.pk]).update(concept_id='dequervain')
        res = _client().get(f'/api/questions/{other.id}/ai/related_pyqs/')
        self.assertEqual(res.status_code, 200, res.data)
        rows = {row['id']: row for row in res.data['related_pyqs']}
        self.assertNotIn('Finkelstein', rows[self.locked.id]['question_text'])
        cache.clear()
        res = _client(self.premium).get(f'/api/questions/{other.id}/ai/related_pyqs/')
        rows = {row['id']: row for row in res.data['related_pyqs']}
        self.assertIn('Finkelstein', rows[self.locked.id]['question_text'])


# ── Repair command ───────────────────────────────────────────────────────

class RepairCommandTests(_Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        common = dict(option_a='1 only', option_b='2 and 3', option_c='1, 3 and 4', option_d='4 only',
                      year=2024, subject=cls.subject)
        cls.empty_key = Question.objects.create(
            question_text='Which of the following?', correct_answer='', **{**common, 'option_a': 'I, II and IV only',
                                                                             'option_d': OPTION_LEAK},
        )
        cls.pasted = Question.objects.create(question_text=PASTED_PAGE, correct_answer='A', **common)
        cls.clean = Question.objects.create(question_text='A clean question?', correct_answer='B', **common)

    def _run(self, *args):
        out = StringIO()
        call_command('fix_answer_label_leaks', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_and_writes_nothing(self):
        before = {q.pk: (q.question_text, q.option_d, q.correct_answer, q.is_active)
                  for q in Question.objects.all()}
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'plan.json'
            out = self._run('--json-report', str(report))
            plan = json.loads(report.read_text(encoding='utf-8'))
        self.assertIn('DRY RUN', out)
        self.assertIn(str(self.pasted.pk), out)
        by_id = {row['id']: row for row in plan['questions']}
        self.assertEqual(set(by_id), {self.locked.pk, self.showcase.pk, self.empty_key.pk, self.pasted.pk})
        self.assertTrue(by_id[self.pasted.pk]['deactivate'])
        self.assertEqual(by_id[self.empty_key.pk]['after']['correct_answer'], 'A')
        after = {q.pk: (q.question_text, q.option_d, q.correct_answer, q.is_active)
                 for q in Question.objects.all()}
        self.assertEqual(before, after)
        self.assertFalse(QuestionRevisionSnapshot.objects.exists())

    def test_apply_repairs_holds_and_snapshots(self):
        self._run('--apply')
        locked = Question.objects.get(pk=self.locked.pk)
        self.assertEqual(locked.option_d, 'I and IV only')
        self.assertEqual(locked.question_text, al.cut_at_answer_label(self.locked.question_text))
        self.assertNotIn('Finkelstein', locked.question_text)
        self.assertTrue(locked.explanation.startswith("De Quervain's involves"))
        self.assertEqual(locked.correct_answer, 'A')
        self.assertTrue(locked.needs_review)
        self.assertTrue(locked.is_active)
        empty_key = Question.objects.get(pk=self.empty_key.pk)
        self.assertEqual((empty_key.option_d, empty_key.correct_answer), ('I and IV only', 'A'))
        pasted = Question.objects.get(pk=self.pasted.pk)
        self.assertFalse(pasted.is_active)
        self.assertTrue(pasted.needs_review)
        self.assertEqual(pasted.question_text, self.pasted.question_text)
        clean = Question.objects.get(pk=self.clean.pk)
        self.assertFalse(clean.needs_review)
        self.assertFalse(clean.revision_snapshots.exists())
        snapshot = QuestionRevisionSnapshot.objects.get(question=self.empty_key)
        self.assertEqual(snapshot.reason, 'Before fix_answer_label_leaks')
        self.assertEqual(snapshot.snapshot['option_d'], self.empty_key.option_d)
        self.assertEqual(snapshot.snapshot['correct_answer'], '')
        # Idempotent: a second run finds nothing left to do.
        out = self._run('--apply')
        self.assertIn('Applied: 0 repaired, 0 deactivated', out)
        self.assertEqual(QuestionRevisionSnapshot.objects.count(), 4)

    def test_ids_limit_the_run(self):
        self._run('--apply', '--ids', str(self.empty_key.pk))
        self.assertEqual(Question.objects.get(pk=self.locked.pk).option_d, self.locked.option_d)
        self.assertEqual(Question.objects.get(pk=self.empty_key.pk).option_d, 'I and IV only')


# ── import_mocktests gate ────────────────────────────────────────────────

class ImportMocktestsGateTests(SimpleTestCase):
    def test_statement_mode_explanation_is_moved_out_of_the_stem(self):
        from questions.management.commands.import_mocktests import answer_label_gate, parse_schema_b

        parsed = parse_schema_b([
            'Q1. Consider the following statements:',
            'I. Gamma is a vitamin', 'II. Delta is a mineral',
            'Select the correct answer using the code given below:',
            '(a) I only', '(b) II only', '(c) Both I and II', '(d) Neither I nor II',
            'Ans: (a) I only',
            'Explanation: Delta is not a mineral.',
        ])
        self.assertEqual(len(parsed), 1)
        pq = parsed[0]
        fields, hold = answer_label_gate(pq)
        self.assertEqual(hold, [])
        public = {**{name: getattr(pq, name) for name in al.PUBLIC_TEXT_FIELDS}, **fields}
        self.assertFalse(al.row_has_answer_label(public), public)

    def test_option_label_is_repaired_and_a_pasted_page_is_held(self):
        from questions.management.commands.import_mocktests import ParsedQuestion, answer_label_gate

        pq = ParsedQuestion(question_text='Which?', option_a='I, II and IV only', option_b='b',
                            option_c='c', option_d=OPTION_LEAK)
        fields, hold = answer_label_gate(pq)
        self.assertEqual(hold, [])
        self.assertEqual(fields, {'option_d': 'I and IV only', 'correct_answer': 'A'})
        page = ParsedQuestion(question_text=PASTED_PAGE, option_a='a', option_b='b', option_c='c',
                              option_d='d', correct_answer='A')
        fields, hold = answer_label_gate(page)
        self.assertEqual(fields, {})
        self.assertTrue(hold)
