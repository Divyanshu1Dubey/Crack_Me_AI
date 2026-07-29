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


# ---------------------------------------------------------------------------
# Shape-B splitter: question-opener ends in '?' (not ':'), body is glued by
# '. '.  See migration 0032 for the prod case this fixes.
#
# Example input (test_real_scabies_row):
#     "Which of the following are correct in respect of scabies? "
#     "Male mite Sarcoptes scabiei are commonly transferred from an "
#     "infected person to a non-infected person. "
#     "Norwegian scabies occur in immunodeficient patients. "
#     "Permethrin cream (5%) is used for treatment. "
#     "Pruritus intensifies at night and after hot shower."
#
# Example output:
#     "Which of the following are correct in respect of scabies? "
#     "1. Male mite Sarcoptes scabiei are commonly transferred from an
#         infected person to a non-infected person.
#      2. Norwegian scabies occur in immunodeficient patients.
#      3. Permethrin cream (5%) is used for treatment.
#      4. Pruritus intensifies at night and after hot shower."

_SHAPE_B_OPENER_RE = re.compile(
    r"^(?P<head>(?:Which|what)\s+of\s+the\s+following"
    r"(?:\s+statements?)?(?:\s+(?:are|is))?"
    r"(?:\s+(?:regarding|with regard to|about|in|in respect of))?"
    r"[^?\n]*\?\s*)",
    re.I,
)

# Trailing-tail regex: matches a tail that sits AT THE END of `rest`
# (after the opener), possibly preceded by whitespace.
_SHAPE_B_TAIL_RE = re.compile(
    r"\s*Select\s+(?:the\s+)?(?:correct\s+)?answer"
    r"(?:\s+using\s+(?:the\s+)?code(?:s)?(?:\s+(?:given\s+)?below)?)?[:.]?\s*$",
    re.I,
)

# Lines that start with a single capital letter followed by '.' or ')'
# are option-prefixed rows, NOT statements (e.g. "A. Carbamazepine").
_OPTION_PREFIX_RE = re.compile(r"^\s*[A-Da-d][\.\)]\s")

# Multi-choice "which is correct" pattern — body uses option-prefixed
# paragraphs, not inlined statements. Refuse.
_OPTION_LIST_RE = re.compile(
    r"\n\s*[A-Da-d][\.\)]\s|\s[a-d]\)\s",
)

# Prefixes that mark INSTRUCTIONAL lines (tail / wrapper / question-
# type scaffolding) rather than statements.
_INSTRUCTION_PREFIXES = (
    "select the answer",
    "select the correct answer",
    "choose the correct answer",
    "choose the answer",
    "using the code",
    "using the codes",
    "codes:",
    "code:",
    "directions:",
    "direction:",
    "explanation:",
    "answer:",
    "options:",
    "list i:",
    "list ii:",
    "column i:",
    "column ii:",
    "match list",
    "match column",
    "match the following",
    "assertion",
    "reason",
)


# Inline-tail detector: matches an instructional marker that occurs
# MID-LINE — i.e. glued to a statement with possible OCR spacing
# artefacts (multiple spaces, missing space, tabs, etc.). The pattern
# captures the leading whitespace that bridges statement→tail.
#
# Examples that MUST match:
#   "Serum testosterone is low Select the correct answer using the
#    code given below:"
#   "Statement ends.  Assertion (A): foo"
#   "Statement ends.   Reason (R): bar"
#
# We deliberately anchor on the keyword + lookbehind for whitespace so
# we don't false-positive on words like "selected" or "reasoning".
_INLINE_TAIL_RE = re.compile(
    r"(?P<bridge>\s{1,})"
    r"(?:"
    r"Select\s+(?:the\s+)?(?:correct\s+|best\s+)?answer"
    r"(?:\s+using\s+(?:the\s+)?code(?:s)?(?:\s+(?:given\s+)?below)?)?[:.]?"
    r"|Choose\s+(?:the\s+)?(?:correct\s+|best\s+)?answer[:.]?"
    r"|Using\s+(?:the\s+)?code(?:s)?(?:\s+(?:given\s+)?below)?[:.]?"
    r"|Codes?\s*:"
    r"|Directions?\s*:"
    r"|Explanation\s*:"
    r"|Answer\s*:"
    r"|Options\s*:"
    r"|List\s+[IVX]+\s*:"
    r"|Column\s+[IVX]+\s*:"
    r"|Match\s+(?:the\s+following|list|column)"
    r"|Assertion\s*(?:\([AR]\))?\s*:?"
    r"|Reason\s*(?:\([AR]\))?\s*:?"
    r")",
    re.I,
)

# Threshold for auto-rewrite: 0.98 — anything below this requires
# manual review (0.80–0.97) or is skipped (<0.80).
_AUTO_REWRITE_THRESHOLD = 0.98
_REVIEW_THRESHOLD = 0.80


