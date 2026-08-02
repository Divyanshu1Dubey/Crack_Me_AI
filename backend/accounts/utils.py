"""Shared helpers for account-related logic."""
from .models import Subscription


def is_premium(user) -> bool:
    """Return True if the user has an active subscription OR is admin/staff.

    Single source of truth used by every freemium gate. Anonymous users,
    users without a subscription, and users whose only subscription is
    expired or cancelled are NOT premium.

    `Subscription.is_active` already enforces status='active' AND
    (expires_at IS NULL OR expires_at > now).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
        return True
    sub = Subscription.get_active_subscription(user)
    return bool(sub and sub.is_active)