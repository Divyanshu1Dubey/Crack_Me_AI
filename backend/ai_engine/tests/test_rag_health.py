"""verify_rag_index / GET /api/ai/knowledge/health/ (ported from feat/ai-production-unification)."""
import os
import sqlite3
import tempfile
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from ai_engine.rag_health import LFS_POINTER_PREFIX, rag_store_health

User = get_user_model()


def _tmp(suffix='.sqlite3'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


class RagStoreHealthTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {'DISABLE_RAG': '', 'DISABLE_RAG_IN_PRODUCTION': ''})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _store(self, rows):
        path = _tmp()
        self.addCleanup(os.unlink, path)
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE chunks (id TEXT PRIMARY KEY, document TEXT, book TEXT)')
        conn.execute('CREATE TABLE idf_cache (term TEXT PRIMARY KEY, idf REAL)')
        conn.executemany('INSERT INTO chunks VALUES (?, ?, ?)', rows)
        conn.execute("INSERT INTO idf_cache VALUES ('heart', 1.5)")
        conn.commit()
        conn.close()
        return path

    def test_healthy(self):
        report = rag_store_health(self._store([('a', 'x', 'Harrison'), ('b', 'y', 'Park'), ('c', 'z', 'Park')]))
        self.assertEqual(report['status'], 'healthy')
        self.assertEqual((report['total_chunks'], report['books'], report['idf_terms']), (3, 2, 1))
        self.assertEqual(report['integrity'], 'ok')

    def test_empty(self):
        self.assertEqual(rag_store_health(self._store([]))['status'], 'empty')

    def test_missing(self):
        self.assertEqual(rag_store_health(os.path.join(tempfile.gettempdir(), 'no_such_store.sqlite3'))['status'],
                         'missing')

    def test_lfs_pointer(self):
        path = _tmp()
        self.addCleanup(os.unlink, path)
        with open(path, 'wb') as fh:
            fh.write(LFS_POINTER_PREFIX + b'\noid sha256:abc\nsize 123\n')
        self.assertEqual(rag_store_health(path)['status'], 'lfs_pointer')

    def test_corrupt(self):
        path = _tmp()
        self.addCleanup(os.unlink, path)
        with open(path, 'wb') as fh:
            fh.write(b'this is not a sqlite database' * 100)
        self.assertEqual(rag_store_health(path)['status'], 'corrupt')

    def test_disabled_makes_missing_store_expected(self):
        with mock.patch.dict(os.environ, {'DISABLE_RAG': '1'}):
            self.assertEqual(rag_store_health(os.path.join(tempfile.gettempdir(), 'no_such.sqlite3'))['status'],
                             'disabled')

    def test_command_exit_codes(self):
        out = StringIO()
        call_command('verify_rag_index', '--check', '--path', self._store([('a', 'x', 'B')]), stdout=out)
        self.assertIn('HEALTHY', out.getvalue())
        with self.assertRaises(SystemExit) as ctx:
            call_command('verify_rag_index', '--check', '--path', self._store([]), stdout=StringIO())
        self.assertEqual(ctx.exception.code, 2)


class KnowledgeHealthEndpointTests(TestCase):
    url = '/api/ai/knowledge/health/'

    def test_anonymous_refused(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_student_refused(self):
        student = User.objects.create_user(username='stud_rag', email='s@example.com', password='Pass-12345!')
        self.client.force_login(student)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_admin_gets_report_without_server_path(self):
        admin = User.objects.create_user(username='adm_rag', email='a@example.com', password='Pass-12345!',
                                         is_staff=True, is_superuser=True, role='admin')
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.json())
        self.assertNotIn('path', response.json())
