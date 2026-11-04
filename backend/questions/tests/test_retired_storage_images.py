"""Figures stored at a Supabase Storage address after that host was shut down (2026-11-03).

Live symptom (2026-11-04, question 25471): the question view handed the browser the stored Supabase
address of two admin-uploaded figures, so they rendered as broken images and "[image unavailable]",
while the image endpoint served both from the restored copy. Every payload (list, detail, admin image
rows) must hand out the image endpoint; the endpoint serves the restored copy
(SUPABASE_STORAGE_MIRROR_DIR) and answers 404 image_missing without one instead of redirecting to the
dead host. questions.image_health reports which figures this server can serve. No network call.
"""
from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from questions.image_context import is_retired_storage_url, serialize_image_for_student
from questions.image_health import figure_source, image_health_report
from questions.models import Question, QuestionImage, Subject

User = get_user_model()
_TMP = tempfile.mkdtemp(prefix='retired-storage-tests-')
_MEDIA = str(Path(_TMP) / 'media')
_MIRROR = str(Path(_TMP) / 'mirror')
_BUCKET = 'crack-cms-question-images'
_STORAGE = 'https://ryuvcdthjnxyetdyjbph.supabase.co/storage/v1/object/public/' + _BUCKET + '/question_images/{q}/{name}'


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _png(color='green'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 20), color=color).save(buf, format='PNG')
    return buf.getvalue()


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _serve_path(image_id):
    return f'/api/questions/images/{image_id}/serve/'


class RetiredStorageUrlTests(SimpleTestCase):
    def test_only_supabase_storage_addresses_are_retired(self):
        self.assertTrue(is_retired_storage_url('https://abc.supabase.co/storage/v1/object/public/b/x.png'))
        self.assertTrue(is_retired_storage_url('  HTTPS://ABC.SUPABASE.CO/storage/v1/object/public/b/x.png'))
        for url in ('', None, '/media/recall_images/x.png', 'https://cdn.example.test/x.png',
                    'https://supabase.co.example.test/storage/x.png', 'https://abc.supabase.co/rest/v1/x'):
            self.assertFalse(is_retired_storage_url(url), url)


