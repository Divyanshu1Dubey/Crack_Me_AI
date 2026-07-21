# Supabase Setup

> Migration from local SQLite to Supabase Postgres + auth bridge configuration.

---

## Overview

CrackCMS uses Supabase as:
1. **Identity provider** (Supabase Auth — primary auth path)
2. **Alternative Postgres database** (replacing local SQLite for production)

The platform supports running **either**:
- Local SQLite (dev / single-server)
- Supabase Postgres + Supabase Auth (production recommended)

Or a **hybrid**:
- Supabase Auth + local SQLite (when migrating auth but not yet DB)

---

## 0. Local Supabase (Docker)

For testing before deploy:

```bash
npx supabase start
```

Then use these local values:

### Backend `.env`
```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

### Frontend `.env.local`
```env
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-local-anon-key-from-supabase-start-output>
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<same-as-anon-key>
NEXT_PUBLIC_AUTH_PROVIDER=supabase
NEXT_PUBLIC_USE_SUPABASE_AUTH=true
```

Run migrations:
```bash
cd backend
python manage.py migrate
python manage.py runserver
```

Frontend:
```bash
cd frontend
npm run dev
```

---

## 1. Backend Database → Supabase Postgres

Set `DATABASE_URL` in your production backend environment:

```env
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres
```

Django automatically uses Postgres when `DATABASE_URL` is set (via `dj_database_url`).

### Connection pooling

For serverless or high-concurrency deploys, use Supabase's transaction-mode pooler:

```
DATABASE_URL=postgresql://postgres.[ref]:[pwd]@aws-0-[region].pooler.supabase.com:6543/postgres?pgbouncer=true
```

---

## 2. Migrate Existing Local Question Bank to Supabase

From repository root:

```bash
python backend/scripts/migrate_questions_to_supabase.py \
  --database-url "postgresql://postgres:[PASSWORD]@db.[ref].supabase.co:5432/postgres"
```

To append without deleting existing rows:

```bash
python backend/scripts/migrate_questions_to_supabase.py \
  --database-url "..." \
  --keep-existing
```

For localhost Supabase:

```bash
python backend/scripts/migrate_questions_to_supabase.py \
  --database-url "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
```

---

## 3. Enable Supabase Auth on Frontend

Set env vars on Vercel:

```env
NEXT_PUBLIC_SUPABASE_URL=https://[ref].supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_USE_SUPABASE_AUTH=true
```

Frontend `lib/supabase.ts::isSupabaseAuthEnabled()` returns true → `api.ts` attaches Supabase JWT.

---

## 4. Supabase Bridge (Backend)

`backend/accounts/supabase_auth.py` validates Supabase tokens on the Django side:

```python
# Pseudocode
def validate_supabase_token(token):
    response = httpx.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
    )
    if response.status_code == 200:
        user_data = response.json()
        return get_or_create_custom_user(user_data)
```

---

## 5. Deploy Order

1. Set `DATABASE_URL` on backend host
2. Run migrations (`build.sh` does this automatically)
3. Set Supabase env vars on frontend
4. Deploy frontend (from `main`)
5. Smoke test:
   - Register a new user
   - Login
   - Open Question Bank
   - Start CMS Simulator

---

## 6. Single-Device Sessions with Supabase

Supabase Auth tokens are JWTs that can be used directly with the Django bridge. `CustomUser.session_key` + `UserDevice` still enforce single-device — the Supabase JWT is just the auth mechanism.

If you need to invalidate a Supabase session:
1. Mark `UserDevice.is_active = False` on backend
2. Next request from that device returns `code: 'session_invalid'`
3. Frontend `api.ts` interceptor calls `supabase.auth.signOut()` to clear the Supabase session

---

## 7. Supabase Row-Level Security (RLS)

CrackCMS does **not** use Supabase RLS today — it accesses Postgres directly via `DATABASE_URL`. Supabase is purely an auth + DB host.

If you later want to expose Supabase directly to the frontend (bypassing Django), enable RLS:

```sql
ALTER TABLE accounts_customuser ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_self ON accounts_customuser
  FOR SELECT USING (auth.uid() = id);
```

---

## 8. Backup Strategy

| What | Backup |
|---|---|
| Supabase Postgres | Automatic daily (Pro plan); on-demand via Supabase dashboard |
| Question fixture | `backend/questions_fixture.json` (committed) |
| RAG store | `backend/chroma_db/rag_store.sqlite3` (committed) |

---

## 9. See Also

- [`API_REFERENCE.md`](../API_REFERENCE.md) — auth endpoints
- [`AUTHENTICATION.md`](../AUTHENTICATION.md) — full auth flow
- [`DATA_MODEL.md`](../DATA_MODEL.md) — schema
- [`SCALING_ROADMAP.md`](../SCALING_ROADMAP.md) — when to migrate off SQLite
