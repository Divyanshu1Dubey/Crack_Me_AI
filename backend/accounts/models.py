"""
accounts/models.py — User model and Token System models.
Contains: CustomUser (AbstractUser with medical exam fields),
TokenBalance (per-user AI token balance with daily/weekly tracking),
TokenConfig (singleton global config for limits and pricing),
TokenTransaction (audit log for all token purchases and consumption).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class CustomUser(AbstractUser):
    """Extended user model for CMS aspirants."""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True)
    college = models.CharField(max_length=200, blank=True, default='')
    profile_bonus_rewarded = models.BooleanField(default=False)
    is_subscribed = models.BooleanField(default=False)
    target_exam = models.CharField(max_length=50, default='UPSC CMS')
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
        """
        self._reset_if_needed()
        if self.available_tokens < amount:
            return False

        config = TokenConfig.get_config()
        tokens_to_deduct = amount

        # 1. Deduct from free daily/weekly
        free_daily_remaining = max(0, config.free_daily_tokens - self.daily_tokens_used)
        free_weekly_remaining = max(0, config.free_weekly_tokens - self.weekly_tokens_used)
        free_available = min(free_daily_remaining, free_weekly_remaining)
        
        deduct_from_free = min(free_available, tokens_to_deduct)
        if deduct_from_free > 0:
            self.daily_tokens_used += deduct_from_free
            self.weekly_tokens_used += deduct_from_free
            tokens_to_deduct -= deduct_from_free

        # 2. Deduct from feedback credits
        if tokens_to_deduct > 0 and self.feedback_credits > 0:
            deduct_from_feedback = min(self.feedback_credits, tokens_to_deduct)
            self.feedback_credits -= deduct_from_feedback
            tokens_to_deduct -= deduct_from_feedback

        # 3. Deduct from purchased
        if tokens_to_deduct > 0 and self.purchased_tokens > 0:
            deduct_from_purchased = min(self.purchased_tokens, tokens_to_deduct)
            self.purchased_tokens -= deduct_from_purchased
            tokens_to_deduct -= deduct_from_purchased

        self.total_tokens_used += amount
        self.save(update_fields=['daily_tokens_used', 'weekly_tokens_used', 'feedback_credits', 'purchased_tokens', 'total_tokens_used'])
        return True

    def add_purchased_tokens(self, amount):
        """Add purchased tokens to the user's balance."""
        self.purchased_tokens += amount
        self.save(update_fields=['purchased_tokens'])

    def refund_token(self, amount=1):
        """Refund tokens (used when AI call fails after token was consumed)."""
        if self.total_tokens_used >= amount:
            self.total_tokens_used -= amount
        else:
            self.total_tokens_used = 0
            
        # Simplistic refund: just refund as daily/weekly if possible
        self.daily_tokens_used = max(0, self.daily_tokens_used - amount)
        self.weekly_tokens_used = max(0, self.weekly_tokens_used - amount)
        self.save(update_fields=['daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used'])

    def add_feedback_credit(self, amount=2):
        """Reward user for accepted feedback (default: +2 tokens)."""
        self.feedback_credits += amount
        self.save(update_fields=['feedback_credits'])


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

    @classmethod
    def get_active_subscription(cls, user):
        """Get the user's current active subscription, if any."""
        # First check for unexpired subscriptions
        active = cls.objects.filter(
            user=user,
            status='active',
        ).order_by('-created_at').first()

        if active and not active.is_active:
            # Auto-expire if past expiry date
            active.status = 'expired'
            active.save(update_fields=['status'])
            # Also update user flag
            user.is_subscribed = False
            user.save(update_fields=['is_subscribed'])
            return None

        return active

    @classmethod
    def activate_from_payment(cls, user, plan, amount_paid, razorpay_order_id='', razorpay_payment_id=''):
        """Create or extend a subscription after successful payment."""
        plan_display_names = {
            '1_month': '1 Month Pass',
            '3_months': '3 Months Pass',
            '1_year': '1 Year Unlimited',
            'scholarship_1_month': 'Scholarship 1 Month',
            'legacy': 'Legacy Early Bird (Lifetime)',
            'admin_grant': 'Admin Granted (Lifetime)',
        }
        duration = cls.PLAN_DURATIONS.get(plan)
        now = timezone.now()

        # Check if user already has an active subscription — extend it
        existing = cls.get_active_subscription(user)
        if existing and existing.is_active and duration:
            # Extend from the existing expiry date (or now if lifetime)
            base_date = existing.expires_at if existing.expires_at else now
            if base_date < now:
                base_date = now
            expires_at = base_date + duration
        elif duration:
            expires_at = now + duration
        else:
            expires_at = None  # lifetime

        sub = cls.objects.create(
            user=user,
            plan=plan,
            plan_display_name=plan_display_names.get(plan, plan),
            amount_paid=amount_paid,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            status='active',
            starts_at=now,
            expires_at=expires_at,
        )

        # Keep the boolean flag in sync for backward compatibility
        user.is_subscribed = True
        user.save(update_fields=['is_subscribed'])

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

