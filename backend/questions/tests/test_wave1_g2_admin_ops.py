"""Wave-1 G2: admin / content-pipeline fixes in the questions app.

Issues: QB-06, QB-09, QB-12, QB-13, MOD-01, QB-15, QB-17, QB-18, QB-21,
EXT-01, QB-25, QB-27, QB-30, QB-31, QB-34. No AI provider is called.
"""
from __future__ import annotations

import json
import os
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from questions.models import (
    AdminAIPromptVersion, DuplicateCluster, DuplicateMember, Question, QuestionAttempt,
    QuestionExtractionItem, QuestionFeedback, QuestionImage, QuestionImportJob,
    QuestionRevisionSnapshot, RemovedQuestion, Subject, Topic, TopicNote,
)

User = get_user_model()

OUTAGE = 'All AI services are temporarily unavailable. Please try again in a moment.'


def _question(subject, i, **kw):
    defaults = dict(
        question_text=f'G2 admin stem {i}', option_a='alpha', option_b='beta', option_c='gamma',
        option_d='delta', correct_answer='A', year=2024, subject=subject,
    )
    defaults.update(kw)
    return Question.objects.create(**defaults)


class _AdminBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='G2 Admin Subject', code='G2ADM', exam_type='neet_pg')
        cls.admin = User.objects.create_user(username='g2-ops-admin', password='unused-pw-1', role='admin')
        cls.student = User.objects.create_user(username='g2-ops-student', email='g2-ops-student@example.com',
                                               password='unused-pw-2')

    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.api.force_authenticate(self.admin)


