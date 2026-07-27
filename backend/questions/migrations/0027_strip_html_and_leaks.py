"""One-off data migrations: strip raw HTML tags + leaked answer-key
fragments from every Question text field.

These two cleanups previously lived as standalone scripts that the dev
ran against the local SQLite DB — but production (Render Postgres) never
got them, so the UI kept leaking <p> / &nbsp; / "correct" / "incorrect"
into question rows. Rolling them into a migration means every deploy
self-heals, no manual operator step required.

Steps:
  1. `strip_imported_html` — drop <p>, <strong>, <ul><li>, decode
     &amp;/&lt;/&gt;/&quot;/&nbsp;, etc. (225 rows on local)
  2. `strip_leaked_correct_incorrect` — drop trailing standalone
     "correct" / "incorrect" annotations on their own line (372 rows
     on local) while leaving legitimate sentences like "2 and 4 are
     correct" intact.

Both functions are idempotent — re-running on already-clean text is a
no-op. A short summary line is printed when anything changed so the
deploy log surfaces the impact.
"""
from __future__ import annotations

import html as _html
import re

from django.db import migrations

# Local copies of the cleanup helpers — kept inside the migration so
# the script files (backend/strip_html_from_text.py, fix_correct_
# incorrect_leak.py) can be removed safely without breaking this
# migration's history.

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

TEXT_FIELDS = (
    "question_text", "option_a", "option_b", "option_c", "option_d",
    "explanation", "mnemonic", "concept_explanation",
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


def _run_cleanup(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    total = 0
    for q in Question.objects.all().iterator(chunk_size=500):
        updates = {}
        for f in TEXT_FIELDS:
            original = getattr(q, f) or ""
            cleaned = strip_imported_html(original)
            cleaned = strip_leaked_correct_incorrect(cleaned)
            if cleaned != original:
                updates[f] = cleaned
        if updates:
            for k, v in updates.items():
                setattr(q, k, v)
            q.save(update_fields=list(updates.keys()))
            total += 1
    if total:
        print(f"[0027_strip_html_and_leaks] touched {total} questions")


def _reverse_noop(apps, schema_editor):
    # Cleanup is one-way — no schema state to undo.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0026_alter_subject_exam_type'),
    ]

    operations = [
        migrations.RunPython(_run_cleanup, _reverse_noop),
    ]