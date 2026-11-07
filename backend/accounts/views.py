"""
accounts/views.py - Authentication and token-management API views.
Endpoints: register, login, profile, token balance, token purchase, token history,
password reset request, and password reset confirm.
Admin users bypass token limits.
"""

import logging

from django.contrib.auth import get_user_model
from rest_framework import exceptions, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Max, Q, Subquery, Sum
from django.core.cache import cache

from crack_cms.throttling import ClientIPScopedRateThrottle, ScopedRateThrottle, UserRateThrottle
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


def _requests_username_change(request) -> bool:
    """A PUT / PATCH whose body sets a username other than the caller's current one."""
    if request.method not in ('PUT', 'PATCH'):
        return False
    data = request.data
    if not hasattr(data, 'get') or 'username' not in data:
        return False
    value = data.get('username')
    current = getattr(request.user, 'username', None) or ''
    # UserSerializer trims the value and accepts an unchanged one as is.
    return not (isinstance(value, str) and value.strip() == current)


class _UsernameChangeThrottle(UserRateThrottle):
    """Username changes -- and attempts at one -- per account: 10 an hour.

    The answer to a new username says whether some account already uses it
    ("This username is taken"), so trying names one after another is
    limited. Reads and profile saves that keep the username are not counted.
    The rate is set here, like _ScholarshipStartThrottle, so the scope needs
    no DEFAULT_THROTTLE_RATES entry.
    """
    scope = 'username_change'
    rate = '10/hour'
    message = 'Too many username changes. Please try again later.'

    def allow_request(self, request, view):
        if not _requests_username_change(request):
            return True
        if super().allow_request(request, view):
            return True
        # Raised here rather than returning False, for a message that says
        # which limit was hit (Retry-After is still set from ``wait``).
        raise exceptions.Throttled(self.wait(), detail=self.message)


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the current user profile.

    ``username`` is the public handle and may be changed here: 3-30 letters,
    digits, ``_`` and ``.``, unique (any case), not an email address or part
    of the user's own (accounts.handles.handle_error). 400 with the reason.
    Username changes are limited to 10 per hour (429; _UsernameChangeThrottle).
    """

    serializer_class = UserSerializer

    def get_throttles(self):
        # The default anon / user rates, plus the limit on username changes.
        return [*super().get_throttles(), _UsernameChangeThrottle()]

    def get_object(self):
        return self.request.user

    PROFILE_BONUS_TOKENS = 10

    def perform_update(self, serializer):
        # UserSerializer.update() saves only the edited fields.
        user = serializer.save()
        # Reward 10 tokens once when BOTH phone and college are filled.
        if user.phone and user.college and not user.profile_bonus_rewarded:
            with transaction.atomic():
                # Compare-and-set claim: of N concurrent PATCHes exactly one
                # flips the flag and pays out. The old check-then-set read a
                # stale flag, so parallel requests each added 10 tokens.
                claimed = (
                    User.objects
                    .filter(pk=user.pk, profile_bonus_rewarded=False)
                    .update(profile_bonus_rewarded=True)
                )
                if not claimed:
                    return
                user.profile_bonus_rewarded = True
                balance, _ = TokenBalance.objects.get_or_create(user=user)
                balance.add_feedback_credit(self.PROFILE_BONUS_TOKENS)
                TokenTransaction.objects.create(
                    user=user,
                    transaction_type="feedback_reward",
                    amount=self.PROFILE_BONUS_TOKENS,
                    price_paid=0.00,
                    note="Bonus for completing profile with mobile number and college name"
                )


class SubscribeView(APIView):
    """Deprecated free-tier subscription activation.

    This view previously activated is_subscribed=True without payment
    verification, which let any authenticated user POST {} and unlock
    the entire premium paywall. It is now a 410 GONE stub that matches
    the disabled `/auth/login/` and `/auth/register/` endpoints. All
    subscription activation must go through SubscribeOrderView +
    SubscribeVerifyView (Razorpay-signed payment required).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        return Response(
            {
                'detail': 'This subscription endpoint has been disabled. '
                          'Use /api/auth/subscribe/order/ and '
                          '/api/auth/subscribe/verify/ to complete a Razorpay '
                          'payment, or contact support if you believe this '
                          'is in error.',
                'error': 'endpoint_gone',
            },
            status=status.HTTP_410_GONE,
        )


SCHOLARSHIP_QUESTION_COUNT = 5
SCHOLARSHIP_MAX_ATTEMPTS = 2
SCHOLARSHIP_CHALLENGE_MAX_AGE = 60 * 60  # seconds a started challenge stays valid
_SCHOLARSHIP_SIGNING_SALT = 'accounts.scholarship-challenge.v1'
_SCHOLARSHIP_LOCKED_MESSAGE = "Max attempts reached. Scholarship challenge is locked."
_SCHOLARSHIP_PLAN_HOLDER_MESSAGE = "The scholarship challenge is for students without an active plan."


def _refuse_scholarship_for_plan_holder(user):
    """409 ``already_subscribed`` for a caller with an active plan, else None.

    An active plan unlocks every answer, the scholarship-challenge questions
    included (questions.views.user_can_view_answer), so its holder can
    neither take the challenge nor unlock its price. Admins, superusers and
    staff may still run it (they test the flow).
    """
    from .utils import is_premium

    if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
        return None
    if not is_premium(user):
        return None
    return Response(
        {"error": _SCHOLARSHIP_PLAN_HOLDER_MESSAGE, "code": "already_subscribed"},
        status=status.HTTP_409_CONFLICT,
    )


def _issue_scholarship_challenge(user_id, question_ids, attempt_number):
    """Signed, expiring record of the question set the server chose for this attempt."""
    from django.core import signing

    return signing.dumps(
        {'u': user_id, 'q': sorted(question_ids), 'n': attempt_number},
        salt=_SCHOLARSHIP_SIGNING_SALT,
        compress=True,
    )


class _ScholarshipStartThrottle(UserRateThrottle):
    """Each start shows five scholarship questions: a few per hour is plenty.

    The rate is set here (not in settings) so this scope never depends on a
    DEFAULT_THROTTLE_RATES entry.
    """
    scope = 'scholarship_start'
    rate = '10/hour'


def _issued_scholarship_set(stored, attempt_number):
    """The question ids stored for ``attempt_number`` (CustomUser.scholarship_challenge), or []."""
    if not isinstance(stored, dict) or stored.get('n') != attempt_number:
        return []
    ids = stored.get('q')
    if not isinstance(ids, list):
        return []
    return [qid for qid in ids if isinstance(qid, int) and not isinstance(qid, bool)]


def _assign_scholarship_set(user_pk, attempt_number, eligible_ids):
    """The attempt's question set: the stored one, else a fresh draw that is stored.

    Runs under a row lock, so concurrent starts of one attempt cannot draw two
    different sets. A stored question that is no longer eligible (an admin
    edit) is replaced; the others are kept.
    """
    import random

    with transaction.atomic():
        locked = User.objects.select_for_update().only('id', 'scholarship_challenge').get(pk=user_pk)
        eligible = set(eligible_ids)
        stored = _issued_scholarship_set(locked.scholarship_challenge, attempt_number)
        chosen = list(dict.fromkeys(qid for qid in stored if qid in eligible))[:SCHOLARSHIP_QUESTION_COUNT]
        if len(chosen) < SCHOLARSHIP_QUESTION_COUNT:
            taken = set(chosen)
            pool = [qid for qid in eligible_ids if qid not in taken]
            chosen += random.SystemRandom().sample(pool, SCHOLARSHIP_QUESTION_COUNT - len(chosen))
        if chosen != stored:
            locked.scholarship_challenge = {'n': attempt_number, 'q': chosen}
            locked.save(update_fields=['scholarship_challenge'])
    return chosen


