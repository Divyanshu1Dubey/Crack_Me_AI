"""Device cap shared by both bearer authenticators (docs/AUTHENTICATION.md section 6).

2 devices without a plan, 4 with one (``accounts.utils.is_premium``). A
device is a browser (its X-Session-ID, ``crack_device_id``) bound to the
sign-in session that uses it: the token's ``session_id`` claim, which the
client can neither omit nor forge (``UserDevice.session_id``). Supabase
tokens carry GoTrue's session id; Django-issued tokens carry the
``AuthSession.sid`` (accounts.native_sessions), so the same rules apply in
both AUTH_PROVIDER modes.

``DeviceLimitMixin`` was extracted unchanged in behaviour from
accounts.supabase_rest_auth (which re-exports these names). The only
provider-specific step is ``_end_session(token, session_id)``, called when a
logged-out device's session comes back: the Supabase authenticator signs the
GoTrue session out, the native one revokes its AuthSession.

Per request the rules are evaluated on ONE query (the user's active devices
plus the rows bound to this session or carrying this browser's device id);
writes happen only when a device is enrolled, re-bound or its last_login is
older than a minute.
"""
from __future__ import annotations

import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions

FREE_DEVICE_LIMIT = 2
SUBSCRIBED_DEVICE_LIMIT = 4
# UserDevice.device_fingerprint of a device known only by its session (no
# usable X-Session-ID). ':' never matches _SESSION_ID_PATTERN, so a client
# cannot address these rows through the header.
_SESSION_FINGERPRINT_PREFIX = "sid:"
# Access tokens carry the sign-in session's id (a UUID) as ``session_id``.
_SESSION_CLAIM_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_NIL_UUID = "00000000-0000-0000-0000-000000000000"

# Requests an over-the-limit device may still make, so the user can open
# Settings and free a slot (list / log out devices, load the profile) or buy
# the 4-device plan from this device (/auth/subscribe/...).
_DEVICE_MANAGEMENT_PATHS = ('/auth/profile/', '/auth/devices/', '/auth/logout/', '/auth/subscribe/')
# Read-only requests every signed-in page makes in the background (Header
# token pill, announcements). Without them the over-limit device could not
# stay on /subscription long enough to buy the 4-device plan. Exact paths
# (any /api prefix allowed), safe methods only; they never enrol the device.
_DEVICE_LIMIT_EXEMPT_READS = ('/auth/tokens/', '/analytics/announcements/')
_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})
# A device's last_login is refreshed at most this often.
_DEVICE_TOUCH_INTERVAL = timedelta(seconds=60)
# Devices unseen for this long no longer hold a slot for a NEW device. They
# stay listed in Settings.
_DEVICE_STALE_AFTER = timedelta(days=30)

# SECURITY (Fix #3): The X-Session-ID header is trusted as a device
# fingerprint. Without validation, any client could rotate the header
# (`1`, `2`, `3`, ...) to spawn unlimited parallel devices. Accepted shapes:
#   - a UUID (8-4-4-4-12 hex),
#   - a client-prefixed random id ``^(dev|ses)_[A-Za-z0-9_]{8,80}$``
#     (frontend/src/lib/api.ts),
#   - an alphanumeric token of 16-128 characters ([A-Za-z0-9_-]).
_SESSION_ID_PATTERN = re.compile(
    r"^(?:"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|(?:dev|ses)_[A-Za-z0-9_]{8,80}"
    r"|[A-Za-z0-9_\-]{16,128}"
    r")$"
)


def _auth_failed(code: str, detail: str) -> exceptions.AuthenticationFailed:
    """AuthenticationFailed with a machine-readable ``code`` the frontend acts on."""
    return exceptions.AuthenticationFailed({"detail": detail, "code": code})


def session_id_from_claims(claims) -> str | None:
    """The sign-in session id (``session_id`` claim) of an access token, if any."""
    if not isinstance(claims, dict):
        return None
    value = claims.get("session_id")
    if not isinstance(value, str) or not _SESSION_CLAIM_PATTERN.match(value) or value == _NIL_UUID:
        return None
    return value.lower()


