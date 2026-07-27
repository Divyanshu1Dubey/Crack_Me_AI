"""Internal helpers shared by data-cleanup migrations 0027 + 0029.

These were originally inlined inside each migration so the migration
files were self-contained. Extracting them lets unit tests import the
helpers without booting Django, while the migrations still own the
data shape (TEXT_FIELDS, etc.).
"""
from __future__ import annotations

import re

_HTML_LIST_OPEN = re.compile(r"<li[^>]*>", re.I)
_HTML_LIST_CLOSE = re.compile(r"</li>", re.I)
_HTML_BLOCK = re.compile(r"<\/?(?:p|div|h[1-6]|ul|ol|li|br)[^>]*>", re.I)
_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&apos;": "'", "&hellip;": "…",
    "&mdash;": "—", "&ndash;": "–",
    "&rsquo;": "'", "&lsquo;": "'", "&rdquo;": '"', "&ldquo;": '"',
}
_LEAK_RE = re.compile(r"\n[ \t]*[\-•\*]?[ \t]*(?:correct|incorrect)\s*$", re.I)
# Match a `<p>…</p>` whose *whole* body is the word correct/incorrect,
# modulo inline formatting tags like `<strong>`.
_FLAG_PARA_RE = re.compile(
    r"<p[^>]*>\s*(?:<[^>]+>\s*)*(?:correct|incorrect)\s*(?:<[^>]+>\s*)*</p>",
    re.I,
)


def strip_imported_html(text):
    if not text or ("<" not in text and "&" not in text):
        return text
    s = text
    s = _HTML_LIST_OPEN.sub("\n- ", s)
    s = _HTML_LIST_CLOSE.sub("\n", s)
    s = _HTML_BLOCK.sub("\n", s)
    s = _HTML_TAG.sub("", s)
    s = re.sub(
        r"&[a-z]+;|&#\d+;",
        lambda m: _HTML_ENTITIES.get(m.group(0).lower(), " "),
        s,
        flags=re.I,
    )
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def strip_leaked_correct_incorrect(text):
    if not text or not _LEAK_RE.search(text):
        return text
    return _LEAK_RE.sub("", text).rstrip()


def strip_flag_paragraphs(text):
    if not text or "<p" not in text.lower():
        return text
    cleaned = _FLAG_PARA_RE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).rstrip()
    return cleaned