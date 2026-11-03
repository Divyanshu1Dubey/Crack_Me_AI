"""Link local accounts to their Supabase Auth identities (CustomUser.supabase_uid).

Sign-ins are matched by the Supabase user id once it is stored. The first
sign-in links a row by its confirmed email automatically, EXCEPT:

* admin / staff / superuser rows, which are linked automatically only for a
  trusted admin identity (Supabase app_metadata or the env admin allowlist) or
  for the identity the row was created from (its Supabase created_at is not
  later than the row's date_joined, give or take a few minutes);
* rows already linked to another identity.

Those users see "This account must be verified by an administrator" (code
``account_link_required``) until an operator links them here. Every mode is a
DRY RUN unless --apply is given:

    python manage.py link_supabase_identity --all-privileged           # report every unlinked admin/staff row
    python manage.py link_supabase_identity --all-privileged --apply   # link the original identities
    python manage.py link_supabase_identity --email admin@example.com --apply
    python manage.py link_supabase_identity --email admin@example.com --uid <supabase-user-id> --apply
    python manage.py link_supabase_identity --email admin@example.com --uid <id> --replace --apply

Without --uid the id is looked up with the Supabase admin API (SUPABASE_URL
and SUPABASE_SERVICE_ROLE_KEY): exactly one Supabase user must have the email
and it must be confirmed. Every link is logged (logger ``accounts.link_identity``)
and written to the admin audit log. Run ``--all-privileged`` once after
deploying migration accounts.0023 (it adds supabase_uid empty on every row);
review the dry-run report first. The Supabase user id is also shown in the
Supabase dashboard (Authentication -> Users).

SECURITY: ``--all-privileged`` applies the sign-in rule. It links a row only
to the identity the row was created from (``is_original_identity``: Supabase
created_at not later than date_joined, give or take a few minutes). A
Supabase identity created AFTER the account joined, or one with no creation
date, is what a sign-up with an admin's address looks like while "Confirm
email" is off. Such rows are reported as ``CHECK`` and skipped. Confirm the
owner out of band, then link the row with ``--email`` (it prints the same
warning). ``--include-newer-identities`` links them in bulk, only after every
CHECK row has been confirmed.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q

logger = logging.getLogger("accounts.link_identity")


def _supabase_users_by_email() -> dict[str, list[dict]]:
    """Every Supabase Auth user (admin API), grouped by lower-cased email."""
    from accounts.supabase_auth import _is_configured, list_supabase_auth_users

    if not _is_configured():
        raise CommandError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to look Supabase identities up "
            "(or pass --email with --uid)."
        )
    try:
        users = list_supabase_auth_users(strict=True)
    except RuntimeError as exc:
        raise CommandError(f"Could not list Supabase users: {exc}") from None
    index: dict[str, list[dict]] = defaultdict(list)
    for supabase_user in users:
        email = str(supabase_user.get("email") or "").strip().lower()
        if email:
            index[email].append(supabase_user)
    return index


def _pick_identity(email: str, index: dict[str, list[dict]]) -> tuple[str, dict | None, str]:
    """(uid, identity, '') for the one confirmed Supabase user with this email, else ('', None, reason)."""
    from accounts.supabase_rest_auth import _supabase_email_confirmed

    matches = index.get(email, [])
    if not matches:
        return "", None, "no Supabase user has this email"
    if len(matches) > 1:
        return "", None, "several Supabase users have this email (pass --email with --uid)"
    match = matches[0]
    if not _supabase_email_confirmed(match):
        return "", None, f"Supabase user {match.get('id')} has not confirmed this email"
    try:
        return str(uuid.UUID(str(match.get("id") or ""))), match, ""
    except ValueError:
        return "", None, "the Supabase user has no valid id"


def _newer_identity_problem(identity: dict, user) -> str:
    """'' when ``user`` was created from ``identity`` (the sign-in rule), else why it may not be.

    Uses accounts.supabase_rest_auth.is_original_identity, the check the
    sign-in path applies before linking an admin/staff row automatically.
    """
    from accounts.supabase_rest_auth import is_original_identity, supabase_created_at

    if is_original_identity(identity, user):
        return ""
    joined = user.date_joined.isoformat() if user.date_joined else "unknown"
    created = supabase_created_at(identity)
    if created is None:
        return (
            f"Supabase identity {identity.get('id')} has no creation date, so it cannot be told "
            f"apart from a later sign-up with this email (account joined {joined})"
        )
    return f"Supabase identity {identity.get('id')} was created {created.isoformat()} AFTER the account joined {joined}"


def _is_privileged(user) -> bool:
    return user.role == "admin" or user.is_superuser or user.is_staff


def _normalize_uid(raw_uid: str) -> str:
    try:
        return str(uuid.UUID(raw_uid))
    except ValueError:
        raise CommandError(f"{raw_uid!r} is not a Supabase user id (UUID).") from None


class Command(BaseCommand):
    help = (
        "Link local accounts to Supabase Auth user ids (supabase_uid). Dry run unless --apply; "
        "--all-privileged links every unlinked admin/staff row."
    )

    def add_arguments(self, parser):
        target = parser.add_mutually_exclusive_group(required=True)
        target.add_argument("--email", help="Email of one local account to link")
        target.add_argument(
            "--all-privileged",
            action="store_true",
            help="Every active admin/staff/superuser row without a linked identity",
        )
        parser.add_argument(
            "--uid",
            default="",
            help="Supabase user id (with --email; looked up with the service-role key if omitted)",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Replace an existing, different link on this account (with --email)",
        )
        parser.add_argument(
            "--include-newer-identities",
            action="store_true",
            help=(
                "With --all-privileged: also link rows whose Supabase identity was created after the "
                "account joined, or has no creation date (reported as CHECK). Use it only after "
                "confirming every CHECK row's owner."
            ),
        )
        parser.add_argument("--apply", action="store_true", help="Write the links (default: dry run)")

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        if options["all_privileged"]:
            if options["uid"] or options["replace"]:
                raise CommandError("--uid and --replace can only be used with --email.")
            self._link_all_privileged(apply, include_newer=bool(options["include_newer_identities"]))
        else:
            if options["include_newer_identities"]:
                raise CommandError(
                    "--include-newer-identities can only be used with --all-privileged "
                    "(--email links the account you name and warns when its identity is newer)."
                )
            self._link_one(
                (options["email"] or "").strip().lower(),
                (options.get("uid") or "").strip(),
                replace=bool(options["replace"]),
                apply=apply,
            )
        if not apply:
            self.stdout.write("Dry run: nothing was written. Re-run with --apply to link.")

    # ── one account ──────────────────────────────────────────────────────
    def _link_one(self, email, raw_uid, *, replace, apply):
        User = get_user_model()
        if not email:
            raise CommandError("--email is required.")

        rows = list(User.objects.filter(email__iexact=email).order_by("id")[:2])
        if not rows:
            raise CommandError(f"No local account has the email {email}.")
        if len(rows) > 1:
            raise CommandError(f"Several local accounts have the email {email}; link one in Django admin instead.")
        user = rows[0]

        identity = None
        if raw_uid:
            supabase_uid = _normalize_uid(raw_uid)
        else:
            supabase_uid, identity, reason = _pick_identity(email, _supabase_users_by_email())
            if not supabase_uid:
                raise CommandError(f"Not linking {email}: {reason}.")

        if user.supabase_uid == supabase_uid:
            self.stdout.write(f"{user.username} is already linked to {supabase_uid}.")
            return
        other = User.objects.filter(supabase_uid=supabase_uid).exclude(pk=user.pk).first()
        if other is not None:
            raise CommandError(
                f"Supabase user {supabase_uid} is already linked to account id={other.pk} ({other.username})."
            )
        if user.supabase_uid and not replace:
            raise CommandError(
                f"{user.username} is linked to {user.supabase_uid}; pass --replace to link {supabase_uid} instead."
            )
        if identity is not None and _is_privileged(user):
            problem = _newer_identity_problem(identity, user)
            if problem:
                # Naming the account with --email is the operator's confirmation;
                # make sure it is an informed one.
                self.stdout.write(self.style.WARNING(
                    f"CHECK {user.username} (id={user.pk}): {problem}. Someone may have signed up with "
                    f"this address; link it only after confirming that this person owns the account."
                ))
        if not apply:
            self.stdout.write(f"Would link {user.username} (id={user.pk}) to Supabase user {supabase_uid}.")
            return
        if not self._write_link(user, supabase_uid, source="link_supabase_identity --email", identity=identity):
            raise CommandError(f"Supabase user {supabase_uid} was linked to another account meanwhile.")
        self.stdout.write(self.style.SUCCESS(f"Linked {user.username} (id={user.pk}) to Supabase user {supabase_uid}."))

    # ── every unlinked admin / staff row ─────────────────────────────────
    def _link_all_privileged(self, apply, *, include_newer=False):
        User = get_user_model()
        rows = list(
            User.objects
            .filter(Q(supabase_uid__isnull=True) | Q(supabase_uid=""))
            .filter(Q(role="admin") | Q(is_staff=True) | Q(is_superuser=True))
            .order_by("id")
        )
        if not rows:
            self.stdout.write("Every admin/staff account is already linked to a Supabase identity.")
            return

        index = _supabase_users_by_email()
        linked = planned = skipped = to_check = 0
        for user in rows:
            email = (user.email or "").strip().lower()
            label = f"id={user.pk} {user.username} <{email or 'no email'}>"
            reason = ""
            supabase_uid, identity = "", None
            if not user.is_active:
                reason = "blocked account"
            elif not email:
                reason = "no email"
            elif User.objects.filter(email__iexact=email).count() > 1:
                reason = "several local accounts have this email"
            else:
                supabase_uid, identity, reason = _pick_identity(email, index)
                if supabase_uid:
                    other = User.objects.filter(supabase_uid=supabase_uid).exclude(pk=user.pk).first()
                    if other is not None:
                        reason = f"Supabase user {supabase_uid} is already linked to account id={other.pk}"
            if reason:
                skipped += 1
                self.stdout.write(f"  skip  {label}: {reason}")
                continue

            # Same rule as the sign-in path: only the identity the row was
            # created from is linked without an owner check.
            problem = _newer_identity_problem(identity, user)
            if problem and not include_newer:
                skipped += 1
                to_check += 1
                self.stdout.write(self.style.WARNING(
                    f"  CHECK {label}: {problem}. Confirm the owner, then link it with "
                    f"--email {email} --apply (or re-run with --include-newer-identities)."
                ))
                continue

            source = "link_supabase_identity --all-privileged"
            created = (identity or {}).get("created_at") or "unknown"
            joined = user.date_joined.isoformat() if user.date_joined else "unknown"
            detail = f"{supabase_uid} (identity created {created}, account joined {joined})"
            if problem:
                source += " --include-newer-identities"
                detail += f" [CHECK: {problem}; included by --include-newer-identities]"
            if not apply:
                planned += 1
                self.stdout.write(f"  would link {label} -> {detail}")
                continue
            if self._write_link(user, supabase_uid, source=source, identity=identity):
                linked += 1
                self.stdout.write(self.style.SUCCESS(f"  linked {label} -> {detail}"))
            else:
                skipped += 1
                self.stdout.write(f"  skip  {label}: Supabase user {supabase_uid} was linked to another account meanwhile")

        summary = f"{linked} linked, {skipped} skipped" if apply else f"{planned} would be linked, {skipped} skipped"
        if to_check:
            summary += f"; {to_check} of them need an owner check (identity newer than the account)"
        self.stdout.write(f"Admin/staff accounts without a linked identity: {len(rows)} ({summary}).")

    # ── shared ───────────────────────────────────────────────────────────
    @staticmethod
    def _write_link(user, supabase_uid, *, source, identity=None) -> bool:
        """Store the link, log it and write the admin audit log. False if the uid got taken.

        ``identity`` is the Supabase user record when it was looked up (None for
        an explicit --uid); the audit log then records whether it was the
        identity the row was created from.
        """
        User = get_user_model()
        previous = user.supabase_uid or None
        try:
            with transaction.atomic():
                updated = User.objects.filter(pk=user.pk).update(supabase_uid=supabase_uid)
        except IntegrityError:
            return False
        if not updated:
            return False
        user.supabase_uid = supabase_uid
        original = None if identity is None else not _newer_identity_problem(identity, user)
        logger.warning(
            "Linked account id=%s (%s) to Supabase identity %s via %s (previous link: %s; original identity: %s).",
            user.pk, user.username, supabase_uid, source, previous or "none",
            "not checked" if original is None
            else ("yes" if original else "NO, created after the account or undated"),
        )
        from accounts.views import create_admin_audit_log

        create_admin_audit_log(
            actor=None,
            action="user_role_update",
            resource_type="user",
            resource_id=user.pk,
            detail=f"Linked {user.username} to Supabase identity {supabase_uid} (manage.py {source})",
            metadata={
                "supabase_uid": supabase_uid,
                "previous_supabase_uid": previous,
                "source": source,
                "original_identity": original,
                "identity_created_at": (identity or {}).get("created_at") or None,
            },
        )
        return True
