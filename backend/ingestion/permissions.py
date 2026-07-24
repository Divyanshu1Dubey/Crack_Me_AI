"""Permission classes for the ingestion app.

Mirrors `accounts.permissions.IsControlTowerAdmin` so the new admin UI
under `/admin/ingestion/` shares the same access rules as the existing
control-tower admin (role=='admin' OR is_superuser). This is the same
gate used by `importers/neetpg/views.py::ImportJobListView`.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsIngestionAdmin(BasePermission):
    """Allow access to authenticated users with admin or superuser role.

    Identical in semantics to IsControlTowerAdmin; reproduced here to
    keep the ingestion app self-contained and avoid coupling to the
    `accounts` permission module's private attributes.
    """

    message = "Admin role required for production ingestion endpoints."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and (
                getattr(user, "is_admin", False)
                or getattr(user, "is_superuser", False)
            )
        )
