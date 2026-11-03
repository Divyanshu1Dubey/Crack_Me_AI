"""Signal receivers of the ingestion app.

After every ``migrate`` (which build.sh and the Procfile ``release`` step run
on each deploy) the django-q Schedule of the stale-job sweeper is created or
updated, so the sweeper runs on the ``qcluster`` worker without a Procfile,
cron or deploy-script entry (see ``ingestion.schedules``). Same pattern as
the renewal-reminder schedule in ``accounts.signals``.
"""
from __future__ import annotations

import logging
import sys

from django.db.models.signals import post_migrate
from django.dispatch import receiver

LOG = logging.getLogger("ingestion.signals")


def _running_tests() -> bool:
    argv = sys.argv or []
    return "test" in argv or "test_all" in argv or "pytest" in argv


@receiver(post_migrate, dispatch_uid="ingestion_recovery_schedule")
def recovery_schedule_post_migrate(sender, **kwargs):
    """Once per migrate run (sender = this app), never during test runs."""
    if getattr(sender, "label", "") != "ingestion" or _running_tests():
        return
    try:
        from django.db import connections

        using = kwargs.get("using") or "default"
        if "django_q_schedule" not in connections[using].introspection.table_names():
            return  # django_q not migrated on this database (yet)
        from .schedules import ensure_recovery_schedule

        ensure_recovery_schedule(using=using)
    except Exception as exc:  # noqa: BLE001 -- must never block migrate
        LOG.warning("Ingestion recovery schedule not created (%s)", exc)
