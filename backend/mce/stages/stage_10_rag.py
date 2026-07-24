"""Stage 10 — RAG chunk emitter.

Every structured question emits a set of RAG-ready chunks aligned with
the existing ai_engine.rag_pipeline schema:

    QuestionChunk {
      chunk_id, question_id, chunk_type, body,
      image_refs, asset_refs, pearl_refs, reference_refs,
      source_trace, embedding (None — future embedding worker),
    }

Chunk types per question:
    stem, options, answer, explanation,
    clinical_pearl, high_yield, mnemonic,
    reference, table, image_caption

The output JSONL is the future embedding worker's input. Re-runs are
idempotent (chunks are derived deterministically from Stage 7 output).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_10_rag")


def _chunk_id(question_id: str, chunk_type: str, suffix: str = "") -> str:
    raw = f"{question_id}|{chunk_type}|{suffix}"
    return f"chk_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _make_chunk(question: dict[str, Any], chunk_type: str, body: str,
                *, suffix: str = "", image_refs: Optional[list[str]] = None,
                asset_refs: Optional[list[str]] = None,
                pearl_refs: Optional[list[str]] = None,
                reference_refs: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "chunk_id": _chunk_id(question["id"], chunk_type, suffix),
        "question_id": question["id"],
        "pdf_sha256_short": question.get("source_sha16", ""),
        "page_number": question.get("page_number"),
        "chunk_type": chunk_type,
        "body": body,
        "image_refs": list(image_refs or []),
        "asset_refs": list(asset_refs or []),
        "pearl_refs": list(pearl_refs or []),
        "reference_refs": list(reference_refs or []),
        "embedding_model": None,
        "embedding": None,
        "indexed_at": None,
        "source_trace": question.get("source_trace"),
    }


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_10_rag")
    out_dir: Path = ctx.stage_dir("10_rag")
    stage7_index = ctx.stage_dir("07_structured") / "_index.json"

    if not stage7_index.exists():
        res.errors.append("Stage 7 index missing — run Stage 7 first")
        return res
    try:
        s7 = json.loads(stage7_index.read_text(encoding="utf-8"))
        questions = s7.get("questions", [])
    except Exception as e:
        res.errors.append(f"stage 7 index read failed: {e}")
        return res

    if pages:
        pages_set = set(pages)
        questions = [q for q in questions if int(q["page_number"]) in pages_set]

    chunks_path = out_dir / "chunks.jsonl"
    if force or not chunks_path.exists():
        chunks_path.write_text("", encoding="utf-8")
    chunks_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_count = 0
    type_hist: dict[str, int] = {}
    with chunks_path.open("a", encoding="utf-8") as f:
        for q in questions:
            qid = q["id"]
            chunks: list[dict[str, Any]] = []

            # Stem.
            if q.get("stem"):
                chunks.append(_make_chunk(q, "stem", q["stem"]))
            # Options.
            opts_text = " ".join(
                f"{o.get('label', '?')}. {o.get('text', '')}" for o in q.get("options", [])
            ).strip()
            if opts_text:
                chunks.append(_make_chunk(q, "options", opts_text))
            # Answer.
            ans = q.get("answer_labels") or []
            if ans:
                chunks.append(_make_chunk(q, "answer", ", ".join(ans)))
            # Explanation.
            if q.get("explanation"):
                chunks.append(_make_chunk(q, "explanation", q["explanation"]))
            # Clinical pearl.
            if q.get("clinical_pearl"):
                chunks.append(_make_chunk(q, "clinical_pearl", q["clinical_pearl"]))
            # High-yield.
            for hyp in q.get("high_yield_points", []):
                if hyp:
                    chunks.append(_make_chunk(q, "high_yield", hyp))
            # Mnemonic.
            if q.get("mnemonic"):
                chunks.append(_make_chunk(q, "mnemonic", q["mnemonic"]))
            # References.
            for r in q.get("references", []):
                ref_text = r.get("citation_text") or r.get("locator") or ""
                if ref_text:
                    chunks.append(_make_chunk(q, "reference", ref_text,
                                              reference_refs=[r.get("id", "")]))
            # Tables (asset IDs).
            for aid in q.get("asset_ids", []):
                chunks.append(_make_chunk(q, "table", aid, suffix=aid,
                                          asset_refs=[aid]))
            # Image captions.
            for iid in q.get("image_ids", []):
                cap = ""
                for c in q.get("captions", []):
                    if iid in c:
                        cap = c
                        break
                chunks.append(_make_chunk(q, "image_caption", cap or iid,
                                          suffix=iid, image_refs=[iid]))

            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                chunk_count += 1
                type_hist[c["chunk_type"]] = type_hist.get(c["chunk_type"], 0) + 1

    (out_dir / "_index.json").write_text(json.dumps({
        "pdf_filename": ctx.pdf_filename,
        "pdf_sha256_short": ctx.pdf_sha256_short,
        "chunk_count": chunk_count,
        "type_histogram": type_hist,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    res.metrics = {
        "chunks": chunk_count,
        "type_histogram": type_hist,
    }
    LOG.info("stage_10_rag: %d chunks (types: %s)", chunk_count, type_hist)
    return res


__all__ = ["run"]
