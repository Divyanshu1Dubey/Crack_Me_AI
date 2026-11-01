# Overnight mission — progress log

_Last updated: 2026-11-01 — fix waves 1-2 committed, dependency floors raised, local E2E suite written; fix wave 3 running_

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
- RAG: whole-store BM25 index with a corpus policy replaces the capped TF-IDF scan (search ~2 ms instead of ~3.5 s; constructor no longer writes to the git-tracked store; offline/total-failure extractive answers). Measured on a held-out test split (n=117, real PYQ explanations): success@5 0.239 → 0.547, MRR 0.168 → 0.431, nDCG@10 0.110 → 0.318 (paired bootstrap CIs exclude 0); full method and limits in `docs/audit/RAG_BENCHMARK.md`. `AI_OFFLINE_MODE=1` is the local default.
- Data quality: NEET PG subject tags agree with the source compilation for 49.8 % of questions (1,679/3,372). 1,693 corrections from the source files were applied to the **local** database only; 2,079 classifier suggestions are left for review (`docs/audit/DATA_QUALITY.md`).

## Discovery (read-only, 139 agents, each finding verified by 2 skeptics)

57 confirmed serious, 2 disputed, 241 medium/low, 55 concerns about earlier fixes. Highlights: committed production credentials (Supabase service-role key, DB passwords, an admin password literal) and committed personal-data dumps; anonymous access to every answer/explanation; Razorpay checkout blocked by the CSP; subscribers capped at 2 AI messages/day; tokens charged when AI fails and outage text persisted into question explanations; blocked users keep API access; deploy-time NEET PG import is destructive; the question rate limiter shares one budget per proxy IP.

## Fix waves (file-disjoint agent groups, each diff reviewed by an independent skeptic)

| Wave | Scope | Result |
|---|---|---|
| 1 | 57 serious + most medium findings, 11 groups | ~291 items fixed, commits `f011c1d`..`d988cec`, `61b4b2c`; backend suite 929 tests OK |
| UI reviews | public (69 verified issues) + app (156 verified issues), from 3 screenshot rounds | routed into wave 2 |
| 2 | wave-1 review problems, cross-group follow-ups, UI issues, 11 groups | ~256 items fixed, commits `0a647c5`..`88d6461` (global-shell group partial: API outage); backend suite 1,185 OK, tsc 0 errors, eslint 0 errors |
| deps | pip-audit: 32 vulnerable packages in the venv, 22 in the production tree | `606c91c`: Django 5.2.18, DRF 3.18.3, PyJWT, cryptography, requests, urllib3, sqlparse … floors; full suite OK. **Pillow stays 11.3** (moviepy 2.2.1 requires `pillow<12`) |
| 3 | 2 high + ~10 medium wave-2 review problems (free-tier answer harvesting via generated tests and the Mistake Notebook, admin lockout after deploy, screenshot entitlement, ingestion sweeper), the unfinished global shell, reviews of the 3 unreviewed wave-2 commits, docs | running (workflow `crack-fix-wave3`) |

## Local E2E suite (Playwright, `frontend/tests/e2e/local/`)

7 spec files, 156 tests over 3 viewports (desktop 1440×900, tablet 820×1180, Pixel 5): auth, question-bank practice (answer/key, Mistake Notebook + Study Time, free-tier lock, bookmarks), mock tests (start → answer → submit → result → review), payments (mock checkout UI; invalid signature, foreign order, unknown/lifetime plan, idempotent verify, stacking, webhook duplicates/forgery/refund event, admin revoke/lifetime grant, AI entitlement), AI tutor offline answer, admin console + authorization, responsive smoke (18 app pages light/dark, 6 public pages). The auth spec passed 6/6 on desktop; the rest runs after wave 3 and a rebuild.

## Findings logged for later phases

- `FormattedText` renders raw HTML (`rehype-raw`) — check sanitisation in the security pass.

## In progress / next

1. Wave 3 → full backend suite, tsc, eslint → commit per group.
2. Rebuild the frontend, restart the app servers, run the E2E suite (desktop, then tablet and mobile), screenshot round 4.
3. Security/performance second pass on the final diff; final report.

Note: this machine has 5.9 GB RAM (heavy paging with many agents). Agents run tests through a slot wrapper (2 backend runs, 1 tsc/eslint at a time). The harness stopped one background launcher task ("Restart Postgres detached") for low memory; the Postgres server it had started kept running on :55432, and the task was not restarted.

## Test commands

```bash
# backend (from backend/): dev settings on SQLite, Sentry disabled
DATABASE_URL= SUPABASE_DATABASE_URL= DEBUG=True SENTRY_DSN= python manage.py test --parallel 1
# frontend (from frontend/)
npx tsc --noEmit -p . && npx eslint src --quiet && npm run build
# local E2E (stack running, from frontend/); artifacts in E2E_OUTPUT_DIR
npx tsc -p tests/e2e/local/tsconfig.json
npx playwright test -c playwright.local.config.ts --project=desktop
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
