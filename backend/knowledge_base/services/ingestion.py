"""
IngestionService — the ONLY path from a connector to KnowledgeChunk.

Contract:
- Deduplicates via (source, text_hash)
- Verifies license whitelist at the row level (defence in depth)
- Records every run in IngestionJob
- Optional: writes embeddings via the embedding service

This service is wrapped by the management command
`ingest_source` and by the admin upload endpoint.
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone

from knowledge_base.connectors.base import ConnectorBase
from knowledge_base.models import (
    KnowledgeChunk, KnowledgeSource, IngestionJob,
    PROHIBITED_LICENSE_MARKERS,
    LICENSE_CC_BY, LICENSE_CC_BY_SA, LICENSE_GOVT_INDIA, LICENSE_OWN_INTERNAL,
    LICENSE_PUBLIC_DOMAIN,
)

logger = logging.getLogger(__name__)

# Licences whose chunks may be auto-approved: commercial use allowed. By
# name, not by position in LICENSE_CHOICES — index 3 is CC BY-NC-SA
# (non-commercial), which the old positional list auto-approved while CC BY-SA
# went to review. Non-commercial and user-attested content always waits for
# an admin.
AUTO_APPROVE_LICENSES = frozenset({
    LICENSE_PUBLIC_DOMAIN,
    LICENSE_CC_BY,
    LICENSE_CC_BY_SA,
    LICENSE_GOVT_INDIA,
    LICENSE_OWN_INTERNAL,
})

# Fields an ingestion run may refresh on an existing chunk. Approval state,
# approval time and the reviewer's decision belong to the moderators.
_REFRESHABLE_FIELDS = (
    "source_url", "locator", "subject", "topic", "subtopic", "tags",
    "license", "attribution", "quality_score",
)


@dataclass
class IngestionResult:
    job_id: int
    source_slug: str
    chunks_added: int
    chunks_updated: int
    chunks_rejected: int
    status: str
    error: str = ""


class IngestionService:
    """Run a connector, write chunks, record an IngestionJob."""

    def __init__(self, connector: ConnectorBase, triggered_by=None,
                 auto_approve_trusted: bool = True):
        self.connector = connector
        self.triggered_by = triggered_by
        self.auto_approve_trusted = auto_approve_trusted
        self._source: Optional[KnowledgeSource] = None
        self._job: Optional[IngestionJob] = None

    @property
    def source(self) -> KnowledgeSource:
        if self._source is None:
            self._source = self.connector.source
        return self._source

    def run(self, max_chunks: Optional[int] = None, **kwargs) -> IngestionResult:
        started = timezone.now()
        self._job = IngestionJob.objects.create(
            source=self.source,
            connector=type(self.connector).__name__,
            status="running",
            started_at=started,
            triggered_by=self.triggered_by,
        )
        added = updated = rejected = unchanged = 0
        error = ""

        try:
            for raw in self.connector.fetch(**kwargs):
                if max_chunks and (added + updated) >= max_chunks:
                    break
                outcome = self._write_chunk(raw)
                if outcome == "added":
                    added += 1
                elif outcome == "updated":
                    updated += 1
                elif outcome == "unchanged":
                    unchanged += 1
                else:
                    rejected += 1
            self._job.chunks_added = added
            self._job.chunks_updated = updated
            self._job.chunks_rejected = rejected
            # A re-run that finds everything already up to date succeeded.
            self._job.status = "success" if (added or updated or unchanged) else "partial"
            self._job.finished_at = timezone.now()
            self._job.save()

            # Update source cache
            self.source.chunk_count = (
                KnowledgeChunk.objects.filter(source=self.source, is_active=True).count()
            )
            self.source.last_ingested_at = self._job.finished_at
            self.source.last_ingestion_status = self._job.status
            self.source.save(update_fields=[
                "chunk_count", "last_ingested_at",
                "last_ingestion_status", "updated_at",
            ])
        except Exception as e:
            logger.exception("Ingestion failed")
            error = str(e)
            self._job.status = "failed"
            self._job.error_log = error
            self._job.finished_at = timezone.now()
            self._job.save()

        return IngestionResult(
            job_id=self._job.id,
            source_slug=self.source.slug,
            chunks_added=added,
            chunks_updated=updated,
            chunks_rejected=rejected,
            status=self._job.status,
            error=error,
        )

    @transaction.atomic
    def _write_chunk(self, raw) -> str:
        """Write or update one chunk.

        Returns 'added' | 'updated' | 'unchanged' | 'rejected'. An existing
        chunk keeps its approval state (an admin's approve/reject survives
        every re-ingest, e.g. the one build.sh runs on each deploy) and its
        version only moves when a stored field actually changed.
        """
        # Final license guard — word-boundary matching so legitimate
        # medical prose that happens to mention a textbook name (e.g.
        # "Park's Preventive Medicine summary") is correctly refused,
        # while unrelated substrings like "parkinson" / "parking" pass.
        text = (raw.text or "").strip()
        if len(text) < 30:
            return "rejected"
        import re as _re_ingest
        for marker in PROHIBITED_LICENSE_MARKERS:
            escaped = _re_ingest.escape(marker).replace(r"\ ", r"\s+")
            if _re_ingest.search(rf"(?<!\w){escaped}(?!\w)", text, _re_ingest.IGNORECASE):
                logger.warning(f"REFUSED chunk containing '{marker}'")
                return "rejected"

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # Determine license / attribution
        license_code = self.source.license
        attribution = self.source.attribution
        citation_template = self.source.citation_template

        approval = (
            KnowledgeChunk.APPROVAL_AUTO
            if self.auto_approve_trusted and license_code in AUTO_APPROVE_LICENSES
            else KnowledgeChunk.APPROVAL_PENDING
        )

        values = {
            "source_url": raw.source_url or self.source.source_url,
            "locator": raw.locator or "",
            "subject": raw.subject or "",
            "topic": raw.topic or "",
            "subtopic": raw.subtopic or "",
            "tags": raw.tags or [],
            "license": license_code,
            "attribution": attribution,
            "quality_score": raw.quality_score,
        }
        chunk = (
            KnowledgeChunk.objects.select_for_update()
            .filter(source=self.source, text_hash=text_hash)
            .first()
        )
        if chunk is None:
            KnowledgeChunk.objects.create(
                source=self.source,
                text_hash=text_hash,
                text=text,
                approval_state=approval,
                approved_at=timezone.now() if approval == KnowledgeChunk.APPROVAL_AUTO else None,
                version=1,
                **values,
            )
            return "added"

        changed = [name for name in _REFRESHABLE_FIELDS if getattr(chunk, name) != values[name]]
        if not changed:
            return "unchanged"
        for name in changed:
            setattr(chunk, name, values[name])
        chunk.version = (chunk.version or 1) + 1
        chunk.save(update_fields=changed + ["version", "updated_at"])
        return "updated"