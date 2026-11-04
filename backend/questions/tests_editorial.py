"""Tests for the question-editor workflows and endpoints (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md: a key changes only through ``change_answer_key`` (source
'editor', evidence cleaned like the review queue's); explain-option is evidence first (a conflict is
never justified, weak evidence abstains, no reference store degrades to insufficient evidence) and its
text only quotes stored passages; explanations are saved for the current key with provenance. The
reference store is mocked: no test reads a local corpus.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from questions.content_hashes import stem_hash
from questions.editorial import (
    change_answer_key,
    compute_explanation_status,
    save_explanation,
    unverify_question,
    verify_question,
)
from questions.explain_option import QUOTE_MAX_CHARS, explain_selected_option
from questions.models import AnswerKeyChange, ExplanationSuggestion, Question, Subject

User = get_user_model()

DECIDE = 'questions.explain_option.ref_api.decide'
TITLE = "Harrison's Principles of Internal Medicine"
LONG_PASSAGE = ('Acute myocardial infarction typically presents with crushing retrosternal chest pain radiating '
                'to the left arm, with ST elevation on the electrocardiogram and a rise in troponin. ') * 3


def _cites(letter, n=2, page=1450):
    return [{'chunk_key': f'0123456789ab:p{page + i}:c{i}{letter}', 'source_title': TITLE, 'page': page + i,
             'tier': 3, 'snippet': LONG_PASSAGE[:240]} for i in range(n)]


def decision(status_, answer='', *, citations=None, per_option=None, margin=0.9, mode='bm25_fts5'):
    per_option = per_option or {letter: {'support': 0.0, 'contradiction': 0.0, 'citations': []} for letter in 'ABCD'}
    return {'status': status_, 'evidence_answer': answer, 'stored_key': 'A', 'selected_key': '', 'confidence': 0.7,
            'margin': margin, 'polarity': 'neutral', 'question_type': 'standard', 'per_option': per_option,
            'citations': citations or [], 'retrieval_mode': mode, 'store_build_id': 'test', 'config_hash': 'x'}


class _Fixture(TestCase):
    def setUp(self):
        cache.clear()   # DRF throttle history (admin_explain) is kept in the cache between tests
        self.subject = Subject.objects.create(name="Internal Medicine", code="MED")
        self.admin = User.objects.create_superuser(
            username="admin_editor", email="admin@cracklabs.test", password="testpassword123")
        self.role_admin = User.objects.create_user(
            username="role_admin", email="role_admin@cracklabs.test", password="testpassword123", role='admin')
        self.staff_only = User.objects.create_user(
            username="staff_only", email="staff@cracklabs.test", password="testpassword123", is_staff=True)
        self.student = User.objects.create_user(
            username="student_user", email="student@cracklabs.test", password="testpassword123")
        self.question = self.make()
        self.client = APIClient()

    def make(self, key='A', text="A 45-year-old male presents with acute chest pain.", **extra):
        return Question.objects.create(
            question_text=text, option_a="Aortic dissection", option_b="Acute myocardial infarction",
            option_c="Pneumothorax", option_d="Pulmonary embolism", correct_answer=key, subject=self.subject,
            year=2024, explanation=extra.pop('explanation', "Initial explanation for option A."), **extra)

    def url(self, name, question=None):
        return f"/api/questions/{(question or self.question).pk}/{name}/"

    @staticmethod
    def source_key(question, letter, source_file='book.pdf', page=3, content_hash=None):
        from datetime import timedelta

        from django.utils import timezone

        from key_audit.models import SourceKey
        return SourceKey.objects.create(
            question=question, source_file=source_file, question_page=page, question_number=1,
            printed_letter=letter, letter=letter, option_order='same', method='answer_key_table', located=True,
            stem_hash=content_hash or stem_hash(question), recovery_version='test',
            recovered_at=timezone.now() - timedelta(days=30))

    def as_admin(self, user=None):
        self.client.force_authenticate(user=user or self.admin)


class EditorialWorkflowTestCase(_Fixture):
    def test_change_answer_key_success_and_immutability(self):
        with self.captureOnCommitCallbacks(execute=True):
            change = change_answer_key(
                self.question, new_key="B", actor=self.admin,
                reason="ECG confirms STEMI; standard clinical protocol indicates AMI.", source="editor")
        self.question.refresh_from_db()
        self.assertEqual(self.question.correct_answer, "B")
        # The audit re-classifies on commit: a staff change that cites no evidence is not "verified".
        self.assertEqual(self.question.answer_key_status, "likely_correct")
        self.assertEqual((change.old_key, change.new_key, change.changed_by), ("A", "B", self.admin))
        self.assertEqual(change.explanation_action, "kept_stale")
        self.assertEqual(self.question.explanation_status, "stale")

        # Immutability check: modifying change record raises ValueError
        change.old_key = "C"
        with self.assertRaises(ValueError):
            change.save()

    def test_change_answer_key_validation(self):
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "Z", actor=self.admin, reason="Valid reason here")
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "B", actor=self.admin, reason="short")
        with self.assertRaises(ValidationError):
            change_answer_key(self.question, "A", actor=self.admin, reason="Valid reason here")

    def test_key_change_with_explanation_records_provenance_and_locks_it(self):
        change_answer_key(self.question, "B", actor=self.admin, reason="Troponin rise confirms the infarct.",
                          explanation_fields={"explanation": "ST elevation with a troponin rise: an infarct."})
        q = Question.objects.get(pk=self.question.pk)
        self.assertEqual((q.explanation_for_key, q.explanation_status, q.explanation_origin), ("B", "human_edited", "human"))
        self.assertTrue(q.lock_explanation)   # students see this text, not an older AI explanation
        self.assertTrue(q.explanation_hash)
        self.assertEqual(compute_explanation_status(q)[0], "human_edited")

    def test_explain_selected_option_without_reference_store_abstains(self):
        with mock.patch('reference_corpus.api.store_available', return_value=False):
            suggestion = explain_selected_option(self.question, selected="B", actor=self.admin)
        self.assertIsInstance(suggestion, ExplanationSuggestion)
        self.assertEqual((suggestion.for_key, suggestion.status, suggestion.model),
                         ("B", "insufficient_evidence", "none"))
        self.assertEqual(suggestion.fields, {})   # never a status message posing as an explanation
        self.assertEqual(Question.objects.get(pk=self.question.pk).explanation, "Initial explanation for option A.")

    def test_compute_explanation_status(self):
        q = self.question
        self.assertEqual(compute_explanation_status(q)[0], "pending_review")   # text without provenance
        q.explanation = "  "
        self.assertEqual(compute_explanation_status(q)[0], "absent")
        q.explanation, q.explanation_status, q.explanation_for_key = "x", "human_edited", "B"
        self.assertEqual(compute_explanation_status(q)[0], "conflict")
        q.explanation_for_key, q.explanation_stem_hash = "A", "0" * 64
        self.assertEqual(compute_explanation_status(q)[0], "stale")
        q.explanation_stem_hash = stem_hash(q)
        self.assertEqual(compute_explanation_status(q), ("human_edited", ""))

    def test_save_explanation_never_overwrites_a_concurrent_key_change(self):
        stale_instance = Question.objects.get(pk=self.question.pk)
        change_answer_key(Question.objects.get(pk=self.question.pk), "B", actor=self.admin,
                          reason="Changed meanwhile by another admin.")
        save_explanation(stale_instance, {"explanation": "Text saved from an older copy."}, actor=self.admin)
        q = Question.objects.get(pk=self.question.pk)
        self.assertEqual(q.correct_answer, "B")
        self.assertEqual(q.explanation, "Text saved from an older copy.")

    def test_verify_refuses_a_key_that_is_not_a_letter(self):
        q = self.make(key='')
        with self.assertRaises(ValidationError):
            verify_question(q, actor=self.admin)

    def test_unverify_removes_the_student_badge(self):
        Question.objects.filter(pk=self.question.pk).update(is_verified_by_admin=True, verified_hash='h')
        q = Question.objects.get(pk=self.question.pk)
        verify_question(q, actor=self.admin)
        status_after = unverify_question(q, actor=self.admin, reason="The option text looks garbled now.")
        q.refresh_from_db()
        self.assertEqual(status_after, "needs_review")
        self.assertFalse(q.is_verified_by_admin)
        self.assertEqual((q.verified_by, q.verified_at, q.verified_hash), (None, None, ''))
        self.assertTrue(q.needs_review)


class EditorialPermissionsTestCase(_Fixture):
    """Every editor endpoint: admin role or superuser only (the editor page's rule)."""

    def calls(self):
        return [
            ('get', self.url('provenance'), None),
            ('get', self.url('key-history'), None),
            ('post', self.url('change-key'), {'new_key': 'B', 'reason': 'Reason with more than ten characters'}),
            ('post', self.url('explain-option'), {'selected': 'B'}),
            ('post', self.url('save-explanation'), {'fields': {'explanation': 'Option A: aortic dissection.'},
                                                    'for_key': 'A'}),
            ('post', self.url('verify-key'), {'action': 'verify'}),
            ('post', self.url('review-explanation'), None),
        ]

    def request(self, method, url, body):
        return getattr(self.client, method)(url, body, format='json') if body is not None else getattr(
            self.client, method)(url)

    def test_anonymous_students_and_staff_only_accounts_are_refused(self):
        with mock.patch(DECIDE, return_value=decision('insufficient_evidence')):
            for user, allowed in ((None, ()), (self.student, ()), (self.staff_only, ())):
                self.client.force_authenticate(user=user)
                for method, url, body in self.calls():
                    with self.subTest(user=getattr(user, 'username', 'anonymous'), url=url):
                        res = self.request(method, url, body)
                        expected = (403,) if user else (401, 403)
                        self.assertIn(res.status_code, expected)
        self.question.refresh_from_db()
        self.assertEqual(self.question.correct_answer, 'A')
        self.assertFalse(AnswerKeyChange.objects.exists())

    def test_admin_role_and_superuser_are_allowed(self):
        with mock.patch(DECIDE, return_value=decision('insufficient_evidence')):
            for user in (self.role_admin, self.admin):
                self.client.force_authenticate(user=user)
                for method, url, body in self.calls():
                    with self.subTest(user=user.username, url=url):
                        res = self.request(method, url, body)
                        self.assertNotIn(res.status_code, (401, 403), res.data)
                        self.assertLess(res.status_code, 500)

    def test_explain_option_has_its_own_throttle_scope(self):
        from django.conf import settings
        from rest_framework.throttling import SimpleRateThrottle

        from questions.views_editorial import ExplainOptionView
        self.assertEqual(ExplainOptionView.throttle_scope, 'admin_explain')
        self.assertIn('admin_explain', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        self.as_admin()
        with mock.patch(DECIDE, return_value=decision('insufficient_evidence')), \
                mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'admin_explain': '2/min'}):
            codes = [self.client.post(self.url('explain-option'), {'selected': 'B'}, format='json').status_code
                     for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


class ChangeKeyEndpointTests(_Fixture):
    def post(self, body, question=None):
        self.as_admin()
        return self.client.post(self.url('change-key', question), body, format='json')

    def test_change_without_strong_evidence_is_likely_correct(self):
        res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.', 'expected_key': 'A'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['old_key'], res.data['new_key']), ('A', 'B'))
        self.assertEqual(res.data['answer_key_status'], 'likely_correct')
        self.assertFalse(res.data['strong_evidence'])
        self.assertEqual(res.data['explanation']['status'], 'stale')   # the old explanation was for A
        q = Question.objects.get(pk=self.question.pk)
        self.assertEqual((q.correct_answer, q.answer_key_status), ('B', 'likely_correct'))
        self.assertTrue(res.data['updated_at'])

    def test_change_citing_a_page_cited_passage_is_verified(self):
        evidence = [{'kind': 'passage', 'source_title': TITLE, 'edition': '21st', 'page_label': '1450',
                     'quote': 'ST elevation with a troponin rise defines an acute myocardial infarction.',
                     'unknown_field': 'dropped'}]
        res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.', 'evidence': evidence,
                         'expected_key': 'A'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data['strong_evidence'])
        self.assertEqual(res.data['answer_key_status'], 'verified')
        stored = AnswerKeyChange.objects.get(question=self.question).evidence
        self.assertNotIn('unknown_field', stored[0])   # cleaned like the review queue's evidence

    def test_incomplete_or_unknown_evidence_is_refused(self):
        for item in ({'kind': 'official_key'}, {'kind': 'passage', 'source_title': 'Book', 'page_label': '3',
                                                 'quote': 'short'},
                     {'kind': 'oracle', 'text': 'trust me'}, {'kind': 'guideline_url', 'source_title': 'WHO',
                                                              'url': 'javascript:alert(1)'}):
            with self.subTest(item=item):
                res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.', 'evidence': [item]})
                self.assertEqual(res.status_code, 400)
        self.assertEqual(Question.objects.get(pk=self.question.pk).correct_answer, 'A')

    def test_source_key_of_another_question_is_refused(self):
        other = self.make(text='Another question about chest pain and its causes?')
        row = self.source_key(other, 'B')
        res = self.post({'new_key': 'B', 'reason': 'Printed key of the source.', 'evidence': [
            {'kind': 'source_key', 'source_key_id': row.pk}]})
        self.assertEqual(res.status_code, 400)
        self.assertIn('evidence', res.data)

    def test_client_cannot_choose_the_source(self):
        res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.', 'source': 'management_command'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(AnswerKeyChange.objects.get(question=self.question).source, 'editor')
        # ... so the audit counts it as an admin decision.
        self.assertEqual(res.data['answer_key_status'], 'likely_correct')

    def test_stale_expected_key_is_a_conflict(self):
        res = self.post({'new_key': 'C', 'reason': 'Troponin rise and ST elevation.', 'expected_key': 'B'})
        self.assertEqual(res.status_code, 409)
        self.assertEqual((res.data['code'], res.data['current_key']), ('key_changed', 'A'))
        res = self.post({'new_key': 'C', 'reason': 'Troponin rise and ST elevation.', 'expected_key': ''})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(Question.objects.get(pk=self.question.pk).correct_answer, 'A')
        self.assertFalse(AnswerKeyChange.objects.exists())

    def test_setting_a_missing_key(self):
        q = self.make(key='', text='Which drug is first line in anaphylaxis?')
        res = self.post({'new_key': 'D', 'reason': 'Adrenaline is the first-line drug.', 'expected_key': ''}, q)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(AnswerKeyChange.objects.get(question=q).old_key, '')

    def test_same_key_reads_as_a_sentence(self):
        res = self.post({'new_key': 'A', 'reason': 'Troponin rise and ST elevation.'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('already has', res.data['detail'])
        self.assertNotIn("['", res.data['detail'])

    def test_explanation_fields_are_checked(self):
        res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.',
                         'explanation_fields': {'correct_answer': 'C'}})
        self.assertEqual(res.status_code, 400)
        res = self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.',
                         'explanation_fields': {'explanation': 'ST elevation and troponin: an infarct.'}})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['explanation']['status'], 'human_edited')
        self.assertEqual(res.data['explanation']['for_key'], 'B')

    def test_change_is_in_the_admin_audit_log(self):
        from accounts.models import AdminAuditLog
        self.post({'new_key': 'B', 'reason': 'Troponin rise and ST elevation.'})
        log = AdminAuditLog.objects.get(action='answer_key_change')
        self.assertEqual((log.resource_id, log.metadata['new_key'], log.metadata['source']),
                         (str(self.question.pk), 'B', 'editor'))

    def test_key_history_lists_the_change(self):
        self.post({'new_key': 'B', 'reason': 'Verified against textbook reference.'})
        res = self.client.get(self.url('key-history'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['current_key'], 'B')
        self.assertEqual([(c['old_key'], c['new_key'], c['source'], c['changed_by_username'])
                          for c in res.data['changes']], [('A', 'B', 'editor', 'admin_editor')])


class ExplainOptionEndpointTests(_Fixture):
    def post(self, body, question=None):
        self.as_admin()
        return self.client.post(self.url('explain-option', question), body, format='json')

    def test_supported_option_quotes_the_passages(self):
        per_option = {letter: {'support': 0.0, 'contradiction': 0.0, 'citations': []} for letter in 'ACD'}
        per_option['B'] = {'support': 1.4, 'contradiction': 0.0, 'citations': _cites('B')}
        with mock.patch(DECIDE, return_value=decision('supported', 'B', citations=_cites('B'),
                                                      per_option=per_option)) as decide:
            res = self.post({'selected': 'B'})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['status'], res.data['for_key'], res.data['stored_key']), ('ok', 'B', 'A'))
        self.assertEqual(set(res.data['fields']), {'explanation'})
        text = res.data['fields']['explanation']
        self.assertIn(TITLE, text)
        self.assertIn('PDF p. 1450', text)
        for quote in [part.split('”')[0] for part in text.split('“')[1:]]:
            self.assertLessEqual(len(quote), QUOTE_MAX_CHARS)
        self.assertEqual(len(res.data['field_citations']['explanation']), 2)
        self.assertEqual(res.data['option_evidence']['B']['support'], 1.4)
        self.assertEqual(res.data['retrieval_mode'], 'bm25_fts5')
        # Evidence first: the decision is asked about the selected option with the stored key beside it.
        self.assertEqual(decide.call_args.kwargs['selected_key'], 'B')
        self.assertEqual(Question.objects.get(pk=self.question.pk).explanation, "Initial explanation for option A.")

    def test_conflict_is_never_justified(self):
        per_option = {letter: {'support': 0.1, 'contradiction': 0.0, 'citations': _cites(letter, 1)}
                      for letter in 'ABCD'}
        per_option['C']['support'] = 2.0
        returned = decision('conflict', 'C', citations=_cites('C'), per_option=per_option, margin=1.9)
        for acknowledge in (False, True):
            with self.subTest(acknowledge=acknowledge), mock.patch(DECIDE, return_value=returned):
                res = self.post({'selected': 'A', 'acknowledge_conflict': acknowledge})
                self.assertEqual(res.status_code, 200, res.data)
                self.assertEqual(res.data['status'], 'conflict')
                self.assertEqual(res.data['fields'], {})
                self.assertEqual((res.data['conflict']['evidence_supports'], res.data['conflict']['selected']),
                                 ('C', 'A'))
                keys = [c['chunk_key'] for c in res.data['citations']]
                self.assertTrue(any(k.endswith('C') for k in keys))
                self.assertEqual(any(k.endswith('A') for k in keys), acknowledge)

    def test_weak_evidence_abstains(self):
        with mock.patch(DECIDE, return_value=decision('insufficient_evidence')):
            res = self.post({'selected': 'B'})
        self.assertEqual((res.data['status'], res.data['fields']), ('insufficient_evidence', {}))
        # "supported" without a single passage is not support either.
        with mock.patch(DECIDE, return_value=decision('supported', 'B')):
            res = self.post({'selected': 'B'})
        self.assertEqual(res.data['status'], 'insufficient_evidence')

    def test_no_reference_store_says_so(self):
        with mock.patch('reference_corpus.api.store_available', return_value=False):
            res = self.post({'selected': 'B'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data['status'], res.data['retrieval_mode'], res.data['fields']),
                         ('insufficient_evidence', 'none', {}))

    def test_a_broken_store_is_a_failed_suggestion_not_a_500(self):
        with mock.patch(DECIDE, side_effect=RuntimeError('database disk image is malformed')):
            res = self.post({'selected': 'B'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data['status'], res.data['fields']), ('failed', {}))

    def test_missing_figure_is_not_explained(self):
        q = self.make(text='Identify the lesion shown in the image below.', is_image_based=True)
        with mock.patch(DECIDE) as decide:
            res = self.post({'selected': 'B'}, q)
        self.assertEqual((res.data['status'], res.data['fields']), ('image_context_missing', {}))
        self.assertTrue(res.data['image_context']['required'])
        decide.assert_not_called()

    def test_draft_values_are_what_gets_checked(self):
        draft = {'question_text': 'Crushing chest pain with ST elevation: diagnosis?', 'option_b': 'STEMI',
                 'correct_answer': 'D', 'lock_answer': True}
        with mock.patch(DECIDE, return_value=decision('insufficient_evidence')) as decide:
            res = self.post({'selected': 'B', 'draft': draft})
        self.assertEqual(res.status_code, 200, res.data)
        checked = decide.call_args.args[0]
        self.assertEqual((checked.question_text, checked.option_b), (draft['question_text'], 'STEMI'))
        self.assertEqual(decide.call_args.kwargs['stored_key'], 'A')   # not the client's correct_answer
        self.assertTrue(res.data['used_draft'])
        expected = stem_hash({**{f: getattr(self.question, f) for f in
                                 ('question_text', 'option_a', 'option_b', 'option_c', 'option_d')},
                              'question_text': draft['question_text'], 'option_b': 'STEMI'})
        self.assertEqual(res.data['draft_stem_hash'], expected)

    def test_invalid_requests(self):
        for body in ({'selected': 'E'}, {'selected': 'b c'}, {'selected': 'B', 'draft': {'is_image_based': 'yes'}},
                     {'selected': 'B', 'draft': {'question_type': 'riddle'}}):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, 400)
        self.assertFalse(ExplanationSuggestion.objects.exists())


