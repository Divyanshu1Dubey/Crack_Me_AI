"""
accounts/views.py - Authentication and token-management API views.
Endpoints: register, login, profile, token balance, token purchase, token history,
password reset request, and password reset confirm.
Admin users bypass token limits.
"""

import logging
from threading import Lock

from django.conf import settings as django_settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.core.management import call_command
from django.db import DatabaseError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TokenBalance, TokenConfig, TokenTransaction
from .serializers import (
    AdminTokenGrantSerializer,
    AdminTokenTransferSerializer,
    AdminUserTokenSerializer,
    LoginSerializer,
    RegisterSerializer,
    TokenBalanceSerializer,
    TokenPurchaseSerializer,
    TokenTransactionSerializer,
    UserSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)
_SCHEMA_REPAIR_LOCK = Lock()


def _is_schema_db_error(exc):
    """Detect table/column migration drift errors from SQLite/PostgreSQL."""
    message = str(exc).lower()
    hints = (
        "no such table",
        "no such column",
        "relation",
        "does not exist",
        "undefined table",
        "undefined column",
        "has no column named",
    )
    return any(hint in message for hint in hints)


def _repair_schema_if_needed(exc):
    """Run migrations once when auth endpoints hit schema-missing errors."""
    if not _is_schema_db_error(exc):
        return False

    if not getattr(django_settings, "ENABLE_RUNTIME_SCHEMA_REPAIR", False):
        logger.warning(
            "Schema error detected but runtime repair is disabled. "
            "Run `python manage.py migrate` on the backend host."
        )
        return False

    with _SCHEMA_REPAIR_LOCK:
        try:
            logger.warning("Schema error detected in auth flow. Running migrate once.")
            call_command("migrate", interactive=False, verbosity=0)
            return True
        except Exception:
            logger.exception("Runtime schema repair failed")
            return False


def _fallback_authenticate(identifier, password):
    """Try case-insensitive username/email auth for valid credentials."""
    ident = (identifier or "").strip()
    if not ident or not password:
        return None

    user = User.objects.filter(username__iexact=ident).first()
    if user is None and "@" in ident:
        user = User.objects.filter(email__iexact=ident).first()

    if user and user.is_active and user.check_password(password):
        return user
    return None


def build_auth_response(user):
    """Return a backwards-compatible auth payload for frontend and tests."""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    return {
        "user": UserSerializer(user).data,
        "tokens": {
            "refresh": refresh_token,
            "access": access_token,
        },
        "refresh": refresh_token,
        "access": access_token,
    }


def send_password_reset_email(user, reset_link):
    """Send a branded password reset email."""
    display_name = user.first_name or user.username
    subject = "CrackCMS | Reset your password"
    text_body = (
        f"Hi {display_name},\n\n"
        "We received a request to reset your CrackCMS password.\n\n"
        f"Reset your password here:\n{reset_link}\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "CrackCMS Team"
    )
    html_body = f"""
    <div style="background:#f4f7fb;padding:32px 16px;font-family:Arial,sans-serif;color:#142334;">
      <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #d5e0eb;border-radius:24px;overflow:hidden;">
        <div style="padding:32px;background:linear-gradient(135deg,#0b728f 0%,#0f766e 55%,#f59e0b 100%);color:#ffffff;">
          <p style="margin:0 0 10px;font-size:12px;letter-spacing:0.18em;text-transform:uppercase;opacity:0.8;">CrackCMS Account Security</p>
          <h1 style="margin:0;font-size:28px;line-height:1.1;">Reset your password</h1>
          <p style="margin:14px 0 0;font-size:15px;line-height:1.6;opacity:0.9;">
            Keep your UPSC CMS preparation moving with a secure reset link.
          </p>
        </div>
        <div style="padding:32px;">
          <p style="margin:0 0 16px;font-size:15px;line-height:1.7;">Hi {display_name},</p>
          <p style="margin:0 0 20px;font-size:15px;line-height:1.7;">
            We received a request to reset your CrackCMS password. Use the button below to choose a new one.
          </p>
          <p style="margin:0 0 24px;">
            <a href="{reset_link}" style="display:inline-block;padding:14px 20px;border-radius:14px;background:#0b728f;color:#ffffff;text-decoration:none;font-weight:700;">
              Reset Password
            </a>
          </p>
          <p style="margin:0 0 12px;font-size:13px;line-height:1.7;color:#5b6f85;">
            If the button does not open, copy this link into your browser:
          </p>
          <p style="margin:0 0 20px;font-size:13px;line-height:1.7;word-break:break-word;color:#14586a;">
            {reset_link}
          </p>
          <p style="margin:0;font-size:13px;line-height:1.7;color:#5b6f85;">
            If you did not request this reset, you can safely ignore this email.
          </p>
        </div>
      </div>
    </div>
    """
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)


