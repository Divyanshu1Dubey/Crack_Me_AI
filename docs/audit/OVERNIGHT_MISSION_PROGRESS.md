# Overnight mission — progress log

_Last updated: 2026-11-01 — phase 2b done except AI offline mode; RAG mapping and discovery triage running_

## Where things are

| Item | Location |
|---|---|
| Git branch | `overnight-mission` (from `worktree-full-audit-fixes` @ 33532e0; tag `overnight-mission-start`) — **not pushed** |
| Worktree | `C:\Users\DIVYANSHU\Desktop\crack_cms\.claude\worktrees\full-audit-fixes` |
| Local infra (not in git) | `C:\Users\DIVYANSHU\crack_local\` |
| Isolated Postgres 16 | data `crack_local\pgdata`, **127.0.0.1:55432**, superuser `crack_super` (trust, localhost only) |
| Pristine restore | database `crack_restore` (never modified) |
| Working database | database `crack_local` (copy of `crack_restore` + 4 new migrations + local seed users + backfills) |
| Restored media | `crack_local\media` (copy of checkout `backend\media`, 11,549 files) |
| Supabase Storage mirror | `crack_local\storage\<bucket>\...` (1,095 objects from the storage zip) |
| Logs | `crack_local\logs\` (restore errors, migrations diff, postgres/backend/frontend logs) |
| Screenshots | `crack_local\screenshots\round1\` (71 routes, 336 shots + `report.json`), `crack_local\screenshots\fix1\` |

The existing PostgreSQL service on :5432 is **not** used or modified.

### Services / ports (local)

| Service | Port | Started by |
|---|---|---|
| PostgreSQL 16 (isolated cluster) | 55432 | `scripts\local\start-local.ps1` (or `pg_ctl`, see below) |
| Django backend (`DJANGO_ENV_FILE=.env.localdev`) | 8000 | `scripts\local\start-local.ps1` |
| Next.js (local auth + mock payments) | 3000 | `scripts\local\start-local.ps1 -Frontend prod|dev` |

## Backup integrity (originals are read-only)

| File | SHA-256 |
|---|---|
| `Downloads\db_cluster-02-10-2026@08-24-39.backup.gz` | `43D991777F68B4EE9F49AC450C1B7F02DDF39A89D1F02EBAB943DEA1260E5C3E` |
| `Downloads\ryuvcdthjnxyetdyjbph.storage.zip` | `99153EF090CA6DE9BBB207C1F3253A32476CC5F2FA0865F0E358793A8084AA1C` |

## Completed

- Phase 0: branch, tag, hashes, tool inventory (PG16 binaries present; no Docker; 18 GB free disk).
- Phase 2 recovery:
  - Cluster dump = Supabase `pg_dumpall` (PG 17.6) of databases `postgres` (production) and `test_postgres`.
  - Restored `postgres` → `crack_restore`: **140/141 tables with identical row counts**; only `vault.secrets` (0 rows, Supabase Vault extension) not restorable. Expected errors only: pgvector types/functions, Vault, PG17-only privileges.
  - Production had applied `questions.0031/0032` (removed from the repo by design) and lacked 4 repo migrations; all 4 applied to `crack_local`, no pending migrations.
  - Image coverage: all 4,200 `QuestionImage` rows have their binary locally (3,579 recall files, 495 Supabase-storage objects, 126 `/media` files).
- Security: **critical** cross-account authentication bug fixed (Supabase token cache keyed on the shared JWT header) — `ff5831a`, regression test.
- Security: subscription order endpoint sold the unlimited lifetime "legacy" plan for ₹199 when `plan` was missing/unknown — now 400 (`c5a041b`).
- Phase 2b local architecture (`c5a041b`, `1d2c85f`, `bb51b4e`):
  - `DJANGO_ENV_FILE`, `MEDIA_ROOT`, `SUPABASE_STORAGE_MIRROR_DIR`, `EMAIL_BACKEND` overrides; `backend/.env.localdev.example`; `scripts/local/make_env_localdev.py`.
  - Dev-only local auth (`LOCAL_DEV_AUTH`, forced off unless `DEBUG`), frontend `NEXT_PUBLIC_AUTH_MODE=local`.
  - Mock Razorpay (`PAYMENTS_MODE=mock`, forced off unless `DEBUG`): order → mock checkout → signed verify → webhook; 8 tests (duplicate verify/webhook, tampered signature, no stacking, expiry, owner scoping).
  - Seed accounts `student@` / `premium@` / `admin@local.test` (`seed_local_dev_users`), start/stop scripts, `docs/LOCAL_DEVELOPMENT.md`.
- UI round 1 (336 screenshots) → bugs fixed in `6ccf6b6`:
  - `/mistake-notebook` and `/study-time` crashed (array vs wrapped payload); notebook links 404'd; wrong status keys.
  - Mistake Notebook was never populated (no code created entries) → automatic capture from question-bank, practice and test answers; `backfill_mistake_notebook` (987 entries from history).
  - Study time was never recorded → server-side recording from answer timings; `backfill_study_time` (336 rows, 10.9 h from history).
  - Practice-mode answers accepted junk letters / misgraded `" B"`.
  - Verified over HTTP with the seed student (3 wrong bank answers + 19 wrong test answers → 22 notebook entries; study time recorded; invalid letter → 400) and re-captured (`screenshots\fix1`, 0 errors).
- Local connection exhaustion ("too many clients" 500s) → `CONN_MAX_AGE=0` for the threaded dev server.

- Local auth could not reach any protected page: the Next middleware gates `/dashboard`, `/questions`, `/tests`, `/admin`… on Supabase cookies, so local mode always redirected to `/login` (41 routes in two screenshot rounds showed the login page). Local mode now gates on presence cookies and makes no Supabase call (`8c2cabd`). Tablet sidebar rail (clipped Premium pills/logo, unnamed Sign-out) fixed in the same commit. Local Playwright harness added (`frontend/playwright.local.config.ts`, `tests/e2e/local/`).
- `dashboard_v3`, heatmap, revision-progress, PYQ-coverage and average-time endpoints all returned 500 (queried non-existent `TestAttempt` fields) — rewritten on real answer events (`0613c3f`).
- RAG: whole-store BM25 index with a corpus policy replaces the capped TF-IDF scan (search ~1 ms instead of ~3.5 s; constructor no longer writes to the git-tracked store; offline/total-failure extractive answers). Benchmark running (`backend/ai_eval/rag_benchmark.py`) — results in `docs/audit/RAG_BENCHMARK.md`.

## Discovery (read-only, 139 agents, each finding verified by 2 skeptics)

57 confirmed serious, 2 disputed, 241 medium/low, 55 concerns about earlier fixes. Highlights: committed production credentials (Supabase service-role key, DB passwords, an admin password literal) and committed personal-data dumps; anonymous access to every answer/explanation; Razorpay checkout blocked by the CSP; subscribers capped at 2 AI messages/day; tokens charged when AI fails and outage text persisted into question explanations; blocked users keep API access; deploy-time NEET PG import is destructive; the question rate limiter shares one budget per proxy IP. Fix wave 1 (11 file-disjoint agent groups + independent reviewers) is running.

## Findings logged for later phases

- **Data quality**: NEET PG subject tags unreliable — 696 questions tagged *Anaesthesia* (694 without topic); a random sample of 18 had ~9 clearly from other subjects. CMS also has placeholder subjects *Expert Curated* (1,285) and *Imported* (541). Plan: classifier + review CSV (never auto-applied to production).
- `FormattedText` renders raw HTML (`rehype-raw`) — check sanitisation in the security pass.

## In progress / next

1. Fix wave 1 (workflow `crack-fix-wave1`): integrate, run full suites, commit per group.
2. RAG benchmark → write `docs/audit/RAG_BENCHMARK.md`; offline mode end to end (with the AI group's `ai_engine/offline.py`).
3. UI: public review done (69 verified issues), protected-page review running (round 3) → combined polish pass → round 4 capture.
4. Playwright E2E suite on the local stack; security/performance second pass; final report.
5. Data quality: subject audit (`backend/ai_eval/subject_audit.py`).

Note: this machine has 5.9 GB RAM (heavy paging with many agents); avoid parallel `next build` / `tsc` runs.

## Test commands

```bash
# backend (from backend/): dev settings on SQLite, Sentry disabled
DATABASE_URL= SUPABASE_DATABASE_URL= DEBUG=True SENTRY_DSN= python manage.py test --parallel 1
# frontend (from frontend/)
npx tsc --noEmit -p . && npx eslint src --quiet && npm run build
```

## Recovery instructions (if interrupted)

```powershell
# whole stack (Postgres 55432, backend 8000, frontend 3000)
powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1 -Frontend prod
# stop app servers but keep the database running
powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1 -KeepDatabase
# database only
& 'C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe' -D C:\Users\DIVYANSHU\crack_local\pgdata -l C:\Users\DIVYANSHU\crack_local\logs\postgres.log start
```
