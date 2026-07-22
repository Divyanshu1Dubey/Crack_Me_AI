# Phase 4 — Test Report

**Date:** 2026-07-22

## Coverage Matrix

| Subsystem | Backend tests | Frontend tests | E2E tests |
|---|---|---|---|
| Auth (Django + Supabase) | ✅ `accounts/tests.py` | ⚠ Phase 5 | ⚠ Phase 5 |
| Question CRUD | ✅ `questions/tests.py` | ✅ Existing | ⚠ Phase 5 |
| Recall search | ✅ NEW `tests_phase4.py` | ✅ Manual | ⚠ |
| AI per-question | ✅ NEW `tests_phase4.py` | ✅ Manual | ⚠ |
| Practice modes | ✅ NEW `tests_phase4.py` | ✅ Manual | ⚠ |
| Practice experience (flag/...) | ✅ NEW `tests_phase4.py` | ⚠ Phase 5 | ⚠ |
| Recall images facets | ✅ NEW `tests_phase4.py` | n/a | n/a |
| Importer | ✅ `importers/neetpg/tests/*` | n/a | n/a |
| Dedup | ✅ `test_deduplicator.py` | n/a | n/a |
| Classifier | ✅ `test_classifier.py` | n/a | n/a |
| Text parser | ✅ `test_text_parser.py` | n/a | n/a |
| Fingerprints | ✅ `test_fingerprints.py` | n/a | n/a |
| Analytics dashboard | ⚠ Phase 5 | ⚠ Phase 5 | ⚠ |
| Importer CLI | ⚠ Phase 5 | n/a | n/a |
| Security posture | ✅ NEW `tests_phase4.py` | n/a | n/a |
| **TOTAL** | **8 backend test files** | Frontend routes skip Cypress for now | n/a |

## New tests added in Phase 4 (`backend/questions/tests_phase4.py`)

| Class | Coverage |
|---|---|
| `RecallSearchTestCase` | 4 tests: filters, facets, pagination |
| `PracticeModesTestCase` | 2 tests: catalogue, image_only queue |
| `AIPerQuestionTestCase` | 3 tests: returns str, cache hit, fallback |
| `PracticeExperienceTestCase` | 4 tests: flag, confidence, elimination, time |
| `RecallImagesFacetsTestCase` | 2 tests: callable, image-required filter |
| `SecurityPostureTestCase` | 2 tests: dev skips, prod raises |

Total: **17 backend tests** added in Phase 4.

## Run command

```bash
cd backend
python manage.py test questions.tests_phase4 -v 2
```

## Recommended Phase-5 work

* Add Playwright e2e tests for `/practice`, `/recall/search`,
  `/analytics/dashboard_v3`.
* Add frontend Jest tests for `QuestionToolbar` state transitions.
* Add integration tests for the importer CLI:
  `python manage.py neetpg_import_run`.

## Self-review checks performed

* `grep -n "TODO|FIXME|XXX"` over Phase-4 code — none.
* Linter unused-import scan — `Sum` import removed; `Iterable` removed;
  rest_framework re-exports tagged with `# noqa: F401`.
* Phase 4 `tests_phase4.py` imports `unittest.mock` and uses
  `mock.patch.object` for AI fallback test, verifying graceful
  degradation when no AI key is configured.
