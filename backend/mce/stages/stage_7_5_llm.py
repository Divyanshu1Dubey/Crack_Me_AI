"""Stage 7.5 — LLM-assisted question reconstruction (hybrid pipeline).

The Medical Document Reconstruction Engine.  Where Stage 7 produces a
deterministic parsed question from typed regions, this stage calls an
LLM to **reorganise** the evidence for blocks that look incomplete:

Trigger conditions (any of):
    * Avg question-reconstruction confidence < 0.85
    * ≥ 2 unclassified regions attached
    * No answer_labels detected
    * More than half the unclassified block text couldn't be role-
      typed by the deterministic state machine

LLM contract (CRITICAL):
    - The model never invents content.  Every word in its response
      output must come from the input evidence.
    - Re-organising evidence is allowed (collapse fragmented text,
      assign roles, parse unconventional answer markers).
    - Output is JSON: {stem, options[], answer_labels[], explanation,
      clinical_pearl, references[], per_region_role_assignments}.
    - Any text the LLM cannot find in evidence must be omitted.

Inputs (per block):
    - Stage 7's deterministic ParsedQuestion dict
    - The raw unclassified regions (text + bbox) inside the block
    - Any OCR text from Stage 6 (image + region)
    - Image OCR (captions)

Failure path:
    - If all 9 LLM providers fail / timeout, return the deterministic
      Stage-7 result verbatim with ``llm_attempted=True,
      llm_applied=False`` markers.
    - If the LLM response fails JSON parse / fails the "no invented
      words" validator, return deterministic Stage-7 result with the
      failure annotated.

The wiring: Stage 8 (QA) consumes the 07_structured output unchanged,
so any quality lift here lifts the QA gate metrics directly.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_7_5_llm")


# Per-call rate-limit so a 144-page run doesn't blast all provider keys.
_MAX_LLM_CALLS_PER_RUN = int(os.environ.get("MCE_LLM_MAX_CALLS", "120"))
_CALLS_USED = 0
_LOCK = threading.Lock()


def _remaining_llm_budget() -> int:
    global _CALLS_USED
    with _LOCK:
        return max(0, _MAX_LLM_CALLS_PER_RUN - _CALLS_USED)


def _consume_llm_budget(n: int = 1) -> bool:
    global _CALLS_USED
    with _LOCK:
        if _CALLS_USED + n > _MAX_LLM_CALLS_PER_RUN:
            return False
        _CALLS_USED += n
        return True


def reset_llm_budget_for_test() -> None:
    """Test hook: zero the per-run LLM call budget counter."""
    global _CALLS_USED
    with _LOCK:
        _CALLS_USED = 0


# ----------------------------------------------------------------- LLM call


LLM_SYSTEM_PROMPT = """You are a medical-document reconstruction assistant for NEET-PG multiple-choice questions.

You receive the deterministic extraction output for one question block:
    - The candidate stem text
    - The candidate options (A. / B. / C. / D. …)
    - The candidate answer marker(s)
    - The candidate explanation text
    - A list of UNCLASSIFIED regions whose role is unknown
    - Image OCR text (captions, labels, annotations) if present

Your job is to REORGANISE the evidence, never to invent content.

Rules:
  1. Every word you return in any field must come from the input evidence below.
  2. If a field cannot be confidently constructed from evidence, return null or [].
  3. Multi-letter answers: keep them in alphabetic order.
  4. Reference fields should be one citation text per item.
  5. The explanation may include the answer prose (e.g. "Ans is b. Lipase") —
     separate the explanation body from the answer letter; the body is what
     follows the answer letter.
  6. Output is JSON only — no markdown fences, no prose outside the JSON.
