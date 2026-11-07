"""Coupon endpoints (2026-11-07); logic in ``accounts.coupons``, models in ``accounts.models_coupons``.

Student:
    POST /api/auth/coupons/validate/  {code, plan?} -> what the code is worth (every plan it applies to,
         or one plan); 400 {code: coupon_*, error} when it cannot be used. 30 checks per hour per account.
    The code itself is applied by POST /api/auth/subscribe/order/ {plan, coupon_code} (accounts.views).
Admin (IsControlTowerAdmin):
    GET/POST   /api/auth/admin/coupons/                list (with uses) / create (an empty code is generated)
    PATCH/DEL  /api/auth/admin/coupons/<id>/           edit / delete (a used code can only be switched off)
    GET        /api/auth/admin/coupons/redemptions/    who used which code: ?coupon=<id>&status=redeemed
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from . import coupons
from .models_coupons import Coupon, CouponRedemption
from .permissions import IsControlTowerAdmin

User = get_user_model()


class _CouponValidateThrottle(UserRateThrottle):
    """Guessing codes costs a request each: 30 checks per hour per account is plenty for a real student."""
    scope = 'coupon_validate'
    rate = '30/hour'


def _coupon_error(exc: coupons.CouponError) -> Response:
    return Response({'code': exc.code, 'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)


class CouponValidateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [_CouponValidateThrottle]

    def post(self, request):
        plan = str(request.data.get('plan') or '').strip() or None
        if plan is not None and plan not in coupons.COUPON_PLANS:
            return _coupon_error(coupons.CouponError('coupon_not_for_plan'))
        try:
            return Response(coupons.quote_for_user(request.data.get('code'), request.user, plan))
        except coupons.CouponError as exc:
            return _coupon_error(exc)


# ── admin ──────────────────────────────────────────────────────────────────────────────────

def _user_view(user):
    return {'id': user.id, 'username': user.username, 'email': user.email} if user else None


def _annotated():
    cutoff = timezone.now() - timedelta(minutes=coupons.RESERVATION_MINUTES)
    return (Coupon.objects.select_related('assigned_user', 'created_by').annotate(
        redeemed=Count('redemptions', filter=Q(redemptions__status='redeemed')),
        holds=Count('redemptions', filter=Q(redemptions__status='reserved', redemptions__created_at__gte=cutoff)),
        discount_given=Sum('redemptions__discount_amount', filter=Q(redemptions__status='redeemed')),
        revenue=Sum('redemptions__final_amount', filter=Q(redemptions__status='redeemed')),
    ))


def _state(coupon) -> str:
    now = timezone.now()
    if not coupon.is_active:
        return 'off'
    if coupon.valid_until and coupon.valid_until < now:
        return 'expired'
    if coupon.valid_from and coupon.valid_from > now:
        return 'scheduled'
    if coupon.max_uses is not None and getattr(coupon, 'redeemed', 0) >= coupon.max_uses:
        return 'used_up'
    return 'live'


def _coupon_view(coupon) -> dict:
    return {
        'id': coupon.id,
        'code': coupon.code,
        'description': coupon.description,
        'discount_type': coupon.discount_type,
        'discount_value': coupon.discount_value,
        'plans': list(coupon.plans or []),
        'max_uses': coupon.max_uses,
        'max_uses_per_user': coupon.max_uses_per_user,
        'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None,
        'valid_until': coupon.valid_until.isoformat() if coupon.valid_until else None,
        'is_active': coupon.is_active,
        'assigned_user': _user_view(coupon.assigned_user),
        'created_by': coupon.created_by.username if coupon.created_by else None,
        'created_at': coupon.created_at.isoformat() if coupon.created_at else None,
        'redeemed': getattr(coupon, 'redeemed', 0) or 0,
        'checkouts_in_progress': getattr(coupon, 'holds', 0) or 0,
        'discount_given': float(getattr(coupon, 'discount_given', 0) or 0),
        'revenue': float(getattr(coupon, 'revenue', 0) or 0),
        'state': _state(coupon),
    }


def _datetime(value, field, errors):
    if value in (None, ''):
        return None
    parsed = parse_datetime(str(value)) if isinstance(value, str) else None
    if parsed is None:
        errors[field] = 'Use an ISO date-time, e.g. 2026-12-31T23:59:00+05:30.'
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def _positive_int(value, field, errors, *, low=1, high=None, allow_none=False):
    if value in (None, '') and allow_none:
        return None
    try:
        number = int(value)
        if isinstance(value, bool) or number < low or (high is not None and number > high):
            raise ValueError
    except (TypeError, ValueError):
        errors[field] = f'Whole number from {low}' + (f' to {high}.' if high is not None else ' up.')
        return None
    return number


def _clean(data, instance=None):
    """``(fields, errors)`` for a create (instance None) or a partial update."""
    fields, errors = {}, {}
    creating = instance is None

    if 'code' in data or creating:
        code = coupons.normalize_code(data.get('code'))
        if not code and creating:
            for _ in range(10):
                code = coupons.generate_code()
                if not Coupon.objects.filter(code=code).exists():
                    break
        if not coupons.CODE_RE.match(code or ''):
            errors['code'] = '3-32 characters: letters, digits and hyphens.'
        elif Coupon.objects.filter(code=code).exclude(pk=getattr(instance, 'pk', None)).exists():
            errors['code'] = 'This code already exists.'
        elif instance is not None and code != instance.code and instance.redemptions.filter(status='redeemed').exists():
            errors['code'] = 'This code has been used; create a new code instead of renaming it.'
        else:
            fields['code'] = code
    if 'description' in data:
        fields['description'] = str(data.get('description') or '').strip()[:200]
    discount_type = data.get('discount_type', getattr(instance, 'discount_type', Coupon.PERCENT))
    if discount_type not in (Coupon.PERCENT, Coupon.FIXED):
        errors['discount_type'] = 'percent or fixed.'
    elif 'discount_type' in data:
        fields['discount_type'] = discount_type
    if 'discount_value' in data or creating:
        high = 100 if discount_type == Coupon.PERCENT else coupons.MAX_FIXED_RUPEES
        value = _positive_int(data.get('discount_value'), 'discount_value', errors, high=high)
        if value is not None:
            fields['discount_value'] = value
    elif 'discount_type' in data and instance is not None and discount_type == Coupon.PERCENT \
            and instance.discount_value > 100:
        errors['discount_value'] = 'A percent discount is at most 100.'
    if 'plans' in data:
        plans = data.get('plans') or []
        if not isinstance(plans, list) or any(p not in coupons.COUPON_PLANS for p in plans):
            errors['plans'] = f'A list of: {", ".join(coupons.COUPON_PLANS)} (empty = all).'
        else:
            fields['plans'] = [p for p in coupons.COUPON_PLANS if p in plans]
    if 'max_uses' in data:
        fields['max_uses'] = _positive_int(data.get('max_uses'), 'max_uses', errors, allow_none=True)
    if 'max_uses_per_user' in data:
        value = _positive_int(data.get('max_uses_per_user'), 'max_uses_per_user', errors, high=100)
        if value is not None:
            fields['max_uses_per_user'] = value
    for field in ('valid_from', 'valid_until'):
        if field in data:
            fields[field] = _datetime(data.get(field), field, errors)
    start = fields.get('valid_from', getattr(instance, 'valid_from', None))
    end = fields.get('valid_until', getattr(instance, 'valid_until', None))
    if start and end and end <= start:
        errors['valid_until'] = 'Must be after the start.'
    if 'assigned_email' in data:
        email = str(data.get('assigned_email') or '').strip()
        if not email:
            fields['assigned_user'] = None
        else:
            matches = list(User.objects.filter(email__iexact=email)[:2])
            if len(matches) != 1:
                errors['assigned_email'] = 'No single account has this email.'
            else:
                fields['assigned_user'] = matches[0]
    if 'is_active' in data:
        if not isinstance(data.get('is_active'), bool):
            errors['is_active'] = 'true or false.'
        else:
            fields['is_active'] = data['is_active']
    return fields, errors


class AdminCouponListView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        return Response({'results': [_coupon_view(c) for c in _annotated()[:500]]})

    def post(self, request):
        fields, errors = _clean(request.data)
        if errors:
            return Response({'code': 'invalid_coupon', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        coupon = Coupon.objects.create(created_by=request.user, **fields)
        return Response(_coupon_view(_annotated().get(pk=coupon.pk)), status=status.HTTP_201_CREATED)


class AdminCouponDetailView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def patch(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if coupon is None:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)
        fields, errors = _clean(request.data, instance=coupon)
        if errors:
            return Response({'code': 'invalid_coupon', 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        for name, value in fields.items():
            setattr(coupon, name, value)
        coupon.save()
        return Response(_coupon_view(_annotated().get(pk=coupon.pk)))

    def delete(self, request, coupon_id: int):
        coupon = Coupon.objects.filter(pk=coupon_id).first()
        if coupon is None:
            return Response({'error': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)
        if coupon.redemptions.filter(status='redeemed').exists():
            return Response({'code': 'coupon_in_use',
                             'error': 'This code has been used, so it is kept for the records. Switch it off instead.'},
                            status=status.HTTP_409_CONFLICT)
        coupon.redemptions.all().delete()   # abandoned checkouts only
        coupon.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCouponRedemptionsView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        rows = CouponRedemption.objects.select_related('coupon', 'user')
        coupon_id = request.query_params.get('coupon')
        if coupon_id:
            if not str(coupon_id).isdigit():
                return Response({'error': 'coupon must be an id.'}, status=status.HTTP_400_BAD_REQUEST)
            rows = rows.filter(coupon_id=int(coupon_id))
        wanted = request.query_params.get('status')
        if wanted in ('reserved', 'released', 'redeemed'):
            rows = rows.filter(status=wanted)
        return Response({'results': [{
            'id': r.id,
            'coupon_id': r.coupon_id,
            'code': r.coupon.code,
            'user': _user_view(r.user),
            'plan': r.plan,
            'original_amount': float(r.original_amount),
            'discount_amount': float(r.discount_amount),
            'final_amount': float(r.final_amount),
            'status': r.status,
            'razorpay_order_id': r.razorpay_order_id,
            'subscription_id': r.subscription_id,
            'created_at': r.created_at.isoformat() if r.created_at else None,
            'redeemed_at': r.redeemed_at.isoformat() if r.redeemed_at else None,
        } for r in rows.order_by('-created_at')[:500]]})
