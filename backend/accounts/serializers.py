from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import DatabaseError
from .models import TokenBalance, TokenConfig, TokenTransaction
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

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'role', 'target_exam', 'target_year', 'avatar_url',
                  'created_at', 'is_admin', 'token_info']
        read_only_fields = ['id', 'role', 'created_at', 'token_info']

    def get_role(self, obj):
        return 'admin' if obj.is_admin else 'student'

    def get_is_admin(self, obj):
        return obj.is_admin

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