def _is_valid_session_id(value):
    """Return True iff ``value`` looks like a non-spoofable device token."""
    if not value or not isinstance(value, str):
        return False
    if len(value) > 128:
        return False
    return bool(_SESSION_ID_PATTERN.match(value))


def _device_limit_for(user) -> int:
    """4 devices with an active plan, else 2 (accounts.utils.is_premium: Subscription rows)."""
    from .utils import is_premium

    return SUBSCRIBED_DEVICE_LIMIT if is_premium(user) else FREE_DEVICE_LIMIT


def _is_device_management_request(request_obj) -> bool:
    """Requests an over-the-limit device may make without taking a slot."""
    path = request_obj.path
    if any(p in path for p in _DEVICE_MANAGEMENT_PATHS):
        return True
    return request_obj.method in _SAFE_METHODS and any(path.endswith(p) for p in _DEVICE_LIMIT_EXEMPT_READS)


class DeviceLimitMixin:
    """Track the user's devices and enforce the 2 (free) / 4 (premium) cap."""

    def _end_session(self, token, session_id):
        """Provider hook: end the sign-in session of a logged-out device (best effort)."""

    def _enforce_device_limits(self, request_obj, user, session_id=None, token=None):
        """Track the user's devices and enforce the 2 (free) / 4 (premium) cap.

        The binding of the device to the session is looked up first, so:

        * a session whose device was logged out (Settings / admin) or replaced
          gets ``device_inactive`` whatever header it sends or omits, and the
          session itself is ended (``_end_session``);
        * a session without a usable header still counts: it is enrolled as a
          device of its own (fingerprint ``sid:<session id>``) and needs a slot;
        * a new sign-in on a browser takes over that browser's device row (no
          new slot); the session it replaces is retired and refused from then
          on, so one device id shared between people gives one seat at a time.

        A NEW device is enrolled only while the user has fewer active devices
        (seen in the last 30 days) than the cap; otherwise
        ``device_limit_reached`` (except on the device-management paths, so
        Settings can free a slot). Existing devices beyond the cap (e.g. after
        a 4 -> 2 downgrade): the ones used most recently win, judged on
        last_login values from BEFORE this request.

        Tokens without a ``session_id`` claim fall back to the old header-only
        rule.
        """
        from .models import UserDevice

        # SECURITY (Fix #3): only device-token shapes are accepted as
        # X-Session-ID, so enumerating 1, 2, 3, ... cannot multiply devices.
        header_value = request_obj.META.get('HTTP_X_SESSION_ID')
        fingerprint = header_value if header_value and _is_valid_session_id(header_value) else None
        if not session_id and not fingerprint:
            return  # nothing identifies the device (token without a session id)

        # SECURITY (Fix #3b): only trust REMOTE_ADDR for IP-based device
        # bookkeeping. X-Forwarded-For is attacker-controlled when the
        # client can reach the backend directly.
        ip = request_obj.META.get('REMOTE_ADDR', '').strip() or None
        user_agent = request_obj.META.get('HTTP_USER_AGENT', '')[:250]
        management_request = _is_device_management_request(request_obj)
        now = timezone.now()
        limit_cache = []

        def device_limit():
            if not limit_cache:  # one Subscription query, only when it matters
                limit_cache.append(_device_limit_for(user))
            return limit_cache[0]

        def at_limit(count):
            return count >= FREE_DEVICE_LIMIT and count >= device_limit()

        def limit_reached():
            return _auth_failed(
                "device_limit_reached",
                f"Maximum device limit reached ({device_limit()} devices). Please manage devices in Settings.",
            )

        def device_inactive():
            self._end_session(token, session_id)
            return _auth_failed("device_inactive", "This device has been logged out or blocked.")

        # One query: every active device of the user, plus the rows bound to
        # this session or carrying this browser's device id (active or not).
        # The rules below only ever look at those rows.
        wanted = Q(is_active=True)
        if session_id:
            wanted |= Q(session_id=session_id)
        if fingerprint:
            wanted |= Q(device_fingerprint=fingerprint)
        rows = list(UserDevice.objects.filter(user=user).filter(wanted))

        device = None
        if session_id:
            # Inactive rows first: any logged-out or replaced binding ends the session.
            bound = sorted((r for r in rows if r.session_id == session_id), key=lambda r: (r.is_active, -r.pk))
            if bound:
                if not bound[0].is_active:
                    raise device_inactive()
                device = bound[0]

        counted_rows = rows
        if device is None:
            row = next((r for r in rows if fingerprint and r.device_fingerprint == fingerprint), None)
            if row is not None and row.is_active:
                if session_id and row.session_id != session_id:
                    # A new sign-in on this browser: the slot moves to it. The
                    # old session's row is retired, so count from the database.
                    self._bind_device_to_session(row, session_id)
                    counted_rows = None
                device = row
            elif row is not None and (not session_id or not row.session_id):
                # Logged out before its session was recorded (or a token
                # without a session id): the browser must sign in again with a
                # fresh device id, as before.
                raise device_inactive()
            else:
                # A device this user has not used yet, or a fresh sign-in on a
                # browser whose (recorded) session was logged out.
                stale_before = now - _DEVICE_STALE_AFTER
                slots_taken = sum(
                    1 for r in rows if r.is_active and r.last_login is not None and r.last_login >= stale_before
                )
                if at_limit(slots_taken):
                    if management_request:
                        return  # let it reach Settings without taking a slot
                    raise limit_reached()
                if row is not None:
                    device = self._reenrol_device(row, session_id, user_agent, ip, now)
                else:
                    device, _created = UserDevice.objects.get_or_create(
                        user=user,
                        device_fingerprint=fingerprint or _SESSION_FINGERPRINT_PREFIX + session_id,
                        defaults={
                            'device_name': user_agent, 'ip_address': ip, 'is_active': True,
                            'session_id': session_id,
                        },
                    )
                request_obj.auth_device_id = device.pk
                return

        request_obj.auth_device_id = device.pk
        if counted_rows is None:
            more_recent = (
                UserDevice.objects
                .filter(user=user, is_active=True, last_login__gt=device.last_login)
                .exclude(pk=device.pk)
                .count()
            )
        else:
            more_recent = sum(
                1 for r in counted_rows
                if r.is_active and r.pk != device.pk and r.last_login is not None
                and (device.last_login is None or r.last_login > device.last_login)
            )
        if at_limit(more_recent):
            if management_request:
                return  # do not refresh last_login, or it would win its slot back
            raise limit_reached()

        if (
            device.last_login is None
            or now - device.last_login >= _DEVICE_TOUCH_INTERVAL
            or device.device_name != user_agent
            or (device.ip_address or None) != ip
        ):
            UserDevice.objects.filter(pk=device.pk).update(
                device_name=user_agent, ip_address=ip, last_login=now,
            )

    @staticmethod
    def _retire_session(user_id, session_id):
        """Record ``session_id`` as ended: its requests get ``device_inactive`` from now on.

        Kept as an inactive UserDevice row (``sid:<session id>``), never listed.
        """
        from .models import UserDevice

        if not session_id:
            return
        retired, created = UserDevice.objects.get_or_create(
            user_id=user_id,
            device_fingerprint=_SESSION_FINGERPRINT_PREFIX + session_id,
            defaults={'session_id': session_id, 'is_active': False, 'device_name': 'Ended session'},
        )
        if not created and (retired.is_active or retired.session_id != session_id):
            UserDevice.objects.filter(pk=retired.pk).update(is_active=False, session_id=session_id)

    def _bind_device_to_session(self, row, session_id):
        """Move an active device row to a new session, retiring the old one."""
        from .models import UserDevice

        with transaction.atomic():
            if row.session_id and row.session_id != session_id:
                self._retire_session(row.user_id, row.session_id)
            UserDevice.objects.filter(pk=row.pk).update(session_id=session_id)
        row.session_id = session_id

    def _reenrol_device(self, row, session_id, user_agent, ip, now):
        """A fresh sign-in on a logged-out device row: enrol it again for the new session."""
        from .models import UserDevice

        with transaction.atomic():
            if row.session_id and row.session_id != session_id:
                self._retire_session(row.user_id, row.session_id)
            UserDevice.objects.filter(pk=row.pk).update(
                is_active=True, session_id=session_id, device_name=user_agent, ip_address=ip, last_login=now,
            )
        row.is_active, row.session_id, row.last_login = True, session_id, now
        return row
