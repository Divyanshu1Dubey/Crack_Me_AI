from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TokenBalance, TokenConfig, TokenTransaction


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'target_exam', 'is_active']
    list_filter = ['role', 'target_exam', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('CMS Profile', {'fields': ('role', 'phone', 'target_exam', 'target_year', 'avatar_url')}),
    )


@admin.register(TokenBalance)
class TokenBalanceAdmin(admin.ModelAdmin):
    """Admin view for managing user token balances."""
    list_display = ['user', 'available_tokens_display', 'purchased_tokens', 'feedback_credits',
                    'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used']
    list_filter = ['last_daily_reset']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['total_tokens_used', 'created_at', 'updated_at']

    def available_tokens_display(self, obj):
        return obj.available_tokens
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
