from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import (
    AdminAuditLog, AuthSession, CustomUser, PendingSignup, TokenBalance, TokenConfig, TokenTransaction, UserIdentity,
)
from .models_coupons import Coupon, CouponRedemption
from .models_freemium import FreeShowcaseQuestion


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'target_exam', 'is_subscribed', 'scholarship_test_attempts', 'scholarship_test_passed', 'is_active']
    list_filter = ['role', 'target_exam', 'is_subscribed', 'scholarship_test_passed', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('CMS Profile', {'fields': ('role', 'phone', 'target_exam', 'target_year', 'avatar_url')}),
        # Linked Supabase Auth identity (see accounts.supabase_rest_auth).
        ('Supabase identity', {'fields': ('supabase_uid',)}),
        # Django-native sign-in (AUTH_PROVIDER=django; accounts.native_auth).
        ('Native sign-in', {'fields': ('email_verified_at',)}),
    )


@admin.register(TokenBalance)
class TokenBalanceAdmin(admin.ModelAdmin):
    """Admin view for managing user token balances."""
    list_display = ['user', 'available_tokens_display', 'purchased_tokens', 'feedback_credits',
                    'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used']
    list_filter = ['last_daily_reset']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['total_tokens_used', 'created_at', 'updated_at']
    list_select_related = ['user']

    def changelist_view(self, request, extra_context=None):
        # One TokenConfig lookup per page instead of one (plus a possible
        # counter-reset UPDATE) per row; see available_tokens_readonly.
        self._token_config = TokenConfig.get_config()
        return super().changelist_view(request, extra_context=extra_context)

    def available_tokens_display(self, obj):
        config = getattr(self, '_token_config', None) or TokenConfig.get_config()
        return obj.available_tokens_readonly(config)
    available_tokens_display.short_description = 'Available Tokens'


@admin.register(TokenConfig)
class TokenConfigAdmin(admin.ModelAdmin):
    """Singleton config — change daily/weekly limits, pricing here."""
    list_display = ['free_daily_tokens', 'free_weekly_tokens', 'token_price', 'feedback_reward']

    def has_add_permission(self, request):
        # Only allow one config row
        return not TokenConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TokenTransaction)
class TokenTransactionAdmin(admin.ModelAdmin):
    """Audit trail for all token purchases and rewards."""
    list_display = ['user', 'transaction_type', 'amount', 'price_paid', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__username', 'payment_id']
    readonly_fields = ['user', 'transaction_type', 'amount', 'price_paid', 'payment_id', 'created_at']


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'action', 'resource_type', 'resource_id']
    list_filter = ['action', 'resource_type', 'created_at']
    search_fields = ['actor__username', 'resource_type', 'resource_id', 'detail']
    readonly_fields = ['actor', 'action', 'resource_type', 'resource_id', 'detail', 'metadata', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}


@admin.register(FreeShowcaseQuestion)
class FreeShowcaseQuestionAdmin(admin.ModelAdmin):
    list_display = ('year', 'position', 'question')
    list_filter = ('year',)
    ordering = ('year', 'position')
    search_fields = ('question__question_text',)
    raw_id_fields = ('question',)


# ── Django-native sign-in (AUTH_PROVIDER=django) ───────────────────────

@admin.register(UserIdentity)
class UserIdentityAdmin(admin.ModelAdmin):
    """External sign-in identities (Google ``sub``). Adding one here is the operator link.

    Admin / staff accounts are never linked by email automatically
    (accounts.google_identity): link them here after checking who owns the
    Google account. Identities are matched on (provider, subject) only.
    """

    list_display = ['user', 'provider', 'source', 'email_verified', 'created_at', 'last_sign_in_at']
    list_filter = ['provider', 'source']
    search_fields = ['user__username', 'user__email', 'subject']
    raw_id_fields = ['user']
    readonly_fields = ['created_at', 'last_sign_in_at', 'supabase_identity_id']

    def get_changeform_initial_data(self, request):
        return {**super().get_changeform_initial_data(request), 'source': 'operator'}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .views import create_admin_audit_log

        create_admin_audit_log(
            actor=request.user, action='identity_link', resource_type='user', resource_id=obj.user_id,
            detail=f'{obj.provider} identity {"changed" if change else "linked"} in Django admin',
            metadata={'provider': obj.provider, 'source': obj.source},
        )


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    """Native sign-in sessions; "Revoke" ends them (refresh token included) on the next request."""

    list_display = ['user', 'method', 'created_at', 'last_used_at', 'expires_at', 'revoked_at', 'revoked_reason']
    list_filter = ['method', 'revoked_reason']
    search_fields = ['user__username', 'user__email', 'sid']
    raw_id_fields = ['user']
    readonly_fields = [f.name for f in AuthSession._meta.fields]
    actions = ['revoke_sessions']

    def has_add_permission(self, request):
        return False

    @admin.action(description='Revoke the selected sessions')
    def revoke_sessions(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now(), revoked_reason='admin')
        from .views import create_admin_audit_log

        create_admin_audit_log(
            actor=request.user, action='session_revoke', resource_type='auth_session',
            detail=f'Revoked {count} native session(s) in Django admin', metadata={'count': count},
        )
        self.message_user(request, f'Revoked {count} session(s).')


@admin.register(PendingSignup)
class PendingSignupAdmin(admin.ModelAdmin):
    """Sign-ups waiting for their emailed link (no account exists yet)."""

    list_display = ['email', 'created_at', 'expires_at']
    search_fields = ['email']
    readonly_fields = ['email', 'username', 'first_name', 'last_name', 'created_at', 'expires_at', 'ip_address']
    exclude = ['password', 'token_hash']

    def has_add_permission(self, request):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """Coupon codes (accounts.coupons). The admin panel's Coupons page is the main editor."""

    list_display = ['code', 'discount_type', 'discount_value', 'max_uses', 'max_uses_per_user', 'valid_until',
                    'is_active', 'created_at']
    list_filter = ['is_active', 'discount_type']
    search_fields = ['code', 'description']
    raw_id_fields = ['assigned_user', 'created_by']


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    """Who used which code: read-only purchase records."""

    list_display = ['coupon', 'user', 'plan', 'original_amount', 'discount_amount', 'final_amount', 'status',
                    'razorpay_order_id', 'created_at', 'redeemed_at']
    list_filter = ['status', 'plan']
    search_fields = ['coupon__code', 'user__username', 'user__email', 'razorpay_order_id']
    readonly_fields = [f.name for f in CouponRedemption._meta.fields]

    def has_add_permission(self, request):
        return False
