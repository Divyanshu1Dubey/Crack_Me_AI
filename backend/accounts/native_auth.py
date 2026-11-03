"""Django-native sign-in endpoints (AUTH_PROVIDER=django). Every view answers 404 in supabase mode.

Mounted under /api/auth/ (accounts/urls.py):

  POST native/login/                {email, password}            -> 200 tokens
  POST native/refresh/              {refresh}                    -> 200 {access, refresh?, session_id}
  POST native/logout/               {refresh?} (+ bearer)        -> 200
  POST native/register/             {email, password, username?, first_name?, last_name?} -> 202
  POST native/verify-email/         {token, password} | {uid, token} -> 201 / 200 tokens
  POST native/resend-verification/  {email}                      -> 202
  POST native/password/             {current_password, new_password} (bearer) -> 200
  POST google/                      {credential}                 -> 200 / 201 tokens (accounts.google_identity)
  POST google/confirm-link/         {token}                      -> 200 tokens
  POST / DELETE google/link/        {credential} (bearer)        -> 200
  GET  config/                      -> {auth_provider, google_client_id, signup_enabled} (both modes)

Password reset keeps its URLs (accounts.views.PasswordResetRequestView /
PasswordResetConfirmView, 410 in supabase mode); in django mode they call
``password_reset_request`` / ``password_reset_confirm`` below.

"tokens" is the body the frontend's token storage reads
(frontend/src/lib/localAuth.ts, as accounts.local_auth._token_payload):
``{access, refresh, session_id, user}``, ``user`` being the profile
(UserSerializer). Errors are ``{detail, code}``.

Rules:
* Sign-in is by email only (case-insensitive, exactly one account). Unknown
  emails and blocked accounts cost one password hash like any other account
  and get the same 401 ``invalid_credentials``. django-axes counts failures
  per (account, client IP) -- 429 ``too_many_attempts`` -- and a per-email
  limit counts failed attempts from every IP (accounts.throttles). Per-IP
  limits key on crack_cms.client_ip (forged forwarding headers do not count).
* ``403 account_blocked`` and ``401 email_not_confirmed`` are only answered
  after the right password; the latter also mails a verification link.
* Sign-up creates no account: each sign-up is its own PendingSignup (the
  hashed password, a digest of the emailed token) until a link is opened; the
  answer is the same 202 whether or not the address is taken. A later sign-up
  with the same address never changes an earlier one -- it may be someone
  else's. Opening a link (POST native/verify-email/ {token, password}) needs
  the password of one of that address's sign-ups: the link proves the
  mailbox, the password picks the sign-up, so nobody else's password ends up
  on the account. ``400 password_mismatch`` otherwise (the link stays usable).
* Accounts that predate native sign-in without a verified email get an
  emailed {uid, token} link (EmailVerificationTokenGenerator): single-use
  (it covers email_verified_at) and valid EMAIL_VERIFICATION_MAX_AGE seconds.
* Password reset: a single-use default_token_generator link valid
  PASSWORD_RESET_TIMEOUT seconds, in the URL fragment of
  FRONTEND_URL/reset-password; confirming it sets the password, verifies the
  email and revokes every session.
"""
from __future__ import annotations

import hashlib
import logging
import math
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password as check_password_hash, make_password
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import exceptions, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from crack_cms.throttling import ClientIPScopedRateThrottle

from .auth_mode import auth_provider, django_auth_enabled
from .device_limits import session_id_from_claims
from .native_auth_authentication import NativeJWTAuthentication
from .native_sessions import (
    NativeAuthError,
    client_ip,
    issue_session_tokens,
    revoke_session,
    revoke_user_sessions,
    rotate,
    session_id_of_token,
)
from .throttles import (
    NativeRefreshThrottle,
    NativeRegisterEmailThrottle,
    NativeVerifyEmailThrottle,
    NativeVerifyLinkThrottle,
    consume_email_quota,
    email_digest,
    email_limit_reached,
    normalized_email,
    record_email_hit,
)

logger = logging.getLogger(__name__)

LOGIN_EMAIL_SCOPE = 'native_login_email'
VERIFY_EMAIL_SCOPE = 'native_verify_email'
_MAX_PASSWORD_CHARS = 4096
_PENDING_TOKEN_BYTES = 32
_DEFAULT_VERIFICATION_MAX_AGE = 86400
# Open sign-ups kept per address; a newer one evicts the oldest.
MAX_PENDING_SIGNUPS_PER_EMAIL = 5

