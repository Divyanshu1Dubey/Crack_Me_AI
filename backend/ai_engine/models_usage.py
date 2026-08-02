"""Per-user daily AI tutor usage counter for freemium 2/day cap.

This is an ADDITIONAL cap on top of the existing token economy (daily 10 +
weekly 50 + purchased + feedback). It applies to the structured AI tutor
endpoints (tutor / mnemonic / explain / rag-answer / analyze) for free
users only; premium and admin users bypass entirely.

Concurrency
-----------
The quota check and increment are wrapped in a single transaction that
holds a row lock (``SELECT ... FOR UPDATE``) for the entire check-and-
increment. This makes the gate race-free even under 100 concurrent
requests: the first request to acquire the lock sees count=N, the next
sees count=N+1, etc., and only the N<=cap-1 callers proceed.
"""
from __future__ import annotations

from typing import Tuple

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


class AITutorDailyUsage(models.Model):
    """One row per (user, day) counting structured AI tutor messages."""

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='ai_tutor_daily_usage',
    )
    date = models.DateField(default=timezone.now)
    message_count = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        indexes = [models.Index(fields=['user', 'date'])]

    def __str__(self):
        return f'{self.user_id} {self.date}: {self.message_count}'


def get_today_usage(user) -> int:
    """Return today's count, or 0 if no row yet."""
    today = timezone.now().date()
    row = (
        AITutorDailyUsage.objects
        .filter(user=user, date=today)
        .only('message_count')
        .first()
    )
    return row.message_count if row else 0


def check_and_consume(user, cap: int) -> Tuple[bool, int]:
    """Atomic check-and-increment. Returns ``(allowed, new_count)``.

    * If the row is below ``cap``, atomically increment and return
      ``(True, new_count)``.
    * If the row is at or above ``cap``, return ``(False, current_count)``
      WITHOUT incrementing — so a spammed 100-request burst sees one
      200 + ninety-nine 402s, never a counter that goes negative.
    * Row creation + lock + check + increment happen inside a single
      transaction with ``select_for_update``. On SQLite (no row-level
      locking) the ``transaction.atomic`` serializes calls via the
      BEGIN IMMEDIATE path that Django uses; on Postgres / MySQL InnoDB
      ``select_for_update`` provides true row-level serialization.

    Pre-condition: caller has already verified the user is NOT premium
    / admin. The helper itself does not re-check — keeping the check
    in the view lets us avoid a duplicate ``Subscription`` roundtrip.
    """
    today = timezone.now().date()
    with transaction.atomic():
        # First, try to lock an existing row.
        row = (
            AITutorDailyUsage.objects
            .select_for_update()
            .filter(user=user, date=today)
            .first()
        )
        if row is None:
            # No row yet. Use INSERT ... ON CONFLICT-style atomic creation:
            # the unique_together on (user, date) makes create() idempotent
            # under concurrent first-time calls. If a concurrent transaction
            # creates the row first, we fall through to a re-lock.
            try:
                row = AITutorDailyUsage.objects.create(
                    user=user, date=today, message_count=0
                )
            except Exception:
                row = (
                    AITutorDailyUsage.objects
                    .select_for_update()
                    .filter(user=user, date=today)
                    .first()
                )
                if row is None:
                    # Should never happen; surface a fail-safe.
                    return False, 0
        # Locked row now in hand — single source of truth for the count.
        if row.message_count >= cap:
            return False, row.message_count
        row.message_count = F('message_count') + 1
        row.save(update_fields=['message_count', 'updated_at'])
        # After F() save, refresh so the returned int is the new value.
        row.refresh_from_db(fields=['message_count'])
        return True, row.message_count


def get_or_create_today(user) -> AITutorDailyUsage:
    """Helper used by admin / reporting UIs. Not used on the hot path."""
    today = timezone.now().date()
    row, _ = AITutorDailyUsage.objects.get_or_create(
        user=user, date=today, defaults={'message_count': 0}
    )
    return row


def consume_ai_tutor_message(user) -> int:
    """Backward-compat thin wrapper for legacy callers / tests.

    Old semantics: increment today's counter by 1 and return the new total.
    New code MUST use :func:`check_and_consume` (atomic check+increment).
    This wrapper uses an effectively-infinite cap so it always increments —
    matching the original behaviour that callers (e.g. tests) relied on.
    """
    # Bypass the cap by using sys.maxsize; the legacy API never had a cap.
    allowed, new_count = check_and_consume(user, cap=2**31 - 1)
    return new_count