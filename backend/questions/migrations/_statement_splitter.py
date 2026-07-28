"""Statement-list splitter for inlined multi-statement question_text.

Some importer paths (e.g. an older NEET PG ingest) store the question
text as a colon-separated stem followed by several statements joined
end-to-end on a single line:

    Consider the following statements with regard to respiratory
    examination:
    Change in note, when patient phonates "EEE" (Egophony) is
    characteristic of interstitial fibrosis
    Whispered pectoriloquy is characteristic of lung consolidation
    Monophonic wheeze is characteristic of asthma
    Hyper-resonant note on percussion is characteristic of pneumothorax
    Which of the above statements are correct?

That renders on the question-bank card as one mashed paragraph with no
list structure — looks ugly and is hard to read.

`split_inlined_statements()` rewrites this into a numbered list:

    Consider the following statements with regard to respiratory
    examination:
    1. Change in note, when patient phonates "EEE" (Egophony) is
       characteristic of interstitial fibrosis.
    2. Whispered pectoriloquy is characteristic of lung consolidation.
    3. Monophonic wheeze is characteristic of asthma.
    4. Hyper-resonant note on percussion is characteristic of
       pneumothorax.
    Which of the above statements are correct?

Strict safety rules (any failure means the row is left untouched):

  * The text must NOT already have ``\\n- …`` or ``\\n1. …`` or
    ``\\nI. …`` list markers.
  * The opener must match a recognised "Consider the following … :"
    pattern.
  * The tail must end with one of the recognised closing phrases
    ("Which of the above statements are correct?", "Select the
    correct answer …", "Which of the statements given above are
    correct?", …).
  * The body must contain at least 2 statements.
  * Average statement length must be >= 15 chars (filters false-
    positive splits on acronym lists like "Insulin Islet amyloid
    polypeptide or amylin Glucagon Somatostatin" where the splitter
    would chop nouns).
"""
from __future__ import annotations

import re

# Hard guard: rows that already have these markers are never touched.
_ALREADY_STRUCTURED = [
    re.compile(r"\n\s*[-•*]\s"),
    re.compile(r"\n\s*\d+[\.\)]\s"),
    re.compile(r"\n\s*[IVX]+[\.\)]\s"),
]

# Recognised openers — "Consider the following … : <body>". The opener
# must end with `:` and a space; everything after is the body.
_OPENERS = [
    r"Consider the following(?:[^:\n])*?:\s*",
    r"Consider the following about(?:[^:\n])*?:\s*",
    r"Consider the following in(?:[^:\n])*?:\s*",
    r"Consider the following in respect of(?:[^:\n])*?:\s*",
    r"Consider the following statements? (?:regarding|with regard to|about|in)\s+(?:[^:\n])*?:\s*",
    r"Which of the following(?: statements?)? (?:are|is)(?:[^:\n])*?:\s*",
    r"Match the following(?:[^:\n])*?:\s*",
]

# Recognised tails — what the body is followed by. The tail is preserved
# verbatim (with leading whitespace) in the output.
_TAILS = [
    r"\s*Which of the (?:above|statements?)(?:[^?\n])*\??",
    r"\s*Select the correct(?:[^.\n]*)",
    r"\s*Which are correct\??",
]

# Average-statement-length floor (chars). Filters false-positive splits
# on noun lists where statements would be 1-2 words.
_MIN_AVG_LEN = 15


def _is_already_structured(s: str) -> bool:
    return any(p.search(s) for p in _ALREADY_STRUCTURED)


def _split_body_into_statements(body: str) -> list[str]:
    """Split a body that may use either ``\\n`` separators or inlined
    sentences joined by ``. `` into a list of statement strings.

    Whichever shape the body has, we return the list of statements.
    """
    body = body.strip()
    # First try the "each statement on its own line" shape — splitter
    # is simpler and more accurate.
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if len(lines) >= 2:
        return lines
    # Otherwise split on `. ` followed by an uppercase letter.
    parts = re.split(r"\.\s+(?=[A-Z])", body)
    return [p.strip() for p in parts if p.strip()]


def split_inlined_statements(text: str) -> str:
    """Return ``text`` rewritten as a numbered list, or ``text`` unchanged
    if it doesn't match the safe Shape-A pattern.

    Idempotent: calling twice on already-clean text returns the same
    string.
    """
    if not text or _is_already_structured(text):
        return text

    for opener_re in _OPENERS:
        m = re.match(opener_re, text, re.S | re.I)
        if not m:
            continue
        head = text[: m.end()]
        rest = text[m.end():]
        for tail_re in _TAILS:
            tm = re.search(tail_re + r"\s*$", rest, re.S | re.I)
            if not tm:
                continue
            body = rest[: tm.start()]
            tail = rest[tm.start():]
            statements = _split_body_into_statements(body)
            if len(statements) < 2:
                continue
            avg_len = sum(len(s) for s in statements) / len(statements)
            if avg_len < _MIN_AVG_LEN:
                continue
            numbered = "\n".join(
                f"{i+1}. {s.rstrip('.')}." for i, s in enumerate(statements)
            )
            return f"{head}{numbered}{tail}"
    return text