INVALID_CREDENTIALS = 'Incorrect email or password.'
BLOCKED_DETAIL = 'This account has been blocked. Contact support if you think this is a mistake.'
INVALID_LINK_DETAIL = 'This link is invalid or has expired. Please request a new one.'
TOO_MANY_DETAIL = 'Too many attempts. Please wait a few minutes and try again.'
PASSWORD_REQUIRED_DETAIL = 'Enter the password you chose when you signed up.'
PASSWORD_MISMATCH_DETAIL = (
    'That is not the password you chose when you signed up with this email. Enter it again, '
    'or sign up again to choose a new one.'
)


def signup_enabled() -> bool:
    return django_auth_enabled() and bool(getattr(settings, 'NATIVE_AUTH_ALLOW_SIGNUP', True))


def _verification_max_age() -> int:
    try:
        return max(60, int(getattr(settings, 'EMAIL_VERIFICATION_MAX_AGE', _DEFAULT_VERIFICATION_MAX_AGE)))
    except (TypeError, ValueError):
        return _DEFAULT_VERIFICATION_MAX_AGE


def _frontend_url(path: str) -> str:
    base = str(getattr(settings, 'FRONTEND_URL', '') or 'http://localhost:3000').rstrip('/')
    return f'{base}{path}'


def _error(code: str, detail: str, http_status: int, **extra) -> Response:
    return Response({'detail': detail, 'code': code, **extra}, status=http_status)


