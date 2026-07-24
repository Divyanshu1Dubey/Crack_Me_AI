"""Stage 5 — Question block reconstruction.

Reads Stage 2 (layout regions) + Stage 3 (image anchors) + Stage 4
(table blocks) and groups everything into per-question blocks.

Algorithm
---------
1. Walk Stage 2 regions top-to-bottom on each page.
2. When a region is typed ``stem`` and was matched by the
   ``question_prefix`` rule, open a new QuestionBlock — UNLESS the
   current block is mid-explanation and the candidate stem line's
   number is small and contiguous to a list already in the current
   block (see ``_looks_like_continuation_bullet`` below).  This
   prevents "1. Measles…" / "3. JE vaccine…" inside an explanation
   from being treated as new questions.
3. All subsequent regions on the same page are appended to the current
   block by a simple state machine:

       stem -> options -> answer -> explanation -> clinical_pearl /
       high_yield / mnemonic / reference

   The first ``unclassified`` region after a stem continues the stem;
   after an explanation starts, unclassified regions continue the
   explanation.

   Continuation lines after an ``Explanation:`` head (or any of the
   trailing prose types) are also gated: a numbered line whose label
   is part of an in-flight bullet list is appended to the explanation,
   not opened as a new block.
4. After all pages are walked, each block is enriched with:
   - image_ids from Stage 3 whose bbox intersects the block bbox
   - asset_ids from Stage 4 whose bbox intersects the block bbox
   - unclassified_blocks that couldn't be merged (preserved as-is)
5. Cross-page stem recovery: blocks whose stem region is empty or
   obviously truncated (e.g. < 8 chars, or first word is a preposition
   like "of") are flagged for cross-page merge with the previous page
   when an explanation region exists that starts on a "stem-like"
   pattern.  This is handled in a post-pass.
6. A page_span entry is added per block whose pages are consecutive.

Outputs
-------
    05_question_blocks/p{NNN}.json   # per-page question blocks
    05_question_blocks/_index.json  # stage-wide index

Each question block carries an ``id`` (``p{NNN}_q{kk}``), a ``bbox``
encompassing every region in the block, and refs to images / assets /
unclassified blocks.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult
from mce.types import SourceTrace


LOG = logging.getLogger("mce.stage_5_question_blocks")


# ----------------------------------------------------------------- helpers


def _bbox_union(b1: tuple[float, ...], b2: tuple[float, ...]) -> tuple[float, ...]:
    return (
        min(b1[0], b2[0]),
        min(b1[1], b2[1]),
        max(b1[2], b2[2]),
        max(b1[3], b2[3]),
    )


def _bbox_intersects(a: tuple[float, ...], b: tuple[float, ...], min_overlap: float = 0.05) -> bool:
    """Return True if bboxes overlap by at least ``min_overlap`` of either's area."""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return False
    overlap = (x1 - x0) * (y1 - y0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return overlap >= min_overlap * min(area_a, area_b)


def _bbox_centroid(b: tuple[float, ...]) -> tuple[float, float]:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _bbox_area(b: tuple[float, ...]) -> float:
    return max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))


