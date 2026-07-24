# Numbering Validation — NEET PG Browser QA

**Date**: 2026-07-25
**Scope**: every place a question number is displayed (list, detail, palette, PYQ position, ID)

---

## Numbering fields on `Question`

| Field | Type | Population | Used by |
|-------|------|------------|---------|
| `id` | integer (auto-increment) | 100% | API always |
| `uuid` | UUID4 | 100% | API always |
| `display_number` | integer nullable | **0%** | nowhere on frontend |
| `page_number` | string | ~95% | PDF page reference |
| `times_asked` | integer | varies | analytics |

---

## Numbering surface

### List page (Question Bank)

`/questions?exam=neet-pg`

- Frontend renders `q.id` (auto-increment integer) — never `display_number`.
- Bug: `display_number` is NULL, so when the frontend grows to use it (planned per-paper Q1, Q2, ...), it will fall back to `id`. Result: a student seeing "Q. 12336" for the 206th question of the 2021 paper is confusing.

### Detail page

`/questions/<id>` (Question Detail view)

- Renders `Question ID: 12336` header — not the paper-relative number.

### Practice player

`/questions/neet-pg/practice?year=2021`

- The player enumerates `questions[state.index]` (1-based from array index), not `display_number`.

### Palette (NEET PG HUD)

- Palette tile shows array index 1..N.

### Year grid

- Year tile shows total count, not per-question number.

---

## Inconsistencies

| Source | ID 12336 | Year 2021 #? |
|--------|----------|--------------|
| `Question.id` | 12336 | — |
| `Question.display_number` | null | — |
| `Question.page_number` | (varies) | "206" (per pdf) |
| Player array index | (irrelevant) | index 0 of 329 |

A student landing on this question via the URL `/questions/neet-pg/practice?q=12336` will see:

- The question text starts with "206. During the course of psychotherapy..." (the PDF's own number, preserved in `question_text`).
- The palette shows Q1 (it's the first item in the array since the API orders by `-id`).

**Conclusion**: Three different numbering schemes co-exist in the same UI:
1. PDF paper-relative: 206 (in stem text)
2. Database id: 12336 (URL, header)
3. Array index: 1 (palette, prev/next nav)

This is a UX bug. The fix: populate `display_number` with the PDF question number, render it in the player header, and use it for the palette instead of array index.

---

## Required fix

1. **Populate `display_number`** — One-off SQL:
   ```sql
   UPDATE questions_question
   SET display_number = SUBSTRING(question_text FROM '^(\d+)\.\s')::int
   WHERE exam_type='neet_pg' AND display_number IS NULL
     AND question_text ~ '^\d+\.\s';
   ```
2. **Renderer** — `NeetPgPlayer` should show `q.display_number ?? idx+1` in the question header.
3. **Palette** — Render `display_number` tile instead of array index.
4. **URLs** — `/questions/<display_number>?exam=neet-pg&year=2021` for human-friendly deep links.

---

## Regression test

`frontend/tests/e2e/neet-pg-qa.spec.ts` — "NEET PG 2021 questions have non-null display_number OR stable ordinal via id" — currently fails (0% populated). Will pass after the data fix.
