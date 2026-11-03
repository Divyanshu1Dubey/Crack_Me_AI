# Overnight mission plan — 2026-11-01

Branch: `overnight-mission` (from `worktree-full-audit-fixes` @ 33532e0, tag `overnight-mission-start`).
Local infrastructure (outside git): `C:\Users\DIVYANSHU\crack_local\` (isolated Postgres cluster, restored storage, logs, backup copies).

## Ground rules

- Never push, deploy, touch production services/DB, send real email, or run real payments.
- The existing Postgres service on :5432 is **not** used. All restores go to an isolated cluster on **:55432**.
- Original backups are read-only; SHA-256 recorded in the progress file.
- `backend/.env` contains production secrets; local mode loads a separate `.env.localdev` (gitignored) instead.

## Priorities and dependencies

| # | Workstream | Depends on | Parallelisable |
|---|---|---|---|
| 0 | Safety: branch, tag, backup hashes, tooling inventory | — | — |
| 1 | Discovery: subsystem inventory + issue candidates (read-only workflow) | 0 | yes (background) |
| 2 | Recovery: isolated Postgres, restore `postgres` DB from cluster dump, verify, migrate a working copy, restore storage files | 0 | no (foundation) |
| 2b | Local architecture: env file, start/stop scripts, local auth (dev-only JWT), mock payments, console email, AI offline mode | 2 | partly |
| 3 | UI/UX: Playwright screenshots (3 viewports × 2 themes, logged-in), review, targeted redesign | 2b | review yes, edits partitioned |
| 4 | RAG: audit, eval set from recovered content, baseline vs alternatives, implement best, regression tests | 2 | yes |
| 5 | Functionality: student/admin/payment workflows end-to-end, fix breaks | 2b | partly |
| 6 | Security & performance second pass (find → adversarially verify → fix) | 2 | yes |
| 7 | Playwright E2E suite (student + admin + negative paths) | 2b, 5 | — |
| 8 | Fix/test loop, second audit pass | all | — |
| 9 | Reports: progress (continuous) + final report | all | — |

## Risks

- Supabase-specific objects (vault, graphql, realtime, pgvector) cannot restore into vanilla Postgres → restore `public` (app data) and `auth`/`storage` tables; document the rest.
- Login is Supabase-only in code → local auth mode needed for E2E; must be impossible to enable in production.
- Disk: ~18 GB free → no torch/CUDA-sized installs unless justified; keep screenshots compressed.
- External AI providers: benchmarks must not depend on them; offline/extractive mode for tests.

## Verification strategy

Django test suite (dev + CI mode), migration checks, `tsc`, `eslint`, `next build`, Playwright E2E against local servers on the restored DB, screenshot review, RAG metrics on a fixed eval set (methodology documented with the numbers).
