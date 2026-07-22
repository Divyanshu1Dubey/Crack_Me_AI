# AI Assistant Rules — Permanent Instructions

> **These are permanent rules for any future AI assistant (Claude Code, Copilot, Cursor, etc.) working in this repository.**
> Read `CLAUDE.md` first, then `docs/INDEX.md`, then this file.

---

## 1. Architecture Rules (NEVER violate)

1. **Frontend never talks to AI providers directly** — all AI calls flow through Django `ai_engine/services.py`.
2. **Backend never embeds API keys in code** — env vars only. `backend/.env` is git-ignored.
3. **AI provider rotation is round-robin** — do not add hardcoded provider preferences.
4. **Tokens are always metered** — every AI endpoint checks `TokenBalance.consume_token()` before provider call.
5. **All admin mutations write `AdminAuditLog`** — never bypass.
6. **Question fixtures are the source of truth** — DB → `_export_fixture.py` → commit JSON → push.
7. **RAG ingestion is via `_train_all.py` or `KnowledgeScanView`** — never write directly to `rag_store.sqlite3`.
8. **Subscription activation goes through `Subscription.activate_from_payment()`** — never write the Subscription row directly.
9. **Single-device enforcement via `CustomUser.session_key` + `UserDevice`** — do not introduce alternative session mechanisms.
10. **CSP and security headers are set in `vercel.json`** — modify with care.

---

## 2. Coding Conventions

### Python (Django)

- PEP 8 + Black formatter (88 char line length)
- Type hints for all new functions
- Use `select_related` / `prefetch_related` in every list-view queryset
- Always wrap multi-step DB writes in `transaction.atomic()`
- Use `logger = logging.getLogger(__name__)` — no `print()`
- DRF: prefer `ViewSet` + `Router` over function views for consistency
- DRF: `permission_classes = [IsAuthenticated]` is the default; explicit `[IsSuperUser]` for admin-only
- Models: explicit `Meta.ordering` when natural order matters
- Models: explicit `db_index=True` on FK + frequently-filtered fields
- Use `StrEnum` for choice fields instead of literal strings
- Migrations: always auto-generate with `python manage.py makemigrations`; never hand-edit
- Tests: use Django `TestCase`; aim for >70% coverage on new code

### TypeScript (Next.js)

- ESLint config from `eslint-config-next` — no overrides without justification
- Use `next/image` not `<img>`
- Use `next/link` for internal navigation
- Use `next/font` for fonts (already done in layout.tsx)
- Use React Server Components by default; `'use client'` only when needed
- Use `next/dynamic` for heavy client components (charts, markdown)
- Avoid `dangerouslySetInnerHTML` — use `react-markdown` with sanitization
- API calls go through `frontend/src/lib/api.ts` — never `axios` directly in components
- Auth state via `useAuth()` hook from `frontend/src/lib/auth.tsx`
- Type all API responses (add to `frontend/src/lib/api/types.ts` if missing)

### Database

- SQLite for development, Postgres for production (set `DATABASE_URL`)
- All migrations must be reversible
- Never delete a migration once applied (use a new migration to undo)

### API

- RESTful conventions: `GET` for read, `POST` for create, `PATCH` for partial update, `DELETE` for delete
- Return JSON with consistent shape: `{ "data": ..., "error": ..., "code": ... }`
- Pagination: `?page=&page_size=`; default `page_size=20`
- All write endpoints require auth
- All admin endpoints require `is_superuser`
- All AI endpoints are token-metered
- Use 402 (Payment Required) for insufficient tokens

### Git

- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`, `security:`
- One concern per commit
- Branch names: `feature/...`, `fix/...`, `chore/...`
- Never force-push to main
- Always update `questions_fixture.json` in the same commit as DB changes

---

## 3. Business Rules

1. **Token economy is the growth lever** — every AI feature must be token-metered; admin/staff bypass.
2. **Single-device prevents account sharing** — `session_invalid` → force logout.
3. **Free tier is intentionally limited** — 10/day, 50/week. Do not increase without product approval.
4. **All payment changes go through Razorpay** — no alternative gateways without CFO sign-off.
5. **Question content is medical** — every correction must be reviewed by a subject-matter expert.
6. **Fixture is the deploy contract** — `build.sh` loads it; if broken, build fails.
7. **Free-tier users get all features but rate-limited** — never gate features behind paywall without PM approval.
8. **Admin actions are audited** — `AdminAuditLog` is append-only.
9. **Subscriptions extend existing subscriptions** — never silently create parallel subscriptions.
10. **Refund tokens only on AI failure** — do not refund for bad AI output (rate-limit user instead).

---

## 4. Critical Files (DO NOT modify casually)

| File | Why critical |
|---|---|
| `backend/crack_cms/settings.py` | Env loading, app registry, middleware, security |
| `backend/crack_cms/urls.py` | Root URL routing |
| `backend/ai_engine/services.py` | AI provider orchestration — affects every AI call |
| `backend/accounts/models.py` | User + token models — affects every authenticated request |
| `backend/questions/models.py` | Question schema — affects every MCQ + fixture |
| `backend/questions_fixture.json` | Production seed |
| `backend/build.sh` | Render deploy contract |
| `frontend/src/lib/api.ts` | Centralized HTTP client — touches every API call |
| `frontend/src/lib/auth.tsx` | Auth context — touches every authenticated route |
| `frontend/next.config.ts` | Build config (output file tracing root) |
| `frontend/vercel.json` | Security headers + rewrites |
| `backend/chroma_db/rag_store.sqlite3` | RAG index (committed via LFS) |
| `.github/workflows/ci.yml` | CI pipeline — affects every PR |

If you must modify a critical file, **explain why in the PR description and tag a reviewer**.

---

## 5. Files That Should Never Be Modified

| Path | Reason |
|---|---|
| `backend/chroma_db/rag_store.sqlite3` | RAG cache — regenerate via `_train_all.py`, never edit |
| `backend/db.sqlite3` (when committed) | Production seed — only via `loaddata` |
| `backend/questions_fixture.json` | Only via `_export_fixture.py` |
| `backend/RECOVERED_KEYS.txt` | Should not exist; if it does, do not commit |
| `backend/.env` | Git-ignored secrets — never commit |
| Git LFS objects | Don't manually edit |
| `.github/skills/`, `.cursor/skills/` | Symlinks to skills; modify source instead |

---

## 6. Deployment Workflow

```
1. Create branch: git checkout -b feature/my-change
2. Make changes + tests
3. Run locally:
   - cd backend && python manage.py makemigrations --check --dry-run
   - cd backend && python manage.py test
   - cd frontend && npm run lint && npm run build
4. If question content changed:
   - cd backend && python _export_fixture.py
   - git add questions_fixture.json
