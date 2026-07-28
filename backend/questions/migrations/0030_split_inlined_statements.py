"""One-off data migration: rewrite inlined-statement question_text into a
numbered list.

Background:
    A subset of NEET PG questions (the 2026-07 ingest) was imported with
    the multi-statement stem either joined end-to-end or separated by
    newlines but missing bullet/number markers. On the question-bank
    card those rows render as one mashed paragraph with no list
    structure, while peers like row 25665 already render as a proper
    numbered list:

        Which of the following chromosomal abnormalities are
        associated with brain tumours?

        1. Neurofibromatosis type 1
        2. Neurofibromatosis type 2
        3. Peutz-Jeghers syndrome
        4. Hereditary nonpolyposis colorectal cancer

    `split_inlined_statements()` (see ``_statement_splitter.py``)
    rewrites the affected shape into the same numbered format. The
    splitter is intentionally conservative — it requires a recognised
    opener + tail, refuses any row that already has bullet/number/
    Roman-numeral markers, and refuses rows where the average
    statement length is suspiciously short (filters false-positive
    splits on noun lists).

    Idempotent: re-running yields zero touches.

    Topic_id NULL is **deliberately** NOT touched by this migration —
    it's a 11,918-row scope and deserves a separate project with
    subject-keyed keyword matching + confidence threshold.
"""
from __future__ import annotations

from django.db import migrations

from ._statement_splitter import split_inlined_statements


def _run_split(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    total = 0
    for q in Question.objects.all().iterator(chunk_size=500):
        original = q.question_text or ""
        cleaned = split_inlined_statements(original)
        if cleaned != original:
            q.question_text = cleaned
            q.save(update_fields=["question_text"])
            total += 1
    if total:
        print(f"[0030_split_inlined_statements] touched {total} questions")


def _reverse_noop(apps, schema_editor):
    # Splitting is one-way; we don't have the original sentence
    # boundaries stored anywhere to reconstruct the inlined form.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0029_strip_flag_paragraphs'),
    ]

    operations = [
        migrations.RunPython(_run_split, _reverse_noop),
    ]