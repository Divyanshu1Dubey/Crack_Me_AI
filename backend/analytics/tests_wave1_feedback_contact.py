"""Feedback, Contact Us and CSV export (PUB-13 / FE-STU-34 / AN-25).

Before: contact messages were only emailed (never stored) and the API said
"sent" even when delivery failed or no mail backend was configured; feedback
was unthrottled, emailed synchronously and listed unbounded; CSV exports
wrote student text that spreadsheets execute as formulas.
"""
import csv
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from analytics.models import ContactMessage, Feedback
from analytics.views import _deliver_contact_email

User = get_user_model()
CONTACT = '/api/analytics/contact/'
FEEDBACK = '/api/analytics/feedback/'
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


# The admin email goes out after commit (accounts.emails.run_in_background,
# synchronous under the in-memory mail backend), so requests run inside
# captureOnCommitCallbacks(execute=True).
@override_settings(EMAIL_BACKEND=LOCMEM)
class ContactUsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _post(self, **data):
        payload = {'name': 'Asha', 'email': 'asha@example.com', 'subject': 'USMLE waitlist', 'message': 'Hello'}
        payload.update(data)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(CONTACT, payload, format='json')

    def test_message_is_stored_and_emailed(self):
        r = self._post()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['stored'])
        msg = ContactMessage.objects.get()
        self.assertEqual((msg.email, msg.subject, msg.message), ('asha@example.com', 'USMLE waitlist', 'Hello'))
        self.assertTrue(msg.email_delivered)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('USMLE waitlist', mail.outbox[0].subject)

    def test_failed_email_is_not_reported_as_delivered(self):
        with mock.patch('analytics.views.send_mail', side_effect=OSError('smtp down')):
            r = self._post()
        self.assertEqual(r.status_code, 200, r.data)  # stored, so nothing is lost
        self.assertFalse(ContactMessage.objects.get().email_delivered)

    @override_settings(EMAIL_BACKEND=CONSOLE)
    def test_console_backend_counts_as_not_delivered(self):
        msg = ContactMessage.objects.create(name='Asha', email='asha@example.com', subject='s', message='m')
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            self.assertFalse(_deliver_contact_email(msg.pk, 'subject', 'body'))
        msg.refresh_from_db()
        self.assertFalse(msg.email_delivered)

    def test_error_when_neither_stored_nor_emailed(self):
        with mock.patch.object(ContactMessage.objects, 'create', side_effect=RuntimeError('db down')), \
                mock.patch('analytics.views.send_mail', side_effect=OSError('smtp down')):
            r = self._post()
        self.assertEqual(r.status_code, 503)
        self.assertIn('error', r.data)

    def test_email_required_and_validated(self):
        self.assertEqual(self._post(email='').status_code, 400)
        self.assertEqual(self._post(email='not-an-email').status_code, 400)
        self.assertEqual(self._post(message='   ').status_code, 400)
        self.assertEqual(self._post(message='x' * 5001).status_code, 400)
        self.assertFalse(ContactMessage.objects.exists())

    def test_signed_in_user_email_is_used_when_blank(self):
        user = User.objects.create_user(username='contact-u', email='contact-u@example.com', password='x')
        self.client.force_authenticate(user)
        r = self._post(email='')
        self.assertEqual(r.status_code, 200, r.data)
        msg = ContactMessage.objects.get()
        self.assertEqual((msg.email, msg.user_id), ('contact-u@example.com', user.id))


@override_settings(EMAIL_BACKEND=LOCMEM)
class FeedbackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = User.objects.create_user(username='fb-student', email='fb@example.com', password='x')
        self.admin = User.objects.create_user(username='fb-admin', email='fba@example.com', password='x', role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def _submit(self, i=0):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(FEEDBACK, {'category': 'bug', 'rating': 4, 'title': f'T{i}', 'message': 'M'},
                                    format='json')

    def test_submit_stores_and_notifies(self):
        r = self._submit()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_submissions_are_throttled(self):
        codes = [self._submit(i).status_code for i in range(11)]
        self.assertEqual(codes[:10], [201] * 10)
        self.assertEqual(codes[10], 429)
        # Reading is not throttled by the submit limit.
        self.assertEqual(self.client.get(FEEDBACK).status_code, 200)

    def test_list_is_paginated_and_scoped(self):
        other = User.objects.create_user(username='fb-other', password='x')
        for i in range(3):
            Feedback.objects.create(user=self.student, title=f'mine {i}', message='m')
        Feedback.objects.create(user=other, title='theirs', message='m')
        mine = self.client.get(FEEDBACK).data
        self.assertEqual(mine['count'], 3)
        self.assertTrue(all(row['username'] == 'fb-student' for row in mine['results']))

        admin = APIClient()
        admin.force_authenticate(self.admin)
        page = admin.get(FEEDBACK, {'page_size': 2}).data
        self.assertEqual((page['count'], len(page['results'])), (4, 2))
        self.assertEqual(admin.get(FEEDBACK, {'page': 'x'}).status_code, 400)

    def test_oversized_message_rejected(self):
        r = self.client.post(FEEDBACK, {'title': 't', 'message': 'x' * 5001}, format='json')
        self.assertEqual(r.status_code, 400)


class CSVExportTests(TestCase):
    def test_formula_cells_are_neutralised(self):
        student = User.objects.create_user(username='=HYPERLINK("http://evil")', email='e@example.com', password='x')
        Feedback.objects.create(user=student, title='=IMPORTXML("http://x","//a")', message='+1 cmd',
                                admin_reply='@SUM(A1)')
        admin = User.objects.create_user(username='csv-admin', password='x', role='admin')
        client = APIClient()
        client.force_authenticate(admin)
        r = client.get('/api/analytics/export/csv/', {'type': 'feedback'})
        self.assertEqual(r.status_code, 200)
        rows = list(csv.reader(io.StringIO(r.content.decode())))
        data = rows[1]
        self.assertEqual(data[0], '\'=HYPERLINK("http://evil")')
        self.assertEqual(data[3], '\'=IMPORTXML("http://x","//a")')
        self.assertEqual(data[4], "'+1 cmd")
        self.assertEqual(data[6], "'@SUM(A1)")
        self.assertEqual(data[2], '5')  # numbers are untouched

        users = list(csv.reader(io.StringIO(client.get('/api/analytics/export/csv/', {'type': 'users'}).content.decode())))
        self.assertIn('\'=HYPERLINK("http://evil")', [row[1] for row in users[1:]])

    def test_students_cannot_export(self):
        client = APIClient()
        client.force_authenticate(User.objects.create_user(username='csv-student', password='x'))
        self.assertEqual(client.get('/api/analytics/export/csv/', {'type': 'feedback'}).status_code, 403)
