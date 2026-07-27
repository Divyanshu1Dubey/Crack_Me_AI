"""Duplicate detection for the material importer.

Two-stage check:

  1. Exact content-hash match (cheap, catches direct re-imports)
  2. 6-gram shingle match on normalized text (catches minor edits)

The shingle stage uses an **inverted index** (shingle → set of doc hashes),
so per-question similarity is O(matching_docs) rather than O(all_docs).
For an 8,000-question corpus this is dramatically faster than the naive
O(N × M) loop above.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .parser.dataclasses import ParsedQuestion
from .parser.text_utils import clean_text, content_hash


@dataclass
class DuplicateResult:
    content_hash: str
    is_duplicate: bool
    duplicate_of_hash: str = ""
    similarity_score: float = 0.0
    reason: str = ""


# Simple whitespace + lower + remove punctuation normalizer.
_PUNCT_RE = re.compile(r"[^a-z0-9\s]+", re.IGNORECASE)


def _normalize(text: str) -> str:
    if not text:
        return ""
    cleaned = clean_text(text).lower()
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _shingles(text: str, k: int = 6) -> set[str]:
    words = text.split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _jaccard_cardinality(a_size: int, b_size: int, inter: int) -> float:
    if a_size == 0 or b_size == 0:
        return 0.0
    union = a_size + b_size - inter
    return inter / union if union else 0.0


class DuplicateDetector:
    """Two-stage (exact hash + inverted-shingle similarity)."""

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self._seen_hashes: dict[str, str] = {}
        self._seen_shingles: dict[str, set[str]] = {}
        # inverted index: shingle -> set of doc_hashes
        self._index: dict[str, set[str]] = defaultdict(set)

    def prime(self, existing_hashes: Iterable[str], existing_texts: Iterable[Tuple[str, str]]) -> None:
        for h, t in existing_texts:
            if not t:
                continue
            self._seen_hashes[h] = h
            sh = _shingles(t)
            self._seen_shingles[h] = sh
            for s in sh:
                self._index[s].add(h)

    def check(self, q: ParsedQuestion) -> DuplicateResult:
        h = content_hash(q.question_text or "")
        if h in self._seen_hashes:
            return DuplicateResult(content_hash=h, is_duplicate=True,
                                    duplicate_of_hash=h, similarity_score=1.0,
                                    reason="exact content hash match")

        norm = _normalize(q.question_text)
        shingles = _shingles(norm)
        if not shingles:
            return DuplicateResult(content_hash=h, is_duplicate=False)

        # Find candidate docs via inverted index.
        counter: dict[str, int] = defaultdict(int)
        for s in shingles:
            for h2 in self._index.get(s, ()):
                counter[h2] += 1

        best_score = 0.0
        best_hash = ""
        for h2, inter in counter.items():
            other_size = len(self._seen_shingles.get(h2, set()))
            score = _jaccard_cardinality(len(shingles), other_size, inter)
            if score > best_score:
                best_score = score
                best_hash = h2

        if best_score >= self.threshold:
            return DuplicateResult(content_hash=h, is_duplicate=True,
                                    duplicate_of_hash=best_hash,
                                    similarity_score=best_score,
                                    reason=f"shingle similarity {best_score:.2f} ≥ {self.threshold}")

        # Register.
        self._seen_hashes[h] = h
        self._seen_shingles[h] = shingles
        for s in shingles:
            self._index[s].add(h)
        return DuplicateResult(content_hash=h, is_duplicate=False, similarity_score=best_score)

    def check_batch(self, questions: List[ParsedQuestion]) -> List[DuplicateResult]:
        return [self.check(q) for q in questions]


def detect_duplicates(questions: List[ParsedQuestion], existing_texts: List[Tuple[str, str]] | None = None) -> List[DuplicateResult]:
    det = DuplicateDetector()
    if existing_texts:
        det.prime(existing_texts, existing_texts)
    return det.check_batch(questions)
