"""
AnalyticsEvent — append-only ingestion table for the internal admin
dashboard. Mirrors the events the frontend fans out via `lib/analytics.ts`
(client-side GA4 / Clarity / PostHog all use their own stores; this table
is the company-owned copy for our own BI + retention modelling).

Storage cap: each `properties` blob is rejected above 8KB so a malicious
client cannot blow up row size. Indexes target the admin dashboard's
hot queries (page_type / page_group / utm_campaign / created_at).
"""
import uuid

from django.db import models
from django.utils import timezone


class AnalyticsEvent(models.Model):
    """One client-relayed event."""

    EVENT_PAGE_VIEW = 'page_view'
    EVENT_QUESTION_SOLVE = 'question_solve'
    EVENT_PAYMENT_SUCCESS = 'payment_success'
    EVENT_SIGN_UP = 'sign_up'
    EVENT_SUBSCRIPTION_INTENT = 'subscription_intent'
    EVENT_CAMPAIGN_CLICK = 'campaign_click'
    EVENT_AI_TUTOR_MESSAGE = 'ai_tutor_message'
    EVENT_BLOG_VIEW = 'blog_view'
    EVENT_LEADERBOARD_VIEW = 'leaderboard_view'
    EVENT_CHECKOUT_START = 'checkout_start'

    id = models.BigAutoField(primary_key=True)
    event_id = models.CharField(max_length=64, default=uuid.uuid4, editable=False)
    event_name = models.CharField(max_length=64, db_index=True)

    user_id = models.IntegerField(null=True, blank=True, db_index=True)

    visitor_id = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text='client-generated UUID for cross-session dedup',
    )
    session_id = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text='per-tab / per-session id',
    )

    path = models.CharField(max_length=512, null=True, blank=True)
    page_type = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    page_group = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    utm_source = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=128, null=True, blank=True)
    utm_campaign = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    utm_term = models.CharField(max_length=128, null=True, blank=True)
    utm_content = models.CharField(max_length=128, null=True, blank=True)

    device_type = models.CharField(max_length=32, null=True, blank=True)
    browser = models.CharField(max_length=32, null=True, blank=True)
    os = models.CharField(max_length=32, null=True, blank=True)
    language = models.CharField(max_length=8, null=True, blank=True)
    country = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    referrer = models.CharField(max_length=512, null=True, blank=True)

    properties = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_name', 'created_at']),
            models.Index(fields=['page_type', 'created_at']),
            models.Index(fields=['page_group', 'created_at']),
            models.Index(fields=['utm_campaign', 'created_at']),
            models.Index(fields=['country', 'created_at']),
        ]

    def __str__(self) -> str:  # pragma: no cover - debug only
        return f'{self.event_name} ({self.path}) @ {self.created_at:%Y-%m-%d %H:%M}'
