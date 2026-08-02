"""Shared helpers for account-related logic.

Single source of truth for "is this user premium?" — every freemium gate
calls ``is_premium()`` and gets the same answer.

The hot-path call is read-only: it does NOT trigger lazy-expiry of stale
``status='active'`` rows. Expiry reconciliation happens inside
``Subscription.get_active_subscription`` ONLY when called from payment /
admin endpoints that already hold an outer transaction. For read-only
gates we go straight to the DB with a tight ``SELECT`` and skip the side
effect.

This avoids the previous bug where every profile fetch for a user with
an expired-but-not-yet-flipped sub would do two writes (one to flip the
Subscription row, one to flip ``user.is_subscribed``) and could deadlock
against concurrent updates of the User row.
"""
from __future__ import annotations

from typing import Optional

from .models import Subscription


def _has_active_sub(user) -> bool:
    """Tight read-only check: any active row exists? Does NOT mutate state."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
        return True
    # Backward-compat grandfather: legacy users with is_subscribed=True but
    # no Subscription row (added before this model existed) still count.
    if getattr(user, 'is_subscribed', False) and not Subscription.objects.filter(user=user).exists():
        return True
    return Subscription.has_active_sub(user)


def is_premium(user) -> bool:
    """True if the user has an active subscription OR is admin/staff.

    Anonymous users, users without a subscription, and users whose only
    subscription is expired or cancelled are NOT premium.

    ``Subscription.is_active`` already enforces status='active' AND
    (expires_at IS NULL OR expires_at > now).
    """
    return _has_active_sub(user)


def refresh_is_premium(user) -> bool:
    """Read-and-reconcile variant. Use ONLY from payment/admin endpoints.

    Performs the same lazy expiry as the old ``get_active_subscription``
    side effect (flips stale rows). Do NOT call from hot read paths.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
        return True
    sub = Subscription.get_active_subscription(user)
    return bool(sub and sub.is_active)