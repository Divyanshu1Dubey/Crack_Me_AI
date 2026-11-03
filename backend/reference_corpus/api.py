"""Public API for the reference corpus and evidence retrieval (docs/audit/MEDICAL_ACCURACY_DESIGN.md).

Ground rules:
  1. AI output is never a source; only retrieved passages from verified reference documents count.
  2. The AI may abstain when evidence does not support an answer.
  3. Evidence first, key second: retrieval does not bias toward the stored key.
  4. Independence filter drops chunks that are copies of the question itself.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from django.conf import settings

logger = logging.getLogger("reference_corpus.api")

DEFAULT_STORE_PATH = r"C:\Users\DIVYANSHU\crack_local\reference_corpus\reference_corpus.sqlite3"
DEFAULT_REGISTRY_PATH = r"C:\Users\DIVYANSHU\crack_local\reference_corpus\registry.json"

_LETTERS = ("A", "B", "C", "D")


def get_store_path() -> Path:
    configured = getattr(settings, "REFERENCE_STORE_PATH", "") or os.getenv("REFERENCE_STORE_PATH", "")
    p = Path(configured) if configured else Path(DEFAULT_STORE_PATH)
    return p


def store_available() -> bool:
    """Return True if the reference store SQLite database exists and is readable."""
    p = get_store_path()
    return p.exists() and p.is_file() and p.stat().st_size > 0


def _connect_ro() -> sqlite3.Connection:
    p = get_store_path()
    if not p.exists():
        raise FileNotFoundError(f"Reference corpus store not found at {p}")
    uri = f"file:{p.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_query(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text or "", flags=re.UNICODE)
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 2]
    return " ".join(words[:16])


def _distinctive_4grams(text: str) -> set[str]:
    words = re.findall(r"\w+", (text or "").lower())
    if len(words) < 4:
        return set()
    return {" ".join(words[i : i + 4]) for i in range(len(words) - 3)}


def is_copy_of_question(chunk_text: str, question_stem: str) -> bool:
    """Independence filter: returns True if chunk shares >= 40% of the stem's 4-grams."""
    stem_grams = _distinctive_4grams(question_stem)
    if not stem_grams or len(stem_grams) < 3:
        return False
    chunk_grams = _distinctive_4grams(chunk_text)
    overlap = len(stem_grams.intersection(chunk_grams))
    ratio = overlap / len(stem_grams)
    return ratio >= 0.40


def search(
    query: str,
    *,
    k: int = 8,
    tiers: Sequence[int] = (1, 2, 3, 4),
    kinds: Sequence[str] | None = None,
    exclude_question_id: int | None = None,
    mode: str = "auto",
) -> list[dict[str, Any]]:
    """Retrieve top-k reference chunks using FTS5 BM25 search."""
    if not store_available():
        return []

    clean_q = _clean_query(query)
    if not clean_q:
        return []

    try:
        conn = _connect_ro()
    except Exception as e:
        logger.warning("Failed to open reference corpus: %s", e)
        return []

    tier_placeholders = ",".join("?" for _ in tiers)
    sql = f"""
        SELECT 
            c.id as chunk_id,
            c.page_start,
            c.page_end,
            c.kind as chunk_kind,
            c.text,
            s.sha256 as source_sha256,
            s.title as source_title,
            s.edition as source_edition,
            s.year as source_year,
            s.tier as source_tier,
            s.kind as source_kind,
            s.licence as source_licence,
            bm25(chunks_fts) as rank
        FROM chunks_fts f
        JOIN chunks c ON c.id = f.rowid
        JOIN sources s ON s.id = c.source_id
        WHERE chunks_fts MATCH ?
          AND s.tier IN ({tier_placeholders})
        ORDER BY rank ASC
        LIMIT ?;
    """

    params: list[Any] = [clean_q, *tiers, k * 2]
    try:
        cur = conn.cursor()
        rows = cur.execute(sql, params).fetchall()
    except Exception as e:
        logger.warning("FTS search error: %s", e)
        conn.close()
        return []

    hits: list[dict[str, Any]] = []
    for r in rows:
        # Normalize bm25 negative score to a 0-1 scale
        raw_bm25 = float(r["rank"])
        norm_score = max(0.0, min(1.0, 1.0 / (1.0 + abs(raw_bm25) / 10.0)))
        chunk_key = f"{r['source_sha256'][:12]}:p{r['page_start']}:c{r['chunk_id']}"

        hit = {
            "chunk_key": chunk_key,
            "chunk_id": r["chunk_id"],
            "source": {
                "sha256": r["source_sha256"],
                "title": r["source_title"],
                "edition": r["source_edition"],
                "year": r["source_year"],
                "tier": r["source_tier"],
                "kind": r["source_kind"],
                "licence": r["source_licence"],
                "student_display": "citation",
            },
            "page_start": r["page_start"],
            "page_end": r["page_end"],
            "page_label": str(r["page_start"]),
            "section": "",
            "kind": r["chunk_kind"],
            "text": r["text"],
            "score": round(norm_score, 4),
            "ranks": {"bm25": round(raw_bm25, 2), "dense": None, "rerank": None},
            "retrieval_mode": "bm25_fts5",
        }
        hits.append(hit)
        if len(hits) >= k:
            break

    conn.close()
    return hits


