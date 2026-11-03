"""Sign in with Google for the Django-native sign-in (AUTH_PROVIDER=django).

The browser gets an ID token from Google Identity Services and posts it to
POST /api/auth/google/. ``verify_google_credential`` checks it with
``google.oauth2.id_token.verify_oauth2_token``: Google's signature, ``exp``
(10 s of clock skew), the issuer (accounts.google.com) and the audience
(one of GOOGLE_OAUTH_CLIENT_IDS). Google's certificates are cached as long
as their Cache-Control allows; a certificate fetch that fails or takes over
3 s is ``503 google_unavailable``. A token is accepted once (its ``jti`` is
remembered until it expires).

Accounts are matched on Google's ``sub`` (``UserIdentity``) only, never on an
email alone (``resolve_google_sign_in``):

1. a known ``sub`` signs its account in; the local email is never changed;
2. otherwise Google must say the email is verified (``400 google_email_unverified``);
3. no account with that email: a new verified student account plus its identity;
4. one account with that email: admin / staff / superuser rows are linked by an
   operator only (``409 account_link_required``); for any other account a
   single-use link valid 30 minutes is mailed to the account's address
   (``409 google_link_required``, no session). Opening it
   (POST /api/auth/google/confirm-link/) links the identity and signs in;
5. several accounts with that email: ``409 account_link_required``.

The emailed link is a signed value (django.core.signing) holding the account
id, the ``sub`` and an HMAC of the account's sign-in state (email, password
hash, last_login, active flag): it stops working after any sign-in, password
or email change, so it is single-use without server-side storage (which a
per-process cache could not guarantee across workers).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from urllib import error as urlerror, request as urlrequest

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .native_sessions import NativeAuthError
from .throttles import consume_email_quota, normalized_email

logger = logging.getLogger(__name__)

PROVIDER = 'google'
CERTS_TIMEOUT_SECONDS = 3.0
CLOCK_SKEW_SECONDS = 10
_CERTS_CACHE_PREFIX = 'google_oauth_certs:'
_CERTS_MIN_SECONDS, _CERTS_MAX_SECONDS, _CERTS_DEFAULT_SECONDS = 60, 86400, 3600
_USED_TOKEN_PREFIX = 'google_id_token_used:'
_ALLOWED_CERT_URLS = frozenset({
    'https://www.googleapis.com/oauth2/v1/certs',
    'https://www.googleapis.com/oauth2/v3/certs',
})
_MAX_AGE_RE = re.compile(r'max-age\s*=\s*(\d+)', re.IGNORECASE)

LINK_MAX_AGE_SECONDS = 30 * 60
_LINK_SALT = 'accounts.google_identity.link.v1'
_LINK_STATE_SALT = 'accounts.google_identity.link-state.v1'
LINK_EMAIL_SCOPE = 'google_link_email'
# Linking from Settings needs a session at most this old (a recent sign-in).
FRESH_SESSION_SECONDS = 15 * 60

TOKEN_INVALID_DETAIL = 'Google sign-in failed. Please try again.'


def google_client_ids() -> list[str]:
    ids = getattr(settings, 'GOOGLE_OAUTH_CLIENT_IDS', None) or []
    if isinstance(ids, str):
        ids = re.split(r'[\s,]+', ids)
    return [str(i).strip() for i in ids if str(i).strip()]


def google_sign_in_enabled() -> bool:
    return bool(google_client_ids())


# ── Certificates (google.auth.transport.Request compatible) ─────────────

class _CertsResponse:
    """The google.auth.transport.Response shape (status, headers, data)."""

    def __init__(self, data: bytes, status: int = 200, headers=None):
        self.status = status
        self.headers = headers or {}
        self.data = data


def _max_age(headers) -> int:
    value = ''
    try:
        value = headers.get('Cache-Control', '') or ''
    except AttributeError:
        value = ''
    match = _MAX_AGE_RE.search(value)
    seconds = int(match.group(1)) if match else _CERTS_DEFAULT_SECONDS
    return max(_CERTS_MIN_SECONDS, min(_CERTS_MAX_SECONDS, seconds))


def _fetch_certs_document(url: str) -> tuple[bytes, int]:
    """(body, seconds it may be cached) of Google's certificate document. Network: tests patch this."""
    from google.auth import exceptions as google_exceptions

    req = urlrequest.Request(url, headers={'Accept': 'application/json'}, method='GET')
    try:
        with urlrequest.urlopen(req, timeout=CERTS_TIMEOUT_SECONDS) as resp:  # noqa: S310 - fixed https URL
            if int(getattr(resp, 'status', 0) or 0) != 200:
                raise google_exceptions.TransportError('Google certificates unavailable')
            body = resp.read()
            ttl = _max_age(resp.headers)
    except (urlerror.URLError, OSError, ValueError) as exc:
        raise google_exceptions.TransportError('Google certificates unavailable') from exc
    return body, ttl


