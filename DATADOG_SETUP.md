# Datadog Setup (CrackCMS)

This project now supports Datadog on both frontend and backend with environment-based configuration.

## Frontend (Next.js RUM + Browser Logs)

Datadog browser instrumentation initializes from [frontend/src/components/DatadogInit.tsx](frontend/src/components/DatadogInit.tsx).

Set these environment variables in your frontend deployment (Vercel/other):

- `NEXT_PUBLIC_DD_CLIENT_TOKEN` (or `NEXT_PUBLIC_DATADOG_CLIENT_TOKEN`)
- `NEXT_PUBLIC_DD_APPLICATION_ID` (or `NEXT_PUBLIC_DATADOG_APPLICATION_ID`)
- `NEXT_PUBLIC_DD_SITE` (default: `datadoghq.com`)
- `NEXT_PUBLIC_DD_ENV` (e.g. `production`)
- `NEXT_PUBLIC_DD_SERVICE` (default: `crackcms-frontend`)
- `NEXT_PUBLIC_DD_VERSION` (optional release id)
- `NEXT_PUBLIC_DD_SESSION_SAMPLE_RATE` (default: `100`)
- `NEXT_PUBLIC_DD_SESSION_REPLAY_SAMPLE_RATE` (default: `20`)
- `NEXT_PUBLIC_DD_LOGS_SAMPLE_RATE` (default: `100`)

## Backend (Django tracing + log correlation)

Datadog tracing hooks are available in:

- [backend/crack_cms/wsgi.py](backend/crack_cms/wsgi.py)
- [backend/crack_cms/asgi.py](backend/crack_cms/asgi.py)

Enable backend tracing only after Datadog agent intake is reachable.

Environment variables:

- `DD_TRACE_ENABLED` (`true`/`false`, default false in render.yaml)
- `DD_LOGS_INJECTION` (`true` recommended)
- `DD_SERVICE` (default `crackcms-backend`)
- `DD_ENV` (e.g. `production`)
- `DD_VERSION` (release/commit)
- `DD_AGENT_HOST` (if your host/platform requires explicit agent host)
- `DD_SITE` (default `datadoghq.com`)

## Important

- Do not hardcode Datadog keys in source.
- If any key was shared publicly, rotate it in Datadog immediately.
- For production releases, set `DD_VERSION` and frontend `NEXT_PUBLIC_DD_VERSION` to the same commit hash/tag for easier correlation.
