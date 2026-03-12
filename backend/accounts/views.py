"""
accounts/views.py — Authentication & Token Management API views.
Endpoints: Register, Login, Profile, Token Balance, Token Purchase, Token History,
           Password Reset (request + confirm).
Admin users bypass all token limits.
"""
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings as django_settings
from .serializers import (
    RegisterSerializer, UserSerializer, LoginSerializer,
    TokenBalanceSerializer, TokenPurchaseSerializer, TokenTransactionSerializer,
    AdminTokenTransferSerializer, AdminTokenGrantSerializer, AdminUserTokenSerializer,
)
from .models import TokenBalance, TokenConfig, TokenTransaction

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Register a new user account. Auto-creates token balance."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Login with username and password, returns JWT tokens + token balance."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Ensure token balance exists
        TokenBalance.objects.get_or_create(user=user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the current user profile (includes token info)."""
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TokenBalanceView(APIView):
    """
    GET: Return current user's token balance & limits.
    Used by the frontend to show remaining tokens.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        balance, _ = TokenBalance.objects.get_or_create(user=request.user)
        serializer = TokenBalanceSerializer(balance)
        return Response(serializer.data)


class TokenPurchaseView(APIView):
    """
    POST: Purchase tokens. In production, integrate with payment gateway (Razorpay/Stripe).
    For now, accepts payment_id and amount to credit tokens.
    
    Body: { "amount": 50, "payment_id": "pay_xxx" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TokenPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        payment_id = serializer.validated_data.get('payment_id', '')
        config = TokenConfig.get_config()
        price = float(config.token_price) * amount

        # TODO: In production, verify payment_id with Razorpay/Stripe API here
        # For now, we trust the payment_id and credit tokens directly

        balance, _ = TokenBalance.objects.get_or_create(user=request.user)
        balance.add_purchased_tokens(amount)

        # Record the transaction
        TokenTransaction.objects.create(
            user=request.user,
            transaction_type='purchase',
            amount=amount,
            price_paid=price,
            payment_id=payment_id,
            note=f'Purchased {amount} tokens at ₹{config.token_price}/token',
        )

        return Response({
            'message': f'{amount} tokens added successfully!',
            'balance': TokenBalanceSerializer(balance).data,
        })


class TokenTransactionHistoryView(APIView):
    """GET: Return user's token transaction history."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        transactions = TokenTransaction.objects.filter(user=request.user)[:50]
        serializer = TokenTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


# ─── SUPER ADMIN TOKEN MANAGEMENT ───────────────────────

class AdminTokenOverviewView(APIView):
    """
    GET: Super admin view — all users' token balances + platform totals.
    Shows total tokens in circulation, per-user breakdown, daily API call budget.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        balances = TokenBalance.objects.select_related('user').all()
        serializer = AdminUserTokenSerializer(balances, many=True)
        config = TokenConfig.get_config()

        # Platform-wide token stats
        total_users = User.objects.count()
        total_purchased = sum(b.purchased_tokens for b in balances)
        total_feedback = sum(b.feedback_credits for b in balances)
        total_consumed = sum(b.total_tokens_used for b in balances)
        total_available = sum(b.available_tokens for b in balances)

        return Response({
            'platform_stats': {
                'total_users': total_users,
                'total_purchased_tokens': total_purchased,
                'total_feedback_credits': total_feedback,
                'total_tokens_consumed': total_consumed,
                'total_available_tokens': total_available,
                'free_daily_per_user': config.free_daily_tokens,
                'free_weekly_per_user': config.free_weekly_tokens,
                'max_free_daily_calls': total_users * config.free_daily_tokens,
                'max_free_weekly_calls': total_users * config.free_weekly_tokens,
                'api_budget': {
                    'gemini_daily_limit': 6000,
                    'groq_daily_limit': 14400,
                    'deepseek_daily_limit': 'pay-as-you-go',
                    'combined_daily_capacity': 20400,
                    'note': 'Gemini: 4 models x 1500 RPD each. Groq: 14400 RPD. DeepSeek: unlimited (paid).',
                },
            },
            'users': serializer.data,
        })


class AdminTokenGrantView(APIView):
    """
    POST: Super admin grants or revokes tokens for a specific user.
    Body: { "user_id": 5, "amount": 50, "note": "Bonus for being active" }
    Use negative amount to revoke tokens.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdminTokenGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        amount = serializer.validated_data['amount']
        note = serializer.validated_data.get('note', '')

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': f'User ID {user_id} not found'}, status=404)

        balance, _ = TokenBalance.objects.get_or_create(user=target_user)

        if amount > 0:
            balance.add_purchased_tokens(amount)
            TokenTransaction.objects.create(
                user=target_user,
                transaction_type='admin_grant',
                amount=amount,
                note=note or f'Admin granted {amount} tokens',
            )
            return Response({
                'message': f'Granted {amount} tokens to {target_user.username}',
                'balance': TokenBalanceSerializer(balance).data,
            })
        else:
            # Revoke (negative amount)
            revoke_amount = abs(amount)
            balance.purchased_tokens = max(0, balance.purchased_tokens - revoke_amount)
            balance.save(update_fields=['purchased_tokens'])
            TokenTransaction.objects.create(
                user=target_user,
                transaction_type='admin_revoke',
                amount=-revoke_amount,
                note=note or f'Admin revoked {revoke_amount} tokens',
            )
            return Response({
                'message': f'Revoked {revoke_amount} tokens from {target_user.username}',
                'balance': TokenBalanceSerializer(balance).data,
            })


class AdminTokenTransferView(APIView):
    """
    POST: Super admin transfers tokens between users.
    Body: { "from_user_id": 5, "to_user_id": 8, "amount": 20, "note": "..." }
    If from_user_id is omitted, tokens are created (granted from system).
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdminTokenTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user_id = serializer.validated_data['to_user_id']
        amount = serializer.validated_data['amount']
        note = serializer.validated_data.get('note', '')
        from_user_id = serializer.validated_data.get('from_user_id')

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({'error': f'Target user ID {to_user_id} not found'}, status=404)

        to_balance, _ = TokenBalance.objects.get_or_create(user=to_user)

        if from_user_id:
            try:
                from_user = User.objects.get(id=from_user_id)
            except User.DoesNotExist:
                return Response({'error': f'Source user ID {from_user_id} not found'}, status=404)

            from_balance, _ = TokenBalance.objects.get_or_create(user=from_user)

            if from_balance.purchased_tokens < amount:
                return Response({
                    'error': f'{from_user.username} only has {from_balance.purchased_tokens} purchased tokens'
                }, status=400)

            # Deduct from source
            from_balance.purchased_tokens -= amount
            from_balance.save(update_fields=['purchased_tokens'])
            TokenTransaction.objects.create(
                user=from_user,
                transaction_type='admin_transfer',
                amount=-amount,
                note=note or f'Admin transferred {amount} tokens to {to_user.username}',
            )

            # Add to target
            to_balance.add_purchased_tokens(amount)
            TokenTransaction.objects.create(
                user=to_user,
                transaction_type='admin_transfer',
                amount=amount,
                note=note or f'Admin transferred {amount} tokens from {from_user.username}',
            )

            return Response({
                'message': f'Transferred {amount} tokens from {from_user.username} to {to_user.username}',
                'from_balance': TokenBalanceSerializer(from_balance).data,
                'to_balance': TokenBalanceSerializer(to_balance).data,
            })
        else:
            # System grant (no source)
            to_balance.add_purchased_tokens(amount)
            TokenTransaction.objects.create(
                user=to_user,
                transaction_type='admin_grant',
                amount=amount,
                note=note or f'Admin granted {amount} tokens (system)',
            )
            return Response({
                'message': f'Granted {amount} tokens to {to_user.username}',
                'to_balance': TokenBalanceSerializer(to_balance).data,
            })


class PasswordResetRequestView(APIView):
    """Request a password reset email. Sends a link with UID + token."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        # Always return success to avoid user enumeration
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:3000')
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            send_mail(
                subject='CrackCMS — Reset Your Password',
                message=f'Hi {user.first_name or user.username},\n\nClick here to reset your password:\n{reset_link}\n\nThis link expires in 24 hours.\n\n— CrackCMS Team',
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except User.DoesNotExist:
            pass  # Silent — prevent email enumeration
        return Response({'message': 'If an account with that email exists, a reset link has been sent.'})


class PasswordResetConfirmView(APIView):
    """Confirm password reset with UID, token, and new password."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get('uid', '')
        token = request.data.get('token', '')
        new_password = request.data.get('new_password', '')
        if not uid or not token or not new_password:
            return Response({'error': 'uid, token, and new_password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, token):
            return Response({'error': 'Reset link has expired or is invalid.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'message': 'Password has been reset successfully.'})
