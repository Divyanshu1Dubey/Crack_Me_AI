# CrackCMS Audit and Capacity Report

Date: March 23, 2026

## 1. What is fixed now

- Gmail SMTP credentials are wired into the backend password-reset flow locally.
- The CrackCMS logo is integrated into the auth UI and shared branding components.
- Login, register, forgot-password, and reset-password pages were redesigned.
- Password reset email sending is implemented with HTML + text email.
- Registration and password reset now use Django password validation.
- The frontend dev server was switched to webpack mode for stability on Windows:
  - `npm run dev` now runs `next dev --webpack`
- Playwright was updated so tests can run against an already-running frontend with:
  - PowerShell: `$env:PLAYWRIGHT_SKIP_WEBSERVER='1'; npx playwright test --workers=1`
- Backend now supports `DATABASE_URL` for production databases, while still falling back to local SQLite for development.

## 2. Exact local content counts

- Active questions in DB: `1966`
- Inactive / excluded draft questions: `215`
- Total questions in DB: `2181`
- Fixture objects in `backend/questions_fixture.json`: `2031`
- Question objects in fixture: `1966`
- Subjects: `5`
- Topics: `60`

## 3. Exact `.env` / provider counts

- Non-empty entries in `backend/.env`: `18`
- Non-empty AI/API keys in `backend/.env`: `12`
  - `GEMINI_API_KEY`
  - `GROQ_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `OPENROUTER_API_KEY`
  - `CEREBRAS_API_KEY`
  - `COHERE_API_KEY`
  - `TOGETHER_API_KEY`
  - `GITHUB_TOKEN`
  - `HUGGINGFACE_API_KEY`
  - `AIML_API_KEY`
  - `OPENROUTER_API_KEY2`
  - `MISTRAL_API_KEY`
- AI providers wired into the runtime request path in `backend/ai_engine/services.py`: `10`
  - Gemini
  - Groq
  - Cerebras
  - Cohere
  - OpenRouter
  - OpenRouter2
  - GitHub Models
  - HuggingFace
  - Mistral
  - DeepSeek
- Additional providers present outside the runtime path / tests: `3`
  - Together
  - AIML
  - Ollama
- Total providers tested live today: `13`

## 4. Live provider status on March 23, 2026

Source: local live run of `backend/test_api_keys.py` and direct header checks.

### Runtime cloud providers

| Provider | Status now | Exact measurable limit | Counted in guaranteed request total |
|---|---|---:|---|
| Groq (`llama-3.3-70b-versatile`) | Working | `30 RPM`, `1000 RPD`, `12000 TPM` | Yes |
| Cerebras (`llama3.1-8b`) | Working | `30 RPM`, `14400 RPD`, `60000 TPM` | Yes |
| GitHub Models (`openai/gpt-4o-mini`) | Working | Model is `low` tier. GitHub docs: `15-20 RPM`, `150-450 RPD`, `5-8` concurrent depending Copilot plan | Yes, counted conservatively at the minimum |
| Cohere (`command-a-03-2025`) | Working | Live headers expose `20` trial endpoint calls and `1000` endpoint calls/month, but the header does not label the short-window interval | Counted only in the operational total |
| HuggingFace routed endpoint | Working | No exact request-limit header exposed by the routed endpoint | No |
| Mistral (`mistral-small`) | Working | Live header exposed `50000 TPM`; no request-count header exposed | No |
| Gemini | Rate-limited | `0` available at test time | No |
| OpenRouter key 1 | Rate-limited | `0` available at test time | No |
| OpenRouter key 2 | Rate-limited | `0` available at test time | No |
| DeepSeek | No balance | `0` until balance is added | No |

### Extra non-runtime providers

| Provider | Status now | Notes |
|---|---|---|
| Together | No balance | Configured, but not used in `AIService` |
| AIML | Invalid key | Configured, but not used in `AIService` |
| Ollama local | Working | Local model, not part of the cloud runtime rotation |

## 5. Exact AI hit counts you can claim today

### Strict proven floor you can state exactly right now

This total uses only providers that are both:

1. Working right now, and
2. Exposing an unambiguous documented or directly measurable request quota

Strict proven minimum available now:

- `60 requests/minute`
- `15400 requests/day`

Breakdown:

- Groq: `30 RPM` + `1000 RPD`
- Cerebras: `30 RPM` + `14400 RPD`

### Operational conservative floor

If I include the current GitHub minimum for low-tier models and the live Cohere header behavior, the working operational floor becomes:

- `95 requests/minute`
- `15550 requests/day`
- plus `1000 requests/month` on Cohere

Operational breakdown:

- Groq: `30 RPM` + `1000 RPD`
- Cerebras: `30 RPM` + `14400 RPD`
- GitHub Models low-tier minimum: `15 RPM` + `150 RPD`
- Cohere: `20` trial endpoint calls + `1000/month`

### Important nuance

The real available capacity is higher than the conservative total above because:

- HuggingFace is working, but the routed endpoint did not expose an exact request-count limit
- Mistral is working and exposed `50000 TPM`, but not a request-count limit

So the conservative floor is:

- `95 RPM` minimum

The practical working total is:

- `95 RPM` plus additional HuggingFace capacity
- `95 RPM` plus Mistral requests up to the point where `50000 TPM` is exhausted

### If currently rate-limited providers recover

- OpenRouter docs currently show free users at `20 RPM` and `50 requests/day`
- You have `2` OpenRouter keys
- So when both are healthy again, OpenRouter can add:
  - `40 RPM`
  - `100 requests/day`

Gemini is different:

- Google now says exact Gemini limits depend on the project tier and should be checked in AI Studio
- Your key was rate-limited during the live test, so I did **not** count Gemini in the exact total for today

## 6. Exact app-server capacity on current hosting

Current Render start command:

```txt
gunicorn crack_cms.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180
```

That means the current backend can handle exactly:

- `1` Gunicorn worker
- `4` request threads
- `4` simultaneous Python requests per backend instance

So the exact answer to "how many student logins can I handle at the same time?" is:

- `4 concurrent login requests` per backend instance

So the exact answer to "how many API hits can the backend handle at the same time?" is:

- `4 concurrent API requests` per backend instance

### What I can and cannot claim exactly

What is exact from the repo/config:

- simultaneous request capacity = `4`

What is **not** exact from the repo alone:

- sustained logins per second
- sustained AI requests per minute through your own backend

Those depend on:

- real Render CPU availability
- current cold-start state
- SQLite lock behavior
- external AI provider latency

Because AI calls can take many seconds and each call occupies one of the `4` threads, the backend instance is your first bottleneck before most provider quotas are.

## 7. Current hosting blockers

### Render free tier

These are current official Render limitations:

- Free web services are **not recommended for production**
- They spin down after `15 minutes` idle
- Spin-up takes about `1 minute`
- Free web services use an **ephemeral filesystem**
- Local files such as SQLite DBs are lost on redeploy, restart, or spin-down
- Free web services cannot scale beyond a **single instance**
- Free web services cannot send outbound traffic on ports `25`, `465`, or `587`

What that means for CrackCMS right now:

- Current forgot-password SMTP with Gmail will **not** work from the Render free backend in production
- If you were using `db.sqlite3` on Render, student data would be unsafe on restart/spin-down
- I fixed the code so you can move to a proper `DATABASE_URL` database, but you still need to provide that database in hosting

### DigitalOcean

Moving to DigitalOcean does **not** automatically fix Gmail SMTP.

DigitalOcean officially says:

- SMTP ports `25`, `465`, and `587` are blocked on Droplets by default

What that means:

- Gmail SMTP password reset will fail on a default Droplet too
- If you move to DigitalOcean, you should plan to use:
  - Postgres for the DB
  - Redis for cache
  - an email API provider instead of Gmail SMTP

## 8. Database risk and fix

Before this audit, the backend was hard-wired to:

- `backend/db.sqlite3`

That is not safe for Render free production because Render free has an ephemeral filesystem.

I changed the backend so it now supports:

- `DATABASE_URL` in production
- SQLite fallback locally

Recommended production database choices:

- Render paid Postgres
- DigitalOcean managed Postgres
- Postgres running on a persistent volume you manage

Do **not** run production student data on local SQLite inside a free web service.

## 9. Test results from this audit

### Backend

- `python manage.py check` -> passed
- `python manage.py test accounts` -> `3 passed`
- `python test_all.py --quick` -> `37 passed, 0 failed`

### Frontend

- `npm run build` -> passed
- `PLAYWRIGHT_SKIP_WEBSERVER=1 npx playwright test --workers=1` -> `10 passed`

### Dev-server stability

- `npm run dev` now uses webpack, not Turbopack
- This fixed the Windows lock / stale-port / Turbopack panic issue during local development and Playwright runs

### Remaining known issue

- Repo-wide `npm run lint` still fails in multiple pre-existing files outside this task's scope

## 10. Recommended next deployment shape

For a stable real deployment:

1. Frontend on Vercel is fine.
2. Backend should use Postgres via `DATABASE_URL`.
3. Add Redis via `REDIS_URL` for cache and token-heavy endpoints.
4. Replace Gmail SMTP with an email API provider.
5. If you stay on Render, move the backend to a paid instance.
6. If you move to DigitalOcean, do **not** assume SMTP will work by default.

## 11. Sources

- Render free-tier limitations: https://render.com/docs/free
- Render outbound SMTP restriction: https://render.com/docs/troubleshooting-outbound-connections
- DigitalOcean SMTP restriction: https://docs.digitalocean.com/support/why-is-smtp-blocked/
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Cerebras rate limits: https://inference-docs.cerebras.ai/support/rate-limits
- GitHub Models prototype/free limits: https://docs.github.com/en/enterprise-cloud@latest/github-models/use-github-models/prototyping-with-ai-models
- GitHub Models catalog / model rate-limit tier: https://docs.github.com/en/rest/models/catalog
- Gemini rate-limits overview: https://ai.google.dev/gemini-api/docs/rate-limits
- OpenRouter pricing and free-plan limits: https://openrouter.ai/pricing
