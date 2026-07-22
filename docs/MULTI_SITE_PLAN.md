# Multi-Site Plan: NEET PG / USMLE / FMGE

> Companion document for the CrackCMS platform expansion.
> **Status**: Phase 1 (single CMS site fixes) complete; this document captures
> the architecture, branding, and feature matrix for the 3 new exam-prep sites.

## 1. Context

The CrackCMS platform currently serves **UPSC CMS** preparation. The student
base has been asking for **NEET PG**, **USMLE**, and **FMGE** modes. Rather
than rebrand the existing site, the plan is to launch **3 sibling sites** —
each with its own visual identity, content library, and exam-specific UX —
that all read from the same Django backend + Supabase auth.

## 2. Architecture Decision

| Concern | Decision | Rationale |
|---|---|---|
| Repo layout | Separate `frontend-neetpg/`, `frontend-usmle/`, `frontend-fmge/` folders | Lets each site own its own `package.json`, brand assets, env vars, and `vercel.json` — independent deploys, independent rollback, independent CMS |
| Backend | Shared `backend/` (Django) | The `Question` model already has `exam_type` enum (`cms / neet_pg / usmle / fmge`). Filter via `?exam_type=neet_pg` on existing `/api/questions/` endpoint |
| Auth | Shared Supabase project | `CustomUser` upserts by email in `supabase_rest_auth.py`; users signed up on one site are recognised on all sites. Single project = single admin console |
| Brand isolation | Each site ships its own `globals.css` palette, logo, tagline, fonts | The existing `[data-track="neet_pg|usmle|fmge"]` palette tokens in `frontend/src/app/globals.css` (lines 99–165) become the canonical palette for each new site |

## 3. Folder Structure

```
crack_cms/                    # existing repo
├── backend/                  # Django API — shared
├── frontend/                 # UPSC CMS site (existing, fixes applied)
├── frontend-neetpg/          # NEW — NEET PG site
│   ├── package.json
│   ├── vercel.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── .env.local.example
│   ├── middleware.ts
│   ├── public/
│   │   ├── neetpg-logo.png
│   │   └── manifest.json
│   └── src/
│       ├── app/
│       │   ├── layout.tsx           # sets data-track="neet_pg"
│       │   ├── page.tsx             # NEET PG landing
│       │   ├── questions/           # Question Bank
│       │   ├── tests/               # NEET PG grand tests
│       │   ├── ai-tutor/
│       │   ├── analytics/
│       │   ├── subscription/
│       │   └── login/
│       ├── components/
│       ├── lib/
│       │   ├── api.ts               # NEXT_PUBLIC_API_URL→ shared backend
│       │   ├── auth.tsx             # copy verbatim
│       │   ├── supabase.ts          # copy verbatim
│       │   ├── utils.ts
│       │   └── seo.ts               # NEET PG specific
│       └── ...
├── frontend-usmle/           # NEW — USMLE site (Step 1/2/3)
└── frontend-fmge/            # NEW — FMGE site
```

## 4. Brand Identity Matrix

Each site is a **completely different visual identity** — different primary
color, different fonts (where appropriate), different landing-page hero,
different copy, and exam-specific navigation.

### 4.1 NEET PG — "CrackPG"

| Element | Value |
|---|---|
| Tagline | "Conquer NEET PG — India's #1 AI medical PG prep" |
| Primary | `#059669` (medical emerald) — already in `[data-track="neet_pg"]` |
| Accent | `#10b981` |
| Font (body) | Manrope (same — already loaded for readability of long question text) |
| Font (display) | Space Grotesk (same) |
| Logo | `neetpg-logo.png` — circular, emerald-green, "PG" monogram |
| Hero motif | Stethoscope + ECG waveform |
| Differentiator | Pre-clinical + clinical + para-clinical subject segregation; All India rank predictor |

### 4.2 USMLE — "CrackUSMLE"

