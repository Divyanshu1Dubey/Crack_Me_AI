"""Every path that changes an answer key goes through questions.editorial.change_answer_key (2026-11).

Ground rule 1 of docs/audit/MEDICAL_ACCURACY_DESIGN.md: the question PATCH / PUT, undo to a revision and
dispute resolution used to write ``correct_answer`` directly, so no AnswerKeyChange (old key, who, why)
was recorded and the answer-key audit, evidence and topic notes were never told.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from key_audit.models import AuditResolution, QuestionAudit
from questions.models import AnswerKeyChange, Question, QuestionRevisionSnapshot, Subject

User = get_user_model()


class KeyWriterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Key Writers', code='KW')
        cls.admin = User.objects.create_user(username='kw-admin', password='unused-pw-1', role='admin', is_staff=True)

    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.q = Question.objects.create(subject=self.subject, question_text='Which nerve supplies the deltoid?',
                                         option_a='Axillary', option_b='Radial', option_c='Median',
                                         option_d='Ulnar', correct_answer='A', year=2024, exam_type='cms')

    def url(self, suffix=''):
        return f'/api/questions/{self.q.id}/{suffix}'

    def test_patch_cannot_change_the_key(self):
        res = self.api.patch(self.url(), {'correct_answer': 'B'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('change-key', str(res.data['correct_answer']))
        self.q.refresh_from_db()
        self.assertEqual((self.q.correct_answer, self.q.lock_answer), ('A', False))
        self.assertFalse(AnswerKeyChange.objects.exists())

    def test_patch_with_the_same_key_saves_the_rest(self):
        res = self.api.patch(self.url(), {'correct_answer': 'A', 'explanation': 'The axillary nerve (C5-C6).'},
                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.q.refresh_from_db()
        self.assertEqual((self.q.correct_answer, self.q.explanation), ('A', 'The axillary nerve (C5-C6).'))
        self.assertFalse(self.q.lock_answer)   # nothing about the key changed

    def test_a_stem_edit_notifies_the_audit(self):
        from key_audit.services import audit_question
        audit_question(self.q)   # an existing audit: decisions made before the edit no longer count
        with self.captureOnCommitCallbacks(execute=True):
            res = self.api.patch(self.url(), {'question_text': 'Which nerve supplies the teres minor?'},
                                 format='json')
        self.assertEqual(res.status_code, 200, res.data)
        audit = QuestionAudit.objects.get(question=self.q)
        self.assertIsNotNone(audit.content_changed_at)

    def test_undo_restores_the_key_through_change_answer_key(self):
        QuestionRevisionSnapshot.objects.create(question=self.q, changed_by=self.admin, reason='before edit',
                                                snapshot={'correct_answer': 'C', 'question_text': self.q.question_text})
        with self.captureOnCommitCallbacks(execute=True):
            res = self.api.post(self.url('undo-last-revision/'), {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.q.refresh_from_db()
        self.assertEqual(self.q.correct_answer, 'C')
        change = AnswerKeyChange.objects.get(question=self.q)
        self.assertEqual((change.old_key, change.new_key, change.source), ('A', 'C', 'undo_revision'))

    def test_undo_to_a_revision_without_a_key_keeps_the_key(self):
        QuestionRevisionSnapshot.objects.create(question=self.q, changed_by=self.admin, reason='old import',
                                                snapshot={'correct_answer': '', 'question_text': self.q.question_text})
        res = self.api.post(self.url('undo-last-revision/'), {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data.get('key_kept'))
        self.q.refresh_from_db()
        self.assertEqual(self.q.correct_answer, 'A')
        self.assertFalse(AnswerKeyChange.objects.exists())

    def test_resolving_a_dispute_with_the_same_key_records_a_decision(self):
        Question.objects.filter(pk=self.q.pk).update(is_disputed=True)
        res = self.api.post(self.url('resolve-dispute/'),
                            {'corrected_answer': 'A', 'justification': 'Checked against the anatomy text.'},
                            format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.q.refresh_from_db()
        self.assertFalse(self.q.is_disputed)
        self.assertFalse(AnswerKeyChange.objects.exists())
        decision = AuditResolution.objects.get(question=self.q)
        self.assertEqual((decision.resolution, decision.stored_key), ('key_confirmed', 'A'))


class StaleExplanationTests(TestCase):
    """After a key correction the explanation written for the old key is not shown to students."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Stale Explanations', code='SE')
        cls.admin = User.objects.create_user(username='se-admin', password='unused-pw-1', role='admin', is_staff=True)
        cls.student = User.objects.create_user(username='se-student', password='unused-pw-2')

    def setUp(self):
        cache.clear()
        self.q = Question.objects.create(
            subject=self.subject, question_text='Drug of choice for absence seizures?', option_a='Phenytoin',
            option_b='Ethosuximide', option_c='Carbamazepine', option_d='Phenobarbital', correct_answer='A',
            explanation='Phenytoin is the answer because ...', ai_explanation='AI: phenytoin ...',
            year=2024, exam_type='cms')

    def test_key_change_hides_the_old_explanation_from_students_only(self):
        from rest_framework.test import APIRequestFactory

        from questions.editorial import change_answer_key
        from questions.serializers import (
            STALE_EXPLANATION_NOTICE, QuestionDetailSerializer, effective_explanation_for,
            explanation_for_another_key,
        )

        self.assertFalse(explanation_for_another_key(self.q))
        change_answer_key(self.q, 'B', actor=self.admin, reason='Ethosuximide is the drug of choice.',
                          evidence=[{'kind': 'note', 'text': 'standard pharmacology'}])
        self.q.refresh_from_db()
        self.assertTrue(explanation_for_another_key(self.q))
        self.assertEqual(effective_explanation_for(self.q), '')
        request = APIRequestFactory().get('/')
        request.user = self.student
        data = QuestionDetailSerializer(self.q, context={'request': request}).data
        self.assertEqual((data['explanation'], data['explanation_notice']), ('', STALE_EXPLANATION_NOTICE))
        request.user = self.admin
        data = QuestionDetailSerializer(self.q, context={'request': request}).data
        self.assertTrue(data['explanation'].startswith('Phenytoin is the answer'))   # admins rewrite it
        self.assertNotIn('explanation_notice', data)

    def test_a_new_explanation_for_the_new_key_is_shown_again(self):
        from questions.editorial import change_answer_key
        from questions.serializers import explanation_for_another_key

        change_answer_key(self.q, 'B', actor=self.admin, reason='Ethosuximide is the drug of choice.',
                          explanation_fields={'explanation': 'Ethosuximide blocks T-type calcium channels.'})
        self.q.refresh_from_db()
        self.assertFalse(explanation_for_another_key(self.q))
