"""
Internal-notes connector.

Reads the user-authored `.md` files in `Medura_Train/textbooks/` and
`Medura_Train/web_knowledge/`. These are the user's own notes (e.g.
`anatomy_cms_notes.md`, `med_hypertension.md`) — explicitly NOT
copyrighted material.

Will REFUSE to ingest:
- Any file whose name matches a known copyrighted textbook
  (harrison, bailey, roberts, park, ghai, nelson, ...)
- Any file larger than 2 MB (rejects scanned-PDF textbook dumps)
"""

import logging
import re
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings

from .base import ConnectorBase, RawChunk

logger = logging.getLogger(__name__)


PROTECTED_TEXTBOOK_TOKENS = [
    "harrison", "bailey", "love", "robbins", "park", "ghai",
    "nelson", "ganong", "guyton", "kdt", "tripathi", "katzung",
    "harper", "goodman", "gilman", "williams", "davidson",
    "oxford handbook", "cmdt", "hutchison",
]

SUBJECT_KEYWORDS = {
    "anatomy": ["anatomy"],
    "physiology": ["physiology"],
    "biochemistry": ["biochemistry"],
    "pathology": ["pathology"],
    "pharmacology": ["pharmacology"],
    "microbiology": ["microbiology"],
    "forensic_medicine": ["forensic", "fmed"],
    "psm": ["psm", "parks", "preventive", "social medicine"],
    "ent": ["ent", "otolaryng"],
    "ophthalmology": ["ophthalmology", "eye"],
    "medicine": ["med_", "medicine", "harrisons", "cms_notes"],
    "surgery": ["surgery"],
    "orthopaedics": ["ortho"],
    "paediatrics": ["pediatr", "paediatr", "ghai"],
    "obg": ["obg", "obstet", "gynecol"],
    "anaesthesia": ["anesthesia", "anaesthesia"],
    "dermatology": ["dermatology", "skin"],
    "psychiatry": ["psychiatry"],
    "radiology": ["radiology"],
}


class InternalNotesConnector(ConnectorBase):
    source_slug = "internal-notes"

    def __init__(self, base_dir: Optional[str] = None):
        super().__init__()
        self.base_dir = Path(
            base_dir or str(getattr(settings, "MEDURA_TRAIN_DIR",
                                    settings.BASE_DIR / "Medura_Train"))
        )

    def _detect_subject(self, filename: str) -> str:
        f = filename.lower()
        for subject, tokens in SUBJECT_KEYWORDS.items():
            for tok in tokens:
                if tok in f:
                    return subject
        return ""

    def _looks_like_copyrighted_textbook(self, path: Path) -> bool:
        n = path.name.lower()
        if not n.endswith((".md", ".txt")):
            return True  # reject .pdf outright
        for token in PROTECTED_TEXTBOOK_TOKENS:
            if token in n:
                return True
        # Reject if the content size resembles a textbook dump
        try:
            size = path.stat().st_size
            if size > 2 * 1024 * 1024:  # 2 MB
                logger.info(f"Skipping {path.name} — too large for note")
                return True
        except OSError:
            return True
        return False

    def fetch(self, **kwargs) -> Iterable[RawChunk]:
        roots = [
            self.base_dir / "textbooks",
            self.base_dir / "web_knowledge",
            self.base_dir / "PYQ",
        ]
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.iterdir()):
                if not path.is_file():
                    continue
                if path.name.startswith(".") or path.name.startswith("Copy of"):
                    continue
                if self._looks_like_copyrighted_textbook(path):
                    logger.info(f"[internal-notes] REFUSED {path.name}")
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    logger.warning(f"Failed reading {path}: {e}")
                    continue
                if not text.strip():
                    continue
                subject = self._detect_subject(path.name)
                topic = path.stem.replace("_", " ").replace("-", " ")
                title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else topic

                # PYQ root files (e.g. 2024paper1.txt) get a hint
                if root.name == "PYQ":
                    subject = subject or "psm"
                    topic = path.stem

                # Extract first source url if any (for traceability)
                src_match = re.search(r"https?://\S+", text)
                src_url = src_match.group(0) if src_match else ""

                for chunk in self._make_chunks(
                    raw_text=text,
                    locator=f"{root.name}/{path.name}",
                    source_url=src_url,
                    subject=subject,
                    topic=topic,
                    title=title,
                    quality_score=0.85,
                ):
                    yield chunk
                logger.info(f"[internal-notes] ingested {path.name}")