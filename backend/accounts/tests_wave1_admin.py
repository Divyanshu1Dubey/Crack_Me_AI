"""Wave 1 regression tests: admin tools and profile writes (G4-auth-accounts).

ACC-16           system actions require an explicit scope
ACC-14 / PERF-01 admin token overview / user list: fixed query count, no writes on GET
ACC-11 / SEC-01 / CFG-15  backup / restore really run, fail loudly, never truncate
ACC-13           profile bonus paid once; profile PATCH writes only edited fields
ACC-20           the reminder schedule points at a callable that runs the command
ACC-21           upload_validation detects DOCX / PPTX / XLSX / legacy Office correctly
"""
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import TokenBalance, TokenTransaction

User = get_user_model()


def _admin(username='ops'):
    return User.objects.create_user(
        username=username, email=f'{username}@local.test', password='x-Long-passw0rd',
        role='admin', is_superuser=True, is_staff=True,
    )


class SystemActionScopeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(_admin())
        from analytics.models import DailyActivity
        self.student = User.objects.create_user(username='s1', email='s1@local.test', password='x-Long-passw0rd')
        DailyActivity.objects.create(user=self.student, date=timezone.localdate(), questions_attempted=3)

    def test_missing_or_unknown_scope_is_rejected_and_deletes_nothing(self):
        from analytics.models import DailyActivity
        for path in ('reset-attempts', 'clear-analytics', 'rerun-evaluation'):
            for payload in ({}, {'user_id': self.student.id}, {'scope': 'everyone'}, {'scope': ['all']}):
                r = self.client.post(f'/api/auth/admin/system/{path}/', payload, format='json')
                self.assertEqual(r.status_code, 400, (path, payload))
        self.assertEqual(DailyActivity.objects.count(), 1)

    def test_explicit_scopes_still_work(self):
        from analytics.models import DailyActivity
        r = self.client.post('/api/auth/admin/system/clear-analytics/', {'scope': 'user'}, format='json')
        self.assertEqual(r.status_code, 400)  # user scope needs user_id
        r = self.client.post('/api/auth/admin/system/clear-analytics/', {'scope': 'user', 'user_id': self.student.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(DailyActivity.objects.count(), 0)
        self.assertEqual(self.client.post('/api/auth/admin/system/rerun-evaluation/', {'scope': 'all'}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/admin/system/reset-attempts/', {'scope': 'ALL'}, format='json').status_code, 200)


class AdminTokenListTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(_admin())

    def _make_users(self, n, start=0):
        yesterday = timezone.localdate() - timedelta(days=1)
        for i in range(start, start + n):
            u = User.objects.create_user(username=f'u{i}', email=f'u{i}@local.test', password='x')
            TokenBalance.objects.update_or_create(user=u, defaults={
                'purchased_tokens': 5, 'feedback_credits': 1,
                'daily_tokens_used': 7, 'weekly_tokens_used': 7,
                # Stale daily counter: the old code reset it with an UPDATE inside the GET.
                'last_daily_reset': yesterday, 'last_weekly_reset': timezone.localdate(),
            })

    def _get(self, url):
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        writes = [q['sql'] for q in ctx.captured_queries if q['sql'].lstrip().upper().startswith('UPDATE "ACCOUNTS_TOKENBALANCE"')]
        return r, len(ctx.captured_queries), writes

    def test_overview_query_count_does_not_grow_and_nothing_is_written(self):
        from accounts.models import TokenConfig
        TokenConfig.get_config()  # the singleton row exists in any real database
        self._make_users(3)
        r1, q1, writes = self._get('/api/auth/tokens/admin/users/')
        self.assertEqual(writes, [])
        self._make_users(12, start=3)
        r2, q2, writes = self._get('/api/auth/tokens/admin/users/')
        self.assertEqual(writes, [])
        self.assertEqual(q1, q2)
        self.assertEqual(r2.data['count'], 15)
        row = next(u for u in r2.data['users'] if u['username'] == 'u0')
        # Stale daily counter counts as reset: 10 free + 5 purchased + 1 credit.
        self.assertEqual(row['available'], 16)
        self.assertEqual(r2.data['platform_stats']['total_available_tokens'], 15 * 16)
        self.assertEqual(r2.data['platform_stats']['total_purchased_tokens'], 15 * 5)

    def test_overview_pagination(self):
        self._make_users(5)
        r = self.client.get('/api/auth/tokens/admin/users/', {'limit': 2, 'offset': 1})
        self.assertEqual((r.data['count'], r.data['limit'], r.data['offset'], len(r.data['users'])), (5, 2, 1, 2))
        self.assertEqual(self.client.get('/api/auth/tokens/admin/users/', {'limit': 'x'}).status_code, 400)

    def test_user_lifecycle_list_does_not_write(self):
        self._make_users(4)
        r, _, writes = self._get('/api/auth/admin/users/?limit=50')
        self.assertEqual(writes, [])
        row = next(u for u in r.data['results'] if u['username'] == 'u1')
        self.assertEqual(row['available_tokens'], 16)


class CoreDataBackupTests(TestCase):
    def setUp(self):
        cache.clear()
        from questions.models import ExamTrack, Subject, Topic
        track, _ = ExamTrack.objects.get_or_create(code='cms-bk', defaults={'name': 'CMS backup'})
        subject = Subject.objects.create(name='Backup Subject', code='bk-sub', exam_track=track)
        Topic.objects.create(name='Backup Topic', subject=subject)
        self.tmpdir = tempfile.mkdtemp(prefix='g4-backup-')
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.path = os.path.join(self.tmpdir, 'core.json')
        env = mock.patch.dict('os.environ', {'CORE_DATA_BACKUP_PATH': self.path})
        env.start()
        self.addCleanup(env.stop)
        self.client = APIClient()
        self.client.force_authenticate(_admin())

    def test_commands_are_discoverable_and_write_a_real_fixture(self):
        out = io.StringIO()
        call_command('backup_core_data', stdout=out)
        with open(self.path, encoding='utf-8') as fh:
            data = json.load(fh)
        models = {obj['model'] for obj in data}
        self.assertTrue({'questions.examtrack', 'questions.subject', 'questions.topic'} <= models)
        call_command('restore_core_data', stdout=io.StringIO())

    def test_admin_backup_then_restore(self):
        r = self.client.post('/api/auth/admin/system/backup-data/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertGreaterEqual(r.data['records'], 3)
        from questions.models import Topic
        Topic.objects.filter(name='Backup Topic').update(name='Changed')
        r = self.client.post('/api/auth/admin/system/restore-data/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(Topic.objects.filter(name='Backup Topic').exists())

    def test_restore_without_a_backup_fails_loudly(self):
        r = self.client.post('/api/auth/admin/system/restore-data/')
        self.assertEqual(r.status_code, 500)
        self.assertIn('No backup file', r.data['error'])
        with self.assertRaises(CommandError):
            call_command('restore_core_data', stdout=io.StringIO())

    def test_failed_backup_keeps_the_previous_file(self):
        with open(self.path, 'w', encoding='utf-8') as fh:
            fh.write('[{"model": "questions.examtrack", "pk": 1, "fields": {}}]')
        with mock.patch('accounts.core_data_backup.call_command', side_effect=RuntimeError('dump failed')):
            r = self.client.post('/api/auth/admin/system/backup-data/')
        self.assertEqual(r.status_code, 500)
        with open(self.path, encoding='utf-8') as fh:
            self.assertIn('questions.examtrack', fh.read())
        self.assertEqual([f for f in os.listdir(self.tmpdir) if f != 'core.json'], [])  # temp file cleaned up

    def test_restore_refuses_unexpected_models(self):
        with open(self.path, 'w', encoding='utf-8') as fh:
            json.dump([{'model': 'accounts.customuser', 'pk': 999, 'fields': {'username': 'x'}}], fh)
        r = self.client.post('/api/auth/admin/system/restore-data/')
        self.assertEqual(r.status_code, 500)
        self.assertFalse(User.objects.filter(pk=999).exists())


class ProfileWriteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='prof', email='prof@local.test', password='x-Long-passw0rd')
        self.stale = User.objects.get(pk=self.user.pk)  # snapshot taken "at request start"
        self.client = APIClient()
        self.client.force_authenticate(self.stale)

    def test_bonus_is_not_paid_twice_from_a_stale_snapshot(self):
        r = self.client.patch('/api/auth/profile/', {'phone': '9876543210', 'college': 'AIIMS'}, format='json')
        self.assertEqual(r.status_code, 200)
        # A parallel request whose user snapshot still says profile_bonus_rewarded=False.
        racing_user = User.objects.get(pk=self.user.pk)
        racing_user.profile_bonus_rewarded = False
        racer = APIClient()
        racer.force_authenticate(racing_user)
        self.assertEqual(racer.patch('/api/auth/profile/', {'phone': '9876543210', 'college': 'AIIMS'}, format='json').status_code, 200)
        balance = TokenBalance.objects.get(user=self.user)
        self.assertEqual(balance.feedback_credits, 10)
        self.assertEqual(TokenTransaction.objects.filter(user=self.user, transaction_type='feedback_reward').count(), 1)

    def test_profile_patch_does_not_overwrite_concurrent_changes(self):
        # A webhook / admin action changes the row after this request loaded it.
        User.objects.filter(pk=self.user.pk).update(is_subscribed=True, is_active=False)
        r = self.client.patch('/api/auth/profile/', {'first_name': 'Edited'}, format='json')
        self.assertEqual(r.status_code, 200)
        fresh = User.objects.get(pk=self.user.pk)
        self.assertEqual(fresh.first_name, 'Edited')
        self.assertTrue(fresh.is_subscribed)
        self.assertFalse(fresh.is_active)


class ReminderScheduleTests(TestCase):
    def test_scheduled_func_is_a_callable_that_runs_the_command(self):
        from importlib import import_module

        from accounts.management.commands import send_subscription_reminders as mod

        with mock.patch.object(mod, 'logger'):
            with mock.patch('django_q.models.Schedule.objects.update_or_create') as upsert:
                mod.schedule_subscription_reminders()
        func_path = upsert.call_args.kwargs['defaults']['func']
        module_path, _, attr = func_path.rpartition('.')
        func = getattr(import_module(module_path), attr)
        with mock.patch('django.core.management.call_command') as cc:
            func()
        cc.assert_called_once_with('send_subscription_reminders', days='7,3,1')


def _office_zip(directory, name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr(f'{directory}document.xml', '<x/>')
    return SimpleUploadedFile(name, buf.getvalue())


class UploadValidationTests(TestCase):
    def test_ooxml_subtypes(self):
        from accounts.upload_validation import validate_uploaded_file

        self.assertTrue(validate_uploaded_file(_office_zip('word/', 'a.docx'), {'document'}).endswith('wordprocessingml.document'))
        self.assertTrue(validate_uploaded_file(_office_zip('ppt/', 'a.pptx'), {'presentation'}).endswith('presentationml.presentation'))
        self.assertTrue(validate_uploaded_file(_office_zip('xl/', 'a.xlsx'), {'spreadsheet'}).endswith('spreadsheetml.sheet'))
        # A PPTX is not accepted where only documents are allowed.
        with self.assertRaises(ValidationError):
            validate_uploaded_file(_office_zip('ppt/', 'a.docx'), {'document'})

    def test_plain_zip_and_renamed_html_are_rejected(self):
        from accounts.upload_validation import validate_uploaded_file

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('payload.txt', 'x')
        with self.assertRaises(ValidationError):
            validate_uploaded_file(SimpleUploadedFile('a.docx', buf.getvalue()), {'document'})
        with self.assertRaises(ValidationError):
            validate_uploaded_file(SimpleUploadedFile('a.jpg', b'<html><script>x</script></html>'), {'image'})

    def test_legacy_office_by_extension_and_images(self):
        from accounts.upload_validation import validate_uploaded_file

        ole = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 64
        self.assertEqual(validate_uploaded_file(SimpleUploadedFile('a.doc', ole), {'document'}), 'application/msword')
        self.assertEqual(validate_uploaded_file(SimpleUploadedFile('a.ppt', ole), {'presentation'}), 'application/vnd.ms-powerpoint')
        png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
        upload = SimpleUploadedFile('a.png', png)
        self.assertEqual(validate_uploaded_file(upload, {'image'}), 'image/png')
        self.assertEqual(upload.read(8), png[:8])  # file position restored
