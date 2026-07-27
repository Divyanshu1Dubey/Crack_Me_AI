# Review Queue

The review queue at `/admin/import-center/review` is the human-in-the-loop
screen for the Import Center. It surfaces every `ExtractedQuestion` that
the parser produced so the content team can decide whether each question
is publishable, needs editing, or should be discarded.

---

## What you see

By default the queue is filtered to `status=needs_review` so the screen
focuses on the rows the parser was *not* confident about. The visible
columns are:

- **Q** — clickable line-clamped preview that opens the *Preview Drawer*.
- **Source** — batch id (link to detail page) + filename.
- **Subject → Topic** — auto-classified. Hover for confidence %.
- **Answer** — letter A/B/C/D or `?` if not detected.
- **Conf.** — classifier confidence (0–100%).
- **Status** — colour-coded chip (see below).
- **Actions** — per-row Approve / Reject / Reset.

A toolbar above the table exposes bulk actions when at least one row is
selected.

## Status colours

| Status | Colour | Meaning |
|---|---|---|
| `pending` | Yellow | Extracted but not yet reviewed. |
| `needs_review` | Orange | Parser was not confident (e.g. missing answer marker). |
| `approved` | Green | Ready for the next publish pass. |
| `rejected` | Red | Excluded from publishing. |
| `published` | Blue | Already promoted to a live `Question` row. |
| `duplicate` | Gray | Detected as a duplicate of an existing question. |

## Filters

Top-right of the queue:

- **Status** dropdown (`pending` / `needs_review` / `approved` / `rejected` / `published` / `duplicate`).
- **Batch #** input — show only questions from a single import batch.

Pagination: 50 rows per page by default. Adjustable via the
`page_size` query param.

## Bulk decisions

Select rows with the checkbox column. When at least one is selected, a
toolbar appears with:

- **Approve** — sets `status='approved'` for every selected row.
- **Reject** — sets `status='rejected'`.
- **Reset** — sets `status='pending'`.

Each bulk operation writes a single `ImportAuditLog` row per touched batch
with the acting username.

## Per-row decisions

Same three buttons in the *Actions* column.

## Preview Drawer

Click any row to open the drawer with:

- Full question text (preserves newlines).
- All four options. The correct one is highlighted green.
- Explanation (full text, preserves inline image tokens).
- Classification metadata (subject, topic, subtopic, difficulty,
  confidence, bloom level).
- AI classification status badge.
- Per-row Approve / Reject / Reset / **🧠 Re-classify** buttons.

The *Re-classify* button calls
`POST /api/admin/import/questions/{id}/classify-ai/` which re-runs the
classifier on this single row. The drawer refreshes with the new
classification.

## Single-question decision endpoint

```
POST /api/admin/import/questions/{id}/decision/
{
  "decision": "approve" | "reject" | "reset",
  "note": "free-form reviewer comment"
}
```

The note is stored on `ExtractedQuestion.review_note` and shown in the
audit log.

## Bulk-decision endpoint

```
POST /api/admin/import/questions/bulk-decision/
{
  "ids": [1, 2, 3, …],
  "decision": "approve" | "reject" | "reset",
  "note": "free-form reviewer comment"
}
```

`ids` must be a non-empty list of integers. One audit-log row is written
per touched batch.

## AI re-classification endpoint

```
POST /api/admin/import/questions/{id}/classify-ai/
{ "use_ai": true }
```

Re-runs `ai_classifier.classify_question(...)` on this single row,
updates `inferred_subject`, `inferred_topic`, `inferred_difficulty`,
`inferred_bloom_level`, `classification_confidence`, `classification_meta`,
and re-resolves the `subject` / `topic` FKs.

Response:

```json
{
  "id": 12345,
  "subject": "General Medicine",
  "topic": "Cardiology",
  "difficulty": "medium",
  "bloom_level": "apply",
  "confidence": 0.78
}
```

## Search

The *Search* tab at `/admin/import-center/search` is a debounced
full-text search across `question_text`, options, explanation,
`inferred_topic`, and filename. Each result links back to the parent
batch.

## Status transitions

```
        ┌─────────────┐
        │  pending    │◄──────────────┐
        └──────┬──────┘               │
               │ approve             │ reset
               ▼                     │
        ┌─────────────┐              │
        │  approved   │──────────────┤
        └──────┬──────┘              │
               │ (publish passes)   │
               ▼                     │
        ┌─────────────┐              │
        │  published  │              │
        └─────────────┘              │
                                      │
        ┌─────────────┐              │
        │  rejected   │──────────────┘
        └─────────────┘

        needs_review = pending + confidence < threshold
                       or correct_answer not in A/B/C/D
                       or explanation length > threshold
```

The auto-flagging rule lives in
`ingest_service._persist_parsed_document`:

```python
needs_review = q.correct_answer not in "ABCD" and bool(q.question_text)
```

After this initial flag, the admin can manually `reset` the row to
`pending` so it reappears in the default review queue.

## Performance

The queue endpoint is paginated and uses `select_related()` for
`material`, `subject`, and `topic` so the JSON payload is small even for
50k-question batches.

For 100k+ question corpora, narrow the filter to a single batch before
bulk-deciding — every bulk decision writes one `ImportAuditLog` row per
touched batch, so a single sweep is cheap but a corpus-wide sweep can
produce a noisy log.

## Best practices

- **Start with the needs_review filter.** That's where the parser was
  uncertain.
- **Use bulk approve** for rows where the parser was confident — the
  filter `status=approved & confidence > 0.8` is a good starting point.
- **Use the Preview Drawer before approving ambiguous rows.** It is much
  faster than opening the question detail in another tab.
- **Reset before re-classifying.** If you re-classify a row that is
  currently `approved` you'll still see the new subject/topic but the
  status won't change — the row is "approved" regardless of classification.
- **Avoid bulk-resetting across batches.** Resetting drops the audit-log
  trail of who approved what. Prefer single-row resets unless you really
  need a corpus-wide reset.