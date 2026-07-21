# Documentation Audit Report

**Date**: 2026-07-21
**Auditor**: Principal Architect (CrackLabs)
**Scope**: All existing documentation in `docs/` and the parallel `.docs/` created earlier

---

## 1. Documents That Already Exist

### `docs/` (operational, partial architectural)
| Path | Type | Purpose |
|---|---|---|
| `docs/README.md` | Index | Folder structure overview |
| `docs/setup/API_KEYS.md` | Setup | AI provider API key acquisition |
| `docs/setup/DATADOG_SETUP.md` | Setup | Datadog RUM + tracing env vars |
| `docs/setup/GMAIL_SETUP.md` | Setup | Gmail App Password for SMTP |
| `docs/setup/ICONS_SETUP.md` | Setup | Icons8 MCP + icon downloader |
| `docs/setup/NVIDIA_MISTRAL_SETUP.md` | Setup | NVIDIA Mistral provider setup |
| `docs/setup/OLLAMA_SETUP.md` | Setup | Ollama local fallback setup |
| `docs/setup/PASSWORD_RESET_SETUP.md` | Setup | Password reset / Gmail SMTP |
| `docs/setup/SECURITY_SECRETS.md` | Setup | Secret rotation + pre-commit scanning |
| `docs/guides/DATA_PIPELINE.md` | Guide | Question data flow + scripts |
| `docs/guides/QUESTION_MANAGEMENT_GUIDE.md` | Guide | All question-edit workflows |
| `docs/guides/QUESTION_MANUAL_UPDATE_GUIDE.md` | Guide | Django admin / shell / API / fixture |
| `docs/reference/AI_SYSTEM.md` | Reference | AI providers, explain-after-answer, RAG, token economy |
| `docs/reference/GIT_CHANGESET_REFERENCE.md` | Reference | NVIDIA Mistral git changeset summary |
| `docs/reports/DEPLOYMENT_CAPACITY_REPORT.md` | Report | Capacity + Render limitations audit |
| `docs/reports/IMPLEMENTATION_COMPLETE.md` | Report | Password-reset implementation report |
| `docs/reports/NVIDIA_INTEGRATION_SUMMARY.md` | Report | NVIDIA Mistral integration summary |
| `docs/backend/SUPABASE_READY_CHECKLIST.md` | Setup | Supabase migration checklist |
| `docs/codebase/.codebase-scan.txt` | Snapshot | Repository file tree (historical) |

### `.docs/` (created earlier — DUPLICATE, TO REMOVE)
| Path | Status |
|---|---|
| `.docs/INDEX.md` | Duplicate of existing docs/INDEX (now in `docs/INDEX.md`) |
| `.docs/PROJECT_OVERVIEW.md` | Partially overlaps `README.md` + `docs/` content |
| `.docs/ARCHITECTURE.md` | More thorough than existing `docs/`, but in wrong location |
| `.docs/FOLDER_STRUCTURE.md` | Similar to existing tree |
| `.docs/FEATURES.md` | New content, no equivalent |

---

## 2. Missing Documentation

These topics are referenced in code or `README.md` but have **no dedicated document**:

- ❌ **Database model reference** (every model, FK, index, constraint, business rule) — *required*
- ❌ **Complete API reference** (every endpoint with auth, request/response, status codes) — *required*
- ❌ **Authentication & authorization** (JWT flow, refresh, roles, protected routes) — *required*
- ❌ **Admin system** (dashboard, permissions, admin APIs, moderation) — *required*
- ❌ **Security audit** (CSRF/CORS/XSS/SQLi/secrets/rate-limit/file uploads) — *required*
- ❌ **Performance audit** (slow queries, missing indexes, N+1, bundle size, caching) — *required*
- ❌ **SEO audit** (titles, descriptions, OG, sitemap, schema, CWV) — *required*
- ❌ **Scaling roadmap** (1K → 1M users with infra/DB/cost) — *required*
- ❌ **Code quality / technical debt** (dead code, smells, debt score) — *required*
- ❌ **Top 100 prioritized improvements** — *required*
- ❌ **AI assistant permanent instructions** (architecture rules, glossary, conventions) — *required*

---

## 3. Outdated Documentation

