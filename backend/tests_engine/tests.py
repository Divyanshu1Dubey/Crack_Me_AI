"""Tests for tests_engine — focused on the freemium `is_free_preview` flag.

The flag is the missing backend hook for Task 4 of the freemium conversion
layer. Free users may only start tests where `is_free_preview=True`; premium
users and admins can start any test. Task 7 wires the actual 403 response
in the start view; this file asserts the model defaults + admin toggle +
the start gate behaviour.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from tests_engine.models import Test
from tests_engine.views import TestViewSet


User = get_user_model()


class TestIsFreePreviewFieldTests(TestCase):
    """Smoke tests for the boolean field added in migration 0006."""

    def test_default_is_false(self):
        """Newly created tests default to non-preview (locked for free users)."""
        test = Test.objects.create(title='Default preview test', test_type='mixed')
        self.assertFalse(test.is_free_preview)
        self.assertEqual(test.is_free_preview, False)

    def test_admin_can_mark_preview(self):
        """Admins can flip the flag on individual tests."""
        test = Test.objects.create(title='Free preview', test_type='mixed')
        test.is_free_preview = True
        test.save()
        test.refresh_from_db()
        self.assertTrue(test.is_free_preview)

    def test_queryset_filter_by_preview(self):
        """`.filter(is_free_preview=True)` returns only the curated subset."""
        Test.objects.create(title='Locked', test_type='mixed')
        Test.objects.create(title='Locked 2', test_type='mixed')
        free = Test.objects.create(title='Free 1', test_type='mixed')
        free.is_free_preview = True
        free.save()
        free2 = Test.objects.create(title='Free 2', test_type='mixed')
        free2.is_free_preview = True
        free2.save()

        previews = list(Test.objects.filter(is_free_preview=True).order_by('title'))
        self.assertEqual([t.title for t in previews], ['Free 1', 'Free 2'])
        self.assertEqual(Test.objects.filter(is_free_preview=False).count(), 2)

    def test_preview_flag_is_persisted_across_reload(self):
        """Survives a fresh DB fetch (sanity check on db_index + column)."""
        test = Test.objects.create(title='Persist', test_type='mixed')
        test.is_free_preview = True
        test.save()

        from_db = Test.objects.get(pk=test.pk)
        self.assertTrue(from_db.is_free_preview)


class TestStartFreemiumGateTests(TestCase):
    """End-to-end: the `/api/tests/{id}/start/` endpoint must gate free users
    on non-preview tests with a 402 + `code: upgrade_required`. Premium and
    admin users always pass through.

    The gate is checked AFTER `self.get_object()` so a non-existent test id
    still returns 404 (and not 403).
    """

    @classmethod
    def setUpTestData(cls):
        cls.locked = Test.objects.create(title='Locked test', test_type='mixed')
        cls.preview = Test.objects.create(title='Free preview test', test_type='mixed', is_free_preview=True)

    def _user(self, *, is_admin=False, is_premium=False, suffix=''):
        user = User.objects.create(
            username=f'test-start-{int(is_admin)}-{int(is_premium)}-{suffix}',
            role='admin' if is_admin else 'student',
        )
        if is_premium:
            from accounts.models import Subscription
            from django.utils import timezone
            from datetime import timedelta
            Subscription.objects.create(
                user=user, plan='1_year', status='active',
                expires_at=timezone.now() + timedelta(days=365),
            )
        return user

    def _start(self, user, test_id):
        factory = APIRequestFactory()
        request = factory.post(f'/api/tests/{test_id}/start/', {}, format='json')
        force_authenticate(request, user=user)
        # Build a view instance with the right kwargs (mimics what the
        # router does for a detail route).
        view = TestViewSet()
        view.kwargs = {'pk': str(test_id)}
        view.action = 'start_attempt'
        view.request = request
        view.format_kwarg = None
        # Initialize the view set attributes DRF normally sets
        from rest_framework.request import Request
        drf_request = Request(request)
        view.request = drf_request
        view.headers = drf_request.headers
        # Use as_view to bind the action method
        bound_view = TestViewSet.as_view({'post': 'start_attempt'})
        return bound_view(request, pk=str(test_id))

    def test_free_user_locked_test_returns_402(self):
        """Free user + non-preview test → 402 upgrade_required."""
        free = self._user(suffix='locked')
        response = self._start(free, self.locked.id)
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.data.get('code'), 'upgrade_required')
        self.assertEqual(response.data.get('feature'), 'Mock Tests')

    def test_free_user_preview_test_passes(self):
        """Free user + preview test → 200, attempt_id returned."""
        free = self._user(suffix='preview')
        response = self._start(free, self.preview.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_premium_user_locked_test_passes(self):
        """Premium user can start any test, including non-preview."""
        premium = self._user(is_premium=True, suffix='premium')
        response = self._start(premium, self.locked.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_admin_user_locked_test_passes(self):
        """Admin bypasses the freemium gate."""
        admin = self._user(is_admin=True, suffix='admin')
        response = self._start(admin, self.locked.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attempt_id', response.data)

    def test_locked_test_does_not_create_attempt(self):
        """A blocked start call must NOT create a TestAttempt row."""
        free = self._user(suffix='noattempt')
        self._start(free, self.locked.id)
        self.assertEqual(
            self.locked.attempts.filter(user=free).count(), 0,
            'Blocked start must not create a TestAttempt',
        )