| Element | Value |
|---|---|
| Tagline | "Match into your dream residency — Step 1, 2 CK & 3" |
| Primary | `#7c3aed` (deep purple) — already in `[data-track="usmle"]` |
| Accent | `#a78bfa` |
| Font (body) | **Inter** (clinical, US-default medical app feel) |
| Font (display) | **Space Grotesk** |
| Logo | `usmle-logo.png` — circular, purple, "US" + caduceus |
| Hero motif | USMLE Step pathway (Step 1 → Step 2 CK → Step 3) |
| Differentiator | Step-specific question banks; NBME-style % correct vs score correlation; First Aid & UWorld cross-references |

### 4.3 FMGE — "CrackFMGE"

| Element | Value |
|---|---|
| Tagline | "Pass FMGE on the first attempt — 19 subjects, 300 MCQs" |
| Primary | `#d97706` (warm amber) — already in `[data-track="fmge"]` |
| Accent | `#f59e0b` |
| Font (body) | Manrope |
| Font (display) | **Plus Jakarta Sans** (welcoming, accessible) |
| Logo | `fmge-logo.png` — circular, amber, "FM" + mortarboard |
| Hero motif | Indian medical graduate arrow abroad |
| Differentiator | NBE pattern simulator; subject weighting as per FMGE blueprint; previous 5-year trend analysis |

## 5. Feature Matrix

Features that **all 4 sites share** (from shared backend):

- PYQ browser with subject/year/difficulty filters
- AI explanation (mnemonics, why-wrong, textbook reference)
- Token economy (daily + weekly + purchased)
- Bookmarks, flashcards (SM-2)
- Discussion threads per question
- Analytics dashboard, leaderboard
- Stripe token purchase
- Supabase auth (email + Google + magic link)

Features that are **NEET PG-specific**:

| Feature | Why | Files |
|---|---|---|
| Pre/Para/Clinical subject segmentation | NEET PG aspirants study in 3 distinct phases | `app/(neetpg)/questions/page.tsx` — extra subject-group filter |
| All India rank predictor | After grand test, predicts AIR using past year distributions | `components/RankPredictor.tsx` |
| INI-CET cross-link | NEET PG aspirants often take INI-CET too | sidebar link + cross-exam topic map |
| College predictor (state/management quota) | High demand for counselling | `app/(neetpg)/colleges/page.tsx` — read-only directory |
| Video lecture index (Marrow/Prepladder pointer) | Aspirants expect a video companion | read-only catalog page |

Features that are **USMLE-specific**:

| Feature | Why | Files |
|---|---|---|
| Step 1 / Step 2 CK / Step 3 mode switcher | USMLE has 3 distinct exams | `components/StepSwitcher.tsx`, sidebar group |
| NBME-style % correct → 3-digit score estimator | Aspirants obsess over score correlation | `components/ScoreEstimator.tsx` |
| First Aid chapter cross-reference | Standard study companion | `app/(usmle)/first-aid/page.tsx` |
| UWorld-style "explanations everywhere" toggle | UWorld raises the bar for explanations | `components/ExplanationToggle.tsx` |
| Residency matcher (specialty quiz) | Aspirants want to know which specialties fit | `app/(usmle)/residency-match/page.tsx` |
| Visa timeline tracker (IMG) | Real-world need for international grads | `app/(usmle)/timeline/page.tsx` |
| Drug name normalisation (US brand ↔ INN) | Confusing for IMGs | utility in `lib/us-drugs.ts` |

Features that are **FMGE-specific**:

| Feature | Why | Files |
|---|---|---|
| 19-subject NBE blueprint weighting | FMGE is strictly 19 subjects | `lib/fmge-blueprint.ts` |
| NBE-pattern 300-question mock test | The exam is exactly 300 Qs / 5 hrs / 2 sessions | `components/FMGESimulator.tsx` |
| Trend analysis (last 5 years) | FMGE has high-repeat rate from past papers | `app/(fmge)/trends/page.tsx` |
| Foreign medical graduate counselling | Aspirants need state registration info | read-only page |
| Subject priority matrix | Tells student which subjects to focus on | dashboard widget |

## 6. Backend Changes (minimal)

The `Question` model already has `exam_type`. **Only serializer / API surface
additions are needed:**

