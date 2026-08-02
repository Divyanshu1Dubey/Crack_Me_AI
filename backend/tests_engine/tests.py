"""Tests for tests_engine — focused on the freemium `is_free_preview` flag.

The flag is the missing backend hook for Task 4 of the freemium conversion
layer. Free users may only start tests where `is_free_preview=True`; premium
users and admins can start any test. Task 7 will wire the actual 403
response in the start view; this file only asserts the model defaults +
admin toggle work as documented.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from tests_engine.models import Test


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
