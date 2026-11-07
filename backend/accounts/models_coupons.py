"""Coupon codes (2026-11-07): an admin creates a code, a student applies it on /subscription.

The price is computed on the server only (``accounts.coupons``). Starting a checkout with a code charges
the discounted amount and RESERVES one use (so the last use of a limited code cannot be sold twice); the
purchase (Razorpay verify or webhook, ``accounts.views._record_razorpay_purchase``) marks it REDEEMED. A
code worth the whole price activates the plan without a payment. Admins see every redemption
(``/api/auth/admin/coupons/``, Django admin).
"""
from django.conf import settings
from django.db import models


class Coupon(models.Model):
    PERCENT = 'percent'
    FIXED = 'fixed'
    DISCOUNT_TYPES = [(PERCENT, 'Percent off'), (FIXED, 'Rupees off')]

    code = models.CharField(max_length=32, unique=True,
                            help_text='Upper-case letters, digits and hyphens; students may type any case.')
    description = models.CharField(max_length=200, blank=True,
                                   help_text='Admin note (who it is for, why). Never shown to students.')
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default=PERCENT)
    discount_value = models.PositiveIntegerField(help_text='1-100 for percent off; rupees for a fixed amount off.')
    plans = models.JSONField(default=list, blank=True,
                             help_text='Plan ids the code applies to (1_month, 3_months, 1_year); empty = all three.')
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text='Total uses; empty = no limit.')
    max_uses_per_user = models.PositiveIntegerField(default=1)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    assigned_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='personal_coupons',
                                      help_text='Only this account may use the code (a personal reward).')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        off = f'{self.discount_value}%' if self.discount_type == self.PERCENT else f'Rs {self.discount_value}'
        return f'{self.code} ({off} off)'


class CouponRedemption(models.Model):
    RESERVED = 'reserved'
    RELEASED = 'released'
    REDEEMED = 'redeemed'
    # A checkout holds one use for RESERVATION_MINUTES (accounts.coupons); the same student's next
    # checkout with the code releases the earlier unpaid hold. A paid order is redeemed whatever its hold.
    STATUSES = [(RESERVED, 'Checkout started'), (RELEASED, 'Checkout abandoned'), (REDEEMED, 'Redeemed')]

    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_redemptions')
    plan = models.CharField(max_length=30)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # The Razorpay order of the checkout, or "COUPON-..." for a code that paid the whole price.
    razorpay_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    subscription = models.ForeignKey('accounts.Subscription', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='+')
    status = models.CharField(max_length=10, choices=STATUSES, default=RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['coupon', 'status'], name='accounts_co_coupon_status_idx')]

    def __str__(self):
        return f'{self.coupon.code} by user {self.user_id} ({self.status})'
