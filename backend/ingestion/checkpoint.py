"""Checkpoint repository — the resume ledger for ImportJob.

Two responsibilities:

  1. Persist a row in ``ImportCheckpoint`` at every stage boundary
     so the orchestrator can recover after a crash.
  2. Read the latest row for a job so the orchestrator can resume
     from the correct stage + page.

This module never touches MCE artefacts; it only writes metadata.
"""
from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Optional

from django.db import transaction

from .exceptions import CheckpointMismatchError
from .models import ImportCheckpoint, ImportJob, MaterialAsset

LOG = logging.getLogger("ingestion.checkpoint")


def _make_token() -> str:
    """Random 32-char hex token. Used to detect stale writers."""
    return secrets.token_hex(16)


def save_checkpoint(
    *,
    job: ImportJob,
    material: MaterialAsset,
    last_completed_stage: str,
    last_processed_page: int,
    current_page: int,
    artifact_root: Path,
    artifact_sha16: str,
    checkpoint_data: Optional[dict] = None,
) -> ImportCheckpoint:
    """Upsert a checkpoint row for ``job``.

    Called by the orchestrator at every stage boundary. Idempotent
    on (job); we update the existing row's stage/page fields rather
    than inserting a fresh row, so the dashboard can read the latest
    state in a single query.
    """
    with transaction.atomic():
        ck, _ = ImportCheckpoint.objects.update_or_create(
            job=job,
            defaults={
                "material_asset": material,
                "last_completed_stage": last_completed_stage,
                "last_processed_page": last_processed_page,
                "current_page": current_page,
                "token": _make_token(),
                "artifact_root": str(artifact_root),
                "artifact_sha16": artifact_sha16,
                "checkpoint_data": checkpoint_data or {},
            },
        )
        # Bump version so the dashboard sees a fresh checkpoint.
        ck.version = (ck.version or 0) + 1
        ck.save(update_fields=["version"])
        return ck


def latest_checkpoint(job: ImportJob) -> Optional[ImportCheckpoint]:
    """Return the most recent checkpoint for ``job`` (or None)."""
    return (
        ImportCheckpoint.objects
        .filter(job=job)
        .order_by("-created_at")
        .first()
    )


def assert_token(ck: ImportCheckpoint, expected: str) -> None:
    """Raise CheckpointMismatchError if the token does not match.

    Defensive guard against a parallel retried worker writing over a
    fresh checkpoint before the current one finished its update.
    """
    if ck.token and expected and ck.token != expected:
        raise CheckpointMismatchError(
            f"Checkpoint token mismatch for job {ck.job_id}: "
            "another writer is active; refresh and retry."
        )


__all__ = ["save_checkpoint", "latest_checkpoint", "assert_token"]
