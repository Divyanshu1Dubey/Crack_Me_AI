"""Explanation figures behind the public image endpoint need a signed token.

``GET /api/questions/images/<id>/serve/`` is AllowAny (an ``<img>`` cannot
send the Authorization header) and image ids are sequential, so a free or
anonymous caller could download the explanation figures of locked and
scholarship questions by counting up from a stem image id. Stem figures stay
public; an explanation figure (runtime role 'explanation') is served only
with a valid token for its id -- carried by payloads built for a viewer
entitled to the answer (questions.image_access) -- or to a caller whose own
credentials make it entitled.

No network call is made.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import time
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import Subscription
from accounts.models_freemium import FreeShowcaseQuestion
from questions import image_access
from questions.models import Question, QuestionImage, Subject

User = get_user_model()
_MEDIA_ROOT = tempfile.mkdtemp(prefix='img-token-tests-')


def tearDownModule():
    shutil.rmtree(_MEDIA_ROOT, ignore_errors=True)


def _png():
    buf = io.BytesIO()
    Image.new('RGB', (40, 20), color='green').save(buf, format='PNG')
    return SimpleUploadedFile('figure.png', buf.getvalue(), content_type='image/png')


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _serve_path(image_id):
    return f'/api/questions/images/{image_id}/serve/'


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class ExplanationFigureTokenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Image Token Subject', code='IMGTOK')

        def question(i, **extra):
            return Question.objects.create(
                question_text=f'Image token stem {i}', option_a='alpha', option_b='beta',
                option_c='gamma', option_d='delta', correct_answer='C', year=2024, subject=subject,
                explanation=f'Gamma is right ({i}).', **extra,
            )

        def image(q, role, index):
            return QuestionImage.objects.create(
                question=q, page_number=0, image_index_in_page=index, role=role,
                file=_png(), mime='image/png', width=40, height=20,
            )

        cls.locked = question(1)
        cls.showcase = question(2)
        cls.scholarship = question(3, is_scholarship_eligible=True)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2024, position=0)
        # A scholarship question is never free content, showcase or not.
        FreeShowcaseQuestion.objects.create(question=cls.scholarship, year=2024, position=1)

        cls.stem = image(cls.locked, 'primary', 0)
        cls.figure = image(cls.locked, 'explanation', 1)
        # Stored as an illustration but referenced only from the
        # explanation: an explanation figure at runtime.
        cls.legacy = image(cls.locked, 'illustration', 2)
        cls.locked.explanation = f'Gamma is right. [[img:{cls.legacy.pk}]]'
        cls.locked.save(update_fields=['explanation'])
        cls.showcase_figure = image(cls.showcase, 'explanation', 0)
        cls.scholarship_figure = image(cls.scholarship, 'explanation', 0)

        cls.free = User.objects.create_user(
            username='imgtok-free', email='imgtok-free@example.com', password='unused-pw-1')
        cls.premium = User.objects.create_user(
            username='imgtok-premium', email='imgtok-premium@example.com', password='unused-pw-2')
        Subscription.objects.create(user=cls.premium, plan='1_year', status='active',
                                    expires_at=timezone.now() + timedelta(days=365))
        cls.admin = User.objects.create_superuser(
            username='imgtok-admin', email='imgtok-admin@example.com', password='unused-pw-3')

    def setUp(self):
        cache.clear()

    # ── helpers ────────────────────────────────────────────────────────────

    def _status(self, url, user=None):
        res = _client(user).get(url)
        try:
            return res.status_code
        finally:
            res.close()

    def _list_row(self, user, question):
        res = _client(user).get('/api/questions/', {'question_id': question.pk})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['results']), 1)
        return res.data['results'][0]

    def _assert_signed_and_working(self, images, ids, key='url'):
        by_id = {img['id']: img for img in images}
        for image_id in ids:
            url = by_id[image_id][key]
            self.assertIn('?t=', url, image_id)
            # No credentials: the token alone opens it (an <img> request).
            self.assertEqual(self._status(url), 200, url)

    def _assert_no_token(self, images, key='url'):
        for img in images:
            self.assertNotIn('t=', img.get(key) or '', img['id'])

    # ── the serve endpoint ─────────────────────────────────────────────────

    def test_stem_figures_stay_public(self):
        for user in (None, self.free):
            self.assertEqual(self._status(_serve_path(self.stem.pk), user), 200)

    def test_serving_a_figure_reads_one_row(self):
        # The role check reads the question's text with the image row (no
        # deferred-field loads on every inline image).
        token = image_access.image_access_token(self.figure.pk)
        for url in (_serve_path(self.stem.pk), f'{_serve_path(self.figure.pk)}?t={token}'):
            with self.assertNumQueries(1):
                self.assertEqual(self._status(url), 200, url)

    def test_explanation_figures_need_a_token(self):
        for user in (None, self.free):
            for image in (self.figure, self.legacy, self.scholarship_figure):
                res = _client(user).get(_serve_path(image.pk))
                self.assertEqual(res.status_code, 403, (user, image.pk))
                self.assertEqual(res.data['code'], 'image_token_required')

    def test_only_a_current_token_for_that_image_opens_it(self):
        path = _serve_path(self.figure.pk)
        good = image_access.image_access_token(self.figure.pk)
        other_image = image_access.image_access_token(self.showcase_figure.pk)
        # Signed with the site key but another salt (any other signed value).
        other_salt = signing.TimestampSigner().sign(str(self.figure.pk)).split(':', 1)[1]
        for bad in ('', 'garbage', 'a:b', 'a:b:c', other_image, other_salt, good + 'x', good[:-1]):
            self.assertEqual(self._status(f'{path}?t={bad}'), 403, bad)
        self.assertEqual(self._status(f'{path}?t={good}'), 200)
        self.assertEqual(self._status(f'{path}?t={good}&w=10'), 200)

    def test_tokens_expire_after_their_ttl(self):
        ttl = image_access.token_ttl_seconds()
        path = _serve_path(self.figure.pk)
        now = time.time()
        with mock.patch('time.time', return_value=now - ttl - 2 * 3600):
            stale = image_access.image_access_token(self.figure.pk)
        with mock.patch('time.time', return_value=now - ttl + 120):
            recent = image_access.image_access_token(self.figure.pk)
        self.assertEqual(self._status(f'{path}?t={stale}'), 403)
        # Issued just under a TTL ago (the hour rounding makes its timestamp
        # older still): still accepted.
        self.assertEqual(self._status(f'{path}?t={recent}'), 200)

    @override_settings(SUPABASE_STORAGE_MIRROR_DIR='')
    def test_a_storage_hosted_figure_is_not_redirected_to_without_a_token(self):
        # A figure stored at a public URL on another live host is served by a
        # redirect; the redirect itself would hand out that URL. (Retired
        # Supabase Storage URLs are never redirected to: see
        # test_retired_storage_images.)
        storage_url = 'https://cdn.example.test/question_images/1/0123456789abcdef.png'
        hosted = QuestionImage.objects.create(
            question=self.locked, page_number=0, image_index_in_page=3, role='explanation',
            url=storage_url, uploaded_by_admin=True,
        )
        res = _client(self.free).get(_serve_path(hosted.pk))
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.has_header('Location'))
        token = image_access.image_access_token(hosted.pk)
        res = _client().get(f'{_serve_path(hosted.pk)}?t={token}')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res['Location'], storage_url)

    def test_entitled_credentials_open_a_figure_without_a_token(self):
        path = _serve_path(self.figure.pk)
        self.assertEqual(self._status(path, self.premium), 200)
        self.assertEqual(self._status(path, self.admin), 200)
        self.assertEqual(self._status(path, self.free), 403)
        # A free showcase question's figure is free content.
        self.assertEqual(self._status(_serve_path(self.showcase_figure.pk)), 200)
        self.assertEqual(self._status(_serve_path(self.scholarship_figure.pk), self.free), 403)

    # ── payloads ───────────────────────────────────────────────────────────

    def test_entitled_payloads_carry_working_tokens(self):
        figures = (self.figure.pk, self.legacy.pk)
        for user in (self.premium, self.admin):
            row = self._list_row(user, self.locked)
            self._assert_signed_and_working(row['images'], figures)
            self._assert_no_token([img for img in row['images'] if img['id'] == self.stem.pk])

            detail = _client(user).get(f'/api/questions/{self.locked.pk}/')
            self.assertEqual(detail.status_code, 200)
            self._assert_signed_and_working(detail.data['images'], figures)
            self._assert_no_token(detail.data['stem_images'])

            gallery = _client(user).get(f'/api/questions/{self.locked.pk}/images/')
            self.assertEqual(gallery.status_code, 200)
            self._assert_signed_and_working(gallery.data, figures, key='file_url')
            self._assert_no_token([r for r in gallery.data if r['id'] == self.stem.pk], key='file_url')

    def test_a_free_showcase_figure_is_signed_for_every_viewer(self):
        for user in (None, self.free):
            row = self._list_row(user, self.showcase)
            self._assert_signed_and_working(row['images'], (self.showcase_figure.pk,))
            detail = _client(user).get(f'/api/questions/{self.showcase.pk}/')
            self.assertEqual(detail.status_code, 200)
            self._assert_signed_and_working(detail.data['images'], (self.showcase_figure.pk,))

    def test_locked_and_scholarship_payloads_carry_no_token(self):
        hidden = {self.figure.pk, self.legacy.pk, self.scholarship_figure.pk}
        for user in (None, self.free):
            for question in (self.locked, self.scholarship):
                row = self._list_row(user, question)
                self.assertFalse({img['id'] for img in row['images']} & hidden, (user, question.pk))
                self._assert_no_token(row['images'])
            gallery = _client(user).get(f'/api/questions/{self.locked.pk}/images/')
            self.assertEqual([r['id'] for r in gallery.data], [self.stem.pk])
            self._assert_no_token(gallery.data, key='file_url')
        anonymous = _client().get(f'/api/questions/{self.locked.pk}/')
        self.assertTrue(anonymous.data['answer_locked'])
        self.assertEqual([img['id'] for img in anonymous.data['images']], [self.stem.pk])
        self._assert_no_token(anonymous.data['images'])

    def test_admin_image_rows_carry_a_signed_serve_url(self):
        res = _client(self.admin).get('/api/questions/images/')
        self.assertEqual(res.status_code, 200)
        rows = res.data['results'] if isinstance(res.data, dict) else res.data
        self._assert_signed_and_working(rows, (self.figure.pk, self.legacy.pk), key='serve_url')


class ImageAccessHelperTests(SimpleTestCase):
    def test_only_serve_endpoint_urls_are_signed(self):
        public = 'https://abc.supabase.co/storage/v1/object/public/question_images/7/ab.png'
        self.assertFalse(image_access.is_image_serve_url(public))
        self.assertEqual(image_access.with_image_token(public, 7), public)
        self.assertEqual(image_access.with_image_token('', 7), '')
        self.assertTrue(image_access.is_image_serve_url('http://testserver/api/questions/images/7/serve/'))
        signed = image_access.with_image_token('/api/questions/images/7/serve/?w=10', 7)
        self.assertTrue(signed.startswith('/api/questions/images/7/serve/?w=10&t='), signed)
        token = signed.split('&t=', 1)[1]
        self.assertTrue(image_access.image_token_is_valid(7, token))
        self.assertFalse(image_access.image_token_is_valid(8, token))
        self.assertFalse(image_access.image_token_is_valid(7, None))

    def test_one_url_per_image_per_hour(self):
        hour = 1_800_000_000 - 1_800_000_000 % 3600
        with mock.patch('time.time', return_value=hour + 5):
            first = image_access.image_access_token(7)
        with mock.patch('time.time', return_value=hour + 3500):
            same_hour = image_access.image_access_token(7)
        with mock.patch('time.time', return_value=hour + 3605):
            next_hour = image_access.image_access_token(7)
        self.assertEqual(first, same_hour)
        self.assertNotEqual(first, next_hour)
