# Overnight mission — final report (2026-11-01)

Branch **`overnight-mission`** in the worktree `C:\Users\DIVYANSHU\Desktop\crack_cms\.claude\worktrees\full-audit-fixes`, built on the previous audit branch `worktree-full-audit-fixes` @ `33532e0` (tag `overnight-mission-start`). **Nothing was pushed, deployed, or run against production.** All database work used an isolated local PostgreSQL cluster restored from your backup; both original backup files are untouched (SHA-256 below).

## Summary

* **Recovery:** the Supabase cluster dump restores into a local PostgreSQL 16 cluster with identical row counts in 140 of 141 tables. Every one of the 4,200 question images has its file locally. The whole stack (Django + Next.js + PostgreSQL) runs on the restored data with local auth, mock payments and offline AI. No Supabase, Razorpay or AI provider is needed.
* **Fixes:** a 139-agent read-only discovery pass found 57 confirmed serious problems. Three fix waves followed, each split into file-disjoint groups and checked by an independent reviewer. A second security/performance pass came after them. Together they fixed several hundred verified items across 69 commits. The serious ones: anonymous and free users could read every answer key; production credentials and personal-data dumps were committed; unknown plans sold a lifetime plan for ₹199; tokens were charged when AI failed, and outage text was saved as explanations; blocked users kept API access; there was a cross-account token-cache bug; the NEET PG deploy import was destructive.
* **RAG:** retrieval now covers the whole textbook store (it used to stop after 2,000 of 7,823 chunks). On a held-out test set, success@5 went from 0.239 to 0.547 and MRR from 0.168 to 0.431, and median latency dropped from 3.5 s to 2 ms. Method and limits are in `docs/audit/RAG_BENCHMARK.md`.
* **Tests:** backend **1,722 tests OK (9 skipped), 0 failures**; frontend type-check and lint clean; **332 / 332** frontend unit tests; local Playwright E2E **156 tests over 3 viewports, 141 passed, 15 skipped (desktop-only flows), 0 failed**.
* **Ready for local use: yes.** Not ready to deploy until the owner actions in §13 are done. Credential rotation and the history purge come first.

## 1. What was recovered from the backups

| Backup | What it is | Result |
|---|---|---|
| `Downloads\db_cluster-02-10-2026@08-24-39.backup.gz` (SHA-256 `43D991777F68B4EE9F49AC450C1B7F02DDF39A89D1F02EBAB943DEA1260E5C3E`, untouched) | Supabase `pg_dumpall` (PostgreSQL 17.6) of `postgres` (production) and `test_postgres` | Restored into an isolated PostgreSQL 16 cluster (`%USERPROFILE%\crack_local\pgdata`, 127.0.0.1:55432) as `crack_restore` (pristine, never modified) and `crack_local` (working copy). **140 of 141 tables have identical row counts.** The only miss is `vault.secrets` (0 rows, Supabase Vault extension). All errors were expected: pgvector types (embeddings are stored as JSON), Vault, and PG17-only privileges. |
| `Downloads\ryuvcdthjnxyetdyjbph.storage.zip` (SHA-256 `99153EF090CA6DE9BBB207C1F3253A32476CC5F2FA0865F0E358793A8084AA1C`, untouched) | Supabase Storage export: 1,095 objects (505 MB), mostly question images, plus educational videos with subtitles/thumbnails | Extracted to `%USERPROFILE%\crack_local\storage\<bucket>\…` and served locally through a storage-mirror setting. |

Restored content: 13,788 questions (10,013 active), 4,200 question images, 1,979 topics, 37 subjects, 213 tests (60,960 question links), 110 test attempts with 2,655 responses, 1,449 question-bank attempts, 127 app users, 17 payment attempts, 14 blog posts and 235 knowledge-base chunks. **Every one of the 4,200 question images has its file locally**: 3,579 recall images in `backend/media`, 495 storage objects and 126 media uploads. Production had applied two migrations that were deliberately removed from the repo, and it lacked four repo migrations. Those four, plus the 11 added by this mission, are applied to `crack_local`. The mission's migrations are `accounts` 0023–0027, `analytics` 0008–0009, `blog_engine` 0002, `questions` 0041 and `tests_engine` 0008–0009. A snapshot of the working copy taken before the last 11 were applied is at `crack_local\backups\crack_local_before_wave3_migrations.dump`.

