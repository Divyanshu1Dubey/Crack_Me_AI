"""Stage 8 — Per-page QA + annotated overlays.

Aggregates Stage 2 (typed regions), Stage 3 (images), Stage 4 (tables),
Stage 5 (question blocks) + Stage 7 (structured questions) and produces:

    08_qa/overlays/p{NNN}.png   # single annotated PNG per page
    08_qa/per_page_report.json  # {page_number: {status, regions, issues, ...}}
    08_qa/per_question_qa.json  # per-question 9-axis V2 scores
    08_qa/summary.json          # {pass_count, fail_count, top_failure_modes, ...}

Page PASS criteria (legacy / engineering gate):
    question_reconstruction_confidence >= 0.85
    AND unclassified_blocks.count <= 2
    AND image_mapping_recall >= 0.95

QA V2 (per-question, educational fidelity):
    Each question is scored on 9 axes by ``mce.qa_v2.score_question``
    and labelled "Production Ready" / "Needs Review" / "Extraction
    Failure".  A page is importable when no question is an Extraction
    Failure.

DB writes for any question on a FAIL page are blocked by downstream
stages (the platform DB writer will respect this).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mce import qa_v2
from mce.debug_overlay import render_overlay
from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_8_qa")


PASS_THRESHOLD = 0.85
MAX_UNCLASSIFIED_BLOCKS = 2


def _load_stage2_regions(stage2_dir: Path, page_number: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (typed_regions, unclassified_regions)."""
    p = stage2_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return [], []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    regions = payload.get("regions", [])
    typed = [r for r in regions if r.get("type") not in ("unclassified", "header", "footer")]
    unclass = [r for r in regions if r.get("type") == "unclassified"]
    return typed, unclass


def _load_stage3_images(stage3_dir: Path, page_number: int) -> list[tuple[str, list[float]]]:
    p = stage3_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [(im["id"], im.get("bbox", [])) for im in payload.get("images", []) if im.get("bbox")]


def _load_stage4_tables(stage4_dir: Path, page_number: int) -> list[tuple[str, list[float]]]:
    p = stage4_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [(t["id"], t.get("bbox", [])) for t in payload.get("tables", []) if t.get("bbox")]


def _load_stage5_blocks(stage5_dir: Path, page_number: int) -> list[dict[str, Any]]:
    p = stage5_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("blocks", [])
    except Exception:
        return []


def _load_stage7_questions(stage7_dir: Path, page_number: int) -> list[dict[str, Any]]:
    p = stage7_dir / f"p{page_number:03d}.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("questions", [])
    except Exception:
        return []


def _recompute_question_confidence(q: dict[str, Any],
                                    unclassified_count: int,
                                    per_image_confs: list[float]) -> dict[str, float]:
    """Compute 4-dim confidence for a question, matching Stage 7's formula.

    Re-exported here so Stage 8 can re-evaluate after Stage 7.5's
    LLM-augmentation without re-running the whole pipeline.
    """
    stem = q.get("stem") or ""
    options = q.get("options") or []
    answer_labels = q.get("answer_labels") or []
    explanation = q.get("explanation") or ""
    image_ids = q.get("image_ids") or []
    ocr_conf = 1.0
    layout_parts = (
        0.25 if stem else 0.0
        + 0.30 if len(options) >= 4 else (0.15 if options else 0.0)
        + 0.20 if answer_labels else 0.0
        + 0.25 if explanation else 0.0
    )
    # The conditional expression above is invalid as written — recompute
    # cleanly:
    layout_parts = 0.0
    layout_parts += 0.25 if stem else 0.0
    layout_parts += 0.30 if len(options) >= 4 else (0.15 if options else 0.0)
    layout_parts += 0.20 if answer_labels else 0.0
    layout_parts += 0.25 if explanation else 0.0
    if image_ids:
        img_conf = min(per_image_confs) if per_image_confs else 0.0
    else:
        img_conf = 1.0
    reconstruction = 0.40 * ocr_conf + 0.35 * layout_parts + 0.10 * img_conf
    reconstruction -= 0.05 * min(unclassified_count, 4)
    reconstruction = max(0.0, min(1.0, reconstruction))
    return {
        "ocr_confidence": ocr_conf,
        "layout_confidence": layout_parts,
        "image_mapping_confidence": img_conf,
        "question_reconstruction_confidence": reconstruction,
    }


def _load_augmented_questions(stage7_5_dir: Path) -> dict[str, dict[str, Any]]:
    """Load Stage 7.5's augmented.json payload."""
    p = stage7_5_dir / "augmented.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("augmented", {})
    except Exception:
        return {}


def _bbox_contains(outer: list[float], inner: list[float], tol: float = 5.0) -> bool:
    if not outer or not inner or len(outer) < 4 or len(inner) < 4:
        return False
    return (
        outer[0] - tol <= inner[0]
        and outer[1] - tol <= inner[1]
        and outer[2] + tol >= inner[2]
        and outer[3] + tol >= inner[3]
    )