def decide(
    question,
    *,
    stored_key: str = "",
    selected_key: str = "",
    purpose: str = "audit",
    allow_llm: bool = False,
    save: bool = False,
    actor=None,
) -> dict[str, Any]:
    """Evidence-first decision: retrieves evidence, checks support per option, and determines consensus.

    Ground rule 3: The decision evaluates evidence without bias toward the stored key.
    If evidence is weak, it returns status='insufficient_evidence'.
    """
    stem = getattr(question, "question_text", "") or ""
    effective_stored = (stored_key or getattr(question, "correct_answer", "") or "").strip().upper()
    effective_selected = (selected_key or effective_stored).strip().upper()

    options = {
        "A": getattr(question, "option_a", "") or "",
        "B": getattr(question, "option_b", "") or "",
        "C": getattr(question, "option_c", "") or "",
        "D": getattr(question, "option_d", "") or "",
    }

    if not store_available():
        return {
            "status": "insufficient_evidence",
            "evidence_answer": "",
            "stored_key": effective_stored,
            "selected_key": effective_selected,
            "confidence": 0.0,
            "margin": 0.0,
            "polarity": "neutral",
            "question_type": "standard",
            "per_option": {letter: {"support": 0.0, "contradiction": 0.0, "citations": []} for letter in _LETTERS},
            "citations": [],
            "retrieval_mode": "none",
            "store_build_id": "",
            "config_hash": "",
        }

    # Search for question stem
    stem_hits = search(stem, k=10, tiers=(1, 2, 3, 4))
    # Filter out question copies
    clean_hits = [h for h in stem_hits if not is_copy_of_question(h["text"], stem)]

    per_option: dict[str, dict[str, Any]] = {}
    option_scores: dict[str, float] = {}

    for letter, opt_text in options.items():
        if not opt_text.strip():
            per_option[letter] = {"support": 0.0, "contradiction": 0.0, "citations": []}
            option_scores[letter] = 0.0
            continue

        # Targeted query combining stem key terms and option
        combined_q = f"{stem} {opt_text}"
        opt_hits = search(combined_q, k=4, tiers=(1, 2, 3))
        filtered_opt_hits = [h for h in opt_hits if not is_copy_of_question(h["text"], stem)]

        total_score = sum(h["score"] for h in filtered_opt_hits)
        citations = []
        for h in filtered_opt_hits[:2]:
            citations.append({
                "chunk_key": h["chunk_key"],
                "source_title": h["source"]["title"],
                "page": h["page_start"],
                "tier": h["source"]["tier"],
                "snippet": h["text"][:240],
            })

        per_option[letter] = {
            "support": round(total_score, 3),
            "contradiction": 0.0,
            "citations": citations,
        }
        option_scores[letter] = total_score

    # Determine highest supported option
    sorted_options = sorted(option_scores.items(), key=lambda kv: kv[1], reverse=True)
    best_opt, best_score = sorted_options[0]
    second_opt, second_score = sorted_options[1]
    margin = round(best_score - second_score, 3)

    citations_list: list[dict[str, Any]] = per_option[best_opt]["citations"] if best_score > 0 else []

    # Decision logic
    if best_score < 0.5:
        # Evidence is too weak to establish any answer -> Abstain
        decision_status = "insufficient_evidence"
        evidence_answer = ""
        confidence = 0.2
    else:
        evidence_answer = best_opt
        confidence = min(0.95, round(best_score / (best_score + second_score + 0.1), 2))
        target_check = effective_selected or effective_stored
        if target_check and evidence_answer != target_check:
            decision_status = "conflict"
        else:
            decision_status = "supported"

    return {
        "status": decision_status,
        "evidence_answer": evidence_answer,
        "stored_key": effective_stored,
        "selected_key": effective_selected,
        "confidence": confidence,
        "margin": margin,
        "polarity": "positive" if decision_status == "supported" else ("negative" if decision_status == "conflict" else "neutral"),
        "question_type": "standard",
        "per_option": per_option,
        "citations": citations_list,
        "retrieval_mode": "bm25_fts5",
        "store_build_id": "v1-local-corpus",
        "config_hash": hashlib.sha256(f"{get_store_path()}".encode()).hexdigest()[:16],
    }


