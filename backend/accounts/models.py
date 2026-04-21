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
    target_exam = models.CharField(max_length=50, default='UPSC CMS')
    target_year = models.IntegerField(null=True, blank=True)
    avatar_url = models.URLField(blank=True)
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
    purchased_tokens = models.IntegerField(default=0, help_text='Tokens bought by user (never expire)')
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

    def consume_token(self):
        """
        Use 1 AI token. Returns True if successful, False if insufficient.
        Priority: free daily/weekly first, then feedback credits, then purchased.
        """
        self._reset_if_needed()
        config = TokenConfig.get_config()

        # Check free daily/weekly limits
        if (self.daily_tokens_used < config.free_daily_tokens and
                self.weekly_tokens_used < config.free_weekly_tokens):
            self.daily_tokens_used += 1
            self.weekly_tokens_used += 1
            self.total_tokens_used += 1
            self.save(update_fields=['daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used'])
            return True

        # Use feedback credits next
        if self.feedback_credits > 0:
            self.feedback_credits -= 1
            self.total_tokens_used += 1
            self.save(update_fields=['feedback_credits', 'total_tokens_used'])
            return True

        # Use purchased tokens last
        if self.purchased_tokens > 0:
            self.purchased_tokens -= 1
            self.total_tokens_used += 1
            self.save(update_fields=['purchased_tokens', 'total_tokens_used'])
            return True

        return False  # No tokens available

    def add_purchased_tokens(self, amount):
        """Add purchased tokens to the user's balance."""
        self.purchased_tokens += amount
        self.save(update_fields=['purchased_tokens'])

    def refund_token(self):
        """Refund 1 token (used when AI call fails after token was consumed)."""
        if self.total_tokens_used > 0:
            self.total_tokens_used -= 1
        # Refund in reverse priority: daily/weekly first, then feedback, then purchased
        if self.daily_tokens_used > 0 and self.weekly_tokens_used > 0:
            self.daily_tokens_used -= 1
            self.weekly_tokens_used -= 1
            self.save(update_fields=['daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used'])
        elif self.feedback_credits > 0:
            self.feedback_credits += 1
            self.save(update_fields=['feedback_credits', 'total_tokens_used'])
        else:
            self.purchased_tokens += 1
            self.save(update_fields=['purchased_tokens', 'total_tokens_used'])

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