class CachingCertsRequest:
    """A google.auth transport that serves Google's certificate URLs from the Django cache."""

    def __call__(self, url, method='GET', body=None, headers=None, timeout=None, **kwargs):
        from google.auth import exceptions as google_exceptions

        if method != 'GET' or url not in _ALLOWED_CERT_URLS:
            raise google_exceptions.TransportError('Unexpected request from the Google token verifier')
        key = _CERTS_CACHE_PREFIX + hashlib.sha256(url.encode('utf-8')).hexdigest()
        try:
            cached = cache.get(key)
        except Exception:  # noqa: BLE001 - a cache outage means a fetch
            cached = None
        if cached:
            return _CertsResponse(cached)
        data, ttl = _fetch_certs_document(url)
        try:
            parsed = json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as exc:
            raise google_exceptions.TransportError('Google certificates unreadable') from exc
        if not isinstance(parsed, dict) or not parsed:
            raise google_exceptions.TransportError('Google certificates unreadable')
        try:
            cache.set(key, data, ttl)
        except Exception:  # noqa: BLE001
            pass
        return _CertsResponse(data)


# ── ID token ────────────────────────────────────────────────────────────

def _remember_once(claims: dict, credential: str) -> bool:
    """True the first time this token is seen (jti, else a digest of the token) until it expires."""
    jti = str(claims.get('jti') or '') or hashlib.sha256(credential.encode('utf-8')).hexdigest()
    try:
        exp = int(float(claims.get('exp') or 0))
    except (TypeError, ValueError):
        exp = 0
    ttl = max(60, exp - int(time.time()) + CLOCK_SKEW_SECONDS)
    key = _USED_TOKEN_PREFIX + hashlib.sha256(jti.encode('utf-8')).hexdigest()
    try:
        return bool(cache.add(key, 1, timeout=ttl))
    except Exception:  # noqa: BLE001 - without a cache the signature and exp checks still apply
        return True


def verify_google_credential(credential) -> dict:
    """The verified claims of a Google ID token, or NativeAuthError (401 / 503)."""
    from google.auth import exceptions as google_exceptions
    from google.oauth2 import id_token

    audiences = google_client_ids()
    if not audiences:
        raise NativeAuthError('google_not_configured', 'Google sign-in is not available right now.', 503)
    if not isinstance(credential, str) or not credential.strip() or len(credential) > 8192:
        raise NativeAuthError('google_token_invalid', TOKEN_INVALID_DETAIL, 401)
    credential = credential.strip()
    try:
        claims = id_token.verify_oauth2_token(
            credential, CachingCertsRequest(), audience=audiences, clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
        )
    except google_exceptions.TransportError:
        logger.warning('Google certificates could not be fetched; Google sign-in refused for now.')
        raise NativeAuthError(
            'google_unavailable', 'Google sign-in is temporarily unavailable. Please try again.', 503,
        ) from None
    except (ValueError, TypeError, KeyError, google_exceptions.GoogleAuthError):
        raise NativeAuthError('google_token_invalid', TOKEN_INVALID_DETAIL, 401) from None
    if not isinstance(claims, dict):
        raise NativeAuthError('google_token_invalid', TOKEN_INVALID_DETAIL, 401)
    sub = str(claims.get('sub') or '').strip()
    if not sub or len(sub) > 255:
        raise NativeAuthError('google_token_invalid', TOKEN_INVALID_DETAIL, 401)
    if not _remember_once(claims, credential):
        raise NativeAuthError('google_token_invalid', 'This Google sign-in was already used. Please try again.', 401)
    return claims


