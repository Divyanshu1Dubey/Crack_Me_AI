# Visual Snapshots — Playwright regression suite

Free, plugin-free visual regression for `cracklabs.app` using Playwright's
built-in `expect(page).toHaveScreenshot()`. Baselines live under
`./visual-snapshots/` and are committed to the repo.

## Generating baselines locally

```bash
cd frontend
# Public pages — no auth needed
LIVE_AUDIT_EMAIL=... LIVE_AUDIT_PASSWORD=... \
  npx playwright test visual-snapshots.spec.ts \
    --project=chromium --grep "public pages" --update-snapshots

# Auth-gated pages — requires a real student account
QA_TEST_USER_EMAIL=... QA_TEST_USER_PASSWORD=... \
  npx playwright test visual-snapshots.spec.ts \
    --project=chromium --grep "private pages" --update-snapshots

# Mobile viewports (Pixel 5 layout)
npx playwright test visual-snapshots.spec.ts \
    --project=chromium-mobile --update-snapshots
```

Baselines are written to:

```
tests/e2e/visual-snapshots/<chromium|chromium-mobile>/<public|private>/<light|dark>/<page>.png
```

The `-actual.png` and `-diff.png` artefacts generated on a regression are
gitignored — only the baseline PNGs are tracked.

## CI

`.github/workflows/ci.yml` defines a `visual-snapshots` job that runs the
suite against `cracklabs.app` on every push and PR. The job is **warning-only
on first run** — it uploads the HTML report as an artifact but does not
block merges. Once baselines are stable (commit a few "first-run" baselines
and let them cook for ~3 pushes), flip it to a hard gate by removing the
`|| true` and the `continue-on-error: true`.

## Required GitHub Actions secrets

Set in `Settings → Secrets and variables → Actions`:

| Secret | Purpose |
|---|---|
| `LIVE_AUDIT_EMAIL` | loginAs(student) for private-route baselines |
| `LIVE_AUDIT_PASSWORD` | same |
| `QA_TEST_USER_EMAIL` | (alias, kept for the original `fixtures/auth.ts` convention) |
| `QA_TEST_USER_PASSWORD` | same |

Without these, the private-route tests skip themselves (via `fixtures/auth.ts#skipIfAnonymous`)
so the job still runs, just with fewer baselines.

## Triage

- Diff < 250 pixels (the configured `maxDiffPixels`) → expected, baseline updates fine.
- Diff > 250 pixels → investigate before regenerating. Likely a real
  regression. Common false positives:
  - Brand new feature rendered for the first time (page genuinely changed)
  - Animation not fully settled → check the `stabilizeForSnapshot()` step
  - Per-user content not masked → expand the `mask: [...]` array in the spec