def _validation_messages(exc: DjangoValidationError) -> list[str]:
    return [str(m) for m in exc.messages] or ['This value is not valid.']


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _uid(user) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def _user_from_uid(uidb64):
    User = get_user_model()
    if not isinstance(uidb64, str) or not uidb64 or len(uidb64) > 64:
        return None
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def auth_methods(user) -> dict:
    """How this account can sign in natively: a usable password and / or a linked Google account."""
    from .models import UserIdentity

    cache = getattr(user, '_prefetched_objects_cache', {}) or {}
    if 'identities' in cache:
        google = any(i.provider == UserIdentity.PROVIDER_GOOGLE for i in cache['identities'])
    else:
        google = UserIdentity.objects.filter(user_id=user.pk, provider=UserIdentity.PROVIDER_GOOGLE).exists()
    return {'password': bool(user.has_usable_password()), 'google': google}


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Links that verify the email of an existing account; invalid once it is verified (single-use)."""

    key_salt = 'accounts.native_auth.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        verified = user.email_verified_at.isoformat() if user.email_verified_at else ''
        return f'{user.pk}|{(user.email or "").strip().lower()}|{verified}|{user.is_active}|{timestamp}'

    def check_token(self, user, token):
        """As PasswordResetTokenGenerator.check_token, expiring after EMAIL_VERIFICATION_MAX_AGE."""
        if not (user and isinstance(token, str) and token):
            return False
        try:
            ts_b36, _ = token.split('-')
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(self._make_token_with_timestamp(user, ts, secret), token):
                break
        else:
            return False
        return (self._num_seconds(self._now()) - ts) <= _verification_max_age()


email_verification_token_generator = EmailVerificationTokenGenerator()


# ── Mail ────────────────────────────────────────────────────────────────

def _mail(subject: str, message: str, recipient: str) -> None:
    from .emails import send_mail_in_background

    send_mail_in_background(subject=subject, message=message, recipient_list=[recipient])


def send_pending_verification(email: str, token: str, name: str = '') -> None:
    link = _frontend_url(f'/verify-email#token={token}')
    hours = max(1, _verification_max_age() // 3600)
    _mail(
        'Confirm your email for CrackLabs',
        (
            f'Hi{" " + name if name else ""},\n\n'
            'Thanks for signing up for CrackLabs. Open this link and enter the password you chose to '
            f'confirm your email address and finish creating your account (it works once, for {hours} '
            f'hours):\n{link}\n\n'
            'If you did not sign up, ignore this email: no account is created.\n\n'
            'The CrackLabs Team'
        ),
        email,
    )


LEGACY_VERIFICATION_REASONS = ('password', 'google', 'resend')


def _legacy_verification_text(reason: str, link: str) -> str:
    if reason == 'password':
        # Sent only after the CORRECT password was entered: say so, and what to do if it was not the owner.
        return (
            'Someone just signed in to CrackLabs with this email address and its correct password. Before '
            'the first sign-in we need to confirm the address. If it was you, open this link (it works '
            f'once; it signs you in):\n{link}\n\n'
            'If it was NOT you, someone knows your password: do not open the link, and choose a new '
            f'password now: {_frontend_url("/forgot-password")}\n\n'
        )
    if reason == 'google':
        return (
            'Someone just signed in to CrackLabs with the Google account connected to your CrackLabs '
            'account. Before the first sign-in we need to confirm this email address. If it was you, open '
            f'this link (it works once; it signs you in):\n{link}\n\n'
            'If it was NOT you, do not open the link and contact support.\n\n'
        )
    return (
        'We were asked to send a new link to confirm the email address of your CrackLabs account. Open '
        f'this link (it works once; it signs you in):\n{link}\n\n'
        'If you did not ask for it, ignore this email: nothing changes.\n\n'
    )


def send_legacy_verification(user, *, reason: str, check_quota: bool = True) -> bool:
    """Mail an {uid, token} link that verifies an existing account's email. True when queued.

    ``reason``: 'password' (a sign-in with the correct password), 'google' (a
    Google sign-in of the linked identity) or 'resend' (someone asked for a new link).
    """
    if reason not in LEGACY_VERIFICATION_REASONS:
        raise ValueError(f'unknown verification reason {reason!r}')
    if not user.email or not user.is_active or user.email_verified_at is not None:
        return False
    if check_quota and not consume_email_quota(VERIFY_EMAIL_SCOPE, user.email):
        return False
    token = email_verification_token_generator.make_token(user)
    link = _frontend_url(f'/verify-email#uid={_uid(user)}&token={token}')
    name = user.first_name or user.username
    _mail(
        'Confirm your email for CrackLabs',
        f'Hi {name},\n\n{_legacy_verification_text(reason, link)}The CrackLabs Team',
        user.email,
    )
    return True


def _send_already_registered(user) -> None:
    _mail(
        'You already have a CrackLabs account',
        (
            f'Hi {user.first_name or user.username},\n\n'
            'Someone tried to sign up for CrackLabs with this email address, but you already have an '
            f'account. Sign in here: {_frontend_url("/login")}\n'
            f'Forgot your password? Reset it here: {_frontend_url("/forgot-password")}\n\n'
            'If this was not you, ignore this email: nothing has changed.\n\n'
            'The CrackLabs Team'
        ),
        user.email,
    )


def _send_password_reset(user) -> None:
    token = default_token_generator.make_token(user)
    link = _frontend_url(f'/reset-password#uid={_uid(user)}&token={token}')
    minutes = max(1, int(getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600)) // 60)
    _mail(
        'Reset your CrackLabs password',
        (
            f'Hi {user.first_name or user.username},\n\n'
            'We received a request to reset (or set) the password of your CrackLabs account. Open this '
            f'link to choose a new password (it works once, for {minutes} minutes):\n{link}\n\n'
            'If you did not ask for this, ignore this email: your password stays the same.\n\n'
            'The CrackLabs Team'
        ),
        user.email,
    )


def _send_welcome(user) -> None:
    from .supabase_rest_auth import SupabaseJWTAuthentication

    SupabaseJWTAuthentication._send_welcome_email(user)


# ── Sessions ────────────────────────────────────────────────────────────

def _reset_axes_for(user, request) -> None:
    """A successful sign-in clears the failures of this (account, client IP), as AXES_RESET_ON_SUCCESS does."""
    try:
        from axes.handlers.proxy import AxesProxyHandler

        ip = getattr(request, 'axes_ip_address', None) or client_ip(request)
        if ip:
            AxesProxyHandler.reset_attempts(ip_address=ip, username=user.get_username())
    except Exception:  # noqa: BLE001 - bookkeeping only
        logger.debug('Could not reset axes attempts', exc_info=True)


def signed_in_response(request, user, method: str, http_status: int = status.HTTP_200_OK, **extra) -> Response:
    """Create a native session for ``user`` and answer with the frontend's token body."""
    from .serializers import UserSerializer

    tokens = issue_session_tokens(user, request, method)
    update_last_login(None, user)  # not user_logged_in: axes would create a Django session per sign-in
    _reset_axes_for(user, request)
    body = {
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'session_id': tokens['session_id'],
        'user': UserSerializer(user, context={'request': request}).data,
        **extra,
    }
    return Response(body, status=http_status)


