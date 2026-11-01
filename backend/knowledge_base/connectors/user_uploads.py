"""
User-upload connector — gated on rights attestation.

A user-uploaded document is only ingested into the knowledge base if:
1. The user has ticked `rights_attested=True` on the upload
2. An admin has approved the upload (decision == 'approved')

This is the legal gate for crowdsourced content. Without both checks
the upload cannot enter search results.
"""

import logging
import re
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings

from knowledge_base.models import KnowledgeSource, LICENSE_USER_ATTESTED, UserUploadAttestation

from .base import ConnectorBase, RawChunk

logger = logging.getLogger(__name__)

# Filenames that name a copyrighted textbook or a competitor platform as the
# document's subject (matched as whole words of the cleaned filename).
REFUSED_FILENAME_MARKERS = (
    "harrison", "bailey", "love", "robbins", "park", "ghai",
    "nelson", "ganong", "guyton", "kdt", "tripathi", "katzung",
    "marrow", "prepladder", "dams", "prepcms", "gomed",
)


def refused_marker(filename: str) -> Optional[str]:
    """The refused marker a filename contains, or None."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", (filename or "").lower()).strip()
    tokens = set(cleaned.split())
    for marker in REFUSED_FILENAME_MARKERS:
        if marker in tokens:
            return marker
    return None


class UserUploadsConnector(ConnectorBase):
    """Own source (``user-uploads``, licence ``user_attested``): uploads used
    to borrow the internal-notes source and were stored as "CrackLabs
    Internal" content and auto-approved. User-attested chunks always wait for
    an admin (see IngestionService.AUTO_APPROVE_LICENSES)."""

    source_slug = "user-uploads"
    SOURCE_DEFAULTS = {
        "name": "User uploads (rights attested)",
        "description": "Documents uploaded by CrackLabs users who attested they hold the rights; admin-reviewed.",
        "license": LICENSE_USER_ATTESTED,
        "attribution": "Uploaded by a CrackLabs user (rights attested)",
        "citation_template": "{title} — {attribution}",
        "is_active": True,
    }

    @property
    def source(self) -> KnowledgeSource:
        if self._source is None:
            source, _created = KnowledgeSource.objects.get_or_create(
                slug=self.source_slug, defaults=self.SOURCE_DEFAULTS,
            )
            if not source.is_active:
                raise RuntimeError(
                    f"Source '{self.source_slug}' is marked inactive. "
                    f"Re-activate in admin before ingesting."
                )
            self._source = source
        return self._source

    def __init__(self, base_dir: Optional[str] = None):
        super().__init__()
        # base_dir is unused — files come from UserUploadAttestation.file.path.
        # Kept on the instance for API compatibility but never read.
        chosen = (
            base_dir
            or str(getattr(settings, "MEDIA_ROOT", None) or "")
        ) or str(getattr(settings, "BASE_DIR", Path.cwd()) / "media")
        self.base_dir = Path(chosen)

    def fetch(self, **kwargs) -> Iterable[RawChunk]:
        approved = UserUploadAttestation.objects.filter(
            decision="approved",
            rights_attested=True,
        ).select_related("user")

        for upload in approved:
            try:
                path = Path(upload.file.path)
            except (ValueError, NotImplementedError):
                continue
            if not path.exists():
                logger.warning(f"Upload missing on disk: {path}")
                continue

            # Same defence-in-depth as internal connector. We strip the
            # extension + non-alpha so "park" doesn't match "parking" or
            # "parks_psm_cms_notes.md" — we only want to refuse filenames
            # that explicitly reference a copyrighted textbook or
            # competitor platform as the document subject. (The old
            # `continue` sat in the marker loop, so refused files were
            # still ingested.)
            marker = refused_marker(path.name)
            if marker:
                logger.warning(f"REFUSED user upload {path.name} — contains '{marker}'")
                continue

            try:
                if path.suffix.lower() == ".pdf":
                    from ai_engine.document_processor import DocumentProcessor
                    pages = DocumentProcessor().extract_text(str(path))
                    text = "\n\n".join(p["text"] for p in pages if p.get("text"))
                else:
                    text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Failed reading upload {path}: {e}")
                continue

            for chunk in self._make_chunks(
                raw_text=text,
                locator=f"user_uploads/{path.name}",
                source_url="",
                subject="",
                topic=upload.title,
                title=upload.title,
                quality_score=0.65,  # lower default for crowdsourced
            ):
                yield chunk
            logger.info(f"[user-uploads] ingested {path.name} (attested by {upload.user.username})")