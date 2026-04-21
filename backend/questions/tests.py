from django.contrib.auth import get_user_model
from django.test import TestCase

from analytics.models import Announcement
from questions.models import Question, QuestionFeedback, Subject
from tests_engine.models import QuestionResponse, Test, TestAttempt


User = get_user_model()


class AdminControlTowerApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_control',
            email='admin-control@example.com',
            password='StrongPass123!',
            role='admin',
        )
        self.student = User.objects.create_user(
            username='student_control',
            email='student-control@example.com',
            password='StrongPass123!',
            role='student',
        )
        self.subject = Subject.objects.create(name='Medicine', code='MED', paper=1)
        self.question = Question.objects.create(
            question_text='Which option is correct?',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='A',
            year=2024,
            subject=self.subject,
            topic=None,
            difficulty='medium',
            explanation='Baseline explanation',
        )
        self.feedback = QuestionFeedback.objects.create(
            question=self.question,
            user=self.student,
            category='wrong_answer',
            comment='Incorrect key',
            status='new',
            is_resolved=False,
        )
        self.client.force_login(self.admin)

    def test_issue_queue_and_status_workflow(self):
        queue_response = self.client.get('/api/questions/feedback/admin-queue/?sort=highest_impact')
        self.assertEqual(queue_response.status_code, 200)
        payload = queue_response.json()
        self.assertGreaterEqual(payload.get('count', 0), 1)
        row = payload['results'][0]
        self.assertIn('feedback_id', row)
        self.assertIn('status', row)

        status_response = self.client.patch(
            f"/api/questions/feedback/{row['feedback_id']}/status/",
            data={'status': 'resolved', 'notify_user': True, 'resolution_note': 'Fixed key'},
            content_type='application/json',
        )
        self.assertEqual(status_response.status_code, 200)
        self.feedback.refresh_from_db()
        self.assertTrue(self.feedback.is_resolved)
        self.assertEqual(self.feedback.status, 'resolved')
        self.assertTrue(self.feedback.notified_user)

    def test_question_revision_diff_and_undo(self):
        update_response = self.client.patch(
            f'/api/questions/{self.question.id}/',
            data={'explanation': 'Updated explanation text'},
            content_type='application/json',
        )
        self.assertEqual(update_response.status_code, 200)

        revisions_response = self.client.get(f'/api/questions/{self.question.id}/revisions/')
        self.assertEqual(revisions_response.status_code, 200)
        revisions_payload = revisions_response.json()
        self.assertGreaterEqual(revisions_payload.get('count', 0), 1)
        revision_id = revisions_payload['results'][0]['id']

        diff_response = self.client.get(f'/api/questions/{self.question.id}/revisions-diff/?revision_id={revision_id}')
        self.assertEqual(diff_response.status_code, 200)
        changed_fields = diff_response.json().get('changed_fields', [])
        self.assertTrue(any(row.get('field') == 'explanation' for row in changed_fields))

        undo_response = self.client.post(
            f'/api/questions/{self.question.id}/undo-last-revision/',
            data={'revision_id': revision_id},
            content_type='application/json',
        )
        self.assertEqual(undo_response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.explanation, 'Baseline explanation')

    def test_campaign_create_and_send_now(self):
        create_response = self.client.post(
            '/api/analytics/admin/campaigns/',
            data={
                'title': 'Revision Push',
                'message': 'Revise medicine high-yield topics',
                'priority': 'normal',
                'is_active': True,
                'audience_filter': {'role': 'student', 'active_only': True},
            },
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 201)
        campaign_id = create_response.json()['id']

        send_response = self.client.post(f'/api/analytics/admin/campaigns/{campaign_id}/send-now/')
        self.assertEqual(send_response.status_code, 200)
        campaign = Announcement.objects.get(id=campaign_id)
        self.assertEqual(campaign.delivery_status, 'sent')
        self.assertEqual(campaign.delivery_count, 1)

    def test_related_concept_reference_and_format_fix(self):
        related = Question.objects.create(
            question_text='Related PYQ sample',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='B',
            year=2023,
            subject=self.subject,
            difficulty='medium',
        )

        relation_response = self.client.patch(
            f'/api/questions/{self.question.id}/related-pyqs/',
            data={'related_ids': [related.id]},
            content_type='application/json',
        )
        self.assertEqual(relation_response.status_code, 200)

        concept_response = self.client.patch(
            f'/api/questions/{self.question.id}/concept-id/',
            data={'concept_id': 'MED-CARD-101'},
            content_type='application/json',
        )
        self.assertEqual(concept_response.status_code, 200)

        reference_response = self.client.patch(
            f'/api/questions/{self.question.id}/reference/',
            data={
                'book_name': 'Harrison',
                'chapter': 'Cardiology',
                'page_number': '123',
                'reference_text': 'Authoritative explanation excerpt',
            },
            content_type='application/json',
        )
        self.assertEqual(reference_response.status_code, 200)

        Question.objects.filter(id=self.question.id).update(
            question_text='Amino Acids statements:\n\n\n I. Essential from diet ; II. Non-essential also needed',
            option_a='A) 1 and 2',
            option_b='B) only 1',
            option_c='C) only 2',
            option_d='D) none',
        )
        format_response = self.client.patch(f'/api/questions/{self.question.id}/format-fix/', content_type='application/json')
        self.assertEqual(format_response.status_code, 200)

        self.question.refresh_from_db()
        self.assertEqual(self.question.concept_id, 'MED-CARD-101')
        self.assertEqual(self.question.book_name, 'Harrison')
        self.assertTrue(self.question.similar_questions.filter(id=related.id).exists())
        self.assertFalse(self.question.option_a.upper().startswith('A)'))

    def test_patch_update_persists_multiline_statement_format(self):
        response = self.client.patch(
            f'/api/questions/{self.question.id}/',
            data={
                'question_text': 'Recessive, sex-linked traits? * I. Retinitis pigmentosa; II. Colour blindness; III. Cystic fibrosis; IV. Duchenne muscular dystrophy.',
                'option_a': 'A) I, II, III',
                'option_b': 'B) I, II, IV',
                'option_c': 'C) II, III, IV',
                'option_d': 'D) I, III, IV',
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        self.question.refresh_from_db()
        self.assertIn('\nI. Retinitis pigmentosa;\nII. Colour blindness;\nIII. Cystic fibrosis;\nIV. Duchenne muscular dystrophy.', self.question.question_text)
        self.assertEqual(self.question.option_a, 'I, II, III')

    def test_model_save_normalizes_multiline_statement_text(self):
        self.question.question_text = 'Recessive, sex-linked traits? * I. Retinitis pigmentosa; II. Colour blindness; III. Cystic fibrosis; IV. Duchenne muscular dystrophy.'
        self.question.save(update_fields=['question_text'])

        self.question.refresh_from_db()
        self.assertIn('\nI. Retinitis pigmentosa;\nII. Colour blindness;\nIII. Cystic fibrosis;\nIV. Duchenne muscular dystrophy.', self.question.question_text)

    def test_question_list_accuracy_filters(self):
        test = Test.objects.create(title='Accuracy Filter Test', test_type='mixed', subject=self.subject, is_published=True)
        attempt = TestAttempt.objects.create(user=self.student, test=test)
        QuestionResponse.objects.create(attempt=attempt, question=self.question, selected_answer='A', is_correct=True)
        QuestionResponse.objects.create(attempt=attempt, question=Question.objects.create(
            question_text='Second item',
            option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A', year=2022, subject=self.subject, difficulty='medium',
        ), selected_answer='B', is_correct=False)

        high_accuracy_response = self.client.get('/api/questions/?accuracy_min=90')
        self.assertEqual(high_accuracy_response.status_code, 200)
        high_rows = high_accuracy_response.json().get('results', high_accuracy_response.json())
        self.assertTrue(any(int(row['id']) == self.question.id for row in high_rows))

        low_accuracy_response = self.client.get('/api/questions/?accuracy_max=10')
        self.assertEqual(low_accuracy_response.status_code, 200)
        low_rows = low_accuracy_response.json().get('results', low_accuracy_response.json())
        self.assertFalse(any(int(row['id']) == self.question.id for row in low_rows))

    def test_tests_generate_rejects_invalid_num_questions(self):
        invalid_response = self.client.post(
            '/api/tests/generate/',
            data={'test_type': 'mixed', 'num_questions': 'not-a-number'},
            content_type='application/json',
        )
        self.assertEqual(invalid_response.status_code, 400)

        non_positive_response = self.client.post(
            '/api/tests/generate/',
            data={'test_type': 'mixed', 'num_questions': 0},
            content_type='application/json',
        )
        self.assertEqual(non_positive_response.status_code, 400)

        too_large_response = self.client.post(
            '/api/tests/generate/',
            data={'test_type': 'mixed', 'num_questions': 501},
            content_type='application/json',
        )
        self.assertEqual(too_large_response.status_code, 400)

    def test_bulk_metadata_rejects_invalid_payload(self):
        invalid_ids_response = self.client.patch(
            '/api/questions/bulk-metadata/',
            data={'ids': ['abc'], 'difficulty': 'medium'},
            content_type='application/json',
        )
        self.assertEqual(invalid_ids_response.status_code, 400)

        invalid_subject_response = self.client.patch(
            '/api/questions/bulk-metadata/',
            data={'ids': [self.question.id], 'subject': 999999},
            content_type='application/json',
        )
        self.assertEqual(invalid_subject_response.status_code, 400)

        invalid_difficulty_response = self.client.patch(
            '/api/questions/bulk-metadata/',
            data={'ids': [self.question.id], 'difficulty': 'impossible'},
            content_type='application/json',
        )
        self.assertEqual(invalid_difficulty_response.status_code, 400)

    def test_student_cannot_access_admin_control_endpoints(self):
        self.client.force_login(self.student)

        verify_response = self.client.patch(
            f'/api/questions/{self.question.id}/verify/',
            data={'verified_note': 'Try verify as student'},
            content_type='application/json',
        )
        self.assertEqual(verify_response.status_code, 403)

        create_campaign_response = self.client.post(
            '/api/analytics/admin/campaigns/',
            data={'title': 'Unauthorized', 'message': 'Student should not create this'},
            content_type='application/json',
        )
        self.assertEqual(create_campaign_response.status_code, 403)

    def test_admin_question_list_includes_inactive_questions(self):
        inactive_question = Question.objects.create(
            question_text='Archived admin-only question',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='B',
            year=2021,
            subject=self.subject,
            topic=None,
            difficulty='easy',
            explanation='Archived explanation',
            is_active=False,
        )

        self.client.logout()
        public_response = self.client.get('/api/questions/?search=Archived')
        self.assertEqual(public_response.status_code, 200)
        public_rows = public_response.json().get('results', public_response.json())
        self.assertFalse(any(int(row['id']) == inactive_question.id for row in public_rows))

        self.client.force_login(self.admin)
        admin_response = self.client.get('/api/questions/?search=Archived')
        self.assertEqual(admin_response.status_code, 200)
        admin_rows = admin_response.json().get('results', admin_response.json())
        self.assertTrue(any(int(row['id']) == inactive_question.id for row in admin_rows))
