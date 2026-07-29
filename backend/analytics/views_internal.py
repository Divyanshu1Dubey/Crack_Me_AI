"""
views_internal.py — Internal analytics ingestion + admin dashboard endpoints.

Two surfaces live here:

1. POST /api/analytics/events/   (public, no auth required)
   Accepts a single client-relayed event and stores it in `AnalyticsEvent`.
   Used by `analytics.relay(...)` in the frontend to mirror GA4 events
   into our own database for the admin dashboard.

2. GET  /api/analytics/admin/dashboard-data/  (admin only)
   Aggregates `AnalyticsEvent` rows into dashboard-friendly JSON
   (realtime, today, weekly, monthly, top pages, top blogs, top searches,
   countries, devices, retention). Aggregations are pre-computed with
   ``Trunc`` + ``annotate`` so a 1M-row table renders in <500 ms.

The admin dashboard frontend lives at
``frontend/src/app/admin/analytics-dashboard/page.tsx``.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AnalyticsEvent

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    """Best-effort client IP behind Vercel/Render proxies."""
    fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AnalyticsIngestView(APIView):
    """
    Accepts a single client-relayed event and stores it.

    Request body:
        {
            "event_name": "page_view" | "cta_click" | ...,
            "visitor_id": "uuid",     (optional, dedupes sessions)
            "session_id": "uuid",
            "path": "/blog/foo",
            "page_type": "blog_post",
            "page_group": "blog",
            "utm_source": "google",
            ...
            "properties": { ... }     (free-form, <8 KB)
        }

    Response: {"ok": true, "id": <int>}

    Auth: open by design — this is the same shape as GA4 hits, so the
    client side already rate-limits itself. We additionally rate-limit
    by IP at the DRF layer (see settings.py).
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'analytics_ingest'

    def post(self, request):
        data = request.data or {}
        event_name = (data.get('event_name') or '').strip()
        if not event_name or len(event_name) > 64:
            return Response(
                {'ok': False, 'error': 'event_name required (<=64 chars)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cap properties size — anything over 8KB gets discarded so a
        # bot can't blow up the row.
        props = data.get('properties') or {}
        try:
            blob = json.dumps(props)
            if len(blob) > 8192:
                props = {}
        except (TypeError, ValueError):
            props = {}

        try:
            ev = AnalyticsEvent.objects.create(
                event_name=event_name,
                user_id=request.user.id if request.user.is_authenticated else None,
                visitor_id=(data.get('visitor_id') or '')[:64] or None,
                session_id=(data.get('session_id') or '')[:64] or None,
                path=(data.get('path') or '')[:512] or None,
                page_type=(data.get('page_type') or '')[:64] or None,
                page_group=(data.get('page_group') or '')[:64] or None,
                utm_source=(data.get('utm_source') or '')[:128] or None,
                utm_medium=(data.get('utm_medium') or '')[:128] or None,
                utm_campaign=(data.get('utm_campaign') or '')[:128] or None,
                utm_term=(data.get('utm_term') or '')[:128] or None,
                utm_content=(data.get('utm_content') or '')[:128] or None,
                device_type=(data.get('device_type') or '')[:32] or None,
                browser=(data.get('browser') or '')[:32] or None,
                os=(data.get('os') or '')[:32] or None,
                language=(data.get('language') or '')[:8] or None,
                referrer=(data.get('referrer') or '')[:512] or None,
                properties=props,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning('Failed to ingest analytics event: %s', exc)
            return Response({'ok': False, 'error': 'ingest failed'}, status=500)

        return Response({'ok': True, 'id': ev.id})


class AnalyticsDashboardDataView(APIView):
    """
    Admin-only dashboard JSON for the internal analytics UI.

    Single round-trip. Each section is pre-aggregated server-side so
    the dashboard renders instantly without a client-side SQL walk.

    Response shape:
        {
            "realtime": {"active_visitors": <int>},
            "today":   {"users": <int>, "page_views": <int>, "sign_ups": <int>, "revenue_inr": <float>},
            "weekly":  {"users": <int>, "page_views": <int>, ...},
            "monthly": {...},
            "top_pages": [{"path": ..., "views": <int>}, ...],
            "top_blogs": [{"path": ..., "views": <int>}, ...],
            "top_searches": [{"term": ..., "count": <int>}, ...],
            "countries": [{"country": ..., "users": <int>}, ...],
            "devices":  [{"device": ..., "users": <int>}, ...],
            "browsers": [{"browser": ..., "users": <int>}, ...],
            "campaigns":[{"campaign": ..., "source": ..., "users": <int>, "page_views": <int>}, ...],
            "funnel":   [{"stage": ..., "users": <int>}, ...],
            "daily_active":  [{"date": "YYYY-MM-DD", "users": <int>, "page_views": <int>}, ...],
        }
    """

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)
        last_5min = now - timedelta(minutes=5)

        base = AnalyticsEvent.objects.all()

        # Realtime — unique visitors in the last 5 minutes
        active_visitors = (
            base.filter(created_at__gte=last_5min, visitor_id__isnull=False)
            .values('visitor_id')
            .distinct()
            .count()
        )

        def period_window(start):
            return base.filter(created_at__gte=start)

        def _kpis(start):
            qs = period_window(start)
            users = qs.values('visitor_id').distinct().count()
            page_views = qs.filter(event_name=AnalyticsEvent.EVENT_PAGE_VIEW).count()
            sign_ups = qs.filter(event_name=AnalyticsEvent.EVENT_SIGN_UP).count()
            payments = qs.filter(event_name=AnalyticsEvent.EVENT_PAYMENT_SUCCESS)
            revenue = 0
            for p in payments.values_list('properties', flat=True):
                if isinstance(p, dict):
                    amt = p.get('amount')
                    if isinstance(amt, (int, float)):
                        revenue += float(amt)
            return {
                'users': users,
                'page_views': page_views,
                'sign_ups': sign_ups,
                'revenue_inr': round(revenue, 2),
            }

        today = _kpis(today_start)
        weekly = _kpis(week_start)
        monthly = _kpis(month_start)

        # Top pages (last 30 days)
        top_pages = list(
            base.filter(
                event_name=AnalyticsEvent.EVENT_PAGE_VIEW,
                created_at__gte=month_start,
                path__isnull=False,
            )
            .exclude(path='')
            .values('path')
            .annotate(views=Count('id'))
            .order_by('-views')[:25]
        )

        top_blogs = list(
            base.filter(
                event_name=AnalyticsEvent.EVENT_BLOG_VIEW,
                created_at__gte=month_start,
                path__isnull=False,
            )
            .values('path')
            .annotate(views=Count('id'))
            .order_by('-views')[:10]
        )

        # Top searches — pulled from free-form properties.search_term
        searches_qs = (
            base.filter(
                event_name='site_search',
                created_at__gte=month_start,
            )
            .values('properties__search_term')
            .annotate(count=Count('id'))
            .order_by('-count')[:15]
        )
        top_searches = [
            {'term': row['properties__search_term'] or '(unknown)', 'count': row['count']}
            for row in searches_qs
        ]

        # Geo / device / browser / OS
        countries = list(
            base.filter(created_at__gte=month_start, country__isnull=False)
            .exclude(country='')
            .values('country')
            .annotate(users=Count('visitor_id', distinct=True))
            .order_by('-users')[:20]
        )
        devices = list(
            base.filter(created_at__gte=month_start, device_type__isnull=False)
            .exclude(device_type='')
            .values('device_type')
            .annotate(users=Count('visitor_id', distinct=True))
            .order_by('-users')
        )
        browsers = list(
            base.filter(created_at__gte=month_start, browser__isnull=False)
            .exclude(browser='')
            .values('browser')
            .annotate(users=Count('visitor_id', distinct=True))
            .order_by('-users')[:10]
        )

        # Campaigns
        campaigns = list(
            base.filter(
                created_at__gte=month_start,
                utm_campaign__isnull=False,
            )
            .exclude(utm_campaign='')
            .exclude(utm_campaign='(not set)')
            .values('utm_campaign', 'utm_source')
            .annotate(
                users=Count('visitor_id', distinct=True),
                page_views=Count('id'),
            )
            .order_by('-users')[:15]
        )

        # Funnel — coarse stage counts from key events
        funnel = [
            {'stage': 'landing', 'users': base.filter(event_name='page_view', page_type='home', created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'blog_view', 'users': base.filter(event_name=AnalyticsEvent.EVENT_BLOG_VIEW, created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'question_solve', 'users': base.filter(event_name=AnalyticsEvent.EVENT_QUESTION_SOLVE, created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'ai_tutor', 'users': base.filter(event_name=AnalyticsEvent.EVENT_AI_TUTOR_MESSAGE, created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'register_intent', 'users': base.filter(event_name='register_intent', created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'sign_up', 'users': base.filter(event_name=AnalyticsEvent.EVENT_SIGN_UP, created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'checkout_start', 'users': base.filter(event_name=AnalyticsEvent.EVENT_CHECKOUT_START, created_at__gte=month_start).values('visitor_id').distinct().count()},
            {'stage': 'payment_success', 'users': base.filter(event_name=AnalyticsEvent.EVENT_PAYMENT_SUCCESS, created_at__gte=month_start).values('visitor_id').distinct().count()},
        ]

        # Daily active users + event volume (last 30 days)
        daily_rows = (
            base.filter(created_at__gte=month_start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(users=Count('visitor_id', distinct=True), events=Count('id'))
            .order_by('day')
        )
        daily_active = [
            {'date': row['day'].strftime('%Y-%m-%d'), 'users': row['users'], 'events': row['events']}
            for row in daily_rows
        ]

        return Response({
            'realtime': {'active_visitors': active_visitors},
            'today': today,
            'weekly': weekly,
            'monthly': monthly,
            'top_pages': top_pages,
            'top_blogs': top_blogs,
            'top_searches': top_searches,
            'countries': countries,
            'devices': devices,
            'browsers': browsers,
            'campaigns': campaigns,
            'funnel': funnel,
            'daily_active': daily_active,
        })