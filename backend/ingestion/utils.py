"""Audit / logger helper for ingestion actions.

Reuses the existing immutable ``accounts.models.AdminAuditLog`` table.
We do NOT extend its `action` enum; instead we use a single
`system_ingestion_event` placeholder and stash the precise verb in
the JSON `metadata` field. This keeps the ingestion app from coupling
to UPSC CMS enum migrations.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

LOG = logging.getLogger("ingestion.audit")


def audit(
    *,
    actor: Optional[Any],
    action: str,
    resource_type: str,
    resource_id: str,
    detail: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist one row to AdminAuditLog.

    Best-effort: if the audit table is unreachable (e.g. migration
    hasn't been applied yet during boot), we swallow the error so the
    calling operation does not fail because of audit.

    Args:
        actor: CustomUser instance or None for system actions.
        action: free-text verb (e.g. ``material.uploaded``,
                ``job.created``, ``job.retried``, ``job.cancelled``).
        resource_type: ``material``, ``job``, ``batch``,
                       ``staged_question``.
        resource_id: PK or sha16 of the resource.
        detail: human-readable detail string.
        metadata: structured JSON-serialisable dict.
    """
    try:
        from accounts.models import AdminAuditLog
    except Exception as e:  # pragma: no cover
        LOG.warning("audit() could not import AdminAuditLog: %s", e)
        return
    try:
        AdminAuditLog.objects.create(
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            action="system_rerun_evaluation",  # reuse existing enum slot; real verb in metadata
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else "",
            detail=detail,
            metadata={"verb": action, **(metadata or {})},
        )
    except Exception as e:  # pragma: no cover
        LOG.warning("audit() write failed: %s", e)
