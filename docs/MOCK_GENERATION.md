# Auto Mock Test Generation

Two flavours of mock-test generation ship with the Import Center:

1. **Bulk build** — runs automatically when an admin clicks
   *Publish &amp; Build Tests*. Produces one auto-test per
   `subject`, per `(subject, topic)`, one `mixed` omnibus, and one per
   PYQ-year filename match.
2. **One-off generation** — runs via the **Generate Mock Test** modal on
   the batch detail page. Produces a single `Test` row using a chosen
   strategy.

Both are implemented in `backend/material_importer/mock_test_builder.py`.
The same code path is exposed:

- via the `publish_batch` management command
- via the `publish_batch_and_build_tests` helper used by the REST endpoint
- via the UI modal that calls `POST /api/admin/import/batches/{id}/generate-mock/`

---

## Bulk build

Triggered by:

- **UI**: *Publish &amp; Build Tests* button on the batch detail page.
- **CLI**: `python manage.py publish_batch --batch 12` (defaults to
  building tests).
- **Helper**: `publish_batch_and_build_tests(batch_id, max_per_test=100)`.

### What it produces

For each `ExtractedQuestion` in the batch with `status ∈ {pending, approved,
published}`:

| Bucket | `Test` name pattern | Kind |
|---|---|---|
| Subject | `Auto • <subject> • batch <id>` | `subject` |
| Topic | `Auto • <subject> → <topic> • batch <id>` | `topic` |
| Mixed | `Auto • Mixed • batch <id>` | `mixed` |
| PYQ year | `Auto • PYQ <year> • batch <id>` | `pyq_year` |

Each auto-test has:

- `test_type` set to the kind.
- `time_limit_minutes=60`, `negative_marking=False` (admin can override).
- `subject` / `topic` set where known.
- A `questions` M2M attached to the **published** `Question` rows
  (only the ones whose `ExtractedQuestion.published_question_id` is not
  null). The cap is `max_per_test` (default 100).

### Idempotency

`_ensure_test(name, kind, description, …)` upserts by name. The bulk
build also pre-deletes any prior auto-tests whose title contains
`batch <id>`, so re-running never duplicates.

`is_published`, `version`, `paper`, and other admin-set fields are
**never** overwritten on existing rows.

### PYQ year detection

If a source filename contains `PYQ`, the builder parses a 4-digit year
(`20\d{2}` or `19\d{2}`) out of the question text or the filename. The
buckets are:

- `Auto • PYQ 2023 • batch 12`
- `Auto • PYQ unknown • batch 12`

The `unknown` bucket is fine — it captures exams without a year in the
filename.

---

## One-off generation

Triggered by the **Generate Mock Test** modal on the batch detail page, or
via `POST /api/admin/import/batches/{id}/generate-mock/`.

### Strategies

| Strategy | Filter applied |
|---|---|
| `entire_file` | All `published` rows in the batch. |
| `by_subject` | Same as above + `subject_id` filter (optional). |
| `by_chapter` | Alias of `by_subject` (kept for UI clarity). |
| `by_topic` | `subject_id` + `topic_id` filter (optional). |
| `by_difficulty` | `inferred_difficulty ∈ {easy, medium, hard}`. |
| `random` | Pseudo-random via Python's `random.sample` (capped by count). |
| `image_based` | Only questions with `image_refs` non-empty. |
| `grand` | Long-form (high `question_count`). |
| `revision` | Smaller cap, mixed difficulty. |
| `weekly` | Same as revision but title-pattern suffixed. |

### Title

```
Auto • <strategy label> • batch <batch.id>
```

Where `<strategy label>` is human-friendly:

| Strategy | Label |
|---|---|
| `entire_file` | Entire File |
| `by_subject` | By Subject |
| `by_chapter` | By Chapter |
| `by_topic` | By Topic |
| `by_difficulty` | By Difficulty (medium) |
| `random` | Random Mix |
| `image_based` | Image Based |
| `grand` | Grand Test |
| `revision` | Revision Test |
| `weekly` | Weekly Test |

### Idempotency

`_ensure_test(name, …)` upserts by name. Re-running the modal with the
same parameters for the same batch replaces the question set, not the
`Test` row.

---

## Customising the test

After generation, open the test in the existing
`/admin/questions-editor` page (or use the `testsAPI.safeUpdate()` API)
to:

- Edit the title (recommended: replace the `Auto •` prefix).
- Set `is_published=True` to make it appear on the public tests page.
- Adjust `time_limit_minutes`, `negative_marking`, `version`, `paper`.

The import pipeline will never touch these fields once the test exists —
your manual edits survive subsequent re-builds.

---

## Why we don't store test questions in the staging area

`tests_engine.Test.questions` is an M2M to the **live** `Question` table.
The bulk build attaches only those `Question` rows whose
`ExtractedQuestion.published_question_id` is not null. This means:

- A test always points at published, fully-edited questions.
- Republishing the batch (after manual edits) refreshes the test's
  question set without touching the live `Question` rows themselves.
- Rollback is symmetric: cascade-deleting the batch's staging rows
  removes the auto-tests but never the published `Question` rows unless
  you explicitly pass `delete_published=true`.

---

## Programmatic example

```python
from material_importer.mock_test_builder import (
    build_for_batch,
    publish_batch,
    publish_batch_and_build_tests,
)

# Publish approved rows only (no test build)
n_published = publish_batch(batch_id=12)

# Publish + auto-build
result = publish_batch_and_build_tests(batch_id=12, max_per_test=50)
# {"published": 1023, "tests_built": 7}

# Just rebuild tests (no DB writes to Question)
n_tests = build_for_batch(batch_id=12, max_per_test=50)
```

```bash
# CLI
python manage.py publish_batch --batch 12 --max-per-test 50
python manage.py publish_batch --all-pending
```