"""Coupon pricing, limits and redemption (models in ``accounts.models_coupons``, 2026-11-07).

* ``quote_for_user(code, user, plan=None)`` -- what the code is worth for this student (every plan it
  applies to, or one plan). Raises ``CouponError`` (``.code`` / ``.message``) when it cannot be used.
* ``reserve(...)`` -- called by the order view after the Razorpay order exists: holds one use for
  ``RESERVATION_MINUTES`` under a row lock, so the last use of a limited code is not sold twice. The
  same student's earlier unpaid holds of the code are released.
* ``mark_redeemed(order_id, subscription)`` -- called inside the purchase transaction
  (``accounts.views._record_razorpay_purchase``, verify and webhook alike).
* ``redeem_free(...)`` -- a code worth the whole price activates the plan at once, without Razorpay.

Prices come from ``PLAN_FEATURES`` (whole rupees). Codes apply to the three plans on sale, never to the
scholarship rate.
"""
from __future__ import annotations

import re
import secrets
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

COUPON_PLANS = ('1_month', '3_months', '1_year')
RESERVATION_MINUTES = 30
CODE_RE = re.compile(r'^[A-Z0-9][A-Z0-9-]{2,31}$')
MAX_FIXED_RUPEES = 100000
FREE_ORDER_PREFIX = 'COUPON-'
MESSAGES = {
    'coupon_invalid': 'This coupon code is not valid.',
    'coupon_not_started': 'This coupon code is not active yet.',
    'coupon_expired': 'This coupon code has expired.',
    'coupon_used_up': 'This coupon code has already been used the maximum number of times.',
    'coupon_already_used': 'You have already used this coupon code.',
    'coupon_not_for_you': 'This coupon code is not valid for your account.',
    'coupon_not_for_plan': 'This coupon code does not apply to this plan.',
}


class CouponError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
        self.message = MESSAGES[code]


def normalize_code(raw) -> str:
    """Upper case, no whitespace: students may type a code in any case."""
    return re.sub(r'\s+', '', str(raw or '')).upper()


