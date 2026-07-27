"""
One-shot cleanup: strip raw HTML tags (& entities) from Question text
fields that were stored verbatim by an older mocktest importer.

Root cause: the docx parser occasionally passed python-docx's rich-text
serialization (<p>…</p>, &nbsp;, <strong>, <ul><li>, <span style=…>)
straight into question_text / option_a..d / explanation. The frontend uses
ReactMarkdown which expects MARKDOWN, not HTML — so <p>, &nbsp; etc. leaked
into the UI as literal characters.

Heuristics applied (lightweight, no lxml):
  - Decode named entities (&nbsp; → space, &amp; → &, &lt; → <, etc.).
  - Replace block-level closers (<p>, </p>, <br>, <br/>) with newlines.
  - Replace list closers (</ul>, </ol>, </li>) with newlines; replace
    <li>…</li> with "- …" (markdown bullet).
  - Drop all remaining tags (including <span style=…>, <strong>, <b>,
    <em>, <i>, <u>) — ReactMarkdown can re-emphasise the inner text later
    if the admin wants.
  - Collapse 3+ blank lines.
  - Trim leading/trailing whitespace.

Run:
    PYTHONIOENCODING=utf-8 python strip_html_from_text.py [--dry-run]
"""
from __future__ import annotations

import os
import re
import sys
import html as _html
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question  # noqa: E402

TEXT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d",
               "explanation", "mnemonic", "concept_explanation")
HAS_HTML_RE = re.compile(r"<[a-zA-Z][^>]*>|&(?:nbsp|amp|lt|gt|quot|#\d+);", re.I)


def strip_html(text: str) -> str:
    if not text:
        return text
    s = text
    # 1. List items → markdown bullet on their own line.
    s = re.sub(r"<li[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"</li>", "\n", s, flags=re.I)
    # 2. Block closers / <br> → newline.
    s = re.sub(r"</?(p|div|h[1-6]|ul|ol|li|br)[^>]*>", "\n", s, flags=re.I)
    # 3. Drop ALL remaining tags.
    s = re.sub(r"<[^>]+>", "", s)
    # 4. Decode entities.
    s = _html.unescape(s)
    # 5. Collapse whitespace.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main(dry_run: bool = False) -> int:
    qs = Question.objects.all().only("id", *TEXT_FIELDS)
    total = qs.count()
    print(f"Scanning {total} questions for raw HTML…")
    touched = 0
    samples: list[tuple[int, str, str, str]] = []
    for q in qs.iterator(chunk_size=500):
        changes: dict[str, str] = {}
        for f in TEXT_FIELDS:
            original = getattr(q, f) or ""
            if not HAS_HTML_RE.search(original):
                continue
            cleaned = strip_html(original)
            if cleaned != original:
                changes[f] = cleaned
                if len(samples) < 4 and f == "question_text":
                    samples.append((q.id, f, original[:90], cleaned[:90]))
        if not changes:
            continue
        touched += 1
        if not dry_run:
            for k, v in changes.items():
                setattr(q, k, v)
            q.save(update_fields=list(changes.keys()))
    print(f"\nDry run: {dry_run}")
    print(f"Questions touched : {touched}")
    for qid, field, before, after in samples:
        print(f"  #{qid} [{field}]\n    BEFORE: {before!r}\n    AFTER : {after!r}\n")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(main(dry_run=dry))