## 2. Running it locally

```powershell
# start everything (PostgreSQL :55432, Django :8000, Next.js :3000); applies pending migrations to the LOCAL database only
powershell -ExecutionPolicy Bypass -File scripts\local\start-local.ps1 -Frontend prod   # or -Frontend dev (hot reload)
# stop the app servers but keep the database / stop everything
powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1 -KeepDatabase
powershell -ExecutionPolicy Bypass -File scripts\local\stop-local.ps1
```

* Frontend http://localhost:3000 · API http://127.0.0.1:8000/api/health/ · Django admin http://127.0.0.1:8000/admin/
* Accounts: `student@local.test` (free), `premium@local.test` (1-year plan), `admin@local.test` (admin). The password is `LOCAL_SEED_PASSWORD` in `backend/.env.localdev` (generated, gitignored).
* `scripts/local/migrate_local.py [--check]` migrates only a database on this machine; it refuses SQLite and non-local hosts.
* Full guide: [`docs/LOCAL_DEVELOPMENT.md`](../LOCAL_DEVELOPMENT.md).

| Concern | Locally |
|---|---|
| Database | real restored data in an isolated PostgreSQL (production never touched) |
| Auth | dev-only local email/password auth (`LOCAL_DEV_AUTH`, refuses to run without `DEBUG`); Supabase is not called; the Next.js middleware gates on local presence cookies |
| Payments | **mocked** Razorpay (`PAYMENTS_MODE=mock`, refuses without `DEBUG`). Only the order API and the checkout popup are replaced; signature verification, the webhook, activation and entitlement run the real code |
| AI | **offline by default** (`AI_OFFLINE_MODE=1`): extractive, cited answers from the textbook store, never charged; set `0` to use real providers |
| Storage / images | local media + Supabase-storage mirror |
| E-mail | written to files (`%USERPROFILE%\crack_local\mail`) |
| Analytics | Simple Analytics is disabled in local builds; GA stays consent-gated |

## 3. What was broken

Discovery used 139 read-only agents, and each finding was verified by 2 independent skeptics. Results: **57 confirmed serious**, 2 disputed, 241 medium/low, and 55 concerns about earlier fixes. Most important first:

* **Secrets and personal data in git:** the Supabase service-role key, database passwords, a Railway credential, an admin password literal, a DeepSeek key and 43 personal-data dumps (user emails, phones, IPs, password hashes, sessions, payment ids, answer history).
* **Answer keys open to everyone:** anonymous and free users could read every answer and explanation through the question API, search filters, test reviews, the Mistake Notebook, AI explain endpoints, page screenshots, recall search and list fields such as textbook excerpts. Generated tests and retakes leaked the key through right/wrong.
* **Money and credits:** an order with a missing or unknown plan sold the lifetime "legacy" plan for ₹199; webhook retries could stack a second period; tokens were charged when AI failed, and the outage sentence was saved as the question's explanation; subscribers were capped at 2 AI messages a day.
* **Auth:** the Supabase token cache was keyed on the shared JWT header, so one user's identity could be served for another's token. Blocked users kept API access. Admin elevation trusted unconfirmed emails. A refresh loop could hammer Supabase.
* **Infrastructure:** the deploy-time NEET PG import was destructive. The question rate limiter shared one budget per proxy IP. The CSP blocked Razorpay checkout. Test runs could call real AI providers and report to production Sentry.
* **Broken features:** Mistake Notebook and Study Time were never populated and their pages crashed. Five analytics endpoints returned 500. A test-start race returned 500. The import job list returned 500. Many pages rendered without the app shell. Local auth could not reach any protected page.
* **RAG:** 74 % of the textbook store was never searched; each search took ~3.5 s; a third of each top 5 was duplicates; personal PDFs were retrievable (details in §7).
* **Honesty:** public pages claimed "2,000+" PYQs and fabricated medical reviewers/bylines, sold "deep analytics" and "adaptive tests" that do not exist, and the cutoff data was stale.

## 4. What was fixed