def generate_code(prefix: str = 'CL') -> str:
    """A random code without look-alike characters (0/O, 1/I)."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return f'{prefix}-' + ''.join(secrets.choice(alphabet) for _ in range(8))


def plan_price(plan: str) -> int:
    from .models import PLAN_FEATURES

    return int(PLAN_FEATURES[plan]['price_inr'])


def applies_to(coupon, plan: str) -> bool:
    return plan in COUPON_PLANS and (not coupon.plans or plan in coupon.plans)


def quote(coupon, plan: str) -> dict:
    """``{plan, original_amount, discount_amount, final_amount}`` in whole rupees."""
    base = plan_price(plan)
    if coupon.discount_type == coupon.PERCENT:
        off = base * min(int(coupon.discount_value), 100) // 100
    else:
        off = min(int(coupon.discount_value), base)
    return {'plan': plan, 'original_amount': base, 'discount_amount': off, 'final_amount': base - off}


def _live_holds(qs):
    """Redeemed uses plus checkouts started in the last RESERVATION_MINUTES."""
    cutoff = timezone.now() - timedelta(minutes=RESERVATION_MINUTES)
    return qs.filter(Q(status='redeemed') | Q(status='reserved', created_at__gte=cutoff))


def uses(coupon) -> int:
    return _live_holds(coupon.redemptions.all()).count()


def check(coupon, user, plan=None) -> None:
    """Raise ``CouponError`` unless ``user`` may use ``coupon`` (for ``plan`` when given)."""
    now = timezone.now()
    if coupon is None or not coupon.is_active:
        raise CouponError('coupon_invalid')
    if coupon.valid_from and coupon.valid_from > now:
        raise CouponError('coupon_not_started')
    if coupon.valid_until and coupon.valid_until < now:
        raise CouponError('coupon_expired')
    if coupon.assigned_user_id and coupon.assigned_user_id != getattr(user, 'id', None):
        raise CouponError('coupon_not_for_you')
    redeemed_by_user = coupon.redemptions.filter(user_id=user.id, status='redeemed').count()
    if redeemed_by_user >= max(int(coupon.max_uses_per_user or 1), 1):
        raise CouponError('coupon_already_used')
    if coupon.max_uses is not None:
        # The student's own unpaid hold is replaced by a new checkout, so it is not counted here.
        others = _live_holds(coupon.redemptions.exclude(user_id=user.id, status='reserved')).count()
        if others >= coupon.max_uses:
            raise CouponError('coupon_used_up')
    if plan is not None and not applies_to(coupon, plan):
        raise CouponError('coupon_not_for_plan')


def find(code):
    from .models_coupons import Coupon

    code = normalize_code(code)
    return Coupon.objects.filter(code=code).first() if code else None


def public_view(coupon) -> dict:
    """What a student may see about a code (never the admin note or the limits)."""
    return {'code': coupon.code, 'discount_type': coupon.discount_type, 'discount_value': coupon.discount_value}


def quote_for_user(code, user, plan=None) -> dict:
    coupon = find(code)
    check(coupon, user, plan)
    plans = [plan] if plan else [p for p in COUPON_PLANS if applies_to(coupon, p)]
    if not plans:
        raise CouponError('coupon_not_for_plan')
    return {**public_view(coupon), 'plans': {p: quote(coupon, p) for p in plans}}


def reserve(coupon, user, plan: str, order_id: str):
    """Hold one use for this checkout (row lock on the coupon). Raises ``CouponError``."""
    from .models_coupons import Coupon, CouponRedemption

    with transaction.atomic():
        locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
        check(locked, user, plan)
        CouponRedemption.objects.filter(coupon=locked, user=user, status='reserved').update(status='released')
        amounts = quote(locked, plan)
        return CouponRedemption.objects.create(
            coupon=locked, user=user, plan=plan, razorpay_order_id=order_id, status='reserved',
            original_amount=amounts['original_amount'], discount_amount=amounts['discount_amount'],
            final_amount=amounts['final_amount'],
        )


def mark_redeemed(order_id: str, subscription) -> str:
    """Mark the hold of a paid order redeemed (whatever became of the hold). Returns its code or ''."""
    from .models_coupons import CouponRedemption

    if not order_id:
        return ''
    row = (CouponRedemption.objects.select_related('coupon').filter(razorpay_order_id=order_id)
           .order_by('-created_at').first())
    if row is None:
        return ''
    if row.status != 'redeemed':
        CouponRedemption.objects.filter(pk=row.pk).update(
            status='redeemed', subscription=subscription, redeemed_at=timezone.now())
    return row.coupon.code


def redeem_free(coupon, user, plan: str):
    """Activate ``plan`` for a code worth its whole price (no payment). Returns the Subscription."""
    from .models import Subscription, TokenTransaction
    from .models_coupons import Coupon, CouponRedemption

    with transaction.atomic():
        locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
        check(locked, user, plan)
        amounts = quote(locked, plan)
        if amounts['final_amount'] != 0:
            raise ValueError('redeem_free needs a code worth the whole price')
        CouponRedemption.objects.filter(coupon=locked, user=user, status='reserved').update(status='released')
        order_id = f'{FREE_ORDER_PREFIX}{locked.code}-{uuid.uuid4().hex[:10]}'
        sub = Subscription.activate_from_payment(user=user, plan=plan, amount_paid=0, razorpay_order_id=order_id)
        CouponRedemption.objects.create(
            coupon=locked, user=user, plan=plan, razorpay_order_id=order_id, status='redeemed',
            subscription=sub, redeemed_at=timezone.now(), original_amount=amounts['original_amount'],
            discount_amount=amounts['discount_amount'], final_amount=0,
        )
        TokenTransaction.objects.create(
            user=user, transaction_type='purchase', amount=0, price_paid=0,
            note=f'Coupon {locked.code} (100% off): {sub.plan_display_name}, order={order_id}',
        )
        return sub
