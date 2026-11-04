"""Per-user layout preferences (Settings > Customise): ``GET`` / ``PATCH /api/auth/preferences/``.

A learner may reorder the sidebar's sections and links, hide links, reorder or hide dashboard
widgets and pick the page the app opens on. Customisation only reorders and hides: a hidden link
stays reachable in the sidebar's "More" group, and every hidden widget can be turned back on in
Settings. The Admin group of the sidebar is not customisable.

Stored in ``CustomUser.ui_preferences``, only what the user changed (``{}`` = the defaults)::

    {
      "sidebar":   {"sections": [<section id>, ...], "items": [<link id>, ...], "hidden": [<link id>, ...]},
      "dashboard": {"order": [<widget id>, ...], "hidden": [<widget id>, ...]},
      "landing_page": "<page id>"
    }

* ``GET`` answers ``{"preferences": {...}}``: the stored value without anything that is no
  longer on the allow-lists (an id dropped in a later release never reaches the client).
* ``PATCH`` replaces each top-level key it names and keeps the others; ``null`` (or an empty
  object) removes a key, so that part goes back to the default. Empty lists are not stored.
  Validation is strict: unknown keys, unknown or repeated ids, wrong types and the free plan's
  upgrade row in ``dashboard.hidden`` answer ``400 invalid_preferences`` (``errors`` names each
  field), a body over ``MAX_BODY_BYTES`` answers ``413 preferences_too_large``; nothing is saved.
  An order list may name only some ids: the client places the ids it does not name after the
  named ones, in their default order.
* Signed-in users only; a user reads and writes only their own row (there is no user
  parameter). Saves are limited to 60 a minute per account (reads are not counted).

The tuples below are the only accepted ids. ``frontend/src/lib/preferences.ts`` holds the same
lists in the same order and ``frontend/tests/unit/preferences.test.ts`` checks that both agree,
so keep every tuple a plain list of quoted ids (no quotes in comments inside a tuple).
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from crack_cms.throttling import UserRateThrottle

logger = logging.getLogger(__name__)
User = get_user_model()

# Sidebar sections, in their default order.
SIDEBAR_SECTION_IDS = (
    'study', 'ai-tools', 'resources', 'account',
)
# Sidebar links (Study, AI Tools, Resources, Account), in their default order.
SIDEBAR_ITEM_IDS = (
    'dashboard', 'questions', 'tests', 'flashcards', 'simulator', 'mistake-notebook', 'study-time',
    'ai-tutor', 'generate', 'roadmap',
    'resources', 'textbooks', 'jobs', 'trends', 'upload',
    'analytics', 'leaderboard', 'bookmarks', 'subscription', 'feedback', 'contact', 'quests', 'topic-notes',
)
# Dashboard widgets, in their default order.
DASHBOARD_WIDGET_IDS = (
    'announcements', 'welcome', 'upgrade', 'stats', 'toolkit', 'today', 'calendar',
    'focus-subjects', 'momentum', 'mastery', 'streak',
)
# The upgrade row of the free plan: it may be moved, never hidden.
DASHBOARD_ALWAYS_SHOWN_IDS = (
    'upgrade',
)
# Pages the app may open on (a subset of the sidebar links).
LANDING_PAGE_IDS = (
    'dashboard', 'questions', 'tests', 'flashcards', 'simulator', 'mistake-notebook',
    'ai-tutor', 'roadmap', 'analytics', 'bookmarks',
)

PREFERENCE_KEYS = ('sidebar', 'dashboard', 'landing_page')
# The id lists of each object-valued preference and the ids each one accepts.
_ID_LISTS = {
    'sidebar': {'sections': SIDEBAR_SECTION_IDS, 'items': SIDEBAR_ITEM_IDS, 'hidden': SIDEBAR_ITEM_IDS},
    'dashboard': {'order': DASHBOARD_WIDGET_IDS, 'hidden': DASHBOARD_WIDGET_IDS},
}
# Ids a list may never contain, per (preference, list).
_NEVER = {('dashboard', 'hidden'): DASHBOARD_ALWAYS_SHOWN_IDS}

# A complete preference object is a few hundred bytes.
MAX_BODY_BYTES = 4096
# Errors reported per request (a body full of unknown keys gets the first ones).
_MAX_ERRORS = 10
_ECHO_CHARS = 40


class PreferencesError(Exception):
    """A PATCH body that breaks the rules; ``errors`` maps a field path to the reason."""

    def __init__(self, errors: dict[str, str]):
        super().__init__('invalid preferences')
        self.errors = errors


def _echo(value: object) -> str:
    """A short, printable form of a client-supplied id for an error message."""
    return repr(str(value)[:_ECHO_CHARS])


def _id_list_error(value: object, allowed: tuple[str, ...], never: tuple[str, ...]) -> str | None:
    """Why ``value`` is not a list of distinct ``allowed`` ids (``never`` excluded), or None."""
    if not isinstance(value, list):
        return 'Expected a list of ids.'
    if len(value) > len(allowed):
        return f'At most {len(allowed)} ids.'
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return 'Ids must be strings.'
        if item not in allowed:
            return f'Unknown id {_echo(item)}.'
        if item in never:
            return f'{_echo(item)} cannot be hidden.'
        if item in seen:
            return f'Repeated id {_echo(item)}.'
        seen.add(item)
    return None


def validate_patch(data: object) -> dict[str, object]:
    """The PATCH body as ``{key: value}``, ``None`` for a key to remove; raises PreferencesError."""
    if not isinstance(data, dict):
        raise PreferencesError({'non_field_errors': 'Send a JSON object.'})
    errors: dict[str, str] = {}
    for key in data:
        if key not in PREFERENCE_KEYS and len(errors) < _MAX_ERRORS:
            errors[str(key)[:_ECHO_CHARS]] = 'Unknown preference.'

    cleaned: dict[str, object] = {}
    for key in PREFERENCE_KEYS:
        if key not in data:
            continue
        value = data[key]
        if value is None:
            cleaned[key] = None
        elif key == 'landing_page':
            if isinstance(value, str) and value in LANDING_PAGE_IDS:
                cleaned[key] = value
            else:
                errors[key] = 'Unknown page.'
        elif not isinstance(value, dict):
            errors[key] = 'Expected an object.'
        else:
            lists = _ID_LISTS[key]
            for field in value:
                if field not in lists and len(errors) < _MAX_ERRORS:
                    errors[f'{key}.{str(field)[:_ECHO_CHARS]}'] = 'Unknown field.'
            part: dict[str, list[str]] = {}
            for field, allowed in lists.items():
                if field not in value:
                    continue
                error = _id_list_error(value[field], allowed, _NEVER.get((key, field), ()))
                if error:
                    errors[f'{key}.{field}'] = error
                elif value[field]:
                    part[field] = list(value[field])
            # An object with nothing left in it is the default: remove the key.
            cleaned[key] = part or None
    if errors:
        raise PreferencesError(errors)
    return cleaned


def clean_stored(raw: object) -> dict[str, object]:
    """Stored preferences without anything the allow-lists no longer accept (never raises)."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, object] = {}
    for key, lists in _ID_LISTS.items():
        value = raw.get(key)
        if not isinstance(value, dict):
            continue
        part: dict[str, list[str]] = {}
        for field, allowed in lists.items():
            ids = value.get(field)
            if not isinstance(ids, list):
                continue
            never = _NEVER.get((key, field), ())
            kept: list[str] = []
            for item in ids:
                if isinstance(item, str) and item in allowed and item not in never and item not in kept:
                    kept.append(item)
            if kept:
                part[field] = kept
        if part:
            out[key] = part
    landing = raw.get('landing_page')
    if isinstance(landing, str) and landing in LANDING_PAGE_IDS:
        out['landing_page'] = landing
    return out