# ── Views ───────────────────────────────────────────────────────────────

class _NativeView(APIView):
    """Anonymous native-auth endpoint: 404 unless AUTH_PROVIDER=django, ``{detail, code}`` errors.

    Per-IP limits (``throttle_scope``) key on crack_cms.client_ip.get_client_ip,
    the address django-axes uses: forged X-Forwarded-For / CF-Connecting-IP
    headers never open a new bucket.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    throttle_classes = [ClientIPScopedRateThrottle]

    def initial(self, request, *args, **kwargs):
        if not django_auth_enabled():
            raise Http404
        return super().initial(request, *args, **kwargs)

    def throttled(self, request, wait):
        # Not Throttled(wait=..., detail={...}): with a wait, DRF appends "Expected available in N
        # seconds" to the detail with str.join, which raises TypeError for a dict (HTTP 500 instead
        # of 429). Setting .wait afterwards keeps the Retry-After header DRF's handler sends.
        exc = exceptions.Throttled(detail={'detail': TOO_MANY_DETAIL, 'code': 'too_many_attempts'})
        exc.wait = math.ceil(wait) if wait is not None else None
        raise exc

    def handle_exception(self, exc):
        if isinstance(exc, NativeAuthError):
            return exc.response()
        return super().handle_exception(exc)


class _SignedInNativeView(_NativeView):
    """A native endpoint for a signed-in account (bearer access token of a native session)."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [NativeJWTAuthentication]

    def current_session(self, request):
        from .models import AuthSession

        payload = getattr(request.auth, 'payload', None)
        sid = session_id_from_claims(payload if isinstance(payload, dict) else None)
        if not sid:
            return None
        return AuthSession.objects.filter(sid=sid, user_id=request.user.pk).first()


