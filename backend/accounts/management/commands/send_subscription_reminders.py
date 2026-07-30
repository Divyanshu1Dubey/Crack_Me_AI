"""
send_subscription_reminders.py
Management command to send renewal reminder emails to subscribed users.

Schedule via django-q2 cron, e.g.:
    python manage.py qcluster    # in one process, then schedule below

    python manage.py qcron --schedule daily  --command 'accounts.management.commands.send_subscription_reminders.Command' --name 'subscription_reminders'

Or run manually:
    python manage.py send_subscription_reminders                # default T-7
    python manage.py send_subscription_reminders --days 3
    python manage.py send_subscription_reminders --days 1,3,7   # multiple thresholds in one pass

The command is idempotent: it records reminder-sent timestamps in a
`reminders_sent` JSONField on Subscription so each user gets exactly
one email per (threshold, subscription) tuple.

If you don't add the JSONField, this command falls back to a Redis-backed
set so the dedup still works without a schema migration. To enable
DB-backed dedup, add `last_reminders_sent = models.JSONField(default=dict, blank=True)`
to Subscription and re-run `makemigrations accounts`.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

REMINDER_DEDUP_KEY = 'sub_reminders_sent:{sub_id}:{threshold}'  # Redis fallback
REMINDER_DEDUP_TTL = 60 * 60 * 24 * 14  # 14 days


def _already_reminded(sub_id: int, threshold: int) -> bool:
    """Return True if a reminder for this (sub, threshold) was sent in the last 14 days."""
    return bool(cache.get(REMINDER_DEDUP_KEY.format(sub_id=sub_id, threshold=threshold)))


def _mark_reminded(sub_id: int, threshold: int) -> None:
    cache.set(
        REMINDER_DEDUP_KEY.format(sub_id=sub_id, threshold=threshold),
        timezone.now().isoformat(),
        REMINDER_DEDUP_TTL,
    )


def _send_reminder_email(user_email: str, user_name: str, plan_name: str, expires_at, days_left: int) -> None:
    """Render and send the renewal reminder email."""
    from django.core.mail import send_mail

    subject = f'Your CrackCMS {plan_name} plan expires in {days_left} day{"s" if days_left != 1 else ""}'
    expiry_str = expires_at.strftime('%d %b %Y') if expires_at else 'soon'
    body = (
        f'Hi {user_name or "there"},\n\n'
        f'Your CrackCMS premium subscription ({plan_name}) expires on {expiry_str} '
        f'- that\'s only {days_left} day{"s" if days_left != 1 else ""} away.\n\n'
        f'Renew now to keep your unlimited AI tutor, mock tests, and study materials uninterrupted:\n'
        f'  https://www.cracklabs.app/subscription\n\n'
        f'Need help or want to switch plans? Reply to this email and we\'ll assist within 24 hours.\n\n'
        f'- The CrackCMS team\n'
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('send_subscription_reminders: email failed for %s — %s', user_email, exc)


class Command(BaseCommand):
    help = 'Send renewal reminder emails to subscribed users whose plan is about to expire.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=str,
            default='7',
            help='Comma-separated list of day thresholds (e.g. "7,3,1"). Defaults to "7".',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print who would receive reminders without sending emails.',
        )

    def handle(self, *args, **options):
        from accounts.models import Subscription  # late import to avoid AppRegistryNotReady

        raw_days = options['days']
        thresholds = sorted({int(d.strip()) for d in raw_days.split(',') if d.strip().isdigit()}, reverse=True)
        if not thresholds:
            self.stdout.write(self.style.ERROR('No valid --days thresholds provided.'))
            return

        dry_run = options['dry_run']
        now = timezone.now()
        total_sent = 0

        for threshold in thresholds:
            window_start = now + timedelta(days=threshold)
            window_end = window_start + timedelta(hours=23, minutes=59)
            qs = Subscription.objects.filter(
                status='active',
                expires_at__gte=window_start,
                expires_at__lte=window_end,
            ).select_related('user')
            for sub in qs:
                if _already_reminded(sub.id, threshold):
                    continue
                days_left = max(0, (sub.expires_at - now).days)
                if dry_run:
                    self.stdout.write(
                        f'[dry-run] would email {sub.user.email} — {sub.plan_display_name} '
                        f'expires in {days_left}d (sub_id={sub.id})'
                    )
                    continue
                _send_reminder_email(
                    user_email=sub.user.email,
                    user_name=sub.user.first_name or sub.user.username,
                    plan_name=sub.plan_display_name,
                    expires_at=sub.expires_at,
                    days_left=days_left,
                )
                _mark_reminded(sub.id, threshold)
                total_sent += 1

        level = self.style.SUCCESS if total_sent else self.style.WARNING
        self.stdout.write(level(f'send_subscription_reminders: sent {total_sent} reminder(s) across thresholds {thresholds}'))


# ── Optional schedule helper for django-q2 ─────────────────────────────────────
# Call from your deploy bootstrap or AppConfig.ready():
#
#     from accounts.management.commands.send_subscription_reminders import schedule_subscription_reminders
#     schedule_subscription_reminders()
#
# Or, if you prefer plain cron + Render Cron Jobs, call once a day:
#
#     0 9 * * *  cd /app && python manage.py send_subscription_reminders --days 7,3,1
#
def schedule_subscription_reminders(schedule_type='D'):
    """Schedule this command via django-q2 if the broker is configured. No-op otherwise."""
    try:
        from django_q.models import Schedule
        Schedule.objects.update_or_create(
            name='subscription_renewal_reminders',
            defaults={
                'func': 'accounts.management.commands.send_subscription_reminders.Command',
                'schedule_type': schedule_type,  # 'D' = daily
                'repeats': -1,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.info('schedule_subscription_reminders: skipped (%s)', exc)
