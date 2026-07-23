"""PDF fingerprinting — stable identity + per-page text fingerprints."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

# Normalise whitespace and common noise before hashing text content.
_TEXT_NORMALISE_RE = re.compile(r"\s+")
_HEADER_FOOTER_HINTS = re.compile(
    r"(page\s*\d+\s*of\s*\d+|www\.[\w\.\-]+|copyright\s*©?\s*\d{4})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Fingerprint:
    pdf_filename: str
    pdf_path: str
    pdf_sha256: str
    pdf_sha256_short: str
    size_bytes: int
    page_count: int
    is_encrypted: bool
    mtime: float
    metadata: dict


def sha256_file(path: Path, chunk: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def sha256_short(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def normalise_text(text: str) -> str:
    """Strip header/footer noise + collapse whitespace."""
    text = _HEADER_FOOTER_HINTS.sub(" ", text)
    text = _TEXT_NORMALISE_RE.sub(" ", text)
    return text.strip()


def page_text_hash(text: str) -> str:
    return hashlib.sha256(normalise_text(text).encode("utf-8")).hexdigest()


def compute_fingerprint(pdf_path: Path, page_count: int, is_encrypted: bool,
                        metadata: Optional[dict] = None) -> Fingerprint:
    st = pdf_path.stat()
    full = sha256_file(pdf_path)
    return Fingerprint(
        pdf_filename=pdf_path.name,
        pdf_path=str(pdf_path),
        pdf_sha256=full,
        pdf_sha256_short=full[:16],
        size_bytes=st.st_size,
        page_count=page_count,
        is_encrypted=is_encrypted,
        mtime=st.st_mtime,
        metadata=metadata or {},
    )


def fingerprint_to_dict(fp: Fingerprint) -> dict:
    return {
        "pdf_filename": fp.pdf_filename,
        "pdf_path": fp.pdf_path,
        "pdf_sha256": fp.pdf_sha256,
        "pdf_sha256_short": fp.pdf_sha256_short,
        "size_bytes": fp.size_bytes,
        "page_count": fp.page_count,
        "is_encrypted": fp.is_encrypted,
        "mtime": fp.mtime,
        "metadata": fp.metadata,
    }


__all__ = [
    "Fingerprint",
    "sha256_file",
    "sha256_short",
    "normalise_text",
    "page_text_hash",
    "compute_fingerprint",
    "fingerprint_to_dict",
]