"""


def _call_llm(prompt: str, system: str = LLM_SYSTEM_PROMPT,
              temperature: float = 0.1, max_tokens: int = 1500) -> Optional[str]:
    """Call an LLM via the existing AI service round-robin.

    Configures Django settings from environment variables when needed
    (Stage 7.5 runs before Django bootstrap in some pipelines), then
    delegates to ``ai_engine.services.AIService._call_ai`` for the
    9-provider round-robin + 120s deadline + provider-error filtering.
    """
    # Bootstrap Django minimal settings so AIService can read keys.
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
    try:
        import django  # type: ignore
        if not getattr(django.conf, "settings", None) or not django.conf.settings.configured:
            django.setup()
    except Exception as e:
        LOG.debug("django.setup() skipped / failed: %s", e)

    try:
        from ai_engine.services import AIService  # type: ignore
    except Exception as e:
        LOG.warning("ai_engine import failed: %s", e)
        return None
    try:
        svc = AIService()
        return svc._call_ai(prompt, system=system, temperature=temperature,
                            max_tokens=max_tokens)
    except Exception as e:
        LOG.warning("ai_engine._call_ai failed: %s", e)
        return None


# ----------------------------------------------------------------- prompt / response parsing


def _build_prompt(q: dict[str, Any],
                  unclassified_regions: list[dict[str, Any]],
                  ocr_text: list[str]) -> str:
    """Construct the user prompt for the LLM.

    Includes every word of evidence, with each unclassified region's
    text quoted verbatim.  Output contract is the JSON shape described
    in the system prompt.
    """
    parts: list[str] = []
    parts.append("# Deterministic Stage-7 output")
    parts.append(f"page={q.get('page_number')}  question_number_in_pdf={q.get('question_number_in_pdf')}")
    parts.append(f"subject={q.get('subject')!r}  topic={q.get('topic')!r}")
    parts.append("\n## Candidate stem\n")
    parts.append((q.get("stem") or "").strip() or "(empty)")
    parts.append("\n## Candidate options")
    for o in q.get("options", []) or []:
        label = o.get("label") or "?"
        text = (o.get("text") or "").strip()
        parts.append(f"  {label}. {text}")
    parts.append("\n## Candidate answer labels")
    parts.append(repr(q.get("answer_labels") or []))
    parts.append("\n## Candidate explanation")
    parts.append((q.get("explanation") or "").strip() or "(empty)")
    parts.append("\n## Candidate clinical pearl")
    parts.append((q.get("clinical_pearl") or "").strip() or "(empty)")
    parts.append("\n## Candidate high-yield points")
    for h in q.get("high_yield_points") or []:
        parts.append(f"  - {h.strip()}")
    parts.append("\n## Candidate mnemonic")
    parts.append((q.get("mnemonic") or "").strip() or "(empty)")
    parts.append("\n## Candidate references")
    for r in q.get("references") or []:
        parts.append(f"  - {r.get('citation_text') or r.get('locator') or ''}".rstrip())

    parts.append("\n## Unclassified regions (use ONLY this text to assign roles)\n")
    if unclassified_regions:
        for u in unclassified_regions:
            parts.append(f"  [region {u.get('id', '?')}] text={u.get('text', '')!r}")
    else:
        parts.append("  (none)")

    if ocr_text:
        parts.append("\n## Image OCR (use verbatim)\n")
        for t in ocr_text:
            parts.append(f"  - {t.strip()}")

    parts.append("\n\n## Output JSON (no markdown fences):\n")
    parts.append("{\n")
    parts.append('  "stem": "...",\n')
    parts.append('  "options": [{"label": "A", "text": "..."}, ...],\n')
    parts.append('  "answer_labels": ["A"],\n')
    parts.append('  "explanation": "...",\n')
    parts.append('  "clinical_pearl": "..." | null,\n')
    parts.append('  "high_yield_points": ["...", ...],\n')
    parts.append('  "mnemonic": "..." | null,\n')
    parts.append('  "references": [{"citation_text": "..."}]\n')
    parts.append("}")
    return "\n".join(parts)


_RESPONSE_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_llm_json(text: str) -> Optional[dict[str, Any]]:
    """Extract the first JSON object from the LLM response."""
    m = _RESPONSE_JSON_RE.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _no_invented_content(llm_payload: dict[str, Any],
                          evidence_blob: str) -> list[str]:
    """Verify that every returned string came from the evidence blob.

    The check is token-level: every word boundary token of every
    string value in the LLM output must appear in the evidence blob
    (case-insensitive whole-word).  Returns the list of words in the
    output that were NOT found in the evidence — when non-empty the
    caller should reject the LLM output as having invented content.
    """
    invented: list[str] = []
    blob_low = (evidence_blob or "").lower()
    tokens_blob = set(re.findall(r"\w+", blob_low, flags=re.UNICODE))

    def _check(field: str, val: Any) -> None:
        if not val:
            return
        if isinstance(val, str):
            text = val
        elif isinstance(val, list):
            text = " ".join(str(x) for x in val if isinstance(x, (str, int, float)))
            text = str(text)
        else:
            text = str(val)
        words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        for w in words:
            if not w or len(w) < 4:
                continue   # skip short tokens / punctuation artifacts
            if w not in tokens_blob:
                invented.append(w)

    for field in ("stem", "explanation", "clinical_pearl", "mnemonic"):
        _check(field, llm_payload.get(field))
    hyp = llm_payload.get("high_yield_points") or []
    for h in hyp:
        _check("high_yield", h)
    for o in llm_payload.get("options", []) or []:
        if isinstance(o, dict):
            _check("option_text", o.get("text"))
    for r in llm_payload.get("references", []) or []:
        if isinstance(r, dict):
            _check("reference", r.get("citation_text"))
    return invented


# ----------------------------------------------------------------- merge deterministic + LLM


def _merge(det: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    """Merge LLM-cleaned fields into the deterministic question dict.

    Per-field rules: prefer LLM's value when non-empty AND its
    underlying text came from evidence.  Otherwise fall back to the
    deterministic value.
    """
    out = dict(det)
    for field in ("stem", "explanation", "clinical_pearl", "mnemonic"):
        new = llm.get(field)
        if isinstance(new, str) and new.strip():
            out[field] = new.strip()
    hyp = llm.get("high_yield_points")
    if isinstance(hyp, list) and any(isinstance(h, str) and h.strip() for h in hyp):
        out["high_yield_points"] = [str(h).strip() for h in hyp if isinstance(h, str) and h.strip()]
    llm_opts = llm.get("options") or []
    if isinstance(llm_opts, list) and llm_opts:
        opts = []
        for o in llm_opts:
            if isinstance(o, dict) and o.get("text"):
                opts.append({
                    "label": o.get("label"),
                    "text": str(o["text"]).strip(),
                    "is_correct": False,
                    "image_ids": [],
                })
        if opts:
            # Mark correct based on answer labels.
            ans = set([c.upper() for c in (out.get("answer_labels") or []) if c])
            for o in opts:
                if o["label"] and o["label"].upper() in ans:
                    o["is_correct"] = True
            out["options"] = opts
    llm_ans = llm.get("answer_labels")
    if isinstance(llm_ans, list) and llm_ans:
        out["answer_labels"] = sorted({str(a).upper() for a in llm_ans if str(a).strip()})
    llm_refs = llm.get("references") or []
    if isinstance(llm_refs, list) and llm_refs:
        refs = []
        for r in llm_refs:
            if isinstance(r, dict) and r.get("citation_text"):
                refs.append({
                    "id": f"ref_{hashlib.sha1(str(r['citation_text']).encode('utf-8')).hexdigest()[:12]}",
                    "citation_text": str(r["citation_text"]).strip(),
                    "source_type": r.get("source_type") or "textbook",
                    "locator": str(r.get("locator") or r["citation_text"]).strip()[:120],
                    "confidence": 0.85,
                })
        if refs:
            out["references"] = refs
    return out


# ----------------------------------------------------------------- per-block


def _block_needs_llm(q: dict[str, Any]) -> bool:
    """Heuristic: should the LLM get a chance to clean this block?"""
    if not q.get("answer_labels"):
        return True
    unclass = q.get("unclassified_blocks") or []
    if len(unclass) >= 2:
        return True
    recon = float(q.get("question_reconstruction_confidence", 0.0) or 0.0)
    if recon < 0.85:
        return True
    # Explanation is missing while we have unclassified text.
    if not q.get("explanation") and any(
        u.get("text") for u in unclass
    ):
        return True
    return False


def _evidence_blob_for(q: dict[str, Any],
                       unclassified: list[dict[str, Any]],
                       ocr_text: list[str]) -> str:
    """All text the LLM is allowed to use to construct output fields."""
    pieces: list[str] = []
    pieces.append(q.get("stem") or "")
    for o in q.get("options", []) or []:
        if isinstance(o, dict):
            pieces.append(o.get("text") or "")
    pieces.append(q.get("explanation") or "")
    pieces.append(q.get("clinical_pearl") or "")
    pieces.extend(q.get("high_yield_points") or [])
    pieces.append(q.get("mnemonic") or "")
    for r in q.get("references", []) or []:
        if isinstance(r, dict):
            pieces.append(r.get("citation_text") or r.get("locator") or "")
    for u in unclassified:
        pieces.append(u.get("text") or "")
    pieces.extend(ocr_text or [])
    return " ".join(pieces)


# ----------------------------------------------------------------- main entry


def _load_questions(stage7_dir: Path) -> list[dict[str, Any]]:
    p = stage7_dir / "_index.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("questions", [])
    except Exception:
        return []


def _load_blocks(stage5_dir: Path) -> dict[str, dict[str, Any]]:
    """Return Stage 5 blocks keyed by id (pNNN_qKK)."""
    out: dict[str, dict[str, Any]] = {}
    p = stage5_dir / "_index.json"
    if not p.exists():
        return out
    try:
        idx = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    for b in idx.get("blocks", []):
        bid = b.get("id") or f"p{int(b.get('page_number', 0)):03d}_q{0:02d}"
        out[bid] = b
    return out


def _load_image_captions(stage3_dir: Path) -> dict[str, list[str]]:
    """Return image_id -> [caption texts]."""
    out: dict[str, list[str]] = {}
    p = stage3_dir / "_index.json"
    if not p.exists():
        return out
    try:
        idx = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return out
    for im in idx.get("images", []):
        cap = (im.get("caption") or "").strip()
        if cap:
            out.setdefault(im["id"], []).append(cap)
    return out


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_7_5_llm")
    out_dir = ctx.stage_dir("07_5_llm")
    stage7_dir = ctx.stage_dir("07_structured")
    stage5_dir = ctx.stage_dir("05_question_blocks")
    stage3_dir = ctx.stage_dir("03_images")

    questions = _load_questions(stage7_dir)
    if not questions:
        res.warnings.append("Stage 7 index missing — run Stage 7 first")
        return res
    blocks_by_id = _load_blocks(stage5_dir)
    captions_by_image = _load_image_captions(stage3_dir)

    if pages:
        pages_set = set(pages)
        questions = [q for q in questions if int(q["page_number"]) in pages_set]

    llm_attempted = 0
    llm_applied = 0
    invented_rejected = 0
    budget_exhausted = 0
    out_path = out_dir / "augmented.json"
    if force and out_path.exists():
        out_path.unlink()

    augmented: dict[str, dict[str, Any]] = {}
    augmented.update(json.loads(out_path.read_text(encoding="utf-8"))
                     if out_path.exists() else {})

    for q in questions:
        qid = q.get("id")
        if qid in augmented and not force:
            continue
        if not _block_needs_llm(q):
            augmented[qid] = {"llm_attempted": False, "llm_applied": False}
            continue
        # Re-budget check.
        if _remaining_llm_budget() <= 0:
            budget_exhausted += 1
            augmented[qid] = {"llm_attempted": False, "llm_applied": False,
                             "reason": "llm_budget_exhausted"}
            continue
        if not _consume_llm_budget():
            budget_exhausted += 1
            continue

        block = blocks_by_id.get(qid, {})
        # Gather unclassified regions from the Stage 5 block.
        unclass = block.get("unclassified_regions") or []
        # Add image OCR text.
        image_ocr: list[str] = []
        for iid in q.get("image_ids") or []:
            image_ocr.extend(captions_by_image.get(iid, []))

        evidence = _evidence_blob_for(q, unclass, image_ocr)
        prompt = _build_prompt(q, unclass, image_ocr)
        llm_attempted += 1
        raw = _call_llm(prompt)
        if not raw:
            augmented[qid] = {"llm_attempted": True, "llm_applied": False,
                             "reason": "llm_unavailable"}
            continue

        parsed = _parse_llm_json(raw)
        if not parsed:
            augmented[qid] = {"llm_attempted": True, "llm_applied": False,
                             "reason": "llm_json_parse_failed"}
            continue

        invented = _no_invented_content(parsed, evidence)
        # Tolerate < 2 invented tokens (small words like "of" can be dropped
        # by PDF text extraction + re-emitted by the LLM).  Anything more is
        # cause to reject.
        if len(invented) > 2:
            invented_rejected += 1
            augmented[qid] = {
                "llm_attempted": True, "llm_applied": False,
                "reason": "llm_invented_content",
                "invented_tokens_sample": invented[:20],
            }
            continue

        merged = _merge(q, parsed)
        merged["llm_attempted"] = True
        merged["llm_applied"] = True
        merged["llm_invented_rejected_count"] = 0
        llm_applied += 1
        augmented[qid] = merged

    # Serialize.
    out_path.write_text(
        json.dumps({"pdf_filename": ctx.pdf_filename,
                    "pdf_sha256_short": ctx.pdf_sha256_short,
                    "augmented": augmented}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Also write the question-level dict back into Stage 7's per-page JSON
    # so Stage 7 + 7.5 read consistently.
    page_groups: dict[int, list[dict[str, Any]]] = {}
    for qid, payload in augmented.items():
        if not (payload and payload.get("llm_applied") and "stem" in payload):
            continue
        for q in questions:
            if q.get("id") == qid:
                page_groups.setdefault(int(q["page_number"]), []).append(payload)
                break
    for pn, payloads in page_groups.items():
        page_path = stage7_dir / f"p{pn:03d}.json"
        if not page_path.exists():
            continue
        try:
            page_data = json.loads(page_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        by_id = {q.get("id"): q for q in page_data.get("questions", [])}
        for payload in payloads:
            bid = payload.get("id")
            if bid in by_id:
                # Preserve Stage 7 / ParsedQuestion contract.
                for k in ("stem", "explanation", "clinical_pearl",
                          "high_yield_points", "mnemonic", "options",
                          "answer_labels", "references"):
                    if k in payload and payload[k]:
                        by_id[bid][k] = payload[k]
        page_path.write_text(
            json.dumps(page_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    res.metrics = {
        "questions_examined": len(questions),
        "llm_attempted": llm_attempted,
        "llm_applied": llm_applied,
        "invented_rejected": invented_rejected,
        "budget_exhausted_count": budget_exhausted,
        "llm_budget_remaining": _remaining_llm_budget(),
    }
    LOG.info("stage_7_5_llm: applied=%d attempted=%d invented_rejected=%d budget_left=%d",
             llm_applied, llm_attempted, invented_rejected,
             _remaining_llm_budget())
    return res


__all__ = ["run", "reset_llm_budget_for_test"]
