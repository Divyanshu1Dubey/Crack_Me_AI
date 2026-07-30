# PROJECT_STATE.md

> Current authoritative state of the CrackCMS project as of 2026-07-27 (ongoing autonomous session).
> This file is the single durable snapshot of what is true *now*. Update on every change.

## One-line summary
CrackLabs is an AI-powered UPSC CMS exam prep platform; recent focus is the new `material_importer` DOCX/PDF/PPTX ingestion pipeline + a CMS/NEET-PG/INI-CET fixture split. The session has produced 4 audit docs and identified 1 high-risk bug (`is_published` overwrite) that needs an immediate surgical fix.

## Tech stack (verified)
- Frontend: Next.js 16.1.6 + React 19 + TypeScript 5 + Tailwind 4 + Radix UI
- Backend: Django 5.x + DRF + SimpleJWT + django-axes
- DB: SQLite by default; Postgres-ready via `dj_database_url` / Supabase
- AI: 9-provider round-robin (`ai_engine/services.py`) + Ollama fallback; **NVIDIA Mistral + DeepSeek initialized but NOT rotated** (legacy gap)
- Auth: Hybrid Supabase-first + Django JWT-fallback
- Background: `django-q2` (4 workers)
- Cache: Redis if `REDIS_URL` else LocMem

## Django apps
`accounts` · `questions` · `tests_engine` · `analytics` · `ai_engine` · `textbooks` · `resources` · `video_engine` · `jobs` · `ingestion` (Phase 1) · **`material_importer` (new)** · `axes`

## Recent diffs (committed)
Last 15 commits confirm a healthy trajectory: security fix to `/api/questions/` (no leaked correct answer), 409 + If-Match fix for optimistic-locking, fixture pipeline fixes, mojibake cleanup.

## Work-in-progress diffs (uncommitted)
- **Backend** (7 files): `crack_cms/settings.py` (+1 INSTALLED_APP), `questions/views.py` (back-compat fixture path), `questions/management/commands/fix_mojibake.py` (multi-fixture), `test_all.py` (3 path updates).
- **Frontend** (3 files): Tailwind v4 syntax upgrades (`[var(--x)]` → `(--x)`, `[10rem]` → `40`, etc.).

## Untracked (new since last commit)
- `backend/material_importer/` (full app, 18 Python files)
- `backend/fixtures/{cms,inicet,neet_pg}_fixture.json` + `images/` + `README.md`
- `backend/questions/management/commands/load_exam_fixture.py`
- `backend/questions/migrations/0026_alter_subject_exam_type.py`
- Helper reports: `docs/qa_report_batch13.json`, `scripts/_mocktest_*.json`, etc.
- `frontend/tests/e2e/live-audit.spec.ts`

## Verified data integrity
- `cms_fixture.json` retains **1,920 questions** + 1,918 topics + 5 CMS subjects.
- `inicet_fixture.json` + `neet_pg_fixture.json` retain thin seed data + doc-comment rows.
- Migration 0026 adds `ini_cet` + `fmge` to `Subject.exam_type` choices; default still `'cms'`.

## Top remaining risks
1. **H1** — `mock_test_builder._ensure_test` silently un-publishes tests on rebuild (high).
2. **H2** — `material_importer` has zero unit tests.
3. **H3** — One DOCX file in `cms_exclusive_material` (`merged_notes-document (1).docx`) fails to parse due to a namespace prefix; recoverable in theory.

## Open follow-ups (in docs/HIGH_PRIORITY_FIXES.md)
10 ranked fixes ready to ship.
