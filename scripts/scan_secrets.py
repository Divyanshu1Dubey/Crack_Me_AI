#!/usr/bin/env python3
"""Lightweight secret scanner for pre-commit.

Scans staged text files passed by pre-commit and blocks commits when likely
credential patterns are detected.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenRouter key", re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}")),
    ("ElevenLabs key", re.compile(r"sk_[A-Za-z0-9]{20,}")),
    ("Groq key", re.compile(r"gsk_[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("Gemini key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Cerebras key", re.compile(r"csk-[A-Za-z0-9]{20,}")),
    ("HuggingFace key", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    ("Together key", re.compile(r"tgp_v1_[A-Za-z0-9_-]{20,}")),
]

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".ico",
    ".woff",
    ".woff2",
}


def _mask(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    if not path.exists() or not path.is_file():
        return []
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return []
    if _is_binary(path):
        return []

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS:
            for match in pattern.finditer(line):
                token = match.group(0)
                findings.append((line_number, label, _mask(token)))
    return findings


def main() -> int:
    paths = [Path(arg) for arg in sys.argv[1:] if arg and not arg.startswith("-")]
    if not paths:
        return 0

    all_findings: list[tuple[Path, int, str, str]] = []
    for path in paths:
        for line_no, label, masked in _scan_file(path):
            all_findings.append((path, line_no, label, masked))

    if not all_findings:
        return 0

    print("Secret scan failed. Potential credentials detected:")
    for path, line_no, label, masked in all_findings:
        print(f"  - {path}:{line_no} [{label}] {masked}")

    print("\nMove secrets to environment variables and rotate exposed credentials before committing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
