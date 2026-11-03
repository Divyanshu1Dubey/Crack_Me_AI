"""
accounts/models.py — User model and Token System models.
Contains: CustomUser (AbstractUser with medical exam fields),
TokenBalance (per-user AI token balance with daily/weekly tracking),
TokenConfig (singleton global config for limits and pricing),
TokenTransaction (audit log for all token purchases and consumption),
Subscription (declared plan features + Razorpay + admin-grant lifecycles).
"""
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
from questions.models import ExamTrack


# ─── PLAN FEATURES (single source of truth for what each plan grants) ─────
# Plan code → display name, duration, marketing price (INR), unlimited AI flag,
# monthly token grant (None = unlimited tokens on top of free daily/weekly).
#
# Marketing copy on /subscription MUST stay in sync with this table — both
# frontend cards (subscription/page.tsx) and the backend SubscribeOrderView
# price lookups reference these values via PLAN_PRICES below.
PLAN_FEATURES = {
    '1_month': {
        'display_name': '1 Month Pass',
        'duration': timedelta(days=30),
        'price_inr': Decimal('129.00'),
        'unlimited_ai': False,
        'monthly_tokens': 100,  # explicit top-up each cycle, on top of free daily/weekly
    },
    '3_months': {
        'display_name': '3 Months Pass',
        'duration': timedelta(days=90),
        'price_inr': Decimal('449.00'),
        'unlimited_ai': False,
        'monthly_tokens': 300,
    },
    '1_year': {
        'display_name': '1 Year Unlimited',
        'duration': timedelta(days=365),
        'price_inr': Decimal('1999.00'),
        'unlimited_ai': True,  # 100% unlimited AI — bypasses token metering entirely
        'monthly_tokens': None,
    },
    'scholarship_1_month': {
        'display_name': 'Scholarship 1 Month',
        'duration': timedelta(days=30),
        'price_inr': None,  # dynamic — set per user via scholarship_granted_price
        'unlimited_ai': False,
        'monthly_tokens': 100,
    },
    'legacy': {
        'display_name': 'Legacy Early Bird (Lifetime)',
        'duration': None,
        'price_inr': Decimal('199.00'),
        'unlimited_ai': True,
        'monthly_tokens': None,
    },
    'admin_grant': {
        'display_name': 'Admin Granted',
        'duration': None,
        'price_inr': Decimal('0.00'),
        'unlimited_ai': True,
        'monthly_tokens': None,
    },
}
PLAN_PRICES = {
    '1_month': 12900,           # paise
    '3_months': 44900,
    '1_year': 199900,
    'scholarship_1_month': 0,   # computed dynamically per user
    'legacy': 19900,
}

# Cached GET /auth/subscribe/status/ payload (accounts.views.SubscriptionStatusView).
SUBSCRIPTION_STATUS_CACHE_KEY = 'sub_status:{user_id}'


def invalidate_subscription_status_cache(user_id) -> None:
    """Drop the cached subscription status after any subscription change."""
    from django.core.cache import cache

    try:
        cache.delete(SUBSCRIPTION_STATUS_CACHE_KEY.format(user_id=user_id))
    except Exception:  # pragma: no cover - cache outages must not break payments
        pass


class CustomUser(AbstractUser):
    """Extended user model for CMS aspirants."""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    # Supabase Auth user id (the token's `sub` / `id` from /auth/v1/user).
    # Once stored, sign-ins are matched by this id, never by email again; see
    # accounts.supabase_rest_auth.SupabaseJWTAuthentication._upsert_local_user.
    supabase_uid = models.CharField(
        max_length=64, unique=True, null=True, blank=True, default=None,
        help_text='Supabase Auth user id linked to this account (set on first sign-in).',
    )
    # When this account proved it owns its email address: the Supabase import
    # (email_confirmed_at), an emailed verification link, a completed password
    # reset or a Google sign-up. Django-native sign-in (AUTH_PROVIDER=django,
    # accounts.native_auth) requires it.
    email_verified_at = models.DateTimeField(
        null=True, blank=True, default=None,
        help_text='When the email address was verified (native sign-in requires it).',
    )
    phone = models.CharField(max_length=15, blank=True)
    college = models.CharField(max_length=200, blank=True, default='')
    session_key = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Unused legacy field. Sessions are not limited to one device; '
                  'devices are tracked in UserDevice (2 free / 4 subscribed).',
    )
    profile_bonus_rewarded = models.BooleanField(default=False)
    is_subscribed = models.BooleanField(default=False)
    target_exam = models.CharField(max_length=50, default='UPSC CMS')
    active_exam_track = models.ForeignKey(ExamTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    target_year = models.IntegerField(null=True, blank=True)
    avatar_url = models.URLField(blank=True)
    current_session_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Unused legacy field (see session_key); devices live in UserDevice.',
    )
    scholarship_test_passed = models.BooleanField(default=False)
    scholarship_test_attempts = models.IntegerField(default=0)
    # Question set issued for the current scholarship attempt,
    # {"n": <attempt number>, "q": [<question ids>]}: every start of that
    # attempt re-issues the same set (accounts.views.ScholarshipStartView);
    # cleared when the attempt is submitted.
    scholarship_challenge = models.JSONField(
        null=True, blank=True, default=None,
        help_text='Question set issued for the current scholarship attempt (kept until it is submitted).',
    )
    last_seen = models.DateTimeField(null=True, blank=True)
    scholarship_granted_price = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_admin(self):
        """Check if user is an admin (no token restrictions)."""
        return self.role == 'admin' or self.is_superuser