| Wave | Scope | Result |
|---|---|---|
| Session 1 + Phase 2 | cross-account token cache, plan-validation hole, local architecture, Mistake Notebook / Study Time capture, dashboard 500s, RAG rewrite | commits `ff5831a`…`19c1b2c` |
| Wave 1 | 57 serious + most medium findings, 11 file-disjoint groups, each reviewed | 271 items, `f011c1d`…`d988cec`, `61b4b2c`; backend suite 929 tests OK |
| UI reviews | 3 screenshot rounds (967 screenshots), 69 public + 156 app issues verified | fed into wave 2 |
| Wave 2 | wave-1 review problems, cross-group follow-ups, UI issues | 256 items, `0a647c5`…`88d6461`; suite 1,185 OK |
| Dependencies | pip-audit | `606c91c` (§9) |
| Wave 3 (+3b) | 2 high + ~10 medium wave-2 review problems (free-tier answer harvesting via generated tests and the Mistake Notebook, admin lockout after deploy, screenshot entitlement, ingestion recovery), the unfinished app shell, independent reviews of 3 unreviewed wave-2 commits (86/95 claims confirmed, 8 medium problems fixed), integration, docs | 146 items (fix + repair) + 15 (integration) + 57 (wave 3b), `624cede`…`e71b967`; suite 1,423 OK |
| Security pass | 6 lenses (entitlement, authz, payments, injection, privacy, performance); every medium-or-worse finding checked by 2 independent skeptics; 14 of 14 confirmed and fixed with regression tests, plus 5 problems found while reviewing those fixes (waves 4 and 4b) | `4d23bad`…`2e0fcd9`; backend suite 1,719 OK |
| E2E fixes | found by the Playwright suite | `59fdc61` (tutor citations), `4bd6a9e` (harness), `3611382` (lifetime members cannot be sold another period) |

Highlights by area (details in each commit message):
* **Entitlement:** one rule (`questions.views.user_can_view_answer` / `free_showcase_rows`) now governs the list, detail, attempt, tests (start/submit/review/generate/adaptive/pyq-simulation), Mistake Notebook, AI explain/screenshot, recall search, flashcards and image serving. Explanation figures need signed URLs. Scholarship questions stay locked for non-subscribers, and blocked reveals answer `402 upgrade_required`.
* **Payments:** the plan allow-list, ownership checks, signatures verified on every call, one atomic claim shared by verify and webhook (no double credit), and the scholarship challenge stored per user (no re-roll).
* **AI:** typed failures (`AIUnavailable`), refunds when nothing answered, no provider error text shown or stored, an offline extractive mode, and admin regenerations that never mark unreviewed AI text as verified.
* **Auth:** linking by Supabase user id (`supabase_uid`) with safe first-login rules, the `link_supabase_identity` deploy command, device limits that cannot lock a user out of buying the bigger plan, blocked users refused everywhere, and deploy checks `accounts.W001-W003`.
* **Infra:** trusted client IP for rate limits, a non-destructive deploy, hermetic tests (external secrets blanked, remote test databases refused), CI secret scanning, and a Bandit gate with no baseline.
* **Imports:** a scheduled stale-job sweeper (django-q), idempotent resume, atomic publish, per-exam job lists, and upload validation by file content.

## 5. What was redesigned (and what was deliberately kept)

Per your instruction, the visual identity, layouts and copy were kept wherever they worked. Redesign was limited to what was broken or clearly weaker:
* **App shell:** 15+ pages that rendered without navigation now share one `AppShell`. Global CSS was moved into Tailwind layers so utilities win. The header shows a readable exam switcher, Premium badges no longer truncate labels, and the floating dock stays off admin, the timed test player and the AI tutor. The free-usage banner now sits under the header bar.
* **Mistake Notebook** (filters, due queue, inline review, pagination) and **Study Time** (ranges, per-subject bars, daily log) were rebuilt. Before, they crashed and were never filled.
* **Dashboard:** clipped cards, the calendar, dark-mode progress bars, empty states, and scoping to the active exam.
* **Practice / tests:** theme tokens instead of hard-coded dark palettes (light mode works), plus clear upgrade and AI-unavailable states.
* **Public pages:** contrast, data-backed counts, honest bylines ("CrackCMS Editorial Team"), consent copy.

Round-4 screenshots come from the E2E smoke suite: 18 app pages in light and dark mode on desktop and mobile (light only on tablet), plus 6 public pages on all three viewports.

