# Documentation Index

> **Single entry point** for all CrackCMS documentation.
> Future Claude sessions: **read `CLAUDE.md` first, then `docs/INDEX.md`**, before opening repository code.

---

## Reading Order

1. **[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)** — *what & why*
2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — *how (system + data flow + diagrams)*
3. **[FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md)** — *where things live*
4. **[DATA_MODEL.md](./DATA_MODEL.md)** — *the schema*
5. **[API_REFERENCE.md](./API_REFERENCE.md)** — *every endpoint*
6. **[AUTHENTICATION.md](./AUTHENTICATION.md)** — *who can do what*
7. **[FEATURES.md](./FEATURES.md)** — *per-feature drilldown*

For audits / improvements:
- **[SECURITY_AUDIT.md](./SECURITY_AUDIT.md)** · **[PERFORMANCE.md](./PERFORMANCE.md)** · **[SEO.md](./SEO.md)** · **[CODE_QUALITY.md](./CODE_QUALITY.md)**
- **[SCALING_ROADMAP.md](./SCALING_ROADMAP.md)** · **[IMPROVEMENTS.md](./IMPROVEMENTS.md)** · **[AI_ASSISTANT_RULES.md](./AI_ASSISTANT_RULES.md)**

For hands-on work:
- **[setup/](./setup/)** — AI providers, Email, Datadog, Icons, Supabase
- **[guides/](./guides/)** — Question management
- **[reference/](./reference/)** — Security secrets, Deployment capacity
- **[reports/](./reports/)** — Implementation reports, changelog

---

## Master Map

### Architecture & Reference (read-first)

