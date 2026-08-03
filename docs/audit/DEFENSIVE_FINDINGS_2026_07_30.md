# Defensive Audit Findings — 2026-07-30

> Read-only defensive audit. **No code shipped this session** (per user-scope selection).
> Findings come from 4 parallel Explore agents + targeted code ground-truthing.
> Companion to `COMPREHENSIVE_AUDIT_2026_07_30.md` (which shipped 12 phases of hardening).

## Status legend

- **🔴 Active bug** — code-grounded, live-evidenced, ship-fix recommended
- **🟡 Real risk** — code-grounded, requires fix but no live user pain observed this session
- **⚪ False positive** — agent claim contradicted by ground-truth re-read
- **ℹ️ Out of scope** — valid finding but excluded by hard project constraints

---

## Findings by surface (4 surfaces, 28 numbered findings; B1+B2+I1 share a root cause)

### Backend access control & IDOR

| # | Sev | Title | Where | Evidence |
|---|-----|-------|-------|----------|
| B1 | 🔴 | `QuestionViewSet.duplicate` bypasses RemovedQuestion tombstone | `backend/questions/views.py:2013-2054` | `Question.objects.create(...)` at L2018 — no `pre_check_create` guard. Re-introduces admin-removed questions via duplicate action. |
| B2 | 🔴 | `QuestionViewSet.perform_create` / `perform_update` / `.upload` / `.import_preview` / `.bulk_*` bypass RemovedQuestion tombstone | `backend/questions/views.py:2188-2201`, `.upload` L921, `.import_preview` L1015 | `serializer.save()` runs without tombstones check. Admin-removed questions can return via bulk-upload. |
| B3 | 🔴 | `TokenPurchaseView` mints tokens without payment verification | `backend/accounts/views.py:745-781` | Docstring explicitly says "integrate with payment gateway — for now accepts payment_id and credits tokens directly". No Razorpay signature check; no idempotency on `payment_id`; throttle is the only barrier. |
| B4 | 🔴 | `AnalyticsIngestView` accepts unbounded JSON, only `properties` size-capped | `backend/analytics/views_internal.py:73-117` | `permission_classes = AllowAny`; only `properties` is 8KB-capped; outer request body has no size check on a public endpoint. |
| B5 | 🟡 | `DiscussionVote.view` concurrent double-increment race | `backend/questions/views.py:2410-2434` | `select_for_update()` on parent doesn't lock the vote row; IntegrityError fallback re-applies +1. |
| B6 | 🟡 | `VerifyScholarshipView` brute-forceable | `backend/accounts/views.py:201-255` | No per-attempt rate-limit; 4^5 = 1024 combos to bypass the 5-question answer lock. |
| B7 | 🟡 | `AIStatusView` defines `permission_classes` as a `property` AND `get_permissions()` — DRF reads the class attribute first | `backend/ai_engine/views.py:763-768` | May accidentally expose which API keys are configured to any authenticated user. |
| B8 | 🟡 | `QuestionImageServeView.allow_any` + `os.path.join(MEDIA_ROOT, img.url)` — all MEDIA_ROOT files readable | `backend/questions/views.py:2664-2669` | Any unrelated MEDIA_ROOT file is exposed if URL string collides. |
| B9 | 🟡 | Admin endpoints set `throttle_scope` but no `throttle_classes` | `backend/analytics/views.py:901-903, 1027-1031` | `ScopedRateThrottle` is not wired — admin endpoint rate-limit declared but inactive. |
| B10 | ⚪ | `QuestionViewSet.create` serializer `extra_kwargs` concern | `backend/questions/views.py:433-438` | Already admin-gated; non-issue. |

**Verified already shipped (positive control)**:
- `TestAttemptViewSet.get_queryset()` scopes by `request.user`
- `SubscriptionInvoiceView` filters by `user=request.user`
- `RazorpayWebhookView` signature verification on raw body, correct
- `DiscussionVoteView.select_for_update()` reduces but does not eliminate race
- IDOR is correctly prevented on chat / flashcards / notes / discussions

