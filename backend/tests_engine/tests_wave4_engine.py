"""Regression tests for the tests-engine fixes of fix wave 4 (group Z2).

* A locked row of /review/ or of the attempt detail (a question the student
  may not see, in an attempt scored before wave 3 or while premium) gives
  nothing of the answer away through its public text either: the stem and
  the options are cut as on locked question-bank rows
  (questions.answer_leak.redact_public_text) -- at an answer / explanation
  label an import left in them ("Ans: B"), and at a correctness flag such
  as "(correct)" or a tick together with the reason printed after it; the
  textbook pointers are blanked and concept_tags keep only "high_yield".
  GET /api/tests/<id>/ cuts the same text. The student's own pick and its
  right / wrong stay (wave-2 contract): /submit/ re-checks the questions,
  so no new attempt is ever scored on a question the student may not see.
  Entitled viewers get the text as stored.
* The loader's "Imported" subject (any case / spacing) is shown as "Expert
  Curated" in the review (row subject, subject_breakdown), the test
  payloads, generated titles and stored titles ("Imported — 20 Questions").
* A submit refreshes the dashboard_v3 caches of that student.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from questions.models import Question, Subject
from tests_engine.entitlement import lock_answer
from tests_engine.models import QuestionResponse, Test, TestAttempt
from tests_engine.serializers import public_test_title

User = get_user_model()

STEM = 'Which drug is the first-line treatment of anaphylaxis?'
STEM_WITH_KEY = f'{STEM}\nAns: B. Adrenaline 0.5 mg IM is the drug of choice (wave4 secret).'
# A stem that lists the options inline, one of them ticked (rows 10206 / 10222).
STEM_LISTING = f'{STEM}\nA. Atropine\nB. Adrenaline ✅\nC. Hydrocortisone\nD. Chlorphenamine'
STEM_LISTING_LOCKED = f'{STEM}\nA. Atropine\nB. Adrenaline\nC. Hydrocortisone\nD. Chlorphenamine'
SECRET_EXPLANATION = 'Adrenaline reverses the vasodilatation (wave4 secret)'
OPTIONS = {'A': 'Atropine', 'B': 'Adrenaline', 'C': 'Hydrocortisone', 'D': 'Chlorphenamine'}
FLAGGED_OPTIONS = {
    'A': 'Atropine',
    'B': 'Adrenaline (correct)',
    'C': 'Hydrocortisone (wrong)',
    'D': 'Chlorphenamine Correct Answer: B. Adrenaline',
}
# A tick and the reason for it after the flagged option (rows 24224 / 24226).
TICKED_OPTIONS = dict(OPTIONS, B='Adrenaline ✔ (Adrenaline is the drug of choice in anaphylaxis)')
TEXTBOOK = dict(book_name='Harrison', chapter='Anaphylaxis: adrenaline first', page_number='2710',
                concept_tags=['adrenaline for anaphylaxis', 'high_yield'])
SHOWN_TITLE = 'Expert Curated — 3 Questions'


def _q(subject, *, options=OPTIONS, **kw):
    data = dict(
        question_text=STEM, correct_answer='B', year=2024, subject=subject,
        explanation=SECRET_EXPLANATION, mnemonic='wave4 secret mnemonic',
        **{f'option_{letter.lower()}': text for letter, text in options.items()},
    )
    data.update(kw)
    return Question.objects.create(**data)


def _user(name, *, premium=False, **extra):
    user = User.objects.create_user(username=name, password='x', **extra)
    if premium:
        from accounts.models import Subscription
        Subscription.objects.create(user=user, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
    return user


def _scored_attempt(user, test, picks):
    """A completed attempt with one response per (question, letter)."""
    attempt = TestAttempt.objects.create(user=user, test=test, is_completed=True, completed_at=timezone.now())
    for question, letter in picks:
        QuestionResponse.objects.create(attempt=attempt, question=question, selected_answer=letter,
                                        is_correct=letter == question.correct_answer)
    return attempt


def _option_fields(options):
    return {f'option_{letter.lower()}': text for letter, text in options.items()}


class _ApiCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)
        return user

    def review(self, test, attempt_id):
        r = self.client.get(f'/api/tests/{test.id}/review/', {'attempt_id': attempt_id})
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r

    def attempt_details(self, attempt_id):
        r = self.client.get(f'/api/tests/attempts/{attempt_id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return {resp['question']: resp['question_detail'] for resp in r.data['responses']}

    def start(self, test):
        r = self.client.post(f'/api/tests/{test.id}/start/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r

    def submit(self, test, attempt_id, letter='B'):
        return self.client.post(
            f'/api/tests/{test.id}/submit/',
            {'attempt_id': attempt_id,
             'answers': [{'question_id': qid, 'selected_answer': letter}
                         for qid in test.questions.values_list('id', flat=True)]},
            format='json',
        )


class LockedRowPublicTextTests(_ApiCase):
    """Answer labels and correctness flags in the stem / options of locked
    review, attempt-detail and test-detail rows."""

    def setUp(self):
        super().setUp()
        subject = Subject.objects.create(name='Wave4 Locked Text', code='W4TEXT')
        # The key glued into the stem by an import ("Ans: B. ...").
        self.stem_key = _q(subject, question_text=STEM_WITH_KEY, **TEXTBOOK)
        # Options flagged "(correct)" / "(wrong)", one with a key label.
        self.flagged = _q(subject, options=FLAGGED_OPTIONS, **TEXTBOOK)
        # Real-data shapes: a tick plus its reason on an option, and a tick
        # on an option the stem lists.
        self.ticked = _q(subject, options=TICKED_OPTIONS, **TEXTBOOK)
        self.listing = _q(subject, question_text=STEM_LISTING, **TEXTBOOK)
        # The same leaks on a free showcase question: its answer is free.
        self.showcase = _q(subject, question_text=STEM_WITH_KEY, options=FLAGGED_OPTIONS, **TEXTBOOK)
        FreeShowcaseQuestion.objects.create(question=self.showcase, year=2024, position=0)
        # A scholarship-challenge question is never free, showcased or not.
        self.scholarship = _q(subject, question_text=STEM_WITH_KEY, options=FLAGGED_OPTIONS,
                              is_scholarship_eligible=True, **TEXTBOOK)
        FreeShowcaseQuestion.objects.create(question=self.scholarship, year=2024, position=1)
        self.locked = (self.stem_key, self.flagged, self.ticked, self.listing, self.scholarship)
        self.locked_stem = {question.id: STEM for question in self.locked}
        self.locked_stem[self.listing.id] = STEM_LISTING_LOCKED
        # Published and created by no one: in every student's library.
        self.test = Test.objects.create(title='Wave4 locked text', test_type='mixed', negative_marking=False)
        self.test.questions.set([*self.locked, self.showcase])
        self.picks = [(self.stem_key, 'B'), (self.flagged, 'A'), (self.ticked, 'B'), (self.listing, 'C'),
                      (self.scholarship, 'B'), (self.showcase, 'B')]

    def assert_nothing_leaks(self, row):
        payload = str(row)
        for leak in ('Ans:', 'Correct Answer', '(correct)', '(wrong)', '✔', '✅', 'secret',
                     'drug of choice', 'adrenaline for anaphylaxis', 'Harrison', '2710'):
            self.assertNotIn(leak, payload)

    def test_free_review_rows_lose_answer_labels_and_flags(self):
        user = self.login(_user('w4-text-free'))
        attempt = _scored_attempt(user, self.test, self.picks)
        response = self.review(self.test, attempt.id)
        rows = {row['question_id']: row for row in response.data['questions']}

        for question in self.locked:
            row = rows[question.id]
            self.assertEqual(row['question_text'], self.locked_stem[question.id])
            self.assertEqual(row['options'], OPTIONS)
            self.assertTrue(row['answer_locked'])
            self.assertIsNone(row['correct_answer'])
            self.assertEqual(row['concept_tags'], ['high_yield'])
            self.assertEqual((row['book_reference'], row['chapter'], row['page_number']), ('', '', ''))
            self.assert_nothing_leaks(row)
        # The student's own pick and its result stay (wave-2 contract).
        self.assertEqual((rows[self.flagged.id]['selected_answer'], rows[self.flagged.id]['is_correct']),
                         ('A', False))
        # The free showcase question is shown as stored.
        showcase = rows[self.showcase.id]
        self.assertFalse(showcase['answer_locked'])
        self.assertEqual(showcase['question_text'], STEM_WITH_KEY)
        self.assertEqual(showcase['options'], FLAGGED_OPTIONS)
        self.assertEqual(showcase['concept_tags'], TEXTBOOK['concept_tags'])
        self.assertEqual((showcase['book_reference'], showcase['chapter'], showcase['page_number']),
                         ('Harrison', TEXTBOOK['chapter'], '2710'))

    def test_free_attempt_detail_rows_lose_answer_labels_and_flags(self):
        user = self.login(_user('w4-detail-free'))
        attempt = _scored_attempt(user, self.test, self.picks)
        details = self.attempt_details(attempt.id)

        expected = _option_fields(OPTIONS)
        for question in self.locked:
            detail = details[question.id]
            self.assertTrue(detail['answer_locked'])
            self.assertEqual(detail['question_text'], self.locked_stem[question.id])
            self.assertEqual({name: detail[name] for name in expected}, expected)
            self.assert_nothing_leaks(detail)
        showcase = details[self.showcase.id]
        self.assertFalse(showcase['answer_locked'])
        self.assertEqual(showcase['question_text'], STEM_WITH_KEY)
        self.assertEqual(showcase['option_b'], FLAGGED_OPTIONS['B'])

    def test_free_test_detail_rows_lose_answer_labels_and_flags(self):
        """GET /api/tests/<id>/ is open to free students for library tests
        (QuestionListSerializer cuts the same text)."""
        self.login(_user('w4-retrieve-free'))
        r = self.client.get(f'/api/tests/{self.test.id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        rows = {row['id']: row for row in r.data['questions']}
        expected = _option_fields(OPTIONS)
        for question in self.locked:
            row = rows[question.id]
            self.assertEqual(row['question_text'], self.locked_stem[question.id])
            self.assertEqual({name: row[name] for name in expected}, expected)
        showcase = rows[self.showcase.id]
        self.assertEqual(showcase['question_text'], STEM_WITH_KEY)
        self.assertEqual(showcase['option_b'], FLAGGED_OPTIONS['B'])

        self.login(_user('w4-retrieve-premium', premium=True))
        rows = {row['id']: row for row in self.client.get(f'/api/tests/{self.test.id}/').data['questions']}
        self.assertEqual(rows[self.ticked.id]['option_b'], TICKED_OPTIONS['B'])
        self.assertEqual(rows[self.listing.id]['question_text'], STEM_LISTING)

    def test_premium_and_staff_rows_are_shown_as_stored(self):
        staff = _user('w4-text-staff', is_staff=True)
        for user in (_user('w4-text-premium', premium=True), _user('w4-text-admin', role='admin'), staff):
            self.login(user)
            attempt = _scored_attempt(user, self.test, self.picks)
            rows = {row['question_id']: row for row in self.review(self.test, attempt.id).data['questions']}
            self.assertEqual(rows[self.stem_key.id]['question_text'], STEM_WITH_KEY, user.username)
            self.assertEqual(rows[self.flagged.id]['options'], FLAGGED_OPTIONS, user.username)
            self.assertEqual(rows[self.ticked.id]['options'], TICKED_OPTIONS, user.username)
            self.assertEqual(rows[self.listing.id]['question_text'], STEM_LISTING, user.username)
            self.assertEqual(rows[self.flagged.id]['concept_tags'], TEXTBOOK['concept_tags'], user.username)
            self.assertEqual(rows[self.flagged.id]['chapter'], TEXTBOOK['chapter'], user.username)
            self.assertFalse(any(row['answer_locked'] for row in rows.values()), user.username)
            details = self.attempt_details(attempt.id)
            self.assertEqual(details[self.stem_key.id]['question_text'], STEM_WITH_KEY, user.username)
            self.assertEqual(details[self.flagged.id]['option_b'], FLAGGED_OPTIONS['B'], user.username)
            self.assertEqual(details[self.ticked.id]['option_b'], TICKED_OPTIONS['B'], user.username)


class LockAnswerUnitTests(SimpleTestCase):
    """entitlement.lock_answer on both row shapes."""

    def test_review_row_shape(self):
        row = {
            'question_id': 1, 'question_text': STEM_WITH_KEY, 'options': dict(FLAGGED_OPTIONS),
            'correct_answer': 'B', 'selected_answer': 'B', 'is_correct': True,
            'explanation': SECRET_EXPLANATION, 'mnemonic': 'm', 'concept_explanation': 'c',
            'textbook_references': [{'book': 'Harrison'}], 'concept_tags': list(TEXTBOOK['concept_tags']),
            'book_reference': 'Harrison', 'chapter': 'Anaphylaxis', 'page_number': '2710',
            'answer_locked': False,
        }
        lock_answer(row)
        self.assertEqual(row['question_text'], STEM)
        self.assertEqual(row['options'], OPTIONS)
        self.assertEqual(
            {key: row[key] for key in ('correct_answer', 'explanation', 'mnemonic', 'concept_explanation',
                                       'textbook_references', 'concept_tags', 'book_reference', 'chapter',
                                       'page_number', 'answer_locked')},
            {'correct_answer': None, 'explanation': '', 'mnemonic': '', 'concept_explanation': '',
             'textbook_references': [], 'concept_tags': ['high_yield'], 'book_reference': '', 'chapter': '',
             'page_number': '', 'answer_locked': True},
        )
        self.assertEqual((row['selected_answer'], row['is_correct']), ('B', True))

    def test_attempt_detail_row_shape(self):
        row = {'id': 1, 'question_text': f'{STEM} Ans: B', 'correct_answer': 'B', 'answer_locked': False,
               **_option_fields(FLAGGED_OPTIONS)}
        lock_answer(row)
        self.assertEqual(row['question_text'], STEM)
        self.assertEqual([row[f'option_{letter}'] for letter in 'abcd'], list(OPTIONS.values()))
        # Keys the row does not carry are not added.
        self.assertFalse({'concept_tags', 'book_reference', 'chapter', 'page_number', 'options'} & set(row))

    def test_correctness_flags(self):
        flagged = {
            'Adrenaline (Correct)': 'Adrenaline',
            'Adrenaline [correct]': 'Adrenaline',
            '(correct) Adrenaline': 'Adrenaline',
            'Adrenaline (correct answer)': 'Adrenaline',
            'Adrenaline (Correct Ans.)': 'Adrenaline',
            'Adrenaline (right answer)': 'Adrenaline',
            'Atropine (Incorrect)': 'Atropine',
            'Atropine [wrong answer]': 'Atropine',
            'Adrenaline ✓': 'Adrenaline',
            'Atropine ✗': 'Atropine',
            # A flag ends the option: what follows it is the reason for it,
            # printed on the flagged option only (rows 24224 / 24226).
            'Adrenaline (correct) 0.5 mg IM': 'Adrenaline',
            'Conjunctival xerosis ✔ (Conjunctival xerosis is the first clinical sign)':
                'Conjunctival xerosis',
            'Phrenoderma ✔ (Concept tested: EFA deficiency → phrenoderma)': 'Phrenoderma',
            # No empty brackets and no emoji variation selector left behind.
            'Adrenaline (✓)': 'Adrenaline',
            'Adrenaline ✔️': 'Adrenaline',
        }
        not_flags = [
            'Statement I is incorrect but Statement II is correct',
            'Both A and R are true and R is the correct explanation of A',
            'Hepatic flexure (right)',
            'Tube (correctly placed)',
            '10 × 10^9/L',
            'Correct',
            # "ANS" is the autonomic nervous system.
            'Autonomic nervous system (ANS)',
            'Autonomic nervous system [ANS]',
        ]
        for text, expected in [*flagged.items(), *((text, text) for text in not_flags)]:
            row = {'option_a': text, 'options': {'A': text}}
            lock_answer(row)
            self.assertEqual((row['option_a'], row['options']['A']), (expected, expected), text)

    def test_stem_listing_the_options(self):
        """A tick on an option the stem lists goes too (also after the
        label cut), on both row shapes."""
        for row in ({'question_text': STEM_LISTING, 'options': {'B': 'Adrenaline ✅'}},
                    {'question_text': f'{STEM_LISTING}\nAns: B', 'option_b': 'Adrenaline ✅'}):
            lock_answer(row)
            self.assertEqual(row['question_text'], STEM_LISTING_LOCKED)
            self.assertEqual(row.get('option_b', row.get('options', {}).get('B')), 'Adrenaline')

    def test_missing_and_non_string_values(self):
        row = {'question_text': None, 'option_a': None, 'option_b': '', 'options': {'A': None, 'B': ''},
               'concept_tags': None}
        lock_answer(row)
        self.assertEqual((row['question_text'], row['option_a'], row['option_b']), (None, None, ''))
        self.assertEqual(row['options'], {'A': None, 'B': ''})
        self.assertEqual(row['concept_tags'], [])
        self.assertTrue(row['answer_locked'])


class ScoringGateTests(_ApiCase):
    """Why a locked review row may keep the student's own pick and right /
    wrong: no new attempt can be scored on a question the student may not
    see. /submit/ re-checks the test's questions, so a question that left
    the free set after /start/, or a plan that lapsed in between, is a 402
    and nothing is scored."""

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Wave4 Gate', code='W4GATE')
        self.free = [_q(self.subject, question_text=f'{STEM} (free {i})') for i in range(2)]
        for position, question in enumerate(self.free):
            FreeShowcaseQuestion.objects.create(question=question, year=2024, position=position)
        self.test = Test.objects.create(title='Wave4 gate', test_type='mixed', negative_marking=False)
        self.test.questions.set(self.free)

    def assert_not_scored(self, user, change):
        self.login(user)
        attempt_id = self.start(self.test).data['attempt_id']
        change()
        r = self.submit(self.test, attempt_id)
        self.assertEqual(r.status_code, 402, getattr(r, 'data', None))
        self.assertEqual(r.data['code'], 'upgrade_required')
        self.assertFalse(TestAttempt.objects.get(pk=attempt_id).is_completed)
        self.assertFalse(QuestionResponse.objects.filter(attempt_id=attempt_id).exists())

    def test_question_leaving_the_showcase_after_start(self):
        self.assert_not_scored(_user('w4-gate-unlisted'),
                               lambda: FreeShowcaseQuestion.objects.filter(question=self.free[1]).delete())

    def test_question_becoming_a_scholarship_question_after_start(self):
        self.assert_not_scored(_user('w4-gate-scholarship'),
                               lambda: Question.objects.filter(pk=self.free[1].pk)
                               .update(is_scholarship_eligible=True))

    def test_plan_lapsing_after_start(self):
        from accounts.models import Subscription

        self.test.questions.add(_q(self.subject, question_text=f'{STEM} (bank)'))
        user = _user('w4-gate-lapsed', premium=True)
        self.assert_not_scored(user, lambda: Subscription.objects.filter(user=user).update(
            status='expired', expires_at=timezone.now() - timedelta(days=1)))

    def test_free_questions_are_still_scored(self):
        self.login(_user('w4-gate-free'))
        attempt_id = self.start(self.test).data['attempt_id']
        r = self.submit(self.test, attempt_id)
        self.assertEqual((r.status_code, r.data['correct_count']), (200, 2))


class LoaderSubjectDisplayTests(_ApiCase):
    """The loader's "Imported" subject is "Expert Curated" in test payloads."""

    def setUp(self):
        super().setUp()
        self.imported = Subject.objects.create(name='Imported', code='W4IMP')
        self.questions = [_q(self.imported, question_text=f'{STEM} ({i})') for i in range(3)]
        self.user = self.login(_user('w4-display-premium', premium=True))

    def assert_shown_as_expert_curated(self, subject):
        questions = list(subject.questions.all())
        test = Test.objects.create(title='Wave4 display', test_type='mixed', negative_marking=False,
                                   subject=subject)
        test.questions.set(questions)
        attempt = _scored_attempt(self.user, test, [(q, 'B') for q in questions])
        response = self.review(test, attempt.id)
        self.assertEqual({row['subject'] for row in response.data['questions']}, {'Expert Curated'})
        self.assertEqual(response.data['subject_breakdown'],
                         {'Expert Curated': {'correct': len(questions), 'incorrect': 0, 'unanswered': 0}})
        self.assertNotIn(subject.name, str(response.data))

        started = self.start(test)
        self.assertEqual(started.data['test']['subject_name'], 'Expert Curated')
        details = self.attempt_details(attempt.id)
        self.assertEqual({detail['subject_name'] for detail in details.values()}, {'Expert Curated'})

    def test_review_rows_and_breakdown(self):
        self.assert_shown_as_expert_curated(self.imported)

    def test_name_case_and_spacing(self):
        """Matched like questions.serializers.public_subject_name (strip +
        case), not only the exact literal."""
        loose = Subject.objects.create(name='imported ', code='W4IMP2')
        for i in range(2):
            _q(loose, question_text=f'{STEM} (loose {i})')
        self.assert_shown_as_expert_curated(loose)
        r = self.client.post('/api/tests/generate/', {'test_type': 'subject', 'subject_id': loose.id},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['subject_name'], r.data['title']),
                         ('Expert Curated', 'Expert Curated — 2 Questions'))

    def test_generated_subject_test(self):
        r = self.client.post('/api/tests/generate/', {'test_type': 'subject', 'subject_id': self.imported.id},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['subject_name'], 'Expert Curated')
        self.assertEqual(r.data['title'], SHOWN_TITLE)
        self.assertNotIn('Imported', str(r.data))
        listed = self.client.get(f'/api/tests/{r.data["id"]}/')
        self.assertEqual(listed.status_code, 200, getattr(listed, 'data', None))
        self.assertEqual(listed.data['title'], SHOWN_TITLE)

    def test_stored_titles(self):
        """Subject tests generated on the loader bucket before wave 4 keep
        the stored title "Imported — N Questions" (the restored bank has
        four, two of them in the official library); every payload shows
        "Expert Curated — N Questions"."""
        stored = 'Imported — 3 Questions'
        admin = _user('w4-title-admin', role='admin')
        library = Test.objects.create(title=stored, test_type='subject', subject=self.imported,
                                      created_by=admin, negative_marking=False)
        mine = Test.objects.create(title=stored, test_type='subject', subject=self.imported,
                                   created_by=self.user, is_published=False, negative_marking=False)
        for test in (library, mine):
            test.questions.set(self.questions)

        payloads = []
        titles = {}
        for scope in ('library', 'mine'):
            r = self.client.get('/api/tests/', {'scope': scope})
            self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
            titles.update({row['id']: row['title'] for row in r.data['results']})
            payloads.append(r.data)
        self.assertEqual((titles[library.id], titles[mine.id]), (SHOWN_TITLE, SHOWN_TITLE))
        detail = self.client.get(f'/api/tests/{library.id}/')
        self.assertEqual(detail.data['title'], SHOWN_TITLE)
        started = self.start(mine)
        self.assertEqual(started.data['test']['title'], SHOWN_TITLE)
        submitted = self.submit(mine, started.data['attempt_id'])
        self.assertEqual(submitted.status_code, 200, getattr(submitted, 'data', None))
        self.assertEqual(submitted.data['test_title'], SHOWN_TITLE)
        attempts = self.client.get('/api/tests/attempts/')
        self.assertEqual({row['test_title'] for row in attempts.data['results']}, {SHOWN_TITLE})
        attempt = self.client.get(f'/api/tests/attempts/{started.data["attempt_id"]}/')
        self.assertEqual(attempt.data['test_title'], SHOWN_TITLE)
        payloads += [detail.data, started.data, submitted.data, attempts.data, attempt.data]
        for payload in payloads:
            self.assertNotIn('Imported', str(payload))
        # Only the output changes: the stored title is as saved.
        self.assertEqual(Test.objects.get(pk=library.pk).title, stored)

    def test_other_subjects_keep_their_name(self):
        real = Subject.objects.create(name='Imported Diseases', code='W4REAL')
        test = Test.objects.create(title='Imported Diseases — 1 Questions', test_type='subject',
                                   subject=real)
        test.questions.set([_q(real)])
        started = self.start(test)
        self.assertEqual(started.data['test']['subject_name'], 'Imported Diseases')
        self.assertEqual(started.data['test']['title'], 'Imported Diseases — 1 Questions')


