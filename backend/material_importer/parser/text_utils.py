"""Small text normalizers shared by every extractor.

Keep this dependency-free so it stays cheap and easy to test.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable

# Strip zero-width / BOM / soft-hyphen characters common in copied MS-Word text.
_INVISIBLE_RE = re.compile(r"[​‌‍⁠﻿­]")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_LEADING_WS_RE = re.compile(r"^[ \t]+", re.MULTILINE)


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = _INVISIBLE_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Remove spaces around newlines but keep the newline.
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    s = _TRAILING_WS_RE.sub("", s)
    s = _LEADING_WS_RE.sub("", s)
    s = _MULTI_NL_RE.sub("\n\n", s)
    s = _MULTI_SPACE_RE.sub(" ", s)
    return s.strip()


def content_hash(*parts: str) -> str:
    """Stable 64-bit-ish hash for duplicate detection."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.strip().lower().encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()[:64]


_OPTION_HEADER_RE = re.compile(r"^\s*\(?([A-Da-d])\)?[\.\):\-]\s+(.*)$")
_ROMAN_RE = re.compile(r"^\s*([IVX]+)\.?\s+(.*)$")


def split_option_line(line: str) -> tuple[str, str] | None:
    """Return (letter, text) if line looks like 'A. ...' / 'A) ...' / '(A) ...'."""
    if not line:
        return None
    m = _OPTION_HEADER_RE.match(line)
    if m:
        letter = m.group(1).upper()
        return letter, m.group(2).strip()
    return None


def is_likely_question_start(line: str) -> bool:
    """Heuristic for start of a new MCQ in flat text: 'Q1.', '1.', 'Q.1', 'Question 5'."""
    if not line:
        return False
    l = line.strip()
    if l.lower().startswith(("question ", "q.", "q-")):
        return True
    if re.match(r"^Q\s*\d+[\.\):]", l, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d+\.\s+[A-Z]", l) and len(l) > 12:
        return True
    return False


def extract_year_hint(text: str) -> int | None:
    """Look for a 4-digit year (PYQ year, etc.). 1990–2030 only."""
    if not text:
        return None
    for y in re.findall(r"\b(19[9]\d|20[0-3]\d)\b", text):
        yi = int(y)
        if 1990 <= yi <= 2030:
            return yi
    return None


def flatten_paragraphs(paragraphs: Iterable[str]) -> list[str]:
    """Drop empties, apply clean_text, keep order."""
    return [clean_text(p) for p in paragraphs if p and p.strip()]
