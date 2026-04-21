from rest_framework.permissions import BasePermission


class IsControlTowerAdmin(BasePermission):
    """Allow access to authenticated users with single admin role or superuser."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(
            user
            and user.is_authenticated
            and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False))
        )
