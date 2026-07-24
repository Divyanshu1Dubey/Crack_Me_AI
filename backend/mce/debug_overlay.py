"""Debug overlay generator.

For every PDF page, render an annotated PNG that shows what the pipeline
detected, in a single image:

    green outline : typed region (stem / option / answer_key / explanation)
    yellow outline: typed region with confidence < 0.85
    red outline   : unclassified region
    magenta       : image bbox from Stage 3
    cyan          : table bbox from Stage 4
    orange        : final image-to-question mapping arrow
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


LOG = logging.getLogger("mce.debug_overlay")


# Outline colors (RGBA).
COLORS = {
    "typed":            (0, 200, 0, 255),     # green
    "typed_low":        (255, 215, 0, 255),    # yellow
    "unclassified":     (220, 20, 60, 255),    # red
    "image":            (255, 0, 255, 255),     # magenta
    "table":            (0, 200, 255, 255),     # cyan
    "mapping_arrow":    (255, 140, 0, 255),    # orange
    "question_bbox":    (0, 100, 255, 255),     # blue
}


def _bbox_to_px(bbox: Sequence[float], page_w_px: int, page_h_px: int,
               page_w_pt: float, page_h_pt: float) -> tuple[int, int, int, int]:
    sx = page_w_px / max(1.0, page_w_pt)
    sy = page_h_px / max(1.0, page_h_pt)
    return (
        max(0, int(bbox[0] * sx)),
        max(0, int(bbox[1] * sy)),
        min(page_w_px, int(bbox[2] * sx)),
        min(page_h_px, int(bbox[3] * sy)),
    )


def _try_load_font(size: int = 14):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def render_overlay(
    page_png: Path,
    out_png: Path,
    *,
    page_w_pt: float,
    page_h_pt: float,
    typed_regions: Iterable[dict[str, Any]],
    unclassified_regions: Iterable[dict[str, Any]] = (),
    image_bboxes: Iterable[tuple[str, Sequence[float]]] = (),
    table_bboxes: Iterable[tuple[str, Sequence[float]]] = (),
    question_bboxes: Iterable[tuple[str, Sequence[float]]] = (),
    mapping_arrows: Iterable[tuple[Sequence[float], Sequence[float]]] = (),
) -> Path | None:
    """Render a single annotated page PNG. Returns out_png or None on error."""
    if not page_png.exists():
        return None
    try:
        with Image.open(str(page_png)).convert("RGBA") as base:
            overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
            drw = ImageDraw.Draw(overlay)
            font = _try_load_font(14)
            page_w_px, page_h_px = base.size

            # Question bbox (blue) — drawn first so other outlines sit on top.
            for _qid, bb in question_bboxes:
                xy = _bbox_to_px(bb, page_w_px, page_h_px, page_w_pt, page_h_pt)
                drw.rectangle(xy, outline=COLORS["question_bbox"], width=4)

            # Typed regions — green or yellow.
            for r in typed_regions:
                conf = float(r.get("confidence", 1.0))
                color = COLORS["typed"] if conf >= 0.85 else COLORS["typed_low"]
                xy = _bbox_to_px(r.get("bbox", [0, 0, 0, 0]), page_w_px, page_h_px, page_w_pt, page_h_pt)
                drw.rectangle(xy, outline=color, width=2)

            # Unclassified — red.
            for r in unclassified_regions:
                xy = _bbox_to_px(r.get("bbox", [0, 0, 0, 0]), page_w_px, page_h_px, page_w_pt, page_h_pt)
                drw.rectangle(xy, outline=COLORS["unclassified"], width=2)

            # Images — magenta.
            for _iid, bb in image_bboxes:
                xy = _bbox_to_px(bb, page_w_px, page_h_px, page_w_pt, page_h_pt)
                drw.rectangle(xy, outline=COLORS["image"], width=3)

            # Tables — cyan.
            for _tid, bb in table_bboxes:
                xy = _bbox_to_px(bb, page_w_px, page_h_px, page_w_pt, page_h_pt)
                drw.rectangle(xy, outline=COLORS["table"], width=3)

            # Mapping arrows — orange.
            for from_bb, to_bb in mapping_arrows:
                fxy = _bbox_to_px(from_bb, page_w_px, page_h_px, page_w_pt, page_h_pt)
                txy = _bbox_to_px(to_bb, page_w_px, page_h_px, page_w_pt, page_h_pt)
                fx = (fxy[0] + fxy[2]) // 2
                fy = (fxy[1] + fxy[3]) // 2
                tx = (txy[0] + txy[2]) // 2
                ty = (txy[1] + txy[3]) // 2
                drw.line([(fx, fy), (tx, ty)], fill=COLORS["mapping_arrow"], width=3)
                drw.ellipse([(tx - 6, ty - 6), (tx + 6, ty + 6)],
                            fill=COLORS["mapping_arrow"])

            # Composite + save.
            composed = Image.alpha_composite(base, overlay)
            composed.convert("RGB").save(str(out_png), "PNG")
            return out_png
    except Exception as e:
        LOG.warning("render_overlay failed for %s: %s", page_png, e)
        return None


__all__ = ["render_overlay", "COLORS"]
