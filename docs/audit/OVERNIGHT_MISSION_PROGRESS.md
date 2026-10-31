# Overnight mission — progress log

_Last updated: 2026-11-01 (phase 2b in progress)_

## Where things are

| Item | Location |
|---|---|
| Git branch | `overnight-mission` (from `worktree-full-audit-fixes` @ 33532e0; tag `overnight-mission-start`) |
| Worktree | `C:\Users\DIVYANSHU\Desktop\crack_cms\.claude\worktrees\full-audit-fixes` |
| Local infra (not in git) | `C:\Users\DIVYANSHU\crack_local\` |
| Isolated Postgres 16 | data `crack_local\pgdata`, **127.0.0.1:55432**, superuser `crack_super` (trust, localhost only) |
| Pristine restore | database `crack_restore` (never modified) |
| Working database | database `crack_local` (copy of `crack_restore` + 4 new migrations) |
| Restored media | `crack_local\media` (copy of checkout `backend\media`, 11,549 files) |
| Supabase Storage mirror | `crack_local\storage\<bucket>\...` (1,095 objects from the storage zip) |
| Logs | `crack_local\logs\` (restore errors, migrations diff, postgres log) |

The existing PostgreSQL service on :5432 is **not** used or modified.

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
- Security: **critical** cross-account authentication bug fixed (Supabase token cache keyed on the shared JWT header) — commit `ff5831a`, regression test.
- Local env plumbing: `DJANGO_ENV_FILE`, `MEDIA_ROOT`, `SUPABASE_STORAGE_MIRROR_DIR`, `EMAIL_BACKEND` overrides; `backend/.env.localdev.example`; `scripts/local/make_env_localdev.py`.

## In progress / next

1. Dev-only local auth (backend + frontend), mock payments, AI offline mode, seed local test users.
2. Start/stop scripts + `docs/LOCAL_DEVELOPMENT.md`.
3. Triage discovery workflow results (`crack-discovery`, running).
4. RAG benchmark, UI screenshot review, E2E suite.

## Recovery instructions (if interrupted)

```powershell
# start the isolated database
& 'C:\Program Files\PostgreSQL\16\bin\pg_ctl.exe' -D C:\Users\DIVYANSHU\crack_local\pgdata -l C:\Users\DIVYANSHU\crack_local\logs\postgres.log start
# backend against the restored DB (from backend/)
$env:DJANGO_ENV_FILE='.env.localdev'; python manage.py runserver 8000
```