def _load_stage3_anchors(stage3_index: Path, page_number: int) -> list[dict[str, Any]]:
    if not stage3_index.exists():
        return []
    try:
        idx = json.loads(stage3_index.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [im for im in idx.get("images", []) if int(im.get("page_number", -1)) == page_number]


def _load_stage4_anchors(stage4_index: Path, page_number: int) -> list[dict[str, Any]]:
    if not stage4_index.exists():
        return []
    try:
        idx = json.loads(stage4_index.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [t for t in idx.get("tables", []) if int(t.get("page_number", -1)) == page_number]


def _attach_anchors(
    block_bbox: tuple[float, ...],
    image_anchors: list[dict[str, Any]],
    table_anchors: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    """Attach image_ids / asset_ids / unclassified_blocks to a block.

    Returns (image_ids, asset_ids, attached_image_ids_for_continuation).
    """
    image_ids: list[str] = []
    asset_ids: list[str] = []
    for im in image_anchors:
        bb = tuple(float(b) for b in im.get("bbox", []))
        if any(bb) and _bbox_intersects(block_bbox, bb, min_overlap=0.02):
            image_ids.append(im["id"])
    for t in table_anchors:
        bb = tuple(float(b) for b in t.get("bbox", []))
        if any(bb) and _bbox_intersects(block_bbox, bb, min_overlap=0.05):
            asset_ids.append(t["id"])
    return image_ids, asset_ids, []


def _attach_anchors_per_block(
    blocks: list[dict[str, Any]],
    image_anchors: list[dict[str, Any]],
    table_anchors: list[dict[str, Any]],
) -> None:
    """Improved image-to-question attach — preserves uncertainty.

    Two strategies, applied in order:

    1. **Geometric containment** — image bbox is *inside* the block bbox
       (with tolerance).  High confidence attach.
    2. **Vertical proximity** — when containment fails, distribute
       unattached images to blocks by centroid-distance along Y, so
       multiple questions on a page each get the image nearest their
       centroid instead of all of them.

    Tables use the simpler bbox-intersection rule (they're usually
    big enough to disambiguate by overlap alone).
    """
    if not image_anchors and not table_anchors:
        return

    # Index blocks by id (mutable — we'll write image_ids/asset_ids).
    attached_imgs: set[str] = set()
    for b in blocks:
        ids: list[str] = []
        bb = tuple(float(x) for x in b["bbox"])
        for im in image_anchors:
            im_bb = tuple(float(x) for x in im.get("bbox", []))
            if not any(im_bb):
                continue
            # Strategy 1: containment (tolerant of small bbox imprecision).
            ix0, iy0, ix1, iy1 = im_bb
            contains_x = ix0 >= bb[0] - 5 and ix1 <= bb[2] + 5
            contains_y = iy0 >= bb[1] - 5 and iy1 <= bb[3] + 5
            if contains_x and contains_y:
                ids.append(im["id"])
                attached_imgs.add(im["id"])
        b["image_ids"] = ids

    # Strategy 2: distribute any unattached images to the closest block on
    # the page by centroid distance (Y-axis dominant because the page
    # scan runs top-to-bottom).
    page_imgs = [im for im in image_anchors if im["id"] not in attached_imgs and any(im.get("bbox", []))]
    if page_imgs:
        # Order blocks top-to-bottom on this page.
        ordered_blocks = sorted(
            [b for b in blocks if b.get("image_ids") is not None],
            key=lambda b: _bbox_centroid(tuple(b["bbox"]))[1],
        )
        for im in page_imgs:
            im_cy = _bbox_centroid(tuple(im["bbox"]))[1]
            best_b = None
            best_dist = float("inf")
            for b in ordered_blocks:
                bcx, bcy = _bbox_centroid(tuple(b["bbox"]))
                # Distance from image center to block top/bottom — pick
                # the block whose vertical extent "contains" or is
                # nearest the image's center Y.
                b_top, b_bot = b["bbox"][1], b["bbox"][3]
                if b_top - 10 <= im_cy <= b_bot + 10:
                    dist = 0
                else:
                    dist = min(abs(im_cy - b_top), abs(im_cy - b_bot))
                if dist < best_dist:
                    best_dist = dist
                    best_b = b
            if best_b is not None and best_dist < 200:    # within 200 PDF-pt
                best_b["image_ids"].append(im["id"])
                attached_imgs.add(im["id"])

    # Tables stay with the simple overlap rule (they're usually distinct).
    for b in blocks:
        a_ids: list[str] = []
        bb = tuple(float(x) for x in b["bbox"])
        for t in table_anchors:
            tb = tuple(float(x) for x in t.get("bbox", []))
            if any(tb) and _bbox_intersects(bb, tb, min_overlap=0.05):
                a_ids.append(t["id"])
        b["asset_ids"] = a_ids


def _detect_question_number(region: dict[str, Any]) -> Optional[int]:
    """Pull the question number from a stem region's text (e.g. '53. A female...')."""
    m = re.match(r"^\s*(\d{1,4})\s*[\.\)]\s*", region.get("text", ""))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


# Match a "1. text" / "1) text" / "(a) text" line — used to decide if a
# stem-tagged region is really a continuation bullet inside an existing
# block's explanation list.
_RE_NUMBERED_BULLET = re.compile(r"^\s*\(?(\d{1,3})[\.\)]\s+\S")


def _looks_like_continuation_bullet(
    text: str,
    current: Optional[dict[str, Any]],
) -> bool:
    """Return True when ``text`` is a numbered bullet that's plausibly
    a continuation of an in-flight bullet list inside ``current``.

    Triggers (all of):
      1. ``text`` matches the numbered-bullet shape.
      2. The current block already has at least one explanation region.
      3. The candidate number is contiguous to the previous bullet
         already in the explanation list (≤ previous + 2) OR the
         block's bbox grew vertically without a question mark on the
         candidate line (so it's a list item, not a question stem).

    This was the root cause of Bug 1: ``RE_QUESTION_PREFIX`` in
    layout_heuristic.py also matches ``1. Measles is a childhood
    infection caused by a virus.`` — a list item inside the
    explanation.  Without this guard Stage 5 opens a phantom question.
    """
    if current is None:
        return False
    if not _RE_NUMBERED_BULLET.match(text):
        return False
    # The current block must already have an explanation list in flight.
    if not current.get("explanation_regions"):
        return False
    # Walk existing explanation regions: collect their leading numbers.
    prev_numbers: list[int] = []
    for er in current["explanation_regions"]:
        m = _RE_NUMBERED_BULLET.match(er.get("text", ""))
        if m:
            try:
                prev_numbers.append(int(m.group(1)))
            except ValueError:
                pass
    cand_m = _RE_NUMBERED_BULLET.match(text)
    if not cand_m:
        return False
    cand_n = int(cand_m.group(1))
    # BUG 7 guard: a real question stem is usually long (> 60 chars
    # body, no terminal period).  The Bug 6 fix made
    # explanation_regions non-empty on most blocks, which caused this
    # guard to over-fire on the next question's stem (e.g. "2. A small
    # boy with multiple fracture of Humerus..." was being absorbed as
    # a continuation bullet of the previous explanation's "1. The
    # doctor places...").  Real question stems are long sentences
    # that describe a clinical scenario; bullets are short and end
    # with a period.  Distinguish them by body length AND terminal
    # punctuation.
    body_text = text[cand_m.end():].strip() if cand_m else ""
    if len(body_text) > 60 and not body_text.endswith("."):
        # Long body without a terminal period — looks like a real
        # question stem describing a clinical scenario.  Don't treat
        # as a continuation bullet regardless of prior numbers.
        return False
    # If the current explanation already has bullets numbered 1, 2, 3
    # and this candidate is "4." or "5." → it's a continuation.
    if prev_numbers and cand_n <= max(prev_numbers) + 2 and cand_n >= 1:
        return True
    # Heuristic 2: the line does not end with a question mark and is
    # shorter than a typical stem — assume it's a bullet in a list.
    text_stripped = text.rstrip()
    if not text_stripped.endswith("?"):
        # If the candidate number is also ≤ 9, very likely a list item.
        if cand_n <= 9:
            return True
    return False


def _looks_like_continuation_option(
    text: str,
    current: Optional[dict[str, Any]],
) -> bool:
    """Return True when ``text`` is a continuation of an in-flight option
    list (so it must NOT be opened as a new option).

    Stage 2's ``RE_OPTION_PREFIX`` is too permissive: it matches
    ``Ans. is a i.e. Scurvy`` and ``Explanation`` as if they were
    options A and E.  This guard detects such lines by their prefix
    and treats them as trailing prose.
    """
    if current is None:
        return False
    t = text.strip()
    if not t:
        return False
    tl = t.lower()
    # Lines starting with these prefixes are NOT options, no matter what
    # layout_heuristic said.
    bad_prefixes = (
        "ans.", "ans ", "answer:", "answer-", "answer<", "explanation",
        "exp:", "explain:", "clinical pearl", "high yield", "mnemonic",
        "reference", "ref:", "source:", "textbook",
        # Watermarks + footer-style lines from MEDICAL JUNCTION
        "medical junction", "medical-junction",
        # Section headers that often follow the answer+explanation
        "radiographic features", "pediatric", "adult",
    )
    for p in bad_prefixes:
        if tl.startswith(p):
            return True
    return False


def _looks_like_truncated_stem(block: dict[str, Any]) -> bool:
    """Return True when the block's stem looks truncated or missing.

    Used by the cross-page stem-recovery pass: a stem with very few
    characters or starting with a preposition is almost certainly the
    tail of a question whose real stem lives on the previous page.
    """
    stems = block.get("stem_regions") or []
    text = " ".join((s.get("text") or "").strip() for s in stems).strip()
    if not text:
        return True
    if len(text) < 8:
        return True
    first_word = text.split()[0].lower().strip(",.;:?!")
    if first_word in {"of", "the", "a", "an", "in", "on", "with", "to",
                      "and", "or", "for", "by", "is", "are", "was", "were"}:
        return True
    return False


# ----------------------------------------------------------------- per-page state machine


def _group_regions_into_blocks(
    page_number: int,
    regions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group Stage 2 regions into question blocks via a small state machine."""
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    last_typed_kind = "stem"      # what the next unclassified region should join

    def open_block(start_region: dict[str, Any], qno: Optional[int]) -> None:
        nonlocal current, last_typed_kind
        bbox = tuple(float(b) for b in start_region["bbox"])
        current = {
            "id": None,                    # filled after we know its index
            "page_number": page_number,
            "page_numbers": [page_number],
            "question_number_in_pdf": qno,
            "stem_regions": [start_region],
            "option_regions": [],
            "answer_regions": [],
            "explanation_regions": [],
            "clinical_pearl_regions": [],
            "high_yield_regions": [],
            "mnemonic_regions": [],
            "reference_regions": [],
            "unclassified_regions": [],
            "bbox": list(bbox),
            "match_rules": [start_region.get("match_rule", "")],
        }
        last_typed_kind = "stem"

    def append_region(region: dict[str, Any]) -> None:
        nonlocal current, last_typed_kind
        if current is None:
            return
        kind = region.get("type", "unclassified")
        bbox = tuple(float(b) for b in region["bbox"])
        current["bbox"] = list(_bbox_union(tuple(current["bbox"]), bbox))
        if kind == "option":
            current["option_regions"].append(region)
            last_typed_kind = "option"
        elif kind == "answer_key":
            current["answer_regions"].append(region)
            last_typed_kind = "answer_key"
        elif kind == "explanation":
            current["explanation_regions"].append(region)
            last_typed_kind = "explanation"
        elif kind == "clinical_pearl":
            current["clinical_pearl_regions"].append(region)
            last_typed_kind = "clinical_pearl"
        elif kind == "high_yield":
            current["high_yield_regions"].append(region)
            last_typed_kind = "high_yield"
        elif kind == "mnemonic":
            current["mnemonic_regions"].append(region)
            last_typed_kind = "mnemonic"
        elif kind == "reference":
            current["reference_regions"].append(region)
            last_typed_kind = "reference"
        elif kind in ("header", "footer"):
            # Skip watermarks + page numbers — never part of a question block.
            return
        elif kind == "unclassified":
            # Merge with the previous typed region.
            if last_typed_kind == "stem":
                current["stem_regions"].append(region)
            elif last_typed_kind == "option":
                # BUG 2 cap: NEET-PG questions never exceed 4 options
                # (A-D).  Once the block has 4 options, no further
                # unclassified region should silently merge into
                # ``option_regions`` — push them into the unclassified
                # bucket where the orphan-sweep post-pass can route
                # them (explanation / clinical_pearl / etc.).
                if len(current.get("option_regions", [])) >= 4:
                    current["unclassified_regions"].append(region)
                else:
                    current["option_regions"].append(region)
            elif last_typed_kind == "answer_key":
                # Once the answer has been captured, the next unclassified
                # region is almost always the explanation prose (the 2021
                # PDF interleaves them: "Answer: A" + "Median Nerve" + 3
                # paragraphs of explanation).  Routing them to
                # ``explanation_regions`` keeps the answer line clean and
                # lets Stage 7 emit a real explanation.
                if current.get("answer_regions"):
                    current["explanation_regions"].append(region)
                else:
                    current["answer_regions"].append(region)
            elif last_typed_kind == "explanation":
                current["explanation_regions"].append(region)
            elif last_typed_kind == "clinical_pearl":
                current["clinical_pearl_regions"].append(region)
            elif last_typed_kind == "high_yield":
                current["high_yield_regions"].append(region)
            elif last_typed_kind == "mnemonic":
                current["mnemonic_regions"].append(region)
            elif last_typed_kind == "reference":
                current["reference_regions"].append(region)
            else:
                current["unclassified_regions"].append(region)
        else:
            current["unclassified_regions"].append(region)
        current["match_rules"].append(region.get("match_rule", ""))

    def close_block() -> None:
        nonlocal current
        if current is None:
            return
        blocks.append(current)
        current = None

    for r in regions:
        kind = r.get("type", "unclassified")
        rule = r.get("match_rule", "")
        text = (r.get("text") or "").strip()
        # Question start: a stem region matched by question_prefix.
        if kind == "stem" and rule == "question_prefix":
            # BUG 1 guard: if the candidate stem is actually a
            # continuation bullet inside the current block's
            # explanation list, treat it as part of the explanation
            # instead of opening a new block.
            if _looks_like_continuation_bullet(text, current):
                # Re-tag the region as unclassified so append_region
                # routes it to the right bucket (explanation, since
                # the current block already has explanation regions).
                r2 = dict(r)
                r2["type"] = "unclassified"
                append_region(r2)
                continue
            # BUG 1 second guard: if the candidate is a numbered
            # bullet in a tiny current block (only stem) AND the
            # current stem doesn't end with a question mark, it's a
            # list inside a stem-list explanation.  Force it into the
            # current stem.
            if (current is not None
                    and _RE_NUMBERED_BULLET.match(text)
                    and not current.get("option_regions")
                    and not current.get("explanation_regions")
                    and not any((s.get("text") or "").strip().endswith("?")
                                for s in current.get("stem_regions", []))):
                r2 = dict(r)
                r2["type"] = "unclassified"
                append_region(r2)
                continue
            # Close any open block first.
            close_block()
            qno = _detect_question_number(r)
            open_block(r, qno)
            continue
        if current is None:
            # Stray region before the first question — keep as unclassified.
            continue
        # BUG 2 guard: an "option" region whose text starts with a
        # non-option prefix is not actually an option — treat as
        # continuation of the previous typed region.
        if kind == "option" and _looks_like_continuation_option(text, current):
            r2 = dict(r)
            r2["type"] = "unclassified"
            append_region(r2)
            continue
        # BUG 2 secondary guard: an unclassified region whose text
        # starts with a known non-option prefix must NOT silently merge
        # into the last typed region (which is usually ``option``).
        # Examples: "Ans. is a i.e. Scurvy" must NOT be appended to
        # option_regions; "Explanation" / "Radiographic features" /
        # "Pediatric" / "MEDICAL JUNCTION TEAM" must NOT either.
        # Force them into ``unclassified_regions`` so the orphan-sweep
        # post-pass can route them correctly.
        if kind == "unclassified" and _looks_like_continuation_option(text, current):
            r2 = dict(r)
            r2["type"] = "unclassified"
            # Override: append_region merges unclassified into last
            # typed kind. Force it into the unclassified bucket by
            # temporarily clearing last_typed_kind.  Easiest path:
            # set kind to something append_region won't recognize so
            # it falls through to the ``else`` branch (unclassified).
            r2["type"] = "annotation"  # not a known kind; will fall through
            append_region(r2)
            continue
        append_region(r)

    close_block()
    return blocks


def _block_to_dict(idx: int, block: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001 - idx reserved for future use
    page = block["page_number"]
    return {
        "id": f"p{page:03d}_q{idx:02d}",
        "page_number": page,
        "page_numbers": list(block["page_numbers"]),
        "question_number_in_pdf": block["question_number_in_pdf"],
        "bbox": block["bbox"],
        "region_counts": {
            "stem": len(block["stem_regions"]),
            "option": len(block["option_regions"]),
            "answer": len(block["answer_regions"]),
            "explanation": len(block["explanation_regions"]),
            "clinical_pearl": len(block["clinical_pearl_regions"]),
            "high_yield": len(block["high_yield_regions"]),
            "mnemonic": len(block["mnemonic_regions"]),
            "reference": len(block["reference_regions"]),
            "unclassified": len(block["unclassified_regions"]),
        },
        "match_rules": block["match_rules"],
    }


# ----------------------------------------------------------------- cross-page recovery + orphan sweep


def _merge_truncated_with_previous(
    blocks_sorted: list[dict[str, Any]],
) -> int:
    """BUG 4 + BUG 5: when a block's stem looks truncated or missing
    AND it has an explanation region, merge it into the previous block
    on the prior page.

    Returns the number of merges performed.
    """
    merges = 0
    # Walk in page-order; pair each block with its immediate predecessor
    # on the page just before it.
    i = 0
    while i < len(blocks_sorted):
        cur = blocks_sorted[i]
        if not _looks_like_truncated_stem(cur):
            i += 1
            continue
        # Find the most-recent block on a strictly earlier page.
        prev = None
        for j in range(i - 1, -1, -1):
            if int(blocks_sorted[j].get("page_number", -1)) < int(cur["page_number"]):
                prev = blocks_sorted[j]
                break
        if prev is None:
            i += 1
            continue
        # Merge cur into prev.  Move every region from cur into prev.
        for key in ("stem_regions", "option_regions", "answer_regions",
                    "explanation_regions", "clinical_pearl_regions",
                    "high_yield_regions", "mnemonic_regions",
                    "reference_regions", "unclassified_regions"):
            prev.setdefault(key, []).extend(cur.get(key, []))
        # Update bbox.
        prev_bbox = list(prev["bbox"])
        cur_bbox = list(cur["bbox"])
        prev["bbox"] = [
            min(prev_bbox[0], cur_bbox[0]),
            min(prev_bbox[1], cur_bbox[1]),
            max(prev_bbox[2], cur_bbox[2]),
            max(prev_bbox[3], cur_bbox[3]),
        ]
        # Track that this block now spans multiple pages.
        prev.setdefault("page_numbers", [prev.get("page_number")])
        if cur.get("page_number") not in prev["page_numbers"]:
            prev["page_numbers"].append(cur["page_number"])
        prev.setdefault("match_rules", []).extend(cur.get("match_rules", []))
        # Remove cur from the list.
        del blocks_sorted[i]
        merges += 1
        # Don't increment i — re-check the new cur position.
    return merges


def _sweep_continuation_orphans(
    blocks: list[dict[str, Any]],
) -> int:
    """BUG 5: when a block's ``unclassified_regions`` are clearly
    continuation prose of the block's explanation (e.g. an Explanation:
    head followed by free text), fold them into the explanation bucket.

    Returns the number of orphan regions re-routed.
    """
    swept = 0
    for b in blocks:
        unclass = list(b.get("unclassified_regions") or [])
        if not unclass:
            continue
        # If the block already has an explanation, sweep all unclassified
        # into the explanation (continuation prose).
        if b.get("explanation_regions"):
            for ur in unclass:
                if ur.get("text"):
                    b["explanation_regions"].append(ur)
                    swept += 1
            b["unclassified_regions"] = []
            continue
        # If the block has 0 explanation regions BUT the very first
        # unclassified region begins with "Explanation" or "Exp:" or
        # similar (heuristic), route ALL orphans into a new
        # explanation list.
        if unclass and any(
            re.match(r"^\s*(?:Explanation|Exp)\s*[:\-]?",
                     (u.get("text") or ""), re.IGNORECASE)
            for u in unclass[:1]
        ):
            b.setdefault("explanation_regions", []).extend(unclass)
            b["unclassified_regions"] = []
            swept += len(unclass)
    return swept


# ----------------------------------------------------------------- main entry


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_5_question_blocks")
    out_dir: Path = ctx.stage_dir("05_question_blocks")
    index_path = out_dir / "_index.json"
    layout_dir = ctx.stage_dir("02_layout")
    stage3_index = ctx.stage_dir("03_images") / "_index.json"
    stage4_index = ctx.stage_dir("04_tables") / "_index.json"

    prev_index: dict[str, dict] = {}
    if index_path.exists() and not force:
        try:
            prev_index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            prev_index = {}

    page_iter = (
        [(p - 1, p) for p in pages]
        if pages
        else [(i, i + 1) for i in range(ctx.page_count)]
    )
    all_blocks: list[dict[str, Any]] = list(prev_index.get("blocks", []))
    done_pages = {int(b["page_number"]) for b in all_blocks}

    for _page_idx, page_number in page_iter:
        if not force and page_number in done_pages:
            res.pages_skipped += 1
            continue
        layout_path = layout_dir / f"p{page_number:03d}.json"
        if not layout_path.exists():
            res.warnings.append(f"p{page_number}: no Stage 2 layout, skipping")
            continue
        try:
            layout_payload = json.loads(layout_path.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover
            res.errors.append(f"p{page_number}: layout read failed: {e}")
            continue
        regions = layout_payload.get("regions", [])
        blocks = _group_regions_into_blocks(page_number, regions)

        image_anchors = _load_stage3_anchors(stage3_index, page_number)
        table_anchors = _load_stage4_anchors(stage4_index, page_number)

        # Index within page + attach image/asset ids using the per-block
        # proximity heuristic (preserves uncertainty instead of greedy
        # overlap-to-everything).
        for idx, b in enumerate(blocks):
            b["image_ids"] = []
            b["asset_ids"] = []
            b["id"] = f"p{page_number:03d}_q{idx:02d}"
            b["source_trace"] = SourceTrace.make(
                pdf_filename=ctx.pdf_filename,
                pdf_sha256=ctx.pdf_sha256,
                pdf_sha256_short=ctx.pdf_sha256_short,
                page_number=page_number,
                bbox=tuple(b["bbox"]),
                extraction_engine="stage_5_question_blocks",
                pipeline_stage="stage_5_question_blocks",
                confidence=1.0,
            ).to_dict()
        _attach_anchors_per_block(blocks, image_anchors, table_anchors)

        page_payload = {
            "page_number": page_number,
            "block_count": len(blocks),
            "blocks": blocks,                  # preserve rich block info
            "summaries": [_block_to_dict(i, b) for i, b in enumerate(blocks)],
        }
        (out_dir / f"p{page_number:03d}.json").write_text(
            json.dumps(page_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        all_blocks = [bb for bb in all_blocks if int(bb["page_number"]) != page_number]
        all_blocks.extend(blocks)
        res.artefacts_written += 1
        res.pages_processed += 1

    # Sort page-order for cross-page pass.
    all_blocks.sort(key=lambda b: (int(b["page_number"]), b["id"]))

    # BUG 5: sweep orphan continuations before cross-page merge so that
    # the orphan count seen by Bug 4 is the *true* leftover.
    swept = _sweep_continuation_orphans(all_blocks)
    # BUG 4: cross-page stem recovery — merge truncated blocks into
    # their predecessor on the previous page.
    merges = _merge_truncated_with_previous(all_blocks)

    # Re-number IDs after merges (some q{NN} slots are now free).
    seq = 0
    for b in all_blocks:
        # The id is page-based + sequential on that page.
        pass  # ids stay as p{NNN}_q{NN} by page; order not affected.

    out_index = {
        "pdf_filename": ctx.pdf_filename,
        "pdf_sha256_short": ctx.pdf_sha256_short,
        "block_count": len(all_blocks),
        "blocks": all_blocks,
        "post_passes": {
            "continuation_orphans_swept": swept,
            "cross_page_merges": merges,
        },
    }
    index_path.write_text(
        json.dumps(out_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Metrics.
    per_page: dict[int, int] = {}
    for b in all_blocks:
        per_page[int(b["page_number"])] = per_page.get(int(b["page_number"]), 0) + 1
    res.metrics = {
        "total_question_blocks": len(all_blocks),
        "pages_with_blocks": len(per_page),
        "avg_blocks_per_page": (sum(per_page.values()) / max(1, len(per_page))),
        "continuation_orphans_swept": swept,
        "cross_page_merges": merges,
    }
    LOG.info("stage_5_question_blocks: %d blocks across %d pages (avg %.1f/page); "
             "swept %d orphans, merged %d cross-page",
             res.metrics["total_question_blocks"], res.metrics["pages_with_blocks"],
             res.metrics["avg_blocks_per_page"], swept, merges)
    return res


__all__ = ["run"]