def _split_inline_tail(text):
    """If ``text`` contains an instructional tail glued mid-line, return
    ``(statement, tail)`` where statement is the pre-tail span (with
    trailing whitespace stripped and a final period appended if missing)
    and tail is the matched span (with leading whitespace preserved).
    Otherwise return ``(text, "")``.

    Handles OCR spacing artefacts (multiple spaces / tabs).
    """
    m = _INLINE_TAIL_RE.search(text)
    if not m:
        return text, ""
    head = text[: m.start()].rstrip()
    tail = text[m.start():]
    if not head:
        return text, ""
    if not head.rstrip().endswith((".", ":", "?", "!")):
        head = head + "."
    return head, tail


def _score_split(parts, body, head, had_trailing_tail, had_inline_tail):
    """Return confidence in [0, 1] that the rewrite is correct.

    Bands:
      >= 0.98  auto-rewrite (paragraph body + recognized tail)
      0.80–0.97 manual review (inlined body + recognized tail, or
               paragraph body without a tail)
      < 0.80   skip (no anchor for body end)

    Components:
      +0.40 canonical opener
      +0.40 trailing tail OR inline tail (one full credit)
      +0.30 paragraph-separated body
      +0.10 every statement >=15 chars, ends with '.'
      +0.05 head + body whitespace consistent (no double-newline)
      -0.20 avg length <20 (borderline)
      -0.10 body contains OCR mojibake

    Cap at 1.0, floor at 0.0.
    """
    score = 0.0
    score += 0.40
    if had_trailing_tail or had_inline_tail:
        score += 0.40
    if "\n" in body:
        score += 0.30
    avg_len = sum(len(p) for p in parts) / max(len(parts), 1)
    canonical = [p.rstrip(".") + "." for p in parts]
    if all(len(c) >= _MIN_AVG_LEN and c.rstrip().endswith((".", ":", "?", "!")) for c in canonical):
        score += 0.10
    if "\n\n" not in body:
        score += 0.05
    if avg_len < 20:
        score -= 0.20
    mojibake = re.compile(r"[╬▓▒░├┤┐└┴┬├─┼╞╟╚╔╩╦╠═╬╧╨╤╥╙╘╒╓╫╪┘┌]")
    if mojibake.search(body):
        score -= 0.10
    return max(0.0, min(1.0, score))


def split_space_joined_stems(text):
    """Return ``text`` rewritten as a numbered list, or ``text`` unchanged
    if it doesn't match the Shape-B pattern.

    Idempotent: re-running yields zero touches.

    Confidence gating
    -----------------
    Each rewrite is given a confidence score in [0, 1]:

      * **>= 0.98** — safe to rewrite automatically.
      * **0.80 – 0.97** — manual review queue.
      * **< 0.80** — skip.

    Currently the function returns the rewritten text only when the
    confidence is >= _AUTO_REWRITE_THRESHOLD; below that it returns
    the original text. Callers that need the manual-review bucket
    should call ``score_space_joined_stems``.
    """
    if not text or _is_already_structured(text):
        return text

    m = _SHAPE_B_OPENER_RE.match(text)
    if not m:
        return text
    head = m.group("head")
    rest = text[m.end():]

    # Refuse if the body already has option-prefixed rows.
    if _OPTION_LIST_RE.search(rest):
        return text

    # Strip a recognisable trailing tail if present.
    tail_m = _SHAPE_B_TAIL_RE.search(rest)
    body = rest if not tail_m else rest[: tail_m.start()]
    trailing_tail = "" if not tail_m else rest[tail_m.start():]

    # Refuse if the body is already paragraph-broken (\\n\\n between
    # sentences). Only the truly inlined shape needs help.
    if "\n\n" in body:
        return text

    # Split body into parts (paragraph or inlined).
    if "\n" in body:
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        if len(lines) >= 3:
            parts = lines
        else:
            parts = re.split(r"\.\s+(?=[A-Z])", body.strip())
            parts = [p.strip() for p in parts if p.strip()]
    else:
        parts = re.split(r"\.\s+(?=[A-Z])", body.strip())
        parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < 3:
        return text

    # Inline-tail pass: peel any instructional tail that's glued onto a
    # statement. The first inline-tail match wins — anything after it
    # is part of the tail.
    inline_tails = []
    for i, p in enumerate(parts):
        new_p, inline_tail = _split_inline_tail(p)
        if inline_tail:
            inline_tails.append(inline_tail)
            parts[i] = new_p
            # Any further parts (i+1..N) were absorbed by the tail.
            dropped = parts[i + 1:]
            parts = parts[: i + 1]
            if dropped:
                # If the dropped parts look like real statements (not
                # tail debris), we'd be losing content — refuse rather
                # than silently drop them.
                if any(len(d) >= _MIN_AVG_LEN and not d.lower().startswith(_INSTRUCTION_PREFIXES) for d in dropped):
                    return text
            break

    # Re-validate: every part must be a non-empty statement, no
    # instruction prefix.
    cleaned_parts = []
    for p in parts:
        if not p or not p.strip():
            return text
        stripped = p.strip()
        if any(stripped.lower().startswith(prefix) for prefix in _INSTRUCTION_PREFIXES):
            return text
        cleaned_parts.append(stripped)
    parts = cleaned_parts
    if len(parts) < 3:
        return text
    avg_len = sum(len(p) for p in parts) / len(parts)
    if avg_len < _MIN_AVG_LEN:
        return text

    # Tail-leak guard (belt and braces). If any numbered statement still
    # starts with an instruction prefix, refuse.
    for p in parts:
        if any(p.lower().startswith(prefix) for prefix in _INSTRUCTION_PREFIXES):
            return text

    # Confidence score.
    score = _score_split(
        parts,
        body,
        head,
        had_trailing_tail=bool(trailing_tail),
        had_inline_tail=bool(inline_tails),
    )
    if score < _AUTO_REWRITE_THRESHOLD:
        return text

    numbered = "\n".join(f"{i+1}. {p.rstrip('.')}." for i, p in enumerate(parts))
    full_tail = trailing_tail
    if inline_tails:
        full_tail = ("".join(inline_tails) + trailing_tail) if trailing_tail else "".join(inline_tails)
    # Strip leading whitespace from full_tail so we can decide on
    # formatting, then put it on its own line.
    if full_tail:
        tail_clean = full_tail.lstrip()
        return f"{head}\n{numbered}\n{tail_clean}"
    return f"{head}\n{numbered}"


