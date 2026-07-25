---
title: NEET PG QA Pass — Playwright-Driven Visual + Content Audit
date: 2026-07-25
status: approved
scope: frontend-neetpg/
---

# NEET PG QA Pass — Design

## Goal

Drive the `frontend-neetpg/` Next.js app to production-ready quality by:
1. Identifying every UI / functional / content bug across all major surfaces
2. Fixing each bug in isolation (one-at-a-time)
3. Re-verifying with Playwright after every fix
4. Producing a final QA report with severity breakdown and before/after screenshots

## Scope (In)

- **Frontend**: `frontend-neetpg/` only (Next.js 16 + React 19 + Tailwind 4)
- **Surfaces**: landing, practice, PYQ, simulator, flashcards, analytics, bookmarks, AI tutor, auth
- **Categories**: UI bugs, UX gaps (student POV), question content correctness
- **Sample size**: 20–30 random questions per category
- **Backend content fixes**: only the specific questions Playwright flags; via JSON edit per fixture-first rule

## Scope (Out — Explicit Non-Goals)

- `frontend/` (main Next.js app — INICET lives there; deferred to a separate pass)
- `frontend-fmge/`, `frontend-usmle/`, `mobile-app/`
- Backend code changes (only content/JSON edits via `_export_fixture.py` workflow)
- AI provider config, auth flow changes, token economy logic
- Refactoring unrelated code (per CLAUDE.md "minimal, targeted changes")
- New features

## Approach

**Playwright-driven visual + functional crawl with one-at-a-time fix loop.**

Each Playwright run captures: console errors, network failures, screenshots at 3 viewports (375×812 mobile, 768×1024 tablet, 1440×900 desktop), and DOM snapshots. Each bug gets logged, triaged P0/P1/P2, fixed in isolation, and re-verified.

## Surface Area (Crawl Order)

1. `/` — Landing (hero, features, CTAs, testimonials)
2. `/auth/login` and `/auth/signup` — Onboarding
3. `/practice` — Random/custom topic practice
4. `/pyq` — Previous Year Questions by year
5. `/simulator` — Timed mock test
6. `/flashcards` — SM-2 spaced repetition
7. `/analytics` — Performance dashboard
8. `/bookmarks` — Saved questions
9. `/ai-tutor` — Chat interface + token economy UX

## Verification Layers (Per Surface)

| Layer | Check | Tool |
|---|---|---|
| Render | No console errors, no React hydration warnings | `browser_console_messages` |
| Network | All API calls return 2xx; no 4xx/5xx | `browser_network_requests` |
| Layout | No overflow, no overlap, no clipping | `browser_take_screenshot` @ 3 viewports |
| Interactivity | Every button/link/form clickable; expected state change | `browser_click` / `browser_fill_form` |
| Content | Sampled Qs have stem + 4 distinct options + valid correctAnswer + explanation + image (if `is_image_based`) | `browser_evaluate` + `browser_snapshot` |
| Auth | Login/signup/logout flows; protected routes redirect when unauthenticated | Full Playwright flow |

## Severity Tiers

- **P0 (blocker)**: app crashes, blank page, auth broken, all questions fail to load → fix immediately
- **P1 (visible regression)**: broken button, wrong content, layout breaks on a common viewport, console error on happy path → fix in this pass
- **P2 (cosmetic)**: minor spacing, polish, edge case on uncommon viewport → log + queue (may defer)

## Fix Loop (Per Bug)

1. Playwright identifies bug → log to `.playwright-mcp/qa-log.md` with: severity, surface, timestamp, repro, expected, actual, console output, network codes
2. Triage → fix in isolation (one commit, one bug)
3. Commit with conventional message: `fix(neetpg): <surface> — <one-line summary>`
4. Re-run Playwright on that surface only → confirm green
5. Update `qa-log.md` with commit hash + green timestamp

## Random Question Sampling (Content Correctness)

- Pull list from `GET /api/questions/?exam=NEETPG&limit=500`
- Use `Math.random()` (in `browser_evaluate`) to pick 20 IDs per category (PYQ, practice, flashcard)
- Visit `/practice/<id>` (or equivalent URL pattern) for each
- Screenshot + assert: non-empty stem, 4 distinct non-empty options, valid `correctAnswer`, non-empty `explanation`, image present if `is_image_based=true`

## Pre-Flight Checks

Before any Playwright run:
1. `cd frontend-neetpg && npm run build` — must succeed
2. `curl http://localhost:3000/` — must return 200
3. `curl http://localhost:8000/api/questions/random/?count=1` — must return valid question

If any fails → stop, report, do not fix infra in this pass.

## Bug Log Format

Each entry in `.playwright-mcp/qa-log.md`:

```
## [P0/P1/P2] [surface] YYYY-MM-DD HH:MM
- Repro: <steps>
- Expected: <behavior>
- Actual: <behavior>
- Console: <errors>
- Network: <status codes>
- Fix: <commit hash or "pending">
- Verified: <timestamp + green check or "open">
```

## Definition of Done

This pass is complete when:
1. All 9 surfaces crawled
2. All P0/P1 bugs fixed + verified
3. All 60–90 sampled questions pass content checks
4. Each fix = one commit with clear message
5. Final report at `.playwright-mcp/qa-final-report.md`:
   - Total bugs found (by severity)
   - Total commits made
   - Remaining P2/punted issues
   - Screenshots before/after for each fix

## Honest Limitations

- "Zero bugs" is not achievable — new edge cases will surface after this pass
- Student-POV UX is partly subjective; I'll surface gaps but some are judgment calls
- Question content correctness is bounded by medical knowledge — I can spot obvious errors (wrong answer for a question where options A/B/C are clearly contradicted by standard textbooks) but I cannot certify every Q
- "Production ready" depends on traffic patterns I can't observe from here; this pass raises the bar but doesn't define what your bar is

## Out-of-Scope Findings

Any bug found in `frontend/` (main app), backend code, or other frontends will be **logged but not fixed** in this pass — they're separate sub-projects per the brainstorming guidance on decomposition.