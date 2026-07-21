# Deployment Capacity Reference

> Capacity audit and hosting limits — based on `DEPLOYMENT_CAPACITY_REPORT.md` (consolidated).

**Audit date**: March 23, 2026

---

## What's fixed now

- Gmail SMTP credentials wired into backend password-reset flow locally
- CrackCMS logo integrated into auth UI + shared branding components
- Login / register / forgot-password / reset-password pages redesigned
- Password-reset email sending implemented with HTML + text
- Registration + password reset use Django password validation
- Frontend dev server switched to webpack (`next dev --webpack`) for Windows stability
- Playwright can run against an already-running frontend
- Backend supports `DATABASE_URL` for production databases while still falling back to local SQLite

---

## Local content counts

- Active questions in DB: **1,966**
- Inactive / excluded draft: **215**
- Total questions in DB: **2,181**
- Fixture objects in `backend/questions_fixture.json`: **2,031**
- Subjects: **5**
- Topics: **60**

---

## Provider counts

- Non-empty entries in `backend/.env`: **18**
- Non-empty AI/API keys in `.env`: **12**
- AI providers in runtime rotation (`services.py`): **11** (incl. NVIDIA Mistral)
- Additional non-runtime providers: **2** (Together, AIML)
- Total cloud + local: **13**

---

## Live provider status (snapshot, March 23, 2026)

| Provider | Status | Limit (measured) |
|---|---|---|
| Groq (`llama-3.3-70b-versatile`) | Working | 30 RPM, 1000 RPD, 12000 TPM |
| Cerebras (`llama3.1-8b`) | Working | 30 RPM, 14400 RPD, 60000 TPM |
| GitHub Models (`openai/gpt-4o-mini`) | Working | 15–20 RPM, 150–450 RPD (low tier) |
| Cohere (`command-a-03-2025`) | Working | 20 trial endpoint calls + 1000/month |
| HuggingFace | Working | No exact request-limit header |
| Mistral | Working | 50000 TPM |
| Gemini | Rate-limited | 0 at test time |
| OpenRouter 1 | Rate-limited | 0 at test time |
| OpenRouter 2 | Rate-limited | 0 at test time |
| DeepSeek | No balance | 0 until balance added |
| Ollama local | Working | Unlimited |
| Together | No balance | Configured but not in rotation |
| AIML | Invalid key | Configured but not in rotation |

---

## Proven AI capacity floor

### Strict proven floor (only working providers with documented quotas)

- **60 requests/minute**
- **15,400 requests/day**
  - Groq: 30 RPM + 1000 RPD
  - Cerebras: 30 RPM + 14400 RPD

### Operational conservative floor (incl. GitHub + Cohere)

- **95 requests/minute**
- **15,550 requests/day**
- Plus **1000 requests/month** on Cohere

### With OpenRouter recovered

- +40 RPM, +100 RPD (both OpenRouter keys)

---

## App-server capacity (current Render free tier)

```txt
gunicorn crack_cms.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180
```

- **1 Gunicorn worker**
- **4 request threads**
- **4 concurrent Python requests per backend instance**
- **4 simultaneous login requests** per instance
- **4 simultaneous API requests** per instance

Long AI calls (up to 120 s) occupy threads → backend is the **first bottleneck** before most provider quotas.

---

## Hosting blockers

### Render free tier

- Free web services not recommended for production
- Spin down after 15 minutes idle; spin-up takes ~1 minute
- **Ephemeral filesystem** — local files (e.g. SQLite) lost on restart/spin-down
- Cannot scale beyond a single instance
- Cannot send outbound traffic on ports **25 / 465 / 587** (Gmail SMTP blocked)

**Implication**: Gmail SMTP password-reset will not work from Render free in production. SQLite data at risk on restart.

### DigitalOcean

- SMTP ports **25 / 465 / 587** blocked by default on Droplets

**Implication**: Gmail SMTP will fail on a default Droplet. Plan for Postgres + Redis + email API provider.

---

## Database risk

Before the audit, backend was hard-wired to `backend/db.sqlite3` — not safe for Render free due to ephemeral filesystem.

**Fix applied**: backend now supports `DATABASE_URL` for production + SQLite fallback locally.

**Recommended production databases**:
- Render paid Postgres
- DigitalOcean managed Postgres
- Postgres on a persistent volume you manage

---

## Test results

### Backend

- `python manage.py check` → passed
- `python manage.py test accounts` → 3 passed
- `python test_all.py --quick` → **37 passed, 0 failed**

### Frontend

- `npm run build` → passed
- `PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test --workers=1` → **10 passed**

### Dev-server stability

- `npm run dev` uses webpack (not Turbopack) — fixed Windows lock / stale-port / Turbopack panic issues during local development and Playwright runs

### Remaining issue

- Repo-wide `npm run lint` still fails in multiple pre-existing files

---

## Recommended next deployment shape

For a stable real deployment:

1. Frontend on Vercel (already done)
2. Backend on Render paid OR DigitalOcean with `DATABASE_URL` Postgres
3. Add Redis via `REDIS_URL` for cache + token-heavy endpoints
4. Replace Gmail SMTP with email API (SendGrid / Mailgun / Postmark)
5. Add 2 gunicorn workers minimum (`--workers 2 --threads 4`) for higher concurrency

---

## Sources

- Render free-tier: https://render.com/docs/free
- Render outbound SMTP: https://render.com/docs/troubleshooting-outbound-connections
- DigitalOcean SMTP: https://docs.digitalocean.com/support/why-is-smtp-blocked/
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Cerebras rate limits: https://inference-docs.cerebras.ai/support/rate-limits
- GitHub Models: https://docs.github.com/en/github-models
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- OpenRouter pricing: https://openrouter.ai/pricing

---

## See Also

- [`../setup/AI_PROVIDERS.md`](../setup/AI_PROVIDERS.md) — provider setup
- [`../SCALING_ROADMAP.md`](../SCALING_ROADMAP.md) — scaling plan
- [`../PERFORMANCE.md`](../PERFORMANCE.md) — performance bottlenecks
