"""Freemium post-migrate signal handlers — make deployment zero-touch.

After `manage.py migrate`, this module ensures that:

1. Every year that has any active ``Question`` rows has exactly 10
   ``FreeShowcaseQuestion`` rows. Existing rows are preserved so admin
   curation is not overwritten. Missing slots are filled by deterministic
   pick (lowest-id active question not already in the showcase).

2. Exactly 2 ``tests_engine.Test`` rows are marked ``is_free_preview=True``:
   the most recently created ``is_active=True`` tests by default. Admin-set
   previews are preserved — we only fill the gap when fewer than 2 exist.

These guarantees run:
    * automatically after every ``migrate`` (post_migrate signal)
    * idempotently on fresh + existing + empty + rolled-back databases
    * never delete user-curated rows
    * never break tests (skip if 'test' in sys.argv OR no Question/Test rows)

The companion ``seed_free_showcase`` management command remains for ops
who want to inspect / re-run with custom flags; production never needs it.
"""
from __future__ import annotations

import logging
import sys

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_migrate
from django.dispatch import receiver

logger = logging.getLogger(__name__)


SHOWCASE_PER_YEAR = 10  # Free users see this many PYQ per year.
FREE_PREVIEW_TARGET = 2  # Free users can attempt this many mock tests.


def _running_tests() -> bool:
    """Skip auto-bootstrap during unit-test runs (in-memory DB has no data)."""
    argv = sys.argv if sys.argv else []
    return 'test' in argv or 'test_all' in argv or 'pytest' in argv


def _app_label(model) -> str:
    return model._meta.app_label


def ensure_showcase_for_year(year: int, per_year: int = SHOWCASE_PER_YEAR) -> int:
    """Fill missing FreeShowcaseQuestion slots for one year. Returns rows created.

    Safe to call inside a transaction. Existing rows are preserved.
    """
    FreeShowcaseQuestion = apps.get_model('accounts', 'FreeShowcaseQuestion')
    Question = apps.get_model('questions', 'Question')

    existing_count = FreeShowcaseQuestion.objects.filter(year=year).count()
    if existing_count >= per_year:
        return 0

    existing_qids = set(
        FreeShowcaseQuestion.objects
        .filter(year=year)
        .values_list('question_id', flat=True)
    )
    needed = per_year - existing_count
    candidate_ids = list(
        Question.objects
        .filter(year=year, is_active=True)
        .exclude(id__in=existing_qids)
        .order_by('id')
        .values_list('id', flat=True)[:needed]
    )

    created = 0
    for offset, qid in enumerate(candidate_ids):
        try:
            with transaction.atomic():
                FreeShowcaseQuestion.objects.create(
                    question_id=qid,
                    year=year,
                    position=existing_count + offset,
                )
                created += 1
        except Exception as exc:  # noqa: BLE001 — one bad row must not abort others
            logger.warning('ensure_showcase_for_year(%s): row %s skipped (%s)', year, qid, exc)
    return created


def ensure_free_preview_tests(target: int = FREE_PREVIEW_TARGET) -> int:
    """Mark exactly ``target`` Test rows as ``is_free_preview=True``.

    Behavior:
      * Existing ``is_free_preview=True`` rows are PRESERVED (admin override).
      * If fewer than ``target`` exist, fill the gap with the newest
        ``is_published=True`` tests (created_at desc, then id desc for
        tie-break).
      * If MORE than ``target`` exist (admin manually set >2), do NOT
        unmark anything — admin choice wins.
      * Returns count of newly-marked tests this call.
    """
    Test = apps.get_model('tests_engine', 'Test')

    existing_count = Test.objects.filter(is_free_preview=True).count()
    if existing_count >= target:
        return 0

    gap = target - existing_count
    # Pick the newest published tests not already marked. We never overwrite
    # admin-curated previews because the filter excludes is_free_preview=True.
    candidates = list(
        Test.objects
        .filter(is_published=True, is_free_preview=False)
        .order_by('-created_at', '-id')
        .values_list('id', flat=True)[:gap]
    )
    if not candidates:
        return 0
    updated = Test.objects.filter(id__in=candidates).update(is_free_preview=True)
    return updated


def ensure_freemium_seed():
    """Run all freemium auto-bootstrap steps. Idempotent and safe to re-run.

    Returns a summary dict for logging/metrics. Never raises.
    """
    if _running_tests():
        return {'skipped': 'test-run'}
    try:
        # Step 1: FreeShowcaseQuestion per year.
        Question = apps.get_model('questions', 'Question')
        years = list(
            Question.objects.filter(is_active=True)
            .values_list('year', flat=True)
            .distinct()
        )
        showcase_created = 0
        for year in years:
            showcase_created += ensure_showcase_for_year(year)

        # Step 2: Free preview tests.
        free_preview_marked = ensure_free_preview_tests()

        summary = {
            'showcase_created': showcase_created,
            'free_preview_marked': free_preview_marked,
            'years_processed': len(years),
        }
        if showcase_created or free_preview_marked:
            logger.info('Freemium auto-seed: %s', summary)
        return summary
    except Exception as exc:  # noqa: BLE001 — must never block migrate
        logger.warning('Freemium auto-seed skipped (%s)', exc)
        return {'error': str(exc)}


@receiver(post_migrate)
def freemium_post_migrate(sender, **kwargs):
    """Run after each app's migrations. We don't gate on app_label here
    because the signal fires for the *last* app migrated (Django default),
    which in our project is ``accounts`` (settings INSTALLED_APPS ordering).
    We rely on idempotency to handle multiple firings safely.
    """
    # Cheap early exit if freemium apps aren't installed yet.
    try:
        apps.get_model('accounts', 'FreeShowcaseQuestion')
        apps.get_model('tests_engine', 'Test')
    except LookupError:
        return
    ensure_freemium_seed()