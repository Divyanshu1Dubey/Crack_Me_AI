# Supabase Ready Checklist

## 1) Set backend database to Supabase

Set this environment variable on your backend host (Render):

DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres

## 2) Move existing local question bank into Supabase

From repository root:

python backend/scripts/migrate_questions_to_supabase.py --database-url "postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres"

If you want to append without deleting existing question rows:

python backend/scripts/migrate_questions_to_supabase.py --database-url "postgresql://postgres:[YOUR-PASSWORD]@db.ryuvcdthjnxyetdyjbph.supabase.co:5432/postgres" --keep-existing

## 3) Deploy frontend/backend

- Deploy backend after DATABASE_URL is set.
- Deploy frontend from latest main.

## 4) Smoke test

- Register a new user
- Login with that user
- Open Question Bank and verify questions are listed
- Start CMS Simulator and verify test generation works
