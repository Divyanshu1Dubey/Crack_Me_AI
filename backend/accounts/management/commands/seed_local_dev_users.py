"""Create/refresh the local test accounts used for local development and E2E.

DEBUG-only. The shared password is read from the LOCAL_SEED_PASSWORD env
var (generated into backend/.env.localdev by scripts/local/make_env_localdev.py)
and is never printed.

Accounts (all on the reserved .test TLD, so no real mail can be sent):
  student@local.test  free student
  premium@local.test  student with an active 1-year (unlimited AI) plan
  admin@local.test    admin (role=admin, is_staff)
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

ACCOUNTS = (
    ('local_student', 'student@local.test', 'Local', 'Student', 'student'),
    ('local_premium', 'premium@local.test', 'Local', 'Premium', 'premium'),
    ('local_admin', 'admin@local.test', 'Local', 'Admin', 'admin'),
)


class Command(BaseCommand):
    help = 'Seed local development test accounts (DEBUG only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Refusing to seed local test accounts with DEBUG off.')
        password = os.getenv('LOCAL_SEED_PASSWORD', '').strip()
        if len(password) < 12:
            raise CommandError('Set LOCAL_SEED_PASSWORD (>=12 chars) in backend/.env.localdev.')

        from accounts.models import CustomUser, Subscription, TokenBalance

        for username, email, first, last, kind in ACCOUNTS:
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={'username': username, 'first_name': first, 'last_name': last},
            )
            user.username = username
            user.first_name, user.last_name = first, last
            user.is_active = True
            user.role = 'admin' if kind == 'admin' else 'student'
            user.is_staff = kind == 'admin'
            user.is_superuser = False
            user.set_password(password)
            # Django-native sign-in (AUTH_PROVIDER=django) requires a verified email.
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
            user.save()
            TokenBalance.objects.get_or_create(user=user)

            if kind == 'premium':
                Subscription.objects.filter(user=user, status='active').update(status='cancelled')
                Subscription.objects.create(
                    user=user, plan='1_year', plan_display_name='1 Year Unlimited (local seed)',
                    amount_paid=0, status='active', starts_at=timezone.now(),
                    expires_at=timezone.now() + timedelta(days=365),
                )
                CustomUser.objects.filter(pk=user.pk).update(is_subscribed=True)
            self.stdout.write(f"{'created' if created else 'updated'} {email} ({kind})")