class ScholarshipStartView(APIView):
    """Start a scholarship attempt: the SERVER picks the five questions.

    POST -> {questions: [{id, question_text, option_a..option_d}],
             challenge_token, expires_in}

    The token is signed and bound to the user, the chosen question ids and
    the current attempt number, so /verify-scholarship/ only scores this
    exact set, once. (The client used to pick any five eligible questions
    itself, e.g. ones whose answers it had already looked up.)

    The set is stored on the user (CustomUser.scholarship_challenge) until
    the attempt is submitted: starting again -- after an hour, a day, or once
    the token expired -- re-issues the same five questions with a new token,
    so a student cannot re-roll until a set they already know comes up.
    Starts are rate limited as well. Callers with an active plan (who can
    read the answers) get 409 already_subscribed, staff excepted.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [_ScholarshipStartThrottle]

    def post(self, request):
        user = request.user
        refused = _refuse_scholarship_for_plan_holder(user)
        if refused is not None:
            return refused
        passed, attempts = (
            User.objects.filter(pk=user.pk)
            .values_list('scholarship_test_passed', 'scholarship_test_attempts')
            .get()
        )
        if passed:
            return Response({"error": "You have already unlocked the scholarship price."}, status=status.HTTP_400_BAD_REQUEST)
        if attempts >= SCHOLARSHIP_MAX_ATTEMPTS:
            return Response({"error": _SCHOLARSHIP_LOCKED_MESSAGE}, status=status.HTTP_403_FORBIDDEN)

        eligible_ids = list(
            Question.objects.filter(is_scholarship_eligible=True, is_active=True)
            .order_by('id').values_list('id', flat=True)
        )
        if len(eligible_ids) < SCHOLARSHIP_QUESTION_COUNT:
            # The subscription page shows its "no scholarship questions" state.
            return Response({'questions': [], 'challenge_token': None, 'expires_in': 0})

        from questions.answer_leak import redact_public_text

        chosen = _assign_scholarship_set(user.pk, attempts, eligible_ids)
        rows = {
            q['id']: q for q in Question.objects.filter(id__in=chosen).values(
                'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            )
        }
        # The challenge taker never sees the answer: an answer key or an
        # explanation glued into the stem / an option by an import is cut off
        # at its label (questions.answer_leak), as for any locked question.
        for row in rows.values():
            redact_public_text(row)
        return Response({
            'questions': [rows[qid] for qid in chosen if qid in rows],
            'challenge_token': _issue_scholarship_challenge(user.pk, chosen, attempts),
            'expires_in': SCHOLARSHIP_CHALLENGE_MAX_AGE,
        })


class VerifyScholarshipView(APIView):
    """Verify scholarship test answers and mark user profile as eligible for promo pricing.

    POST {answers: {<question_id>: 'A'|'B'|'C'|'D'}, challenge_token}
    -> {status: 'passed'|'failed', score: 5|null, message}
    The answered ids must be exactly the set issued by ScholarshipStartView,
    each with a letter (a blank is refused, without using up an attempt).
    A failed attempt does not say how many answers were right (``score`` is
    null): the count, with blanks or a guess on one question, was that
    question's right/wrong signal, and the challenge questions' answers are
    never shown to students without a plan.
    The attempt counter is checked and incremented under a row lock.
    Callers with an active plan get 409 already_subscribed (staff excepted),
    without using up an attempt.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.core import signing

        user = request.user
        refused = _refuse_scholarship_for_plan_holder(user)
        if refused is not None:
            return refused

        if user.scholarship_test_attempts >= SCHOLARSHIP_MAX_ATTEMPTS and not user.scholarship_test_passed:
            return Response({"error": _SCHOLARSHIP_LOCKED_MESSAGE}, status=status.HTTP_403_FORBIDDEN)

        answers = request.data.get('answers', {})
        if not isinstance(answers, dict) or len(answers) != SCHOLARSHIP_QUESTION_COUNT:
            return Response({"error": "Invalid test submission. Must submit 5 answers."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the submission before counting an attempt: exactly five
        # *distinct* scholarship-eligible questions, one letter each.
        # Previously the same question could be submitted several times
        # under different keys ("1", "01", "001") with A/B/C/D, or any
        # question the user already knew could be used. Blanks are refused
        # too: one guess plus four blanks used to turn the score into that
        # question's right/wrong signal.
        normalized = {}
        for q_id, selected_opt in answers.items():
            try:
                qid_int = int(str(q_id).strip())
            except (TypeError, ValueError):
                return Response({"error": "Invalid question id in submission."}, status=status.HTTP_400_BAD_REQUEST)
            letter = str(selected_opt or '').strip().upper()
            if not letter:
                return Response({"error": "Answer all 5 questions before submitting."}, status=status.HTTP_400_BAD_REQUEST)
            if qid_int in normalized or letter not in ('A', 'B', 'C', 'D'):
                return Response({"error": "Invalid test submission."}, status=status.HTTP_400_BAD_REQUEST)
            normalized[qid_int] = letter

        # The question set must be the one the server issued for this user
        # and attempt (ScholarshipStartView), not one the client chose.
        token = str(request.data.get('challenge_token') or '')
        try:
            challenge = signing.loads(token, salt=_SCHOLARSHIP_SIGNING_SALT, max_age=SCHOLARSHIP_CHALLENGE_MAX_AGE)
        except signing.SignatureExpired:
            return Response(
                {"error": "This scholarship challenge has expired. Please start it again.", "code": "scholarship_expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except signing.BadSignature:
            return Response(
                {"error": "Please start the scholarship challenge again from the subscription page.", "code": "scholarship_not_started"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            not isinstance(challenge, dict)
            or challenge.get('u') != user.pk
            or sorted(normalized) != challenge.get('q')
        ):
            return Response({"error": "Submission contains questions that are not part of the scholarship challenge."},
                            status=status.HTTP_400_BAD_REQUEST)

        questions = {
            q.id: q for q in Question.objects.filter(
                id__in=list(normalized), is_scholarship_eligible=True, is_active=True,
            )
        }
        if len(questions) != SCHOLARSHIP_QUESTION_COUNT:
            return Response({"error": "Submission contains questions that are not part of the scholarship challenge."},
                            status=status.HTTP_400_BAD_REQUEST)

        correct_count = 0
        for qid_int, letter in normalized.items():
            correct_ans = (questions[qid_int].correct_answer or '').strip().upper()[:1]
            if correct_ans and correct_ans == letter:
                correct_count += 1

        with transaction.atomic():
            # Row lock: parallel submissions used to read the same counter
            # and each get a "first attempt", getting around the 2-attempt cap.
            locked = User.objects.select_for_update().get(pk=user.pk)
            if locked.scholarship_test_passed:
                return Response({"error": "You have already unlocked the scholarship price."}, status=status.HTTP_400_BAD_REQUEST)
            if locked.scholarship_test_attempts >= SCHOLARSHIP_MAX_ATTEMPTS:
                return Response({"error": _SCHOLARSHIP_LOCKED_MESSAGE}, status=status.HTTP_403_FORBIDDEN)
            if challenge.get('n') != locked.scholarship_test_attempts:
                # Each started challenge can be submitted once.
                return Response(
                    {"error": "This scholarship challenge was already submitted. Please start it again.", "code": "scholarship_not_started"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            issued = _issued_scholarship_set(locked.scholarship_challenge, locked.scholarship_test_attempts)
            if issued and sorted(issued) != challenge.get('q'):
                # Only the set stored for this attempt can be scored, so a
                # token issued before the set was stored cannot add another.
                return Response(
                    {"error": "Please start the scholarship challenge again from the subscription page.", "code": "scholarship_not_started"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            locked.scholarship_test_attempts += 1
            locked.scholarship_challenge = None
            update_fields = ['scholarship_test_attempts', 'scholarship_challenge']
            if correct_count == SCHOLARSHIP_QUESTION_COUNT:
                locked.scholarship_test_passed = True
                locked.scholarship_granted_price = 79 if locked.scholarship_test_attempts == 1 else 99
                update_fields += ['scholarship_test_passed', 'scholarship_granted_price']
            locked.save(update_fields=update_fields)

        if correct_count == SCHOLARSHIP_QUESTION_COUNT:
            return Response({
                "status": "passed",
                "score": SCHOLARSHIP_QUESTION_COUNT,
                "message": f"Congratulations! You scored 100% and unlocked the ₹{locked.scholarship_granted_price} special offer!"
            })
        # No count of correct answers on a failure (see the docstring).
        if locked.scholarship_test_attempts == 1:
            return Response({
                "status": "failed",
                "score": None,
                "message": "You did not get all 5 right. You need 5/5. You have 1 attempt remaining for the ₹99 offer."
            })
        return Response({
            "status": "failed",
            "score": None,
            "message": "You did not get all 5 right. Challenge Failed. No attempts remaining."
        })


# Plans a student can buy. 'legacy' (lifetime early-bird) and 'admin_grant'
# are no longer sold and can only be granted by an admin.
PURCHASABLE_PLANS = frozenset({'1_month', '3_months', '1_year', 'scholarship_1_month'})


class SubscribeOrderView(APIView):
    """Create a Razorpay order for dynamic pricing plans."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'subscription_order'

    def post(self, request):
        import os
        import uuid
        key_id = os.getenv('RAZORPAY_KEY_ID', '') or os.getenv('razorpayliveapi', '')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET', '') or os.getenv('razorpaylivekeysecret', '')
        if not key_id or not key_secret:
            return Response({'error': 'Razorpay is not configured on the server. Please add razorpayliveapi and razorpaylivekeysecret to .env'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Only plans that are actually on sale can be bought. The previous
        # default/fallback turned a missing or unknown plan into 'legacy' --
        # a LIFETIME unlimited plan -- for Rs 199 (the 1-year plan is Rs 1999).
        plan = str(request.data.get('plan') or '').strip()
        if plan not in PURCHASABLE_PLANS:
            return Response(
                {'error': 'Unknown or unavailable plan.', 'available_plans': sorted(PURCHASABLE_PLANS)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user

        # A lifetime plan never expires and already includes unlimited AI:
        # any further period would be paid for and add nothing. The page
        # hides the buy buttons for these members; the API refuses too.
        active = Subscription.get_active_subscription(user)
        if active is not None and active.expires_at is None and active.unlimited_ai:
            return Response(
                {'code': 'lifetime_member', 'error': 'Your account already has lifetime access, so there is nothing to buy.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Client idempotency key — prevents double-charge if the user
        # double-clicks "Renew" before the modal dismisses. Same key within
        # 5 minutes returns the original order instead of creating a new one.
        client_request_id = (request.data.get('request_id') or '').strip()
        if client_request_id:
            from .models import PaymentAttempt
            existing = PaymentAttempt.objects.filter(
                user=user,
                error_message__icontains=f'request_id:{client_request_id}',
            ).first()
            if existing:
                return Response({
                    'order_id': existing.razorpay_order_id,
                    'amount': int(existing.amount * 100),
                    'key_id': key_id,
                    'plan': existing.plan,
                    'idempotent_replay': True,
                })

        # Coupon code (2026-11-07, accounts.coupons): checked and priced on the server only. A code
        # worth the whole price activates the plan here, without a payment; otherwise the order is
        # created for the discounted amount and holds one use of the code until it is paid.
        from . import coupons
        coupon = None
        coupon_quote = None
        coupon_code = coupons.normalize_code(request.data.get('coupon_code'))
        if coupon_code:
            if plan not in coupons.COUPON_PLANS:
                error = coupons.CouponError('coupon_not_for_plan')
                return Response({'code': error.code, 'error': error.message}, status=status.HTTP_400_BAD_REQUEST)
            coupon = coupons.find(coupon_code)
            try:
                coupons.check(coupon, user, plan)
            except coupons.CouponError as error:
                return Response({'code': error.code, 'error': error.message}, status=status.HTTP_400_BAD_REQUEST)
            coupon_quote = coupons.quote(coupon, plan)
            if coupon_quote['final_amount'] == 0:
                try:
                    sub = coupons.redeem_free(coupon, user, plan)
                except coupons.CouponError as error:
                    return Response({'code': error.code, 'error': error.message}, status=status.HTTP_400_BAD_REQUEST)
                return Response({
                    'free_activation': True,
                    'plan': plan,
                    'coupon_code': coupon.code,
                    'message': f'Coupon {coupon.code} applied: your {sub.plan_display_name} is active.',
                    'is_subscribed': True,
                    'subscription': _serialize_subscription(sub),
                })

        # Plan routing & amount lookup.
        if plan == '1_year':
            amount_paise = 199900
            amount_rs = 1999.00
        elif plan == '3_months':
            amount_paise = 44900
            amount_rs = 449.00
        elif plan == '1_month':
            amount_paise = 12900
            amount_rs = 129.00
        elif plan == 'scholarship_1_month':
            if not user.scholarship_test_passed:
                return Response({'error': 'You are not eligible for the scholarship rate. Please complete the scholarship test first.'}, status=status.HTTP_403_FORBIDDEN)
            amount_rs = float(user.scholarship_granted_price or 79.00)
            amount_paise = int(amount_rs * 100)
        else:  # pragma: no cover - unreachable, plan validated above
            return Response({'error': 'Unknown or unavailable plan.'}, status=status.HTTP_400_BAD_REQUEST)
        if coupon_quote is not None:
            amount_rs = float(coupon_quote['final_amount'])
            amount_paise = int(coupon_quote['final_amount']) * 100

        from .payments_mock import get_razorpay_client
        client = get_razorpay_client(key_id, key_secret)

        try:
            order_notes = {
                'plan': plan,
                'user_id': str(user.id),
            }
            if client_request_id:
                order_notes['request_id'] = client_request_id
            if coupon is not None:
                order_notes['coupon'] = coupon.code

            order_data = {
                'amount': amount_paise,
                'currency': 'INR',
                'payment_capture': '1',
                'notes': order_notes,
            }
            order = client.order.create(data=order_data)

            # Record payment attempt with plan type
            from accounts.models import PaymentAttempt
            error_marker = f'request_id:{client_request_id}' if client_request_id else ''
            attempt = PaymentAttempt.objects.create(
                user=user,
                razorpay_order_id=order['id'],
                amount=amount_rs,
                plan=plan,
                status='initiated',
                error_message=error_marker,  # reuse field for idempotency tag
            )
            # No "complete your checkout" email here: this runs before the
            # user has even seen the payment popup, so every buyer got a nag
            # mail mid-checkout (promising unlimited AI on metered plans). An
            # abandoned-checkout reminder belongs in a scheduled job that
            # mails attempts still 'initiated' hours later.
        except Exception:
            logger.exception('Failed to create Razorpay order for user_id=%s plan=%s', user.id, plan)
            return Response({'error': 'Could not start the payment. Please try again in a moment.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if coupon is not None:
            try:
                coupons.reserve(coupon, user, plan, order['id'])
            except coupons.CouponError as error:
                # Another checkout took the last use meanwhile: this order is never paid.
                PaymentAttempt.objects.filter(pk=attempt.pk).update(status='failed', error_message=f'coupon:{error.code}')
                return Response({'code': error.code, 'error': error.message}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            'order_id': order['id'],
            'amount': order['amount'],
            'key_id': key_id,
            'plan': plan,
        }
        if coupon is not None:
            payload.update({'coupon_code': coupon.code, 'original_amount': coupon_quote['original_amount'],
                            'discount_amount': coupon_quote['discount_amount']})
        return Response(payload)


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
        # SECURITY (Fix #1): verify that the PaymentAttempt (if any) belongs
        # to the requesting user. Without this check, any authenticated user
        # who happens to learn another user's `razorpay_order_id` could verify
        # the payment against their own account and steal the subscription.
        # Razorpay's HMAC signature proves the payment happened — but it does
        # NOT prove the payment was for THIS user; the attacker can replay
        # someone else's successful verify call with their own JWT.
        from accounts.models import PaymentAttempt
        try:
            existing_attempt = PaymentAttempt.objects.get(razorpay_order_id=order_id)
        except PaymentAttempt.DoesNotExist:
            existing_attempt = None

        if existing_attempt is not None and existing_attempt.user_id != request.user.id:
            logger.warning(
                "SubscribeVerify ownership mismatch: user_id=%s tried to verify order_id=%s owned by user_id=%s",
                request.user.id, order_id, existing_attempt.user_id,
            )
            return Response(
                {'error': 'This payment belongs to a different account.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        key_id = os.getenv('RAZORPAY_KEY_ID', '') or os.getenv('razorpayliveapi', '')
        key_secret = os.getenv('RAZORPAY_KEY_SECRET', '') or os.getenv('razorpaylivekeysecret', '')
        if not key_id or not key_secret:
            return Response({'error': 'Razorpay keys not configured on server'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from .payments_mock import get_razorpay_client
        client = get_razorpay_client(key_id, key_secret)

        # The signature is checked for EVERY call, including replays of an
        # order that is already 'successful': replays may activate a stranded
        # order (_already_processed_response), and an order id alone (any
        # payment id / signature string) must never do that.
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
        except Exception as e:
            # Mark attempt as failed -- unless the webhook claimed it
            # meanwhile: overwriting 'successful' would let a later verify
            # claim (and activate) the same payment a second time.
            if existing_attempt:
                PaymentAttempt.objects.filter(pk=existing_attempt.pk).exclude(status='successful').update(
                    status='failed', error_message=str(e), updated_at=timezone.now(),
                )
            logger.warning('SubscribeVerify: signature verification failed for order %s: %s', order_id, e)
            return Response({'error': 'Payment signature verification failed.'}, status=status.HTTP_400_BAD_REQUEST)

        if existing_attempt is not None and existing_attempt.status == 'successful':
            # Already verified (ownership was checked above) — report the
            # real subscription state without re-processing.
            return _already_processed_response(request.user, existing_attempt)

        # ── Activate subscription ──
        user = request.user

        # Every order this server creates has a PaymentAttempt (see
        # SubscribeOrderView). A validly signed payment for an order we did
        # not create (another product on the same Razorpay account, a
        # payment link, ...) used to fall back to a *lifetime* "legacy"
        # plan -- never grant access for an order we can't match.
        if existing_attempt is None:
            logger.error(
                'SubscribeVerify: signed payment %s for unknown order %s (user_id=%s) -- not activating; reconcile manually',
                payment_id, order_id, user.id,
            )
            return Response(
                {'error': 'We could not match this payment to a checkout. Please contact support with your payment ID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Atomic compare-and-set claim AND activation in ONE transaction:
        # exactly one of {this verify call, the webhook, a duplicate verify}
        # flips the attempt to successful and activates; the others see 0
        # rows updated. Before, the claim committed on its own, so a failure
        # in activation left a paid order marked successful with no plan,
        # and later verify calls reported "already active".
        try:
            sub = _claim_and_activate(existing_attempt, payment_id, user=user, source='verify')
        except Exception:
            logger.exception('SubscribeVerify: activation failed for order %s (user_id=%s); claim rolled back', order_id, user.id)
            return Response(
                {'error': "Your payment was received but we couldn't activate your plan yet. Please click 'Retry Verification' or contact support with your payment ID."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if sub is None:
            return _already_processed_response(user, existing_attempt)

        price_paid = float(existing_attempt.amount)
        _send_purchase_emails(user, sub, price_paid, order_id, payment_id)

        return Response({
            'message': 'Subscription verified and activated successfully!',
            'is_subscribed': True,
            'subscription': _serialize_subscription(sub),
        })


def _record_razorpay_purchase(user, attempt, payment_id, *, source):
    """Activate the plan bought by ``attempt`` and log the purchase.

    Must run inside the transaction that claimed the attempt.
    """
    price_paid = float(attempt.amount)
    order_id = attempt.razorpay_order_id
    sub = Subscription.activate_from_payment(
        user=user,
        plan=attempt.plan or 'legacy',
        amount_paid=price_paid,
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
    )
    # A coupon held for this order is used now (verify, webhook or recovery alike).
    from .coupons import mark_redeemed
    coupon_code = mark_redeemed(order_id, sub)
    label = {'verify': 'Razorpay Premium', 'webhook': 'Razorpay Webhook:'}.get(source, f'Razorpay ({source})')
    TokenTransaction.objects.create(
        user=user,
        transaction_type="purchase",
        amount=0,
        price_paid=price_paid,
        note=(f"{label} {sub.plan_display_name} (₹{price_paid}): order={order_id}, payment={payment_id}"
              + (f", coupon={coupon_code}" if coupon_code else '')),
    )
    return sub


def _claim_and_activate(attempt, payment_id, *, user, source):
    """Claim ``attempt`` (compare-and-set) and activate it, atomically.

    Returns the new Subscription, or None when another request already
    claimed the order. Any exception rolls the claim back so the order can
    be verified again (or delivered again by the webhook).
    """
    from .models import PaymentAttempt

    with transaction.atomic():
        claimed = (
            PaymentAttempt.objects
            .filter(pk=attempt.pk, user_id=user.id)
            .exclude(status='successful')
            .update(status='successful', razorpay_payment_id=payment_id, updated_at=timezone.now())
        )
        if not claimed:
            return None
        return _record_razorpay_purchase(user, attempt, payment_id, source=source)


# Plans whose orders predate the Subscription model (the old lifetime early-bird
# pass) have no Subscription rows by design: never "recover" those.
_NOT_RECOVERABLE_PLANS = frozenset({'', 'legacy'})


def _heal_stranded_payment(attempt):
    """Activate an order that is marked successful but has no subscription.

    Before the claim and the activation shared a transaction, a failure in
    between left exactly this state and nothing ever recovered it. Locks the
    attempt so concurrent callers activate it at most once.

    Callers must have authenticated the payment first: SubscribeVerifyView
    after the Razorpay signature check, RazorpayWebhookView after the webhook
    HMAC. Legacy (pre-Subscription) orders are skipped -- an admin may have
    revoked those users since, and a replay must not restore a lifetime plan.
    """
    from .models import PaymentAttempt

    if (attempt.plan or '') in _NOT_RECOVERABLE_PLANS:
        return None
    with transaction.atomic():
        locked = (
            PaymentAttempt.objects.select_for_update()
            .select_related('user')
            .filter(pk=attempt.pk, status='successful')
            .first()
        )
        if locked is None or (locked.plan or '') in _NOT_RECOVERABLE_PLANS:
            return None
        if Subscription.objects.filter(user_id=locked.user_id, razorpay_order_id=locked.razorpay_order_id).exists():
            return None
        logger.error(
            'Payment order %s (user_id=%s) was marked successful without a subscription; activating it now',
            locked.razorpay_order_id, locked.user_id,
        )
        return _record_razorpay_purchase(locked.user, locked, locked.razorpay_payment_id or '', source='recovered')


def _already_processed_response(user, attempt):
    """Response for an order that was already claimed: the REAL subscription state.

    Only called for an authenticated payment (see _heal_stranded_payment).
    """
    try:
        _heal_stranded_payment(attempt)
    except Exception:
        logger.exception('Could not recover stranded payment order %s', attempt.razorpay_order_id)
    sub = Subscription.get_active_subscription(user)
    if sub is None:
        # The plan this order bought has run out or was revoked: an ordinary
        # answer, not an incident. Only an order with no subscription record
        # at all (and not recoverable above) needs a human.
        if not Subscription.objects.filter(user_id=user.id, razorpay_order_id=attempt.razorpay_order_id).exists():
            logger.error(
                'Payment order %s (user_id=%s) is marked successful but has no subscription record',
                attempt.razorpay_order_id, user.id,
            )
            message = 'This payment was already processed, but no active subscription was found. Please contact support with your payment ID.'
        else:
            message = 'This payment was already processed. The plan it activated is no longer active.'
        return Response(
            {
                'error': message,
                'is_subscribed': False,
                'subscription': None,
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response({
        'message': 'Subscription is already active!',
        'is_subscribed': True,
        'subscription': _serialize_subscription(sub),
    })


def _send_purchase_emails(user, sub, price_paid, order_id, payment_id):
    """Receipt for the student and a notification for the admin, sent off the request path."""
    from .emails import run_in_background, send_mail_in_background

    name = user.first_name or user.username
    expires_str = sub.expires_at.strftime('%d %b %Y') if sub.expires_at else 'Lifetime'
    if sub.unlimited_ai:
        ai_line = "unlimited AI Tutor interactions"
    elif sub.monthly_tokens_grant:
        ai_line = f"{sub.monthly_tokens_grant} AI Tutor tokens added to your wallet (on top of the free daily allowance)"
    else:
        ai_line = "the AI Tutor"
    send_mail_in_background(
        subject=f"🎉 Welcome to CrackLabs Premium, Dr. {name}! 🩺",
        message=(
            f"Dear Dr. {name},\n\n"
            f"Congratulations! Your payment of ₹{price_paid} was successfully verified, and your Premium Membership is now fully active.\n\n"
            f"Details of your Transaction:\n"
            f"- Plan: {sub.plan_display_name}\n"
            f"- Amount Paid: ₹{price_paid}\n"
            f"- Valid Until: {expires_str}\n"
            f"- Razorpay Order ID: {order_id}\n"
            f"- Razorpay Payment ID: {payment_id}\n\n"
            f"You now have full access to all CrackLabs Premium features, including our full 2018-2026 UPSC CMS bank, spaced repetition tools, and {ai_line}.\n\n"
            f"Best of luck with your preparation!\n\n"
            f"Best regards,\n"
            f"The CrackLabs Team\n"
            f"https://www.cracklabs.app"
        ),
        recipient_list=[user.email],
    )

    from analytics.views import send_admin_notification_email
    run_in_background(
        send_admin_notification_email,
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
        ),
    )


def _serialize_subscription(sub):
    """Helper to serialize a Subscription object for API responses."""
    if not sub:
        return None
    return {
        'id': sub.id,
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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'subscription_status'

    def get(self, request):
        from .models import SUBSCRIPTION_STATUS_CACHE_KEY

        user = request.user
        cache_key = SUBSCRIPTION_STATUS_CACHE_KEY.format(user_id=user.id)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        sub = Subscription.get_active_subscription(user)

        # Subscription rows only. The bare is_subscribed flag (no row) used to
        # be reported as a "Legacy Early Bird (Lifetime)" plan, but the removed
        # unpaid /auth/subscribe/ endpoint set it for anyone; accounts that
        # paid before the Subscription model got real rows (accounts.0026).
        result = Response({
            'is_subscribed': sub.is_active if sub else False,
            'subscription': _serialize_subscription(sub) if sub else None,
        })
        cache.set(cache_key, result.data, 120)
        return result


class SubscriptionHistoryView(APIView):
    """
    Return the authenticated user's full subscription history (all records, newest-first).

    The first entry is the currently-active record (if any), followed by every
    previous subscription (active/expired/cancelled) so users can see exactly
    what they bought, when, how long it lasted, and how much they paid.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'subscription_status'

    def get(self, request):
        user = request.user
        subs = Subscription.objects.filter(user=user).order_by('-created_at')
        return Response({
            'count': subs.count(),
            'subscriptions': [_serialize_subscription(s) for s in subs],
        })


class SubscriptionInvoiceView(APIView):
    """
    Printable invoice/receipt for a single Subscription row.

    Returns JSON describing the payment so the frontend can render a printable
    view at `/subscription/invoice/<subscription_id>/`. Returns 404 if the
    subscription does not belong to the requesting user (security: never leak
    someone else's order id).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, subscription_id: int):
        user = request.user
        try:
            sub = Subscription.objects.get(id=subscription_id, user=user)
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'Invoice not found for this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Best-effort: link to the matching PaymentAttempt for verification trail
        payment = None
        if sub.razorpay_order_id:
            from .models import PaymentAttempt
            try:
                payment = PaymentAttempt.objects.get(razorpay_order_id=sub.razorpay_order_id)
            except PaymentAttempt.DoesNotExist:
                payment = None

        coupon = None
        if sub.razorpay_order_id:
            from .models_coupons import CouponRedemption
            redemption = (CouponRedemption.objects.select_related('coupon')
                          .filter(razorpay_order_id=sub.razorpay_order_id, user=user, status='redeemed').first())
            if redemption is not None:
                coupon = {'code': redemption.coupon.code,
                          'original_amount': float(redemption.original_amount),
                          'discount_amount': float(redemption.discount_amount)}

        return Response({
            'subscription': _serialize_subscription(sub),
            'coupon': coupon,
            'payment': {
                'razorpay_order_id': payment.razorpay_order_id if payment else (sub.razorpay_order_id or ''),
                'razorpay_payment_id': (
                    payment.razorpay_payment_id if payment
                    else (getattr(sub, 'razorpay_payment_id', '') or '')
                ),
                'amount': float(payment.amount) if payment else float(sub.amount_paid),
                'plan': payment.plan if payment else sub.plan,
                'status': payment.status if payment else 'successful',
                'paid_at': payment.updated_at.isoformat() if payment else sub.created_at.isoformat(),
            } if (payment or sub.amount_paid > 0) else None,
            'invoice_no': f'CMS-INV-{sub.id:06d}',
            'issued_to': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
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

        # SECURITY: Refuse unsigned webhooks in production.
        # If no secret is configured, this endpoint would accept ANY signed/unsigned request,
        # letting attackers activate subscriptions. Reject by default.
        if not webhook_secret:
            logger.error('RAZORPAY_WEBHOOK_SECRET not configured — rejecting webhook')
            return Response(
                {'error': 'Webhook not configured'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        received_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
        if not received_signature:
            logger.warning('Razorpay webhook missing X-Razorpay-Signature header')
            return Response({'error': 'Missing signature'}, status=status.HTTP_400_BAD_REQUEST)

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

        # Idempotency: if Razorpay retries with the SAME payment_id we've
        # already credited, treat as no-op. If it sends a *different*
        # payment_id (re-captured under a new payment, possible on capture
        # retries), update the stored payment_id and re-activate — the
        # previous Subscription.activate_from_payment is naturally
        # idempotent (extends existing expiry), so the result converges.
        # Once an order has been credited (by verify or an earlier webhook
        # delivery) never activate again -- a retry carrying a different
        # payment_id used to stack a second subscription period. The
        # compare-and-set makes concurrent verify/webhook deliveries safe.
        if attempt.status == 'successful':
            if attempt.razorpay_payment_id != payment_id:
                logger.warning(
                    'Razorpay webhook: order %s already credited with payment %s; ignoring payment %s',
                    order_id, attempt.razorpay_payment_id, payment_id,
                )
            try:
                _heal_stranded_payment(attempt)
            except Exception:
                logger.exception('Razorpay webhook: could not recover stranded order %s', order_id)
            return Response({'status': 'already_processed'})

        user = attempt.user
        # Claim + activation in one transaction (see SubscribeVerifyView). On
        # failure the claim is rolled back and the 500 makes Razorpay retry.
        try:
            sub = _claim_and_activate(attempt, payment_id, user=user, source='webhook')
        except Exception:
            logger.exception('Razorpay webhook: activation failed for order %s; claim rolled back', order_id)
            return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if sub is None:
            return Response({'status': 'already_processed'})

        logger.info('Webhook activated subscription for %s: %s', user.username, sub.plan_display_name)
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
    POST: Purchase tokens. STUB — payment integration is not yet wired.

    The original implementation accepted an arbitrary `amount` + `payment_id`
    and credited tokens directly. Without a payment-gateway verification
    step (Razorpay / Stripe), that path is a free-for-all: any authenticated
    user could mint unlimited tokens simply by calling the endpoint.

    Until payment integration is finalized, the endpoint is disabled and
    returns 503 with a `payments_unavailable` error code. The frontend
    "/tokens" page reads this code and surfaces a clear "temporarily
    unavailable" notice. The legacy mint code is retained as a private
    helper for tests and legacy fixtures, but is no longer reachable
    from the URL.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_purchase'

    def post(self, request):
        # Payment integration is not yet wired up. Return 503 so the
        # frontend can show a clear "temporarily unavailable" state and
        # we never accidentally mint unlimited tokens from an
        # authenticated-but-unverified endpoint.
        return Response(
            {
                "error": (
                    "Token purchases are temporarily unavailable while "
                    "payment integration is being finalized."
                ),
                "code": "payments_unavailable",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
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

    DEFAULT_LIMIT = 1000
    MAX_LIMIT = 5000

    def get(self, request):
        create_admin_audit_log(
            actor=request.user,
            action='token_view',
            resource_type='token_overview',
            detail='Viewed platform token overview',
        )
        try:
            limit = min(max(int(request.query_params.get('limit', self.DEFAULT_LIMIT)), 1), self.MAX_LIMIT)
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (TypeError, ValueError):
            return Response({'error': 'limit and offset must be integers'}, status=status.HTTP_400_BAD_REQUEST)

        # A fixed number of queries and NO writes, whatever the user count.
        # The old code serialised every TokenBalance through the
        # available_tokens property, i.e. a TokenConfig get_or_create plus a
        # possible counter-reset UPDATE per row (twice: serializer + sum).
        config = TokenConfig.get_config()
        today = timezone.localdate()
        total_purchased = total_feedback = total_consumed = total_available = 0
        balance_count = 0
        # (No .iterator(): server-side cursors break behind a transaction-mode
        # connection pooler.)
        for row in TokenBalance.objects.only(
            'daily_tokens_used', 'weekly_tokens_used', 'last_daily_reset', 'last_weekly_reset',
            'purchased_tokens', 'feedback_credits', 'total_tokens_used',
        ):
            balance_count += 1
            total_purchased += row.purchased_tokens
            total_feedback += row.feedback_credits
            total_consumed += row.total_tokens_used
            total_available += row.available_tokens_readonly(config, today)

        page = TokenBalance.objects.select_related("user").order_by('id')[offset:offset + limit]
        serializer = AdminUserTokenSerializer(page, many=True, context={'token_config': config})
        total_users = User.objects.count()

        return Response(
            {
                "count": balance_count,
                "limit": limit,
                "offset": offset,
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
            if from_user.id == to_user.id:
                return Response({"error": "Source and target user must be different"}, status=400)

            # One atomic unit: the row lock is only valid inside a
            # transaction (Postgres raises TransactionManagementError
            # otherwise) and the debit + credit must succeed or fail
            # together.
            with transaction.atomic():
                from_balance = TokenBalance.objects.select_for_update().filter(user=from_user).first()
                if from_balance is None or from_balance.purchased_tokens < amount:
                    available = from_balance.purchased_tokens if from_balance else 0
                    return Response(
                        {"error": f"{from_user.username} only has {available} purchased tokens"},
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


_PASSWORD_RESET_GONE = {
    'detail': 'Password reset is handled by Supabase Auth. Use "Forgot password" on the sign-in page.',
    'error': 'endpoint_gone',
}


class PasswordResetRequestView(APIView):
    """AUTH_PROVIDER=supabase (default): disabled, 410 -- reset goes through Supabase (resetPasswordForEmail).

    This endpoint used to email a Django uid/token link that the
    /reset-password page ignores (it calls supabase.auth.updateUser), so the
    mail could never work, and anyone could trigger it for any address.
    Returns 410 like the disabled local login/register endpoints.

    AUTH_PROVIDER=django: 202 for any address; a single-use link
    (FRONTEND_URL/reset-password#uid=..&token=..) is mailed when exactly one
    active account has the email (accounts.native_auth.password_reset_request).
    Limited per client IP (password_reset) and per address (password_reset_email).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def get_authenticators(self):
        # django mode: anonymous (a stale bearer token must not turn "Forgot password" into a 401).
        from .auth_mode import django_auth_enabled

        return [] if django_auth_enabled() else super().get_authenticators()

    def get_throttles(self):
        from .auth_mode import django_auth_enabled

        if django_auth_enabled():
            from .throttles import PasswordResetEmailThrottle

            # Per client IP as django-axes sees it (forged forwarding headers stop counting
            # once the client address is hardened; accounts.W007).
            return [ClientIPScopedRateThrottle(), PasswordResetEmailThrottle()]
        return super().get_throttles()

    def post(self, request):
        from .auth_mode import django_auth_enabled

        if django_auth_enabled():
            from .native_auth import password_reset_request

            return password_reset_request(request)
        return Response(_PASSWORD_RESET_GONE, status=status.HTTP_410_GONE)


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
        # One config lookup and no writes for the whole page (the property
        # did a get_or_create + possible UPDATE per user).
        token_config = TokenConfig.get_config()
        today = timezone.localdate()

        results = []
        for u in users:
            bal = balances.get(u.id)
            available = bal.available_tokens_readonly(token_config, today) if bal else 0
            
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
        if blocked:
            # Django-native sessions (AUTH_PROVIDER=django) end now, refresh
            # tokens included; Supabase sessions are refused per request.
            from .native_sessions import revoke_user_sessions

            revoke_user_sessions(target, 'blocked')

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
        # Promotion grants API admin rights (role) and is_staff (needed by
        # DRF IsAdminUser endpoints), but never Django superuser: superusers
        # are only created from trusted sources (Supabase app_metadata, the
        # admin email allowlist, createsuperuser). Demotion removes all three.
        target.is_staff = role == 'admin'
        if role != 'admin':
            target.is_superuser = False
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
        from analytics.models import DailyActivity, StudyStreak, UserBadge, UserTopicPerformance, XPEvent

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
            # The dated XP ledger behind weekly / monthly leaderboards goes
            # with the all-time total reset below.
            xp_events_deleted, _ = XPEvent.objects.filter(user=target).delete()

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
            'xp_events_deleted': xp_events_deleted,
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


# Phrase a platform-wide (scope=all) system action must carry as `confirm`;
# the admin UI asks the admin to type the same phrase
# (frontend/src/app/admin/_lib/adminHelpers.ts PLATFORM_WIDE_CONFIRM_PHRASE).
PLATFORM_WIDE_CONFIRM_PHRASE = 'RESET ALL'


def _system_action_scope(request):
    """Return (scope, None) for an explicit 'all' / 'user' scope, else (None, 400 response).

    A missing or misspelled scope used to default to 'all', so a call like
    {"user_id": 5} wiped every user's attempts or analytics. scope=all also
    needs confirm='RESET ALL', so no single mistaken field rewrites every
    user's data.
    """
    raw_scope = request.data.get('scope')
    scope = raw_scope.strip().lower() if isinstance(raw_scope, str) else ''
    if scope not in ('all', 'user'):
        return None, Response(
            {'error': "scope is required and must be 'all' or 'user'"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if scope == 'all':
        confirm = request.data.get('confirm')
        if not isinstance(confirm, str) or confirm.strip() != PLATFORM_WIDE_CONFIRM_PHRASE:
            return None, Response(
                {
                    'error': f"Platform-wide actions need confirm='{PLATFORM_WIDE_CONFIRM_PHRASE}'.",
                    'code': 'confirmation_required',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    return scope, None


class AdminSystemResetAttemptsView(APIView):
    """Reset test attempts either scoped to one user or globally."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from tests_engine.models import QuestionResponse, TestAttempt

        scope, error_response = _system_action_scope(request)
        if error_response is not None:
            return error_response
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
        from analytics.models import DailyActivity, StudyStreak, UserBadge, UserTopicPerformance, XPEvent

        scope, error_response = _system_action_scope(request)
        if error_response is not None:
            return error_response
        user_id = request.data.get('user_id')
        parsed_user_id = None

        topic_qs = UserTopicPerformance.objects.all()
        daily_qs = DailyActivity.objects.all()
        badge_qs = UserBadge.objects.all()
        streak_qs = StudyStreak.objects.all()
        xp_qs = XPEvent.objects.all()

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
            xp_qs = xp_qs.filter(user_id=parsed_user_id)

        with transaction.atomic():
            topic_rows_deleted, _ = topic_qs.delete()
            daily_rows_deleted, _ = daily_qs.delete()
            badge_rows_deleted, _ = badge_qs.delete()
            # XP totals are reset below; the dated ledger goes with them.
            xp_events_deleted, _ = xp_qs.delete()
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
            'xp_events_deleted': xp_events_deleted,
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


def _rebuild_topic_performance_rows(responses, qbank_attempts):
    """UserTopicPerformance rows rebuilt the way the live writers keep them.

    Live writers (tests_engine.views._record_submission_analytics for test
    answers, questions.practice_experience.record_attempt_stats for a user's
    first answer to a question-bank question) count answered questions only,
    and bump BOTH the subject-level row (topic=NULL, every answer in the
    subject) and, when the question has a topic, the topic row.
    analytics.views.subject_totals() reads the subject-level row, so without
    it the dashboard and score-prediction totals undercounted after a rerun.
    Returns (rows, answered_responses, qbank_answers).
    """
    from analytics.models import UserTopicPerformance

    answered = responses.filter(attempt__is_completed=True, is_correct__isnull=False)
    totals = {}

    def _add(key, attempts, correct, incorrect, seconds, confidence, last):
        row = totals.setdefault(key, {
            'attempts': 0, 'correct': 0, 'incorrect': 0, 'seconds': 0,
            'confidence_sum': 0.0, 'confidence_n': 0, 'last': None,
        })
        row['attempts'] += attempts or 0
        row['correct'] += correct or 0
        row['incorrect'] += incorrect or 0
        row['seconds'] += seconds or 0
        if confidence:
            row['confidence_sum'] += confidence[0]
            row['confidence_n'] += confidence[1]
        if last is not None and (row['last'] is None or last > row['last']):
            row['last'] = last

    response_counts = dict(
        attempts=Count('id'),
        correct=Count('id', filter=Q(is_correct=True)),
        incorrect=Count('id', filter=Q(is_correct=False)),
        seconds=Sum('time_taken_seconds'),
        confidence_sum=Sum('confidence_level'),
        confidence_n=Count('confidence_level'),
        last=Max('attempt__started_at'),
    )
    qbank_counts = dict(
        attempts=Count('id'),
        correct=Count('id', filter=Q(is_correct=True)),
        incorrect=Count('id', filter=Q(is_correct=False)),
        last=Max('attempted_at'),
    )
    groupings = (
        # (queryset, user field, extra grouping, counts) -- subject level, then topic level.
        (answered, 'attempt__user_id', (), response_counts),
        (answered.filter(question__topic__isnull=False), 'attempt__user_id', ('question__topic_id',), response_counts),
        (qbank_attempts, 'user_id', (), qbank_counts),
        (qbank_attempts.filter(question__topic__isnull=False), 'user_id', ('question__topic_id',), qbank_counts),
    )
    answered_total = qbank_total = 0
    for queryset, user_field, extra, counts in groupings:
        for row in queryset.order_by().values(user_field, 'question__subject_id', *extra).annotate(**counts):
            key = (row[user_field], row['question__subject_id'], row['question__topic_id'] if extra else None)
            confidence = (row['confidence_sum'] or 0, row['confidence_n'] or 0) if 'confidence_n' in row else None
            _add(key, row['attempts'], row['correct'], row['incorrect'], row.get('seconds'), confidence, row['last'])
            if not extra:
                if user_field == 'user_id':
                    qbank_total += row['attempts'] or 0
                else:
                    answered_total += row['attempts'] or 0

    rows = [
        UserTopicPerformance(
            user_id=user_id,
            subject_id=subject_id,
            topic_id=topic_id,
            total_attempts=t['attempts'],
            correct_answers=t['correct'],
            incorrect_answers=t['incorrect'],
            total_time_seconds=t['seconds'],
            avg_confidence=round(t['confidence_sum'] / t['confidence_n'], 2) if t['confidence_n'] else 0,
            last_attempted=t['last'],
        )
        for (user_id, subject_id, topic_id), t in totals.items()
    ]
    return rows, answered_total, qbank_total


class AdminSystemRerunEvaluationView(APIView):
    """Recompute UserTopicPerformance from test answers and question-bank answers.

    Builds the subject-level row (topic=NULL) and the per-topic rows exactly
    as the live writers maintain them (see _rebuild_topic_performance_rows).
    """

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from analytics.models import UserTopicPerformance
        from questions.models import QuestionAttempt
        from tests_engine.models import QuestionResponse

        scope, error_response = _system_action_scope(request)
        if error_response is not None:
            return error_response
        user_id = request.data.get('user_id')
        parsed_user_id = None

        responses = QuestionResponse.objects.all()
        qbank_attempts = QuestionAttempt.objects.all()
        if scope == 'user':
            if not user_id:
                return Response({'error': 'user_id is required when scope=user'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                return Response({'error': 'user_id must be a valid integer'}, status=status.HTTP_400_BAD_REQUEST)
            responses = responses.filter(attempt__user_id=parsed_user_id)
            qbank_attempts = qbank_attempts.filter(user_id=parsed_user_id)

        rows, answered_total, qbank_total = _rebuild_topic_performance_rows(responses, qbank_attempts)

        with transaction.atomic():
            if scope == 'all':
                UserTopicPerformance.objects.all().delete()
            else:
                UserTopicPerformance.objects.filter(user_id=parsed_user_id).delete()
            UserTopicPerformance.objects.bulk_create(rows)

        metadata = {
            'scope': scope,
            'user_id': parsed_user_id,
            'rows_created': len(rows),
            'subject_rows_created': sum(1 for row in rows if row.topic_id is None),
            'processed_responses': answered_total,
            'processed_qbank_answers': qbank_total,
        }
        create_admin_audit_log(
            actor=request.user,
            action='system_rerun_evaluation',
            resource_type='system',
            detail='Reran evaluation aggregation',
            metadata=metadata,
        )
        return Response({'message': 'Evaluation rerun completed', 'results': metadata})


def _backup_not_configured_response(action, exc):
    """503 for a deployment without CORE_DATA_BACKUP_PATH (see accounts.core_data_backup)."""
    logger.warning('Admin core data %s refused: %s', action.lower(), exc)
    return Response(
        {'error': f'{action} is not available: {exc}', 'code': 'backup_not_configured'},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class AdminSystemBackupDataView(APIView):
    """Backups core configuration data to JSON fixture."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from .core_data_backup import CoreDataBackupError, CoreDataBackupNotConfigured, backup_core_data

        try:
            _path, count = backup_core_data()
        except CoreDataBackupNotConfigured as exc:
            return _backup_not_configured_response('Backup', exc)
        except CoreDataBackupError as exc:
            logger.exception('Admin core data backup failed')
            return Response({'error': f'Backup failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        create_admin_audit_log(
            actor=request.user,
            action='system_backup',
            resource_type='system',
            detail=f'Backed up {count} core data records to JSON',
            metadata={'records': count},
        )
        return Response({'message': f'Core data backup completed: {count} records saved.', 'records': count})


class AdminSystemRestoreDataView(APIView):
    """Restores core configuration data from JSON fixture."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request):
        from .core_data_backup import CoreDataBackupError, CoreDataBackupNotConfigured, restore_core_data

        try:
            count = restore_core_data()
        except CoreDataBackupNotConfigured as exc:
            return _backup_not_configured_response('Restore', exc)
        except CoreDataBackupError as exc:
            logger.exception('Admin core data restore failed')
            return Response({'error': f'Restore failed: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        create_admin_audit_log(
            actor=request.user,
            action='system_restore',
            resource_type='system',
            detail=f'Restored {count} core data records from JSON',
            metadata={'records': count},
        )
        return Response({'message': f'Core data restore completed: {count} records loaded.', 'records': count})

class PasswordResetConfirmView(APIView):
    """AUTH_PROVIDER=supabase (default): disabled (410), see PasswordResetRequestView.

    It set a Django password that no login path uses (sign-in is Supabase
    only) and could give staff a usable Django-admin password.

    AUTH_PROVIDER=django: {uid, token, new_password} sets the password, marks
    the email verified, revokes every session and signs in
    (accounts.native_auth.password_reset_confirm). The token is single-use.
    """

    permission_classes = [permissions.AllowAny]

    def get_authenticators(self):
        from .auth_mode import django_auth_enabled

        return [] if django_auth_enabled() else super().get_authenticators()

    def get_throttles(self):
        from .auth_mode import django_auth_enabled

        if django_auth_enabled():
            return [ClientIPScopedRateThrottle()]  # scope: throttle_scope below
        return super().get_throttles()

    @property
    def throttle_scope(self):
        from .auth_mode import django_auth_enabled

        # Only in django mode, so the supabase-mode 410 keeps its old (default) throttles.
        return 'password_reset' if django_auth_enabled() else None

    def post(self, request):
        from .auth_mode import django_auth_enabled

        if django_auth_enabled():
            from .native_auth import password_reset_confirm

            return password_reset_confirm(request)
        return Response(_PASSWORD_RESET_GONE, status=status.HTTP_410_GONE)


class UserDeviceListView(APIView):
    """List all active devices for the authenticated user.

    Each row carries ``is_current``: true for the device this request comes
    from -- the one the authenticator resolved from the request's Supabase
    session (``request.auth_device_id``), else the row of its X-Session-ID.
    """

    def get(self, request):
        from .models import UserDevice
        from .serializers import UserDeviceSerializer
        from .supabase_rest_auth import _is_valid_session_id

        current_id = getattr(request, 'auth_device_id', None)
        current = request.META.get('HTTP_X_SESSION_ID') or ''
        devices = UserDevice.objects.filter(user=request.user, is_active=True).order_by('-last_login')
        serializer = UserDeviceSerializer(
            devices, many=True,
            context={
                'current_device_id': current_id,
                'current_device_fingerprint': current if _is_valid_session_id(current) else '',
            },
        )
        return Response(serializer.data)


def _end_native_session_of(device) -> None:
    """A logged-out device's Django-native session (AUTH_PROVIDER=django) ends too, refresh token included.

    No-op for Supabase sessions (no AuthSession row): those are refused per
    request (device_inactive) and signed out upstream by the authenticator.
    """
    if device.session_id:
        from .native_sessions import revoke_session

        revoke_session(device.session_id, 'device_logout')


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
            _end_native_session_of(device)
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
            
        from .models import PLAN_FEATURES, invalidate_subscription_status_cache

        action = request.data.get('action') # 'grant', 'revoke'
        plan = request.data.get('plan') # '1_month', '3_months', '1_year', 'legacy'

        if action == 'grant':
            if not plan:
                return Response({'error': 'Plan is required for granting'}, status=status.HTTP_400_BAD_REQUEST)
            # An unknown code used to become a never-expiring premium
            # subscription with an invalid plan code.
            if not isinstance(plan, str) or plan not in PLAN_FEATURES:
                return Response(
                    {'error': 'Unknown plan.', 'available_plans': sorted(PLAN_FEATURES)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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
                action='subscription_grant',
                resource_type='subscription',
                resource_id=str(user.id),
                detail=f'Granted {plan} subscription to {user.username}',
            )
            return Response({'message': f'Subscription {plan} granted to {user.username}'})

        elif action == 'revoke':
            # NOTE: Subscription has no `is_active` column — `is_active` is a
            # @property that derives from status=='active' and not-yet-expired.
            # The prior filter `is_active=True` translated to `WHERE FALSE` and
            # silently matched zero rows, so admins could never actually
            # revoke. Filter by status='active' instead.
            revoked_count = Subscription.objects.filter(
                user=user, status='active'
            ).update(status='cancelled')
            user.is_subscribed = False
            user.save(update_fields=['is_subscribed'])
            invalidate_subscription_status_cache(user.id)

            create_admin_audit_log(
                actor=request.user,
                action='subscription_revoke',
                resource_type='subscription',
                resource_id=str(user.id),
                detail=f'Revoked {revoked_count} active subscription(s) for {user.username}',
                metadata={'revoked_count': revoked_count},
            )
            return Response({
                'message': f'Subscription revoked for {user.username}',
                'revoked_count': revoked_count,
            })
            
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
            _end_native_session_of(device)
            create_admin_audit_log(
                actor=request.user,
                action='device_logout',
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
        from .models_coupons import CouponRedemption
        payments = list(PaymentAttempt.objects.select_related('user').order_by('-created_at')[:100])
        codes = dict(CouponRedemption.objects.filter(razorpay_order_id__in=[p.razorpay_order_id for p in payments])
                     .values_list('razorpay_order_id', 'coupon__code'))
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
                'coupon_code': codes.get(p.razorpay_order_id, ''),
                'created_at': p.created_at,
            })
        return Response(data)


