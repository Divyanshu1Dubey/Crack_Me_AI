"""Environment-driven configuration for the NEET PG importer."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


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
                "NEETPG_OUTPUT_DIR",
                Path(__file__).resolve().parent / "_output",
            )
        )
    )
    ocr_dpi: int = field(default_factory=lambda: _env_int("NEETPG_OCR_DPI", 200))
    ocr_lang: str = field(
        default_factory=lambda: os.environ.get("NEETPG_OCR_LANG", "eng")
    )
    batch_size: int = field(default_factory=lambda: _env_int("NEETPG_BATCH_SIZE", 500))
    min_ocr_confidence: float = field(
        default_factory=lambda: _env_float("NEETPG_MIN_OCR_CONFIDENCE", 60.0)
    )
    enable_llm_fallback: bool = field(
        default_factory=lambda: _env_bool("NEETPG_ENABLE_LLM_FALLBACK", False)
    )
    dedup_threshold: float = field(
        default_factory=lambda: _env_float("NEETPG_DEDUP_THRESHOLD", 0.92)
    )
    image_phash_threshold: int = field(
        default_factory=lambda: _env_int("NEETPG_IMAGE_PHASH_THRESHOLD", 5)
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


__all__ = ["Config", "get_config"]
