"""Deduplicator — sha + rapidfuzz + embedding + image-hash.

Designed to be cheap to run on a single batch. The full corpus dedup
(over millions of questions) belongs in a vector DB; this module
provides the per-batch primitives.

Levels (per DEDUPLICATION_PLAN.md):
  L1 — exact sha of normalised text
  L2 — RapidFuzz token_set_ratio ≥ 0.92
  L3 — sentence-transformers cosine ≥ 0.92
  L4 — pHash Hamming ≤ 5

The deduplicator NEVER deletes a question. It only emits a cluster
mapping; the writer phase decides whether to dedup or keep both.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable, Optional

from .models import ParsedQuestion, ImageRecord

LOG = logging.getLogger(__name__)


# Optional deps
try:
    from rapidfuzz import fuzz  # type: ignore
    _HAS_RAPIDFUZZ = True
except Exception:  # pragma: no cover
    fuzz = None  # type: ignore
    _HAS_RAPIDFUZZ = False

try:
    import numpy as np  # type: ignore
    _HAS_NUMPY = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    _HAS_NUMPY = False


# ----------------------------------------------------------------- L1 sha

_NORMALISE_RE = re.compile(r"\s+")
_NOISE_RE = re.compile(
    r"\[(?:image|fig|figure)[^\]]*\]|\b(?:q|question|ans|answer|exp|explanation)\s*[:\-\.]?\s*",
    re.IGNORECASE,
)


def normalise(text: str) -> str:
    text = (text or "").lower()
    text = _NOISE_RE.sub(" ", text)
    text = _NORMALISE_RE.sub(" ", text)
    return text.strip()


def text_sha256(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- L2 fuzzy

def fuzzy_score(a: str, b: str) -> float:
    if _HAS_RAPIDFUZZ:
        return fuzz.token_set_ratio(a, b) / 100.0
    return SequenceMatcher(None, a, b).ratio()


# ----------------------------------------------------------------- L3 embed

def embed(text: str, model) -> Optional[list[float]]:
    """Encode text with a sentence-transformers model.

    The model is injected to avoid importing the heavy dep at module
    load time. Returns None when the model is missing.
    """
    if model is None:
        return None
    try:
        vec = model.encode([normalise(text)], normalize_embeddings=True)
    except Exception as e:  # pragma: no cover
        LOG.warning("Embedding failed: %s", e)
        return None
    if _HAS_NUMPY:
        return vec[0].tolist()
    return list(vec[0])


def cosine(a: list[float], b: list[float]) -> float:
    if not _HAS_NUMPY or not a or not b or len(a) != len(b):
        return 0.0
    va, vb = np.asarray(a), np.asarray(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(np.dot(va, vb) / denom)


# ----------------------------------------------------------------- L4 image

def hamming(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 99
    return sum(1 for x, y in zip(a, b) if x != y)


def image_match(a: ImageRecord, b: ImageRecord, threshold: int = 5) -> bool:
    if a.phash and b.phash and hamming(a.phash, b.phash) <= threshold:
        return True
    if a.sha256 and b.sha256 and a.sha256 == b.sha256:
        return True
    return False


# ----------------------------------------------------------------- cluster

@dataclass
class DedupCluster:
    canonical_text_hash: str
    member_text_hashes: list[str] = field(default_factory=list)
    detection_methods: list[str] = field(default_factory=list)


@dataclass
class DedupReport:
    new_canonical: int = 0
    exact_sha_duplicates: int = 0
    fuzzy_duplicates: int = 0
    embedding_duplicates: int = 0
    image_duplicates: int = 0
    clusters: list[DedupCluster] = field(default_factory=list)


def dedup_batch(
    questions: Iterable[ParsedQuestion],
    images: Iterable[ImageRecord],
    *,
    fuzzy_threshold: float = 0.92,
    image_phash_threshold: int = 5,
) -> DedupReport:
    """Run all 4 levels on a batch; emit a DedupReport.

    The function is intentionally conservative — borderline scores are
    recorded but NOT auto-linked. Human review (or the runner's flag
    queue) takes over.
    """
    report = DedupReport()
    canonical: dict[str, ParsedQuestion] = {}

    qs = list(questions)
    for q in qs:
        h = text_sha256(q.stem or q.stem_raw)
        if h in canonical:
            report.exact_sha_duplicates += 1
            cluster = _find_or_make_cluster(report, h)
            cluster.member_text_hashes.append(h)
            cluster.detection_methods.append("sha")
            continue
        # Fuzzy match against existing canonical stems.
        matched: Optional[str] = None
        for eh, existing in canonical.items():
            score = fuzzy_score(normalise(q.stem or q.stem_raw),
                                normalise(existing.stem or existing.stem_raw))
            if score >= fuzzy_threshold:
                matched = eh
                report.fuzzy_duplicates += 1
                cluster = _find_or_make_cluster(report, eh)
                cluster.member_text_hashes.append(h)
                cluster.detection_methods.append("rapidfuzz")
                break
        if matched is None:
            canonical[h] = q
            report.new_canonical += 1

    # Image-level dedup
    seen: dict[str, ImageRecord] = {}
    for img in images:
        key = img.sha256_short or img.phash
        if not key:
            seen[id(img)] = img
            continue
        matched_key = None
        for k, existing in seen.items():
            if image_match(img, existing, image_phash_threshold):
                matched_key = k
                report.image_duplicates += 1
                break
        if matched_key is None:
            seen[key] = img

    return report


def _find_or_make_cluster(report: DedupReport, canonical_hash: str) -> DedupCluster:
    for c in report.clusters:
        if c.canonical_text_hash == canonical_hash:
            return c
    c = DedupCluster(canonical_text_hash=canonical_hash)
    report.clusters.append(c)
    return c


__all__ = [
    "DedupCluster",
    "DedupReport",
    "normalise",
    "text_sha256",
    "fuzzy_score",
    "embed",
    "cosine",
    "hamming",
    "image_match",
    "dedup_batch",
]