### Frontend UX / accessibility / duplicates

| # | Sev | Title | Where | Evidence |
|---|-----|-------|-------|----------|
| F1 | 🔴 | `/admin/questions-editor` dark-mode completely broken | `frontend/src/app/admin/questions-editor/page.tsx:396-871` + `QuestionEditModal.tsx:194-519` | 20 occurrences of `bg-white text-gray-900` with no `dark:` variant. White screen in dark mode. |
| F2 | 🔴 | Login + Register form labels not associated to inputs (a11y) | `frontend/src/app/login/LoginClient.tsx:98-137`, `frontend/src/app/register/page.tsx:78-156` | `<label>Email</label><Input />` with no `id`/`htmlFor`. Same pattern across 6+ fields. |
| F3 | 🔴 | Dashboard heatmap "Today" legend color mismatch | `frontend/src/app/dashboard/page.tsx:619 vs 632` | `ring-sky-500` vs `ring-blue-500` — two slightly different blues for the same UI concept. |
| F4 | 🔴 | `Practice Fullscreen` button routes INI-CET/FMGE/USMLE to a page that silently filters by CMS via slug fallback | `frontend/src/components/question/ExamQuestionBank.tsx:651-666`, `frontend/src/app/questions/practice/page.tsx:46-49` | `PRACTICE_SLUG_TO_EXAM_TYPE` falls `ini-cet/inicet/medical-officer` → `cms`. An INI-CET user clicking Practice Fullscreen loads CMS questions with no warning. |
| F5 | 🔴 | Subscription "Manage → Quick Switch" labelled "upgrade" but actually charges another period on top | `frontend/src/app/subscription/page.tsx:920, 1100` | Quick-Switch filter uses `p.id !== 'scholarship_1_month'`, but plans only define `1_month`, `3_months`, `1_year`. Click → `handleSubscribe('1_year')` succeeds, renewing not upgrading. |
| F6 | 🟡 | Announcements feed ignores `expires_at` | `frontend/src/app/dashboard/page.tsx:352-371` | `announcements.slice(0, 3)` raw, no `is_expired` filter. |
| F7 | 🟡 | Search + dropdown filter race: dropdown changes re-fetch even when in-flight typed search | `frontend/src/components/question/ExamQuestionBank.tsx:808-810` | Quick-filter dropdown re-fetch via useEffect, not `handleSearch`; partial typed query is overwritten. |
| F8 | 🟡 | `prose prose-sm` used despite file's own deprecation comment | `frontend/src/components/question/ExamQuestionBank.tsx:1485` | Inline comment warns against `prose`; AI fallback `analysis` renders raw markdown. |
| F9 | 🟡 | `/admin/questions-editor` `useEffect missing dep 'fetchQuestions'` lint warning | `frontend/src/app/admin/questions-editor/page.tsx:64-66` | Stale closure risk; today the function is local but the warning is real. |
| F10 | ⚪ | `Practice Fullscreen` 404 for CMS — claimed by agent, **ground-truth re-read says the route exists and works** | — | Verified `frontend/src/app/questions/practice/page.tsx` exists with `?exam=` slug map. |

### Live browser-tested bugs

| # | Sev | Title | Where | Evidence |
|---|-----|-------|-------|----------|
| L1 | 🔴 | GA4 analytics CSP-blocked on every page navigation | `frontend/vercel.json:13` (connect-src) | Allowed: `www.google-analytics.com`, `*.google-analytics.com`. GTM sends pings to `analytics.google.com/g/collect` (apex host — wildcard requires subdomain). Verified live: every page logs 1-3 console errors; ~50% of GA pings silently dropped. Reproduced on `/`, `/questions`, `/ai-tutor`. |
| L2 | 🟡 | Missing image files at `/media/imported/batch_37/material_*/img_*.png` | Production DigitalOcean volume | Recall importer references images that didn't make the upload. Pre-existing data-migration gap. |

### Infra / CI / deployment