## 6. What was added

* **Local stack:** `DJANGO_ENV_FILE`, local auth, mock payments, offline AI, storage mirror, file e-mail, start/stop/migrate scripts, seed accounts, `docs/LOCAL_DEVELOPMENT.md`.
* **Automatic Mistake Notebook capture** (question bank, practice, tests) and **study-time recording**, plus backfills from history (987 notebook entries, 336 study-time rows locally).
* **RAG:** whole-store BM25 index (`ai_engine/lexical_index.py`), corpus policy, offline extractive answers, benchmark harness `ai_eval/rag_benchmark.py`, and 14 retrieval regression tests.
* **Data-quality audit** (`ai_eval/subject_audit.py`).
* **Commands:** `link_supabase_identity`, `cleanup_seed_samples` (dry run by default), `backfill_mistake_notebook`, `backfill_study_time`, `fix_answer_label_leaks`, `reconcile_legacy_subscriptions`, `rename_email_derived_usernames` (all write only with `--apply`).
* **Local Playwright E2E suite:** 7 spec files, 156 tests over 3 viewports.
* **HTML sanitizer** for stored and AI-generated content (`frontend/src/lib/markdownSanitize.ts`).
* **Deploy checks** `accounts.W001-W003`, plus a scheduled ingestion recovery job.

## 7. RAG (textbook retrieval): what changed and the measured effect

**Before (verified by reading and measuring the old code):** the search stopped after the first 2,000 of 7,823 chunks in rowid order, so 74 % of the store (267 of 274 books, every topic note) was never searched; IDF was fetched with one SQL query per term per chunk (~3.5 s per search); the same files were indexed under 2–3 names, so a third of every top 5 was a duplicate; the tokenizer dropped non-ASCII (`β-blocker` → `-blocker`); personal/administrative PDFs and an internal business document were retrievable; the constructor wrote to the git-tracked store on every request; and a total provider failure returned operator text ("configure API keys") as the answer.

**Now:** Okapi BM25 over the whole store from an in-memory index (`backend/ai_engine/lexical_index.py`), Greek/diacritic-aware tokenizer with a conservative plural stemmer, a corpus policy (one indexing pass per source file, exact duplicates dropped, personal/admin documents never returned, raw question papers only on request), a read-only constructor, and an extractive, cited answer when `AI_OFFLINE_MODE=1` or every provider fails (flagged `generated: false`, not charged). 14 regression tests in `backend/ai_eval/tests_rag_retrieval.py`.

**Benchmark** (`python -m ai_eval.rag_benchmark`, full method in `docs/audit/RAG_BENCHMARK.md`). Datasets were built from the restored question bank with no hand- or LLM-written relevance labels; decisions were made on the dev split (2018–2021) and the numbers below are the held-out test split (2022–2025).

| Answer-bearing retrieval, test n = 117 | success@1 | success@5 (Recall@5) | precision@5 | MRR@10 | nDCG@10 | duplicates in top 5 | median latency |
|---|---|---|---|---|---|---|---|
| Old production | 0.128 | 0.239 | 0.075 | 0.168 | 0.110 | 33 % | 3,454 ms (p95 5,757) |
| **Shipped** | **0.333** | **0.547** | **0.179** | **0.431** | **0.318** | **0 %** | **2.0 ms** (p95 4.9) |
| SQLite FTS5 + same policy (not shipped) | 0.385 | 0.530 | 0.183 | 0.454 | 0.336 | 0 % | 3.0 ms |

* Paired bootstrap (1,000 resamples), shipped vs old: success@5 **+0.31** [+0.21, +0.41], MRR **+0.26** [+0.19, +0.34], nDCG@10 **+0.21** [+0.16, +0.26].
* Topic-note retrieval (silver labels, n = 132): success@5 0.000 → **0.629**. Coverage smoke test (n = 1,306): success@1 0.039 → **0.885**.
* FTS5 scored slightly higher than the shipped BM25 on test success@1/MRR/nDCG but lower on dev ANS MRR and on topic notes; the differences are within the confidence intervals, and the in-memory BM25 was kept (chosen on dev, no schema change to the tracked store).
* Offline extractive answers: the answer contains the correct option for 12.0 % → **36.8 %** of test questions; 100 % of answer sentences are verbatim from the cited passage. (A no-policy variant reaches 47.9 % only because it retrieves raw question papers that contain the answer keys — leakage, so it was rejected.)
* **Faithfulness of LLM-generated answers was not measured**: that needs external model calls, which this run avoided. Dense/hybrid retrieval and re-ranking were not benchmarked (no embedding runtime available locally).
* **Main limit is content, not ranking:** only 263 of 1,876 dated CMS PYQs have their answer text anywhere in the study material.