| File | Change |
|---|---|
| `backend/questions/serializers.py` | Add `exam_type` to `QuestionListSerializer.fields` and `QuestionDetailSerializer.fields`; add `exam_type` + `exam_track` to `SubjectSerializer.fields` |
| `backend/questions/views.py` | `question_stats` action: add `exam_type` query param support (currently uses `exam_source`) |
| `backend/questions/management/commands/import_neet_pg.py` | Bug fix line 237: also set `exam_type='neet_pg'` (currently only `exam_source='NEET PG'`) |
| `backend/.env.example` | Add `CORS_ALLOWED_ORIGINS` entries for `neetpg.crackme-ai.com`, `usmle.crackme-ai.com`, `fmge.crackme-ai.com` |

**No model migration is required.**

## 7. Deployment

| Site | Vercel project | Domain | Backend |
|---|---|---|---|
| UPSC CMS (existing) | `crack-cms` | `cracklabs.app` | `crackcms-vsthc.ondigitalocean.app/api` |
| NEET PG | `crack-neetpg` | `neetpg.crackme-ai.com` | same |
| USMLE | `crack-usmle` | `usmle.crackme-ai.com` | same |
| FMGE | `crack-fmge` | `fmge.crackme-ai.com` | same |

Each Vercel project reads:
- `NEXT_PUBLIC_API_URL` → shared Django backend
- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` → shared Supabase project
- `NEXT_PUBLIC_SITE_URL` → its own domain (used for SEO + auth callbacks)
- `NEXT_PUBLIC_SEO_BRAND` → "CrackPG" / "CrackUSMLE" / "CrackFMGE"
- `NEXT_PUBLIC_DEFAULT_TRACK` → "neet_pg" / "usmle" / "fmge"

## 8. Reuse Catalogue (what each new site copies verbatim from `frontend/`)

- `src/lib/api.ts` — only the production API URL constant needs to change
- `src/lib/auth.tsx` — copy verbatim
- `src/lib/supabase.ts` — copy verbatim
- `src/lib/utils.ts` — copy verbatim
- `src/components/ui/*` — copy verbatim (Radix wrappers)
- `src/components/FormattedText.tsx` — copy verbatim
- `src/components/PasswordStrength.tsx`, `BackendWarmup.tsx`, `DiscussionThread.tsx` — copy verbatim
- `src/utils/supabase/*` — copy verbatim

## 9. Per-Site Replacements

Each new site MUST customise:

- `src/lib/seo.ts` — site-specific title, description, keywords, OG image
- `src/components/BrandMark.tsx` — site-specific logo, wordmark, tagline
- `src/components/Header.tsx` — site-specific `pageTitles` map
- `src/components/Sidebar.tsx` — site-specific nav items + tagline
- `src/components/BottomNav.tsx` — site-specific mobile nav
- `src/components/ExamSwitcher.tsx` — removed (each site is mono-exam)
- `src/components/ExamCountdown.tsx` — site-specific exam dates
- `src/app/globals.css` — site-specific palette tokens (already partially defined under `[data-track="…"]`)
- `src/app/layout.tsx` — `defaultTheme` and `<html data-track="…">`

## 10. Rollout Phases

| Phase | Scope | Effort |
|---|---|---|
| ✅ Phase 1 (done in this PR) | UPSC CMS bug fixes + audit tool | 1 PR |
| Phase 2 | Scaffold `frontend-neetpg/` with shared lib + brand + landing | 1 week |
| Phase 3 | NEET PG Question Bank + AI Tutor wired | 1 week |
| Phase 4 | NEET PG rank predictor + college predictor | 3 days |
| Phase 5 | Scaffold `frontend-usmle/` + scaffold `frontend-fmge/` in parallel | 1 week |
| Phase 6 | USMLE Step switcher + score estimator | 1 week |
| Phase 7 | FMGE simulator + blueprint weighting | 4 days |
| Phase 8 | Production deploy + DNS + monitoring | 2 days |

## 11. Success Criteria

- All 3 sites load on their own domain with distinct visual identity
- All 4 sites share one backend and one auth
- A user signed up on NEET PG can log into USMLE with the same email
- Question counts per exam surface correctly (CMS ~1900, NEET PG growing, USMLE/FMGE seeded)
- Each site has a working question bank with at least 200 sample questions per exam type
- Stripe token purchase works on all 4 sites