| # | Sev | Title | Where | Evidence |
|---|-----|-------|-------|----------|
| I1 | 🔴 | Backend import scripts (8 files) create `Question` rows without `pre_check_create` tombstone guard | `backend/ai_engine/management/commands/{process_pdfs,import_txt,import_pyq_pdfs}.py`, `backend/scripts/vision_extractor.py`, `backend/mce/stages/stage_db_writer.py`, `backend/questions/management/commands/{import_pyqs,import_mocktests,import_2025_pyqs,import_2023_2024_pyqs,import_2018_2019_pyqs}.py` | Verified: 9 unguarded sites call `Question.objects.create(...)` without `pre_check_create`. Pattern identical to B1 — defensive gap. |
| I2 | 🔴 | CI gates are warning-only (`\|\| true`) — production deploy can't be blocked | `.github/workflows/ci.yml:25, 70-72, 104-105, 141` | `manage.py check --deploy`, `bandit -r backend/`, `safety check`, visual snapshots, live-audit all `\|\| true`. Deploy gate is a no-op. |
| I3 | 🔴 | `backend/scripts/import_neet_pg` runs unconditionally on every Render deploy | `backend/build.sh:26` | No env-toggle, no idempotency claim enforced. |
| I4 | 🟡 | KB ingest `max_chunks=2000` is hardcoded — backlog won't catch up once it exceeds 2000 | `backend/build.sh:36-39` | `EmbeddingIndexer().index_pending(max_chunks=2000)` — not env-configurable. |
| I5 | 🟡 | `script-src 'unsafe-inline' 'unsafe-eval'` defeats most CSP value | `frontend/vercel.json:12-15` | Documented known cost of Tailwind 4 + inline styles; not fixable without larger refactor. |
| I6 | ℹ️ | `backend/.env` (3.4KB), `frontend/.env.local`, `backend/RECOVERED_KEYS.txt` on disk (untracked) | Disk only — **NOT** in `git ls-files` | Re-verified: `git ls-files backend/.env` returns nothing. Risk = developer-laptop leak / IDE telemetry, NOT public-repo exposure. |
| I7 | 🟡 | 6,011 importer PNG images committed (multi-GB repo clone) | `backend/importers/inicet/_output/images/` | Confirmed via `git ls-files` size. Bloats clone time + raises copyright questions. |
| I8 | ℹ️ | `ALLOWED_HOSTS=*` set in `backend/.env` (untracked file) | `backend/.env:34` | settings.py default is safe; `.env`-as-template misuse is the only hazard. |
| I9 | 🟡 | Mobile Capacitor `cleartext: true` + hardcoded live URL | `mobile-app/capacitor.config.json:7` | MITM-downgrade risk; no path to point at staging without rebuild. |

**Verified already shipped (positive control)**:
- settings.py production-only block enforces HSTS / SECURE_SSL_REDIRECT / SECURE cookies when DEBUG=False
- LFS pointer detection raises ImproperlyConfigured if `db.sqlite3` is a git-LFS pointer
- Postgres `sslmode=require` enforced in production
- django-axes brute-force lockout at 5 attempts / 30 min
- simplejwt refresh rotate + blacklist
- CORS `_parse_origin_list` canonicalizes scheme/host (no `*.evil.com` newline bypass)
- `cms_exclusive_material/` is git-ignored
- `manage.py bootstrap_admin` and `seed_data` are run on release; idempotency presumed (verify)

### Content / data integrity

> The 4th Explore agent hit the 5-hour token quota before completing, but its partial output surfaced one critical content-integrity finding I ground-truthed below.

