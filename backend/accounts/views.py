"""
accounts/views.py - Authentication and token-management API views.
Endpoints: register, login, profile, token balance, token purchase, token history,
password reset request, and password reset confirm.
Admin users bypass token limits.
"""

import logging

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Avg, Count, Max, Q, Subquery, Sum

from .models import TokenBalance, TokenConfig, TokenTransaction
from .permissions import IsControlTowerAdmin
from .serializers import (
    AdminAuditLogSerializer,
    AdminTokenGrantSerializer,
    AdminTokenTransferSerializer,
    AdminUserTokenSerializer,
    RegisterSerializer,
    TokenBalanceSerializer,
    TokenPurchaseSerializer,
    TokenTransactionSerializer,
    UserSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def create_admin_audit_log(*, actor, action, resource_type, resource_id='', detail='', metadata=None):
    """Best-effort audit logger for sensitive admin operations."""
    try:
        from .models import AdminAuditLog

        AdminAuditLog.objects.create(
            actor=actor if getattr(actor, 'is_authenticated', False) else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id or ''),
            detail=detail,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception('Failed to write admin audit log')


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
    """Legacy local registration endpoint disabled in favor of Supabase Auth."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        return Response(
            {
                "error": "Local username/password registration is disabled. Use Supabase Auth to sign up.",
            },
            status=status.HTTP_410_GONE,
        )


class LoginView(APIView):
    """Local username/email login is disabled. Use Supabase authentication instead."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        return Response(
            {
                'detail': 'Local login is disabled. Please use Supabase authentication at /auth/login.',
                'error': 'endpoint_gone',
            },
            status=status.HTTP_410_GONE,
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

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        create_admin_audit_log(
            actor=request.user,
            action='token_view',
            resource_type='token_overview',
            detail='Viewed platform token overview',
        )
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

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

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
            create_admin_audit_log(
                actor=request.user,
                action='token_grant',
                resource_type='token_balance',
                resource_id=target_user.id,
                detail=f'Granted {amount} tokens to {target_user.username}',
                metadata={'amount': amount, 'target_user_id': target_user.id},
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
        create_admin_audit_log(
            actor=request.user,
            action='token_revoke',
            resource_type='token_balance',
            resource_id=target_user.id,
            detail=f'Revoked {revoke_amount} tokens from {target_user.username}',
            metadata={'amount': revoke_amount, 'target_user_id': target_user.id},
        )
        return Response(
            {
                "message": f"Revoked {revoke_amount} tokens from {target_user.username}",
                "balance": TokenBalanceSerializer(balance).data,
            }
        )


class AdminTokenTransferView(APIView):
    """Transfer tokens between users or grant them from the system."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

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

            create_admin_audit_log(
                actor=request.user,
                action='token_transfer',
                resource_type='token_balance',
                resource_id=to_user.id,
                detail=f'Transferred {amount} tokens from {from_user.username} to {to_user.username}',
                metadata={
                    'amount': amount,
                    'from_user_id': from_user.id,
                    'to_user_id': to_user.id,
                },
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
        create_admin_audit_log(
            actor=request.user,
            action='token_grant',
            resource_type='token_balance',
            resource_id=to_user.id,
            detail=f'Granted {amount} tokens to {to_user.username} (system grant)',
            metadata={'amount': amount, 'target_user_id': to_user.id},
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
            logger.info("Password reset requested for unknown email=%s", email)

        return Response({"message": "If an account with that email exists, a reset link has been sent."})


class AdminAuditLogListView(APIView):
    """List recent admin audit logs for operational traceability."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        from .models import AdminAuditLog

        raw_limit = request.query_params.get('limit', 100)
        try:
            parsed_limit = int(raw_limit)
        except (TypeError, ValueError):
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        if parsed_limit <= 0:
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        limit = min(parsed_limit, 500)
        logs = AdminAuditLog.objects.select_related('actor').all()[:limit]
        serializer = AdminAuditLogSerializer(logs, many=True)
        return Response({'count': len(serializer.data), 'results': serializer.data})


class AdminUserLifecycleListView(APIView):
    """List users with search/filter for lifecycle controls."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        role = (request.query_params.get('role') or '').strip().lower()
        status_filter = (request.query_params.get('status') or '').strip().lower()
        raw_limit = request.query_params.get('limit', 200)
        try:
            limit = min(max(int(raw_limit), 1), 1000)
        except (TypeError, ValueError):
            limit = 200

        queryset = User.objects.all().order_by('-date_joined')
        if q:
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(email__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)
            )
        if role in ['admin', 'student']:
            queryset = queryset.filter(role=role)
        if status_filter == 'blocked':
            queryset = queryset.filter(is_active=False)
        elif status_filter == 'active':
            queryset = queryset.filter(is_active=True)

        users = list(queryset[:limit])
        balances = {
            b.user_id: b
            for b in TokenBalance.objects.filter(user_id__in=[u.id for u in users])
        }
        from tests_engine.models import TestAttempt

        attempt_map = {
            row['user_id']: row['count']
            for row in TestAttempt.objects
            .filter(user_id__in=[u.id for u in users])
            .values('user_id')
            .annotate(count=Count('id'))
        }

        results = []
        for u in users:
            bal = balances.get(u.id)
            available = bal.available_tokens if bal else 0
            results.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'role': u.role,
                'is_active': u.is_active,
                'is_superuser': u.is_superuser,
                'date_joined': u.date_joined,
                'last_login': u.last_login,
                'available_tokens': available,
                'test_attempt_count': attempt_map.get(u.id, 0),
            })

        create_admin_audit_log(
            actor=request.user,
            action='user_view',
            resource_type='user_lifecycle',
            detail='Viewed user lifecycle list',
            metadata={'query': q, 'role': role, 'status': status_filter, 'count': len(results)},
        )
        return Response({'count': len(results), 'results': results})


class AdminUserBlockToggleView(APIView):
    """Block or unblock user account by toggling is_active."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def patch(self, request, user_id):
        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if 'blocked' not in request.data:
            return Response({'error': 'blocked is required'}, status=status.HTTP_400_BAD_REQUEST)

        blocked_raw = request.data.get('blocked')
        if isinstance(blocked_raw, bool):
            blocked = blocked_raw
        elif isinstance(blocked_raw, str):
            normalized = blocked_raw.strip().lower()
            if normalized in ['true', '1', 'yes']:
                blocked = True
            elif normalized in ['false', '0', 'no']:
                blocked = False
            else:
                return Response({'error': 'blocked must be true or false'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'blocked must be true or false'}, status=status.HTTP_400_BAD_REQUEST)

        target.is_active = not blocked
        target.save(update_fields=['is_active'])

        create_admin_audit_log(
            actor=request.user,
            action='user_block',
            resource_type='user',
            resource_id=target.id,
            detail=f"{'Blocked' if blocked else 'Unblocked'} user {target.username}",
            metadata={'blocked': blocked, 'target_user_id': target.id},
        )
        return Response({
            'id': target.id,
            'username': target.username,
            'is_active': target.is_active,
            'blocked': blocked,
        })


class AdminUserRoleUpdateView(APIView):
    """Assign admin/student role to a user."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def patch(self, request, user_id):
        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        role = (request.data.get('role') or '').strip().lower()
        if role not in ['student', 'admin']:
            return Response({'error': "role must be 'student' or 'admin'"}, status=status.HTTP_400_BAD_REQUEST)

        old_role = target.role
        target.role = role
        target.is_superuser = role == 'admin'
        target.is_staff = role == 'admin'
        target.save(update_fields=['role', 'is_superuser', 'is_staff'])

        create_admin_audit_log(
            actor=request.user,
            action='user_role_update',
            resource_type='user',
            resource_id=target.id,
            detail=f'Changed role for {target.username} from {old_role} to {role}',
            metadata={'old_role': old_role, 'new_role': role, 'target_user_id': target.id},
        )
        return Response({'id': target.id, 'username': target.username, 'role': target.role})


class AdminUserResetProgressView(APIView):
    """Reset one user's learning progress while keeping account identity."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request, user_id):
        try:
            target = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        from questions.models import Discussion, Flashcard, Note, QuestionBookmark
        from tests_engine.models import QuestionResponse, TestAttempt
        from analytics.models import DailyActivity, StudyStreak, UserBadge, UserTopicPerformance

        with transaction.atomic():
            attempt_subquery = TestAttempt.objects.filter(user=target).values('id')
            responses_deleted, _ = QuestionResponse.objects.filter(attempt_id__in=Subquery(attempt_subquery)).delete()
            attempts_deleted, _ = TestAttempt.objects.filter(user=target).delete()

            bookmarks_deleted, _ = QuestionBookmark.objects.filter(user=target).delete()
            notes_deleted, _ = Note.objects.filter(user=target).delete()
            flashcards_deleted, _ = Flashcard.objects.filter(user=target).delete()
            discussions_deleted, _ = Discussion.objects.filter(user=target).delete()
            topic_rows_deleted, _ = UserTopicPerformance.objects.filter(user=target).delete()
            daily_rows_deleted, _ = DailyActivity.objects.filter(user=target).delete()
            badges_deleted, _ = UserBadge.objects.filter(user=target).delete()

            StudyStreak.objects.filter(user=target).update(
                current_streak=0,
                longest_streak=0,
                total_study_days=0,
                last_activity_date=None,
                xp_points=0,
            )

        payload = {
            'responses_deleted': responses_deleted,
            'attempts_deleted': attempts_deleted,
            'bookmarks_deleted': bookmarks_deleted,
            'notes_deleted': notes_deleted,
            'flashcards_deleted': flashcards_deleted,
            'discussions_deleted': discussions_deleted,
            'topic_rows_deleted': topic_rows_deleted,
            'daily_rows_deleted': daily_rows_deleted,
            'badges_deleted': badges_deleted,
        }
        transaction.on_commit(
            lambda: create_admin_audit_log(
                actor=request.user,
                action='user_progress_reset',
                resource_type='user',
                resource_id=target.id,
                detail=f'Reset progress for {target.username}',
                metadata=payload,
            )
        )
        return Response({'message': 'User progress reset completed', 'user_id': target.id, 'results': payload})


class AdminSystemResetAttemptsView(APIView):
    """Reset test attempts either scoped to one user or globally."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from tests_engine.models import QuestionResponse, TestAttempt

        scope = (request.data.get('scope') or 'all').strip().lower()
        user_id = request.data.get('user_id')
        parsed_user_id = None

        attempts_qs = TestAttempt.objects.all()
        if scope == 'user':
            if not user_id:
                return Response({'error': 'user_id is required when scope=user'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                return Response({'error': 'user_id must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)
            attempts_qs = attempts_qs.filter(user_id=parsed_user_id)

        with transaction.atomic():
            attempt_subquery = attempts_qs.values('id')
            responses_deleted, _ = QuestionResponse.objects.filter(attempt_id__in=Subquery(attempt_subquery)).delete()
            attempts_deleted, _ = attempts_qs.delete()

        metadata = {
            'scope': scope,
            'user_id': parsed_user_id,
            'attempts_deleted': attempts_deleted,
            'responses_deleted': responses_deleted,
        }
        create_admin_audit_log(
            actor=request.user,
            action='system_attempt_reset',
            resource_type='system',
            detail='Reset test attempts',
            metadata=metadata,
        )
        return Response({'message': 'Test attempts reset completed', 'results': metadata})


class AdminSystemClearAnalyticsView(APIView):
    """Clear analytics rows either scoped to one user or globally."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from analytics.models import DailyActivity, StudyStreak, UserBadge, UserTopicPerformance

        scope = (request.data.get('scope') or 'all').strip().lower()
        user_id = request.data.get('user_id')
        parsed_user_id = None

        topic_qs = UserTopicPerformance.objects.all()
        daily_qs = DailyActivity.objects.all()
        badge_qs = UserBadge.objects.all()
        streak_qs = StudyStreak.objects.all()

        if scope == 'user':
            if not user_id:
                return Response({'error': 'user_id is required when scope=user'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                return Response({'error': 'user_id must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)
            topic_qs = topic_qs.filter(user_id=parsed_user_id)
            daily_qs = daily_qs.filter(user_id=parsed_user_id)
            badge_qs = badge_qs.filter(user_id=parsed_user_id)
            streak_qs = streak_qs.filter(user_id=parsed_user_id)

        with transaction.atomic():
            topic_rows_deleted, _ = topic_qs.delete()
            daily_rows_deleted, _ = daily_qs.delete()
            badge_rows_deleted, _ = badge_qs.delete()
            streak_rows_reset = streak_qs.update(
                current_streak=0,
                longest_streak=0,
                total_study_days=0,
                last_activity_date=None,
                xp_points=0,
            )

        metadata = {
            'scope': scope,
            'user_id': parsed_user_id,
            'topic_rows_deleted': topic_rows_deleted,
            'daily_rows_deleted': daily_rows_deleted,
            'badge_rows_deleted': badge_rows_deleted,
            'streak_rows_reset': streak_rows_reset,
        }
        transaction.on_commit(
            lambda: create_admin_audit_log(
                actor=request.user,
                action='system_analytics_clear',
                resource_type='system',
                detail='Cleared analytics rows',
                metadata=metadata,
            )
        )
        return Response({'message': 'Analytics clear completed', 'results': metadata})


class AdminSystemRerunEvaluationView(APIView):
    """Recompute UserTopicPerformance from submitted question responses."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from analytics.models import UserTopicPerformance
        from tests_engine.models import QuestionResponse

        scope = (request.data.get('scope') or 'all').strip().lower()
        user_id = request.data.get('user_id')
        parsed_user_id = None

        responses = QuestionResponse.objects.select_related('attempt__user', 'question__subject', 'question__topic').all()
        if scope == 'user':
            if not user_id:
                return Response({'error': 'user_id is required when scope=user'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                return Response({'error': 'user_id must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)
            responses = responses.filter(attempt__user_id=parsed_user_id)

        aggregated_rows = list(
            responses
            .values('attempt__user_id', 'question__subject_id', 'question__topic_id')
            .annotate(
                total_attempts=Count('id'),
                correct_answers=Count('id', filter=Q(is_correct=True)),
                incorrect_answers=Count('id', filter=Q(is_correct=False)),
                total_time_seconds=Sum('time_taken_seconds'),
                avg_confidence=Avg('confidence_level'),
                last_attempted=Max('attempt__started_at'),
            )
        )

        with transaction.atomic():
            if scope == 'all':
                UserTopicPerformance.objects.all().delete()
            else:
                UserTopicPerformance.objects.filter(user_id=parsed_user_id).delete()

            UserTopicPerformance.objects.bulk_create([
                UserTopicPerformance(
                    user_id=row['attempt__user_id'],
                    subject_id=row['question__subject_id'],
                    topic_id=row['question__topic_id'],
                    total_attempts=row['total_attempts'] or 0,
                    correct_answers=row['correct_answers'] or 0,
                    incorrect_answers=row['incorrect_answers'] or 0,
                    total_time_seconds=row['total_time_seconds'] or 0,
                    avg_confidence=float(row['avg_confidence'] or 0),
                    last_attempted=row['last_attempted'],
                )
                for row in aggregated_rows
            ])

        metadata = {
            'scope': scope,
            'user_id': parsed_user_id,
            'rows_created': len(aggregated_rows),
            'processed_responses': sum(row['total_attempts'] for row in aggregated_rows),
        }
        create_admin_audit_log(
            actor=request.user,
            action='system_rerun_evaluation',
            resource_type='system',
            detail='Reran evaluation aggregation',
            metadata=metadata,
        )
        return Response({'message': 'Evaluation rerun completed', 'results': metadata})


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