class PublicTestTitleTests(SimpleTestCase):
    def test_loader_bucket_parts_are_renamed(self):
        renamed = {
            'Imported — 20 Questions': 'Expert Curated — 20 Questions',
            'imported — 20 Questions': 'Expert Curated — 20 Questions',
            ' Imported  — 20 Questions': 'Expert Curated — 20 Questions',
            'Imported | PYQ 2020 — 20 Questions': 'Expert Curated | PYQ 2020 — 20 Questions',
            'PYQ 2020 | Imported — 20 Questions': 'PYQ 2020 | Expert Curated — 20 Questions',
            'Imported': 'Expert Curated',
        }
        for title, expected in renamed.items():
            self.assertEqual(public_test_title(title), expected, title)

    def test_other_titles_are_unchanged(self):
        for title in ('Imported Diseases — 20 Questions', 'Mixed Practice — 20 Questions',
                      'Re-imported cases — 5 Questions', 'AI Adaptive Test — 30 Questions', '', None):
            self.assertEqual(public_test_title(title), title, title)


class SubmitRefreshesDashboardTests(_ApiCase):
    """A submit drops the student's dashboard_v3 caches (60 s), as an answer
    in the question bank does; other students' caches stay."""

    def test_submit_drops_the_dashboard_v3_cache(self):
        from analytics import dashboard_v3

        subject = Subject.objects.create(name='Wave4 Dashboard', code='W4DASH')
        test = Test.objects.create(title='Wave4 dashboard', test_type='mixed', negative_marking=False)
        test.questions.set([_q(subject)])
        user = self.login(_user('w4-dash-premium', premium=True))
        other = _user('w4-dash-other')
        keys = {who.id: [dashboard_v3._cache_key(who.id, name) for name in dashboard_v3.CACHED_RESULTS]
                for who in (user, other)}
        for user_keys in keys.values():
            cache.set_many({key: {'stale': True} for key in user_keys}, 300)

        r = self.submit(test, self.start(test).data['attempt_id'])
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        self.assertEqual(cache.get_many(keys[user.id]), {})
        self.assertEqual(len(cache.get_many(keys[other.id])), len(keys[other.id]))
        cache.delete_many(keys[other.id])