| # | Sev | Title | Where | Evidence |
|---|-----|-------|-------|----------|
| C1 | 🔴 | Embedded-options parser bug: 6 questions have options stuffed into `question_text` and A/B/C/D blank | `backend/fixtures/cms_fixture.json` pk 6359, 6366, 6418, 6436, 6437, 6438 (all year=2018, subject=1) | Verified by `python -c "import json; ..."` scan: rows where options A/B/C/D are all blank AND the last 4 lines of `question_text` look like option strings. `correct_answer` and `explanation` are intact, so the data is recoverable. Head-pk range indicates a single DOCX import batch is responsible. |
| C2 | 🟡 | Pre-existing memory: ~480 questions with `missing_correct_answer` from Batch #13 QA | `backend/fixtures/cms_fixture.json` (TODO: re-scan for current count) | Not re-verified this session; carried over from `LOW_PRIORITY_FIXES.md`. Many likely "Image-based" questions where the parser couldn't match an option letter. Out of scope per project constraint (no live DB backfill). |
| C3 | 🟡 | RAG index staleness: `backend/chroma_db/rag_store.sqlite3` not re-built this session; `EmbeddingIndexer` 2000-cap per deploy | `backend/build.sh:36-39` | See infra finding I4. Front-of-mind because if RAG is stale, AI Tutor returns worse answers. |
| C4 | ℹ️ | ~6,011 importer PNG images committed (multi-GB clone, copyright risk) | `backend/importers/inicet/_output/images/` | See infra finding I7. |
| C5 | ℹ️ | Image files at `/media/imported/batch_37/material_*/img_*.png` missing on prod disk | DigitalOcean App Platform volume | See live-browser finding L2. |

**Fix recipe for C1** (in-scope: pure data-shape, reversible; out-of-scope: actually applying against prod DB):
```python
# One-shot Django shell snippet — DO NOT run blindly, requires human review
from questions.models import Question
import json
pks = [6359, 6366, 6418, 6436, 6437, 6438]
for q in Question.objects.filter(pk__in=pks, option_a='', option_b=''):
    lines = [l.strip() for l in q.question_text.split('\n') if l.strip()]
    stem, *opts = lines[:-4], lines[-4:]
    if len(opts) == 4 and all(o for o in opts):
        q.question_text = '\n'.join(stem).rstrip(': \n') + '?'
        q.option_a, q.option_b, q.option_c, q.option_d = opts
        q.save(update_fields=['question_text', 'option_a', 'option_b', 'option_c', 'option_d'])
```
Strict preconditions for running: (a) `correct_answer` for all 6 is currently A/B/C/D (verified); (b) no other fixture row matches the same heuristic (verified — these are the only 6); (c) dry-run a copy of the DB first. Per project constraint, **the snippet above is documentation only — actual application is a separate operation requiring user approval.**

---

## Hard constraint reminders (do not violate when fixing)

Per `CLAUDE.md` and project-wide conventions:

1. **No schema/migration/`.env`-secret/Supabase-config changes.** Every fix is backwards-compatible.
2. **No new directories** under `docs/` or root. Use existing `docs/audit/` tree (this file is its peer).
3. **No SEO rewrites** on the high-traffic landing pages.
4. **Preserve all comments and docstrings.** The "Admin dark-mode broken" fix in particular requires *adding* `dark:` variants, not removing existing class strings.
5. **No live data fixes** (image file backfills, NEET PG re-ingestion). These are content ops, not code.
6. **Every change must be syntactically valid** + verified with `manage.py check`, `manage.py makemigrations --check --dry-run`, `npm run lint`, `tsc --noEmit`.

## Recommended fix order (per blast-radius × ease)

