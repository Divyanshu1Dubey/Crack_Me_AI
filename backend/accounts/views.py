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

from .models import TokenBalance, TokenConfig, TokenTransaction, Subscription
from questions.models import Question
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
    <div style="background:#e8f0fe;padding:32px 16px;font-family:Arial,sans-serif;color:#142334;">
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

    def perform_update(self, serializer):
        user = serializer.save()
        # Reward 10 tokens once when BOTH phone and college are filled
        if user.phone and user.college and not user.profile_bonus_rewarded:
            user.profile_bonus_rewarded = True
            user.save(update_fields=['profile_bonus_rewarded'])
            
            # Get or create token balance
            balance, _ = TokenBalance.objects.get_or_create(user=user)
            # Reward tokens as feedback_credits
            balance.feedback_credits += 10
            balance.save(update_fields=['feedback_credits'])
            
            # Create transaction audit record
            TokenTransaction.objects.create(
                user=user,
                transaction_type="feedback_reward",
                amount=10,
                price_paid=0.00,
                note="Bonus for completing profile with mobile number and college name"
            )


class SubscribeView(APIView):
    """Activate ₹199 premium subscription for the user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_subscribed:
            return Response(
                {"error": "You are already subscribed to the Premium plan."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_subscribed = True
        user.save(update_fields=['is_subscribed'])
        
        # Log a purchase transaction
        TokenTransaction.objects.create(
            user=user,
            transaction_type="purchase",
            amount=0,
            price_paid=199.00,
            note="Purchased ₹199 Early Bird Premium Subscription"
        )
        
        return Response({
            "message": "Premium Subscription activated successfully!",
            "is_subscribed": True
        })


class VerifyScholarshipView(APIView):
    """Verify scholarship test answers and mark user profile as eligible for promo pricing."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        if user.scholarship_test_attempts >= 2 and not user.scholarship_test_passed:
            return Response({"error": "Max attempts reached. Scholarship challenge is locked."}, status=status.HTTP_403_FORBIDDEN)

        answers = request.data.get('answers', {})
        if not answers or len(answers) < 5:
            return Response({"error": "Invalid test submission. Must submit 5 answers."}, status=status.HTTP_400_BAD_REQUEST)
        
        correct_count = 0
        for q_id, selected_opt in answers.items():
            try:
                qid_int = int(q_id)
                question = Question.objects.get(id=qid_int)
                correct_ans = question.correct_answer
                
                if correct_ans.upper() == str(selected_opt).upper():
                    correct_count += 1
            except (Question.DoesNotExist, ValueError):
                pass

        user.scholarship_test_attempts += 1

        if correct_count == 5:
            user.scholarship_test_passed = True
            if user.scholarship_test_attempts == 1:
                user.scholarship_granted_price = 79
            else:
                user.scholarship_granted_price = 99
                
            user.save(update_fields=['scholarship_test_passed', 'scholarship_test_attempts', 'scholarship_granted_price'])
            return Response({
                "status": "passed",
                "score": 5,
                "message": f"Congratulations! You scored 100% and unlocked the ₹{user.scholarship_granted_price} special offer!"
            })
        else:
            user.save(update_fields=['scholarship_test_attempts'])
            if user.scholarship_test_attempts == 1:
                return Response({
                    "status": "failed",
                    "score": correct_count,
                    "message": f"You scored {correct_count}/5. You need 5/5. You have 1 attempt remaining for the ₹99 offer."
                })
            else:
                return Response({
                    "status": "failed",
                    "score": correct_count,
                    "message": f"You scored {correct_count}/5. Challenge Failed. No attempts remaining."
                })