@override_settings(MEDIA_ROOT=_MEDIA, SUPABASE_STORAGE_MIRROR_DIR=_MIRROR)
class RetiredStorageFigureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Retired Storage Subject', code='RETSTO')
        cls.question = Question.objects.create(
            question_text='Given below is a table.', option_a='I only', option_b='II only',
            option_c='Both', option_d='Neither', correct_answer='A', year=2025, subject=subject,
        )
        q = cls.question.pk

        def stored(name, index):
            return QuestionImage.objects.create(
                question=cls.question, page_number=0, image_index_in_page=index, role='illustration',
                url=_STORAGE.format(q=q, name=name), mime='image/png', width=40, height=20,
                uploaded_by_admin=True,
            )

        # The restored copy has this one ...
        cls.restored = stored('aaaa1111.png', 0)
        mirrored = Path(_MIRROR, _BUCKET, 'question_images', str(q), 'aaaa1111.png')
        mirrored.parent.mkdir(parents=True, exist_ok=True)
        mirrored.write_bytes(_png())
        # ... and not this one.
        cls.lost = stored('bbbb2222.png', 1)
        cls.question.question_text = (f'Given below is a table. [[img:{cls.restored.pk}]] [[img:{cls.lost.pk}]] '
                                      'Which of the statements is correct?')
        cls.question.save(update_fields=['question_text'])
        cls.admin = User.objects.create_superuser(
            username='retsto-admin', email='retsto-admin@example.com', password='unused-pw-1')
        cls.student = User.objects.create_user(
            username='retsto-student', email='retsto-student@example.com', password='unused-pw-2')

    def setUp(self):
        cache.clear()

    def _assert_endpoint_urls(self, images, key='url'):
        self.assertEqual({img['id'] for img in images}, {self.restored.pk, self.lost.pk})
        for img in images:
            url = img[key]
            self.assertNotIn('supabase', url, img['id'])
            self.assertTrue(url.split('?', 1)[0].endswith(_serve_path(img['id'])), url)

    def test_the_question_view_hands_out_the_image_endpoint(self):
        res = _client().get(f'/api/questions/{self.question.pk}/')
        self.assertEqual(res.status_code, 200)
        self._assert_endpoint_urls(res.data['images'])
        self._assert_endpoint_urls(res.data['stem_images'])

    def test_the_question_list_hands_out_the_image_endpoint(self):
        res = _client().get('/api/questions/', {'question_id': self.question.pk})
        self.assertEqual(res.status_code, 200)
        self._assert_endpoint_urls(res.data['results'][0]['images'])

    def test_the_admin_image_rows_hand_out_the_image_endpoint(self):
        res = _client(self.admin).get('/api/questions/images/', {'question': self.question.pk})
        self.assertEqual(res.status_code, 200)
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        self._assert_endpoint_urls([r for r in rows if r['question'] == self.question.pk], key='serve_url')

    def test_the_endpoint_serves_the_restored_copy_and_never_redirects_to_the_retired_host(self):
        ok = _client().get(_serve_path(self.restored.pk))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok['Content-Type'], 'image/png')
        ok.close()
        lost = _client().get(_serve_path(self.lost.pk))
        self.assertEqual(lost.status_code, 404)
        self.assertEqual(lost.data['code'], 'image_missing')
        self.assertFalse(lost.has_header('Location'))

    @override_settings(SUPABASE_STORAGE_MIRROR_DIR='')
    def test_without_a_restored_copy_nothing_points_at_the_retired_host(self):
        payload = serialize_image_for_student(self.restored, revealed=True, prefer_stored_url=True)
        self.assertEqual(payload['url'], _serve_path(self.restored.pk))
        lost = _client().get(_serve_path(self.restored.pk))
        self.assertEqual(lost.status_code, 404)
        self.assertFalse(lost.has_header('Location'))
        # A figure on another live host keeps its address and its redirect.
        live = QuestionImage.objects.create(question=self.question, page_number=0, image_index_in_page=5,
                                            role='illustration', url='https://cdn.example.test/fig.png')
        self.assertEqual(serialize_image_for_student(live, revealed=True, prefer_stored_url=True)['url'],
                         'https://cdn.example.test/fig.png')
        redirect = _client().get(_serve_path(live.pk))
        self.assertEqual((redirect.status_code, redirect['Location']), (302, 'https://cdn.example.test/fig.png'))

    def test_the_health_report_finds_every_figure_the_server_cannot_serve(self):
        on_disk = QuestionImage.objects.create(
            question=self.question, page_number=0, image_index_in_page=2, role='illustration',
            file=SimpleUploadedFile('upload.png', _png('red'), content_type='image/png'))
        Path(_MEDIA, 'recall_images').mkdir(parents=True, exist_ok=True)
        Path(_MEDIA, 'recall_images', 'here.png').write_bytes(_png('blue'))
        media_ok = QuestionImage.objects.create(question=self.question, page_number=1, image_index_in_page=0,
                                                url='/media/recall_images/here.png')
        media_lost = QuestionImage.objects.create(question=self.question, page_number=1, image_index_in_page=1,
                                                  url='/media/recall_images/gone.png')
        external = QuestionImage.objects.create(question=self.question, page_number=1, image_index_in_page=2,
                                                url='https://cdn.example.test/elsewhere.png')
        nothing = QuestionImage.objects.create(question=self.question, page_number=1, image_index_in_page=3)
        inactive = Question.objects.create(question_text='Hidden', option_a='a', option_b='b', option_c='c',
                                           option_d='d', correct_answer='A', year=2025,
                                           subject=self.question.subject, is_active=False)
        QuestionImage.objects.create(question=inactive, page_number=0, url='/media/recall_images/none.png')

        self.assertEqual([figure_source(img) for img in (on_disk, media_ok, self.restored, external, nothing)],
                         ['file', 'media', 'retired_storage', 'external', 'none'])
        report = image_health_report()
        self.assertEqual(report['total'], 7)
        self.assertEqual(report['missing'], 3)               # lost (storage), gone.png (media), nothing
        self.assertEqual(report['servable'], 3)               # upload, here.png, restored
        self.assertEqual(report['external_unchecked'], 1)
        self.assertEqual(report['questions_with_missing_figures'], 1)
        self.assertTrue(report['mirror_configured'])
        self.assertEqual(report['by_source']['retired_storage'], {'total': 2, 'missing': 1})
        self.assertEqual({row['image_id'] for row in report['missing_sample']},
                         {self.lost.pk, media_lost.pk, nothing.pk})
        self.assertEqual(len(image_health_report(sample_limit=1)['missing_sample']), 1)

    def test_the_health_endpoint_is_for_admins_only(self):
        self.assertIn(_client().get('/api/questions/images/health/').status_code, (401, 403))
        self.assertEqual(_client(self.student).get('/api/questions/images/health/').status_code, 403)
        res = _client(self.admin).get('/api/questions/images/health/', {'limit': 'x'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['missing'], 1)
        self.assertEqual(res.data['missing_sample'], [
            {'image_id': self.lost.pk, 'question_id': self.question.pk, 'source': 'retired_storage'}])

    def test_the_health_command_prints_counts_and_ids_only(self):
        out = io.StringIO()
        call_command('image_health', stdout=out)
        text = out.getvalue()
        self.assertIn('figures: 2 | servable: 1 | missing: 1', text)
        self.assertIn(f'missing: image {self.lost.pk} (question {self.question.pk}, retired_storage)', text)
        self.assertNotIn('Given below', text)