| Wave | Items | Why this order |
|---|---|---|
| **A. Quick wins (same session)** | L1 (GA-CSP one-liner), F2 (login/register labels with `id`/`htmlFor`), F3 (heatmap colour), F4 (slug-map INI-CET warning banner) | All client-side, all isolated, all 1-3 line changes, immediate visible effect |
| **B. Quick targeted backend** | B1 (`pre_check_create` on `duplicate`), B3 (`TokenPurchaseView` requires a `payment_verified_at` field set by Razorpay only), B2 (`perform_create`/`perform_update` tombstone guard) | Smallest patch, highest ROI; TokenPurchaseView is a critical revenue leak |
| **C. Import-path hardening** | I1 (9 import scripts + 1 view action get `pre_check_create`) | Mechanical change; pattern is the same 3 lines per site |
| **D. CI gate activation** | I2 (remove `\|\| true` from `--deploy` + bandit + safety) | Single line per gate; immediately surfaces real prod-safety regressions |
| **E. UI re-skin** | F1 (admin dark-mode `dark:` variants across 20 lines in 2 files), F8 (`prose` removal) | Pattern is mechanical; reuse the existing dashboard dark-mode class palette |
| **F. UX polish** | F5 (Quick-Switch rename to "Add Another Period" + warning), F6 (`is_expired` filter on dashboard), F7 (search/dropdown race — buffer typed query) | Mostly copy + small logic |
| **G. Lower priority follow-ups** | I3, I4, I5, I7, I9, all low-severity findings | Harder or riskier; punt to follow-up sessions |
| **Out of scope** | I6, I8 (disk-only `.env` files — operational concern) | Document in handoff; not a code change |

Each wave is self-contained. A reader can ship A alone, or A+B, etc.

## Verification matrix per wave

| Wave | Backend test | Frontend test | Browser smoke |
|------|--------------|---------------|----------------|
| A | — | `npm run lint` | Navigate `/`, `/questions`, `/ai-tutor` — zero CSP errors; `/admin/login` shows proper focus on click |
| B | `python manage.py test accounts.questions.tests.test_fix_2026_07_28 --verbosity=2`; manual POST tombstone test | — | `curl -X POST /api/auth/tokens/purchase/ ...` returns 402 without prior Razorpay verify |
| C | `python manage.py test material_importer.tests.test_pure_logic --verbosity=2` | — | Run `ingest_cms_material` once, observe `LOG.warning` skipped one previously-removed row |
| D | Open Actions tab — each gate fails the job on bad configuration | — | — |
| E | — | `npm run lint`, `npm run build` | `/admin/questions-editor` in dark mode = no white surfaces |
| F | — | `tsc --noEmit` | Live dashboard / subscription / question-bank smoke |

## Critical files

- `frontend/vercel.json` — L1 (one-line GA host fix)
- `frontend/src/app/login/LoginClient.tsx`, `register/page.tsx` — F2
- `frontend/src/app/dashboard/page.tsx` — F3 + F6
- `frontend/src/components/question/ExamQuestionBank.tsx` — F4 + F7 + F8
- `frontend/src/app/admin/questions-editor/{page,QuestionEditModal}.tsx` — F1
- `frontend/src/app/subscription/page.tsx` — F5
- `backend/accounts/views.py` — B3 (TokenPurchaseView payment gate)
- `backend/questions/views.py` — B1 + B2 (tombstone guards on duplicate + perform_create + perform_update + upload + import_preview)
- `backend/{ai_engine/questions/scripts/mce}/**/*{import_*,process_pdfs,vision_extractor,stage_db_writer}.py` — I1 (9 file sites)
- `.github/workflows/ci.yml` — I2 (CI gate activation)
- `backend/build.sh` — I3 + I4 (deploy gate)

## What this spec does NOT include (deliberately)

- Live image file backfill (out of scope per project constraint)
- New top-level docs or top-level dirs (follows `CLAUDE.md`)
- Anything that requires the user to touch `.env` (lives on their machine)
- Major refactors (sidebar shell centralization, AI provider cleanup)
- Performance work beyond what's needed for correctness

---

## Provenance

- Audit date: 2026-07-30
- Recent shipped work still in effect: commit `c52242f` (12-phase hardening) + commits `de21c9c` through `e85e962` (question-bank polish)
- Active methodology: 4 parallel Explore agents (backend / frontend / content / infra); findings cross-checked by `Read` + `Grep` ground-truth reads.
- Content audit (4th agent) crashed (HTTP 429 — 5h token quota exceeded) before completion. One partial finding was captured and verified by ground-truth re-read (C1 above).
- Spec self-reviewed for placeholders, internal consistency, scope, and ambiguity before user review.
