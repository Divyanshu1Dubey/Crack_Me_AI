"""Per-user daily AI tutor usage counter for freemium 2/day cap.

This is an ADDITIONAL cap on top of the existing token economy (daily 10 +
weekly 50 + purchased + feedback). It applies to the structured AI tutor
endpoints (tutor / mnemonic / explain / rag-answer / analyze) for free
users only; premium and admin users bypass entirely.
"""
from datetime import date

from django.db import models, transaction
from django.db.models import F


class AITutorDailyUsage(models.Model):
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='ai_tutor_daily_usage',
    )
    date = models.DateField(default=date.today)
    message_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        indexes = [models.Index(fields=['user', 'date'])]


def consume_ai_tutor_message(user) -> int:
    """Atomically increment today's counter and return the new total.

    Always uses select_for_update + transaction.atomic so concurrent
    requests can't double-count past the cap.
    """
    today = date.today()
    with transaction.atomic():
        row, _ = (
            AITutorDailyUsage.objects
            .select_for_update()
            .get_or_create(user=user, date=today, defaults={'message_count': 0})
        )
        AITutorDailyUsage.objects.filter(pk=row.pk).update(
            message_count=F('message_count') + 1
        )
        row.refresh_from_db(fields=['message_count'])
        return row.message_count


def get_today_usage(user) -> int:
    """Return today's count, or 0 if no row yet."""
    row = AITutorDailyUsage.objects.filter(user=user, date=date.today()).first()
    return row.message_count if row else 0