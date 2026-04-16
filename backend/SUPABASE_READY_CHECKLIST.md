# Supabase Ready Checklist

## 0) Localhost Supabase (for testing before deploy)

Start local Supabase stack (Docker required):

```bash
npx supabase start
```

Use these local values for backend and frontend while testing on localhost:

```env
# Backend DATABASE_URL (Supabase local Postgres)
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# Frontend Supabase local
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-local-anon-key-from-supabase-start-output>
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<same-as-anon-key>
NEXT_PUBLIC_AUTH_PROVIDER=supabase
NEXT_PUBLIC_USE_SUPABASE_AUTH=true
```

Then run backend migrations against local Supabase:

```bash
cd backend
python manage.py migrate
python manage.py runserver
```

And frontend:

```bash
cd frontend
npm run dev
```

## 1) Set backend database to Supabase

Set this environment variable on your backend host (DigitalOcean):

DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres

## 2) Move existing local question bank into Supabase

From repository root:

python backend/scripts/migrate_questions_to_supabase.py --database-url "postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres"

If you want to append without deleting existing question rows:

python backend/scripts/migrate_questions_to_supabase.py --database-url "postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres" --keep-existing

For localhost Supabase, use:

```bash
python backend/scripts/migrate_questions_to_supabase.py --database-url "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
```

## 3) Deploy frontend/backend

- Deploy backend after DATABASE_URL is set.
- Deploy frontend from latest main.

## 4) Smoke test

- Register a new user
- Login with that user
- Open Question Bank and verify questions are listed
- Start CMS Simulator and verify test generation works