5. git commit -m "feat: ..."
6. Push branch + open PR
7. CI runs: lint, test, bandit, safety, build
8. Merge to main → Render + Vercel auto-deploy
9. Verify production: curl https://crackcms-vsthc.ondigitalocean.app/api/health/
10. Monitor Sentry + Datadog for errors
```

---

## 7. Testing Workflow

### Backend

```bash
cd backend
python manage.py test --verbosity=2            # All tests
python manage.py test accounts.tests            # Auth tests
python test_all.py --quick                      # Quick suite (skip AI)
python test_all.py --endpoints-only             # HTTP endpoints only
python test_all.py --auth-only                  # Auth flow only
python test_api_keys.py                         # Verify AI keys
```

### Frontend

```bash
cd frontend
npm run lint                                    # ESLint
npm run build                                   # Production build
PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test --workers=1   # E2E
```

### Pre-deploy checklist

- [ ] `manage.py check --deploy` passes (or warnings acknowledged)
- [ ] `manage.py makemigrations --check --dry-run` reports no missing migrations
- [ ] `manage.py test` passes
- [ ] `npm run lint` passes
- [ ] `npm run build` succeeds
- [ ] `bandit -r backend/` reports no high-severity issues
- [ ] `safety check` reports no critical CVEs
- [ ] Fixture is updated if question content changed
- [ ] `docs/INDEX.md` is updated if any doc changed

---

## 8. Git Workflow

- Default branch: `main`
- Feature branches: `feature/<short-desc>`
- Bug fix branches: `fix/<short-desc>`
- Chore branches: `chore/<short-desc>`
- Hotfix branches: `hotfix/<short-desc>` (for production emergencies)
- Squash-merge feature branches
- Rebase-merge bug fixes
- Tag releases: `v1.2.3` format
- Commit messages: Conventional Commits

### Forbidden

- Force-push to `main`
- Direct commits to `main`
- Merge commits in feature branches
- Large binary files outside Git LFS
- Commits containing secrets (pre-commit hook blocks)

---

## 9. Common Mistakes to Avoid

| Mistake | Why it's wrong |
|---|---|
| Adding an AI provider without updating `services.py` round-robin | Won't be used |
| Editing `questions_fixture.json` by hand without re-exporting | DB drift |
| Returning 200 with error body | Use proper status codes |
| Using `print()` for logging | Use `logger` |
| Storing API keys in `frontend/.env.local` | Use backend env only |
| Creating migrations manually | Always `makemigrations` |
| Skipping `select_related` | N+1 query bug |
| Adding `is_staff=True` for admin features | Use `is_superuser` instead |
| Pasting real keys in docs | Pre-commit hook will block |
| Forgetting to update `TokenConfig` after raising limits | Affects every user |
| Hardcoding dates for subscription expiry | Always use `timezone.now()` |
| Mixing `JWT` and `SessionAuthentication` in the same view | Pick one |
| Returning PII in Sentry events | Set `SENTRY_SEND_DEFAULT_PII=False` |

---

## 10. Project Glossary

| Term | Meaning |
|---|---|
| **PYQ** | Previous Year Question (UPSC CMS exam) |
| **CMS** | Combined Medical Services (UPSC exam) |
| **RAG** | Retrieval-Augmented Generation |
| **SM-2** | SuperMemo 2 spaced repetition algorithm |
| **TF-IDF** | Term Frequency–Inverse Document Frequency |
| **Token** | AI call credit (1 token = 1 AI call) |
| **Free tokens** | Daily (10) + Weekly (50) quota |
| **Purchased tokens** | Bought via Razorpay, never expire |
| **Feedback credits** | +2 tokens for verified feedback |
| **Single-device** | One active session per user (enforced via `UserDevice`) |
| **Fixture** | `questions_fixture.json` — production seed |
| **Round-robin** | Provider rotation pattern (11 providers + Ollama) |
| **CrackLabs** | The company |
| **CrackCMS** | The product (UPSC CMS prep platform) |
| **Crack_Me_AI** | Brand name of the product |
| **`session_invalid`** | Error code emitted when single-device check fails |
| **`insufficient_tokens`** | Error code for 402 Payment Required |
| **CMS_SYSTEM_PROMPT** | The system prompt that grounds AI responses in CMS exam context |

---

## 11. Code Review Checklist

When reviewing a PR, verify:

- [ ] Production code is not modified without justification
- [ ] No new dependencies without `requirements.txt` / `package.json` update
- [ ] Migrations are auto-generated
- [ ] DB queries use `select_related` / `prefetch_related` where needed
- [ ] All write endpoints check permissions
- [ ] All admin endpoints require `is_superuser`
- [ ] All AI endpoints check tokens
- [ ] No secrets in code or commits
- [ ] No PII in Sentry events
- [ ] Tests added for new logic
- [ ] Fixture updated if question content changed
- [ ] Docs updated if architecture or API changed
- [ ] CI passes (lint, test, build, bandit, safety)
- [ ] Frontend bundle size not regressed >5%
- [ ] No new dependencies on Render free tier

---

## 12. When You're Stuck

1. Read `docs/INDEX.md` → relevant doc
2. Check `docs/AUDIT/DOCS_AUDIT.md` for known outdated sections
3. Grep `git log -p --all -S "<term>"` for prior decisions
4. Check `.github/copilot-instructions.md` for Copilot's working rules
5. Search `.github/skills/` and `.agent/skills/` for relevant skill
6. Ask the user — do not invent behavior

---

## 13. See Also

- [`INDEX.md`](./INDEX.md) — full doc index
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`AUTHENTICATION.md`](./AUTHENTICATION.md)
- [`ADMIN_SYSTEM.md`](./ADMIN_SYSTEM.md)
- [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md)
- [`IMPROVEMENTS.md`](./IMPROVEMENTS.md)
