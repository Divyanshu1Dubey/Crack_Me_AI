"""Premium flags from before the Subscription model: keep what was paid for, nothing else.

Until accounts.0011 (2026-07-18) premium was only ``CustomUser.is_subscribed``.
It was set by

* the Razorpay verify view after a SIGNED payment: from 2026-07-02 the ₹199
  lifetime Early Bird pass, recorded only as a TokenTransaction note
  "Razorpay Premium: order=..., payment=..."; from 2026-07-03 also as a
  PaymentAttempt (status 'successful'); from 2026-07-04 the dated plans too
  (1 month ₹129, 3 months ₹449, 1 year ₹1999, the scholarship month), which
  likewise only set the flag and so never expired;
* POST /api/auth/subscribe/ (2026-07-02 to 2026-07-26), which set it for ANY
  signed-in user without a payment and wrote the TokenTransaction note
  "Purchased ₹199 Early Bird Premium Subscription" with no payment id;
* manual edits in Django admin.

A flag without a Subscription row used to count as a lifetime plan, so the
unpaid endpoint's users kept premium forever, and a later dated purchase even
turned the flag into a real lifetime row with unlimited AI. Premium now comes
from Subscription rows only (accounts.utils.is_premium). This module turns the
PAYMENT EVIDENCE of the flagged accounts without rows into the rows they paid
for:

* the ₹199 Early Bird pass -> a 'legacy' row (lifetime, as it was sold);
* a dated plan -> its row with the period it bought, counted from the order
  date and stacked like Subscription.activate_from_payment. Periods that have
  ended are stored as history and expire on the next read (which also clears
  the flag).

Migration accounts.0026 restores them once on deploy. Accounts without any
payment evidence get no row and are no longer premium; ``manage.py
reconcile_legacy_subscriptions`` lists them, and clears their stale flag only
with ``--apply --clear-unproven`` after an owner review (grant a plan in the
admin panel first to any account that should keep premium).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger("accounts.legacy_subscriptions")

# What was sold in July 2026, frozen: this records history and must not follow
# later price or plan changes.
_PLANS = {
    "legacy": ("Legacy Early Bird (Lifetime)", None),
    "1_month": ("1 Month Pass", timedelta(days=30)),
    "3_months": ("3 Months Pass", timedelta(days=90)),
    "1_year": ("1 Year Unlimited", timedelta(days=365)),
    "scholarship_1_month": ("Scholarship 1 Month", timedelta(days=30)),
}
_PLAN_BY_PRICE = {
    Decimal("199.00"): "legacy",
    Decimal("129.00"): "1_month",
    Decimal("449.00"): "3_months",
    Decimal("1999.00"): "1_year",
}
# Written by the Razorpay verify view only after the payment signature checked out.
_RAZORPAY_NOTE_PREFIX = "Razorpay Premium"
_ORDER_PAYMENT_RE = re.compile(r"order=(?P<order>[^,\s]+),\s*payment=(?P<payment>[^,\s]+)")
# Written by the removed unpaid /auth/subscribe/ endpoint.
FREE_ENDPOINT_NOTE = "Purchased ₹199 Early Bird Premium Subscription"
SOURCE = "reconcile_legacy_subscriptions"


@dataclass(frozen=True)
class Purchase:
    plan: str
    amount: Decimal
    paid_at: datetime
    order_id: str
    payment_id: str
    source: str  # 'payment_attempt' | 'token_transaction'


@dataclass
class FlaggedAccount:
    """An account with ``is_subscribed`` set and no Subscription row."""

    user_id: int
    email: str
    purchases: list = field(default_factory=list)
    rows: list = field(default_factory=list)  # Subscription fields the payments prove
    free_claim_at: datetime | None = None     # used the unpaid endpoint
    premium_after_restore: bool = False
    action: str = ""                          # 'restored' | 'cleared' | 'skipped' | ''

    @property
    def proven(self) -> bool:
        return bool(self.rows)


def _price(value) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _plan_for(recorded_plan, amount) -> str | None:
    """The plan a successful payment bought (None: no usable evidence)."""
    if recorded_plan in _PLANS and recorded_plan != "legacy":
        return recorded_plan
    # 'legacy' is also the default every order made before accounts.0011
    # (which added PaymentAttempt.plan) received: the amount says what it was.
    price = _price(amount)
    if price is None or price <= 0:
        return None
    return _PLAN_BY_PRICE.get(price, "scholarship_1_month")


def payment_evidence(user_id, *, PaymentAttempt, TokenTransaction) -> list[Purchase]:
    """Every signed Razorpay payment on record for ``user_id``, oldest first."""
    purchases: list[Purchase] = []
    orders: set[str] = set()
    attempts = (
        PaymentAttempt.objects.filter(user_id=user_id, status="successful")
        .exclude(razorpay_payment_id__isnull=True)
        .exclude(razorpay_payment_id="")
        .order_by("created_at", "pk")
    )
    for attempt in attempts:
        plan = _plan_for(attempt.plan, attempt.amount)
        if plan is None:
            continue
        orders.add(attempt.razorpay_order_id)
        purchases.append(Purchase(
            plan, _price(attempt.amount), attempt.created_at,
            attempt.razorpay_order_id, attempt.razorpay_payment_id, "payment_attempt",
        ))
    # Before 2026-07-03 a signed payment left only this note.
    notes = (
        TokenTransaction.objects.filter(
            user_id=user_id, transaction_type="purchase", note__startswith=_RAZORPAY_NOTE_PREFIX,
        ).order_by("created_at", "pk")
    )
    for tx in notes:
        match = _ORDER_PAYMENT_RE.search(tx.note or "")
        if match is None or match["order"] in orders:
            continue
        plan = _plan_for("legacy", tx.price_paid)
        if plan is None:
            continue
        orders.add(match["order"])
        purchases.append(Purchase(
            plan, _price(tx.price_paid), tx.created_at, match["order"], match["payment"], "token_transaction",
        ))
    purchases.sort(key=lambda p: (p.paid_at, p.order_id))
    return purchases


def planned_rows(purchases) -> list[dict]:
    """Subscription fields for ``purchases``; dated periods stack like activate_from_payment."""
    rows, latest_expiry = [], None
    for purchase in purchases:
        display_name, duration = _PLANS[purchase.plan]
        if duration is None:
            expires_at = None
        else:
            start = latest_expiry if latest_expiry is not None and latest_expiry > purchase.paid_at else purchase.paid_at
            expires_at = start + duration
            latest_expiry = expires_at
        rows.append({
            "plan": purchase.plan,
            "plan_display_name": display_name,
            "amount_paid": purchase.amount,
            "razorpay_order_id": (purchase.order_id or "")[:100],
            "razorpay_payment_id": (purchase.payment_id or "")[:100],
            # Ended periods are flipped to 'expired' (and the flag cleared) by
            # the next Subscription.get_active_subscription, like any plan.
            "status": "active",
            "starts_at": purchase.paid_at,
            "expires_at": expires_at,
        })
    return rows


def flagged_without_plan(User, Subscription):
    """Accounts with ``is_subscribed`` set and no Subscription row at all."""
    return (
        User.objects.filter(is_subscribed=True)
        .exclude(pk__in=Subscription.objects.values("user_id"))
        .order_by("pk")
    )


def _invalidate_status_cache(user_id):
    try:
        from accounts.models import invalidate_subscription_status_cache

        invalidate_subscription_status_cache(user_id)
    except Exception:  # noqa: BLE001 - best effort
        pass


def _audit(AuditLog, action, user_id, detail, metadata):
    if AuditLog is None:
        return
    AuditLog.objects.create(
        actor=None, action=action, resource_type="subscription", resource_id=str(user_id),
        detail=detail, metadata={"source": SOURCE, **metadata},
    )


def _restore(account, *, Subscription, AuditLog):
    with transaction.atomic():
        # Idempotent: skip an account that has rows by now (second run, a purchase).
        if Subscription.objects.filter(user_id=account.user_id).exists():
            account.action = "skipped"
            return
        for row in account.rows:
            Subscription.objects.create(user_id=account.user_id, **row)
        _audit(
            AuditLog, "subscription_grant", account.user_id,
            f"Restored {len(account.rows)} pre-Subscription plan(s) from payment records",
            {
                "orders": [p.order_id for p in account.purchases],
                "plans": [p.plan for p in account.purchases],
                "premium_after_restore": account.premium_after_restore,
            },
        )
    account.action = "restored"
    _invalidate_status_cache(account.user_id)
    logger.warning(
        "Restored %d plan(s) for user_id=%s from payment records (%s); premium now: %s",
        len(account.rows), account.user_id, ", ".join(p.plan for p in account.purchases),
        account.premium_after_restore,
    )


def _clear(account, *, User, Subscription, AuditLog):
    with transaction.atomic():
        updated = (
            User.objects.filter(pk=account.user_id, is_subscribed=True)
            .exclude(pk__in=Subscription.objects.filter(user_id=account.user_id).values("user_id"))
            .update(is_subscribed=False)
        )
        if not updated:
            account.action = "skipped"
            return
        _audit(
            AuditLog, "subscription_revoke", account.user_id,
            "Cleared is_subscribed: no payment on record (pre-Subscription flag)",
            {"used_unpaid_endpoint": account.free_claim_at is not None},
        )
    account.action = "cleared"
    _invalidate_status_cache(account.user_id)
    logger.warning("Cleared is_subscribed for user_id=%s: no payment on record", account.user_id)


def reconcile(*, User, Subscription, PaymentAttempt, TokenTransaction, AuditLog=None,
              restore=False, clear_unproven=False, now=None) -> list[FlaggedAccount]:
    """Report (and optionally fix) every flagged account without a Subscription row.

    ``restore`` creates the rows the payment evidence proves; ``clear_unproven``
    clears the flag of accounts without any evidence. Takes the model classes,
    so a migration can pass its historical models.
    """
    now = now or timezone.now()
    accounts = []
    for user in flagged_without_plan(User, Subscription).only("pk", "email"):
        purchases = payment_evidence(user.pk, PaymentAttempt=PaymentAttempt, TokenTransaction=TokenTransaction)
        rows = planned_rows(purchases)
        free_claim = (
            TokenTransaction.objects.filter(user_id=user.pk, transaction_type="purchase", note=FREE_ENDPOINT_NOTE)
            .order_by("created_at").values_list("created_at", flat=True).first()
        )
        account = FlaggedAccount(
            user_id=user.pk, email=user.email or "", purchases=purchases, rows=rows, free_claim_at=free_claim,
            premium_after_restore=any(r["expires_at"] is None or r["expires_at"] > now for r in rows),
        )
        accounts.append(account)
        if account.proven and restore:
            _restore(account, Subscription=Subscription, AuditLog=AuditLog)
        elif not account.proven and clear_unproven:
            _clear(account, User=User, Subscription=Subscription, AuditLog=AuditLog)
    return accounts
