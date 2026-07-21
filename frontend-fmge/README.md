# CrackFMGE — Foreign Medical Graduate Examination Prep

Independent Next.js frontend for the FMGE exam track. Shares the
Django backend (`backend/`) and Supabase project with the main CMS site.

## Run locally

```bash
cd frontend-fmge
cp .env.local.example .env.local
npm install
npm run dev -- --webpack
```

## What's different from the CMS site

- Brand color `#d97706` (warm amber) via `[data-track="fmge"]`.
- Display font `Plus Jakarta Sans` for a welcoming, rounded look.
- New `lib/fmge-blueprint.ts` encodes the NBE's 19-subject / 300-question
  blueprint and provides `blueprintForMock()`, `estimatePassProbability()`,
  and `isPassing()` helpers.
- Each question request sends `exam_type=fmge`.
- Landing page surfaces the full blueprint subject list.

## Deploy

Standalone Vercel project, root directory `frontend-fmge`, pointing at
the shared Django backend.
