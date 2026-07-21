# CrackUSMLE — USMLE Step 1, 2 CK & 3 Prep

Independent Next.js frontend for the USMLE exam track. Shares the
Django backend (`backend/`) and Supabase project with the main CMS site.

## Run locally

```bash
cd frontend-usmle
cp .env.local.example .env.local
npm install
npm run dev -- --webpack
```

## What's different from the CMS site

- Brand color `#7c3aed` (deep purple) via `[data-track="usmle"]`.
- Body font `Inter`, display font `Space Grotesk`.
- Landing page exposes a Step 1 / 2 CK / 3 switcher.
- New `lib/step.ts` provides score estimation (Step 1 / 2 CK / 3 → 3-digit score).
- New `lib/us-drugs.ts` annotates US brand names with INN/INNs for IMGs.
- Each question request sends `exam_type=usmle`.

## Score estimator example

```ts
import { estimateStepScore, isPassing } from "@/lib/step";

const score = estimateStepScore(72, "step1"); // → ~232
const passing = isPassing("step1", score);   // → true
```

## Deploy

Same pattern as the NEET PG site — standalone Vercel project, root
directory `frontend-usmle`, pointing at the shared Django backend.
