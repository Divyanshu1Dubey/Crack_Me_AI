"""Answer-key detector.

Many PDFs bundle the answer key as a separate trailing section. This
module locates that section and returns a `{question_number: [labels]}`
map. Inline answers detected by `text_parser.ANSWER_LINE` are already
captured on the question itself.
"""
from __future__ import annotations

import re
from typing import Optional

ANSWER_KEY_HEADER = re.compile(
    r"(?:answer\s*key|correct\s*answers|key\s*to\s*(?:the\s*)?questions?)",
    re.IGNORECASE,
)

ANSWER_LINE_NUMBERED = re.compile(
    r"^\s*(\d{1,4})\s*[\.\)\:]\s*\(?([A-Fa-f](?:\s*[,/&+\s]\s*[A-Fa-f])*)\)?\s*$",
    re.MULTILINE,
)


def extract_answer_key(text: str) -> tuple[Optional[int], dict[int, list[str]]]:
    """Return (start_index, {question_number: [labels]}).

    `start_index` is the offset into `text` where the answer key section
    begins, or None when no key section was found.
    """
    m = ANSWER_KEY_HEADER.search(text)
    if not m:
        return None, {}
    start = m.end()
    matches = list(ANSWER_LINE_NUMBERED.finditer(text, start))
    key: dict[int, list[str]] = {}
    for mm in matches:
        try:
            qno = int(mm.group(1))
        except ValueError:
            continue
        labels = sorted({c.upper() for c in re.findall(r"[A-Fa-f]", mm.group(2))})
        if labels:
            key[qno] = labels
    return start, key


def merge_inline_with_key(
    inline: dict[int, list[str]],
    key: dict[int, list[str]],
) -> dict[int, list[str]]:
    """Prefer inline answers; fall back to key answers when missing."""
    out = dict(key)
    for qno, labels in inline.items():
        out[qno] = labels
    return out


__all__ = ["ANSWER_KEY_HEADER", "extract_answer_key", "merge_inline_with_key"]