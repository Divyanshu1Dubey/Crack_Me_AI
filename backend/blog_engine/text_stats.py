"""Word count and reading time of a blog post, from its markdown body.

One rule for the whole site. ``BlogPost.save()`` stores ``count_words(body)``
in ``body_word_count``; the API reports it as ``word_count`` with
``reading_time`` derived from it, and the cards, the post header and
/admin/blog all show those values. The stored ``word_count`` /
``reading_time`` columns are the static seed's metadata (most claimed about
2,000 words for a ~100-word body) and are not shown anywhere.

frontend/src/lib/blogText.ts is the same algorithm, step for step, for the
static fallback posts and the editor's live count; the vectors in
``tests_blog_editor_api.py`` and ``frontend/tests/unit/blog-article.test.ts``
keep the two in step. Change both together.
"""
from __future__ import annotations

import re

#: Reading speed behind ``reading_minutes``.
WORDS_PER_MINUTE = 200
#: Posts with fewer words are flagged "thin" in /admin/blog.
THIN_POST_WORDS = 400

_STEPS = (
    (re.compile(r"\r\n?"), "\n"),
    (re.compile(r"<!--[\s\S]*?-->"), " "),                      # HTML comments
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),                  # images (alt text is not read)
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),               # links: keep the text
    (re.compile(r"<[^>\n]*>"), " "),                              # HTML tags, <autolinks>
    (re.compile(r"https?://\S+", re.IGNORECASE), " "),           # bare URLs
    (re.compile(r"\[!(?:note|tip|important|warning|caution)\]", re.IGNORECASE), " "),  # callout markers
    (re.compile(r"^[ \t]*\d{1,9}[.)](?=[ \t])", re.MULTILINE), " "),  # ordered-list numbers
    (re.compile(r"[#>*_`~|\[\]\\]"), " "),                       # markdown punctuation
)


def count_words(markdown: str | None) -> int:
    """Words a reader sees in ``markdown``: whitespace-separated tokens with a letter or a digit."""
    text = markdown or ""
    for pattern, replacement in _STEPS:
        text = pattern.sub(replacement, text)
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def reading_minutes(words: int) -> int:
    """Minutes at WORDS_PER_MINUTE, rounded half up, at least 1."""
    return max(1, int(max(0, words) / WORDS_PER_MINUTE + 0.5))


def reading_time_label(words: int) -> str:
    """'N min', what the cards and the post header show."""
    return f"{reading_minutes(words)} min"


def is_thin(words: int) -> bool:
    return words < THIN_POST_WORDS