def _email_verified(claims: dict) -> bool:
    value = claims.get('email_verified')
    return value is True or str(value).strip().lower() == 'true'


# ── Account rules ───────────────────────────────────────────────────────

def is_privileged(user) -> bool:
    return bool(user.role == 'admin' or user.is_staff or user.is_superuser)


def _blocked():
    return NativeAuthError(
        'account_blocked', 'This account has been blocked. Contact support if you think this is a mistake.', 403,
    )


def _link_required():
    return NativeAuthError(
        'account_link_required',
        'This account must be verified by an administrator before it can sign in with Google. '
        'Please contact support.',
        409,
    )


def _name_parts(claims: dict) -> tuple[str, str]:
    first = str(claims.get('given_name') or '').strip()
    last = str(claims.get('family_name') or '').strip()
    if not first and not last:
        full = str(claims.get('name') or '').strip()
        first, _, last = full.partition(' ')
    return first[:150], last.strip()[:150]


def _picture(claims: dict) -> str:
    url = str(claims.get('picture') or '').strip()
    return url if url.startswith('https://') and len(url) <= 200 else ''


def _touch_identity(identity, claims):
    fields = {'last_sign_in_at': timezone.now()}
    email = normalized_email(claims.get('email'))
    if email and email != identity.email:
        fields['email'] = email[:254]
        fields['email_verified'] = _email_verified(claims)
    type(identity).objects.filter(pk=identity.pk).update(**fields)


def _create_google_account(claims, sub, email):
    from django.contrib.auth import get_user_model

    from .handles import username_for_new_account
    from .models import PendingSignup, TokenBalance, UserIdentity

    User = get_user_model()
    first, last = _name_parts(claims)
    now = timezone.now()
    with transaction.atomic():
        user = User(
            username=username_for_new_account(User, None, email),
            email=email,
            first_name=first,
            last_name=last,
            avatar_url=_picture(claims),
            role='student',
            email_verified_at=now,
        )
        user.set_unusable_password()
        user.save()
        TokenBalance.objects.get_or_create(user=user)
        UserIdentity.objects.create(
            user=user, provider=PROVIDER, subject=sub, email=email[:254], email_verified=True,
            source='signup', last_sign_in_at=now,
        )
        PendingSignup.objects.filter(email=email).delete()
    return user