## 8. Data quality

* NEET PG subject tags agree with the source compilation for only 49.8 % of questions (1,679 / 3,372). 1,693 corrections taken from the source files were applied to the **local** database only (`crack_local`; backup of the old values in `crack_local\data_quality\subject_suggestions_before_apply.csv`). Production is unchanged.
* A text classifier (cross-validated accuracy 63.1 %, macro-F1 0.60) produced 2,079 further suggestions (71 at confidence ≥ 0.9) for human review — not applied. Details: `docs/audit/DATA_QUALITY.md`.

## 9. Security and dependencies

**Dependencies:** pip-audit found 32 vulnerable packages in the local venv, 22 of them in the production install tree of `backend/requirements.txt`. Commit `606c91c` raises the floors (Django 5.2.18, DRF 3.18.3, ddtrace 4.15.6, plus PyJWT, cryptography, requests, urllib3, idna, certifi, sqlparse, aiohttp, h2, …); the local venv was upgraded to match (`pip check` clean; snapshot of the old versions in `crack_local\logs\venv_freeze_before_security_upgrade.txt`) and the full backend suite passed on it. **Pillow stays on 11.3.0, which has open advisories**: moviepy 2.2.1 (latest) requires `pillow<12`, and the fixes start at 12.1.1. npm production dependencies: 0 known vulnerabilities.

**Second security/performance pass:** A second security and performance pass ran after wave 3. Six review lenses covered entitlement, authorization, payments/credits, injection, secrets/privacy and performance. They produced 32 findings, 29 after de-duplication. All 14 medium-or-worse findings were checked by 2 independent skeptics, with a third breaking a split, and all 14 were confirmed. The skeptics re-rated their severity: 1 high, 8 medium, 5 low. Follow-up reviews of the fixes found 5 more problems, which were fixed in waves 4 and 4b. Every fix has regression tests.

| Confirmed finding | Fix |
|---|---|
| 744 questions carry their answer key or explanation inside the public stem/option text: answer labels, ✔/✅ ticks, "(correct)", pasted answer-key tables. Anyone could read them, including on locked questions | Locked rows are cut at these labels and flags in every payload (question list/detail, test detail and review, Mistake Notebook, scholarship set, recall, bookmarks, duplicates). Text search no longer matches the hidden part. Imports hold such rows for review. `fix_answer_label_leaks` repairs the stored data, but this is an owner action (§13). |
| The floating-dock chat accepted messages of any length, and the offline composer was quadratic (cheap DoS) | 4,000-character limit; bounded composer |
| Anonymous recall search ran an uncapped OR of ILIKEs; `?search=` took unlimited terms | Token, term and length caps; an opt-in database statement timeout |
| Any random bearer token made the backend call Supabase before throttling, and failures were never cached | Malformed or expired tokens are refused locally. Refusals are cached for 60 s, cache life is capped at the token's `exp`, concurrency and per-IP limits apply, and a busy check answers `429 auth_verification_busy` |
| The device limit relied on a client header (omit `X-Session-ID` → unlimited devices, survives logout) | Devices are bound to the Supabase session (`accounts.0025`) |
| Premium self-activated through the old unpaid endpoint counted as lifetime; old unpaid "legacy" orders could still be paid | Premium comes only from Subscription rows. `accounts.0026` restores plans that have a signed payment on record; `reconcile_legacy_subscriptions` handles the rest (owner action) |
| Open redirect: `/<TAB>/host` passed the post-sign-in `next=` check | Control characters, whitespace and backslashes are rejected, and the path must resolve to the site origin |
| The reveal panel started up to four synchronous AI rotations (90 s each) inside GET requests | GETs serve stored text only and answer `202 pending` while one background job (django-q) generates it |
| `dashboard_v3` read the whole answer history four times per request, uncached; `?nocache=1` worked for anyone | One read per request, a per-user 60 s cache, `nocache` for admins only. Output is checked equal to the old implementation on fixed and random histories |
| The leaderboard showed every learner the email local part of the top learner | Public names only. New accounts get chosen or generated handles; `accounts.0027` renames email-derived student usernames |
| The weekly production-audit CI job uploaded Playwright traces containing the live QA account passwords and session tokens | No traces, videos, reports or storage state uploaded; only allow-listed diff images and the audit JSON |
| Mistake Notebook "due" list was unpaginated | Paginated |
| `backend/db.sqlite3` is tracked and holds real account data and admin password hashes | Not changed in code (it is a deployment artifact); owner action §13 |

