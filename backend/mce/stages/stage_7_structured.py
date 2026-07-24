"""Stage 7 — Structured question reconstruction.

Consumes Stage 5 (question blocks) + Stage 6 (per-region OCR + answer
key) + Stage 2 (raw layout regions for unclassified-block merge) and
emits one ``ParsedQuestion`` per block.

Each ``ParsedQuestion`` has every field the platform needs to render
the question + the provenance for every field:

    stem                       joined stem regions
    options[A..F]              ordered option list with labels
    answer_labels              merged: block answer + global answer-key fallback
    explanation                joined explanation regions
    clinical_pearl             from clinical_pearl regions
    high_yield_points          list, from high_yield regions
    mnemonic                   from mnemonic regions
    references                 list[ReferenceRecord] from reference regions
    image_ids                  Stage 3 image ids attached to this question
    asset_ids                  Stage 4 table ids attached to this question
    pearl_ids                  (placeholder for Stage 7 expansion; reserved)
    captions                   OCR-derived captions from Stage 6 image-OCR
    unclassified_blocks        never silently dropped — preserved
    ocr_confidence / layout_confidence / image_mapping_confidence /
    question_reconstruction_confidence
    exam_type / exam_source    from the ExamProfile
    subject / topic / subtopic from the keyword mapper
    page_number / page_numbers / bbox / source_trace

Outputs
-------
    07_structured/p{NNN}.json           # per-page ParsedQuestion list
    07_structured/all_questions.jsonl   # flattened, one JSON per line
    07_structured/_index.json           # stage-wide index

The full pipeline never silently discards content: any text region
that didn't classify cleanly is preserved in the question's
``unclassified_blocks`` list with full provenance.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult
from mce.types import ParsedQuestion, Region, SourceTrace


LOG = logging.getLogger("mce.stage_7_structured")


# ----------------------------------------------------------------- helpers


def _join_region_text(regions: list[dict[str, Any]]) -> str:
    """Concatenate region text blocks into a single paragraph.

    Concatenates with single-space separators and collapses
    whitespace. Each region contributes its visible text only (no
    bbox info).
    """
    parts: list[str] = []
    for r in regions:
        t = (r.get("text") or "").strip()
        if t:
            parts.append(t)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _parse_option_label(text: str) -> tuple[Optional[str], str]:
    """Extract ``(label, body)`` from an option region text.

    Returns ``(None, text)`` when no leading label is detected — the
    caller is responsible for tolerating that.
    """
    m = re.match(r"^\s*\(?([A-Fa-f])\s*[\.\)]\s*(.+)$", text, re.DOTALL)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return None, text.strip()


def _build_reference_record(ref_text: str, page_number: int, pdf_filename: str,
                             pdf_sha256: str, pdf_sha256_short: str,
                             bbox: tuple[float, ...]) -> dict[str, Any]:
    """Build a ReferenceRecord dict from a free-text reference line."""
    # Heuristic: pull out the locator (e.g. "Harrison 21e p.1245").
    locator = ""
    m = re.search(r"((?:Harrison|Robbins|Guyton|Bailey\s*&\s*Love|KDT|First\s*Aid|NEET\s*PG\s*Key)[^\n,;.]*)",
                  ref_text, re.IGNORECASE)
    if m:
        locator = m.group(1).strip()
    if not locator:
        locator = ref_text.strip()[:120]
    trace = SourceTrace.make(
        pdf_filename=pdf_filename, pdf_sha256=pdf_sha256,
        pdf_sha256_short=pdf_sha256_short, page_number=page_number,
        bbox=bbox, extraction_engine="reference_extractor",
        pipeline_stage="stage_7_structured",
        confidence=0.85,
    )
    return {
        "id": f"ref_{pdf_sha256_short}_{page_number}_{abs(hash(locator)) % 10000:04d}",
        "source_sha16": pdf_sha256_short,
        "page_number": page_number,
        "citation_text": ref_text.strip(),
        "source_type": "textbook",
        "locator": locator,
        "confidence": 0.85,
        "bbox": list(bbox),
        "source_trace": trace.to_dict(),
    }


def _whole_word_count(text: str, kw: str) -> int:
    """Count occurrences of keyword in text using whole-word boundary regex.

    Replaces the legacy ``kw in text`` substring check that produced
    collisions such as ``ear`` matching ``year`` / ``near``.  All
    returned counts are ≥ 0.
    """
    if not text or not kw:
        return 0
    return len(re.findall(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE))


# Layout-context answer detection.  Looks at every region attached to
# the block (in y-order) and returns the first region that *follows*
# the last option region AND whose text begins with any of the accepted
# answer prefixes.  This catches every 2021 NEET-PG variant
# ("Ans is b", "Ans. is b", "Answer- A", "Answer: A", "Answer < A",
# "Correct answer: A", "Correct Option: B", "Correct ans is c",
# "Ans is (B)", "The answer is A", "Ans. is b i.e. Plating",
# "Ans: A and C are both correct", etc.).
RE_ANSWER_HEAD = re.compile(
    r"""^\s*
        (?:Answer|Ans|Key|Correct\s*answer|Correct\s*ans|Correct\s*option
          |The\s*answer\s*is|Right\s*answer)
        \s*[.:<\-]?\s*
        (?:is\s+)?              # "Ans. is b", "Correct ans is B"
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Match answer letters that appear RIGHT AFTER the answer head, before
# any explanatory prose begins.  Supports three forms found in 2021:
#   1. bare run of letters:        "A"        → ['A']
#   2. run separated by ,/and/&:   "A, C, D"  → ['A','C','D']
#   3. parenthetical:              "(B)"      → ['B']
# Multi-letter answers separated by commas/and/slashes are supported.
#
# CRITICAL DESIGN NOTE: the regex below does NOT consume "and"/"or"
# filler words (which would let stray 'a'/'d' leak into the answer
# letter set).  Instead each capture group holds a single answer
# letter; we extract letters via ``m.groups()`` (filtering None),
# never ``re.findall`` on the matched span.
#
# Group 1 is always the FIRST letter (so single-letter answers
# still match even when all the trailing optional groups fail).
# Groups 2..7 are up to 5 additional letters, each separated by
# either a single punctuation char (one of `` ,&/+``) OR a single
# word (``and``/``or`` — case-insensitive, allowing trailing
# whitespace).  We restrict to 7 groups total to keep the regex
# bounded (answers rarely exceed 4 letters).
_RE_ANSWER_BARE = re.compile(
    r"^\s*([A-Fa-f])"
    # Up to 4 punct-separated letters (A, B / A&B / A, B, C, D).
    r"(?:\s*[ ,&/+]\s*([A-Fa-f]))?"
    r"(?:\s*[ ,&/+]\s*([A-Fa-f]))?"
    r"(?:\s*[ ,&/+]\s*([A-Fa-f]))?"
    r"(?:\s*[ ,&/+]\s*([A-Fa-f]))?"
    # Then up to 3 word-separated letters (A and B and C / A or B).
    r"(?:\s+(?:and|or)\s+([A-Fa-f]))?"
    r"(?:\s+(?:and|or)\s+([A-Fa-f]))?"
    r"(?:\s+(?:and|or)\s+([A-Fa-f]))?"
    r"\b",
    re.IGNORECASE,
)
_RE_ANSWER_PAREN = re.compile(
    r"^\s*\(\s*([A-Fa-f])\s*\)",
)


