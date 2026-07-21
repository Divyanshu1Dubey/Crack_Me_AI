# Code Quality & Technical Debt

> Audit of dead code, unused files, duplicate logic, circular imports, large classes/functions, code smells, maintainability risks, and an overall technical-debt score.

---

## Technical Debt Score

**Score: 58 / 100** (Medium-High)

The codebase is functional and ships, but has accumulated debt in three areas: (1) scripts and fixtures scattered in non-standard locations, (2) backend views files have grown to 60–80 KB without decomposition, (3) documentation duplicates between `README.md` and `docs/` (now being consolidated).

| Dimension | Score | Notes |
|---|---:|---|
| Naming consistency | 80 | Consistent Python + TS naming |
| Function size | 50 | Several `views.py` exceed 1,500 lines |
| Class size | 70 | `AIService` is large (60+ KB) but bounded |
| Module cohesion | 65 | Some `accounts/views.py` responsibilities blur (auth + admin + subscriptions) |
| Dead code | 40 | Many ad-hoc loader scripts, `_import_*.py`, etc. |
| Duplicate logic | 55 | Token balance vs. transaction creation duplicated across views |
| Cyclomatic complexity | 60 | Several views have nested if/else for permissions |
| Test coverage | 40 | Backend tests exist (`test_all.py`) but coverage unknown |
| Documentation | 85 | Now consolidated to single `docs/` |
| Configuration | 70 | Mixed `.env`, `.env.example`, `render.yaml`, hardcoded constants |
| **Overall** | **58** | |

---

## 1. Dead Code

### Suspected dead code (no clear consumer)

| Path | Reason suspected dead |
|---|---|
| `backend/_import_pyq_md.py` | Superseded by fixture-first workflow |
| `backend/_import_pyq_txt.py` | Same |
| `backend/_import_sample.py` | Sample loading — only useful for initial dev |
| `backend/_fix_and_enrich_answers.py` | Not referenced in any management command |
| `backend/_manual_fix_answers.py` | Not in current workflow |
| `backend/_check_db.py` | May be a one-off script |
| `backend/_compact.py` | Not referenced |
| `backend/load_chunks.py`, `load_chunks.ps1` | One-off data migration |
| `backend/split_dump.py` | One-off |
| `backend/fix_db.py`, `seed_jobs.py`, `check_qs.py` (root) | One-off utilities |
| `backend/jobs_backup.json`, `q_debug.json`, `audit_report.csv` | Left-over data dumps |
| `backend/data_dump*.json` (root too) | Snapshot dumps; should be git-ignored except for tagged releases |
| `backend/Medura_Train/PYQ/cms_pyq_database_2018_2024.md` | Legacy one-off |
| `backend/RECOVERED_KEYS.txt` | Should NOT exist (per `SECURITY_SECRETS.md`) |
| `frontend/src/app/admin/` (verify) | Check if current |

### Verification needed

- [ ] `git grep -l "from _import_pyq"`
- [ ] `git grep -l "_manual_fix_answers"`
- [ ] Verify `RECOVERED_KEYS.txt` is git-ignored

### Recommendation

Remove all scripts confirmed as one-off / superseded. Move active maintenance scripts into `backend/scripts/` (already exists but mostly empty). Move data dumps to `backend/data_versions/` (already exists).

---

## 2. Unused Files

### Frontend

| File | Reason |
|---|---|
| `frontend/src/app/admin/` (verify contents) | Verify if pages are routed correctly |
| `frontend/src/utils/` | May duplicate `lib/utils.ts` |
| `frontend/devserver.err.log`, `devserver.log` | Stale logs at repo root — should be git-ignored |

### Backend

| File | Reason |
|---|---|
| `backend/scripts/` contents | Verify active vs. stale |
| `backend/scratch/` | Already git-ignored (verify) |

---

## 3. Duplicate Logic

### Token consumption pattern

`TokenBalance.consume_token()` is the canonical method. But `TokenTransaction` rows are created in **multiple views** (purchase, admin_grant, refund) — same pattern repeated.

**Fix**: Centralize in `TokenBalance.consume_token()` + a corresponding helper `TokenBalance.credit()`.

### Single-device session check

`accounts/middleware.py` duplicates session validation logic that `views.py` also performs for sensitive endpoints.

**Fix**: Single source of truth in middleware; views trust `request.user`.

### AI provider error filtering

`_PROVIDER_ERROR_PHRASES` filter is applied in `ai_engine/services.py`. Each `_call_*` method should use a single helper.

**Fix**: Wrap `_call_*` with a `_safe_call()` decorator.

### Subscription activation

`Subscription.activate_from_payment()` is the canonical method. But manual subscription creation in admin views bypasses it.

