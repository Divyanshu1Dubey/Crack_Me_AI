"""
Common base for ingestion connectors.

Contract:
- A connector is responsible for pulling raw text from one whitelisted
  source and producing (text, locator, source_url, attribution, license)
  tuples. It MUST NOT touch the KnowledgeChunk table directly.
- `IngestionService.run_connector()` is the only thing that writes to
  the DB; this lets us deduplicate, license-check, and audit in one
  place.
- A connector MUST refuse to ingest anything that does not match its
  declared source slug.
"""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable

from knowledge_base.models import (
    PROHIBITED_LICENSE_MARKERS, KnowledgeSource, LICENSE_CHOICES,
)

logger = logging.getLogger(__name__)


@dataclass
class RawChunk:
    """A piece of text the connector wants to ingest."""

    text: str
    locator: str = ""
    source_url: str = ""
    subject: str = ""
    topic: str = ""
    subtopic: str = ""
    tags: Optional[list[str]] = None
    title: str = ""
    quality_score: float = 0.7  # default: trusted source


class ConnectorBase(ABC):
    """
    Abstract base. Subclasses implement `fetch()` to yield RawChunk
    instances from their whitelisted source.
    """

    #: Source slug this connector is bound to. MUST match a
    #: KnowledgeSource.slug registered in ontology.loader.
    source_slug: str = ""

    def __init__(self):
        self._source: Optional[KnowledgeSource] = None
        # _prohibited_markers is now read from models.PROHIBITED_LICENSE_MARKERS
        # lazily inside `_get_prohibited_patterns`, so we don't cache it here.

    @property
    def source(self) -> KnowledgeSource:
        if self._source is None:
            try:
                self._source = KnowledgeSource.objects.get(slug=self.source_slug)
            except KnowledgeSource.DoesNotExist as e:
                raise RuntimeError(
                    f"Connector {type(self).__name__} requires source slug "
                    f"'{self.source_slug}' to be registered in KnowledgeSource. "
                    f"Run: python manage.py load_ontology"
                ) from e
            if not self._source.is_active:
                raise RuntimeError(
                    f"Source '{self.source_slug}' is marked inactive. "
                    f"Re-activate in admin before ingesting."
                )
        return self._source

    @abstractmethod
    def fetch(self, **kwargs) -> Iterable[RawChunk]:
        """Yield RawChunk instances. Implemented per source."""

    # ─── Guards ────────────────────────────────────────────

    # Pre-compiled regexes for prohibited markers — word-boundary
    # aware so "park" does not match "parkinson" / "parking" and
    # "kdt" does not match words containing those letters.
    # Markers may contain spaces; we use a custom boundary that also
    # accepts punctuation (`.` for "k.d.", `-` for compound names).
    _PROHIBITED_PATTERNS = None  # built lazily below

    @classmethod
    def _get_prohibited_patterns(cls):
        """Lazily compile word-boundary regexes for each marker."""
        if cls._PROHIBITED_PATTERNS is not None:
            return cls._PROHIBITED_PATTERNS
        from knowledge_base.models import PROHIBITED_LICENSE_MARKERS
        compiled = []
        for marker in PROHIBITED_LICENSE_MARKERS:
            # Escape special regex chars but allow the spaces to be
            # flexible (any whitespace between words).
            escaped = re.escape(marker).replace(r"\ ", r"\s+")
            # Word boundary on the OUTSIDE only — `(?<!\w) ... (?!\w)`
            # so `k.d.` matches "K.D. Tripathi" but not "kid".
            pat = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
            compiled.append((marker, pat))
        cls._PROHIBITED_PATTERNS = compiled
        return compiled

    def _guard_text(self, text: str) -> str:
        """Reject text that contains prohibited markers.

        Defence-in-depth: even if a connector is misconfigured, the
        loader will refuse to ingest chunks that look like they came
        from a copyrighted textbook or competitor platform.

        Uses word-boundary matching so common medical prose that
        happens to contain "park" (e.g. "Park's Preventive Medicine
        textbook summary") is correctly matched, while unrelated
        words like "parkinson", "parking", "parkland" are NOT.
        """
        if not text or len(text.strip()) < 30:
            return ""
        for marker, pat in self._get_prohibited_patterns():
            if pat.search(text):
                logger.warning(
                    f"[{self.source_slug}] REFUSED chunk — contains "
                    f"prohibited marker '{marker}'"
                )
                return ""
        return text

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace, drop control chars."""
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _chunk_text(self, text: str, target: int = 500, overlap: int = 80) -> list[str]:
        """Section-aware chunker. Mirrors ai_engine.document_processor
        semantics so behavior is consistent across both pipelines."""
        if not text:
            return []
        # Split on section boundaries
        blocks = re.split(r"\n{2,}|(?=\n#{1,6}\s)|(?=\n[-*]\s)|(?=\n\|)", text)
        segments = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            words = block.split()
            if len(words) > target:
                sents = re.split(r"(?<=[.!?:;])\s+|\n", block)
                segments.extend(s.strip() for s in sents if s.strip())
            else:
                segments.append(block)
        chunks, current, current_len = [], [], 0
        for seg in segments:
            slen = len(seg.split())
            if current_len + slen > target and current:
                chunks.append(" ".join(current))
                # Keep overlap
                overlap_words, overlap_len = [], 0
                for s in reversed(current):
                    sw = s.split()
                    if overlap_len + len(sw) > overlap:
                        break
                    overlap_words.insert(0, s)
                    overlap_len += len(sw)
                current = overlap_words
                current_len = overlap_len
            current.append(seg)
            current_len += slen
        if current:
            chunks.append(" ".join(current))
        return chunks

    def _make_chunks(self, raw_text: str, locator: str = "",
                     source_url: str = "", subject: str = "",
                     topic: str = "", title: str = "",
                     quality_score: float = 0.7) -> Iterable[RawChunk]:
        raw_text = self._normalize_text(raw_text)
        raw_text = self._guard_text(raw_text)
        if not raw_text:
            return []
        for chunk in self._chunk_text(raw_text):
            chunk = self._guard_text(chunk)
            if not chunk:
                continue
            yield RawChunk(
                text=chunk,
                locator=locator,
                source_url=source_url,
                subject=subject,
                topic=topic,
                title=title,
                quality_score=quality_score,
            )


def license_is_acceptable(source: KnowledgeSource) -> bool:
    """Sanity check that the source license is on the whitelist."""
    allowed = {code for code, _ in LICENSE_CHOICES}
    return source.license in allowed