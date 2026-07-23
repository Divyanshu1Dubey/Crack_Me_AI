"""Environment-driven configuration for the INI-CET importer.

Mirrors `backend.importers.neetpg.config` but writes output under
`backend/importers/inicet/_output` and is tagged with `exam_type = ini_cet`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


# Stable identifiers used by db_writer and management command.
EXAM_TYPE = "ini_cet"
EXAM_SOURCE = "INI-CET (recall)"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    output_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get(
                "INICET_OUTPUT_DIR",
                Path(__file__).resolve().parent / "_output",
            )
        )
    )
    ocr_dpi: int = field(default_factory=lambda: _env_int("INICET_OCR_DPI", 200))
    ocr_lang: str = field(
        default_factory=lambda: os.environ.get("INICET_OCR_LANG", "eng")
    )
    # Smaller batch (vs neetpg=500) to avoid OOM on the 20-30 MB image-rich INI-CET PDFs.
    batch_size: int = field(default_factory=lambda: _env_int("INICET_BATCH_SIZE", 50))
    min_ocr_confidence: float = field(
        default_factory=lambda: _env_float("INICET_MIN_OCR_CONFIDENCE", 60.0)
    )
    enable_llm_fallback: bool = field(
        default_factory=lambda: _env_bool("INICET_ENABLE_LLM_FALLBACK", False)
    )
    dedup_threshold: float = field(
        default_factory=lambda: _env_float("INICET_DEDUP_THRESHOLD", 0.92)
    )
    image_phash_threshold: int = field(
        default_factory=lambda: _env_int("INICET_IMAGE_PHASH_THRESHOLD", 5)
    )

    # ------------------------------------------------------------------ paths

    @property
    def raw_dir(self) -> Path:
        return self.output_dir / "raw"

    @property
    def pages_dir(self) -> Path:
        return self.output_dir / "pages"

    @property
    def images_dir(self) -> Path:
        return self.output_dir / "images"

    @property
    def parsed_dir(self) -> Path:
        return self.output_dir / "parsed"

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "manifest.json"

    # ------------------------------------------------------------------ ensure

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.raw_dir, self.pages_dir,
                  self.images_dir, self.parsed_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


def get_config() -> Config:
    cfg = Config()
    cfg.ensure_dirs()
    return cfg


__all__ = ["Config", "get_config", "EXAM_TYPE", "EXAM_SOURCE"]