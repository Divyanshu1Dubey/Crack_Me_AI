"""Atomic JSONL writers + manifest manager.

All output is written via `_atomic_write()` so a crash mid-run never
leaves a half-written file. The manifest tracks per-source progress so
the runner can resume safely.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    n = 0
    buf = []
    for row in rows:
        buf.append(json.dumps(row, ensure_ascii=False))
        n += 1
        if len(buf) >= 500:
            _atomic_write(path, "\n".join(buf) + "\n")
            buf = []
    if buf:
        _atomic_write(path, "\n".join(buf) + "\n")
    return n


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------- manifest

def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "runs": []}


def save_manifest(path: Path, manifest: dict) -> None:
    _atomic_write(path, json.dumps(manifest, indent=2, ensure_ascii=False))


def is_source_processed(manifest: dict, sha16: str) -> bool:
    for run in manifest.get("runs", []):
        for entry in run.get("processed", []):
            if entry.get("sha256_short") == sha16:
                return True
    return False


__all__ = [
    "write_jsonl",
    "append_jsonl",
    "load_manifest",
    "save_manifest",
    "is_source_processed",
]