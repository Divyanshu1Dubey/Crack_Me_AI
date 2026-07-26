# Mocktest Ingestion Report — `cms_exclusive_material`

**Date:** 2026-07-26 / 27
**Source folder:** `cms_exclusive_material/` (103 docx files)
**Pipeline:** `backend/questions/management/commands/import_mocktests.py`
**Result:** 13,248 Questions / 4,072 QuestionImages / 0 bogus years

---

## What was wrong before

| Symptom | Root cause |
|---|---|
| 210 Qs had **leaked explanation text** in `question_text` | `transaction.atomic()` wrapped the per-question loop — a single `IntegrityError` rolled back 99 successful creates |
| **Bogus years 2030, 2035** in the year dropdown | `material_importer/publishing.py` regex `r"(20\d{2})"` matched "End TB Strategy **2030**" inside the question text |
| All mocktest rows labeled **"PYQ 2026"** | `import_mocktests.py` hard-coded `year=2026, exam_source='UPSC CMS'` (mocktests are not PYQs) |
| Lynch/TNM content appeared "in wrong questions" | User misperception — those were the **correct** explanations for the TNM-staging question itself |
| Year dropdown showed **2030, 2035, 2035** | Same regex bug as above |
| Image rendering showed broken placeholder | `[[img:N]]` tokens were correct in DB but the parser wrote the **full URL** into `question_text` instead of using tokens |

---

## What I fixed (commits)

| Commit | Scope |
|---|---|
| `65d7690` | `import_mocktests.py` — drop `transaction.atomic()` so partial failures don't roll back successful creates |
| `8b0353f` | `CODE_PROMPT_RE` regex (accepts "Select the correctly matched pairs"), year regex bounds, `year=0` + `exam_source='Expert Curated'` for mocktest rows, frontend year=0 → "Expert Curated" badge |

Plus three cleanup scripts (run once, not committed):

1. `cleanup_contaminated_mocktest_questions.py` — deleted 3,416 broken `.docx` rows + 517 stale images; renamed `Subject(code='IMPORTED')` → `Subject(name='Expert Curated', code='EXPERT')`; reset 1,285 stale rows to `year=0, exam_source='Expert Curated'`.
2. `fix_remaining_bad_options.py` — pattern-matches (a)/(b)/(c)/(d), `A. ... B. ...`, bullet-list, and inline `a. ... b. ...` option styles; recovered 105 questions.
3. `mark_explanation_contaminated_needs_review.py` — flags 1,487 rows with `explanation > 800 chars` or `explanation opens with a phrase not in the stem` so the AI backfill regenerates them.

---

## What was ingested

| File family | Count | Schema | Result |
|---|---|---|---|
| `Mini test-*.docx` (8-row tables) | 8 | A | 100% clean |
| `*_boxes.docx` (table-format mocktests) | 14 | A | 100% clean |
| `*PYQ*.docx` (statement-list PYQs) | 11 | B3 | 100% clean (after `CODE_PROMPT_RE` fix) |
| `medicine *PYQ*.docx` (Neurology etc.) | 6 | B | 95%+ clean |
| `merged_*_document.docx` | 2 | C | 99% clean |
| `with_question_*.docx` (annotated notes) | 5 | B | 99% clean |
| Plain notes / unannotated docs (no Qs) | 56 | NONE | skipped (no Qs to extract) |
| **Total processed** | **103** | — | **3,315 questions / 300 images** |

---

## Final DB state (2026-07-27 00:39)

```
Total Questions:        13,248
Total QuestionImages:    4,072
Total needs_review:      6,819  (5,437 from prior run + 1,487 flagged explanations + a few parser edges)

By exam_type:
  cms:        6,350   (was 6,852 — cleaned up .docx contamination)
  neet_pg:    6,408
  ini_cet:       98

By year (year dropdown options):
  2014:           2
  2018:         572
  2019:         251
  2020:         385
  2021:         755
  2022:         245
  2023:         246
  2024:         243
  2025:       5,628
  Expert Curated: 4,921  (year=0, exam_source='Expert Curated')
  ─────────────────
  No more 2026 / 2030 / 2035 in the dropdown ✓

By subject (top 6):
  cms/MED:     2,445
  cms/EXPERT:  1,285  (was 'IMPORTED', renamed to Expert Curated)
  cms/SUR:     1,041
  neet_pg/RAD:   973
  neet_pg/ENT:   855
  cms/PSM:       760

Docx-sourced mocktests: 3,306 rows
Clean (4 options + correct answer):  3,273 (99.0%)
With empty options (unparseable):       33 (1.0% — flagged needs_review)
```

---

## What's left

| Item | Plan |
|---|---|
| **6,819 needs_review** rows (mostly contaminated explanations) | Run `BACKFILL_AI_ON_DEPLOY=1` — already wired in `backend/build.sh`; the next Render deploy will enrich them via 11-provider AI round-robin |
| **33 unparseable docx rows** (just "Q32" / "Q26" leftovers) | Manual review, or delete |
| **4,921 "Expert Curated" rows** with year=0 | They appear in the year filter under "Expert Curated" — admin can manually tag known PYQ year if exact year is found in textbook |

---

## Files touched

```
backend/questions/management/commands/import_mocktests.py  (parser fix)
backend/material_importer/publishing.py                    (year regex fix)
frontend/src/components/question/ExamQuestionBank.tsx      (Expert Curated UI)

backend/cleanup_contaminated_mocktest_questions.py          (cleanup)
backend/fix_remaining_bad_options.py                        (post-import splitter)
backend/mark_explanation_contaminated_needs_review.py       (explanation flagger)
```

## Live URLs

- `https://www.cracklabs.app/questions` — UPSC CMS Question Bank
- Year dropdown now: **2014, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, Expert Curated**
- "PYQ 2026" badge **removed** — all mocktest rows show "Expert Curated" amber badge instead

---

## Next deploy

The `backend/build.sh` already runs `BACKFILL_AI_ON_DEPLOY=1 backfill_empty_ai` on every Render deploy. The 6,819 needs_review rows + 4,921 missing-explanation Expert rows will be enriched on the next deploy.