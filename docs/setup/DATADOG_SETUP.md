# Datadog Setup (CrackCMS)

> Environment-based configuration for Datadog RUM (frontend) and APM tracing (backend).

---

## Frontend (Next.js RUM + Browser Logs)

Datadog browser instrumentation initializes from `frontend/src/components/DatadogInit.tsx`.

Set these environment variables in your Vercel deployment:

| Variable | Required | Default |
|---|---|---|
| `NEXT_PUBLIC_DD_CLIENT_TOKEN` (or `NEXT_PUBLIC_DATADOG_CLIENT_TOKEN`) | Yes | — |
| `NEXT_PUBLIC_DD_APPLICATION_ID` (or `NEXT_PUBLIC_DATADOG_APPLICATION_ID`) | Yes | — |
| `NEXT_PUBLIC_DD_SITE` | No | `datadoghq.com` |
| `NEXT_PUBLIC_DD_ENV` | Yes | e.g. `production` |
| `NEXT_PUBLIC_DD_SERVICE` | No | `crackcms-frontend` |
| `NEXT_PUBLIC_DD_VERSION` | Optional | release id |
| `NEXT_PUBLIC_DD_SESSION_SAMPLE_RATE` | No | `100` |
| `NEXT_PUBLIC_DD_SESSION_REPLAY_SAMPLE_RATE` | No | `20` |
| `NEXT_PUBLIC_DD_LOGS_SAMPLE_RATE` | No | `100` |

---

## Backend (Django tracing + log correlation)

Datadog tracing hooks are available in:

- `backend/crack_cms/wsgi.py`
- `backend/crack_cms/asgi.py`

Enable backend tracing only after Datadog agent intake is reachable.

| Variable | Required | Default |
|---|---|---|
| `DD_TRACE_ENABLED` | No | `false` in `render.yaml` |
| `DD_LOGS_INJECTION` | Recommended | `true` |
| `DD_SERVICE` | No | `crackcms-backend` |
| `DD_ENV` | Yes | e.g. `production` |
| `DD_VERSION` | Yes | release/commit hash |
| `DD_AGENT_HOST` | Conditional | if host requires explicit agent host |
| `DD_SITE` | No | `datadoghq.com` |

---

## Important

- ⚠️ **Do not hardcode Datadog keys in source.**
- ⚠️ **If any key was shared publicly, rotate it in Datadog immediately.**
- ✅ For production releases, set `DD_VERSION` (backend) and `NEXT_PUBLIC_DD_VERSION` (frontend) to the **same commit hash/tag** for easier correlation.

---

## See Also

- [`../SECURITY_AUDIT.md`](../SECURITY_AUDIT.md) — observability debt
- [`../PERFORMANCE.md`](../PERFORMANCE.md) — APM metrics
- [`../SCALING_ROADMAP.md`](../SCALING_ROADMAP.md) — when APM pays off
