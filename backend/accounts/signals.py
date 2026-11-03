"""Freemium post-migrate signal handlers — make deployment zero-touch.

After `manage.py migrate`, this module ensures that every year that has any
active ``Question`` rows has 10 ``FreeShowcaseQuestion`` rows. Existing rows
are preserved so admin curation is not overwritten. Missing slots are filled
by deterministic pick (lowest-id active question not already in the
showcase). Scholarship-challenge questions (``is_scholarship_eligible``) are
never picked: they are never free content (questions.views.free_showcase_rows
skips them), so a showcase row pointing at one only shows as locked. Existing
rows like that are reported with a warning so an admin can replace them.

(Free preview TESTS are no longer seeded: ``Test.is_free_preview`` is retired
and the test start gate ignores it -- AN-27.)

These guarantees run:
    * automatically after every ``migrate`` (post_migrate signal)
    * idempotently on fresh + existing + empty + rolled-back databases
    * never delete user-curated rows
    * never break tests (skip if 'test' in sys.argv OR no Question rows)

The companion ``seed_free_showcase`` management command remains for ops
who want to inspect / re-run with custom flags; production never needs it.

The same post_migrate hook also keeps the daily renewal-reminder schedule in
place (``renewal_reminders_post_migrate``, ACC-20).
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


def _running_tests() -> bool:
    """Skip auto-bootstrap during unit-test runs (in-memory DB has no data)."""
    argv = sys.argv if sys.argv else []
    return 'test' in argv or 'test_all' in argv or 'pytest' in argv


def _app_label(model) -> str:
    return model._meta.app_label


def ensure_showcase_for_year(year: int, per_year: int = SHOWCASE_PER_YEAR) -> int:
    """Fill missing FreeShowcaseQuestion slots for one year. Returns rows created.

    Safe to call inside a transaction. Existing rows are preserved.
    Scholarship-challenge questions are never added (see module docstring).
    """
    FreeShowcaseQuestion = apps.get_model('accounts', 'FreeShowcaseQuestion')
    Question = apps.get_model('questions', 'Question')

    locked_rows = list(
        FreeShowcaseQuestion.objects
        .filter(year=year, question__is_scholarship_eligible=True)
        .values_list('question_id', flat=True)
    )
    if locked_rows:
        logger.warning(
            'Free showcase %s holds scholarship-challenge question(s) %s; they are never shown '
            'as free. Replace them in Django admin (Free showcase questions).',
            year, sorted(locked_rows),
        )

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
        .filter(year=year, is_active=True, is_scholarship_eligible=False)
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


def ensure_freemium_seed():
    """Run the freemium auto-bootstrap (showcase per year). Idempotent and safe to re-run.

    Returns a summary dict for logging/metrics. Never raises.
    """
    if _running_tests():
        return {'skipped': 'test-run'}
    try:
        Question = apps.get_model('questions', 'Question')
        years = list(
            Question.objects.filter(is_active=True)
            .values_list('year', flat=True)
            .distinct()
        )
        showcase_created = 0
        for year in years:
            showcase_created += ensure_showcase_for_year(year)

        summary = {
            'showcase_created': showcase_created,
            'years_processed': len(years),
        }
        if showcase_created:
            logger.info('Freemium auto-seed: %s', summary)
        return summary
    except Exception as exc:  # noqa: BLE001 — must never block migrate
        logger.warning('Freemium auto-seed skipped (%s)', exc)
        return {'error': str(exc)}


@receiver(post_migrate)
def freemium_post_migrate(sender, **kwargs):
    """Seed the showcase once per ``migrate`` run.

    post_migrate is sent once per installed app, after ALL migrations of the
    run are applied, so running for sender = this app is enough (it used to
    re-run the whole seed, and now its warnings, for every app).
    """
    if getattr(sender, 'label', '') != 'accounts':
        return
    # Cheap early exit if the freemium models aren't installed yet.
    try:
        apps.get_model('accounts', 'FreeShowcaseQuestion')
        apps.get_model('questions', 'Question')
    except LookupError:
        return
    ensure_freemium_seed()


@receiver(post_migrate)
def renewal_reminders_post_migrate(sender, **kwargs):
    """Keep the daily renewal-reminder schedule in place (ACC-20).

    /subscription promises reminder emails 7, 3 and 1 day before a plan
    expires, but nothing ever created the django-q schedule, so none were
    sent. The release step runs ``migrate``, so this (idempotent
    update_or_create) runs on every deploy. The schedule fires while a
    ``qcluster`` worker runs (Procfile ``worker``). Once per migrate run
    (sender = this app), never during test runs.
    """
    if getattr(sender, 'label', '') != 'accounts' or _running_tests():
        return
    try:
        from accounts.management.commands.send_subscription_reminders import schedule_subscription_reminders

        schedule_subscription_reminders()
    except Exception as exc:  # noqa: BLE001 -- must never block migrate
        logger.warning('Renewal reminder schedule not created (%s)', exc)