def resolve_google_sign_in(claims: dict, request=None):
    """(user, created) for verified Google claims, or NativeAuthError (rules in the module docstring)."""
    from django.contrib.auth import get_user_model

    from .models import UserIdentity

    User = get_user_model()
    sub = str(claims['sub']).strip()
    identity = UserIdentity.objects.select_related('user').filter(provider=PROVIDER, subject=sub).first()
    if identity is not None:
        user = identity.user
        if not user.is_active:
            raise _blocked()
        _touch_identity(identity, claims)
        if user.email_verified_at is None:
            google_email = normalized_email(claims.get('email'))
            if _email_verified(claims) and google_email and google_email == normalized_email(user.email):
                # Google attests the very address of the account.
                user.email_verified_at = timezone.now()
                User.objects.filter(pk=user.pk, email_verified_at__isnull=True).update(
                    email_verified_at=user.email_verified_at,
                )
            else:
                from .native_auth import send_legacy_verification

                send_legacy_verification(user)
                raise NativeAuthError(
                    'email_not_confirmed',
                    'Please confirm your email address: we sent you a link.',
                    401,
                )
        return user, False

    email = normalized_email(claims.get('email'))
    if not email or not _email_verified(claims):
        raise NativeAuthError(
            'google_email_unverified', 'Your Google account email is not verified, so it cannot be used to sign in.',
            400,
        )

    rows = list(User.objects.filter(email__iexact=email).order_by('id')[:2])
    if not rows:
        from .native_auth import signup_enabled

        if not signup_enabled():
            raise NativeAuthError('signup_disabled', 'New sign-ups are closed right now.', 403)
        try:
            return _create_google_account(claims, sub, email), True
        except IntegrityError:
            # A concurrent request created this identity (or an account took the address).
            identity = UserIdentity.objects.select_related('user').filter(provider=PROVIDER, subject=sub).first()
            if identity is None:
                raise _link_required() from None
            if not identity.user.is_active:
                raise _blocked() from None
            return identity.user, False
    if len(rows) > 1:
        logger.warning('Google sign-in for an email shared by several accounts (ids %s); refused.',
                       ', '.join(str(r.pk) for r in rows))
        raise _link_required()
    row = rows[0]
    if is_privileged(row):
        logger.warning('Google sign-in for privileged account id=%s without a linked identity; refused.', row.pk)
        raise _link_required()
    if not row.is_active:
        raise _blocked()
    send_link_mail(row, sub)
    raise NativeAuthError(
        'google_link_required',
        'An account with this email already exists. We sent a link to that address: open it to connect '
        'your Google account.',
        409,
    )


# ── Emailed link confirmation ───────────────────────────────────────────

def _link_state(user, sub: str) -> str:
    last_login = user.last_login.isoformat() if user.last_login else ''
    value = '|'.join((
        str(user.pk), sub, normalized_email(user.email), user.password or '', last_login, str(bool(user.is_active)),
    ))
    return salted_hmac(_LINK_STATE_SALT, value, algorithm='sha256').hexdigest()


def make_link_token(user, sub: str) -> str:
    return signing.dumps({'u': user.pk, 's': sub, 'h': _link_state(user, sub)}, salt=_LINK_SALT, compress=True)


def _frontend_url(path: str) -> str:
    base = str(getattr(settings, 'FRONTEND_URL', '') or 'http://localhost:3000').rstrip('/')
    return f'{base}{path}'


def send_link_mail(user, sub: str) -> bool:
    """Mail the connect-Google link (at most GOOGLE_LINK_EMAIL rate per address). True when queued."""
    from .emails import send_mail_in_background

    if not consume_email_quota(LINK_EMAIL_SCOPE, user.email):
        return False
    link = _frontend_url(f'/connect-google#token={make_link_token(user, sub)}')
    name = user.first_name or user.username
    send_mail_in_background(
        subject='Connect Google sign-in to your CrackLabs account',
        message=(
            f'Hi {name},\n\n'
            'Someone tried to sign in to CrackLabs with a Google account that uses this email address. '
            'Your CrackLabs account was not signed in.\n\n'
            'If it was you, open this link within 30 minutes to connect that Google account. You will be '
            f'signed in, and can use "Sign in with Google" from then on:\n{link}\n\n'
            'If it was not you, ignore this email: nothing changes.\n\n'
            'The CrackLabs Team'
        ),
        recipient_list=[user.email],
    )
    return True