| File | Issue |
|---|---|
| `docs/reference/AI_SYSTEM.md` | Says **7 providers** + 60s timeout; actual code has **11 providers** + 120s deadline + 15-20s per provider. Lists Cerebras as `llama-3.3-70b`; actual is `llama-3.1-8b`. Says `similar_topics` is part of explain payload (not in actual code). Says Python 3.14 in DB schema notes (Python 3.12 is CI baseline). |
| `docs/setup/API_KEYS.md` | Says **7 providers** + Ollama; missing NVIDIA Mistral, HuggingFace, Mistral Native (9 of the 11 cloud). Includes `ELEVENLABS_API_KEY` (not present in settings.py). Lists OpenRouter twice but missing 2nd OpenRouter key naming convention. |
| `docs/setup/PASSWORD_RESET_SETUP.md` | Contains a real-looking Gmail App Password fragment (`nlhdqbxklvcjxlki`) which should not appear in repo docs (per `SECURITY_SECRETS.md` policy). |
| `docs/reference/GIT_CHANGESET_REFERENCE.md` | States "10/11 active providers"; `DEPLOYMENT_CAPACITY_REPORT.md` says only 7 actually work reliably today. Contradictory. |
| `docs/guides/QUESTION_MANAGEMENT_GUIDE.md` | JSON payload example is truncated (`},` mid-array). Reads like working notes, not a guide. Refers to `python manage.py enrich_questions` as if it exists (no such management command found). |
| `docs/guides/DATA_PIPELINE.md` | Mentions scripts like `_import_pyq_txt.py`, `_import_pyq_md.py`, `_fix_and_enrich_answers.py` whose existence is not verified. `Enrichment Pipeline` section duplicates info in `QUESTION_MANAGEMENT_GUIDE.md`. |
| `docs/reports/DEPLOYMENT_CAPACITY_REPORT.md` | Mentions "1 worker, 4 threads" → "4 concurrent requests" but does not match gunicorn defaults documented elsewhere. **Note**: real start command has `--workers 1 --threads 4 --timeout 180`. |
| `docs/codebase/.codebase-scan.txt` | Truncated historical tree dump; no value for current engineering use. |

---

## 4. Duplicate Documentation

| Topic | Locations | Recommended Action |
|---|---|---|
| AI provider list / round-robin | `README.md`, `docs/reference/AI_SYSTEM.md`, `docs/setup/API_KEYS.md`, `docs/setup/NVIDIA_MISTRAL_SETUP.md`, `docs/setup/OLLAMA_SETUP.md` (5×) | Consolidate into `docs/ARCHITECTURE.md#ai-architecture` + `docs/setup/AI_PROVIDERS.md` |
| Gmail SMTP setup | `docs/setup/GMAIL_SETUP.md` ≈ `docs/setup/PASSWORD_RESET_SETUP.md` (≈ 80% overlap) | Merge into `docs/setup/EMAIL_SETUP.md` |
| Question editing | `docs/guides/QUESTION_MANAGEMENT_GUIDE.md` ≈ `docs/guides/QUESTION_MANUAL_UPDATE_GUIDE.md` (large overlap on Admin / Shell / API / Fixture) | Merge into `docs/guides/QUESTION_MANAGEMENT.md` (single canonical guide) |
| Question data pipeline | `README.md` + `docs/guides/DATA_PIPELINE.md` + `docs/guides/QUESTION_MANAGEMENT_GUIDE.md` | Keep one canonical: `docs/guides/QUESTION_MANAGEMENT.md` |
| NVIDIA Mistral integration | `docs/setup/NVIDIA_MISTRAL_SETUP.md` ≈ `docs/reports/NVIDIA_INTEGRATION_SUMMARY.md` ≈ `docs/reference/GIT_CHANGESET_REFERENCE.md` | Keep one canonical: `docs/setup/AI_PROVIDERS.md` (delete the other two as historical artifacts) |
| Implementation reports | `docs/reports/IMPLEMENTATION_COMPLETE.md` (login + reset) + `docs/reports/DEPLOYMENT_CAPACITY_REPORT.md` (capacity) + `docs/reports/NVIDIA_INTEGRATION_SUMMARY.md` | **Retain** — these are point-in-time reports, not duplicates |
| `.docs/*` (5 files) vs new consolidated `docs/*` | All 5 `.docs/` files duplicate or will be superseded by the new consolidated tree | **Delete `.docs/` entirely** |

---

## 5. Contradictory Information

| Claim | Source A | Source B |
|---|---|---|
| AI provider count | `AI_SYSTEM.md`: 7 + Ollama | `NVIDIA_MISTRAL_SETUP.md`: 11 + Ollama (correct in code) |
| Cerebras model | `AI_SYSTEM.md`: `llama-3.3-70b` | `services.py` code: `llama-3.1-8b` |
| Production API URL | `frontend/src/lib/api.ts`: DigitalOcean `crackcms-vsthc.ondigitalocean.app` | `README.md`: Render `crackcms-backend.onrender.com` (flagged unhealthy in code) |
| Explain-after-answer JSON shape | `AI_SYSTEM.md`: includes `similar_topics` | `services.py` actual: `is_correct, correct_answer, why_correct, why_others_wrong, mnemonic, high_yield_points, textbook_reference` |
| Strict proven AI quota | `DEPLOYMENT_CAPACITY_REPORT.md`: `60 RPM` | `AI_SYSTEM.md` mentions higher per-provider totals that aren't all working |
| Bundled JS bundle location | (none) | N/A — first mention goes in `PERFORMANCE.md` |

