"""Figures staged after the container started serve on their first request (2026-11-07).

Live symptom: the 126 figures of the July 2026 material imports (``QuestionImage.url`` =
``/media/imported/...``) showed "Figure could not be loaded" in production. The upload script
(scripts/railway/upload_media_to_db.py --only-referenced) never staged ``/media/`` addresses held in
``QuestionImage.url``, and a staged file reached the volume only at the next container start. Now the
script stages them, and the image endpoint writes a staged file (questions.media_restore) the first time
it is asked for, after the same checks as ``manage.py restore_media_transfer``. No network call.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image
from rest_framework.test import APIClient

from questions import media_restore
from questions.models import Question, QuestionImage, Subject

_TMP = tempfile.mkdtemp(prefix='media-restore-tests-')
_MEDIA = str(Path(_TMP) / 'media')
_MIRROR = str(Path(_TMP) / 'mirror')
_STORAGE = 'https://ryuvcdthjnxyetdyjbph.supabase.co/storage/v1/object/public/'


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _png(color='green'):
    buf = io.BytesIO()
    Image.new('RGB', (30, 20), color=color).save(buf, format='PNG')
    return buf.getvalue()


def _serve(image_id):
    return APIClient().get(f'/api/questions/images/{image_id}/serve/')


def _load_upload_script():
    path = Path(settings.BASE_DIR).parent / 'scripts' / 'railway' / 'upload_media_to_db.py'
    spec = importlib.util.spec_from_file_location('upload_media_to_db_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@override_settings(MEDIA_ROOT=_MEDIA, SUPABASE_STORAGE_MIRROR_DIR=_MIRROR)
class LazyRestoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Media Restore Subject', code='MEDRES')
        cls.question = Question.objects.create(
            question_text='Which of the following statements are correct?', option_a='1 only',
            option_b='2 only', option_c='Both', option_d='Neither', correct_answer='C', year=2024,
            subject=subject,
        )

    def setUp(self):
        cache.clear()
        media_restore._misses.clear()
        blob = 'bytea' if connection.vendor == 'postgresql' else 'blob'
        with connection.cursor() as cur:
            cur.execute(f'CREATE TABLE {media_restore.TABLE} (id integer PRIMARY KEY, target varchar(10) NOT NULL, '
                        f'rel_path text NOT NULL, sha256 varchar(64) NOT NULL, size bigint NOT NULL, '
                        f'data {blob} NOT NULL, UNIQUE (target, rel_path))')
        self._next_id = 1

    def tearDown(self):
        media_restore._misses.clear()

    def _stage(self, target, rel_path, data, sha=None):
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO {media_restore.TABLE} (id, target, rel_path, sha256, size, data) '
                        'VALUES (%s, %s, %s, %s, %s, %s)',
                        [self._next_id, target, rel_path, sha or hashlib.sha256(data).hexdigest(), len(data), data])
        self._next_id += 1

    def _figure(self, index, **fields):
        return QuestionImage.objects.create(question=self.question, page_number=0, image_index_in_page=index,
                                            role='illustration', mime='image/png', **fields)

    def _assert_png(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        response.close()

    def test_a_staged_media_address_is_written_and_served_on_first_request(self):
        rel = 'imported/batch_0701/chylo-ct.png'
        data = _png('blue')
        self._stage('media', rel, data)
        figure = self._figure(0, url=f'/media/{rel}')
        self.assertFalse(Path(_MEDIA, rel).exists())
        self._assert_png(_serve(figure.pk))
        self.assertEqual(Path(_MEDIA, rel).read_bytes(), data)
        # Next request reads the disk, not the table.
        with CaptureQueriesContext(connection) as queries:
            self._assert_png(_serve(figure.pk))
        self.assertFalse(any(media_restore.TABLE in q['sql'] for q in queries.captured_queries))

    def test_a_stored_file_missing_on_disk_is_written_from_the_table(self):
        rel = 'question_images/2026/07/missing-upload.png'
        self._stage('media', rel, _png('red'))
        figure = self._figure(1, file=rel)
        self._assert_png(_serve(figure.pk))
        self.assertTrue(Path(_MEDIA, rel).is_file())

    def test_a_stored_file_nothing_staged_still_answers_503(self):
        figure = self._figure(2, file='question_images/2026/07/never-staged.png')
        res = _serve(figure.pk)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data['error'], 'image file missing on server')

    def test_a_storage_address_is_restored_into_the_mirror(self):
        rel = 'crack-cms-question-images/question_images/77/cccc3333.png'
        self._stage('mirror', rel, _png('yellow'))
        figure = self._figure(3, url=_STORAGE + rel)
        self._assert_png(_serve(figure.pk))
        self.assertTrue(Path(_MIRROR, rel).is_file())

    def test_a_checksum_mismatch_is_never_written(self):
        rel = 'imported/batch_0701/corrupt.png'
        self._stage('media', rel, _png(), sha='0' * 64)
        figure = self._figure(4, url=f'/media/{rel}')
        self.assertEqual(_serve(figure.pk).status_code, 404)
        self.assertFalse(Path(_MEDIA, rel).exists())

    def test_a_miss_is_remembered_and_never_escapes_the_media_root(self):
        figure = self._figure(5, url='/media/imported/batch_0701/not-staged.png')
        self.assertEqual(_serve(figure.pk).status_code, 404)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(_serve(figure.pk).status_code, 404)
        self.assertFalse(any(media_restore.TABLE in q['sql'] for q in queries.captured_queries))
        # A staged row cannot write outside its root.
        self._stage('media', '../outside.png', _png())
        self.assertIsNone(media_restore.restore_staged_file('media', '../outside.png'))
        self.assertFalse(Path(_TMP, 'outside.png').exists())
        self.assertIsNone(media_restore.restore_staged_file('media', 'C:/outside.png'))

    @override_settings(SUPABASE_STORAGE_MIRROR_DIR='')
    def test_without_a_mirror_a_storage_address_stays_image_missing(self):
        rel = 'crack-cms-question-images/question_images/77/dddd4444.png'
        self._stage('mirror', rel, _png())
        figure = self._figure(6, url=_STORAGE + rel)
        res = _serve(figure.pk)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data['code'], 'image_missing')


class NoStagingTableTests(TestCase):
    def setUp(self):
        media_restore._misses.clear()

    def test_no_table_means_no_file(self):
        with override_settings(MEDIA_ROOT=_MEDIA):
            self.assertIsNone(media_restore.restore_staged_file('media', 'imported/batch_0701/x.png'))
            self.assertIsNone(media_restore.restore_staged_file('elsewhere', 'x.png'))


class UploadScriptTests(SimpleTestCase):
    """--only-referenced stages QuestionImage.url /media/ addresses (the July 2026 imports were missed)."""

    class _Conn:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, sql, *args):
            for marker, rows in self.rows.items():
                if marker in sql:
                    return iter(rows)
            return iter([])

    def test_referenced_includes_media_addresses_and_honours_the_prefix(self):
        script = _load_upload_script()
        self.assertEqual(script.media_rel('/media/imported/batch_1/a.png?v=2'), 'imported/batch_1/a.png')
        # Own dir: Django runs this SimpleTestCase after the module's TestCases (and tearDownModule).
        media = Path(tempfile.mkdtemp(prefix='upload-media-tests-'))
        self.addCleanup(shutil.rmtree, media, True)
        for rel in ('imported/batch_1/a.png', 'recall_images/b.png', 'imported/batch_2/c.png'):
            Path(media, rel).parent.mkdir(parents=True, exist_ok=True)
            Path(media, rel).write_bytes(b'x')
        conn = self._Conn({
            "SELECT file FROM questions_questionimage": [('recall_images/b.png',)],
            "SELECT url FROM questions_questionimage WHERE url LIKE '/media/": [
                ('/media/imported/batch_1/a.png',), ('/media/imported/batch_2/c.png?v=1',),
                ('/media/imported/batch_9/absent.png',)],
        })
        plan, missing = script.referenced(conn, media, None)
        self.assertEqual([rel for _, rel, _ in plan],
                         ['imported/batch_1/a.png', 'imported/batch_2/c.png', 'recall_images/b.png'])
        self.assertEqual(missing, 1)
        plan, missing = script.referenced(conn, media, None, ['imported/'])
        self.assertEqual([rel for _, rel, _ in plan], ['imported/batch_1/a.png', 'imported/batch_2/c.png'])
        self.assertEqual(missing, 1)
