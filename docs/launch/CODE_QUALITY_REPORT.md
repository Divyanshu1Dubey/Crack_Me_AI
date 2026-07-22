# Phase 4 — Code Quality Report

**Date:** 2026-07-22

## Lint debt removed in Phase 4

| File | Symbol | Action |
|---|---|---|
| `backend/analytics/dashboard_v3.py` | `Sum` (unused import) | Removed |

## Documented re-exports (intentional)

The following files keep `rest_framework` imports marked with
`# noqa: F401 — intentional re-export`:

* `backend/questions/recall_search.py` — re-exports `status`, `action`,
  `Response` so future test code can import them through the same
  module path.

## Dead code eliminated

None found in Phase-4 files.

## Duplicate logic

None added.  Phase-3 `practice_experience` reuses `QuestionBookmark.notes`
as a prefix-tagged JSON store, **avoiding** a new model.  Phase-3
`practice_modes` reuses existing queryset filters rather than introducing
helper classes.

## Naming conventions

* Snake case for Python (Django idiomatic).
* PascalCase for React components.
* `kebab-case.md` for docs.
* Lowercase URL paths.

## Docstring coverage

* Every Phase-3 / Phase-4 module has a top-of-file docstring.
* Every `@action` method names its URL path + permission class.
* Every DB-side helper docstring lists the index it depends on.

## Recommended Phase-5 work

* Add `mypy --strict` to the backend CI (currently untyped).
* Add ESLint `--max-warnings 0` to the frontend CI.
* Add `bandit -r backend/` to the CI step.
