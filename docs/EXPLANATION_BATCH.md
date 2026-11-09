# AI explanation batch and its review queue (2026-11-09)

Code: `backend/questions/explanation_batch.py`, `management/commands/generate_explanations.py`,
`views_explanation_batch.py` (admin API), `tasks.run_explanation_batch_task` (django-q); admin page
`frontend/src/app/admin/explanations`. Models `ExplanationBatchRun`, `ExplanationBatchItem` (questions.0050).

## Which questions

Active questions with a valid key (A-D) whose `explanation` is empty, the NEET PG placeholder ("Reference: NEET PG
previous year question bank.") or only `[[img:N]]` tokens, or was written for another key (a corrected key:
`explanation_for_key` differs, or `stale` "Key changed ..."). Left out: locked explanations, questions with a figure
(`is_image_based` or a primary image: the model cannot see it; editors write those), questions without a valid key.

Production copy, 2026-11-09 (after questions.0049): **6,016** questions (CMS 2,515, NEET PG 3,407, INI-CET 94);
5,703 without the stale ones. 375 figure / image-based questions and 380 questions without a valid key are not in it.

## What is saved (and what is not)

`AIService.explain_after_answer` answers the question itself and reports a disagreement with the key. An explanation
is saved only when:

* the AI's own answer is the stored key, otherwise the item is **disagrees**: nothing saved, the question is listed
  on the admin page for a key check (answer-key review);
* the output is usable: a reason why the key is right (40+ characters), at least two wrong options explained, no
  provider error or "as an AI" text; otherwise it is retried, then **invalid**.

The model's citations are never kept: reference / source lines, "(Book, p. 12)" / "Chapter 4" style citations and
`[cite ...]` artefacts are removed, and its `textbook_reference`, `similar_pyq`, `pyq_frequency` are not used.
Verified citations come only from the evidence app (quotes checked on the page).

The text is composed from its parts: **Answer** (the key and its option), **Why X is correct**, **Why the other options
are wrong** (one line each), **High-yield points**, **Clinical pearl** in `explanation`; the core concept in
`concept_explanation`; the mnemonic in `mnemonic`. It is saved with `editorial.save_explanation(actor=None)`:
`explanation_status='ai_generated'`, `explanation_origin='ai'`, `explanation_for_key`, `explanation_stem_hash`,
`explanation_hash`. Students see it with "AI-generated, not yet reviewed by our team: cross-check with your textbook"
until an admin reviews it.

## Checkpoints, claims, retries

One `ExplanationBatchItem` per question and run (`queued` → `claimed` → `done` / `disagrees` / `invalid` / `failed` /
`skipped`). An item is claimed with a conditional UPDATE (`claimed_until`, 10 minutes), so two workers never take the
same question and an abandoned claim is taken again. An AI outage puts the item back (`MAX_ATTEMPTS` = 3, then
`failed`); `AI_OFFLINE_MODE` stops the run without using up an attempt. Before saving, the question is checked again:
hidden, a new key, an edited stem, a locked or newly written explanation since it was queued means `skipped`. A run
can be continued any time; a finished one does nothing.

## Running it

Admin page **AI Explanations** (`/admin/explanations`): counts, "Create batch" (exam, years, at most N, with or without
the stale ones), "Process next N" (queued on the django-q worker; `start_web.sh` starts it), the items of a batch by
status (e.g. "AI chose another answer"), and the **review queue** (AI-generated explanations not reviewed yet: "Mark
reviewed" = `POST /api/questions/<id>/review-explanation/`, which records the review for this exact text; "Open to
edit").

Shell (Railway):

```
python manage.py generate_explanations --count
python manage.py generate_explanations --create --exam cms            # prints the run id
python manage.py generate_explanations --run <id> --max 200 --sleep 1.5
python manage.py generate_explanations --status <id>
```

It needs the AI provider keys (the 10-entry rotation, `docs/setup/API_KEYS.md`); a provider's free-tier limits set
the pace (about one question every few seconds). Nothing runs at deploy.

## API (admin)

| Method | Path | |
|---|---|---|
| GET | `/api/questions/explanation-batches/` | `{needed: {total, by_exam}, runs: [{id, created_at, scope, note, total, counts}]}` |
| POST | `/api/questions/explanation-batches/` | `{exam_type?, years?, include_stale?, limit?, note?}` → `201` the run |
| POST | `/api/questions/explanation-batches/<id>/process/` | `{max_items (≤ 500), sleep_seconds}` → `202` queued; `409 ai_offline` |
| GET | `/api/questions/explanation-batches/<id>/items/` | `?status=&page=` (50 per page) |
| GET | `/api/questions/explanation-review/` | AI-generated, not reviewed: `?exam_type=&page=` |