class SaveExplanationEndpointTests(_Fixture):
    def post(self, body, question=None, user=None):
        self.as_admin(user)
        return self.client.post(self.url('save-explanation', question), body, format='json')

    def suggestion(self, **overrides):
        values = {'question': self.question, 'for_key': 'A', 'stored_key': 'A', 'mode': 'extractive', 'status': 'ok',
                  'fields': {'explanation': 'Option A: reference passages'}, 'draft_stem_hash': stem_hash(self.question)}
        values.update(overrides)
        return ExplanationSuggestion.objects.create(**values)

    def test_saves_for_the_current_key_with_provenance(self):
        res = self.post({'fields': {'explanation': 'Tearing pain radiating to the back: aortic dissection.'},
                         'for_key': 'A'}, user=self.role_admin)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['explanation_status'], 'human_edited')
        q = Question.objects.get(pk=self.question.pk)
        self.assertEqual(q.explanation, 'Tearing pain radiating to the back: aortic dissection.')
        self.assertEqual((q.explanation_for_key, q.explanation_origin), ('A', 'human'))
        self.assertEqual(q.explanation_stem_hash, stem_hash(q))
        self.assertTrue(q.lock_explanation)
        self.assertEqual(q.explanation_reviewed_by, self.role_admin)   # an admin role is a reviewer too
        self.assertEqual(str(q.updated_at), str(res.data['updated_at']))

    def test_explanation_for_another_key_is_refused(self):
        res = self.post({'fields': {'explanation': 'An infarct explains the pain.'}, 'for_key': 'B'})
        self.assertEqual(res.status_code, 409)
        self.assertEqual((res.data['code'], res.data['current_key']), ('key_changed', 'A'))
        self.assertEqual(Question.objects.get(pk=self.question.pk).explanation, "Initial explanation for option A.")

    def test_question_without_a_key(self):
        q = self.make(key='', text='Which drug is first line in anaphylaxis?')
        res = self.post({'fields': {'explanation': 'Adrenaline intramuscularly.'}}, q)
        self.assertEqual((res.status_code, res.data['code']), (400, 'no_key'))

    def test_bad_fields(self):
        for body in ({'fields': {}}, {'fields': {'correct_answer': 'B'}}, {'fields': {'why_correct': 'x'}},
                     {'fields': {'explanation': 'x'}, 'accepted_fields': ['explanation']},
                     {'fields': {'explanation': 'x'}, 'suggestion_id': '00000000-0000-0000-0000-000000000000'}):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, 400)

    def test_accepting_a_supported_suggestion_is_mixed_provenance(self):
        suggestion = self.suggestion()
        res = self.post({'fields': {'explanation': 'Option A: reference passages, edited.'}, 'for_key': 'A',
                         'suggestion_id': str(suggestion.id), 'accepted_fields': ['explanation']})
        self.assertEqual(res.status_code, 200, res.data)
        q = Question.objects.get(pk=self.question.pk)
        self.assertEqual((q.explanation_origin, q.explanation_suggestion_id), ('mixed', suggestion.id))
        suggestion.refresh_from_db()
        self.assertIsNotNone(suggestion.accepted_at)
        self.assertEqual(suggestion.accepted_by, self.admin)

    def test_unsupported_stale_or_other_key_suggestions_cannot_be_accepted(self):
        cases = (
            (self.suggestion(status='conflict', fields={}), 400, 'suggestion_not_supported'),
            (self.suggestion(for_key='B'), 409, 'suggestion_for_other_key'),
            (self.suggestion(draft_stem_hash='f' * 64), 409, 'suggestion_for_other_content'),
        )
        for suggestion, code, name in cases:
            with self.subTest(name=name):
                res = self.post({'fields': {'explanation': 'Text.'}, 'suggestion_id': str(suggestion.id),
                                 'accepted_fields': ['explanation']})
                self.assertEqual((res.status_code, res.data.get('code')), (code, name))
        self.assertEqual(Question.objects.get(pk=self.question.pk).explanation_origin, '')

    def test_ai_generated_text_is_mixed_provenance(self):
        res = self.post({'fields': {'explanation': 'AI text the admin reviewed.'}, 'ai_fields': ['explanation']})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Question.objects.get(pk=self.question.pk).explanation_origin, 'mixed')

    def test_saving_re_audits_the_question(self):
        res = self.post({'fields': {'explanation': 'Option C is correct: air in the pleural space.'}})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['answer_key_status'], 'needs_review')
        from key_audit.models import QuestionAudit
        self.assertEqual(QuestionAudit.objects.get(question=self.question).status_reason, 'explanation_states_other')


