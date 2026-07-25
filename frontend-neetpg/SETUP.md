# NEET PG Frontend — Setup

## First-time setup

```bash
cd frontend-neetpg
npm install
cp .env.local.example .env.local
# Edit .env.local and fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY,
# and NEXT_PUBLIC_API_URL (use http://localhost:8000/api for local dev).
npm run dev
```

## Required env vars (see `.env.local.example`)

| Var | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Django backend URL (e.g. `http://localhost:8000/api`) |
| `NEXT_PUBLIC_API_FALLBACK_URL` | Optional failover base URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL — same project as the CMS site |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key — same project as the CMS site |
| `NEXT_PUBLIC_SITE_URL` | Public URL (e.g. `https://neetpg.crackme-ai.com`) |
| `NEXT_PUBLIC_SEO_BRAND` | Brand name (default: `CrackPG`) |
| `NEXT_PUBLIC_SEO_TAGLINE` | SEO tagline |
| `NEXT_PUBLIC_DEFAULT_TRACK` | Analytics track (default: `neet_pg`) |

If Supabase env vars are missing, `src/lib/supabase.ts:13-15` throws and
`AuthProvider` (`src/lib/auth.tsx:66`) crashes the entire React tree with
HTTP 500. Always set these before running the app.

## Routes (this app, not the CMS one)

| Path | Surface |
|---|---|
| `/` | Landing |
| `/login` | Sign in |
| `/signup` | Register |
| `/questions` | Question list (PYQ + practice) |
| `/questions/[id]` | Single question |
| `/tests` | Grand test / simulator |
| `/flashcards` | Spaced-repetition flashcards |
| `/analytics` | Performance dashboard |
| `/bookmarks` | Saved questions |
| `/ai-tutor` | AI chat tutor |