class TokenBalance(models.Model):
    """
    Tracks AI token usage per user.
    
    Each AI call costs 1 token. Students get free daily/weekly tokens.
    Admins are exempt from token limits (checked via user.is_admin).
    
    Token Config (change in TokenConfig model or settings):
    - FREE_DAILY_TOKENS: Free tokens per day (default: 10)
    - FREE_WEEKLY_TOKENS: Free tokens per week (default: 50)
    - Purchased tokens never expire.
    - Feedback reward: +2 tokens for correct feedback reports.
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='token_balance')
    purchased_tokens = models.IntegerField(default=50, help_text='Tokens bought by user (never expire)')
    daily_tokens_used = models.IntegerField(default=0, help_text='Free tokens used today')
    weekly_tokens_used = models.IntegerField(default=0, help_text='Free tokens used this week')
    total_tokens_used = models.IntegerField(default=0, help_text='Lifetime tokens consumed')
    last_daily_reset = models.DateField(default=timezone.now, help_text='Last date daily counter was reset')
    last_weekly_reset = models.DateField(default=timezone.now, help_text='Last date weekly counter was reset')
    feedback_credits = models.IntegerField(default=0, help_text='Tokens earned from accepted feedback')
    # High-water marks used by refund_token to restore purchased tokens /
    # feedback credits when an AI call fails after consuming a token. We
    # can't peek into consume_token()'s source-of-truth after the fact, so
    # we track the maximum purchased/feedback pool we've ever seen and
    # refund the difference between that and the current balance. If a
    # user has spent 3 of 5 purchased tokens (max=5, current=2) and gets
    # a refund of 1, refund_token can restore purchased back to 3.
    purchased_tokens_max = models.IntegerField(
        default=50,
        help_text='High-water mark of purchased tokens — used by refund_token.',
    )
    feedback_credits_max = models.IntegerField(
        default=0,
        help_text='High-water mark of feedback credits — used by refund_token.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Token Balance'
        verbose_name_plural = 'Token Balances'

    def __str__(self):
        return f"{self.user.username}: {self.available_tokens} tokens available"

    def _reset_if_needed(self):
        """Reset daily/weekly counters if the period has elapsed."""
        today = timezone.localdate()
        changed = False
        last_daily_reset = self.last_daily_reset.date() if hasattr(self.last_daily_reset, 'date') else self.last_daily_reset
        last_weekly_reset = self.last_weekly_reset.date() if hasattr(self.last_weekly_reset, 'date') else self.last_weekly_reset
        if last_daily_reset < today:
            self.daily_tokens_used = 0
            self.last_daily_reset = today
            changed = True
        # Reset weekly on Monday
        week_start = today - timedelta(days=today.weekday())
        if last_weekly_reset < week_start:
            self.weekly_tokens_used = 0
            self.last_weekly_reset = week_start
            changed = True
        if changed:
            self.save(update_fields=['daily_tokens_used', 'weekly_tokens_used',
                                     'last_daily_reset', 'last_weekly_reset'])

    @property
    def available_tokens(self):
        """
        Total tokens available to the user right now.
        = remaining free daily + remaining free weekly + purchased + feedback credits
        Note: daily tokens are subset of weekly (both limits apply independently).
        """
        self._reset_if_needed()
        config = TokenConfig.get_config()
        free_daily_remaining = max(0, config.free_daily_tokens - self.daily_tokens_used)
        free_weekly_remaining = max(0, config.free_weekly_tokens - self.weekly_tokens_used)
        # Free tokens are the minimum of daily and weekly remaining
        free_tokens = min(free_daily_remaining, free_weekly_remaining)
        return free_tokens + self.purchased_tokens + self.feedback_credits

    def available_tokens_readonly(self, config, today=None):
        """Same value as ``available_tokens`` without any query or write.

        For list views (admin overview, admin user list, Django admin): the
        property runs ``TokenConfig.get_config()`` and may ``save()`` a
        counter reset for every row. Here a counter whose reset date is in a
        past period simply counts as 0 used, which is exactly what the reset
        would have written.
        """
        today = today or timezone.localdate()

        def _as_date(value):
            return value.date() if hasattr(value, 'date') else value

        week_start = today - timedelta(days=today.weekday())
        daily_used = self.daily_tokens_used if _as_date(self.last_daily_reset) >= today else 0
        weekly_used = self.weekly_tokens_used if _as_date(self.last_weekly_reset) >= week_start else 0
        free_tokens = min(
            max(0, config.free_daily_tokens - daily_used),
            max(0, config.free_weekly_tokens - weekly_used),
        )
        return free_tokens + self.purchased_tokens + self.feedback_credits

    def consume_token(self, amount=1):
        """
        Use `amount` AI tokens. Returns True if successful, False if insufficient.
        Priority: free daily/weekly first, then feedback credits, then purchased.

        Wrapped in transaction.atomic() with select_for_update() to prevent race
        conditions where concurrent requests double-spend the same balance.
        """
        from django.db import transaction
        with transaction.atomic():
            # Lock the row for the duration of this transaction.
            # On SQLite this is a no-op; on Postgres it issues SELECT ... FOR UPDATE.
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return False

            locked._reset_if_needed()
            if locked.available_tokens < amount:
                return False

            config = TokenConfig.get_config()
            tokens_to_deduct = amount
            deduct_from_feedback = 0
            deduct_from_purchased = 0

            # 1. Deduct from free daily/weekly
            free_daily_remaining = max(0, config.free_daily_tokens - locked.daily_tokens_used)
            free_weekly_remaining = max(0, config.free_weekly_tokens - locked.weekly_tokens_used)
            free_available = min(free_daily_remaining, free_weekly_remaining)

            deduct_from_free = min(free_available, tokens_to_deduct)
            if deduct_from_free > 0:
                locked.daily_tokens_used += deduct_from_free
                locked.weekly_tokens_used += deduct_from_free
                tokens_to_deduct -= deduct_from_free

            # 2. Deduct from feedback credits
            if tokens_to_deduct > 0 and locked.feedback_credits > 0:
                deduct_from_feedback = min(locked.feedback_credits, tokens_to_deduct)
                locked.feedback_credits -= deduct_from_feedback
                tokens_to_deduct -= deduct_from_feedback

            # 3. Deduct from purchased
            if tokens_to_deduct > 0 and locked.purchased_tokens > 0:
                deduct_from_purchased = min(locked.purchased_tokens, tokens_to_deduct)
                locked.purchased_tokens -= deduct_from_purchased
                tokens_to_deduct -= deduct_from_purchased

            locked.total_tokens_used += amount
            locked.save(update_fields=['daily_tokens_used', 'weekly_tokens_used', 'feedback_credits', 'purchased_tokens', 'total_tokens_used'])

            # Exact pools this call drew from, so a refund can reverse it
            # precisely (see refund_token / ai_engine.views.refund_ai_token).
            self._last_consumption = {
                'free': deduct_from_free,
                'feedback': deduct_from_feedback,
                'purchased': deduct_from_purchased,
            }

            # Sync in-memory state so subsequent property reads in this request see new values
            self.daily_tokens_used = locked.daily_tokens_used
            self.weekly_tokens_used = locked.weekly_tokens_used
            self.feedback_credits = locked.feedback_credits
            self.purchased_tokens = locked.purchased_tokens
            self.total_tokens_used = locked.total_tokens_used
            return True

    def add_purchased_tokens(self, amount):
        """Add purchased tokens to the user's balance."""
        from django.db import transaction
        with transaction.atomic():
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return
            locked.purchased_tokens += amount
            # Keep the high-water mark in sync so refund_token can restore
            # spent tokens back up to (but not above) what the user paid for.
            locked.purchased_tokens_max = max(
                locked.purchased_tokens_max or 0,
                locked.purchased_tokens,
            )
            locked.save(update_fields=['purchased_tokens', 'purchased_tokens_max'])
            self.purchased_tokens = locked.purchased_tokens
            self.purchased_tokens_max = locked.purchased_tokens_max

    def refund_token(self, amount=1, breakdown=None):
        """Refund tokens (used when AI call fails after token was consumed).

        Refund priority mirrors consume in REVERSE: restore `purchased_tokens`
        FIRST, then `feedback_credits`, then decrement `daily_tokens_used` /
        `weekly_tokens_used`. This is the silent-token-leak bug-fix for the
        previous implementation, which only decremented `daily_tokens_used` /
        `weekly_tokens_used` / `total_tokens_used` and never restored
        `purchased_tokens` or `feedback_credits` — meaning a paid token (or a
        token earned by submitting feedback) that was consumed before an AI
        provider failure was permanently lost.

        Why we restore purchased first:
            - Purchased tokens have no free replacement path. A user who paid
              for 10 tokens and lost 1 to an upstream failure would silently
              lose money.
            - Feedback credits come from a positive contribution (rated answer)
              that the user actually earned. Don't punish them for an
              upstream failure either.
            - Free daily/weekly counters reset on their own schedule; giving
              them back here is the least valuable refund.

        Note: we cannot perfectly reconstruct which source `consume_token`
        drew from for a particular call — that information is lost once the
        counters are updated. We approximate by restoring purchased first,
        then feedback, then free, until the refund amount is satisfied.
        """
        from django.db import transaction
        with transaction.atomic():
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return

            if breakdown is not None:
                # Exact reversal of a recorded consume_token() call.
                free = max(0, int(breakdown.get('free', 0) or 0))
                feedback = max(0, int(breakdown.get('feedback', 0) or 0))
                purchased = max(0, int(breakdown.get('purchased', 0) or 0))
                locked.purchased_tokens += purchased
                locked.feedback_credits += feedback
                locked.daily_tokens_used = max(0, locked.daily_tokens_used - free)
                locked.weekly_tokens_used = max(0, locked.weekly_tokens_used - free)
                locked.total_tokens_used = max(0, locked.total_tokens_used - (free + feedback + purchased))
                locked.save(update_fields=[
                    'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used',
                    'purchased_tokens', 'feedback_credits',
                ])
                self.daily_tokens_used = locked.daily_tokens_used
                self.weekly_tokens_used = locked.weekly_tokens_used
                self.total_tokens_used = locked.total_tokens_used
                self.purchased_tokens = locked.purchased_tokens
                self.feedback_credits = locked.feedback_credits
                return

            remaining = amount

            # 1. Restore purchased tokens first (highest-value refund).
            if remaining > 0 and locked.purchased_tokens_max is not None:
                # `purchased_tokens_max` is the running high-water mark of
                # purchased tokens ever observed for this user. Anything
                # below it was consumed and is eligible for refund.
                # If we don't have a high-water mark (legacy rows), fall
                # back to refunding up to current purchased + amount.
                restore_from_purchased = min(remaining, max(0, (locked.purchased_tokens_max or 0) - locked.purchased_tokens))
                if restore_from_purchased > 0:
                    locked.purchased_tokens += restore_from_purchased
                    remaining -= restore_from_purchased
            # (No high-water mark: we cannot know purchased tokens were
            # spent, so the refund falls through to the free counters
            # below instead of minting purchased tokens.)

            # 2. Restore feedback credits next.
            if remaining > 0 and locked.feedback_credits_max is not None:
                restore_from_feedback = min(remaining, max(0, (locked.feedback_credits_max or 0) - locked.feedback_credits))
                if restore_from_feedback > 0:
                    locked.feedback_credits += restore_from_feedback
                    remaining -= restore_from_feedback

            # 3. Decrement daily/weekly counters symmetrically with consume:
            # consume() charges both daily + weekly in lockstep, so we
            # decrement both. We just give back up to `remaining` total.
            # IMPORTANT: we decrement daily + weekly by the SAME amount
            # (mirroring consume's lockstep behaviour). Capturing
            # ``daily_refund`` before mutating ``remaining`` is required —
            # if we let ``remaining`` reach 0 after the daily decrement,
            # the weekly decrement would become a no-op.
            if remaining > 0:
                daily_refund = min(remaining, locked.daily_tokens_used)
                weekly_refund = min(remaining, locked.weekly_tokens_used)
                locked.daily_tokens_used -= daily_refund
                locked.weekly_tokens_used -= weekly_refund

            # Decrement the lifetime counter to keep it consistent.
            locked.total_tokens_used = max(0, locked.total_tokens_used - amount)

            locked.save(update_fields=[
                'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used',
                'purchased_tokens', 'feedback_credits',
                'purchased_tokens_max', 'feedback_credits_max',
            ])
            self.daily_tokens_used = locked.daily_tokens_used
            self.weekly_tokens_used = locked.weekly_tokens_used
            self.total_tokens_used = locked.total_tokens_used
            self.purchased_tokens = locked.purchased_tokens
            self.feedback_credits = locked.feedback_credits
            self.purchased_tokens_max = locked.purchased_tokens_max
            self.feedback_credits_max = locked.feedback_credits_max

    def add_feedback_credit(self, amount=2):
        """Reward user for accepted feedback (default: +2 tokens)."""
        from django.db import transaction
        with transaction.atomic():
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return
            locked.feedback_credits += amount
            # Keep the high-water mark in sync for refund_token.
            locked.feedback_credits_max = max(
                locked.feedback_credits_max or 0,
                locked.feedback_credits,
            )
            locked.save(update_fields=['feedback_credits', 'feedback_credits_max'])
            self.feedback_credits = locked.feedback_credits
            self.feedback_credits_max = locked.feedback_credits_max


