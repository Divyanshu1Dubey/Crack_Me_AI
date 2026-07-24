"""Stage orchestrator base for the Medical Content Engine.

Every stage in `mce/stages/` follows the same contract:

    def run(ctx: MceContext, *, pages: list[int] | None = None) -> StageResult:

Where:

* `MceContext` carries the immutable run-wide context (PDF path, sha,
  profile, artefact root). All stages share one context.
* `pages=None` means run on every page; `pages=[38, 39]` means run only
  on those pages (used for incremental / debug runs).
* `StageResult` records what was produced, what was skipped, and any
  warnings so the CLI can build a human-readable summary.

A stage must NEVER mutate a previous stage's outputs. It only writes
into its own artefact folder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mce.profiles import ExamProfile


@dataclass
class MceContext:
    """Immutable run-wide context shared by every stage."""

    pdf_path: Path
    pdf_filename: str
    pdf_sha256: str
    pdf_sha256_short: str
    page_count: int
    profile: ExamProfile
    artefact_root: Path           # e.g. _artifacts/mce/neet_pg/2021/{sha16}/
    pdf_metadata: dict[str, Any] = field(default_factory=dict)

    def stage_dir(self, stage_name: str) -> Path:
        """Return the artefact dir for a given stage (created on first write)."""
        d = self.artefact_root / stage_name
        d.mkdir(parents=True, exist_ok=True)
        return d


@dataclass
class StageResult:
    """Per-stage result envelope. Every stage returns one."""

    stage: str
    pages_processed: int = 0
    pages_skipped: int = 0
    artefacts_written: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "pages_processed": self.pages_processed,
            "pages_skipped": self.pages_skipped,
            "artefacts_written": self.artefacts_written,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metrics": dict(self.metrics),
        }


__all__ = ["MceContext", "StageResult"]