**Fix**: Always use `activate_from_payment()` (or new `activate_admin_grant()`).

---

## 4. Circular Imports

### Known risks

- `accounts/models.py` imports `from questions.models import ExamTrack` (line 12)
- `accounts/views.py` may import from `questions` for cross-app references
- `ai_engine/views.py` may import from `accounts`

### Recommendation

- Convert Eager FKs to Lazy (`from questions.models import ExamTrack` at module top is acceptable, but be aware)
- Use Django's `app_label.ModelName` string references where possible
- Run `python -c "import django; django.setup(); from django.apps import apps; apps.check_apps_ready()"` after each refactor

---

## 5. Large Classes / Functions

### Backend

| File | Size | Concern |
|---|---|---|
| `backend/ai_engine/services.py` | 57 KB / ~1,500 lines | `AIService` is a god class |
| `backend/ai_engine/views.py` | 25 KB | Many endpoints, shared helpers inlined |
| `backend/questions/views.py` | 76 KB | Largest view module — many responsibilities |
| `backend/accounts/views.py` | 67 KB | Auth + admin + subscriptions + devices |
| `backend/analytics/views.py` | large | Dashboard + campaigns + feedback |

**Refactor plan**:

1. Split `ai_engine/services.py` into:
   - `services/round_robin.py` (provider orchestration)
   - `services/callers.py` (`_call_groq`, `_call_cerebras`, …)
   - `services/filters.py` (error phrase filtering)
   - `services/cache.py` (24h response cache)

2. Split `questions/views.py` into:
   - `views/questions.py`
   - `views/flashcards.py`
   - `views/discussions.py`
   - `views/notes.py`

3. Split `accounts/views.py` into:
   - `views/auth.py`
   - `views/profile.py`
   - `views/tokens.py`
   - `views/admin.py`
   - `views/subscriptions.py`
   - `views/devices.py`

### Frontend

| File | Concern |
|---|---|
| `frontend/src/app/page.tsx` | Heavy dynamic imports; verify each `dynamic()` is `loading: () => <Skeleton/>` |
| `frontend/src/app/admin/page.tsx` | Multiple tabs — split into route segments |
| `frontend/src/lib/api.ts` | 200+ lines — split into `api/client.ts`, `api/interceptors.ts`, `api/endpoints/*.ts` |

---

## 6. Code Smells

### Shotgun surgery
- Changing the token metering policy requires edits in 6+ places: `TokenBalance`, `TokenTransaction`, `views.py` (multiple), `middleware.py`, `ai_engine/views.py`. Centralize.

### Long parameter lists
- `AIService.call_ai(prompt, system, temperature, max_tokens, ...)` — 7+ params. Group into a `CallConfig` dataclass.

### Feature envy
- `views.py` helpers access `request.user.token_balance` repeatedly — move to `CustomUser.consume_token()` proxy.

### Primitive obsession
- `correct_answer` is `CharField(1)` with values A/B/C/D. Wrap in `AnswerEnum` (Python `StrEnum`).

### Inappropriate intimacy
- `accounts/middleware.py` reads private fields on `UserDevice` and `CustomUser`. Add public methods.

### Dead branches
- Search for `# TODO` comments — many may be stale. Audit and either implement or remove.

---

## 7. Maintainability Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Single Render instance = single point of failure | High | Move to autoscaling |
| SQLite in production = data loss risk | High | Move to Postgres |
| No DRF throttling = abuse vector | High | Add throttling middleware |
| Token race condition | Medium | Add `transaction.atomic()` + `select_for_update` |
| RAG SQLite read/write contention | Medium | Migrate to `pgvector` |
| Fixture churn (5+ MB JSON in git) | Medium | JSONL format or seed migration |
| Magic strings in serializers | Low | Enum + factory pattern |
| Untyped API responses | Medium | Add TypeScript types in `lib/api/types.ts` |

---

## 8. Test Coverage

### Current

- `backend/test_all.py` — comprehensive suite (37 tests passing per audit)
- `backend/accounts/tests.py` — auth flow tests
- `backend/questions/tests.py` — question CRUD tests
- `backend/analytics/tests.py` — likely exists
- `frontend/tests/` — Playwright E2E (10 tests passing per audit)

### Gaps

- No coverage metric known (`coverage.py` not run)
- `ai_engine/services.py` is critical but under-tested
- RAG pipeline lacks regression tests
- Frontend component tests minimal

### Recommendation

```yaml
# .github/workflows/ci.yml addition
- name: Backend coverage
  run: |
    coverage run --source='backend' manage.py test
    coverage report --fail-under=70
```

---

## 9. Documentation Debt

### Issues found