def merge_preferences(stored: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    """``stored`` with each top-level key of ``patch`` replaced (``None`` removes it)."""
    merged = dict(stored)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return {key: merged[key] for key in PREFERENCE_KEYS if key in merged}


class _PreferencesSaveThrottle(UserRateThrottle):
    """Preference saves per account: 60 a minute. Reads are not counted.

    The Settings page sends one save per burst of changes (it waits for a
    pause), so only a script reaches this. The rate is set here, like
    accounts.views._UsernameChangeThrottle, so the scope needs no
    DEFAULT_THROTTLE_RATES entry.
    """

    scope = 'ui_preferences'
    rate = '60/min'

    def allow_request(self, request, view):
        if request.method != 'PATCH':
            return True
        return super().allow_request(request, view)


class UIPreferencesView(APIView):
    """``GET`` / ``PATCH /api/auth/preferences/``: the signed-in user's own layout preferences."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def get_throttles(self):
        # The default anon / user rates, plus the limit on saves.
        return [*super().get_throttles(), _PreferencesSaveThrottle()]

    def get(self, request):
        # Read from the database: the authenticated user object may predate a save.
        stored = User.objects.filter(pk=request.user.pk).values_list('ui_preferences', flat=True).first()
        return Response({'preferences': clean_stored(stored)})

    def patch(self, request):
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            length = 0
        if length > MAX_BODY_BYTES:
            return Response(
                {'detail': f'Preferences are limited to {MAX_BODY_BYTES} bytes.', 'code': 'preferences_too_large'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            patch = validate_patch(request.data)
        except PreferencesError as exc:
            return Response(
                {'detail': 'These preferences cannot be saved.', 'code': 'invalid_preferences', 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            # Row lock: two saves that name different keys must not drop each other's key.
            user = User.objects.select_for_update().only('pk', 'ui_preferences').get(pk=request.user.pk)
            merged = merge_preferences(clean_stored(user.ui_preferences), patch)
            if merged != user.ui_preferences:
                user.ui_preferences = merged
                user.save(update_fields=['ui_preferences'])
        return Response({'preferences': merged})
