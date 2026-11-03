# Full-stack audit & repair — 2026-10-31

Branch: `worktree-full-audit-fixes`. Every item below was reproduced or
verified by reading code, and fixed in code; regression tests live in
`backend/questions/tests/test_audit_regressions_2026_10.py`.

## Critical (security / money / data)

| Area | Problem | Fix |
|---|---|---|
| `QuestionViewSet.get_permissions` | Ignored `@action(permission_classes=...)`; unlisted actions were **AllowAny**. Anonymous users could `remove-from-bank`, `unremove-from-bank`, `merge-duplicates` and **rewrite correct answers** via `resolve-dispute` (reproduced on a DB copy). | Admin actions listed explicitly; decorator permissions honoured for all other actions. |
| Per-question AI (`ai/concept`, `why_correct`, `clinical`, `mnemonic`) | Anonymous GETs called a non-existent `generate_text`, then **overwrote stored AI content with template text**. | Real `AIService` call, AI only for logged-in users, never persist fallback text, never overwrite non-empty fields. |
| `generate-explanation` | Method lived on the image viewset (AttributeError); failure text `"AI generation failed: <exc>"` was saved into the explanation. | Moved to `QuestionViewSet` with admin permission; failures never saved. |
| Test submit | Client-supplied answer list trusted (foreign ids, duplicates → 500, omitted wrong answers → 100% accuracy, XP farming); no lock against double submit. | Only the test's questions, deduped, scored against the full paper, row-locked. |
| Freemium gate on tests | Used stored `num_questions` (default 20, never set by the mock builder) → 100-question premium mocks were free. | Gate + badge use the real question count; builder records `num_questions`. |
| Test visibility | Every student's generated tests were published to everyone; unpublished tests startable. | Non-admins see official published tests + their own. |
| Payments | Verify + webhook could both activate (stacked periods); a signed payment for an **unknown order granted a lifetime plan**. | Compare-and-set activation; unknown orders rejected and logged. |
| Subscriptions | Only the newest active row was considered: a stacked monthly hid the 1-year/lifetime unlimited AI and, on expiry, flipped `is_subscribed` off. | All active rows evaluated; best live one returned. |
| Token refunds | Refunds raised the high-water marks (minting permanent purchased tokens) and refunded bypassed (subscriber) calls. | Exact-pool reversal recorded per request; no refund when nothing was consumed. |
| Quests | No generator; client could set `xp_reward`/progress, re-claim, delete-and-reclaim. | Server-generated daily quests, progress from real activity, one validated claim. |
| Knowledge-base ask | Unmetered LLM access; admin endpoints `AllowAny` when `DEBUG`. | Freemium cap + token metering + throttle; no DEBUG relaxation. |
| Scholarship verify | Same question resubmitted under `"1"`, `"01"`… with A–D passed 5/5. | Exactly 5 distinct, scholarship-eligible questions. |
| Admin revenue KPI | Computed from public, forgeable `payment_success` events. | Computed from `PaymentAttempt` / users. |

## Broken features fixed

- Missing migrations (quests, mistake notebook, study time, TopicNote fields, indexes) — those tables did not exist.
- `questions/0019` failed on any DB with existing questions (callable default evaluated once ⇒ duplicate UUIDs).
- Feedback endpoints 500 (`rest_framework.throttles` import); analytics ingest + topic-note generate 500 (undefined throttle scopes).
- Practice-mode state (flag/confidence/time/elimination) used non-existent `QuestionBookmark` fields → new `QuestionPracticeState`.
- TopicNote: fields referenced by serializers/views/pages added; admin CRUD route `questions/topic-notes/library/` (the old `notes/` prefix was shadowed by personal notes).
- `/practice` page and question components called `/api/api/...` (404).
- Admin ingestion pages were server components calling the authenticated API (always empty).
- `load_exam_fixture` crashed on the first row (`clean` used before assignment).
- NameErrors: `Sum` (study time), `Http404` (mistake notebook / quests); `list_images_facets` alias; image `reorder` not routed; `images/facets` shadowed.
- Importer parser: `Ans: B\nExp:` parsed as B+E, `Answer all…` as A.
- Invoice 500 without a matching payment; admin token transfer lock outside a transaction.
- SM-2 lapse handling; UTC vs IST dates for resets/streaks/activity/KPIs; atomic XP and study-time increments.
- Question list: N+1 on duplicate cluster id, cache key collisions, dead cache invalidation.

## Frontend

- Test player keeps answers on a failed submit (inline retry), no double submit.
- Tests page: `exam_type` on generation, visible errors, de-dup key bug (collapsed all tests of one type).
- Quests / topic notes pages use real API fields; topic notes admin-gated.
- Dashboard calendar uses local dates; hydration-safe promo banner.
- `globals.css` `@layer tokens` declarations were outside any rule (invalid; build warned) — wrapped in `:root` without overriding Tailwind theme variables.
- Dark mode (analytics pages, NEET PG / INI-CET players), responsive fixes, accessibility labels / keyboard support.
- `BackendWarmup` used a hard-coded production host; image fallbacks used the frontend origin — both now use `lib/apiBase.ts`.

## CI / dependencies

- CI backend job could never pass: with `DEBUG=False` the HTTPS redirect turned every test-client request into a `301`. `SECURE_SSL_REDIRECT` is now off only inside the test runner (production unchanged).
- Test discovery was broken (`questions/tests.py` + `questions/tests/` package) — the suite never actually ran in CI.
- `npm audit --audit-level=high` failed (13 high, 1 critical). Fixed via non-breaking updates and `next` 16.1.6 → 16.4.3 (same major); `eslint-plugin-react-hooks` pinned to 7.0.1 via `overrides` to keep lint rules unchanged. Remaining: 16 moderate.
- Tool pages showed component identifiers as titles/breadcrumbs ("CollegePredictor 2026"); one breadcrumb linked to a non-existent `/tools`.

## Verification

- Backend: full Django suite green (see final run), `makemigrations --check` clean, `check --deploy` no issues.
- All 55 pending migrations applied to a copy of the committed `db.sqlite3`.
- Frontend: `tsc --noEmit` clean, `eslint --quiet` clean, `next build` (Turbopack) succeeds with no warnings (817 pages).
- HTTP smoke against local servers (permissions, health/ready, ingest, facets).

## Remaining / external

- Login is Supabase-only; authenticated browser flows were verified through API tests, not a real login (the configured Supabase project is production).
- `.env` `DATABASE_URL` points to a Supabase pooler that reports "tenant not found" — check the Supabase project status.
- Production must run `python manage.py migrate` (build.sh does) to create the new tables/columns.