- Provider count contradicted across 5 files (consolidated in this pass)
- Cerebras model name wrong in old `AI_SYSTEM.md`
- Old `API_KEYS.md` had outdated provider list + leaked keys
- `PASSWORD_RESET_SETUP.md` had a real-looking Gmail App Password fragment

### Status

✅ **Resolved in this pass** — `docs/` consolidated, `.docs/` deleted, all contradictions removed.

---

## 10. Configuration Debt

### Issues

- `DJANGO_SECRET_KEY` falls back to insecure default in DEBUG (good defense, but should add explicit "FAIL if DEBUG=False and SECRET_KEY looks insecure")
- AI provider keys silently skipped — should warn at startup if only 2 providers are configured (degraded mode)
- Token limits (`10/day`, `50/week`) hardcoded in `TokenConfig` defaults but overridden via env — verify sync

### Recommendation

- Add a startup check that validates config:
  ```python
  # backend/crack_cms/startup.py
  def validate_config():
      if not DEBUG and SECRET_KEY.startswith('django-insecure'):
          raise ImproperlyConfigured("Insecure SECRET_KEY in production")
      active_providers = sum(1 for k in AI_KEYS if k)
      if active_providers < 3:
          logger.warning(f"Only {active_providers} AI providers configured — degraded mode")
  ```

---

## 11. Security & Privacy Debt

(See [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md) for full audit.)

| Debt | Severity |
|---|---|
| No rate limiting | High |
| No CAPTCHA | Medium |
| No email verification | Medium |
| Upload magic-bytes not validated | Medium |
| JWT refresh not auto-rotated | Medium |
| Historical secret leak in git history | Resolved (key rotated) |

---

## 12. Dependency Hygiene

### Issues

- Most packages in `requirements.txt` have no upper bounds → breaking upgrades possible
- Unused packages: `together` (not in active round-robin), `aiml` (not active)
- `google-generativeai` is deprecated (per `ai_engine/services.py` warning); migrate to `google-genai`

### Recommendation

```txt
# Pin upper bounds on critical packages
Django>=5.0,<6.0
djangorestframework>=3.15,<4.0
djangorestframework-simplejwt>=5.3,<6.0
cryptography>=42.0,<44.0
```

Remove `together`, `aiml` if unused. Migrate from `google-generativeai` to `google-genai`.

---

## 13. Observability Debt

| Gap | Fix |
|---|---|
| No request tracing in dev | Add `django-debug-toolbar` |
| No structured log shipping | Add Datadog log shipping |
| No frontend performance monitoring | Verify Datadog RUM config |
| No business metrics dashboard | Build Mixpanel or PostHog dashboard |
| No uptime monitoring | Add UptimeRobot / BetterStack |

---

## 14. Prioritized Refactor Plan

| Priority | Item | Effort | Impact |
|---|---|---|---|
| P0 | Remove dead code (one-off scripts, leftover dumps) | 1 day | High |
| P0 | Move from SQLite to Postgres | 1 day | Critical |
| P0 | Add DRF throttling | 1 day | High |
| P1 | Split `accounts/views.py` and `questions/views.py` | 3 days | High |
| P1 | Add DB indexes | 4 hours | High |
| P1 | Add coverage CI gate | 1 day | High |
| P2 | Refactor `ai_engine/services.py` god class | 1 week | Medium |
| P2 | Migrate from `google-generativeai` to `google-genai` | 1 day | Medium |
| P2 | Pin upper bounds on requirements.txt | 2 hours | Medium |
| P3 | Replace LocMemCache with Redis | 1 day | Medium |
| P3 | Frontend component tests | 1 week | Medium |

---

## 15. Code Smell Catalog (grep targets)

```bash
# Find functions > 100 lines
git grep -nE "^\s*def [a-z_]+\(.*\):" backend/ | awk -F: '{print $1, $2}'

# Find views.py files > 50 KB
find backend -name "views.py" -size +50k

# Find TODOs older than 1 year
git log --since="1 year ago" --pretty=format: --name-only --diff-filter=A | sort -u | head

# Find duplicate string literals
git grep -nE "'user_id'|user_id" backend/accounts/ backend/ai_engine/

# Find print statements (should use logger)
git grep -nE "^\s*print\(" backend/

# Find bare except
git grep -nE "^\s*except:" backend/
```

---

## 16. See Also

- [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md)
- [`PERFORMANCE.md`](./PERFORMANCE.md)
- [`IMPROVEMENTS.md`](./IMPROVEMENTS.md) — Top 100 prioritized fixes
- [`AI_ASSISTANT_RULES.md`](./AI_ASSISTANT_RULES.md) — Conventions for future contributors
