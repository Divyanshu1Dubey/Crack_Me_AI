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
    PROHIBITED_LICENSE_MARKERS, LICENSE_CHOICES,
)

logger = logging.getLogger(__name__)


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
        added = updated = rejected = 0
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
                else:
                    rejected += 1
            self._job.chunks_added = added
            self._job.chunks_updated = updated
            self._job.chunks_rejected = rejected
            self._job.status = "success" if (added or updated) else "partial"
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
        """Write or update one chunk. Returns 'added' | 'updated' | 'rejected'."""
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
            if self.auto_approve_trusted and self.source.license in {
                LICENSE_CHOICES[0][0],  # public domain
                LICENSE_CHOICES[1][0],  # cc_by
                LICENSE_CHOICES[3][0],  # cc_by_sa
                LICENSE_CHOICES[4][0],  # govt_india
                LICENSE_CHOICES[5][0],  # internal
            }
            else KnowledgeChunk.APPROVAL_PENDING
        )

        defaults = {
            "text": text,
            "source_url": raw.source_url or self.source.source_url,
            "locator": raw.locator or "",
            "subject": raw.subject or "",
            "topic": raw.topic or "",
            "subtopic": raw.subtopic or "",
            "tags": raw.tags or [],
            "license": license_code,
            "attribution": attribution,
            "approval_state": approval,
            "approved_at": timezone.now() if approval == KnowledgeChunk.APPROVAL_AUTO else None,
            "quality_score": raw.quality_score,
        }
        chunk, created = KnowledgeChunk.objects.update_or_create(
            source=self.source,
            text_hash=text_hash,
            defaults=defaults,
        )
        if created:
            chunk.version = 1
            chunk.save(update_fields=["version"])
            return "added"
        # Bump version
        chunk.version = (chunk.version or 1) + 1
        chunk.save(update_fields=["version", "updated_at"])
        return "updated"