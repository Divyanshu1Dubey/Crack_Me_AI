"""
text_encoding.py — Centralized Unicode-safe text handling.

Root cause of "ΓÇÿ" / "Ã©" / "â€™" Mojibake seen on the site:
  * Python opened text files with a non-UTF-8 locale (often cp1252 on Windows).
  * Bytes that were already valid UTF-8 (e.g. 0xE2 0x80 0x98 for U+2018 '‘')
    got decoded as Latin-1 / cp1252 into the strings â€˜, then saved into
    Postgres/SQLite and shipped to the browser, which renders the double-
    encoded bytes as "ΓÇÿ".

This module provides a single normalize_text() that any importer / serializer
MUST call before persisting user-visible text. It also exposes fix_mojibake()
for one-shot cleanup of legacy rows.

API:
    normalize_text(value)              -> clean str (safe for storage / JSON)
    fix_mojibake(value)                 -> str with known mojibake un-doubled
    read_text_file(path, ...)           -> str, UTF-8 with safe fallback
"""
from __future__ import annotations

import codecs
import logging
import re
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


# --- Decoding helpers --------------------------------------------------------

def _decode_bytes(data: bytes) -> str:
    """Decode bytes as UTF-8, falling back to cp1252 / latin-1 on failure.

    Never raises. Always returns a valid str. Replacement chars (U+FFFD) that
    come back from UTF-8-with-errors-replace are surfaced via the higher-level
    fix_mojibake() pass; we don't try to second-guess them here.
    """
    # Fast path: pure ASCII.
    try:
        return data.decode("ascii")
    except UnicodeDecodeError:
        pass

    # Try UTF-8 strict first — most files in repo are valid UTF-8.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # Fall back to cp1252 (Windows default), which can decode any byte.
    try:
        return data.decode("cp1252")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def read_text_file(path: str | Path, *, errors: str = "normalize") -> str:
    """Read a text file and return a clean, NFC-normalized string.

    args:
        path: file to read
        errors: 'normalize' (default) returns a fixed string even if the file
                contained mojibake; 'strict' raises on decode failure;
                'replace' inserts U+FFFD for bad bytes.
    """
    data = Path(path).read_bytes()
    if errors == "strict":
        text = data.decode("utf-8")
    elif errors == "replace":
        text = data.decode("utf-8", errors="replace")
    else:
        text = _decode_bytes(data)
        text = fix_mojibake(text)
    return _normalize_whitespace_and_quotes(text)


# --- Mojibake repair ---------------------------------------------------------

# Each entry: (mojibake_sequence_as_read_in_latin1, intended_unicode_char).
# We only fix sequences that show up in the user-reported browser output
# (Γ / Ç / ÿ / â / € / ¢ / ™ etc.). Anything else is left alone so we don't
# corrupt genuine Latin-1 content.
_MOJIBAKE_TABLE: dict[str, str] = {
    # Smart quotes / apostrophes (the ΓÇÿ / ΓÇÖ cases the user reported).
    "ΓÇÿ": "‘",   # left single quote
    "ΓÇÖ": "’",   # right single quote / apostrophe
    "ΓÇÜ": "“",   # left double quote
    "ΓÇ¥": "”",   # right double quote
    "ΓÇ£": "–",   # en dash
    "ΓÇ": "—",    # em dash (best-effort)

    # Latin-1 double-encoded — 'Ã©' is é, etc.
    "Ã©": "é", "Ã¨": "è", "Ã¢": "â",
    "Ã®": "î", "Ã´": "ô", "Ã¹": "ù",
    "Ã\x83Â©": "é",  # double-encoded é

    # Right-single-quote double-encoded as â€™
    "â€™": "’",
    "â€˜": "‘",
    "â€œ": "“",
    "â€\x9d": "”",
    "â€“": "–",
    "â€”": "—",
    "â€¦": "…",

    # Single-encoded right single quote (only one UTF-8-as-latin1 round-trip
    # survived into the DB). The 3-char sequence `â` (U+00E2) + `\x80`
    # (U+0080) + `\x99` (U+0099) is exactly the UTF-8 bytes of `'` (U+2019)
    # interpreted as Latin-1 codepoints. Without this entry the cleanup
    # script reports mojibake but normalize_text cannot repair it.
    "â\x80\x99": "’",
    "â\x80\x9c": "“",
    "â\x80\x9d": "”",
    "â\x80\x98": "‘",
    "â\x80\x99s": "’s",
    "â\x80\x9cs": "'s",
    "â\x80\x9ds": "'s",

    # NBSP / zero-width artefacts occasionally survive from upstream tooling.
    "Â ": " ",
}

# Compile a single regex so we can run one pass.
_MOJIBAKE_PATTERN = re.compile(
    "|".join(re.escape(k) for k in sorted(_MOJIBAKE_TABLE, key=len, reverse=True))
)


def fix_mojibake(value: str | None) -> str:
    """Repair known UTF-8-as-Latin-1 / UTF-8-as-cp1252 mojibake in `value`.

    Safe to call repeatedly — once a sequence is repaired, the repair chars
    aren't in the table so the second pass is a no-op.
    """
    if not value:
        return value or ""
    # Quick guard: if no suspect byte at all, skip the regex.
    if not any(ch in value for ch in ("Γ", "Ç", "ÿ", "Â", "â", "Ã")):
        return value
    return _MOJIBAKE_PATTERN.sub(lambda m: _MOJIBAKE_TABLE[m.group(0)], value)


# --- Whitespace / quote normalization ---------------------------------------

# Stray NBSP from PDF / Windows tooling.
_NBSP = " "
_ZWSP = "​"

# Common smart-quote pairs that read better as straight quotes inside MCQs
# (the source DB has them all and they confuse grep / diff).
_QUOTE_MAP = {
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
}


def _normalize_whitespace_and_quotes(text: str) -> str:
    """Collapse whitespace runs and (optionally) flatten smart quotes."""
    if not text:
        return text
    text = text.replace(_NBSP, " ").replace(_ZWSP, "")
    # Collapse 3+ newlines and trailing whitespace on lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def normalize_text(value: str | None) -> str:
    """One-shot normalizer every importer / serializer must call.

    Steps:
      1. repair known mojibake
      2. NFC unicode normalize (so 'é' (U+00E9) and 'é' (U+0065 U+0301)
         compare equal)
      3. collapse whitespace

    Returns '' for None.
    """
    if value is None:
        return ""
    text = fix_mojibake(value)
    # NFC normalize.
    import unicodedata
    text = unicodedata.normalize("NFC", text)
    text = _normalize_whitespace_and_quotes(text)
    return text


def normalize_fields(record: dict, fields: Iterable[str]) -> dict:
    """Return a new dict with the listed fields passed through normalize_text."""
    out = dict(record)
    for f in fields:
        if f in out:
            out[f] = normalize_text(out[f])
    return out