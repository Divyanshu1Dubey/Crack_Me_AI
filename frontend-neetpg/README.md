# CrackPG — NEET PG Preparation

Independent Next.js frontend for the NEET PG exam track. Shares the
Django backend (`backend/`) and Supabase project with the main CMS site.

## Run locally

```bash
cd frontend-neetpg
cp .env.local.example .env.local       # then fill in NEXT_PUBLIC_API_URL etc.
npm install
npm run dev -- --webpack
```

App boots at `http://localhost:3000`.

## Environment

See `.env.local.example`. The two required values are
`NEXT_PUBLIC_API_URL` (the shared Django backend) and the Supabase keys.

## Deploy

This folder is a standalone Vercel project. Configure:

- Build command: `next build`
- Output directory: `.next`
- Root directory: `frontend-neetpg`

## What this site covers

- NEET PG PYQ question bank (subject + topic + year + difficulty filters)
- AI-powered explanations
- Grand tests with All India rank prediction
- Token economy (shared with the CMS site — one Stripe account)

## What this site does NOT cover yet

- Rank predictor UI (`components/RankPredictor.tsx`) — Phase 4
- College predictor (`app/(neetpg)/colleges/page.tsx`) — Phase 4
- Video lecture index — Phase 5
- INI-CET cross-link — Phase 5