| File | Purpose |
|---|---|
| [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) | Product vision, target users, tech stack, integrations, repo layout |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture with mermaid diagrams (frontend, backend, AI, auth, deployment, data flow) |
| [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Every important folder: purpose, dependencies, key files |
| [FEATURES.md](./FEATURES.md) | Per-feature reference (purpose, files, models, APIs, user flows) |
| [DATA_MODEL.md](./DATA_MODEL.md) | Every model, FK, index, constraint, business rule, lifecycle, bottlenecks |
| [API_REFERENCE.md](./API_REFERENCE.md) | Every endpoint: auth, request/response, status codes, errors, examples |
| [AUTHENTICATION.md](./AUTHENTICATION.md) | JWT/session/refresh, roles, authorization, security model, protected routes |
| [ADMIN_SYSTEM.md](./ADMIN_SYSTEM.md) | Admin dashboard, permissions, admin APIs, moderation, management features |

### Audits

| File | Purpose |
|---|---|
| [SECURITY_AUDIT.md](./SECURITY_AUDIT.md) | JWT / CSRF / CORS / XSS / SQLi / secrets / rate limit / uploads / dependency vulnerabilities |
| [PERFORMANCE.md](./PERFORMANCE.md) | Slow queries, missing indexes, N+1, bundle size, caching, memory, recommendations |
| [SEO.md](./SEO.md) | Titles, descriptions, OG, Twitter, schema, sitemap, Core Web Vitals, accessibility |
| [CODE_QUALITY.md](./CODE_QUALITY.md) | Dead code, duplicate logic, large classes/functions, technical-debt score |

### Strategy

| File | Purpose |
|---|---|
| [SCALING_ROADMAP.md](./SCALING_ROADMAP.md) | Scaling plan: current → 1K → 10K → 50K → 100K → 500K → 1M users (infra, DB, AI, cost) |
| [IMPROVEMENTS.md](./IMPROVEMENTS.md) | Top 100 prioritized improvements (impact, difficulty, time, value, priority) |

### Meta

| File | Purpose |
|---|---|
| [AI_ASSISTANT_RULES.md](./AI_ASSISTANT_RULES.md) | Permanent instructions for future AI assistants (architecture rules, conventions, glossary) |
| [KNOWN_GAPS.md](./KNOWN_GAPS.md) | Verification status (now 100% verified — historical log) |
| [audit/DOCS_AUDIT.md](./audit/DOCS_AUDIT.md) | Audit of pre-consolidation docs/ — what existed, what was duplicated, what was deleted |
| [audit/FINAL_REPORT.md](./audit/FINAL_REPORT.md) | Final consolidation report: 100/100 quality score, 12+ critical corrections applied |
| **[AUDIT_2026_07_27.md](./AUDIT_2026_07_27.md)** | Master audit of `material_importer`, fixture migration, and recent diffs (this session) |
| **[MATERIAL_IMPORTER_AUDIT.md](./MATERIAL_IMPORTER_AUDIT.md)** | Deep dive on the new DOCX/PDF/PPTX ingestion app + bug list |
| **[HIGH_PRIORITY_FIXES.md](./HIGH_PRIORITY_FIXES.md)** | Top 10 ranked fixes ready to ship |
| **[LOW_PRIORITY_FIXES.md](./LOW_PRIORITY_FIXES.md)** | Backlog of low-priority / future-work items |
| **[NEXT_STEPS.md](../NEXT_STEPS.md)** | Session handoff for the next Claude |

---

## `setup/` — Operational Setup

| File | Purpose |
|---|---|
| [setup/AI_PROVIDERS.md](./setup/AI_PROVIDERS.md) | All 11 AI providers + Ollama fallback (consolidates former `API_KEYS.md` + `NVIDIA_MISTRAL_SETUP.md` + `OLLAMA_SETUP.md`) |
| [setup/EMAIL_SETUP.md](./setup/EMAIL_SETUP.md) | Gmail SMTP + password-reset flow (consolidates former `GMAIL_SETUP.md` + `PASSWORD_RESET_SETUP.md`) |
| [setup/DATADOG_SETUP.md](./setup/DATADOG_SETUP.md) | Datadog RUM + backend tracing env vars |
| [setup/ICONS_SETUP.md](./setup/ICONS_SETUP.md) | Icons8 MCP + bulk icon downloader |
| [setup/SUPABASE_SETUP.md](./setup/SUPABASE_SETUP.md) | Supabase Postgres + migration checklist |

## `guides/` — Process Guides

| File | Purpose |
|---|---|
| [guides/QUESTION_MANAGEMENT.md](./guides/QUESTION_MANAGEMENT.md) | Canonical guide for editing questions (Admin / Shell / API / Fixture / CSV review) — consolidates 3 former files |

## `reference/` — Reference Material

| File | Purpose |
|---|---|
| [reference/SECURITY_SECRETS.md](./reference/SECURITY_SECRETS.md) | Secret rotation policy + pre-commit scanner |
| [reference/DEPLOYMENT_CAPACITY.md](./reference/DEPLOYMENT_CAPACITY.md) | Capacity audit, Render/DO limits, AI quota floors |

## `reports/` — Point-in-time Implementation Reports

| File | Purpose |
|---|---|
| [reports/IMPLEMENTATION_LOGIN_RESET.md](./reports/IMPLEMENTATION_LOGIN_RESET.md) | Login + password-reset feature completion report |
| [reports/CHANGELOG.md](./reports/CHANGELOG.md) | Historical implementation log (NVIDIA Mistral integration + docs consolidation) |

## `knowledge-base/` — Monica AI Tutor Knowledge Platform

| File | Purpose |
|---|---|
| [knowledge-base/ARCHITECTURE.md](./knowledge-base/ARCHITECTURE.md) | Source-whitelisted RAG + KG + citation engine backing Monica |
| [knowledge-base/SOURCES.md](./knowledge-base/SOURCES.md) | Legally-defensible source whitelist (NCBI / OpenStax / Govt / Internal only) |
| [knowledge-base/SETUP.md](./knowledge-base/SETUP.md) | Supabase + Upstash Redis + Cloudflare CDN one-time setup |
| [knowledge-base/INGESTION.md](./knowledge-base/INGESTION.md) | How to ingest new content + run daily/weekly ops |

---

## Cross-Reference Table

| Topic | Canonical Document |
|---|---|
| AI providers & round-robin | [ARCHITECTURE.md § AI Architecture](./ARCHITECTURE.md#4-ai-architecture) + [setup/AI_PROVIDERS.md](./setup/AI_PROVIDERS.md) |
| Token economy | [FEATURES.md § 5 Token Economy](./FEATURES.md#5-token-economy) + [DATA_MODEL.md § accounts](./DATA_MODEL.md#accounts-app) |
| Authentication flow | [AUTHENTICATION.md](./AUTHENTICATION.md) + [ARCHITECTURE.md § Authentication](./ARCHITECTURE.md#5-authentication-flow) |
| Database schema | [DATA_MODEL.md](./DATA_MODEL.md) |
| Every API endpoint | [API_REFERENCE.md](./API_REFERENCE.md) |
| Question management workflow | [guides/QUESTION_MANAGEMENT.md](./guides/QUESTION_MANAGEMENT.md) |
| Gmail/SMTP setup | [setup/EMAIL_SETUP.md](./setup/EMAIL_SETUP.md) |
| Supabase migration | [setup/SUPABASE_SETUP.md](./setup/SUPABASE_SETUP.md) |
| Datadog observability | [setup/DATADOG_SETUP.md](./setup/DATADOG_SETUP.md) |
| CI/CD | [ARCHITECTURE.md § Deployment](./ARCHITECTURE.md#7-deployment-architecture) |
| Security posture | [SECURITY_AUDIT.md](./SECURITY_AUDIT.md) |
| Performance bottlenecks | [PERFORMANCE.md](./PERFORMANCE.md) |
| SEO | [SEO.md](./SEO.md) |
| Scaling plan | [SCALING_ROADMAP.md](./SCALING_ROADMAP.md) |
| Prioritized improvements | [IMPROVEMENTS.md](./IMPROVEMENTS.md) |
| AI-assistant rules | [AI_ASSISTANT_RULES.md](./AI_ASSISTANT_RULES.md) |
| Knowledge base / Monica | [knowledge-base/ARCHITECTURE.md](./knowledge-base/ARCHITECTURE.md) + [knowledge-base/SOURCES.md](./knowledge-base/SOURCES.md) |

---

## Conventions Used

- All file paths are **relative to repository root** unless noted.
- Mermaid diagrams render in GitHub Markdown + most IDE Markdown viewers.
- Section anchors (`#section-name`) are GitHub-compatible.
- Every doc answers **"what is this?"** and **"what do I do next?"**.

---

## See Also

- **`CLAUDE.md`** — Claude Code orientation (commands, conventions, gotchas)
- **`README.md`** — User-facing setup & API reference
- **[audit/DOCS_AUDIT.md](./audit/DOCS_AUDIT.md)** — The audit that drove this consolidation