def confirm_link(token):
    """The account whose Google link ``token`` was opened, after linking; or NativeAuthError."""
    from django.contrib.auth import get_user_model

    from .models import UserIdentity

    invalid = NativeAuthError(
        'invalid_or_expired_link', 'This link is invalid or has expired. Please sign in with Google again.', 400,
    )
    if not isinstance(token, str) or not token or len(token) > 2048:
        raise invalid
    try:
        payload = signing.loads(token, salt=_LINK_SALT, max_age=LINK_MAX_AGE_SECONDS)
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        raise invalid from None
    if not isinstance(payload, dict):
        raise invalid
    User = get_user_model()
    sub = str(payload.get('s') or '')
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=payload.get('u')).first()
        if user is None or not sub or not constant_time_compare(str(payload.get('h') or ''), _link_state(user, sub)):
            raise invalid
        if is_privileged(user):
            raise _link_required()
        if not user.is_active:
            raise _blocked()
        owner = UserIdentity.objects.filter(provider=PROVIDER, subject=sub).values_list('user_id', flat=True).first()
        if owner is not None and owner != user.pk:
            raise NativeAuthError(
                'identity_in_use', 'This Google account is already connected to another CrackLabs account.', 409,
            )
        if owner is None:
            UserIdentity.objects.create(
                user=user, provider=PROVIDER, subject=sub, email=normalized_email(user.email)[:254],
                email_verified=True, source='email_confirmed', last_sign_in_at=timezone.now(),
            )
        fields = ['last_login']
        # Changes the link state under the row lock, so a second request with
        # the same link (even a concurrent one) finds it invalid.
        user.last_login = timezone.now()
        if user.email_verified_at is None:
            # The link was mailed to this address.
            user.email_verified_at = user.last_login
            fields.append('email_verified_at')
        user.save(update_fields=fields)
    _log_identity_link(user, 'email_confirmed')
    return user


def _log_identity_link(user, source: str, actor=None):
    from .views import create_admin_audit_log

    create_admin_audit_log(
        actor=actor,
        action='identity_link',
        resource_type='user',
        resource_id=user.pk,
        detail=f'Google identity linked ({source})',
        metadata={'provider': PROVIDER, 'source': source},
    )


# ── Settings: link / unlink while signed in ─────────────────────────────

def link_to_signed_in_user(user, claims, session) -> None:
    """Attach the Google identity of ``claims`` to ``user`` (a recent native session), or NativeAuthError."""
    from .models import UserIdentity

    if is_privileged(user):
        raise _link_required()
    if session is None or session.created_at is None or (
        (timezone.now() - session.created_at).total_seconds() > FRESH_SESSION_SECONDS
    ):
        raise NativeAuthError(
            'reauthentication_required', 'For your security, sign in again before connecting Google.', 403,
        )
    sub = str(claims['sub']).strip()
    with transaction.atomic():
        owner = UserIdentity.objects.filter(provider=PROVIDER, subject=sub).values_list('user_id', flat=True).first()
        if owner == user.pk:
            return
        if owner is not None:
            raise NativeAuthError(
                'identity_in_use', 'This Google account is already connected to another CrackLabs account.', 409,
            )
        if UserIdentity.objects.filter(user=user, provider=PROVIDER).exists():
            raise NativeAuthError(
                'google_already_linked', 'Another Google account is already connected. Disconnect it first.', 409,
            )
        try:
            with transaction.atomic():
                UserIdentity.objects.create(
                    user=user, provider=PROVIDER, subject=sub,
                    email=normalized_email(claims.get('email'))[:254], email_verified=_email_verified(claims),
                    source='user_linked', last_sign_in_at=timezone.now(),
                )
        except IntegrityError:
            raise NativeAuthError(
                'identity_in_use', 'This Google account is already connected to another CrackLabs account.', 409,
            ) from None
    _log_identity_link(user, 'user_linked', actor=user)


def unlink_from_user(user) -> int:
    """Remove the account's Google identities; refused when it would leave no way to sign in."""
    from .models import UserIdentity

    google = UserIdentity.objects.filter(user=user, provider=PROVIDER)
    if not google.exists():
        raise NativeAuthError('google_not_linked', 'No Google account is connected.', 404)
    others = UserIdentity.objects.filter(user=user).exclude(provider=PROVIDER).exists()
    if not user.has_usable_password() and not others:
        raise NativeAuthError(
            'last_sign_in_method',
            'Set a password first ("Forgot password" on the sign-in page), then disconnect Google.',
            409,
        )
    removed, _ = google.delete()
    from .views import create_admin_audit_log

    create_admin_audit_log(
        actor=user, action='identity_link', resource_type='user', resource_id=user.pk,
        detail='Google identity disconnected by the account owner', metadata={'provider': PROVIDER, 'removed': removed},
    )
    return removed