class ForceRegenerateTests(_AdminBase):
    def test_outage_sentence_is_not_saved(self):
        q = _question(self.subject, 1, ai_answer='Curated answer', ai_explanation='Curated explanation')
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.analyze_question.return_value = OUTAGE
            res = self.api.post(f'/api/questions/{q.id}/force-regenerate/')
        self.assertEqual(res.status_code, 503)
        q.refresh_from_db()
        self.assertEqual((q.ai_answer, q.ai_explanation), ('Curated answer', 'Curated explanation'))

    def test_provider_exception_is_a_503(self):
        q = _question(self.subject, 2, ai_explanation='Keep me')
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.analyze_question.side_effect = RuntimeError('All AI providers failed')
            res = self.api.post(f'/api/questions/{q.id}/force-regenerate/')
        self.assertEqual(res.status_code, 503)
        q.refresh_from_db()
        self.assertEqual(q.ai_explanation, 'Keep me')

    def test_active_prompt_version_is_used(self):
        q = _question(self.subject, 3)
        prompt = AdminAIPromptVersion.objects.create(
            name='v-test', prompt_text='Lead with the mechanism.', is_active=True, created_by=self.admin,
        )
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.analyze_question.return_value = '## Real analysis'
            res = self.api.post(f'/api/questions/{q.id}/force-regenerate/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['active_prompt_version'], prompt.id)
        kwargs = service.return_value.analyze_question.call_args.kwargs
        self.assertEqual(kwargs['user_prompt'], 'Lead with the mechanism.')
        q.refresh_from_db()
        self.assertEqual(q.ai_explanation, '## Real analysis')


class AICacheTaskAndBackfillTests(_AdminBase):
    FAILED = {'why_correct': OUTAGE, 'why_wrong': {}, 'mnemonic': '', 'raw_response': OUTAGE}
    GOOD = {
        'why_correct': 'Alpha is right because...', 'mnemonic': 'A for alpha',
        'clinical_pearl': 'Pearl', 'exam_tip': 'AI exam tip', 'core_concept': 'Concept',
        'textbook_reference': {'book': 'Harrison'}, 'around_concepts': ['x', 'y'],
    }

    def test_task_does_not_persist_failure_output(self):
        from questions.tasks import generate_ai_task
        q = _question(self.subject, 10, learning_technique='Curated technique')
        with mock.patch('questions.tasks.AIService') as service:
            service.return_value.explain_after_answer.return_value = dict(self.FAILED)
            self.assertFalse(generate_ai_task(q.id))
            service.return_value.explain_after_answer.side_effect = RuntimeError('AIUnavailable')
            self.assertFalse(generate_ai_task(q.id))
        q.refresh_from_db()
        self.assertEqual((q.ai_answer, q.ai_explanation, q.learning_technique), ('', '', 'Curated technique'))

    def test_task_honours_locks_and_keeps_curated_learning_technique(self):
        from questions.tasks import generate_ai_task
        q = _question(self.subject, 11, ai_answer='Locked answer', lock_answer=True,
                      learning_technique='Curated technique')
        with mock.patch('questions.tasks.AIService') as service:
            service.return_value.explain_after_answer.return_value = dict(self.GOOD)
            self.assertTrue(generate_ai_task(q.id))
        q.refresh_from_db()
        self.assertEqual(q.ai_answer, 'Locked answer')
        self.assertEqual(q.learning_technique, 'Curated technique')
        self.assertEqual(json.loads(q.ai_explanation)['why_correct'], 'Alpha is right because...')
        self.assertEqual(q.ai_mnemonic, 'A for alpha')

    def test_backfill_skips_failure_output(self):
        from questions.management.commands.backfill_empty_ai import Command
        q = _question(self.subject, 12, learning_technique='Keep')
        service = mock.Mock()
        service.explain_after_answer.return_value = dict(self.FAILED)
        cmd = Command(stdout=StringIO())
        self.assertFalse(cmd._process_one(q, service, max_retries=0))
        q.refresh_from_db()
        self.assertEqual((q.ai_explanation, q.ai_answer, q.learning_technique), ('', '', 'Keep'))
        service.explain_after_answer.return_value = dict(self.GOOD)
        self.assertTrue(cmd._process_one(q, service, max_retries=0))
        q.refresh_from_db()
        self.assertEqual(q.ai_answer, 'Alpha is right because...')
        self.assertEqual(q.learning_technique, 'Keep')


class GenerateExplanationImageTests(_AdminBase):
    def test_image_without_caption_does_not_500(self):
        q = _question(self.subject, 20, explanation='')
        QuestionImage.objects.create(question=q, page_number=1, caption='', ocr_text='ECG: ST elevation')
        result = {'explanation': 'Generated explanation', 'why_correct': 'Because'}
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value.generate_admin_explanation.return_value = result
            res = self.api.post(f'/api/questions/{q.id}/generate-explanation/', {'correct_answer': 'A'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        kwargs = service.return_value.generate_admin_explanation.call_args.kwargs
        self.assertEqual(kwargs['image_descriptions'], ['ECG: ST elevation'])
        q.refresh_from_db()
        self.assertEqual(q.explanation, 'Generated explanation')


class PartialSaveTests(_AdminBase):
    def test_update_fields_save_does_not_revert_concurrent_edits(self):
        q = _question(self.subject, 30, explanation='Old explanation')
        stale = Question.objects.get(pk=q.pk)
        Question.objects.filter(pk=q.pk).update(question_text='Admin fixed stem', explanation='Admin fixed')
        stale.video_url = 'https://example.com/v.mp4'
        stale.save(update_fields=['video_url'])
        q.refresh_from_db()
        self.assertEqual(q.question_text, 'Admin fixed stem')
        self.assertEqual(q.explanation, 'Admin fixed')
        self.assertEqual(q.video_url, 'https://example.com/v.mp4')


class DeleteIsSoftTests(_AdminBase):
    def test_delete_tombstones_and_keeps_history(self):
        q = _question(self.subject, 40)
        QuestionAttempt.objects.create(user=self.student, question=q, selected_answer='A', is_correct=True)
        QuestionImage.objects.create(question=q, page_number=1)  # PROTECT relation
        res = self.api.delete(f'/api/questions/{q.id}/')
        self.assertEqual(res.status_code, 204)
        q.refresh_from_db()
        self.assertFalse(q.is_active)
        self.assertTrue(q.is_dropped)
        self.assertTrue(RemovedQuestion.objects.filter(original_question_id=q.id).exists())
        self.assertTrue(QuestionAttempt.objects.filter(question=q).exists())

    def test_students_cannot_delete(self):
        q = _question(self.subject, 41)
        client = APIClient()
        client.force_authenticate(self.student)
        self.assertEqual(client.delete(f'/api/questions/{q.id}/').status_code, 403)


class ResolveDisputeTests(_AdminBase):
    def test_answer_is_validated_normalised_and_locked(self):
        q = _question(self.subject, 50, is_disputed=True)
        for raw, expected in (('b', 'B'), ('Option C', 'C')):
            res = self.api.post(f'/api/questions/{q.id}/resolve-dispute/',
                                {'corrected_answer': raw, 'justification': 'key error'}, format='json')
            self.assertEqual(res.status_code, 200, res.data)
            q.refresh_from_db()
            self.assertEqual(q.correct_answer, expected)
        self.assertTrue(q.lock_answer)
        self.assertTrue(q.admin_edited)
        self.assertFalse(q.is_disputed)
        self.assertEqual(QuestionRevisionSnapshot.objects.filter(question=q).count(), 2)
        for bad in ('E', 'xyz', 'AB'):
            res = self.api.post(f'/api/questions/{q.id}/resolve-dispute/',
                                {'corrected_answer': bad, 'justification': 'x'}, format='json')
            self.assertEqual(res.status_code, 400, bad)

    def test_verify_answers_fix_skips_human_decisions(self):
        locked = _question(self.subject, 51, year=2031, lock_answer=True)
        verified = _question(self.subject, 52, year=2031, is_verified_by_admin=True)
        open_q = _question(self.subject, 53, year=2031)
        # The mismatch report goes to a temp dir (it used to land in the
        # working directory as answer_mismatches_2031.csv on every run).
        with tempfile.TemporaryDirectory() as tmp:
            report = os.path.join(tmp, 'mismatches.csv')
            with mock.patch('ai_engine.services.AIService') as service:
                service.return_value.get_consensus_answer.return_value = 'B'
                call_command('verify_answers', year=2031, fix=True, sleep_ms=0, output=report, stdout=StringIO())
            with open(report, encoding='utf-8') as fh:
                self.assertIn(str(open_q.id), fh.read())
        for q, expected in ((locked, 'A'), (verified, 'A'), (open_q, 'B')):
            q.refresh_from_db()
            self.assertEqual(q.correct_answer, expected, q.id)


class FeedbackQueueTests(_AdminBase):
    def setUp(self):
        super().setUp()
        from tests_engine.models import QuestionResponse, Test, TestAttempt
        self.q = _question(self.subject, 60)
        self.reporter2 = User.objects.create_user(username='g2-ops-reporter2', password='unused-pw-3')
        self.f1 = QuestionFeedback.objects.create(question=self.q, user=self.student, category='wrong_answer', comment='1')
        self.f2 = QuestionFeedback.objects.create(question=self.q, user=self.reporter2, category='typo', comment='2')
        for i in range(3):
            test = Test.objects.create(title=f'G2 queue test {i}', test_type='mixed')
            attempt = TestAttempt.objects.create(user=self.student, test=test)
            QuestionResponse.objects.create(attempt=attempt, question=self.q, selected_answer='A', is_correct=i == 0)

    def _row(self):
        rows = self.api.get('/api/questions/feedback/admin-queue/').data['results']
        return next(r for r in rows if r['question_id'] == self.q.id)

    def _rewards(self):
        from accounts.models import TokenTransaction
        return TokenTransaction.objects.filter(transaction_type='feedback_reward').count()

    def test_counts_are_distinct_and_status_is_derived(self):
        row = self._row()
        self.assertEqual((row['reports'], row['unresolved_reports'], row['attempts']), (2, 2, 3))
        self.assertEqual(row['status'], 'new')
        self.api.patch(f'/api/questions/feedback/{self.f1.id}/status/', {'status': 'in_progress'}, format='json')
        self.assertEqual(self._row()['status'], 'in_progress')

    def test_queue_resolve_resolves_all_reports_and_pays_each_reporter_once(self):
        res = self.api.patch(f"/api/questions/feedback/{self._row()['feedback_id']}/status/",
                             {'status': 'resolved', 'notify_user': True}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(QuestionFeedback.objects.filter(question=self.q, is_resolved=True).count(), 2)
        self.assertEqual(self._rewards(), 2)
        self.assertEqual(self._row()['status'], 'resolved')
        self.f1.refresh_from_db()
        self.assertTrue(self.f1.notified_user)  # reporter has an e-mail
        self.f2.refresh_from_db()
        self.assertFalse(self.f2.notified_user)  # no e-mail -> not claimed as notified
        # toggling back and resolving again never pays twice
        self.api.patch(f'/api/questions/feedback/{self.f1.id}/status/', {'status': 'new'}, format='json')
        self.api.patch(f'/api/questions/feedback/{self.f1.id}/status/', {'status': 'resolved'}, format='json')
        self.assertEqual(self._rewards(), 2)
        self.assertEqual(self.api.patch(f'/api/questions/feedback/{self.f1.id}/resolve/').status_code, 400)
        self.assertEqual(self._rewards(), 2)

    def test_reporters_cannot_preset_moderation_fields(self):
        res = APIClient().post('/api/questions/feedback/', {
            'question': self.q.id, 'category': 'typo', 'comment': 'x',
            'status': 'resolved', 'resolution_note': 'self-resolved',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        fb = QuestionFeedback.objects.get(pk=res.data['id'])
        self.assertEqual((fb.status, fb.resolution_note, fb.is_resolved), ('new', '', False))


class ExtractionPublishTests(_AdminBase):
    def _item(self, **kw):
        job = QuestionImportJob.objects.create(job_type='pdf', source_filename='paper.pdf')
        defaults = dict(job=job, status='approved', question_text='A real stem', subject=self.subject,
                        option_a='a', option_b='b', option_c='c', option_d='d', correct_answer='b', year=2023)
        defaults.update(kw)
        return QuestionExtractionItem.objects.create(**defaults)

    def _publish(self, item):
        return self.api.post(f'/api/questions/extraction/items/{item.id}/publish/', {}, format='json')

    def test_only_complete_approved_items_can_be_published(self):
        cases = [
            self._item(status='pending'),
            self._item(status='rejected'),
            self._item(question_text='Extracted content pending parser review'),
            self._item(option_c=''),
            self._item(correct_answer=''),
        ]
        before = Question.objects.count()
        for item in cases:
            self.assertEqual(self._publish(item).status_code, 400, item.id)
        self.assertEqual(Question.objects.count(), before)

    def test_publish_uses_explicit_answer_and_subject_exam(self):
        res = self._publish(self._item())
        self.assertEqual(res.status_code, 201, res.data)
        q = Question.objects.get(pk=res.data['question_id'])
        self.assertEqual((q.correct_answer, q.exam_type, q.exam_source), ('B', 'neet_pg', 'NEET PG'))


class MergeDuplicatesTests(_AdminBase):
    def test_text_match_duplicates_can_be_merged_without_a_cluster(self):
        keep = _question(self.subject, 70, question_text='Same duplicate stem', exam_source='NEET PG')
        dup = _question(self.subject, 71, question_text='Same duplicate stem!', exam_source='NEET PG')
        res = self.api.post(f'/api/questions/{keep.id}/merge-duplicates/', {'duplicate_ids': [dup.id]}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        dup.refresh_from_db()
        self.assertEqual((dup.is_active, dup.is_dropped), (False, True))
        cluster = DuplicateCluster.objects.get(pk=res.data['cluster_id'])
        self.assertEqual(cluster.canonical_question_id, keep.id)
        self.assertEqual(set(cluster.members.values_list('question_id', flat=True)), {keep.id, dup.id})

    def test_rejected_merge_leaves_no_orphan_cluster(self):
        keep = _question(self.subject, 72, question_text='Lonely stem')
        other = _question(self.subject, 73, question_text='Completely different stem')
        res = self.api.post(f'/api/questions/{keep.id}/merge-duplicates/', {'duplicate_ids': [other.id]}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(DuplicateCluster.objects.exists())
        other.refresh_from_db()
        self.assertTrue(other.is_active)

    def test_merge_opened_from_a_non_canonical_member_keeps_the_canonical(self):
        canonical, member, sibling = (_question(self.subject, i) for i in (74, 75, 76))
        cluster = DuplicateCluster.objects.create(canonical_question=canonical)
        for q in (canonical, member, sibling):
            DuplicateMember.objects.create(cluster=cluster, question=q, similarity_score=0.99)
        res = self.api.post(f'/api/questions/{member.id}/merge-duplicates/',
                            {'duplicate_ids': [member.id, sibling.id]}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['canonical_id'], canonical.id)
        self.assertEqual(Question.objects.filter(pk__in=[member.id, sibling.id], is_active=False).count(), 2)
        res = self.api.post(f'/api/questions/{canonical.id}/merge-duplicates/',
                            {'duplicate_ids': [canonical.id]}, format='json')
        self.assertEqual(res.status_code, 400)


class TopicNoteTests(_AdminBase):
    def setUp(self):
        super().setUp()
        self.topic = Topic.objects.create(subject=self.subject, name='G2 Shock')

    def test_create_then_update_in_place(self):
        payload = {'title': 'Shock notes', 'content': 'v1', 'subject': self.subject.id,
                   'topic': self.topic.id, 'exam_type': 'neet_pg'}
        self.assertEqual(self.api.post('/api/questions/topic-notes/', payload, format='json').status_code, 201)
        payload.update(title='Shock notes (rev)', content='v2', is_published=True)
        res = self.api.post('/api/questions/topic-notes/', payload, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        note = TopicNote.objects.get()
        self.assertEqual((note.content, note.title, note.is_published), ('v2', 'Shock notes (rev)', True))

    def test_generate_without_pk_reuses_the_topic_note(self):
        TopicNote.objects.create(title='Existing title', content='', subject=self.subject, topic=self.topic,
                                 exam_type='neet_pg')
        _question(self.subject, 80, topic=self.topic, exam_type='neet_pg', explanation='Shock explanation')
        with mock.patch('ai_engine.services.AIService') as service:
            service.return_value._call_ai.return_value = '# Generated topic notes'
            # pk=0 means "no pk": the view falls back to the body lookup,
            # which used to get_or_create on the title -> IntegrityError.
            res = self.api.post('/api/questions/topic-notes/0/generate/',
                                {'subject': self.subject.id, 'topic': self.topic.id,
                                 'exam_type': 'neet_pg', 'title': 'Another title'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(TopicNote.objects.count(), 1)
        self.assertEqual(TopicNote.objects.get().content, '# Generated topic notes')

    def test_students_can_read_published_notes_only(self):
        TopicNote.objects.create(title='Draft', content='d', subject=self.subject, topic=self.topic,
                                 exam_type='neet_pg', is_published=False)
        other = Topic.objects.create(subject=self.subject, name='G2 Sepsis')
        TopicNote.objects.create(title='Published', content='p', subject=self.subject, topic=other,
                                 exam_type='neet_pg', is_published=True)
        client = APIClient()
        client.force_authenticate(self.student)
        res = client.get('/api/questions/topic-notes/published/')
        self.assertEqual(res.status_code, 200)
        titles = [row['title'] for row in res.data['results']]
        self.assertEqual(titles, ['Published'])
        self.assertIn(APIClient().get('/api/questions/topic-notes/published/').status_code, (401, 403))


class BackupAndFixtureCommandTests(_AdminBase):
    def test_export_questions_backup_runs(self):
        _question(self.subject, 90)
        with tempfile.TemporaryDirectory() as tmp:
            call_command('export_questions_backup', output_dir=tmp, stdout=StringIO())
            path = os.path.join(tmp, 'questions.question.json')
            with open(path, encoding='utf-8') as fh:
                rows = json.load(fh)
        self.assertTrue(any(row['fields']['question_text'] == 'G2 admin stem 90' for row in rows))

    def test_replace_never_deletes_questions(self):
        from questions.management.commands.load_exam_fixture import Command
        used = Subject.objects.create(name='G2 Used', code='G2USED', exam_type='ini_cet')
        q = _question(used, 91)
        unused = Subject.objects.create(name='G2 Obsolete', code='G2OBS', exam_type='ini_cet')
        listed = Subject.objects.create(name='G2 Listed', code='G2LIST', exam_type='ini_cet')
        raw = [{'model': 'questions.subject', 'fields': {'code': 'G2LIST', 'name': 'G2 Listed'}}]
        Command(stdout=StringIO())._purge_exam('ini_cet', raw)
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())
        self.assertTrue(Subject.objects.filter(pk=used.pk).exists())
        self.assertTrue(Subject.objects.filter(pk=listed.pk).exists())
        self.assertFalse(Subject.objects.filter(pk=unused.pk).exists())


class NoRequestTimeBootstrapTests(_AdminBase):
    def test_public_gets_never_run_management_commands(self):
        from questions import views
        self.assertFalse(hasattr(views, '_ensure_question_bank_loaded'))
        with mock.patch('django.core.management.call_command') as cmd:
            self.assertEqual(APIClient().get('/api/questions/years/').status_code, 200)
            self.assertEqual(APIClient().get('/api/questions/stats/').status_code, 200)
        cmd.assert_not_called()
