"""One-off data migration: strip leaked `<p>correct</p>` / `<p>incorrect</p>`
flag paragraphs that the high-fidelity DOCX extractor (`BoxedMCQExtractorFidelity`)
emitted into ``option_*`` fields.

These were the rows the user saw still leaking after migration 0027 ran.
Root cause: the fidelity extractor's ``_row_value_html`` rendered every
non-label cell of a boxed `Option | <text> | correct` row into the
option HTML, concatenating the flag cell into the option body.

Migration 0027 only matched a `\\n…correct$` trailing-line pattern. The
flag paragraphs in the fidelity path are wrapped in their own `<p>…</p>`,
so they slip past 0027. This migration adds a second, stricter scrubber:

  - Match `<p[^>]*>\\s*(?:<…>\\s*)*(?:correct|incorrect)\\s*(?:<…>\\s*)*</p>`
    — a paragraph whose entire body (ignoring inline formatting tags) is
    the lone word `correct` or `incorrect`.
  - Optional `<strong>correct</strong>` / `<em>…</em>` wrappers are
    tolerated so admin-side rich-text doesn't defeat the cleanup.
  - `correct`/`incorrect` *inside* a sentence, a list item, or
    embedded in a longer paragraph is **not** matched by design — we
    never want to silently rewrite legitimate prose like
    "Statements 2 and 4 are correct" or "Options A and B are
    correct choices".

The migration also re-runs the 0027 cleanup (``strip_imported_html`` +
``strip_leaked_correct_incorrect``) which is idempotent — already-clean
rows are no-ops.
"""
from __future__ import annotations

from django.db import migrations

from ._data_cleanups import (
    strip_flag_paragraphs,
    strip_imported_html,
    strip_leaked_correct_incorrect,
)

TEXT_FIELDS = (
    "question_text", "option_a", "option_b", "option_c", "option_d",
    "explanation", "mnemonic", "concept_explanation",
)


def _run_cleanup(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    total = 0
    for q in Question.objects.all().iterator(chunk_size=500):
        updates = {}
        for f in TEXT_FIELDS:
            original = getattr(q, f) or ""
            # 0027 pipeline (idempotent) — no-op on already-clean rows.
            cleaned = strip_imported_html(original)
            cleaned = strip_leaked_correct_incorrect(cleaned)
            # 0029 scrubber: drop flag paragraphs (the high-fidelity leak).
            cleaned = strip_flag_paragraphs(cleaned)
            if cleaned != original:
                updates[f] = cleaned
        if updates:
            for k, v in updates.items():
                setattr(q, k, v)
            q.save(update_fields=list(updates.keys()))
            total += 1
    if total:
        print(f"[0029_strip_flag_paragraphs] touched {total} questions")


def _reverse_noop(apps, schema_editor):
    # Cleanup is one-way — no schema state to undo.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0028_questionimage_updated_at'),
    ]

    operations = [
        migrations.RunPython(_run_cleanup, _reverse_noop),
    ]