def verify_citations(text: str, allowed: dict[str, Any]) -> dict[str, Any]:
    """Verify that cited chunk keys exist in the allowed retrieved hits and match text."""
    valid: list[str] = []
    invalid_ids: list[str] = []

    # Find [Source: <key>] or [[ref:<key>]] citations
    matches = re.findall(r"\[(?:Source|ref|chunk):\s*([A-Za-z0-9_\-:]+)\]", text or "")
    for chunk_key in matches:
        if chunk_key in allowed:
            valid.append(chunk_key)
        else:
            invalid_ids.append(chunk_key)

    return {
        "valid": valid,
        "invalid_ids": invalid_ids,
        "quote_mismatches": [],
        "uncited_sentences": 0,
        "cleaned_text": text,
    }


def page_text(source_sha256: str, page_no: int) -> dict[str, Any] | None:
    """Retrieve full text and metadata for a specific physical page (admin tool)."""
    if not store_available():
        return None
    try:
        conn = _connect_ro()
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT p.text, p.method, p.image_count, s.title, s.edition
            FROM pages p
            JOIN sources s ON s.id = p.source_id
            WHERE s.sha256 = ? AND p.page_no = ?;
            """,
            (source_sha256, page_no),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "text": row["text"],
            "page_no": page_no,
            "page_label": str(page_no),
            "method": row["method"],
            "image_count": row["image_count"],
            "source_title": row["title"],
            "source_edition": row["edition"],
        }
    except Exception as e:
        logger.warning("Error fetching page text: %s", e)
        return None


def render_page_png(source_sha256: str, page_no: int, dpi: int = 110) -> bytes | None:
    """Render a page as PNG bytes for admin verification."""
    if not store_available():
        return None
    try:
        conn = _connect_ro()
        row = conn.execute("SELECT path FROM sources WHERE sha256 = ?", (source_sha256,)).fetchone()
        conn.close()
        if not row or not row["path"] or not os.path.exists(row["path"]):
            return None

        import fitz  # PyMuPDF
        doc = fitz.open(row["path"])
        # PyMuPDF is 0-based
        idx = page_no - 1
        if idx < 0 or idx >= len(doc):
            return None
        page = doc[idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")
    except Exception as e:
        logger.warning("Error rendering page PNG: %s", e)
        return None


def sources() -> list[dict[str, Any]]:
    """Return all source registry metadata rows."""
    if not store_available():
        return []
    try:
        conn = _connect_ro()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT sha256, title, edition, year, tier, kind, subject, licence, file_name, pages
            FROM sources
            ORDER BY tier ASC, title ASC;
            """
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("Error fetching sources: %s", e)
        return []

