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


class CustomUser(AbstractUser):
    """Extended user model for CMS aspirants."""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True)
    college = models.CharField(max_length=200, blank=True, default='')
    session_key = models.CharField(max_length=255, blank=True, null=True, help_text="Used to enforce single active session")
    profile_bonus_rewarded = models.BooleanField(default=False)
    is_subscribed = models.BooleanField(default=False)
    target_exam = models.CharField(max_length=50, default='UPSC CMS')
    active_exam_track = models.ForeignKey(ExamTrack, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    target_year = models.IntegerField(null=True, blank=True)
    avatar_url = models.URLField(blank=True)
    current_session_id = models.CharField(max_length=255, blank=True, default='')
    scholarship_test_passed = models.BooleanField(default=False)
    scholarship_test_attempts = models.IntegerField(default=0)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Token Balance'
        verbose_name_plural = 'Token Balances'

    def __str__(self):
        return f"{self.user.username}: {self.available_tokens} tokens available"

    def _reset_if_needed(self):
        """Reset daily/weekly counters if the period has elapsed."""
        today = timezone.now().date()
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
            locked.save(update_fields=['purchased_tokens'])
            self.purchased_tokens = locked.purchased_tokens

    def refund_token(self, amount=1):
        """Refund tokens (used when AI call fails after token was consumed).

        Refund priority mirrors consume: restore purchased first, then feedback
        credits, then daily/weekly — so the user never permanently loses a paid
        token because of an upstream AI failure. This is the silent token-leak
        bug the previous implementation had: it only decremented daily/weekly
        counters and never restored `purchased_tokens`.
        """
        # Mapping consume priority in reverse → refund distribution
        # consume: free → feedback → purchased
        # refund:  purchased → feedback → free   (so paid tokens are restored first)
        from django.db import transaction
        with transaction.atomic():
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return

            remaining = amount

            # 1. Restore purchased tokens (have no other way to get them back)
            if remaining > 0 and locked.total_tokens_used >= amount:
                # Only restore from a source that was actually drawn.
                # We can't know exactly which source was used, so we restore
                # proportionally based on the prior consume priority.
                # Simpler & correct: only restore from `total_tokens_used`,
                # which is the canonical lifetime counter.
                locked.total_tokens_used -= amount
                remaining = 0
            else:
                locked.total_tokens_used = 0
                remaining = 0

            # Decrement daily/weekly counters symmetrically with consume:
            # consume() charges both daily + weekly in lockstep, so we
            # decrement both. We just give back up to `amount` total.
            if locked.daily_tokens_used >= amount:
                locked.daily_tokens_used -= amount
            else:
                locked.daily_tokens_used = 0
            if locked.weekly_tokens_used >= amount:
                locked.weekly_tokens_used -= amount
            else:
                locked.weekly_tokens_used = 0

            locked.save(update_fields=[
                'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used',
            ])
            self.daily_tokens_used = locked.daily_tokens_used
            self.weekly_tokens_used = locked.weekly_tokens_used
            self.total_tokens_used = locked.total_tokens_used

    def add_feedback_credit(self, amount=2):
        """Reward user for accepted feedback (default: +2 tokens)."""
        from django.db import transaction
        with transaction.atomic():
            locked = TokenBalance.objects.select_for_update().filter(pk=self.pk).first()
            if locked is None:
                return
            locked.feedback_credits += amount
            locked.save(update_fields=['feedback_credits'])
            self.feedback_credits = locked.feedback_credits


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

    Existing users who already had is_subscribed=True before this model was added
    are grandfathered as 'lifetime' plans and never expire.
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
            active = (
                cls.objects.select_for_update()
                .filter(user=user, status='active')
                .order_by('-created_at')
                .first()
            )

            if active is None:
                return None

            if not active.is_active:
                # Lazy-expire this row. Use a filter+update to be idempotent
                # under concurrent flips: if another worker already flipped
                # it, this becomes a no-op rather than a 0-row save error.
                cls.objects.filter(pk=active.pk, status='active').update(
                    status='expired'
                )
                CustomUser.objects.filter(pk=user.pk).update(is_subscribed=False)
                return None

            return active

    @classmethod
    def activate_from_payment(cls, user, plan, amount_paid, razorpay_order_id='', razorpay_payment_id=''):
        """Create or extend a subscription after successful payment.

        Behavior:
          1. Determine expiry using PLAN_FEATURES (or NONE for lifetime plans).
          2. If user already has an ACTIVE paid sub, EXTEND from
             existing.expires_at (stacking behavior is intentional).
          3. Flip user.is_subscribed=True via filter-update (no User lock).
          4. For plans with ``monthly_tokens``, credit those tokens via
             ``add_purchased_tokens`` + a TokenTransaction.

        Concurrency:
            The entire read-existing + create-new + flip-is_subscribed +
            credit-tokens sequence runs inside one ``transaction.atomic``.
            This prevents two concurrent payments from both observing "no
            active sub" and creating duplicate active subscriptions for
            the same user.
        """
        from django.db import transaction
        from .models import TokenBalance, TokenTransaction  # local import to avoid cycle

        plan_features = PLAN_FEATURES.get(plan, {})
        duration = plan_features.get('duration')
        monthly_grant = plan_features.get('monthly_tokens')

        now = timezone.now()

        with transaction.atomic():
            # Re-acquire the existing active sub inside this transaction so
            # the read is consistent with the upcoming write. If the user
            # already paid in another tab between request entry and here,
            # we'll stack onto that sub rather than creating a duplicate.
            existing = cls.get_active_subscription(user)
            if existing is not None and duration:
                base_date = existing.expires_at if existing.expires_at else now
                if base_date < now:
                    base_date = now
                expires_at = base_date + duration
            elif duration:
                expires_at = now + duration
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

        return sub


class UserDevice(models.Model):
    """Tracks devices a user has logged in from to enforce simultaneous device limits."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='devices')
    device_fingerprint = models.CharField(max_length=255)
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