class RegisterView(generics.CreateAPIView):
    """Register a new user account and auto-create token balance."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        for attempt in range(2):
            try:
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                user = serializer.save()
                return Response(build_auth_response(user), status=status.HTTP_201_CREATED)
            except DatabaseError as exc:
                logger.exception("Register DB error (attempt=%s)", attempt + 1)
                if attempt == 0 and _repair_schema_if_needed(exc):
                    continue
                return Response(
                    {"error": "Server database is not ready. Please try again in a minute."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )


class LoginView(APIView):
    """Login with username and password and return JWT tokens."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        for attempt in range(2):
            try:
                serializer = LoginSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                username_or_email = serializer.validated_data["username"]
                password = serializer.validated_data["password"]
                user = authenticate(
                    request,
                    username=username_or_email,
                    password=password,
                )

                if not user:
                    user = _fallback_authenticate(username_or_email, password)

                if not user:
                    return Response(
                        {"error": "Invalid credentials"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                try:
                    TokenBalance.objects.get_or_create(user=user)
                except DatabaseError as exc:
                    logger.exception("Token tables unavailable during login for user=%s", user.id)
                    if attempt == 0 and _repair_schema_if_needed(exc):
                        continue

                return Response(build_auth_response(user))
            except DatabaseError as exc:
                logger.exception("Login DB error (attempt=%s)", attempt + 1)
                if attempt == 0 and _repair_schema_if_needed(exc):
                    continue
                return Response(
                    {"error": "Server database is not ready. Please try again in a minute."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the current user profile."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TokenBalanceView(APIView):
    """Return the current user's token balance and limits."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        balance, _ = TokenBalance.objects.get_or_create(user=request.user)
        serializer = TokenBalanceSerializer(balance)
        return Response(serializer.data)


class TokenPurchaseView(APIView):
    """
    POST: Purchase tokens. In production, integrate with a payment gateway.
    For now, the endpoint accepts payment_id and amount and credits tokens directly.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TokenPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data["amount"]
        payment_id = serializer.validated_data.get("payment_id", "")
        config = TokenConfig.get_config()
        price = float(config.token_price) * amount

        balance, _ = TokenBalance.objects.get_or_create(user=request.user)
        balance.add_purchased_tokens(amount)

        TokenTransaction.objects.create(
            user=request.user,
            transaction_type="purchase",
            amount=amount,
            price_paid=price,
            payment_id=payment_id,
            note=f"Purchased {amount} tokens at INR {config.token_price}/token",
        )

        return Response(
            {
                "message": f"{amount} tokens added successfully!",
                "balance": TokenBalanceSerializer(balance).data,
            }
        )


class TokenTransactionHistoryView(APIView):
    """Return the user's recent token transactions."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        transactions = TokenTransaction.objects.filter(user=request.user)[:50]
        serializer = TokenTransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class AdminTokenOverviewView(APIView):
    """Super-admin view with platform token totals and user balances."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        balances = TokenBalance.objects.select_related("user").all()
        serializer = AdminUserTokenSerializer(balances, many=True)
        config = TokenConfig.get_config()

        total_users = User.objects.count()
        total_purchased = sum(b.purchased_tokens for b in balances)
        total_feedback = sum(b.feedback_credits for b in balances)
        total_consumed = sum(b.total_tokens_used for b in balances)
        total_available = sum(b.available_tokens for b in balances)

        return Response(
            {
                "platform_stats": {
                    "total_users": total_users,
                    "total_purchased_tokens": total_purchased,
                    "total_feedback_credits": total_feedback,
                    "total_tokens_consumed": total_consumed,
                    "total_available_tokens": total_available,
                    "free_daily_per_user": config.free_daily_tokens,
                    "free_weekly_per_user": config.free_weekly_tokens,
                    "max_free_daily_calls": total_users * config.free_daily_tokens,
                    "max_free_weekly_calls": total_users * config.free_weekly_tokens,
                    "api_budget": {
                        "gemini_daily_limit": 6000,
                        "groq_daily_limit": 14400,
                        "deepseek_daily_limit": "pay-as-you-go",
                        "combined_daily_capacity": 20400,
                        "note": "Gemini: 4 models x 1500 RPD each. Groq: 14400 RPD. DeepSeek: unlimited (paid).",
                    },
                },
                "users": serializer.data,
            }
        )


class AdminTokenGrantView(APIView):
    """Grant or revoke tokens for a specific user."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdminTokenGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        amount = serializer.validated_data["amount"]
        note = serializer.validated_data.get("note", "")

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": f"User ID {user_id} not found"}, status=404)

        balance, _ = TokenBalance.objects.get_or_create(user=target_user)

        if amount > 0:
            balance.add_purchased_tokens(amount)
            TokenTransaction.objects.create(
                user=target_user,
                transaction_type="admin_grant",
                amount=amount,
                note=note or f"Admin granted {amount} tokens",
            )
            return Response(
                {
                    "message": f"Granted {amount} tokens to {target_user.username}",
                    "balance": TokenBalanceSerializer(balance).data,
                }
            )

        revoke_amount = abs(amount)
        balance.purchased_tokens = max(0, balance.purchased_tokens - revoke_amount)
        balance.save(update_fields=["purchased_tokens"])
        TokenTransaction.objects.create(
            user=target_user,
            transaction_type="admin_revoke",
            amount=-revoke_amount,
            note=note or f"Admin revoked {revoke_amount} tokens",
        )
        return Response(
            {
                "message": f"Revoked {revoke_amount} tokens from {target_user.username}",
                "balance": TokenBalanceSerializer(balance).data,
            }
        )


class AdminTokenTransferView(APIView):
    """Transfer tokens between users or grant them from the system."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdminTokenTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user_id = serializer.validated_data["to_user_id"]
        amount = serializer.validated_data["amount"]
        note = serializer.validated_data.get("note", "")
        from_user_id = serializer.validated_data.get("from_user_id")

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({"error": f"Target user ID {to_user_id} not found"}, status=404)

        to_balance, _ = TokenBalance.objects.get_or_create(user=to_user)

        if from_user_id:
            try:
                from_user = User.objects.get(id=from_user_id)
            except User.DoesNotExist:
                return Response({"error": f"Source user ID {from_user_id} not found"}, status=404)

            from_balance, _ = TokenBalance.objects.get_or_create(user=from_user)

            if from_balance.purchased_tokens < amount:
                return Response(
                    {"error": f"{from_user.username} only has {from_balance.purchased_tokens} purchased tokens"},
                    status=400,
                )

            from_balance.purchased_tokens -= amount
            from_balance.save(update_fields=["purchased_tokens"])
            TokenTransaction.objects.create(
                user=from_user,
                transaction_type="admin_transfer",
                amount=-amount,
                note=note or f"Admin transferred {amount} tokens to {to_user.username}",
            )

            to_balance.add_purchased_tokens(amount)
            TokenTransaction.objects.create(
                user=to_user,
                transaction_type="admin_transfer",
                amount=amount,
                note=note or f"Admin transferred {amount} tokens from {from_user.username}",
            )

            return Response(
                {
                    "message": f"Transferred {amount} tokens from {from_user.username} to {to_user.username}",
                    "from_balance": TokenBalanceSerializer(from_balance).data,
                    "to_balance": TokenBalanceSerializer(to_balance).data,
                }
            )

        to_balance.add_purchased_tokens(amount)
        TokenTransaction.objects.create(
            user=to_user,
            transaction_type="admin_grant",
            amount=amount,
            note=note or f"Admin granted {amount} tokens (system)",
        )
        return Response(
            {
                "message": f"Granted {amount} tokens to {to_user.username}",
                "to_balance": TokenBalanceSerializer(to_balance).data,
            }
        )


class PasswordResetRequestView(APIView):
    """Request a password reset email. Sends a link with uid and token."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend_url = getattr(django_settings, "FRONTEND_URL", "http://localhost:3000")
            reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
            try:
                send_password_reset_email(user, reset_link)
            except Exception as exc:
                logger.warning("Password reset email failed for user_id=%s: %s", user.pk, exc)
        except User.DoesNotExist:
            pass

        return Response({"message": "If an account with that email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    """Confirm password reset with uid, token, and new password."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("new_password", "")
        if not uid or not token or not new_password:
            return Response(
                {"error": "uid, token, and new_password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response(
                {"error": "Reset link has expired or is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except Exception as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else "Password is too weak."
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password has been reset successfully."})