---

## 6. Documents That Should Be Merged

1. `GMAIL_SETUP.md` + `PASSWORD_RESET_SETUP.md` → `setup/EMAIL_SETUP.md`
2. `QUESTION_MANAGEMENT_GUIDE.md` + `QUESTION_MANUAL_UPDATE_GUIDE.md` → `guides/QUESTION_MANAGEMENT.md`
3. `API_KEYS.md` + `NVIDIA_MISTRAL_SETUP.md` + (extracts from `AI_SYSTEM.md`) → `setup/AI_PROVIDERS.md`
4. `OLLAMA_SETUP.md` → folds into `setup/AI_PROVIDERS.md` (it's a provider)
5. `NVIDIA_INTEGRATION_SUMMARY.md` + `GIT_CHANGESET_REFERENCE.md` → historical archive only; keep one combined changelog in `docs/changelog/`
6. New comprehensive `ARCHITECTURE.md`, `DATA_MODEL.md`, `API_REFERENCE.md`, `AUTHENTICATION.md`, `ADMIN_SYSTEM.md`, `SECURITY_AUDIT.md`, `PERFORMANCE.md`, `SEO.md`, `SCALING_ROADMAP.md`, `CODE_QUALITY.md`, `IMPROVEMENTS.md`, `AI_ASSISTANT_RULES.md`, `FOLDER_STRUCTURE.md`, `FEATURES.md`, `INDEX.md`, `PROJECT_OVERVIEW.md` under `docs/`

---

## 7. Documents That Should Be Deleted

| Path | Reason |
|---|---|
| `.docs/` (entire directory, 5 files) | Duplicate of consolidated `docs/`; causes navigation confusion |
| `docs/codebase/.codebase-scan.txt` | Historical snapshot with no current value |
| `docs/reports/NVIDIA_INTEGRATION_SUMMARY.md` | Superseded by `docs/setup/AI_PROVIDERS.md` |
| `docs/reference/GIT_CHANGESET_REFERENCE.md` | Same content as the summary report; keep only the summary in `docs/changelog/` |
| `docs/guides/DATA_PIPELINE.md` | Most of its content lives in the merged `guides/QUESTION_MANAGEMENT.md` |
| `docs/setup/PASSWORD_RESET_SETUP.md` | Subsumed by `setup/EMAIL_SETUP.md` |
| `docs/setup/NVIDIA_MISTRAL_SETUP.md` | Subsumed by `setup/AI_PROVIDERS.md` |
| `docs/setup/OLLAMA_SETUP.md` | Subsumed by `setup/AI_PROVIDERS.md` |
| `docs/guides/QUESTION_MANUAL_UPDATE_GUIDE.md` | Subsumed by `guides/QUESTION_MANAGEMENT.md` |

---

## 8. Documentation Quality Score

| Dimension | Score (0–100) | Notes |
|---|---:|---|
| Coverage (breadth of topics) | 35 | Setup & question guides exist; **no API ref, no data-model doc, no security/performance/SEO audits, no scaling roadmap, no AI-assistant rules** |
| Accuracy / freshness | 30 | Multiple outdated provider counts, wrong model names, contradictory JSON shapes, exposed-looking password fragment |
| Internal consistency | 25 | 5 different AI provider counts across 5 files; contradictory production URLs |
| Organization / navigation | 55 | Has folder structure but no real `INDEX.md`; `.docs/` is a parallel disorganized tree |
| Diagrams (mermaid, ASCII) | 60 | Some good diagrams in `AI_SYSTEM.md`, `DATA_PIPELINE.md`, `QUESTION_MANAGEMENT_GUIDE.md`; otherwise mostly prose |
| Actionability (setup / run / debug) | 70 | Setup guides are usable; question guides are good for the operations they cover |
| Security & privacy posture | 45 | `SECURITY_SECRETS.md` exists and is good, but `PASSWORD_RESET_SETUP.md` contradicts the policy |
| **Overall** | **45 / 100** | Strong on operations, weak on architecture; needs comprehensive consolidation |

---

## 9. Recommended Documentation Structure

```
docs/
├── INDEX.md                              # Master index (NEW — single entry point)
├── PROJECT_OVERVIEW.md                   # Vision / users / stack / integrations (NEW)
├── ARCHITECTURE.md                       # Full system architecture w/ mermaid (NEW, replaces .docs/ARCHITECTURE.md)
├── FOLDER_STRUCTURE.md                   # Every important folder (NEW)
├── FEATURES.md                           # Per-feature reference (NEW, replaces .docs/FEATURES.md)
│
├── DATA_MODEL.md                         # Every model, FK, index, business rule (NEW)
├── API_REFERENCE.md                      # Every endpoint (NEW)
├── AUTHENTICATION.md                     # JWT/session/refresh/roles/protected routes (NEW)
├── ADMIN_SYSTEM.md                       # Admin dashboard, APIs, moderation (NEW)
│
├── SECURITY_AUDIT.md                     # JWT/CSRF/CORS/XSS/SQLi/secrets/etc. (NEW)
├── PERFORMANCE.md                        # Queries, indexes, bundle, caching (NEW)
├── SEO.md                                # SEO + Core Web Vitals audit (NEW)
│
├── SCALING_ROADMAP.md                    # Current → 1M users (NEW)
├── CODE_QUALITY.md                       # Dead code, smells, debt score (NEW)
├── IMPROVEMENTS.md                       # Top 100 ranked improvements (NEW)
├── AI_ASSISTANT_RULES.md                 # Permanent AI-assistant instructions (NEW)
│
├── audit/
│   └── DOCS_AUDIT.md                     # This file (NEW)
│
├── setup/                                # Operational setup (existing, consolidated)
│   ├── AI_PROVIDERS.md                   # All 11 providers + Ollama (NEW — consolidates 5 files)
│   ├── EMAIL_SETUP.md                    # Gmail SMTP + password reset (NEW — consolidates 2 files)
│   ├── DATADOG_SETUP.md                  # (kept)
│   ├── ICONS_SETUP.md                    # (kept)
│   └── SUPABASE_SETUP.md                 # (NEW — from docs/backend/SUPABASE_READY_CHECKLIST.md)
│
├── guides/                               # Workflow guides (existing, consolidated)
│   └── QUESTION_MANAGEMENT.md            # All question-edit workflows (NEW — consolidates 3 files)
│
├── reference/                            # Reference docs (kept)
│   ├── SECURITY_SECRETS.md               # (kept)
│   └── DEPLOYMENT_CAPACITY.md            # (NEW — from reports/DEPLOYMENT_CAPACITY_REPORT.md)
│
├── reports/                              # Point-in-time implementation reports (kept)
│   ├── IMPLEMENTATION_LOGIN_RESET.md     # (kept from IMPLEMENTATION_COMPLETE.md)
│   └── CHANGELOG.md                      # (NEW — combines NVIDIA + git-changeset refs)
│
└── (removed) docs/codebase/              # Historical; remove .codebase-scan.txt
```

**Cleanup actions taken in this pass**:
- ✅ Deleted `.docs/` (5 duplicate files)
- ✅ Created 16 new top-level docs (architecture, model, API, auth, admin, security, performance, SEO, scaling, code-quality, improvements, AI rules, etc.)
- ✅ Consolidated `setup/` folder from 8 → 5 files (merged Gmail + AI keys + Supabase)
- ✅ Consolidated `guides/` from 3 → 1 file (single canonical question-management guide)
- ✅ Created `INDEX.md` as the single navigation entry point
- ⏳ Old `docs/setup/PASSWORD_RESET_SETUP.md`, `NVIDIA_MISTRAL_SETUP.md`, `OLLAMA_SETUP.md`, `docs/reports/NVIDIA_INTEGRATION_SUMMARY.md`, `docs/reference/GIT_CHANGESET_REFERENCE.md`, `docs/guides/QUESTION_MANUAL_UPDATE_GUIDE.md`, `docs/guides/DATA_PIPELINE.md`, `docs/codebase/.codebase-scan.txt` marked for deletion in the cleanup pass

---

## 10. Guiding Principles

1. **Single source of truth**: Every topic gets one canonical file. Cross-reference instead of copy.
2. **Accuracy over verbosity**: Code is the final authority — docs must match it. Outdated docs are deleted, not patched.
3. **No secrets in docs**: All credentials referenced by env-var name only; never paste real keys.
4. **Diagrams where they help**: Mermaid for architecture/flow; tables for API/model references.
5. **Actionable**: Every doc must answer "what is this?" and "what do I do next?".
6. **AI-friendly**: Structured headings, table-of-contents, mermaid blocks so Claude Code can navigate quickly.

**Target overall documentation quality score after consolidation: 85 / 100**.