def score_space_joined_stems(text):
    """Return ``(confidence, rewrite|None)``. The rewrite is None when
    the splitter refused (idempotent: re-running yields zero touches)
    OR when the confidence is below the auto-rewrite threshold (caller
    decides whether to queue the row for manual review).

    Confidence bands:
      >= 0.98  safe to rewrite automatically
      0.80–0.97 manual review queue
      < 0.80   skip
    """
    if not text or _is_already_structured(text):
        return 0.0, None
    m = _SHAPE_B_OPENER_RE.match(text)
    if not m:
        return 0.0, None
    head = m.group("head")
    rest = text[m.end():]
    if _OPTION_LIST_RE.search(rest):
        return 0.0, None
    tail_m = _SHAPE_B_TAIL_RE.search(rest)
    body = rest if not tail_m else rest[: tail_m.start()]
    trailing_tail = "" if not tail_m else rest[tail_m.start():]
    if "\n\n" in body:
        return 0.0, None
    if "\n" in body:
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        parts = lines if len(lines) >= 3 else re.split(r"\.\s+(?=[A-Z])", body.strip())
        parts = [p.strip() for p in parts if p.strip()]
    else:
        parts = re.split(r"\.\s+(?=[A-Z])", body.strip())
        parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < 3:
        return 0.0, None
    inline_tails = []
    for i, p in enumerate(parts):
        new_p, inline_tail = _split_inline_tail(p)
        if inline_tail:
            inline_tails.append(inline_tail)
            parts[i] = new_p
            dropped = parts[i + 1:]
            parts = parts[: i + 1]
            if any(len(d) >= _MIN_AVG_LEN and not d.lower().startswith(_INSTRUCTION_PREFIXES) for d in dropped):
                return 0.0, None
            break
    cleaned = []
    for p in parts:
        if not p or not p.strip():
            return 0.0, None
        s = p.strip()
        if any(s.lower().startswith(prefix) for prefix in _INSTRUCTION_PREFIXES):
            return 0.0, None
        cleaned.append(s)
    parts = cleaned
    if len(parts) < 3:
        return 0.0, None
    avg_len = sum(len(p) for p in parts) / len(parts)
    if avg_len < _MIN_AVG_LEN:
        return 0.0, None
    for p in parts:
        if any(p.lower().startswith(prefix) for prefix in _INSTRUCTION_PREFIXES):
            return 0.0, None
    score = _score_split(
        parts,
        body,
        head,
        had_trailing_tail=bool(trailing_tail),
        had_inline_tail=bool(inline_tails),
    )
    rewrite = None
    # REVIEW band also produces a rewrite — caller decides whether to
    # auto-apply (>= AUTO_REWRITE_THRESHOLD) or queue for human review.
    if score >= _REVIEW_THRESHOLD:
        numbered = "\n".join(f"{i+1}. {p.rstrip('.')}." for i, p in enumerate(parts))
        full_tail = trailing_tail
        if inline_tails:
            full_tail = ("".join(inline_tails) + trailing_tail) if trailing_tail else "".join(inline_tails)
        if full_tail:
            tail_clean = full_tail.lstrip()
            rewrite = f"{head}\n{numbered}\n{tail_clean}"
        else:
            rewrite = f"{head}\n{numbered}"
    return score, rewrite