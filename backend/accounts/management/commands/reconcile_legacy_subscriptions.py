"""Review accounts flagged ``is_subscribed`` that have no Subscription row.

Premium comes from Subscription rows only. Accounts flagged before the
Subscription model existed get the rows their signed Razorpay payments prove
from migration accounts.0026; the rest -- typically users of the removed
unpaid POST /api/auth/subscribe/ endpoint -- keep an inert flag. This command
lists them (DRY RUN unless --apply is given):

    python manage.py reconcile_legacy_subscriptions                            # report only
    python manage.py reconcile_legacy_subscriptions --apply                    # restore rows the payments prove
    python manage.py reconcile_legacy_subscriptions --apply --clear-unproven   # ... and clear unproven flags

RESTORE  a signed payment is on record; --apply creates its Subscription row(s)
         (normally migration 0026 has done this already).
UNPROVEN no payment on record ("unpaid endpoint" when the old endpoint's
         note is present). The account is not premium. Grant a plan in the
         admin panel to any that should keep premium, then clear the rest
         with --apply --clear-unproven (writes the admin audit log).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Report / reconcile accounts flagged is_subscribed without a Subscription row (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run).")
        parser.add_argument(
            "--clear-unproven", action="store_true",
            help="With --apply: clear is_subscribed of accounts without any payment on record.",
        )

    def handle(self, *args, **options):
        from accounts.legacy_subscriptions import reconcile
        from accounts.models import AdminAuditLog, CustomUser, PaymentAttempt, Subscription, TokenTransaction

        apply, clear_unproven = options["apply"], options["clear_unproven"]
        if clear_unproven and not apply:
            raise CommandError("--clear-unproven needs --apply (run without both first to review the list).")

        accounts = reconcile(
            User=CustomUser, Subscription=Subscription, PaymentAttempt=PaymentAttempt,
            TokenTransaction=TokenTransaction, AuditLog=AdminAuditLog,
            restore=apply, clear_unproven=clear_unproven,
        )
        restorable = [a for a in accounts if a.proven]
        unproven = [a for a in accounts if not a.proven]
        for account in restorable:
            plans = ", ".join(
                f"{p.plan} (order {p.order_id}, {p.paid_at:%Y-%m-%d})" for p in account.purchases
            )
            state = "stays premium" if account.premium_after_restore else "period(s) already ended"
            done = f" -> {account.action}" if account.action else ""
            self.stdout.write(f"RESTORE  user={account.user_id} {account.email}: {plans}; {state}{done}")
        for account in unproven:
            why = "no payment on record"
            if account.free_claim_at:
                why += f"; used the unpaid /auth/subscribe/ endpoint on {account.free_claim_at:%Y-%m-%d}"
            done = f" -> {account.action}" if account.action else ""
            self.stdout.write(f"UNPROVEN user={account.user_id} {account.email}: {why}{done}")

        summary = (
            f"{len(accounts)} flagged account(s) without a plan: {len(restorable)} with payments on record, "
            f"{len(unproven)} without."
        )
        if not apply:
            summary += " Dry run: nothing was written (--apply to restore, --apply --clear-unproven to clear)."
        self.stdout.write(self.style.SUCCESS(summary) if not unproven or clear_unproven else summary)