class TokenConfig(models.Model):
    """
    Singleton configuration for token system.
    Only one row should exist. Change these values to adjust limits.
    
    Fields:
    - free_daily_tokens:  How many free AI calls per user per day (default: 10)
    - free_weekly_tokens: How many free AI calls per user per week (default: 50)
    - token_price:        Price per token in INR for purchases (default: 1.0)
    - feedback_reward:    Tokens given for each accepted feedback (default: 2)
    """
    free_daily_tokens = models.IntegerField(default=10, help_text='Free AI tokens per user per day')
    free_weekly_tokens = models.IntegerField(default=50, help_text='Free AI tokens per user per week')
    # Freemium 2/day cap on structured AI tutor calls (tutor/mnemonic/explain/
    # textbook/analyze) for free users. Premium and admin users bypass this cap
    # entirely. Change here to tune without redeploying.
    ai_tutor_daily_cap = models.IntegerField(
        default=2,
        help_text='Free AI Tutor messages/day for free users (premium/admin bypass).',
    )
    token_price = models.DecimalField(max_digits=6, decimal_places=2, default=1.00,
                                      help_text='Price per token in INR')
    feedback_reward = models.IntegerField(default=2, help_text='Tokens awarded for accepted feedback')
    min_purchase = models.IntegerField(default=10, help_text='Minimum tokens per purchase')
    max_purchase = models.IntegerField(default=500, help_text='Maximum tokens per purchase')

    class Meta:
        verbose_name = 'Token Configuration'
        verbose_name_plural = 'Token Configuration'

    def __str__(self):
        return f"Token Config: {self.free_daily_tokens}/day, {self.free_weekly_tokens}/week, ₹{self.token_price}/token"

    @classmethod
    def get_config(cls):
        """Get or create the singleton config. Always returns one instance."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class TokenTransaction(models.Model):
    """
    Records every token purchase or credit event.
    Used for revenue tracking and audit trail.
    """
    TRANSACTION_TYPES = [
        ('purchase', 'Token Purchase'),
        ('feedback_reward', 'Feedback Reward'),
        ('admin_grant', 'Admin Grant'),
        ('admin_revoke', 'Admin Revoke'),
        ('admin_transfer', 'Admin Transfer'),
        ('refund', 'Refund'),
        ('subscription_grant', 'Subscription Grant'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='token_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.IntegerField(help_text='Number of tokens')
    price_paid = models.DecimalField(max_digits=8, decimal_places=2, default=0.00,
                                     help_text='Amount paid in INR (0 for rewards)')
    payment_id = models.CharField(max_length=200, blank=True, help_text='Payment gateway reference ID')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.get_transaction_type_display()} +{self.amount} tokens"


class AdminAuditLog(models.Model):
    """Immutable audit trail for sensitive admin operations."""

    ACTION_CHOICES = [
        ('token_grant', 'Token Grant'),
        ('token_revoke', 'Token Revoke'),
        ('token_transfer', 'Token Transfer'),
        ('token_view', 'Token View'),
        ('user_view', 'User View'),
        ('user_block', 'User Block/Unblock'),
        ('user_role_update', 'User Role Update'),
        ('user_progress_reset', 'User Progress Reset'),
        ('subscription_grant', 'Subscription Grant'),
        ('subscription_revoke', 'Subscription Revoke'),
        ('device_logout', 'Device Force Logout'),
        ('system_attempt_reset', 'System Attempt Reset'),
        ('system_analytics_clear', 'System Analytics Clear'),
        ('system_rerun_evaluation', 'System Rerun Evaluation'),
        # Medical-accuracy mission (2026-11): identity recovery and editorial audit trail.
        ('identity_import', 'Identity Import'),
        ('identity_link', 'Identity Link'),
        ('recovery_link', 'Recovery Link'),
        ('email_change', 'Email Change'),
        ('session_revoke', 'Session Revoke'),
        ('answer_key_change', 'Answer Key Change'),
        ('evidence_review', 'Evidence Review'),
        ('audit_resolution', 'Audit Resolution'),
    ]

    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='admin_actions')
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=120, blank=True)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'system'
        return f"{actor_name}: {self.action} {self.resource_type}"


class PaymentAttempt(models.Model):
    """Tracks Razorpay subscription payment sessions and outcomes."""
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
    ]
    PLAN_CHOICES = [
        ('1_month', '1 Month Pass'),
        ('3_months', '3 Months Pass'),
        ('1_year', '1 Year Unlimited'),
        ('scholarship_1_month', 'Scholarship 1 Month'),
        ('legacy', 'Legacy Early Bird'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payments')
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    plan = models.CharField(max_length=30, choices=PLAN_CHOICES, default='legacy')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.razorpay_order_id} ({self.status})"


class Subscription(models.Model):
    """
    Tracks a user's premium subscription with plan type, dates, and status.

    Premium is derived from these rows only (accounts.utils.is_premium);
    ``CustomUser.is_subscribed`` is a mirror. Accounts that paid before this
    model was added got the rows their payments prove from migration
    accounts.0026 (accounts.legacy_subscriptions); a flag without payment
    evidence grants nothing.
    """
    PLAN_CHOICES = [
        ('1_month', '1 Month Pass'),
        ('3_months', '3 Months Pass'),
        ('1_year', '1 Year Unlimited'),
        ('scholarship_1_month', 'Scholarship 1 Month'),
        ('legacy', 'Legacy Early Bird (Lifetime)'),
        ('admin_grant', 'Admin Granted'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    PLAN_DURATIONS = {
        '1_month': timedelta(days=30),
        '3_months': timedelta(days=90),
        '1_year': timedelta(days=365),
        'scholarship_1_month': timedelta(days=30),
        'legacy': None,  # lifetime
        'admin_grant': None,  # lifetime
    }

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=30, choices=PLAN_CHOICES)
    plan_display_name = models.CharField(max_length=100, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    razorpay_order_id = models.CharField(max_length=100, blank=True, default='')
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True, help_text='NULL = lifetime/never expires')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Hot-path EXISTS query for has_active_sub(). The migration
            # 0020 added this index via AddIndex; declaring it here too so
            # ``manage.py makemigrations --check`` doesn't see drift and
            # so fresh databases pick it up at table-create time.
            models.Index(
                fields=['user', 'status', 'expires_at'],
                name='subscription_user_status_idx',
            ),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.get_plan_display()} ({self.status})"

    @property
    def is_active(self):
        """Check if subscription is currently active (not expired)."""
        if self.status != 'active':
            return False
        if self.expires_at is None:
            return True  # lifetime
        return timezone.now() < self.expires_at

    @property
    def days_remaining(self):
        """Days remaining on this subscription. -1 = lifetime, 0 = expired."""
        if self.expires_at is None:
            return -1  # lifetime
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    @property
    def is_lifetime(self):
        """True if this subscription never expires (legacy / admin_grant / 1_year with NULL expiry)."""
        return self.expires_at is None

    @classmethod
    def has_active_sub(cls, user) -> bool:
        """Tight read-only check: does the user have any active sub right now?

        Used by ``accounts.utils.is_premium`` on hot read paths. Performs
        NO writes — does not lazy-expire stale rows. If a row is past its
        expiry but still status='active' (because nobody has read it yet),
        it counts as active here until a payment/admin endpoint triggers
        ``get_active_subscription`` to flip it.

        The DB query is a single ``EXISTS`` with a WHERE on status +
        expires_at — covered by ``subscription_user_status_idx`` (added
        in migration 0020). No row read, no row lock, no savepoint.
        """
        from django.db.models import Q
        from django.utils import timezone

        if not user or not getattr(user, 'is_authenticated', False):
            return False
        now = timezone.now()
        return cls.objects.filter(
            user=user,
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        ).exists()

    @property
    def unlimited_ai(self):
        """True if the plan grants UNLIMITED AI usage — bypass token metering entirely.

        Truth table (single source of truth):
            1_year             → True (marketing: "100% UNLIMITED AI explanations")
            legacy             → True (early-bird lifetime)
            admin_grant        → True
            1_month            → False (daily limits apply)
            3_months           → False (daily limits apply)
            scholarship_1_month→ False (daily limits apply)
        """
        return PLAN_FEATURES.get(self.plan, {}).get('unlimited_ai', False)

    @property
    def monthly_tokens_grant(self):
        """Plan-defined monthly token top-up (None = no top-up)."""
        return PLAN_FEATURES.get(self.plan, {}).get('monthly_tokens', None)

    @classmethod
    def get_active_subscription(cls, user):
        """Get the user's current active subscription, if any.

        Side-effect: if a ``status='active'`` row is found that is actually
        past its expiry date, flip it to ``'expired'`` and clear
        ``user.is_subscribed``. Returns ``None`` if no live subscription.

        Concurrency:
            * Locks the Subscription row with ``select_for_update`` so
              concurrent profile fetches don't race the same expiry-flip.
            * Updates ``user.is_subscribed`` via ``User.objects.filter(
              id=user.id).update(...)`` rather than ``user.save()`` to
              avoid pulling the User row into the same lock graph
              (which previously could deadlock when the user row was
              already locked by another request).

        The function is safe to call from inside an outer
        ``transaction.atomic``; Django nests the lock acquisition as a
        savepoint.
        """
        from django.db import transaction

        with transaction.atomic():
            rows = list(
                cls.objects.select_for_update()
                .filter(user=user, status='active')
                .order_by('-created_at')
            )
            if not rows:
                return None

            # Evaluate EVERY active row, not just the newest: a user can hold
            # several (e.g. lifetime + a later monthly, or 1-year + a stacked
            # monthly). Previously an expired newest row flipped the user to
            # unsubscribed even though an older lifetime row was still live,
            # and a stacked non-unlimited row hid the 1-year plan's
            # unlimited AI.
            live = [r for r in rows if r.is_active]
            expired_ids = [r.pk for r in rows if not r.is_active]
            if expired_ids:
                # Idempotent under concurrent flips.
                cls.objects.filter(pk__in=expired_ids, status='active').update(status='expired')
                transaction.on_commit(lambda: invalidate_subscription_status_cache(user.pk))
            if not live:
                CustomUser.objects.filter(pk=user.pk).update(is_subscribed=False)
                # Keep the caller's instance in step: code that reads
                # user.is_subscribed later in the same request must not see
                # the stale True.
                if hasattr(user, 'is_subscribed'):
                    user.is_subscribed = False
                return None

            far_future = timezone.now() + timedelta(days=365 * 100)
            live.sort(
                key=lambda r: (
                    bool(r.unlimited_ai),
                    r.expires_at is None,
                    r.expires_at or far_future,
                    r.created_at,
                ),
                reverse=True,
            )
            return live[0]

    @classmethod
    def activate_from_payment(cls, user, plan, amount_paid, razorpay_order_id='', razorpay_payment_id=''):
        """Create or extend a subscription after successful payment.

        Behavior:
          1. Determine expiry using PLAN_FEATURES (or NONE for lifetime plans).
             Unknown plan codes raise ``ValueError`` (they used to become a
             never-expiring subscription with an invalid plan code).
          2. Dated plans EXTEND from the latest expiry among the user's live
             dated rows (stacking is intentional). The old code extended from
             get_active_subscription()'s "best" row, which can expire before
             a stacked one, so a purchase could add no time at all.
          3. Flip user.is_subscribed=True via filter-update (no User lock).
          4. For plans with ``monthly_tokens``, credit those tokens via
             ``add_purchased_tokens`` + a TokenTransaction.

        A bare ``is_subscribed`` flag (no Subscription row) is NOT turned into
        a lifetime 'legacy' row here any more: the removed unpaid
        /auth/subscribe/ endpoint set that flag for anyone, so a ₹129 month
        bought lifetime unlimited AI. Accounts that paid before the
        Subscription model existed got their rows from accounts.0026.

        Concurrency:
            The entire read-existing + create-new + flip-is_subscribed +
            credit-tokens sequence runs inside one ``transaction.atomic``.
            This prevents two concurrent payments from both observing "no
            active sub" and creating duplicate active subscriptions for
            the same user.
        """
        from django.db import transaction
        from django.db.models import Max
        from .models import TokenBalance, TokenTransaction  # local import to avoid cycle

        if plan not in PLAN_FEATURES:
            raise ValueError(f'Unknown subscription plan: {plan!r}')
        plan_features = PLAN_FEATURES[plan]
        duration = plan_features.get('duration')
        monthly_grant = plan_features.get('monthly_tokens')

        now = timezone.now()

        with transaction.atomic():
            # Re-acquire the active subs inside this transaction (row locks +
            # lazy expiry) so the read is consistent with the upcoming write.
            # If the user already paid in another tab between request entry
            # and here, we stack onto that sub rather than overlapping it.
            cls.get_active_subscription(user)
            if duration:
                latest_expiry = (
                    cls.objects
                    .filter(user=user, status='active', expires_at__gt=now)
                    .aggregate(latest=Max('expires_at'))['latest']
                )
                base_date = latest_expiry if latest_expiry and latest_expiry > now else now
                expires_at = base_date + duration
            else:
                expires_at = None  # lifetime

            display_name = plan_features.get('display_name') or plan.replace('_', ' ').title()

            sub = cls.objects.create(
                user=user,
                plan=plan,
                plan_display_name=display_name,
                amount_paid=amount_paid,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                status='active',
                starts_at=now,
                expires_at=expires_at,
            )

            # Mirror for legacy code paths that still read user.is_subscribed.
            # Use filter-update so we don't lock the user row inside the
            # Subscription-graph transaction.
            CustomUser.objects.filter(pk=user.pk).update(is_subscribed=True)

            # Credit the student's wallet with the plan's monthly token grant.
            if monthly_grant and monthly_grant > 0:
                balance, _ = TokenBalance.objects.get_or_create(user=user)
                balance.add_purchased_tokens(monthly_grant)
                TokenTransaction.objects.create(
                    user=user,
                    transaction_type='subscription_grant',
                    amount=monthly_grant,
                    price_paid=Decimal(str(amount_paid)),
                    payment_id=razorpay_payment_id or f'sub_{sub.id}',
                    note=f'Subscription grant: {display_name} (+{monthly_grant} tokens)',
                )

            # The status endpoint caches its answer for 2 minutes.
            transaction.on_commit(lambda: invalidate_subscription_status_cache(user.pk))

        if hasattr(user, 'is_subscribed'):
            user.is_subscribed = True
        return sub


class UserDevice(models.Model):
    """Tracks devices a user has logged in from to enforce simultaneous device limits.

    ``device_fingerprint`` is the browser's X-Session-ID, or ``sid:<session>``
    for a device known only by its Supabase session. ``session_id`` is the
    Supabase auth session bound to the device (accounts.supabase_rest_auth).
    Inactive ``sid:`` rows record ended sessions and are never listed.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='devices')
    device_fingerprint = models.CharField(max_length=255)
    session_id = models.CharField(
        max_length=64, null=True, blank=True, default=None, db_index=True,
        help_text='Supabase auth session (access-token session_id claim) bound to this device.',
    )
    device_name = models.CharField(max_length=255, blank=True)
    browser = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_login = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_login']
        unique_together = ('user', 'device_fingerprint')

    def __str__(self):
        return f"{self.user.username} - {self.device_name} ({self.ip_address})"


