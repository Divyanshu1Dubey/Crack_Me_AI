"""Which links may stand behind a published job listing, and when a listing counts as verified.

A listing is shown to students only when an admin checked it against the official notification (``source_url``)
and approved it: both its links are on an official recruitment site (Indian government and public-institution
domains: ``.gov.in``, ``.nic.in``, ``.edu.in``, ``.ac.in``, ``.res.in``, AIIMS New Delhi's ``aiims.edu``, plus
``settings.JOBS_EXTRA_OFFICIAL_DOMAINS``), and the check is at most ``settings.JOBS_VERIFY_MAX_AGE_DAYS`` old
(re-verify to keep a long-open listing up). Nothing here fetches or invents a listing.
"""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

OFFICIAL_SUFFIXES = ('.gov.in', '.nic.in', '.edu.in', '.ac.in', '.res.in')
OFFICIAL_HOSTS = ('aiims.edu', 'cdac.in')  # AIIMS New Delhi; C-DAC runs several forces' recruitment portals
DEFAULT_VERIFY_MAX_AGE_DAYS = 45


def official_url(url) -> bool:
    """An http(s) link on an official recruitment site."""
    try:
        parsed = urlparse((url or '').strip())
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip('.')
    extra = tuple(d.strip().lower().lstrip('.') for d in getattr(settings, 'JOBS_EXTRA_OFFICIAL_DOMAINS', ()) or ()
                  if d and d.strip())
    if any(host == h or host.endswith('.' + h) for h in OFFICIAL_HOSTS + extra):
        return True
    return host.endswith(OFFICIAL_SUFFIXES)


def verify_max_age_days() -> int:
    try:
        return max(1, int(getattr(settings, 'JOBS_VERIFY_MAX_AGE_DAYS', DEFAULT_VERIFY_MAX_AGE_DAYS)))
    except (TypeError, ValueError):
        return DEFAULT_VERIFY_MAX_AGE_DAYS


def verified_recently(when, now=None) -> bool:
    now = now or timezone.now()
    return bool(when) and when >= now - timedelta(days=verify_max_age_days())


def public_filter(now=None) -> Q:
    """The listings students see: active, approved, verified recently, not past their deadline."""
    now = now or timezone.now()
    return (Q(is_active=True, status='approved', last_verified_at__gte=now - timedelta(days=verify_max_age_days()))
            & (Q(expires_at__isnull=True) | Q(expires_at__gte=now)))


def approval_problems(*, apply_link, source_url, last_verified_at) -> list[str]:
    """Why a listing may not be approved ([] when it may)."""
    problems = []
    if not official_url(apply_link):
        problems.append('The apply link must be on an official recruitment site (.gov.in, .nic.in, .edu.in, .ac.in, '
                        '.res.in, aiims.edu).')
    if not official_url(source_url):
        problems.append('Add the official notification the listing was checked against (source URL on an official '
                        'site).')
    if not verified_recently(last_verified_at):
        problems.append(f'Verify the listing against the official notification first (a check older than '
                        f'{verify_max_age_days()} days does not count).')
    return problems
