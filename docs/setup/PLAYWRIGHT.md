# Playwright End-to-End Testing

Playwright is the project's browser-automation framework. It drives a real
Chromium against the live production site (or a local dev server) to catch
visual regressions and confirm that auth-gated pages render correctly.

## Status (2026-07-26)

- **Installed**: `@playwright/test@1.58.2` (already in `frontend/package.json`).
- **Browsers downloaded**: chromium-1208 (path: `%LOCALAPPDATA%\ms-playwright\chromium-1208`).
- **Config**: `frontend/playwright.config.ts` — base URL is `http://localhost:3000`
  by default; pass `BASE_URL` to override.
- **Test directory**: `frontend/tests/e2e/`.

## Existing test suites

| File | Purpose |
|---|---|
| `auth.spec.ts` | Public login + register + forgot-password + unauth redirect. |
| `protected-routes.spec.ts` | Auth-gated redirect behaviour. |
| `questions.spec.ts` | Public question-list page. |
| `neet-pg-qa.spec.ts` | **Detailed NEET PG regression suite** — 7 phases covering the 10 production bugs fixed on 2026-07-25 (sidebar, filters, AI tutor, image viewer, etc.). |
| `neet-pg-screenshots.spec.ts` | **Visual screenshots** of the NEET PG player at 4 viewports/themes (desktop + mobile, light + dark) plus an answer-reveal capture. |
| `admin-control-tower.spec.ts` | Admin-side smoke. |

## Running

### Against production (no local server needed)

```bash
cd frontend
PLAYWRIGHT_SKIP_WEBSERVER=1 \
BASE_URL=https://www.cracklabs.app \
./node_modules/.bin/playwright test
```

### Against local dev server

```bash
cd frontend
npm run dev -- --webpack   # in another terminal
./node_modules/.bin/playwright test
```

The Playwright config auto-starts `npm run dev` if `PLAYWRIGHT_SKIP_WEBSERVER` is not set.

### One file at a time

```bash
./node_modules/.bin/playwright test tests/e2e/neet-pg-qa.spec.ts
./node_modules/.bin/playwright test tests/e2e/neet-pg-screenshots.spec.ts
```

### Screenshots only

The `neet-pg-screenshots.spec.ts` suite writes PNGs to
`frontend/screenshots/neet-pg/`. It also produces failure captures in
`frontend/test-results/`.

## Required environment variables

The screenshot suite and any auth-gated test read credentials from env vars.
**Never hardcode credentials** — they're loaded at runtime.

| Var | Purpose |
|---|---|
| `BASE_URL` | Frontend URL. Defaults to `http://localhost:3000`. |
| `API_BASE_URL` | Backend API URL. Defaults to the production URL baked into `neet-pg-qa.spec.ts`. |
| `PLAYWRIGHT_SKIP_WEBSERVER` | Set to `1` to skip auto-starting `npm run dev` (use when targeting prod). |
| `QA_TEST_USER_EMAIL` | Login email for auth-gated tests. Tests `test.skip()` if missing. |
| `QA_TEST_USER_PASSWORD` | Login password for auth-gated tests. |

Tip: export them in a `.env.playwright` file (gitignored) and `source` it before running:

```bash
# frontend/.env.playwright  (DO NOT COMMIT)
export BASE_URL=https://www.cracklabs.app
export PLAYWRIGHT_SKIP_WEBSERVER=1
export QA_TEST_USER_EMAIL=<redacted>
export QA_TEST_USER_PASSWORD=<redacted>
```

```bash
source .env.playwright && ./node_modules/.bin/playwright test
```

## Installing browsers on a new machine

```bash
cd frontend
./node_modules/.bin/playwright install chromium        # chromium only
./node_modules/.bin/playwright install chromium --with-deps  # also install OS libs (Linux)
```

To target other browsers, add them to `playwright.config.ts` `projects:`.

## Last green run

2026-07-26 — `auth.spec.ts` (7/8 pass; 1 known failure on the live site: the password-strength label regex is now stale). The auth suite, the protected-routes suite, and the questions suite all run against the live production site without any local backend.

## Verifying the NEET PG player fix

The bug fixed in `frontend/src/components/neet-pg/NeetPgPlayer.tsx` and
`frontend/src/lib/textCleanup.ts` (NEET PG recall questions render with no
options) is not yet covered by an automated test. To verify by hand:

1. Set `QA_TEST_USER_EMAIL` + `QA_TEST_USER_PASSWORD`.
2. Run: `BASE_URL=https://www.cracklabs.app PLAYWRIGHT_SKIP_WEBSERVER=1 ./node_modules/.bin/playwright test tests/e2e/neet-pg-screenshots.spec.ts`.
3. Open `frontend/screenshots/neet-pg/desktop-light.png` and confirm the question shows 4 A/B/C/D option buttons.
4. Run the `answer-reveal` capture and confirm the "Why correct" panel renders (instead of an empty area).

To automate the regression, add a test to `neet-pg-screenshots.spec.ts` that asserts
`await expect(page.locator('[data-testid="option-A"]')).toBeVisible()` on the PQLI question (id 2204) once a known-bad question ID is locatable via the player URL.