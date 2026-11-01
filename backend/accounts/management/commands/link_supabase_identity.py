"""Link a local account to its Supabase Auth identity (CustomUser.supabase_uid).

Sign-ins are matched by the Supabase user id once it is stored. The first
sign-in links a row by its confirmed email automatically, EXCEPT for
admin / staff / superuser rows (unless the identity is a trusted admin: Supabase
app_metadata or the env admin allowlist) and rows already linked to another
identity. Those users see "This account must be verified by an administrator"
(code ``account_link_required``) until an operator runs:

    python manage.py link_supabase_identity --email admin@example.com --uid <supabase-user-id>
    python manage.py link_supabase_identity --email admin@example.com          # look the id up (service-role key)
    python manage.py link_supabase_identity --email admin@example.com --uid <id> --replace   # move an existing link

The Supabase user id is shown in the Supabase dashboard (Authentication -> Users).
"""
from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


def _lookup_supabase_uid(email: str) -> str:
    """The id of the one Supabase user with this CONFIRMED email (admin API)."""
    from accounts.supabase_auth import _is_configured, list_supabase_auth_users

    if not _is_configured():
        raise CommandError("Pass --uid, or set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to look the id up.")
    matches = [
        u for u in list_supabase_auth_users()
        if str(u.get("email") or "").strip().lower() == email
    ]
    if not matches:
        raise CommandError(f"No Supabase user has the email {email}.")
    if len(matches) > 1:
        raise CommandError(f"Several Supabase users have the email {email}; pass --uid.")
    match = matches[0]
    if not match.get("email_confirmed_at"):
        raise CommandError(f"The Supabase user {match.get('id')} has not confirmed {email}; not linking.")
    return str(match.get("id") or "")


class Command(BaseCommand):
    help = "Link a local account to a Supabase Auth user id (supabase_uid)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email of the local account")
        parser.add_argument("--uid", default="", help="Supabase user id (looked up with the service-role key if omitted)")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace an existing, different link on this account",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        email = options["email"].strip().lower()
        if not email:
            raise CommandError("--email is required.")

        rows = list(User.objects.filter(email__iexact=email).order_by("id")[:2])
        if not rows:
            raise CommandError(f"No local account has the email {email}.")
        if len(rows) > 1:
            raise CommandError(f"Several local accounts have the email {email}; link one in Django admin instead.")
        user = rows[0]

        raw_uid = (options.get("uid") or "").strip() or _lookup_supabase_uid(email)
        try:
            supabase_uid = str(uuid.UUID(raw_uid))
        except ValueError:
            raise CommandError(f"{raw_uid!r} is not a Supabase user id (UUID).") from None

        if user.supabase_uid == supabase_uid:
            self.stdout.write(f"{user.username} is already linked to {supabase_uid}.")
            return
        other = User.objects.filter(supabase_uid=supabase_uid).exclude(pk=user.pk).first()
        if other is not None:
            raise CommandError(
                f"Supabase user {supabase_uid} is already linked to account id={other.pk} ({other.username})."
            )
        if user.supabase_uid and not options["replace"]:
            raise CommandError(
                f"{user.username} is linked to {user.supabase_uid}; pass --replace to link {supabase_uid} instead."
            )

        previous = user.supabase_uid
        User.objects.filter(pk=user.pk).update(supabase_uid=supabase_uid)
        from accounts.views import create_admin_audit_log

        create_admin_audit_log(
            actor=None,
            action="user_role_update",
            resource_type="user",
            resource_id=user.pk,
            detail=f"Linked {user.username} to Supabase identity {supabase_uid} (manage.py link_supabase_identity)",
            metadata={"supabase_uid": supabase_uid, "previous_supabase_uid": previous},
        )
        self.stdout.write(self.style.SUCCESS(f"Linked {user.username} (id={user.pk}) to Supabase user {supabase_uid}."))
