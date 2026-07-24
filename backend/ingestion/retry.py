"""Retry planner — decides whether a job is retryable and what config to use.

Retries always create a NEW ``ImportJob`` row with ``retry_of`` pointing
at the original. The new row inherits ``parent_exam`` and ``config``
from the original (with ``force=True`` so cache invalidation runs).

Retries are only allowed for jobs in failed / crashed / cancelled /
completed states. A queued or processing job cannot be retried —
callers must cancel first.
"""
from __future__ import annotations

from .constants import JOB_CANCELLED, JOB_COMPLETED, JOB_CRASHED, JOB_FAILED
from .exceptions import InvalidJobTransitionError
from .models import ImportJob


RETRYABLE_STATES = {JOB_FAILED, JOB_CRASHED, JOB_CANCELLED, JOB_COMPLETED}


def can_retry(job: ImportJob) -> bool:
    """Return True if ``job`` may be retried."""
    return job.status in RETRYABLE_STATES


def plan_retry(original: ImportJob, *, created_by=None) -> ImportJob:
    """Create a fresh retry job. Raises InvalidJobTransitionError if not retryable."""
    if not can_retry(original):
        raise InvalidJobTransitionError(
            f"Job {original.id} is in state {original.status}; not retryable."
        )
    from .orchestrator import create_retry_job
    return create_retry_job(original, created_by=created_by)


__all__ = ["can_retry", "plan_retry", "RETRYABLE_STATES"]
