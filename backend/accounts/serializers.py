from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import DatabaseError
from .models import AdminAuditLog, TokenBalance, TokenConfig, TokenTransaction
from .supabase_auth import sync_user_to_supabase_auth

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password2',
                  'first_name', 'last_name', 'phone', 'target_exam', 'target_year']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        validate_password(data['password'])
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        raw_password = validated_data.get('password', '')
        user = User.objects.create_user(**validated_data)

        # Optional: mirror user into Supabase Auth so it appears in Supabase Auth > Users.
        # Requires SUPABASE_AUTH_MIRROR_ENABLED=true and service-role credentials.
        try:
            sync_user_to_supabase_auth(
                email=user.email,
                password=raw_password,
                username=user.username,
            )
        except Exception:
            # Registration should remain successful even if Supabase mirror fails.
            pass

        # Auto-create token balance for new users
        try:
            TokenBalance.objects.get_or_create(user=user)
        except DatabaseError:
            # Keep registration functional even if token tables are not migrated yet.
            pass
        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile — includes token balance info."""
    role = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    token_info = serializers.SerializerMethodField()
    subscription_info = serializers.SerializerMethodField()

    is_online = serializers.SerializerMethodField()
    # Freemium conversion layer (Task 9): exposes per-user AI tutor daily
    # counter + per-year showcase quota so the frontend can render the
    # <UsageBanner> "X/2 AI chats used today" copy and the question bank
    # can show the showcase progress badge.
    ai_tutor_used_today = serializers.SerializerMethodField()
    ai_tutor_daily_cap = serializers.SerializerMethodField()
    showcase_questions_remaining = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'college', 'role', 'target_exam', 'target_year', 'avatar_url',
                  'created_at', 'is_admin', 'token_info', 'profile_bonus_rewarded', 'is_subscribed',
                  'scholarship_test_passed', 'scholarship_test_attempts', 'scholarship_granted_price',
                  'subscription_info', 'last_seen', 'is_online',
                  'ai_tutor_used_today', 'ai_tutor_daily_cap',
                  'showcase_questions_remaining', 'is_premium']
        read_only_fields = ['id', 'username', 'email', 'role', 'created_at', 'token_info', 'profile_bonus_rewarded', 'is_subscribed', 'scholarship_test_passed', 'scholarship_test_attempts', 'scholarship_granted_price', 'subscription_info', 'last_seen', 'is_online', 'ai_tutor_used_today', 'ai_tutor_daily_cap', 'showcase_questions_remaining', 'is_premium']

    def get_is_online(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        if obj.last_seen:
            return (timezone.now() - obj.last_seen) < timedelta(minutes=10)
        return False

    def get_role(self, obj):
        return 'admin' if obj.is_admin else 'student'

    def get_is_admin(self, obj):
        return obj.is_admin

    def get_subscription_info(self, obj):
        """Return current subscription details for the user."""
        from .models import Subscription
        sub = Subscription.get_active_subscription(obj)
        if sub:
            return {
                'plan': sub.plan,
                'plan_display_name': sub.plan_display_name,
                'status': sub.status,
                'is_active': sub.is_active,
                'starts_at': sub.starts_at.isoformat() if sub.starts_at else None,
                'expires_at': sub.expires_at.isoformat() if sub.expires_at else None,
                'days_remaining': sub.days_remaining,
                'amount_paid': float(sub.amount_paid),
            }
        # Backward compat: grandfathered lifetime user
        if obj.is_subscribed:
            return {
                'plan': 'legacy',
                'plan_display_name': 'Legacy Early Bird (Lifetime)',
                'status': 'active',
                'is_active': True,
                'starts_at': obj.created_at.isoformat() if obj.created_at else None,
                'expires_at': None,
                'days_remaining': -1,
                'amount_paid': 0,
            }
        return None

    def get_token_info(self, obj):
        """Return current token balance summary for the user."""
        try:
            balance, _ = TokenBalance.objects.get_or_create(user=obj)
            config = TokenConfig.get_config()
        except DatabaseError:
            return {
                'available': 0,
                'purchased': 0,
                'feedback_credits': 0,
                'daily_used': 0,
                'weekly_used': 0,
                'daily_limit': 0,
                'weekly_limit': 0,
                'total_used': 0,
                'is_admin': obj.is_admin,
            }
        return {
            'available': balance.available_tokens,
            'purchased': balance.purchased_tokens,
            'feedback_credits': balance.feedback_credits,
            'daily_used': balance.daily_tokens_used,
            'weekly_used': balance.weekly_tokens_used,
            'daily_limit': config.free_daily_tokens,
            'weekly_limit': config.free_weekly_tokens,
            'total_used': balance.total_tokens_used,
            'is_admin': obj.is_admin,
        }

    # ── Freemium conversion layer (Task 9) ───────────────────────────
    def get_is_premium(self, obj):
        """True if the user has any active subscription OR is admin/staff.

        Mirrors `accounts.utils.is_premium()` — exposed inline here so the
        frontend can gate render logic without making a second API call.
        Admins and lifetime subscribers always read as premium.
        """
        try:
            from .utils import is_premium
            return bool(is_premium(obj))
        except Exception:
            # Never let a freemium payload crash the profile fetch.
            return bool(getattr(obj, 'is_admin', False))

    def get_ai_tutor_used_today(self, obj):
        """Today's AI tutor message count for this user (0 if no row).

        Premium and admin users always read as 0 so the soft banner's
        progress copy (`X/2`) is hidden — they are unlimited.
        """
        try:
            from ai_engine.models_usage import get_today_usage
            if self.get_is_premium(obj):
                return 0
            return int(get_today_usage(obj))
        except Exception:
            # Never break profile fetch on freemium telemetry lookup.
            return 0

    def get_ai_tutor_daily_cap(self, obj):
        """Daily AI tutor cap for this user. Premium and admin → None (unlimited)."""
        try:
            from ai_engine.views import AI_TUTOR_DAILY_FREE_CAP
            if self.get_is_premium(obj):
                return None
            return int(AI_TUTOR_DAILY_FREE_CAP)
        except Exception:
            return 2

    def get_showcase_questions_remaining(self, obj):
        """Count of FreeShowcaseQuestion rows per year for the user's track.

        Premium users → None (they see the full bank, no per-year cap).
        Free users → 10 (the admin-curated ceiling — UI can refine per year).
        """
        try:
            if self.get_is_premium(obj):
                return None
            from accounts.models_freemium import FreeShowcaseQuestion
            # 10/year is the admin-curated ceiling. We just confirm at least
            # one year has been curated; if not, surface 0 so the banner can
            # prompt "no showcase for your track yet — subscribe for full PYQ".
            return int(FreeShowcaseQuestion.objects.values('year').distinct().count() and 10)
        except Exception:
            return 10


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class TokenBalanceSerializer(serializers.ModelSerializer):
    """Full token balance details for the settings/token page."""
    available = serializers.IntegerField(source='available_tokens', read_only=True)
    daily_limit = serializers.SerializerMethodField()
    weekly_limit = serializers.SerializerMethodField()
    token_price = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = TokenBalance
        fields = ['available', 'purchased_tokens', 'feedback_credits',
                  'daily_tokens_used', 'weekly_tokens_used', 'total_tokens_used',
                  'daily_limit', 'weekly_limit', 'token_price', 'is_admin']

    def get_daily_limit(self, obj):
        return TokenConfig.get_config().free_daily_tokens

    def get_weekly_limit(self, obj):
        return TokenConfig.get_config().free_weekly_tokens

    def get_token_price(self, obj):
        return float(TokenConfig.get_config().token_price)

    def get_is_admin(self, obj):
        return obj.user.is_admin


class TokenPurchaseSerializer(serializers.Serializer):
    """Validates token purchase requests."""
    amount = serializers.IntegerField(min_value=1)
    payment_id = serializers.CharField(max_length=200, required=False, default='')

    def validate_amount(self, value):
        config = TokenConfig.get_config()
        if value < config.min_purchase:
            raise serializers.ValidationError(f"Minimum purchase is {config.min_purchase} tokens.")
        if value > config.max_purchase:
            raise serializers.ValidationError(f"Maximum purchase is {config.max_purchase} tokens.")
        return value


class TokenTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenTransaction
        fields = ['id', 'transaction_type', 'amount', 'price_paid', 'note', 'created_at']


# ─── ADMIN-ONLY SERIALIZERS ─────────────────────────────

class AdminTokenTransferSerializer(serializers.Serializer):
    """Validates admin token transfer requests (take from one user, give to another)."""
    from_user_id = serializers.IntegerField(required=False, help_text='User to take tokens from (optional)')
    to_user_id = serializers.IntegerField(help_text='User to give tokens to')
    amount = serializers.IntegerField(min_value=1, help_text='Number of tokens to transfer')
    note = serializers.CharField(max_length=500, required=False, default='')


class AdminTokenGrantSerializer(serializers.Serializer):
    """Validates admin token grant/revoke requests."""
    user_id = serializers.IntegerField(help_text='Target user ID')
    amount = serializers.IntegerField(help_text='Tokens to grant (positive) or revoke (negative)')
    note = serializers.CharField(max_length=500, required=False, default='')


class AdminUserTokenSerializer(serializers.ModelSerializer):
    """Shows a user's token info for the admin dashboard."""
    user_id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    email = serializers.CharField(source='user.email')
    is_admin = serializers.BooleanField(source='user.is_admin')
    available = serializers.IntegerField(source='available_tokens', read_only=True)

    class Meta:
        model = TokenBalance
        fields = ['user_id', 'username', 'email', 'is_admin', 'available', 'purchased_tokens',
                  'feedback_credits', 'daily_tokens_used', 'weekly_tokens_used',
                  'total_tokens_used']


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AdminAuditLog
        fields = [
            'id',
            'actor',
            'actor_username',
            'action',
            'resource_type',
            'resource_id',
            'detail',
            'metadata',
            'created_at',
        ]


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import UserDevice
        model = UserDevice
        fields = ['id', 'device_name', 'browser', 'ip_address', 'last_login', 'is_active', 'created_at']