class AuthConfigView(APIView):
    """GET /api/auth/config/: which sign-in the backend runs (both modes; the frontend checks its build)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def get(self, request):
        from .google_identity import google_client_ids

        provider = auth_provider()
        ids = google_client_ids() if provider == 'django' else []
        return Response({
            'auth_provider': provider,
            'google_client_id': ids[0] if ids else '',
            'signup_enabled': signup_enabled(),
        })


class NativeLoginView(_NativeView):
    throttle_scope = 'native_login'

    def post(self, request):
        User = get_user_model()
        data = request.data if hasattr(request.data, 'get') else {}
        email = normalized_email(data.get('email'))
        password = data.get('password')
        if not email or not isinstance(password, str) or not password or len(password) > _MAX_PASSWORD_CHARS:
            return _error('invalid_request', 'Enter your email address and password.', status.HTTP_400_BAD_REQUEST)
        if email_limit_reached(LOGIN_EMAIL_SCOPE, email):
            return _error('too_many_attempts', TOO_MANY_DETAIL, status.HTTP_429_TOO_MANY_REQUESTS)

        rows = list(User.objects.filter(email__iexact=email).order_by('pk')[:2])
        row = rows[0] if len(rows) == 1 else None
        if row is not None and not row.is_active:
            return self._blocked_account(request, row, email, password)
        # No single account: a name no account has (':' is never in a
        # username), so ModelBackend still hashes the password once (same
        # timing) and axes counts the failures of this address as well.
        username = row.get_username() if row is not None else f'unknown-email:{email_digest(email)[:40]}'
        user = authenticate(request=request, username=username, password=password)
        if getattr(request, 'axes_locked_out', False):
            record_email_hit(LOGIN_EMAIL_SCOPE, email)
            return _error('too_many_attempts', TOO_MANY_DETAIL, status.HTTP_429_TOO_MANY_REQUESTS)
        if user is None:
            record_email_hit(LOGIN_EMAIL_SCOPE, email)
            return _error('invalid_credentials', INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)
        if user.email_verified_at is None:
            send_legacy_verification(user, reason='password')
            return _error(
                'email_not_confirmed',
                'Please confirm your email address: we sent you a link. Open it, then sign in.',
                status.HTTP_401_UNAUTHORIZED,
            )
        return signed_in_response(request, user, 'password')

    @staticmethod
    def _blocked_account(request, row, email, password):
        """A blocked account: ONE password check, as for every other account; 'blocked' only with the right password.

        authenticate() would check the password (ModelBackend) and then refuse
        the inactive row, and a second check to tell "blocked" from "wrong
        password" doubled the time of a failure -- which told anyone which
        emails belong to blocked accounts. django-axes is consulted and told
        about a failure as authenticate() does.
        """
        from axes.handlers.proxy import AxesProxyHandler
        from django.contrib.auth.signals import user_login_failed

        credentials = {'username': row.get_username()}
        record_email_hit(LOGIN_EMAIL_SCOPE, email)
        if not AxesProxyHandler.is_allowed(request, credentials):
            return _error('too_many_attempts', TOO_MANY_DETAIL, status.HTTP_429_TOO_MANY_REQUESTS)
        if check_password_hash(password, row.password):  # no setter: never re-hashed
            return _error('account_blocked', BLOCKED_DETAIL, status.HTTP_403_FORBIDDEN)
        user_login_failed.send(sender=__name__, credentials=credentials, request=request)
        if getattr(request, 'axes_locked_out', False):
            return _error('too_many_attempts', TOO_MANY_DETAIL, status.HTTP_429_TOO_MANY_REQUESTS)
        return _error('invalid_credentials', INVALID_CREDENTIALS, status.HTTP_401_UNAUTHORIZED)


class NativeRefreshView(_NativeView):
    throttle_classes = [NativeRefreshThrottle]

    def post(self, request):
        data = request.data if hasattr(request.data, 'get') else {}
        result = rotate(data.get('refresh'))
        return Response(result)


class NativeLogoutView(_NativeView):
    """Ends the session of the refresh token (and of the bearer access token). The device keeps its slot."""

    throttle_classes = [NativeRefreshThrottle]

    def post(self, request):
        data = request.data if hasattr(request.data, 'get') else {}
        sids = set()
        sid, _user_id = session_id_of_token(data.get('refresh'), 'RefreshToken')
        if sid:
            sids.add(sid)
        header = request.META.get('HTTP_AUTHORIZATION', '')
        parts = header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            sid, _user_id = session_id_of_token(parts[1], 'AccessToken')
            if sid:
                sids.add(sid)
        for sid in sids:
            revoke_session(sid, 'logout')
        return Response({'detail': 'Signed out.'})


def _optional_text(data, name: str, limit: int = 150) -> str:
    value = data.get(name)
    return value.strip()[:limit] if isinstance(value, str) else ''


class NativeRegisterView(_NativeView):
    throttle_scope = 'native_register'
    throttle_classes = [ClientIPScopedRateThrottle, NativeRegisterEmailThrottle]

    def post(self, request):
        from .models import PendingSignup

        User = get_user_model()
        if not signup_enabled():
            return _error('signup_disabled', 'New sign-ups are closed right now.', status.HTTP_403_FORBIDDEN)
        data = request.data if hasattr(request.data, 'get') else {}
        email = normalized_email(data.get('email'))
        try:
            if not email:
                raise DjangoValidationError('Enter a valid email address.')
            validate_email(email)
        except DjangoValidationError:
            return _error('invalid_email', 'Enter a valid email address.', status.HTTP_400_BAD_REQUEST)
        password = data.get('password')
        username = _optional_text(data, 'username')
        first_name, last_name = _optional_text(data, 'first_name'), _optional_text(data, 'last_name')
        if not isinstance(password, str) or not password or len(password) > _MAX_PASSWORD_CHARS:
            return _error('invalid_password', 'Choose a password.', status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, User(username=username, email=email, first_name=first_name, last_name=last_name))
        except DjangoValidationError as exc:
            messages = _validation_messages(exc)
            return _error('invalid_password', messages[0], status.HTTP_400_BAD_REQUEST, errors={'password': messages})

        now = timezone.now()
        existing = User.objects.filter(email__iexact=email).order_by('pk').first()
        if existing is not None:
            # Same answer as a new address; the owner learns about the attempt.
            _send_already_registered(existing)
        else:
            token = secrets.token_urlsafe(_PENDING_TOKEN_BYTES)
            with transaction.atomic():
                PendingSignup.objects.filter(expires_at__lt=now - timedelta(days=7)).delete()
                PendingSignup.objects.filter(email=email, expires_at__lte=now).delete()
                # A sign-up of its own: an earlier sign-up with this address (maybe
                # somebody else's) keeps its password and its link. The oldest
                # open ones beyond the cap are dropped.
                keep = list(
                    PendingSignup.objects.filter(email=email).order_by('-created_at', '-pk')
                    .values_list('pk', flat=True)[:MAX_PENDING_SIGNUPS_PER_EMAIL - 1]
                )
                PendingSignup.objects.filter(email=email).exclude(pk__in=keep).delete()
                PendingSignup.objects.create(
                    email=email,
                    password=make_password(password),
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    token_hash=_hash_token(token),
                    expires_at=now + timedelta(seconds=_verification_max_age()),
                    ip_address=client_ip(request),
                )
            send_pending_verification(email, token, first_name)
        return Response(
            {
                'needs_email_confirmation': True,
                'detail': 'Check your inbox: we sent you a link to confirm your email address.',
            },
            status=status.HTTP_202_ACCEPTED,
        )


def _create_account_from_pending(pending):
    from django.contrib.auth import get_user_model

    from .handles import generate_handle, username_for_new_account
    from .models import TokenBalance

    User = get_user_model()
    for attempt in range(2):
        username = (
            username_for_new_account(User, pending.username, pending.email) if attempt == 0 else generate_handle(User)
        )
        try:
            with transaction.atomic():
                user = User(
                    username=username,
                    email=pending.email,
                    first_name=pending.first_name,
                    last_name=pending.last_name,
                    role='student',
                    email_verified_at=timezone.now(),
                )
                user.password = pending.password  # hashed at sign-up
                user.save()
                TokenBalance.objects.get_or_create(user=user)
            return user
        except IntegrityError:
            if attempt:
                raise
    raise IntegrityError('could not create the account')  # pragma: no cover


class NativeVerifyEmailView(_NativeView):
    """Open an emailed link: {token, password} finishes a sign-up, {uid, token} confirms an existing account.

    Limited per client IP (native_verify) and per link (native_verify_link).
    """

    throttle_scope = 'native_verify'
    throttle_classes = [ClientIPScopedRateThrottle, NativeVerifyLinkThrottle]

    def post(self, request):
        data = request.data if hasattr(request.data, 'get') else {}
        token = data.get('token')
        uid = data.get('uid')
        if uid:
            return self._verify_existing_account(request, uid, token)
        return self._verify_pending_signup(request, token, data.get('password'))

    def _verify_pending_signup(self, request, token, password):
        """Create the account of the sign-up whose password is given; the link proves the mailbox.

        Every link mailed to an address goes to the same inbox, so any open
        link of that address will do; the password chooses WHICH sign-up of
        the address becomes the account. Someone who signed up with another
        person's address cannot get that person to create an account with the
        stranger's password just by opening the mail.
        """
        from .models import PendingSignup

        User = get_user_model()
        if not isinstance(token, str) or not 16 <= len(token) <= 256:
            return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
        if not isinstance(password, str) or not password:
            return _error('password_required', PASSWORD_REQUIRED_DETAIL, status.HTTP_400_BAD_REQUEST)
        outcome, user = None, None
        now = timezone.now()
        with transaction.atomic():
            pending = PendingSignup.objects.select_for_update().filter(token_hash=_hash_token(token)).first()
            if pending is None:
                outcome = 'invalid'
            elif pending.expires_at <= now:
                pending.delete()
                outcome = 'invalid'
            elif User.objects.filter(email__iexact=pending.email).exists():
                PendingSignup.objects.filter(email=pending.email).delete()
                outcome = 'exists'
            else:
                open_signups = list(
                    PendingSignup.objects.select_for_update()
                    .filter(email=pending.email, expires_at__gt=now).order_by('-created_at', '-pk')
                )
                # This link's own sign-up first, then the address's other open ones.
                open_signups.sort(key=lambda p: p.pk != pending.pk)
                chosen = None
                if len(password) <= _MAX_PASSWORD_CHARS:
                    chosen = next((p for p in open_signups if check_password_hash(password, p.password)), None)
                if chosen is None:
                    outcome = 'mismatch'  # nothing is consumed: the owner may type it again
                else:
                    user = _create_account_from_pending(chosen)
                    PendingSignup.objects.filter(email=pending.email).delete()
        if outcome == 'invalid':
            return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
        if outcome == 'mismatch':
            return _error('password_mismatch', PASSWORD_MISMATCH_DETAIL, status.HTTP_400_BAD_REQUEST)
        if outcome == 'exists':
            return _error(
                'account_exists', 'An account with this email already exists. Please sign in.',
                status.HTTP_409_CONFLICT,
            )
        _send_welcome(user)
        return signed_in_response(request, user, 'verify', status.HTTP_201_CREATED, created=True)

    def _verify_existing_account(self, request, uid, token):
        User = get_user_model()
        user = _user_from_uid(uid)
        if user is None or not email_verification_token_generator.check_token(user, token):
            return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return _error('account_blocked', BLOCKED_DETAIL, status.HTTP_403_FORBIDDEN)
        # Compare-and-set: of two requests with the same link only one signs in.
        if not User.objects.filter(pk=user.pk, email_verified_at__isnull=True).update(email_verified_at=timezone.now()):
            return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
        user.refresh_from_db(fields=['email_verified_at'])
        return signed_in_response(request, user, 'verify')


class NativeResendVerificationView(_NativeView):
    throttle_scope = 'native_verify'
    throttle_classes = [ClientIPScopedRateThrottle, NativeVerifyEmailThrottle]

    def post(self, request):
        from .models import PendingSignup

        User = get_user_model()
        data = request.data if hasattr(request.data, 'get') else {}
        email = normalized_email(data.get('email'))
        if email:
            rows = list(User.objects.filter(email__iexact=email).order_by('pk')[:2])
            now = timezone.now()
            pending = (
                PendingSignup.objects.filter(email=email, expires_at__gt=now).order_by('-created_at', '-pk').first()
            )
            if not rows and pending is not None:
                # A new link for the newest sign-up (its password is unchanged; any
                # link of the address works with the password of any of its sign-ups).
                token = secrets.token_urlsafe(_PENDING_TOKEN_BYTES)
                PendingSignup.objects.filter(pk=pending.pk).update(
                    token_hash=_hash_token(token),
                    expires_at=now + timedelta(seconds=_verification_max_age()),
                )
                send_pending_verification(email, token, pending.first_name)
            elif len(rows) == 1:
                # The view throttle already counted this request for the address.
                send_legacy_verification(rows[0], reason='resend', check_quota=False)
        return Response(
            {'detail': 'If this email needs confirming, we sent a new link.'},
            status=status.HTTP_202_ACCEPTED,
        )


class NativePasswordChangeView(_SignedInNativeView):
    throttle_scope = 'native_password_change'

    def post(self, request):
        User = get_user_model()
        user = request.user
        data = request.data if hasattr(request.data, 'get') else {}
        current = data.get('current_password')
        new = data.get('new_password')
        if not user.has_usable_password():
            return _error(
                'password_not_set',
                'This account has no password yet. Use "Forgot password" on the sign-in page to set one.',
                status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(current, str) or not current or not isinstance(new, str) or not new:
            return _error('invalid_request', 'Enter your current and your new password.', status.HTTP_400_BAD_REQUEST)
        if len(current) > _MAX_PASSWORD_CHARS or len(new) > _MAX_PASSWORD_CHARS:
            return _error('invalid_request', 'That password is too long.', status.HTTP_400_BAD_REQUEST)
        checked = authenticate(request=request, username=user.get_username(), password=current)
        if getattr(request, 'axes_locked_out', False):
            return _error('too_many_attempts', TOO_MANY_DETAIL, status.HTTP_429_TOO_MANY_REQUESTS)
        if checked is None or checked.pk != user.pk:
            # 400, not 401: a 401 would make the frontend refresh and sign out.
            return _error('invalid_credentials', 'Your current password is incorrect.', status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, checked)
        except DjangoValidationError as exc:
            messages = _validation_messages(exc)
            return _error('invalid_password', messages[0], status.HTTP_400_BAD_REQUEST, errors={'new_password': messages})
        session = self.current_session(request)
        with transaction.atomic():
            fresh = User.objects.select_for_update().get(pk=user.pk)
            fresh.set_password(new)
            fresh.save(update_fields=['password'])
            revoked = revoke_user_sessions(fresh, 'password_change', except_sid=session.sid if session else None)
        _reset_axes_for(fresh, request)
        return Response({'detail': 'Password changed. Your other devices have been signed out.', 'revoked_sessions': revoked})


# ── Password reset (called by accounts.views in django mode) ───────────

def password_reset_request(request) -> Response:
    User = get_user_model()
    data = request.data if hasattr(request.data, 'get') else {}
    email = normalized_email(data.get('email'))
    if email:
        rows = list(User.objects.filter(email__iexact=email, is_active=True).order_by('pk')[:2])
        if len(rows) == 1:
            _send_password_reset(rows[0])
    return Response(
        {'detail': 'If an account exists for this email, we sent a link to reset its password.'},
        status=status.HTTP_202_ACCEPTED,
    )


def password_reset_confirm(request) -> Response:
    User = get_user_model()
    data = request.data if hasattr(request.data, 'get') else {}
    token = data.get('token')
    new_password = data.get('new_password') or data.get('password')
    user = _user_from_uid(data.get('uid'))
    if user is None or not isinstance(token, str) or not default_token_generator.check_token(user, token):
        return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
    if not user.is_active:
        return _error('account_blocked', BLOCKED_DETAIL, status.HTTP_403_FORBIDDEN)
    if not isinstance(new_password, str) or not new_password or len(new_password) > _MAX_PASSWORD_CHARS:
        return _error('invalid_password', 'Choose a new password.', status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(new_password, user)
    except DjangoValidationError as exc:
        messages = _validation_messages(exc)
        return _error('invalid_password', messages[0], status.HTTP_400_BAD_REQUEST, errors={'new_password': messages})
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if not default_token_generator.check_token(user, token):  # a concurrent use of the same link
            return _error('invalid_or_expired_link', INVALID_LINK_DETAIL, status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        fields = ['password']
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()  # the link was mailed to this address
            fields.append('email_verified_at')
        user.save(update_fields=fields)
        revoke_user_sessions(user, 'password_reset')
    try:
        from axes.handlers.proxy import AxesProxyHandler

        AxesProxyHandler.reset_attempts(username=user.get_username())  # a locked-out owner can sign in again
    except Exception:  # noqa: BLE001
        logger.debug('Could not reset axes attempts', exc_info=True)
    return signed_in_response(request, user, 'reset', password_reset=True)


# ── Google ──────────────────────────────────────────────────────────────

class GoogleSignInView(_NativeView):
    throttle_scope = 'google_signin'

    def post(self, request):
        from .google_identity import resolve_google_sign_in, verify_google_credential

        data = request.data if hasattr(request.data, 'get') else {}
        claims = verify_google_credential(data.get('credential'))
        user, created = resolve_google_sign_in(claims, request)
        if created:
            _send_welcome(user)
        return signed_in_response(
            request, user, 'google', status.HTTP_201_CREATED if created else status.HTTP_200_OK, created=created,
        )


class GoogleConfirmLinkView(_NativeView):
    throttle_scope = 'google_signin'

    def post(self, request):
        from .google_identity import confirm_link

        data = request.data if hasattr(request.data, 'get') else {}
        user = confirm_link(data.get('token'))
        return signed_in_response(request, user, 'google_link')


class GoogleLinkView(_SignedInNativeView):
    """Connect (POST {credential}) or disconnect (DELETE) Google sign-in from Settings."""

    throttle_scope = 'google_signin'

    def post(self, request):
        from .google_identity import link_to_signed_in_user, verify_google_credential

        data = request.data if hasattr(request.data, 'get') else {}
        claims = verify_google_credential(data.get('credential'))
        link_to_signed_in_user(request.user, claims, self.current_session(request))
        return Response({'detail': 'Google account connected.', 'auth_methods': auth_methods(request.user)})

    def delete(self, request):
        from .google_identity import unlink_from_user

        unlink_from_user(request.user)
        return Response({'detail': 'Google account disconnected.', 'auth_methods': auth_methods(request.user)})
