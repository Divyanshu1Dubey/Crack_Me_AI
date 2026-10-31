# Running CrackLabs locally (restored backup, no Supabase/Railway)

Everything runs on this machine. Nothing talks to production: the backend
loads `backend/.env.localdev` (never `backend/.env`), sign-in uses a dev-only
local auth mode, payments use a mock provider, mail is written to files.

## One-time setup (already done on this machine)

| Piece | Location |
|---|---|
| Isolated PostgreSQL 16 cluster | `%USERPROFILE%\crack_local\pgdata` → `127.0.0.1:55432`, superuser `crack_super` (trust, localhost only) |
| Pristine restore of the production backup | database `crack_restore` (do not use for development) |
| Working database | database `crack_local` |
| Media (recall images, uploads) | `%USERPROFILE%\crack_local\media` |
| Supabase Storage mirror (question images, videos) | `%USERPROFILE%\crack_local\storage\<bucket>\...` |
| Captured outgoing mail | `%USERPROFILE%\crack_local\mail` |
| Logs | `%USERPROFILE%\crack_local\logs` |

`backend/.env.localdev` is generated (gitignored):

```powershell
python scripts/local/make_env_localdev.py --with-ai-keys   # copies ONLY AI provider keys from backend/.env
```

Seed the local test accounts (DEBUG-only command; password = `LOCAL_SEED_PASSWORD` in `backend/.env.localdev`):

```powershell
cd backend; $env:DJANGO_ENV_FILE='.env.localdev'; python manage.py seed_local_dev_users
```

| Account | Purpose |
|---|---|
| `student@local.test` | free student |
| `premium@local.test` | student with an active 1-year plan (unlimited AI) |
| `admin@local.test` | admin (`/admin` pages, Django admin) |

## Start / stop

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1          # dev frontend (hot reload)
powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1 -Frontend prod   # next build + next start
powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1           # stops frontend, backend, database
powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1 -KeepDatabase
```

- Frontend: http://localhost:3000 — Backend: http://127.0.0.1:8000/api/health/ — Django admin: http://127.0.0.1:8000/admin/
- The frontend is started with `NEXT_PUBLIC_AUTH_MODE=local`, `NEXT_PUBLIC_PAYMENTS_MODE=mock`, `NEXT_PUBLIC_API_URL=http://localhost:8000/api`.
- Run the scripts from a normal console. (When invoked from another script with piped output, the call returns only when the servers stop, because the children inherit the pipe.)

## Local-only switches (all refuse to work unless `DEBUG=True`)

| Switch | Effect |
|---|---|
| `DJANGO_ENV_FILE=.env.localdev` | load the local env file instead of `backend/.env` |
| `LOCAL_DEV_AUTH=1` | `/api/auth/local/{login,register,refresh}/` + SimpleJWT bearer auth |
| `PAYMENTS_MODE=mock` | Razorpay replaced by `accounts/payments_mock.py`; `/api/auth/subscribe/mock-checkout/` simulates the checkout popup |
| `AI_OFFLINE_MODE=1` | no external LLM calls (see RAG notes) |
| `SUPABASE_STORAGE_MIRROR_DIR` | serve Supabase-storage image URLs from the local mirror |
| `EMAIL_BACKEND=...filebased...` | write mail to `EMAIL_FILE_PATH` |

## Rebuilding the database from the backups

```powershell
python C:\Users\DIVYANSHU\crack_local\split_dump.py <db_cluster.sql> <out_dir>     # roles.sql + postgres_db.sql (sanitised)
psql -h 127.0.0.1 -p 55432 -U crack_super -d postgres -f roles.sql
psql -h 127.0.0.1 -p 55432 -U crack_super -d postgres -c "CREATE DATABASE crack_restore TEMPLATE template0"
psql -h 127.0.0.1 -p 55432 -U crack_super -d crack_restore -f postgres_db.sql
psql -h 127.0.0.1 -p 55432 -U crack_super -d postgres -c "CREATE DATABASE crack_local TEMPLATE crack_restore"
cd backend; $env:DJANGO_ENV_FILE='.env.localdev'; python manage.py migrate
```

Expected restore errors (harmless): pgvector types/functions (not installed; embeddings are stored as JSON), Supabase Vault, PG17-only privileges.
