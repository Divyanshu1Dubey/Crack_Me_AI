"""Admin image uploads without Supabase Storage (Railway deployment, 2026-11): the bytes go to Django's
default storage under MEDIA_ROOT and the row is served like every recall image."""
import io
import os
import tempfile
from unittest import mock

from django.test import TestCase, override_settings

from questions.image_upload import supabase_storage_configured, upload_image_to_supabase
from questions.models import Question, QuestionImage, Subject

PNG_1PX = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
           b'\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82')
_MEDIA = tempfile.mkdtemp(prefix='upload-local-')


@override_settings(MEDIA_ROOT=_MEDIA)
class LocalStorageUploadTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Medicine', code='MED')
        self.q = Question.objects.create(
            question_text='Stem', option_a='a', option_b='b', option_c='c', option_d='d', correct_answer='A',
            year=2024, subject=subject, explanation='Because.')

    def _upload(self, role=None):
        with mock.patch.dict(os.environ, {'SUPABASE_URL': '', 'NEXT_PUBLIC_SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': ''}):
            self.assertFalse(supabase_storage_configured())
            return upload_image_to_supabase(file_obj=io.BytesIO(PNG_1PX), question_id=self.q.id, content_type='image/png',
                                            original_filename='fig.png', role=role)

    def test_stored_under_media_root_and_never_calls_supabase(self):
        with mock.patch('questions.image_upload._ensure_supabase_client') as client:
            up = self._upload()
        client.assert_not_called()
        row = QuestionImage.objects.get(pk=up.id)
        self.assertEqual(row.url, '')
        self.assertTrue(row.file.name)
        self.assertTrue(os.path.isfile(os.path.join(_MEDIA, row.file.name)))
        self.assertTrue(row.uploaded_by_admin)

    def test_same_bytes_reuse_the_row(self):
        first = self._upload()
        second = self._upload()
        self.assertEqual(first.id, second.id)
        self.assertEqual(QuestionImage.objects.filter(question=self.q).count(), 1)

    def test_explanation_role_appends_token(self):
        up = self._upload(role='explanation')
        self.q.refresh_from_db()
        self.assertIn(f'[[img:{up.id}]]', self.q.explanation)

    def test_supabase_configured_still_uses_supabase(self):
        env = {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SERVICE_ROLE_KEY': 'k'}
        with mock.patch.dict(os.environ, env), mock.patch('questions.image_upload._ensure_supabase_client') as client:
            client.return_value.storage.from_.return_value.get_public_url.return_value = 'https://example.supabase.co/x.png'
            up = upload_image_to_supabase(file_obj=io.BytesIO(PNG_1PX), question_id=self.q.id, content_type='image/png',
                                          original_filename='fig.png')
        client.assert_called_once()
        self.assertEqual(QuestionImage.objects.get(pk=up.id).url, 'https://example.supabase.co/x.png')
