# TASKS.md — Live Task Tracker

> Every active task. Update on every status change. The session only ends when this list is empty OR every remaining item is documented as out-of-scope in `NEXT_STEPS.md`.

| ID | Status | Subject | Owner |
|---|---|---|---|
| H1 | ✅ Shipped | Fix silent `is_published` overwrite in `mock_test_builder._ensure_test` | claude |
| H2 | ✅ Shipped | Add importer unit test scaffolding | claude |
| H3 | ⏳ Pending | DOCX namespace-error XML fallback | claude |
| H4 | ✅ Shipped | Cache dedup index to disk | claude |
| H5 | ✅ Shipped | Cache subject alias dict + fix `Name_or_code` typo | claude |
| H6 | ⏳ Pending | Batch enrichment + AI cache | claude |
| H7 | ✅ Shipped | Filter `_doc/_note` rows in `load_exam_fixture` | claude |
| H8 | ⏳ Pending | Tailwind 4 syntax sweep across whole frontend | claude |
| H9 | ✅ Shipped | Confirm CI runs `manage.py test material_importer` (autodiscovery) | claude |
| H10 | ✅ Shipped | Confirm `_ensure_question_bank_loaded` logs on bootstrap | claude |
| ARCH-1 | ✅ Shipped | `docs/MOCK_TEST_ARCHITECTURE.md` deep doc | claude |
| ARCH-2 | ✅ Shipped | Implement admin "Publish + Build Tests" action + CLI | claude |
| CONTENT-1 | ⏳ Pending | Identify the 480 Batch #13 questions missing `correct_answer` | claude |
| CONTENT-2 | ⏳ Pending | AI enrichment for image-based questions | claude |
| AUDIT-2026-07-30 | ✅ Shipped | 12-phase comprehensive audit (sub UX, security throttles, CSP, magic-bytes, 3rd-party doc, repo cleanup, a11y, SEO adds, docs) | claude |
| SECURITY-1 | ⛔ Documented | Sign-out should clear single-device session | NEXT_STEPS.md §B |
| OUT-OF-SCOPE-1 | ⛔ Documented | Playwright E2E sweep | requires browser + dev server |
| OUT-OF-SCOPE-2 | ⛔ Documented | AI backfill on 8,233 prod questions | requires live DB + tokens |
| OUT-OF-SCOPE-3 | ⛔ Documented | Live admin walkthrough | requires auth credentials |
| OUT-OF-SCOPE-4 | ⛔ Documented | Apply upload magic-byte validator to all ~40 upload endpoints | covered by module, opt-in per view |

## Completion rules

- After every change, update `PROJECT_STATE.md`, `WORKLOG.md`, `BUGS.md`, and this file.
- If new work surfaces, add an entry here first.
- "✅ Shipped" = code in working tree + `py_compile` clean + tests pass + bug doc updated.
- "⏳ Pending" = known but not started.
- "⛔ Documented" = explicitly out-of-scope this session; documented in NEXT_STEPS.md.