class VerifyAndReviewEndpointTests(_Fixture):
    def test_verify_then_unverify(self):
        from key_audit.models import AuditResolution
        self.as_admin()
        res = self.client.post(self.url('verify-key'), {'action': 'verify'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['answer_key_status'], res.data['is_verified']), ('likely_correct', True))
        self.assertEqual(res.data['verification']['verified_by'], 'admin_editor')
        Question.objects.filter(pk=self.question.pk).update(is_verified_by_admin=True)
        res = self.client.post(self.url('verify-key'), {'action': 'unverify', 'reason': 'Options look garbled.'},
                               format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['answer_key_status'], 'needs_review')
        self.assertFalse(res.data['verification']['is_verified_by_admin'])
        self.assertEqual(list(AuditResolution.objects.filter(question=self.question)
                              .order_by('resolved_at', 'id').values_list('resolution', flat=True)),
                         ['key_confirmed', 'deferred'])

    def test_bad_verify_requests(self):
        self.as_admin()
        self.assertEqual(self.client.post(self.url('verify-key'), {'action': 'approve'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url('verify-key'), {'action': 'unverify', 'reason': {'x': 1}},
                                          format='json').status_code, 400)
        q = self.make(key='', text='Which drug is first line in anaphylaxis?')
        res = self.client.post(self.url('verify-key', q), {'action': 'verify'}, format='json')
        self.assertEqual((res.status_code, res.data['code']), (400, 'no_key'))

    def test_review_explanation_rules(self):
        self.as_admin()
        empty = self.make(text='Which drug is first line in anaphylaxis?', explanation='')
        self.assertEqual(self.client.post(self.url('review-explanation', empty)).status_code, 400)
        change_answer_key(self.question, 'B', actor=self.admin, reason='Troponin rise and ST elevation.')
        res = self.client.post(self.url('review-explanation'))
        self.assertEqual((res.status_code, res.data['code']), (409, 'explanation_stale'))

        fresh = self.make(text='Tearing chest pain radiating to the back: diagnosis?')
        res = self.client.post(self.url('review-explanation', fresh))
        self.assertEqual(res.status_code, 200, res.data)
        fresh.refresh_from_db()
        self.assertEqual((fresh.explanation_status, fresh.explanation_for_key, fresh.explanation_origin),
                         ('reviewed', 'A', 'legacy'))
        self.assertEqual(fresh.explanation_stem_hash, stem_hash(fresh))
        self.assertEqual(fresh.explanation_reviewed_hash, fresh.explanation_hash)


class ProvenanceEndpointTests(_Fixture):
    def test_provenance_payload(self):
        self.source_key(self.question, 'A', 'book.pdf')
        self.source_key(self.question, 'C', 'old.pdf', page=9, content_hash='0' * 64)   # made for older text
        self.as_admin()
        res = self.client.get(self.url('provenance'))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['correct_answer'], res.data['answer_key_status']), ('A', 'unaudited'))
        self.assertIsNone(res.data['audit'])
        self.assertEqual(res.data['explanation']['status'], 'pending_review')
        self.assertEqual([(r['source_file'], r['current_content']) for r in res.data['source_keys']],
                         [('book.pdf', True), ('old.pdf', False)])
        self.assertIn('reference_store_available', res.data)

        self.client.post(self.url('verify-key'), {'action': 'verify'}, format='json')
        res = self.client.get(self.url('provenance'))
        self.assertEqual((res.data['audit']['status'], res.data['answer_key_status']),
                         ('likely_correct', 'likely_correct'))
        self.assertEqual(res.data['verification']['verified_by'], 'admin_editor')

    def test_unknown_question(self):
        self.as_admin()
        self.assertEqual(self.client.get('/api/questions/999999/provenance/').status_code, 404)