# ─── Django-native sign-in (AUTH_PROVIDER=django; accounts.native_auth) ─────

class UserIdentity(models.Model):
    """An external sign-in identity of an account, matched on (provider, subject) only.

    ``subject`` is the provider's stable account id (Google's ``sub``). The
    email is informational and is never used to find an identity: an email
    proves nothing about who signs in with it.
    """

    PROVIDER_GOOGLE = 'google'
    PROVIDER_CHOICES = [(PROVIDER_GOOGLE, 'Google')]
    SOURCE_CHOICES = [
        ('supabase_import', 'Imported from Supabase Auth'),
        ('signup', 'Signed up with this identity'),
        ('email_confirmed', 'Linked through an emailed confirmation link'),
        ('user_linked', 'Linked by the signed-in user'),
        ('operator', 'Linked by an operator'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='identities')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    subject = models.CharField(max_length=255, help_text="The provider's account id (Google: sub).")
    email = models.EmailField(max_length=254, blank=True, default='', help_text='Informational only; never matched.')
    email_verified = models.BooleanField(default=False)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    supabase_identity_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    last_sign_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'subject'], name='useridentity_provider_subject_uniq'),
        ]
        indexes = [models.Index(fields=['user', 'provider'], name='useridentity_user_provider_idx')]

    def __str__(self):
        return f'{self.user_id}: {self.provider}'