class SubscribeOrderView(APIView):
    """Create a Razorpay order for dynamic pricing plans."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import os
        key_id = os.getenv('RAZORPAY_KEY_ID', '') or os.getenv('razorpayliveapi', '')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET', '') or os.getenv('razorpaylivekeysecret', '')
        if not key_id or not key_secret:
            return Response({'error': 'Razorpay is not configured on the server. Please add razorpayliveapi and razorpaylivekeysecret to .env'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        plan = request.data.get('plan', 'legacy')
        user = request.user

        # Plan routing & amount lookup
        if plan == '1_year':
            amount_paise = 199900
            amount_rs = 1999.00
            description = 'CrackLabs Premium 1 Year Plan'
        elif plan == '3_months':
            amount_paise = 44900
            amount_rs = 449.00
            description = 'CrackLabs Premium 3 Months Plan'
        elif plan == '1_month':
            amount_paise = 12900
            amount_rs = 129.00
            description = 'CrackLabs Premium 1 Month Plan'
        elif plan == 'scholarship_1_month':
            if not user.scholarship_test_passed:
                return Response({'error': 'You are not eligible for the scholarship rate. Please complete the scholarship test first.'}, status=status.HTTP_403_FORBIDDEN)
            amount_rs = float(user.scholarship_granted_price or 79.00)
            amount_paise = int(amount_rs * 100)
            description = 'CrackLabs Premium 1 Month (Scholarship Special) Plan'
        else:
            # Fallback legacy early bird pass
            plan = 'legacy'
            amount_paise = 19900
            amount_rs = 199.00
            description = 'CrackLabs Premium Early Bird Plan'

        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        
        try:
            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'payment_capture': '1'
            }
            order = client.order.create(data=order_data)
            
            # Record payment attempt with plan type
            from accounts.models import PaymentAttempt
            PaymentAttempt.objects.create(
                user=user,
                razorpay_order_id=order['id'],
                amount=amount_rs,
                plan=plan,
                status='initiated'
            )
            
            # Send initiated checkout email
            try:
                from django.core.mail import send_mail
                from django.conf import settings as django_settings
                subject = f"⚠️ Complete your {description} Checkout"
                message = (
                    f"Dear Dr. {user.first_name or user.username},\n\n"
                    f"We noticed that you initiated the checkout for our {description} (₹{amount_rs}) but haven't completed it yet.\n\n"
                    f"Here is what you are missing out on:\n"
                    f"- Unlimited AI Tutor usage (no token limits)\n"
                    f"- Top-Teacher curated handwritten study sheets\n"
                    f"- Direct doubt clearance portal with renowned CMS faculty\n"
                    f"- Complete UPSC CMS & NEET PG PYQ bank (2018-2025)\n\n"
                    f"Please complete your subscription payment on your dashboard to claim your premium membership.\n\n"
                    f"If you experienced any issues during payment, please reply directly to this email.\n\n"
                    f"Best regards,\n"
                    f"The CrackLabs Team\n"
                    f"https://www.cracklabs.app"
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            return Response({
                'order_id': order['id'],
                'amount': order['amount'],
                'key_id': key_id,
                'plan': plan,
            })
        except Exception as e:
            return Response({'error': f'Failed to create Razorpay order: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubscribeVerifyView(APIView):
    """Verify payment signature from Razorpay and activate subscription."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import os
        payment_id = request.data.get('razorpay_payment_id')
        order_id = request.data.get('razorpay_order_id')
        signature = request.data.get('razorpay_signature')

        if not all([payment_id, order_id, signature]):
            return Response({'error': 'Missing payment verification details'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Idempotency: if this order was already verified, return success ──
        from accounts.models import PaymentAttempt
        try:
            existing_attempt = PaymentAttempt.objects.get(razorpay_order_id=order_id)
            if existing_attempt.status == 'successful':
                # Already verified — return success without re-processing
                sub = Subscription.get_active_subscription(request.user)
                return Response({
                    'message': 'Subscription is already active!',
                    'is_subscribed': True,
                    'subscription': _serialize_subscription(sub) if sub else None,
                })
        except PaymentAttempt.DoesNotExist:
            existing_attempt = None

        key_id = os.getenv('RAZORPAY_KEY_ID', '') or os.getenv('razorpayliveapi', '')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET', '') or os.getenv('razorpaylivekeysecret', '')
        if not key_id or not key_secret:
            return Response({'error': 'Razorpay keys not configured on server'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))

        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
        except Exception as e:
            # Mark attempt as failed
            if existing_attempt:
                existing_attempt.status = 'failed'
                existing_attempt.error_message = str(e)
                existing_attempt.save(update_fields=['status', 'error_message'])
            return Response({'error': f'Payment signature verification failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Activate subscription ──
        user = request.user
        plan = 'legacy'
        price_paid = 199.00

        # Mark attempt as successful and extract plan info
        if existing_attempt:
            existing_attempt.razorpay_payment_id = payment_id
            existing_attempt.status = 'successful'
            existing_attempt.save(update_fields=['razorpay_payment_id', 'status'])
            price_paid = float(existing_attempt.amount)
            plan = existing_attempt.plan or 'legacy'
        else:
            PaymentAttempt.objects.create(
                user=user,
                razorpay_order_id=order_id,
                razorpay_payment_id=payment_id,
                amount=199.00,
                plan='legacy',
                status='successful'
            )

        # Create proper Subscription record with plan + expiry
        sub = Subscription.activate_from_payment(
            user=user,
            plan=plan,
            amount_paid=price_paid,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
        )

        # Log transaction
        TokenTransaction.objects.create(
            user=user,
            transaction_type="purchase",
            amount=0,
            price_paid=price_paid,
            note=f"Razorpay Premium {sub.plan_display_name} (₹{price_paid}): order={order_id}, payment={payment_id}"
        )

        # Send customized successful payment / membership email
        try:
            from django.core.mail import send_mail
            from django.conf import settings as django_settings
            expires_str = sub.expires_at.strftime('%d %b %Y') if sub.expires_at else 'Lifetime'
            subject = "🎉 Welcome to CrackLabs Premium, Dr. {}! 🩺".format(user.first_name or user.username)
            message = (
                f"Dear Dr. {user.first_name or user.username},\n\n"
                f"Congratulations! Your payment of ₹{price_paid} was successfully verified, and your Premium Membership is now fully active.\n\n"
                f"Details of your Transaction:\n"
                f"- Plan: {sub.plan_display_name}\n"
                f"- Amount Paid: ₹{price_paid}\n"
                f"- Valid Until: {expires_str}\n"
                f"- Razorpay Order ID: {order_id}\n"
                f"- Razorpay Payment ID: {payment_id}\n\n"
                f"You now have full access to all CrackLabs Premium features, including our full 2018-2025 UPSC CMS bank, spaced repetition tools, and unlimited AI Tutor interactions.\n\n"
                f"Best of luck with your preparation!\n\n"
                f"Best regards,\n"
                f"The CrackLabs Team\n"
                f"https://www.cracklabs.app"
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass

        # Send email notification to admin
        try:
            from analytics.views import send_admin_notification_email
            send_admin_notification_email(
                subject=f"[PREMIUM PURCHASE] {user.username} subscribed to {sub.plan_display_name}",
                message=(
                    f"A user has successfully paid and upgraded to {sub.plan_display_name}.\n\n"
                    f"User Details:\n"
                    f"  Username: {user.username}\n"
                    f"  Email: {user.email}\n"
                    f"  Phone: {getattr(user, 'phone', 'Not provided')}\n"
                    f"  College: {getattr(user, 'college', 'Not provided')}\n\n"
                    f"Payment Details:\n"
                    f"  Plan: {sub.plan_display_name}\n"
                    f"  Amount: ₹{price_paid}\n"
                    f"  Razorpay Order ID: {order_id}\n"
                    f"  Razorpay Payment ID: {payment_id}\n"
                )
            )
        except Exception:
            logger.exception("Failed to send admin payment notification email")

        return Response({
            'message': 'Subscription verified and activated successfully!',
            'is_subscribed': True,
            'subscription': _serialize_subscription(sub),
        })


def _serialize_subscription(sub):
    """Helper to serialize a Subscription object for API responses."""
    if not sub:
        return None
    return {
        'plan': sub.plan,
        'plan_display_name': sub.plan_display_name,
        'status': sub.status,
        'is_active': sub.is_active,
        'starts_at': sub.starts_at.isoformat() if sub.starts_at else None,
        'expires_at': sub.expires_at.isoformat() if sub.expires_at else None,
        'days_remaining': sub.days_remaining,
        'amount_paid': float(sub.amount_paid),
        'razorpay_order_id': sub.razorpay_order_id,
        'created_at': sub.created_at.isoformat() if sub.created_at else None,
    }


class SubscriptionStatusView(APIView):
    """Return the authenticated user's current subscription status."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        sub = Subscription.get_active_subscription(user)

        # Backward compat: if user.is_subscribed but no Subscription record,
        # they are a grandfathered lifetime user
        if not sub and user.is_subscribed:
            return Response({
                'is_subscribed': True,
                'subscription': {
                    'plan': 'legacy',
                    'plan_display_name': 'Legacy Early Bird (Lifetime)',
                    'status': 'active',
                    'is_active': True,
                    'starts_at': user.created_at.isoformat() if user.created_at else None,
                    'expires_at': None,
                    'days_remaining': -1,
                    'amount_paid': 0,
                    'razorpay_order_id': '',
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                },
            })

        return Response({
            'is_subscribed': sub.is_active if sub else False,
            'subscription': _serialize_subscription(sub) if sub else None,
        })


class RazorpayWebhookView(APIView):
    """
    Razorpay server-to-server webhook handler.

    This catches the edge case where a student pays successfully but closes
    the browser before the frontend can call /subscribe/verify/.
    Razorpay will POST to this endpoint with payment.captured event.

    Setup: In Razorpay Dashboard > Settings > Webhooks, add:
      URL: https://crackcms-vsthc.ondigitalocean.app/api/auth/subscribe/webhook/
      Events: payment.captured
      Secret: (set RAZORPAY_WEBHOOK_SECRET in .env)
    """
    permission_classes = [permissions.AllowAny]  # Razorpay calls this, no auth header
    authentication_classes = []  # Disable DRF auth for webhook

    def post(self, request):
        import os
        import hmac
        import hashlib

        webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')

        # Verify webhook signature if secret is configured
        if webhook_secret:
            received_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                request.body,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(received_signature, expected_signature):
                logger.warning('Razorpay webhook signature mismatch')
                return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

        payload = request.data
        event = payload.get('event', '')

        if event != 'payment.captured':
            # We only care about successful captures
            return Response({'status': 'ignored'})

        payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id', '')
        order_id = payment_entity.get('order_id', '')

        if not order_id:
            return Response({'status': 'no_order_id'})

        # Find the payment attempt
        from accounts.models import PaymentAttempt
        try:
            attempt = PaymentAttempt.objects.get(razorpay_order_id=order_id)
        except PaymentAttempt.DoesNotExist:
            logger.warning(f'Razorpay webhook: no PaymentAttempt for order {order_id}')
            return Response({'status': 'order_not_found'})

        # Idempotency: already processed
        if attempt.status == 'successful':
            return Response({'status': 'already_processed'})

        # Activate subscription
        attempt.razorpay_payment_id = payment_id
        attempt.status = 'successful'
        attempt.save(update_fields=['razorpay_payment_id', 'status'])

        user = attempt.user
        plan = attempt.plan or 'legacy'
        price_paid = float(attempt.amount)

        sub = Subscription.activate_from_payment(
            user=user,
            plan=plan,
            amount_paid=price_paid,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
        )

        # Log transaction
        TokenTransaction.objects.create(
            user=user,
            transaction_type="purchase",
            amount=0,
            price_paid=price_paid,
            note=f"Razorpay Webhook: {sub.plan_display_name} (₹{price_paid}): order={order_id}, payment={payment_id}"
        )

        logger.info(f'Webhook activated subscription for {user.username}: {sub.plan_display_name}')
        return Response({'status': 'activated'})


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
                        "combined_daily_capacity": 20400,
                        "note": "Gemini: 4 models x 1500 RPD each. Groq: 14400 RPD.",
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
        from accounts.models import UserDevice
        from django.utils import timezone
        from datetime import timedelta

        attempt_map = {
            row['user_id']: row['count']
            for row in TestAttempt.objects
            .filter(user_id__in=[u.id for u in users])
            .values('user_id')
            .annotate(count=Count('id'))
        }
        
        device_last_login_map = {
            row['user']: row['max_login']
            for row in UserDevice.objects
            .filter(user__in=[u.id for u in users], is_active=True)
            .values('user')
            .annotate(max_login=Max('last_login'))
        }
        
        now = timezone.now()

        results = []
        for u in users:
            bal = balances.get(u.id)
            available = bal.available_tokens if bal else 0
            
            last_seen = u.last_seen or device_last_login_map.get(u.id) or u.last_login
            is_online = False
            if last_seen:
                is_online = (now - last_seen) < timedelta(minutes=10)
                
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
                'last_login': last_seen,
                'is_online': is_online,
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


class AdminSystemBackupDataView(APIView):
    """Backups core configuration data to JSON fixture."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from django.core.management import call_command
        import io
        try:
            # We just call the management command we created
            call_command('backup_core_data')
            create_admin_audit_log(
                actor=request.user,
                action='system_backup',
                resource_type='system',
                detail='Initiated core data backup to JSON',
            )
            return Response({'message': 'Core data structure backup completed successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminSystemRestoreDataView(APIView):
    """Restores core configuration data from JSON fixture."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from django.core.management import call_command
        try:
            call_command('restore_core_data')
            create_admin_audit_log(
                actor=request.user,
                action='system_restore',
                resource_type='system',
                detail='Restored core data structure from JSON',
            )
            return Response({'message': 'Core data structure restore completed successfully'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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


class UserDeviceListView(APIView):
    """List all active devices for the authenticated user."""

    def get(self, request):
        from .models import UserDevice
        from .serializers import UserDeviceSerializer
        devices = UserDevice.objects.filter(user=request.user, is_active=True).order_by('-last_login')
        serializer = UserDeviceSerializer(devices, many=True)
        return Response(serializer.data)


class UserDeviceLogoutView(APIView):
    """Log out a specific device (by setting is_active=False)."""

    def post(self, request):
        from .models import UserDevice
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'device_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            device = UserDevice.objects.get(id=device_id, user=request.user, is_active=True)
            device.is_active = False
            device.save(update_fields=['is_active'])
            return Response({'message': 'Device logged out successfully.'})
        except UserDevice.DoesNotExist:
            return Response({'error': 'Device not found or already logged out.'}, status=status.HTTP_404_NOT_FOUND)


# ── ADMIN PHASE 3 ROUTES ──

class AdminSubscriptionManageView(APIView):
    """Admin endpoint to manage user subscriptions (grant/revoke/extend)."""
    permission_classes = [IsControlTowerAdmin]
    
    def post(self, request, user_id):
        from .models import Subscription
        from django.utils import timezone
        import datetime
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
        action = request.data.get('action') # 'grant', 'revoke'
        plan = request.data.get('plan') # '1_month', '3_months', '1_year', 'legacy'
        
        if action == 'grant':
            if not plan:
                return Response({'error': 'Plan is required for granting'}, status=status.HTTP_400_BAD_REQUEST)
            # Create a manual subscription payment log
            Subscription.activate_from_payment(
                user=user,
                plan=plan,
                amount_paid=0,
                razorpay_order_id=f'admin_manual_{timezone.now().timestamp()}',
                razorpay_payment_id='admin_granted'
            )
            create_admin_audit_log(
                actor=request.user,
                action='user_role_update',
                resource_type='subscription',
                resource_id=str(user.id),
                detail=f'Granted {plan} subscription to {user.username}',
            )
            return Response({'message': f'Subscription {plan} granted to {user.username}'})
            
        elif action == 'revoke':
            Subscription.objects.filter(user=user, is_active=True).update(is_active=False, status='cancelled')
            user.is_subscribed = False
            user.save(update_fields=['is_subscribed'])
            
            create_admin_audit_log(
                actor=request.user,
                action='user_role_update',
                resource_type='subscription',
                resource_id=str(user.id),
                detail=f'Revoked subscription for {user.username}',
            )
            return Response({'message': f'Subscription revoked for {user.username}'})
            
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class AdminDeviceManageView(APIView):
    """Admin endpoint to view and force logout devices for a user."""
    permission_classes = [IsControlTowerAdmin]
    
    def get(self, request, user_id):
        from .models import UserDevice
        from .serializers import UserDeviceSerializer
        devices = UserDevice.objects.filter(user_id=user_id, is_active=True).order_by('-last_login')
        serializer = UserDeviceSerializer(devices, many=True)
        return Response(serializer.data)
        
    def post(self, request, user_id):
        from .models import UserDevice
        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'error': 'device_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            device = UserDevice.objects.get(id=device_id, user_id=user_id)
            device.is_active = False
            device.save(update_fields=['is_active'])
            create_admin_audit_log(
                actor=request.user,
                action='user_role_update', # Using existing valid choice
                resource_type='device',
                resource_id=str(user_id),
                detail=f'Logged out device {device_id} for user {user_id}',
            )
            return Response({'message': 'Device force logged out.'})
        except UserDevice.DoesNotExist:
            return Response({'error': 'Device not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminPaymentHistoryView(APIView):
    """Admin endpoint to view all payment attempts."""
    permission_classes = [IsControlTowerAdmin]
    
    def get(self, request):
        from .models import PaymentAttempt
        # Return last 100 payments for simplicity
        payments = PaymentAttempt.objects.select_related('user').order_by('-created_at')[:100]
        data = []
        for p in payments:
            data.append({
                'id': p.id,
                'user_id': p.user.id,
                'username': p.user.username,
                'email': p.user.email,
                'plan': p.plan,
                'amount': float(p.amount) if p.amount else 0,
                'status': p.status,
                'razorpay_order_id': p.razorpay_order_id,
                'created_at': p.created_at,
            })
        return Response(data)


