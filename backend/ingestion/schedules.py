"""django-q Schedule for the ingestion stale-job sweeper.

A worker that dies mid-job (django-q timeout, OOM, deploy restart) leaves
its ImportJob ``processing``; django-q's own re-delivery cannot resume it
with the shipped Q_CLUSTER settings (see
``orchestrator.stale_processing_after``). The recovery pass
``ingestion.tasks.recover_stale_jobs`` marks such jobs crashed and
re-queues the ones that can resume. This module keeps a django-q
``Schedule`` for it, so it runs every ``INGESTION_RECOVERY_SCHEDULE_MINUTES``
(default 10; 0 removes the schedule) on the ``qcluster`` worker with no
Procfile, cron or deploy-script entry.

``ensure_recovery_schedule`` is idempotent. ``ingestion.signals`` calls it
after every ``migrate`` (build.sh / the Procfile release step run migrate
on each deploy); it can also be called by hand from a shell.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

LOG = logging.getLogger("ingestion.schedules")

RECOVERY_SCHEDULE_NAME = "ingestion_recover_stale_jobs"
RECOVERY_TASK = "ingestion.tasks.recover_stale_jobs"
DEFAULT_RECOVERY_MINUTES = 10


def recovery_schedule_minutes() -> int:
    """Minutes between recovery passes (``INGESTION_RECOVERY_SCHEDULE_MINUTES``)."""
    try:
        return max(0, int(getattr(settings, "INGESTION_RECOVERY_SCHEDULE_MINUTES",
                                  DEFAULT_RECOVERY_MINUTES)))
    except (TypeError, ValueError):
        return DEFAULT_RECOVERY_MINUTES


def ensure_recovery_schedule(using: str | None = None):
    """Create or update the recovery Schedule; returns it (None when disabled).

    Re-running it changes nothing unless the schedule was edited or the
    interval setting changed: only ``func`` / type / interval / ``repeats``
    are reset, and ``next_run`` is set only when the row is created.
    """
    from django_q.models import Schedule

    manager = Schedule.objects.db_manager(using) if using else Schedule.objects
    minutes = recovery_schedule_minutes()
    if minutes == 0:
        manager.filter(name=RECOVERY_SCHEDULE_NAME).delete()
        return None

    wanted = {
        "func": RECOVERY_TASK,
        "schedule_type": Schedule.MINUTES,
        "minutes": minutes,
        "repeats": -1,
    }
    schedule = manager.filter(name=RECOVERY_SCHEDULE_NAME).order_by("id").first()
    if schedule is None:
        return manager.create(
            name=RECOVERY_SCHEDULE_NAME,
            next_run=timezone.now() + timedelta(minutes=1),
            **wanted,
        )
    changed = [field for field, value in wanted.items() if getattr(schedule, field) != value]
    for field in changed:
        setattr(schedule, field, wanted[field])
    if changed:
        schedule.save(update_fields=changed)
    # Duplicates (e.g. created by hand) would each run the pass.
    manager.filter(name=RECOVERY_SCHEDULE_NAME).exclude(pk=schedule.pk).delete()
    return schedule


__all__ = [
    "DEFAULT_RECOVERY_MINUTES",
    "RECOVERY_SCHEDULE_NAME",
    "RECOVERY_TASK",
    "ensure_recovery_schedule",
    "recovery_schedule_minutes",
]
