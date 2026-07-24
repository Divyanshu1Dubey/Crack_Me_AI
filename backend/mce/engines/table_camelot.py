"""Camelot TableEngine — production implementation.

Camelot 0.11+ is the best open-source table extractor for NEET-PG-style
PDFs. It has two flavours:

* ``lattice`` — for bordered tables (drug charts, classification boxes
  with visible lines). Requires explicit row/column separators.
* ``stream`` — for borderless tables (flow charts laid out in a grid
  by whitespace).

We try lattice first, then stream. Tables that come back empty fall
through to the heuristic fallback (whitespace column detection).

Safety net: if Camelot is not installed, the engine returns ``[]`` and
``is_available() == False`` — Stage 4 will skip table extraction for
that run.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

LOG = logging.getLogger("mce.table_camelot")


# ----------------------------------------------------------------- optional deps

try:
    import camelot  # type: ignore
    _HAS_CAMELOT = True
except Exception:  # pragma: no cover
    camelot = None  # type: ignore
    _HAS_CAMELOT = False

# Camelot depends on `ghostscript` for lattice mode on some platforms.
# Probe via subprocess so we fail gracefully.
_GS_BIN: str | None = None

# Common Windows install locations for the Ghostscript binary.  Camelot's
# lattice parser shells out to ``gswin64c`` (or ``gs`` on POSIX) so the
# binary must be discoverable via PATH or one of these well-known paths.
_GS_FALLBACK_PATHS = [
    r"C:\Ghostscript\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.07.1\bin\gswin64c.exe",
    r"C:\Program Files\gs\gs10.07.0\bin\gswin64c.exe",
    r"C:\Program Files (x86)\gs\gs10.07.1\bin\gswin32c.exe",
]


def _find_ghostscript() -> str | None:
    """Locate the Ghostscript binary on PATH or at common Windows paths.

    Caches the result in module state.  Returns ``None`` if not found.
    """
    global _GS_BIN
    if _GS_BIN is not None:
        return _GS_BIN or None
    from shutil import which
    found = None
    for name in ("gswin64c", "gswin32c", "gs"):
        path = which(name)
        if path:
            found = path
            break
    if not found:
        for cand in _GS_FALLBACK_PATHS:
            if Path(cand).exists():
                found = cand
                break
    if found:
        # Make Camelot's internal subprocess invocations see it too:
        gs_dir = str(Path(found).parent)
        current = os.environ.get("PATH", "")
        if gs_dir.lower() not in current.lower():
            os.environ["PATH"] = gs_dir + os.pathsep + current
    _GS_BIN = found or ""
    return _GS_BIN or None


# ----------------------------------------------------------------- engine


class CamelotTableEngine:
    name = "table_camelot"

    def is_available(self) -> bool:
        if not _HAS_CAMELOT:
            return False
        # Camelot needs ghostscript for lattice mode; if it's missing
        # we still return True and let extract() pick stream-only mode.
        return True

    # ---------------------------------------------------------------- API

    def extract(  # noqa: ARG002 - Protocol params kept for Stage 4 compatibility
        self,
        *,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
        lines,
    ) -> list[dict[str, Any]]:
        """Try lattice, then stream. Return list of dict-shaped table blocks.

        Each block:
            {
              "type":     "table" | "algorithm" | "flowchart" | "drug_chart",
              "bbox":     [x0,y0,x1,y1],
              "cells":    [[str, ...], ...],
              "preview_png": str | None,
              "confidence": float,
              "method":   "lattice" | "stream",
            }

        Camelot requires a real PDF path (not a PNG), so we open the
        original PDF (callers pass the page number). The ``page_png_path``
        is used for the preview crop only.
        """
        if not self.is_available():
            return []

        # Locate the PDF — the engine API contract doesn't carry the PDF
        # path, so we walk up from page_png_path to find an `_artefacts`
        # parent that knows the source. The simplest stable lookup: the
        # page_png_path sits inside ``<artefact_root>/01_pdf_pages/``;
        # the MceContext exposes ``artefact_root`` but not from here.
        # We require the caller to have set MCE_PDF_PATH in the env, or
        # we accept that the engine can't run without it.
        pdf_path = os.environ.get("MCE_PDF_PATH")
        if not pdf_path or not Path(pdf_path).exists():
            LOG.debug("Camelot engine: MCE_PDF_PATH not set / missing — skipping")
            return []

        out: list[dict[str, Any]] = []
        out.extend(self._try_lattice(pdf_path, page_number, page_png_path, page_width_pt, page_height_pt))
        if not out:
            out.extend(self._try_stream(pdf_path, page_number, page_png_path, page_width_pt, page_height_pt))
        return out

    # ---------------------------------------------------------------- helpers

    def _try_lattice(  # noqa: ARG002
        self,
        pdf_path: str,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
    ) -> list[dict[str, Any]]:
        if not _find_ghostscript():
            LOG.debug("Camelot lattice: ghostscript not found, falling back to stream")
            return []
        try:
            tables = camelot.read_pdf(  # type: ignore[attr-defined]
                pdf_path,
                pages=str(page_number),
                flavor="lattice",
                suppress_stdout=True,
            )
        except Exception as e:
            LOG.debug("Camelot lattice failed: %s", e)
            return []
        return [self._camelot_table_to_dict(t, page_png_path, method="lattice")
                for t in tables if t and len(t.df) >= 2]

    def _try_stream(  # noqa: ARG002
        self,
        pdf_path: str,
        page_number: int,
        page_png_path: Path,
        page_width_pt: float,
        page_height_pt: float,
    ) -> list[dict[str, Any]]:
        try:
            tables = camelot.read_pdf(  # type: ignore[attr-defined]
                pdf_path,
                pages=str(page_number),
                flavor="stream",
                suppress_stdout=True,
            )
        except Exception as e:
            LOG.debug("Camelot stream failed: %s", e)
            return []
        return [self._camelot_table_to_dict(t, page_png_path, method="stream")
                for t in tables if t and len(t.df) >= 2]

    @staticmethod
    def _camelot_table_to_dict(t, page_png_path: Path, *, method: str) -> dict[str, Any]:  # noqa: ARG004
        # Camelot's cells: t.df is a pandas DataFrame; convert to list of lists.
        cells = [[str(c) if c is not None else "" for c in row] for row in t.df.values.tolist()]
        # bbox in PDF points.
        try:
            x0, y0, x1, y1 = float(t._bbox[0]), float(t._bbox[1]), float(t._bbox[2]), float(t._bbox[3])
        except Exception:
            x0 = y0 = x1 = y1 = 0.0
        confidence = float(getattr(t, "accuracy", 0.0)) or 0.7
        return {
            "type": "table",
            "bbox": [x0, y0, x1, y1],
            "cells": cells,
            "preview_png": None,           # Stage 4 will crop
            "confidence": confidence,
            "method": method,
        }


__all__ = ["CamelotTableEngine"]