def _evaluate_page(
    typed: list[dict[str, Any]],
    unclass: list[dict[str, Any]],
    images: list[tuple[str, list[float]]],
    tables: list[tuple[str, list[float]]],
    blocks: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    augmented: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return a per-page QA report dict.

    When Stage 7.5 ran, ``augmented`` carries the LLM-updated fields
    per question id; we overlay those onto the deterministic Stage-7
    questions before computing per-page metrics, then RE-compute the
    4-dim confidence using the formula Stage 7 uses.  This is the only
    way the QA gate can reflect the LLM's contribution to quality.
    """
    # Unclassified regions that are inside ANY question-block bbox on
    # this page are *consumed* by Stage 5 (merged as continuation), not
    # orphan content.  Discount them so the QA gate reflects real
    # leftover unclassified regions.
    block_bboxes = [b.get("bbox") for b in blocks if b.get("bbox")]
    consumed = 0
    orphans: list[dict[str, Any]] = []
    for u in unclass:
        ub = u.get("bbox") or []
        if any(_bbox_contains(bb, ub) for bb in block_bboxes):
            consumed += 1
        else:
            orphans.append(u)
    unclass_count = len(orphans)

    # Overlay Stage 7.5 augmentations when present + re-score each
    # question's recon confidence using the formula.  Augmented
    # questions typically gain stem / options / explanation text
    # and lose unclassified regions, lifting both layout_conf and
    # the recon score.
    if augmented:
        for q in questions:
            aug = augmented.get(q.get("id"))
            if not aug or not aug.get("llm_applied"):
                continue
            # Replace deterministic fields with augmented ones.
            for k in ("stem", "explanation", "clinical_pearl",
                      "high_yield_points", "mnemonic", "options",
                      "answer_labels"):
                if k in aug and aug[k]:
                    q[k] = aug[k]
            # Re-score with the same formula Stage 7 uses.
            unc = q.get("unclassified_blocks") or []
            ic = [_recompute_image_conf(q.get("image_ids") or [])]
            new = _recompute_question_confidence(q, len(unc), ic)
            for k, v in new.items():
                q[k] = v
            # Flag the augmentation so downstream stages know this
            # row was LLM-augmented.
            q["llm_applied"] = True

    questions_count = len(questions)
    avg_recon = (
        sum(q.get("question_reconstruction_confidence", 0) for q in questions)
        / max(1, questions_count)
    )
    image_mapping_conf_avg = (
        sum(q.get("image_mapping_confidence", 0) for q in questions)
        / max(1, questions_count)
    )

    issues: list[dict[str, Any]] = []
    if unclass_count > MAX_UNCLASSIFIED_BLOCKS:
        issues.append({"type": "too_many_unclassified", "count": unclass_count})
    if avg_recon < PASS_THRESHOLD:
        issues.append({"type": "low_avg_recon", "value": round(avg_recon, 3)})
    if image_mapping_conf_avg < 0.95:
        issues.append({"type": "low_image_mapping", "value": round(image_mapping_conf_avg, 3)})
    if questions_count == 0 and (typed or unclass):
        issues.append({"type": "no_question_blocks_detected"})

    status = "PASS" if not issues else "FAIL"
    return {
        "status": status,
        "typed_region_count": len(typed),
        "unclassified_count": unclass_count,
        "unclassified_consumed_by_stage5": consumed,
        "image_count": len(images),
        "table_count": len(tables),
        "block_count": len(blocks),
        "question_count": questions_count,
        "avg_question_reconstruction_confidence": round(avg_recon, 4),
        "avg_image_mapping_confidence": round(image_mapping_conf_avg, 4),
        "issues": issues,
    }


def _recompute_image_conf(image_ids: list[str]) -> float:
    """Conservative default when Stage 3 image conf not in scope."""
    return 0.5 if image_ids else 1.0


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_8_qa")
    out_dir: Path = ctx.stage_dir("08_qa")
    overlays_dir = out_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    stage1_index = ctx.stage_dir("01_pdf_pages") / "_index.json"
    page_meta: dict[int, dict[str, Any]] = {}
    if stage1_index.exists():
        try:
            page_meta = {int(k): v for k, v in json.loads(stage1_index.read_text(encoding="utf-8")).items()}
        except Exception:
            page_meta = {}

    stage2_dir = ctx.stage_dir("02_layout")
    stage3_dir = ctx.stage_dir("03_images")
    stage4_dir = ctx.stage_dir("04_tables")
    stage5_dir = ctx.stage_dir("05_question_blocks")
    stage7_dir = ctx.stage_dir("07_structured")
    stage7_5_dir = ctx.stage_dir("07_5_llm")
    pages_render_dir = ctx.stage_dir("01_pdf_pages")

    per_page_report: dict[str, dict[str, Any]] = {}
    failure_modes: dict[str, int] = {}

    # Load Stage 7.5 augmentations (may be empty if Stage 7.5 wasn't run).
    augmented_by_id = _load_augmented_questions(stage7_5_dir)
    augmented_by_page: dict[int, dict[str, dict[str, Any]]] = {}
    if augmented_by_id:
        # Group augmented entries by page_number so each page eval
        # only receives the relevant subset.
        for qid, payload in augmented_by_id.items():
            # qid format: "p{NNN}_q{kk}" → derive page number.
            try:
                pn = int(qid.split("_", 1)[0].lstrip("p"))
            except Exception:
                continue
            augmented_by_page.setdefault(pn, {})[qid] = payload

    page_iter = (
        [(p - 1, p) for p in pages]
        if pages
        else [(i, i + 1) for i in range(ctx.page_count)]
    )
    pass_count = 0
    fail_count = 0
    v2_question_scores: dict[str, dict[str, Any]] = {}
    v2_status_buckets = {"Production Ready": 0, "Needs Review": 0,
                         "Extraction Failure": 0}
    v2_axis_pass_counts = {
        "stem_complete": 0,
        "options_complete": 0,
        "answer_correct": 0,
        "explanation_complete": 0,
        "image_attached_if_referenced": 0,
        "image_placement": 0,
        "table_attached_if_referenced": 0,
        "clinical_pearl_present": 0,
        "reference_field_present": 0,
    }

    for _, page_number in page_iter:
        pmeta = page_meta.get(page_number, {})
        page_w_pt = float(pmeta.get("width_pt") or 0) or 595.3
        page_h_pt = float(pmeta.get("height_pt") or 0) or 841.9

        typed, unclass = _load_stage2_regions(stage2_dir, page_number)
        images = _load_stage3_images(stage3_dir, page_number)
        tables = _load_stage4_tables(stage4_dir, page_number)
        blocks = _load_stage5_blocks(stage5_dir, page_number)
        questions = _load_stage7_questions(stage7_dir, page_number)

        page_augmented = augmented_by_page.get(page_number)
        report = _evaluate_page(
            typed, unclass, images, tables, blocks, questions,
            augmented=page_augmented,
        )
        per_page_report[str(page_number)] = report
        for issue in report["issues"]:
            failure_modes[issue["type"]] = failure_modes.get(issue["type"], 0) + 1
        if report["status"] == "PASS":
            pass_count += 1
        else:
            fail_count += 1

        # ---- QA V2: per-question 9-axis scoring ----
        # Attach image bboxes (by id) to each question so axis 6 can
        # verify placement.  When an image appears on this page AND
        # the question has the image in its ``image_ids``, copy the
        # bbox into ``image_bboxes`` for axis 6.
        img_bbox_by_id = {iid: bb for iid, bb in images}
        for q in questions:
            iids = q.get("image_ids") or []
            q["image_bboxes"] = [img_bbox_by_id[i] for i in iids if i in img_bbox_by_id]
            score = qa_v2.score_question(q)
            v2_question_scores[q["id"]] = {
                "page_number": page_number,
                "status": score["status"],
                "passing_count": score["passing_count"],
                "total_axes": score["total_axes"],
                "failing_axes": score["failing_axes"],
                "axes": score["axes"],
            }
            v2_status_buckets[score["status"]] += 1
            for axis_name, ok in score["axes"].items():
                if ok:
                    v2_axis_pass_counts[axis_name] = v2_axis_pass_counts.get(axis_name, 0) + 1

        # Render overlay.
        page_png = pages_render_dir / f"p{page_number:03d}.png"
        overlay_path = overlays_dir / f"p{page_number:03d}.png"
        if page_png.exists():
            render_overlay(
                page_png, overlay_path,
                page_w_pt=page_w_pt, page_h_pt=page_h_pt,
                typed_regions=typed,
                unclassified_regions=unclass,
                image_bboxes=images,
                table_bboxes=tables,
                question_bboxes=[(b.get("id"), b.get("bbox", [])) for b in blocks],
            )
            res.artefacts_written += 1
        res.pages_processed += 1

    # Write per-question V2 score artefacts.
    (out_dir / "per_question_qa.json").write_text(
        json.dumps(v2_question_scores, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Write per-page report.
    (out_dir / "per_page_report.json").write_text(
        json.dumps(per_page_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {
        "pdf_filename": ctx.pdf_filename,
        "pdf_sha256_short": ctx.pdf_sha256_short,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total_pages_evaluated": len(per_page_report),
        "failure_modes": failure_modes,
        "pass_threshold": PASS_THRESHOLD,
        "max_unclassified_blocks": MAX_UNCLASSIFIED_BLOCKS,
        # QA V2 (per-question, educational-fidelity scoring)
        "v2_question_count": len(v2_question_scores),
        "v2_status_buckets": v2_status_buckets,
        "v2_axis_pass_counts": v2_axis_pass_counts,
        "v2_production_ready_pct": (
            round(100.0 * v2_status_buckets["Production Ready"]
                  / max(1, len(v2_question_scores)), 2)
        ),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    res.metrics = summary
    LOG.info(
        "stage_8_qa: %d pass / %d fail (failure modes: %s)",
        pass_count, fail_count, failure_modes,
    )
    return res


__all__ = ["run", "PASS_THRESHOLD"]