class AuthSession(models.Model):
    """A Django-native sign-in session (one per sign-in on one browser).

    ``sid`` is the ``session_id`` claim of its tokens and the
    ``UserDevice.session_id`` of the device using it, so the device cap of
    accounts.device_limits applies unchanged. ``refresh_jti`` is the only
    refresh token that may rotate; ``previous_refresh_jti`` is answered (with
    tokens equivalent to the current ones) only within
    NATIVE_AUTH_REFRESH_REUSE_SECONDS of a rotation (another tab rotated
    first, or the rotation's answer was lost). Any other reuse revokes the
    session.
    """

    METHOD_CHOICES = [
        ('password', 'Email and password'),
        ('google', 'Google'),
        ('google_link', 'Google (emailed link confirmation)'),
        ('reset', 'Password reset'),
        ('verify', 'Email verification'),
        ('local', 'Local development'),
    ]
    REVOKED_REASON_CHOICES = [
        ('logout', 'Logout'),
        ('password_reset', 'Password reset'),
        ('password_change', 'Password change'),
        ('refresh_reuse', 'Refresh token reuse'),
        ('device_logout', 'Device logged out'),
        ('blocked', 'Account blocked'),
        ('admin', 'Revoked by an admin'),
    ]

    sid = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='auth_sessions')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    refresh_jti = models.CharField(max_length=64, blank=True, default='')
    previous_refresh_jti = models.CharField(max_length=64, blank=True, default='')
    rotated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text='Absolute end of the session (NATIVE_AUTH_SESSION_MAX_DAYS).')
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=20, blank=True, default='', choices=REVOKED_REASON_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        indexes = [models.Index(fields=['user', 'revoked_at'], name='authsession_user_revoked_idx')]

    def __str__(self):
        return f'{self.user_id}: {self.method} session'

    def is_active_at(self, now) -> bool:
        return self.revoked_at is None and self.expires_at > now


class PendingSignup(models.Model):
    """A sign-up waiting for its emailed verification link (one row per sign-up).

    The account row is created only when a link is opened
    (POST /api/auth/native/verify-email/ {token, password}), so an unverified
    sign-up cannot squat an address. Several sign-ups of one address are
    separate rows: a later one never changes an earlier one's password, and
    the password typed when opening a link picks the row that becomes the
    account (accounts.native_auth). Only a SHA-256 digest of the emailed token
    is stored.
    """

    email = models.EmailField(max_length=254, db_index=True, help_text='Lower-cased.')
    password = models.CharField(max_length=128, help_text='make_password() hash.')
    username = models.CharField(max_length=150, blank=True, default='')
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f'pending sign-up {self.pk}'