Problems found while reviewing those fixes, all fixed: text search still matching the hidden part of a locked row (an answer-key oracle, high); question feedback echoing raw locked stems; scholarship verification reporting a score on failed attempts (answer one question, leave four blank); username "taken" checks revealing hidden email-derived names; sign-up usernames skipping the format rules.

Reported as low and not verified, so treat them as leads: login CSRF through the auth-callback fragment; the CSRF check on the admin generate-explanation view; legacy `/api/questions/quests/*` routes skipping freeze rules; feedback rewards paid for junk reports; a concurrent first AI-tutor request of the day returning 500; the textbook-reference exact-stem check; inner-ZIP size in DOCX/PPTX imports; attacker text through `/login?authError=`; Sentry receiving request bodies; no audit record for bulk user exports; a frontend CSP without script restrictions; per-row `get_or_create` on test submit; heavy prefetch on per-question actions; no per-user limit on `/tests/generate/`; Datadog SDKs bundled for every visitor.

**XSS:** `FormattedText`, which renders stems, explanations, topic notes, blog posts and tutor answers, used `rehype-raw` with no sanitizer. Stored iframes, forms, `<style>` and full-screen overlays reached every student. It now runs an allow-list sanitizer; 6 unit tests check both the attack payloads and normal formatting.

## 10. Tests — commands and results

| Suite | Command (see `CLAUDE.md`) | Result |
|---|---|---|
| Backend (hermetic; SQLite; external secrets blanked) | `cd backend` then `DATABASE_URL= SUPABASE_DATABASE_URL= DEBUG=True SENTRY_DSN= python manage.py test --parallel 1` | 1,722 tests OK (9 skipped), 0 failures |
| Missing migrations | `python manage.py makemigrations --check --dry-run` | no changes |
| Frontend types / lint | `cd frontend; npx tsc --noEmit -p .; npx eslint src --quiet` | 0 errors / 0 errors |
| Frontend unit | `node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs" "tests/unit/*.test.ts"` | 332 / 332 |
| E2E specs type-check | `npx tsc -p tests/e2e/local/tsconfig.json` | 0 errors |
| Local E2E (stack running) | `npx playwright test -c playwright.local.config.ts` (`--project=desktop|tablet|mobile`) | final run on the last build: desktop 52/52, tablet 44 passed + 8 skipped, mobile 45 passed + 7 skipped; 0 failed, 0 flaky (39 min). Afterwards the payments spec was re-run for the lifetime-order fix: 6/6 |
| Bandit gate | `bandit -r backend/ -x '*/migrations/*,*/__pycache__/*' --skip B101 -lll -iii` | 0 findings (no baseline) |
| RAG benchmark | `cd backend; python -m ai_eval.rag_benchmark --out ../docs/audit/rag` | numbers in §7 |

## 11. Playwright / Chrome

The Claude-in-Chrome extension never connected during session 1, so every browser check used headless Playwright (Chromium) against the local stack. Screenshot rounds 1-3 used a capture script (`crack_local\ui\capture.mjs`): 967 screenshots over 71 routes × 3 viewports × light/dark. The E2E suite covers the end-to-end flows on desktop 1440×900, tablet 820×1180 and Pixel 5. Every test also fails on console errors, page errors, failed requests, 5xx responses or horizontal overflow. History of the runs: desktop run 1 passed 42/52. Of the 10 failures, 8 came from test-side assumptions, which were fixed: tokens re-seeded after logout, a too-strict text matcher, locked questions answering 404 rather than 402, the documented 503 for an offline tutor with nothing to cite, showcase-first ordering for free users, and the sidebar auto-hiding on the question bank. The other 2 were app bugs, both fixed. The AI tutor listed citations only in Textbook Search mode. Local builds loaded Simple Analytics, so local traffic reached the production analytics account. Tablet and mobile then passed 87 tests with 15 skipped, failing only on the tutor citations test until the rebuild. The final run on the last build passed everything. Two more problems came from the suite itself: the raw "Imported" subject label on the dashboard and Mistake Notebook, spotted in its screenshots and fixed in wave 4, and the server accepting an order from a lifetime member, recorded by the payments spec and fixed in `3611382`.

