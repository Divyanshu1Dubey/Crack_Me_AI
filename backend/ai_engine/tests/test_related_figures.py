"""Related PYQ figures next to an AI Tutor answer (ai_engine/related_figures.py)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from ai_engine.related_figures import related_figures, tokens
from questions.models import Question, QuestionImage, Subject

User = get_user_model()


class RelatedFiguresTests(TestCase):
    def setUp(self):
        cache.clear()
        self.subject = Subject.objects.create(name='Medicine', code='MED')
        self.ecg = self._question('ECG of a patient with hyperkalemia shows tall tented T waves; identify the change',
                                  alt='Twelve-lead ECG with tall peaked T waves')
        self.xray = self._question('Chest radiograph of a smoker with a cavitating lesion in the right upper lobe',
                                   alt='Chest X-ray, right upper lobe cavity')
        self.hidden = self._question('Histology of hyperkalemia kidney biopsy with tented T waves', role='explanation',
                                     alt='ECG tall tented T waves hyperkalemia')
        self.scholarship = self._question('ECG hyperkalemia tented T waves challenge question',
                                          alt='ECG tented', scholarship=True)
        self.url = reverse('ai-related-figures')

    def _question(self, text, *, alt='', role='primary', scholarship=False):
        q = Question.objects.create(subject=self.subject, question_text=text, option_a='a', option_b='b',
                                    option_c='c', option_d='d', correct_answer='A', exam_type='cms', year=2024,
                                    is_active=True, is_scholarship_eligible=scholarship)
        QuestionImage.objects.create(question=q, page_number=1, role=role, alt_text=alt, is_active=True,
                                     caption='Answer: hyperkalemia', caption_reveals_answer=True)
        return q

    def _client(self, *, premium=False, staff=False):
        user = User.objects.create_user(username=f'u{User.objects.count()}', email=f'u{User.objects.count()}@t.test',
                                        password='x-Unused-9f2!')
        if staff:
            user.is_staff = True
            user.save()
        if premium:
            Subscription.objects.create(user=user, plan='1_month', plan_display_name='1 Month', status='active',
                                        amount_paid=129, expires_at=timezone.now() + timedelta(days=20))
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_tokens_drop_question_words(self):
        self.assertEqual(tokens('Explain the pathophysiology of the ECG in hyperkalemia'), {'ecg', 'hyperkalemia'})

    def test_matching_uses_stem_side_figures_only_and_needs_a_real_overlap(self):
        ids = [row['question_id'] for row in related_figures('ECG changes in hyperkalemia: tented T waves')]
        self.assertEqual(ids, [self.ecg.pk])          # not the explanation figure, not the scholarship question
        self.assertEqual(related_figures('Explain the pathophysiology of this'), [])   # vague: nothing
        self.assertEqual(related_figures(''), [])

    def test_premium_gets_figures_without_answer_captions(self):
        res = self._client(premium=True).get(self.url, {'q': 'hyperkalemia ECG tented T waves'})
        self.assertEqual(res.status_code, 200)
        figures = res.data['figures']
        self.assertEqual([f['question_id'] for f in figures], [self.ecg.pk])
        image = figures[0]['image']
        self.assertEqual(image['caption'], '')                 # the caption names the answer
        self.assertTrue(image['caption_after_reveal'])
        self.assertIn('alt_text', image)
        self.assertNotIn('ocr_text', image)

    def test_free_users_only_get_questions_they_may_open(self):
        client = self._client()
        self.assertEqual(client.get(self.url, {'q': 'hyperkalemia ECG tented T waves'}).data['figures'], [])
        FreeShowcaseQuestion.objects.create(question=self.ecg, year=2024, position=1)
        ids = [f['question_id'] for f in client.get(self.url, {'q': 'hyperkalemia ECG tented'}).data['figures']]
        self.assertEqual(ids, [self.ecg.pk])

    def test_anonymous_is_refused_and_staff_sees_all(self):
        self.assertIn(APIClient().get(self.url, {'q': 'ECG'}).status_code, (401, 403))
        ids = [f['question_id'] for f in self._client(staff=True).get(
            self.url, {'q': 'chest radiograph cavitating lesion'}).data['figures']]
        self.assertEqual(ids, [self.xray.pk])

    def test_deactivated_question_disappears_even_from_a_cached_index(self):
        related_figures('hyperkalemia ECG tented')   # builds and caches the index
        Question.objects.filter(pk=self.ecg.pk).update(is_active=False)
        res = self._client(premium=True).get(self.url, {'q': 'hyperkalemia ECG tented T waves'})
        self.assertEqual(res.data['figures'], [])