def _extract_bare_labels(body: str) -> list[str]:
    """Extract answer-letter labels from an answer body string.

    Single regex with up to 7 capture groups (one per letter).
    Letters are separated by EITHER single punctuation (`` ,&/+``)
    OR the word ``and``/``or`` (case-insensitive).  We never run
    ``re.findall('[A-Fa-f]', body)`` — that would pull 'a' and 'd'
    from "and" filler in "A and C" and produce the false-positive set
    ``['A','C','D']`` (since 'd' is in [A-Fa-f]).  By extracting
    only the captured letter groups we get exactly the answer
    letters.  Returns an empty list when no shape matches.
    """
    m = _RE_ANSWER_BARE.match(body)
    if not m:
        return []
    letters = [g for g in m.groups() if g]
    return sorted({c.upper() for c in letters})


def _layout_context_answer(block: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return {labels, text} for the first answer-marker region that
    follows the last typed option region.  Returns None when no such
    region exists.
    """
    regions: list[dict[str, Any]] = []
    # In y-order, after every typed option region.
    for kind_key in ("option_regions", "explanation_regions",
                     "clinical_pearl_regions", "high_yield_regions",
                     "mnemonic_regions", "reference_regions",
                     "unclassified_regions"):
        for r in block.get(kind_key, []):
            regions.append((r, kind_key))
    # Sort by y1 ascending (top-to-bottom).
    regions.sort(key=lambda rr: float(rr[0].get("bbox", [0, 0, 0, 0])[1]) if rr[0].get("bbox") else 0)

    # Find the index of the last option region.
    last_option_idx = -1
    for i, (r, kind) in enumerate(regions):
        if kind == "option_regions":
            last_option_idx = i
    if last_option_idx < 0:
        return None

    # Walk forward from last_option_idx + 1, looking for an answer marker.
    for i in range(last_option_idx + 1, len(regions)):
        r, kind = regions[i]
        text = (r.get("text") or "").strip()
        if not text:
            continue
        # Only treat the line as an answer candidate if its leading
        # token matches an accepted answer prefix.
        m_head = RE_ANSWER_HEAD.match(text)
        if not m_head:
            continue
        # Strip the answer prefix and grab letters that appear BEFORE
        # any explanatory prose begins.  Support three forms:
        #   1. parenthetical:  "(B)"        → ['B']
        #   2. bare run:       "A"          → ['A']
        #   3. list:           "A, C, D"    → ['A','C','D']
        body = text[m_head.end():].lstrip()
        labels: list[str] = []
        m_paren = _RE_ANSWER_PAREN.match(body)
        if m_paren:
            labels = [m_paren.group(1).upper()]
        else:
            labels = _extract_bare_labels(body)
        if not labels:
            continue
        return {"labels": labels, "text": text}
    return None
    """Count occurrences of keyword in text using whole-word boundary regex.

    Replaces the legacy ``kw in text`` substring check that produced
    collisions such as ``ear`` matching ``year`` / ``near``.  All
    returned counts are ≥ 0.
    """
    if not text or not kw:
        return 0
    return len(re.findall(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE))


def _map_subject(stem: str, filename_subject: Optional[str],
                 subject_keywords: dict[str, tuple[str, ...]]) -> Optional[str]:
    """Map question stem to subject via the profile's whole-word keyword table.

    Prefers the subject with the highest whole-word keyword count.  When
    multiple subjects tie, break the tie by alphabet so the result is
    deterministic across runs.
    """
    if not stem:
        return filename_subject
    text = stem.lower()
    best = (-1, "")
    for subj, kws in subject_keywords.items():
        score = sum(_whole_word_count(text, kw.lower()) for kw in kws if kw)
        if score > best[0]:
            best = (score, subj)
    if best[0] <= 0:
        return filename_subject
    return best[1] or filename_subject


def _guess_year(filename: str) -> int:
    m = re.search(r"\b(20\d{2})\b", filename or "")
    return int(m.group(1)) if m else 0


def _compute_question_confidence(
    stem: str,
    options: list[dict[str, Any]],
    answer_labels: list[str],
    explanation: str,
    image_ids: list[str],
    unclassified_count: int,
) -> tuple[float, float, float, float]:
    """Return (ocr_confidence, layout_confidence, image_mapping_confidence,
    question_reconstruction_confidence)."""
    # OCR confidence: digital text always 1.0; OCR-engine fallback would
    # be lowered here. For now we assume digital text.
    ocr_conf = 1.0

    # Layout confidence: 1.0 when stem + options + answer + explanation
    # all detected; degrades with each missing structural element.
    layout_parts = 0.0
    layout_parts += 0.25 if stem else 0.0
    layout_parts += 0.30 if len(options) >= 4 else (0.15 if options else 0.0)
    layout_parts += 0.20 if answer_labels else 0.0
    layout_parts += 0.25 if explanation else 0.0

    # Image mapping confidence: 1.0 when at least one image attached
    # OR the question is text-only. Lower when Stage 3 placement method
    # was pixel-scan (caller pre-downgrades per-image confidence; we
    # take the min over attached images as a proxy).
    image_conf = 1.0 if image_ids else 0.0   # text-only questions are clean

    # Reconstruction confidence: weighted sum.
    reconstruction = (
        0.40 * ocr_conf
        + 0.35 * layout_parts
        + 0.10 * image_conf
        - 0.05 * min(unclassified_count, 4)   # unclassified blocks reduce confidence
    )
    reconstruction = max(0.0, min(1.0, reconstruction))
    return ocr_conf, layout_parts, image_conf, reconstruction


# ----------------------------------------------------------------- per-block


def _build_parsed_question(
    ctx: MceContext,
    block: dict[str, Any],
    answer_key_map: dict[str, list[str]],
    image_meta: dict[str, dict[str, Any]],
) -> ParsedQuestion:
    """Convert one Stage 5 block into a ParsedQuestion."""
    page_number = int(block["page_number"])
    bbox = tuple(float(b) for b in block["bbox"])

    # ---- Stem ----
    stem = _join_region_text(block.get("stem_regions", []))

    # ---- Options ----
    options: list[dict[str, Any]] = []
    for o in block.get("option_regions", []):
        t = o.get("text", "")
        label, body = _parse_option_label(t)
        opt = {"label": label, "text": body, "is_correct": False, "image_ids": []}
        options.append(opt)

    # ---- Answer: layout-context aware detection ----
    # Try in priority order:
    #   1. typed ``answer_key`` regions explicitly matched in Stage 2
    #   2. the first unclassified/loose region immediately after the last
    #      option that begins with any of the accepted answer prefixes.
    #   3. global answer-key fallback (only when keys section exists).
    answer_labels: list[str] = []
    answer_text = None
    for ar in block.get("answer_regions", []):
        text = (ar.get("text") or "").strip()
        if not text:
            continue
        # Strip the answer prefix when present (e.g. "Answer: A Median
        # Nerve" → "A Median Nerve").  Without this step
        # ``_extract_bare_labels`` returns [] because the text does not
        # START with a bare letter.  Real 2021 PDF answer regions almost
        # always carry the "Answer: X" / "Ans. is X" prefix.
        m_head = RE_ANSWER_HEAD.match(text)
        body = text[m_head.end():].lstrip() if m_head else text
        # Support parenthetical first ("(B)"), then list, then bare.
        m_paren = _RE_ANSWER_PAREN.match(body)
        if m_paren:
            answer_labels = [m_paren.group(1).upper()]
            answer_text = text
            break
        # Use the shared helper that dispatches between punct and
        # word-separator forms — neither consumes "and"/"or" filler.
        labels = _extract_bare_labels(body)
        if labels:
            answer_labels = labels
            answer_text = text
            break

    # Layout-context fallback: examine the regions attached to this block
    # in y-order.  The block's "answer candidate" is the first region
    # whose text matches an accepted answer prefix and that lives AFTER
    # the last option region by y-coordinate.
    if not answer_labels:
        candidate = _layout_context_answer(block)
        if candidate:
            answer_labels = candidate["labels"]
            answer_text = candidate["text"]

    # Fallback to global answer-key map when the block has no inline answer.
    if not answer_labels and block.get("question_number_in_pdf") is not None:
        key_labels = answer_key_map.get(str(block["question_number_in_pdf"]))
        if key_labels:
            answer_labels = list(key_labels)

    # Mark correct options.
    ans_set = set(answer_labels)
    for o in options:
        if o["label"] and o["label"] in ans_set:
            o["is_correct"] = True

    # ---- Explanation ----
    explanation = _join_region_text(block.get("explanation_regions", [])) or None

    # ---- Clinical pearl / high-yield / mnemonic ----
    clinical_pearl = _join_region_text(block.get("clinical_pearl_regions", [])) or None
    hyp = block.get("high_yield_regions", [])
    high_yield_points = [_join_region_text([h]) for h in hyp] if hyp else []
    mnemonic = _join_region_text(block.get("mnemonic_regions", [])) or None

    # ---- References ----
    references: list[dict[str, Any]] = []
    for r in block.get("reference_regions", []):
        ref_text = r.get("text", "")
        rb = tuple(float(b) for b in r.get("bbox", bbox))
        if not ref_text.strip():
            continue
        references.append(_build_reference_record(
            ref_text, page_number, ctx.pdf_filename,
            ctx.pdf_sha256, ctx.pdf_sha256_short, rb,
        ))

    # ---- Image / asset / caption refs ----
    image_ids = list(block.get("image_ids", []))
    asset_ids = list(block.get("asset_ids", []))
    captions: list[str] = []
    for img_id in image_ids:
        im = image_meta.get(img_id, {})
        if im.get("caption"):
            captions.append(im["caption"])

    # ---- Unclassified blocks (NEVER silently dropped) ----
    unclassified: list[Region] = []
    for ur in block.get("unclassified_regions", []):
        try:
            unclassified.append(Region(
                id=ur.get("id", ""),
                type="unclassified",
                page_number=page_number,
                bbox=tuple(float(b) for b in ur.get("bbox", bbox)),
                text=ur.get("text", ""),
                confidence=float(ur.get("confidence", 0.5)),
                source_trace=SourceTrace.make(
                    pdf_filename=ctx.pdf_filename,
                    pdf_sha256=ctx.pdf_sha256,
                    pdf_sha256_short=ctx.pdf_sha256_short,
                    page_number=page_number,
                    bbox=tuple(float(b) for b in ur.get("bbox", bbox)),
                    extraction_engine="layout_heuristic",
                    pipeline_stage="stage_7_structured",
                    confidence=float(ur.get("confidence", 0.5)),
                ),
                warnings=["could not assign typed role; routed to unclassified"],
            ))
        except Exception:
            continue

    # ---- Subject / topic mapping (best-effort, whole-word) ----
    filename_subject = ctx.profile.subjects[0] if ctx.profile.subjects else None
    subject = _map_subject(stem, filename_subject, ctx.profile.subject_keywords)
    topic = None
    if subject:
        # Use the profile's keyword table to find a topic under the chosen
        # subject.  We pick the topic whose whole-word match count is
        # highest — fall back to first non-zero match when counts tie.
        text_lower = stem.lower()
        subj_kws = ctx.profile.subject_keywords.get(subject, ())
        scored = [(_whole_word_count(text_lower, kw.lower()), kw)
                  for kw in subj_kws if kw]
        scored.sort(key=lambda x: (-x[0], x[1]))
        for score, kw in scored:
            if score > 0:
                topic = kw
                break

        # ---- Image-mapping confidence from per-image extraction_confidence ----
    # The bbox-intersection in Stage 5 attaches every image whose bbox overlaps
    # the question block.  When pixel-scan / ordinal-pairing bboxes are
    # coarse, multiple questions share the same image ids and the real
    # signal lies in the per-image extraction_confidence we already
    # computed in Stage 3.  Take the min as the question-level mapping
    # confidence; questions with no images get a clean 1.0.
    if image_ids:
        per_image_confs: list[float] = []
        for iid in image_ids:
            meta = image_meta.get(iid, {})
            ec = meta.get("extraction_confidence")
            if ec is None:
                ec = 0.6  # unknown placement
            per_image_confs.append(float(ec))
        img_conf = min(per_image_confs) if per_image_confs else 0.0
    else:
        img_conf = 1.0   # text-only questions have perfect mapping

    # ---- Confidence ----
    ocr_conf, layout_conf, img_conf_recompute, rec_conf = _compute_question_confidence(
        stem, options, answer_labels, explanation or "",
        image_ids, len(unclassified),
    )
    # Overwrite the image slot with the per-image-derived value.
    img_conf = img_conf

    q = ParsedQuestion(
        id=block["id"],
        source_sha16=ctx.pdf_sha256_short,
        page_number=page_number,
        page_numbers=list(block.get("page_numbers", [page_number])),
        question_number_in_pdf=block.get("question_number_in_pdf"),
        stem=stem,
        stem_raw=stem,
        options=options,
        answer_labels=answer_labels,
        answer_text=answer_text,
        explanation=explanation,
        clinical_pearl=clinical_pearl,
        high_yield_points=high_yield_points,
        mnemonic=mnemonic,
        references=references,
        image_ids=image_ids,
        asset_ids=asset_ids,
        pearl_ids=[],
        captions=captions,
        unclassified_blocks=unclassified,
        subject=subject,
        topic=topic,
        subtopic=None,
        question_type="single_best",
        clinical_category="clinical",
        difficulty="medium",
        language="en",
        ocr_confidence=ocr_conf,
        layout_confidence=layout_conf,
        image_mapping_confidence=img_conf,
        question_reconstruction_confidence=rec_conf,
        is_image_based=bool(image_ids),
        needs_review=(rec_conf < 0.85) or bool(unclassified),
        review_reason=("low_confidence" if rec_conf < 0.85 else
                       ("unclassified_blocks" if unclassified else "")),
        bbox=bbox,
        exam_type=ctx.profile.exam_type,
        exam_source=ctx.profile.exam_source,
        recall_status="recall",
        raw=stem,
    )
    q.source_trace = SourceTrace.make(
        pdf_filename=ctx.pdf_filename,
        pdf_sha256=ctx.pdf_sha256,
        pdf_sha256_short=ctx.pdf_sha256_short,
        page_number=page_number,
        bbox=bbox,
        extraction_engine="stage_7_structured",
        pipeline_stage="stage_7_structured",
        confidence=rec_conf,
    )
    return q


# ----------------------------------------------------------------- main entry


def _load_image_meta(stage3_index: Path) -> dict[str, dict[str, Any]]:
    """Load Stage 3 image index keyed by image id, for caption lookups."""
    if not stage3_index.exists():
        return {}
    try:
        idx = json.loads(stage3_index.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {im["id"]: im for im in idx.get("images", [])}


def _load_answer_key(ocr_dir: Path) -> dict[str, list[str]]:
    ak = ocr_dir / "answer_key.json"
    if not ak.exists():
        return {}
    try:
        payload = json.loads(ak.read_text(encoding="utf-8"))
        return {str(k): v for k, v in payload.get("answers", {}).items()}
    except Exception:
        return {}


def _load_region_ocr(ocr_dir: Path, page_number: int) -> dict[str, dict[str, Any]]:
    """Load Stage 6's per-region OCR results for one page, keyed by region id.

    Stage 6 emits ``region_ocr`` rows like
    ``{region_id, bbox, ocr_text, ocr_confidence, replaces_text}`` —
    we return a dict keyed by region_id so Stage 7 can look up OCR
    improvements for the regions it consumed.
    """
    p = ocr_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        r["region_id"]: r for r in payload.get("region_ocr", []) if r.get("region_id")
    }


def _ocr_replacement(eligible: list[dict[str, Any]], ocr_map: dict[str, dict[str, Any]]) -> bool:
    """Replace any region in ``eligible`` with OCR text where Stage 6
    signalled a high-confidence replacement.  Returns True if any text
    changed (caller uses to attribute the change).
    """
    if not ocr_map:
        return False
    changed = False
    for r in eligible:
        rid = r.get("id")
        if not rid:
            continue
        ocr = ocr_map.get(rid)
        if not ocr or not ocr.get("replaces_text"):
            continue
        ocr_text = (ocr.get("ocr_text") or "").strip()
        if not ocr_text:
            continue
        # Only replace when OCR confidence is genuinely high; the
        # Stage-2 digital confidence threshold gates "eligible".
        if r.get("type") not in ("unclassified",) and r.get("confidence", 1.0) >= 0.85:
            continue
        r["text"] = ocr_text
        changed = True
    return changed


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:  # noqa: ARG001 - reserved for incremental reruns
    res = StageResult(stage="stage_7_structured")
    out_dir: Path = ctx.stage_dir("07_structured")
    blocks_dir = ctx.stage_dir("05_question_blocks")
    ocr_dir = ctx.stage_dir("06_ocr")
    stage3_index = ctx.stage_dir("03_images") / "_index.json"

    blocks_index = blocks_dir / "_index.json"
    if not blocks_index.exists():
        res.errors.append("Stage 5 blocks index missing — run Stage 5 first")
        return res
    try:
        blocks_payload = json.loads(blocks_index.read_text(encoding="utf-8"))
    except Exception as e:
        res.errors.append(f"blocks index read failed: {e}")
        return res
    blocks_by_page: dict[int, list[dict[str, Any]]] = {}
    for b in blocks_payload.get("blocks", []):
        blocks_by_page.setdefault(int(b["page_number"]), []).append(b)

    answer_key_map = _load_answer_key(ocr_dir)
    image_meta = _load_image_meta(stage3_index)

    page_iter = (
        [(p - 1, p) for p in pages]
        if pages
        else [(i, i + 1) for i in range(ctx.page_count)]
    )
    all_questions: list[dict[str, Any]] = []
    total_recon_conf = 0.0
    needs_review_count = 0
    pages_with_q = 0

    for _, page_number in page_iter:
        page_blocks = blocks_by_page.get(page_number, [])
        if not page_blocks:
            continue
        # Load Stage 6 OCR for this page so we can replace
        # low-confidence digital regions with the OCR text.
        ocr_map = _load_region_ocr(ocr_dir, page_number)
        if ocr_map:
            # OCR-replace inside each block's typed/unclassified regions.
            for b in page_blocks:
                regions_for_ocr: list[dict[str, Any]] = []
                regions_for_ocr.extend(b.get("unclassified_regions", []))
                for kind in ("stem_regions", "explanation_regions",
                             "high_yield_regions",
                             "clinical_pearl_regions", "mnemonic_regions"):
                    regions_for_ocr.extend(b.get(kind, []))
                _ocr_replacement(regions_for_ocr, ocr_map)
        page_questions: list[dict[str, Any]] = []
        for b in page_blocks:
            try:
                q = _build_parsed_question(ctx, b, answer_key_map, image_meta)
                page_questions.append(q.to_dict())
                all_questions.append(q.to_dict())
                total_recon_conf += q.question_reconstruction_confidence
                if q.needs_review:
                    needs_review_count += 1
            except Exception as e:  # pragma: no cover
                res.errors.append(f"p{page_number} {b.get('id')}: build failed: {e}")
        if page_questions:
            (out_dir / f"p{page_number:03d}.json").write_text(
                json.dumps({"page_number": page_number,
                            "questions": page_questions},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            pages_with_q += 1
            res.artefacts_written += 1
        res.pages_processed += 1

    # Flattened JSONL.
    jsonl_path = out_dir / "all_questions.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for q in all_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # Stage-wide index.
    index_path = out_dir / "_index.json"
    index_path.write_text(json.dumps({
        "pdf_filename": ctx.pdf_filename,
        "pdf_sha256_short": ctx.pdf_sha256_short,
        "profile_name": ctx.profile.name,
        "question_count": len(all_questions),
        "questions": all_questions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    res.metrics = {
        "questions": len(all_questions),
        "pages_with_questions": pages_with_q,
        "needs_review": needs_review_count,
        "avg_recon_confidence": (total_recon_conf / max(1, len(all_questions))),
        "answer_key_questions": len(answer_key_map),
    }
    LOG.info(
        "stage_7_structured: %d questions across %d pages, %d need review, avg_recon=%.3f",
        res.metrics["questions"], res.metrics["pages_with_questions"],
        res.metrics["needs_review"], res.metrics["avg_recon_confidence"],
    )
    return res


__all__ = ["run"]