## 12. Verified vs mocked vs unverified

| | |
|---|---|
| **Verified locally** (real code, restored data) | question-bank practice and answer reveal; entitlement gates for anonymous/free/premium/admin; mock tests start→submit→review; Mistake Notebook and Study Time capture; bookmarks; dashboards and analytics endpoints; admin console pages and API authorization; payment rules with real HMAC signature checks (invalid signature, foreign order, unknown/lifetime plan, idempotent verify, stacking, webhook forgery/duplicates, no further purchase for lifetime members); admin revoke/grant and entitlement; offline AI tutor answers with citations; migrations on the restored data; responsive layout on 24 pages × 3 viewports; RAG retrieval quality (benchmark) |
| **Mocked** | Razorpay order creation and checkout popup; Supabase auth (local auth mode); AI providers (offline mode); e-mail (file backend); object storage (local mirror) |
| **Not verified** | real Supabase sign-in, identity linking against real GoTrue, real Razorpay checkout in a browser (CSP), LLM answer quality and faithfulness, the deploy itself (build.sh, Procfile, DigitalOcean/Vercel), django-q schedules on a real worker, e-mail delivery, the mobile app (`mobile-app/`), performance under production load |

## 13. Remaining issues and owner actions

**Before any deploy (security):**
1. **Rotate** every credential that was committed: Supabase service-role key and database password, the Railway credential, Django/Supabase admin passwords, the DeepSeek key. They stay valid until rotated, whatever the code says.
2. **Purge git history** of those credentials and the personal-data dumps, including `backend/questions_backup.json` and `backend/Medura_Train` personal/administrative PDFs. The repository is public. This needs a history rewrite and force push, which only you can approve.
3. `backend/db.sqlite3` (tracked for deployment) still holds 12 real user rows; decide whether to strip them.
4. The 43 personal-data dumps moved out of the repository sit unencrypted in `%USERPROFILE%\crack_local\repo_pii_backup` (see `MANIFEST.tsv`). Encrypt or delete them.
5. Supabase dashboard: turn **Confirm email** and **Secure email change** ON, then set `SUPABASE_EMAIL_CONFIRMATION_ENABLED=true` (`accounts.W001`). Set `SUPABASE_ANON_KEY` (W002) and `CORE_DATA_BACKUP_PATH` on a persistent volume (W003).

**Deploy steps:**
6. After `accounts.0023` is deployed, run `python manage.py link_supabase_identity --all-privileged` (dry run; the build log prints it), confirm the CHECK rows out of band, then run it with `--apply`.
7. DigitalOcean: add a worker component running `python manage.py qcluster` (imports, renewal reminders, stale-job recovery).
8. Client IP: call `GET /api/health/client-ip/` as admin, set `TRUSTED_CLIENT_IP_HEADER=DO-Connecting-IP` and `NUM_PROXIES`. Decide `ANALYTICS_COUNTRY_HEADER`.
9. Production media: page screenshots and other `MEDIA_ROOT` files are served only under `DEBUG`. Choose persistent storage (bucket) and an entitlement-checked delivery.
10. One-time data cleanups, each with a dry run first: `import_neet_pg --replace`, `cleanup_seed_samples --apply`, `python seed_jobs.py --delete-placeholders`.
11. Deploy commits `0a647c5`…`185a1cf` as one unit; they are not individually consistent.

