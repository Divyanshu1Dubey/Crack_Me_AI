"""The jobs board shows only listings an admin checked against the official notification and approved
(jobs.official_sources): official links, a recent verification, still open. Nothing is fetched or generated."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from jobs.models import Job
from jobs.official_sources import official_url
from jobs.testing import OFFICIAL_APPLY_LINK, OFFICIAL_SOURCE_URL, published_job

User = get_user_model()


def _ids(resp):
    data = resp.json()
    rows = data if isinstance(data, list) else data.get('results', [])
    return {row['id'] for row in rows}


class OfficialUrlTests(SimpleTestCase):

    def test_official_recruitment_sites(self):
        for url in ('https://upsc.gov.in/examinations/active-exams', 'https://www.aiimsexams.ac.in/info/x.html',
                    'https://aiims.edu/index.php/en/notices', 'http://rpsc.rajasthan.gov.in/', 'https://esic.nic.in/',
                    'https://natboard.edu.in/viewnbenews', 'https://www.icmr.res.in/', 'https://careerindianairforce.cdac.in'):
            self.assertTrue(official_url(url), url)

    def test_anything_else_is_refused(self):
        for url in ('https://example.com/apply', 'https://gov.in.evil.example/x', 'https://evilgov.in/', 'ftp://upsc.gov.in/',
                    'javascript:alert(1)', '', None, 'https://aiims.edu.fake.example/'):
            self.assertFalse(official_url(url), url)

    @override_settings(JOBS_EXTRA_OFFICIAL_DOMAINS=['cghs.example'])
    def test_extra_domains_from_settings(self):
        self.assertTrue(official_url('https://portal.cghs.example/jobs'))


class VerifiedBoardTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='jobs-admin', password='x', is_staff=True, is_superuser=True)
        self.student = User.objects.create_user(username='jobs-student', password='x')

    def _draft(self, **kw):
        kw.setdefault('apply_link', OFFICIAL_APPLY_LINK)
        return Job.objects.create(title='Junior Resident', hospital='AIIMS New Delhi', location='New Delhi',
                                  description='Non-academic JR posts', **kw)

    def test_students_see_only_approved_recently_verified_open_listings(self):
        shown = published_job(title='Shown', hospital='H', location='L', description='d')
        draft = self._draft()
        rejected = published_job(title='Rejected', hospital='H', location='L', description='d', status='rejected')
        stale = published_job(title='Stale', hospital='H', location='L', description='d',
                              last_verified_at=timezone.now() - timedelta(days=60))
        closed = published_job(title='Closed', hospital='H', location='L', description='d',
                               expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(_ids(self.client.get('/api/jobs/')), {shown.id})
        self.assertEqual(self.client.get(f'/api/jobs/{draft.id}/').status_code, 404)
        self.client.force_authenticate(self.student)
        self.assertEqual(_ids(self.client.get('/api/jobs/')), {shown.id})
        self.assertEqual(self.client.post(f'/api/jobs/{draft.id}/bookmark/').status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(_ids(self.client.get('/api/jobs/')), {shown.id, draft.id, rejected.id, stale.id, closed.id})

    def test_a_student_payload_shows_the_verification_but_not_the_admin_note(self):
        job = published_job(title='Shown', hospital='H', location='L', description='d', review_note='internal')
        row = self.client.get(f'/api/jobs/{job.id}/').json()
        self.assertEqual(row['source_url'], OFFICIAL_SOURCE_URL)
        self.assertTrue(row['last_verified_at'])
        self.assertNotIn('review_note', row)
        self.assertNotIn('verified_by', row)

    def test_verify_and_publish_needs_official_links(self):
        job = self._draft(apply_link='https://example.com/apply')
        self.client.force_authenticate(self.admin)
        refused = self.client.post(f'/api/jobs/{job.id}/verify/', {'source_url': OFFICIAL_SOURCE_URL, 'approve': True},
                                   format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('apply link', ' '.join(refused.json()['status']))

        job = self._draft()
        no_source = self.client.post(f'/api/jobs/{job.id}/verify/', {'approve': True}, format='json')
        self.assertEqual(no_source.status_code, 400)

        ok = self.client.post(f'/api/jobs/{job.id}/verify/', {'source_url': OFFICIAL_SOURCE_URL, 'approve': True},
                              format='json')
        self.assertEqual(ok.status_code, 200, ok.content)
        job.refresh_from_db()
        self.assertEqual((job.status, job.source_url, job.verified_by_id), ('approved', OFFICIAL_SOURCE_URL,
                                                                            self.admin.id))
        self.assertIsNotNone(job.last_verified_at)
        self.client.force_authenticate(None)
        self.assertIn(job.id, _ids(self.client.get('/api/jobs/')))

    def test_approving_by_patch_needs_a_verification_and_students_cannot_verify(self):
        job = self._draft(source_url=OFFICIAL_SOURCE_URL)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f'/api/jobs/{job.id}/verify/', {}, format='json').status_code, 403)
        self.client.force_authenticate(self.admin)
        refused = self.client.patch(f'/api/jobs/{job.id}/', {'status': 'approved'}, format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Verify', ' '.join(refused.json()['status']))
        typed = self.client.patch(f'/api/jobs/{job.id}/', {'last_verified_at': timezone.now().isoformat()},
                                  format='json')
        self.assertEqual(typed.status_code, 200)
        job.refresh_from_db()
        self.assertIsNone(job.last_verified_at)  # read-only: only the verify action records a check

    def test_an_approved_listing_cannot_be_pointed_at_another_site(self):
        job = published_job(title='Shown', hospital='H', location='L', description='d')
        self.client.force_authenticate(self.admin)
        refused = self.client.patch(f'/api/jobs/{job.id}/', {'apply_link': 'https://example.com/apply'}, format='json')
        self.assertEqual(refused.status_code, 400)

    def test_reject_takes_a_listing_off_the_board(self):
        job = published_job(title='Shown', hospital='H', location='L', description='d')
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'/api/jobs/{job.id}/reject/', {'note': 'notification withdrawn'}, format='json')
        self.assertEqual(r.status_code, 200)
        job.refresh_from_db()
        self.assertEqual((job.status, job.review_note), ('rejected', 'notification withdrawn'))
        self.client.force_authenticate(None)
        self.assertNotIn(job.id, _ids(self.client.get('/api/jobs/')))