**Product / data decisions:**
12. Pillow stays at 11.3 (open advisories) because moviepy 2.2.1 requires `pillow<12`. Either drop moviepy (the video slides could use the ffmpeg CLI) or wait for a moviepy release.
13. Refunds are not handled automatically: the webhook ignores refund events, and access must be revoked by hand in the admin panel.
14. Data quality: review the 2,079 NEET PG subject suggestions. The 1,693 source-file corrections were applied to the local database only.
15. RAG store: remove the personal/administrative PDFs and the internal business document from `backend/Medura_Train`, and check licensing of the commercial textbook copies. Coverage, not ranking, now limits answer quality.
16. Decisions taken here, which you may revisit: analytics stays free (no "Deep Analytics" upsell); the public blog stays static (DB posts are not rendered); premium users may read scholarship answers.
17. Answer keys pasted into question text: run `python manage.py fix_answer_label_leaks --json-report plan.json` (dry run) on a copy of production, review it (659 rows repaired automatically, 85 deactivated for review, 20+ key conflicts where a tick and the stored key disagree — e.g. 24224-24236 except 24233, 25348), then `--apply`; re-score attempts on the conflict rows once their keys are settled. Details: `docs/audit/DATA_QUALITY.md` §4.
18. After deploying `accounts.0026`, read the `reconcile_legacy_subscriptions` dry run in the build log; grant plans by hand to unpaid accounts that should keep premium (comps), then run `--apply --clear-unproven`. `accounts.0027` renames email-derived student usernames on deploy.
19. If the weekly Production Audit workflow ever uploaded Playwright reports or traces before this change, delete those artifacts and rotate the `QA_TEST_USER_*` and `LIVE_AUDIT_*` passwords.
20. The question reveal panel now generates missing AI sections in the background: production needs the django-q worker (item 7), and `REDIS_URL` for the shared concept cache.
21. The legacy `import_neet_pg` management command writes questions directly and does not apply the answer-label hold that the ingestion gate, Material Importer and NEET PG recall writer now apply; run `fix_answer_label_leaks` after any run of it.

## 14. Where things are

| What | Where |
|---|---|
| This report, progress log, RAG benchmark, data quality | `docs/audit/OVERNIGHT_MISSION_FINAL_REPORT.md`, `OVERNIGHT_MISSION_PROGRESS.md`, `RAG_BENCHMARK.md` (+ `rag/`), `DATA_QUALITY.md` (+ `data_quality/`) |
| Screenshots (review rounds 1-3, fix round) | `%USERPROFILE%\crack_local\screenshots\round1`, `round2`, `round3`, `fix1` (967 JPG) |
| E2E artifacts (screenshots, traces, videos of failures) | `%USERPROFILE%\crack_local\e2e\run1`, `run2`, `final` (HTML report `final\html\index.html`, `final\results.json`, 715 screenshots), `final-payments` |
| Logs (restore, migrations, servers, test runs, pip-audit, Bandit) | `%USERPROFILE%\crack_local\logs` |
| Database snapshot before the last migrations | `%USERPROFILE%\crack_local\backups\crack_local_before_wave3_migrations.dump` |
| Venv package list before the security upgrade | `%USERPROFILE%\crack_local\logs\venv_freeze_before_security_upgrade.txt` |

## 15. Branch and commits

`overnight-mission`, 69 commits since `overnight-mission-start` (`git log --oneline overnight-mission-start..overnight-mission`). It was not pushed: the repository is public and the history still holds the leaked credentials, so you should rotate first and then decide how to publish. Every commit message lists what it fixed and how it was verified.

During the run, the harness stopped one background launcher task ("Restart Postgres detached") because memory was low. The PostgreSQL server it had started kept running on :55432, and the task was not restarted.

## 16. Is it genuinely ready for local use?

**Yes, for local use and further development.** The restored data runs end to end on this machine with local auth, mock payments and offline AI. Every user-facing flow the suite covers passes on desktop, tablet and mobile. The backend suite (1,722 tests) and the frontend checks (types, lint, 332 unit tests) are green.

What it is **not** yet: verified against the real Supabase, Razorpay or AI providers, or deployed anywhere. Before any deploy, do §13 items 1–5 first. Rotate the leaked credentials, then purge them and the personal-data dumps from git history; the repository is public. Then do the deploy steps (items 6–11). Known limits that remain: Pillow 11.3 advisories (the moviepy pin); answer keys stored inside the text of 744 questions until `fix_answer_label_leaks --apply` is run (already hidden from viewers without access); and the low-severity leads in §9, which were reported but not verified.
