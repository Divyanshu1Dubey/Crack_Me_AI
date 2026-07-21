# Secret Handling & Incident Response

> Policy and procedures for managing secrets across the CrackCMS repository.

---

## Current Status

- Exposed key lines were scrubbed from `API_KEYS.md` (now superseded by [`../setup/AI_PROVIDERS.md`](../setup/AI_PROVIDERS.md)).
- Secrets are documented as environment variables only — never pasted in docs, code, or commits.
- Commit-time secret scanning is configured via pre-commit hook.

---

## Required Rotation Actions

Rotate and revoke these credentials immediately in provider dashboards if they have ever appeared in repo history:

1. **OpenRouter** key exposed in `API_KEYS.md`
2. **ElevenLabs** key exposed in `API_KEYS.md`
3. **Gmail App Password** (if ever pasted in `PASSWORD_RESET_SETUP.md` — now superseded)

After rotation, update only environment variables — never docs or source files:

```env
OPENROUTER_API_KEY=
OPENROUTER_API_KEY2=
ELEVENLABS_API_KEY=
EMAIL_HOST_PASSWORD=
```

---

## History Scan Command

Run from repository root to detect any leaked secrets in git history:

```bash
git rev-list --all | xargs -I {} git grep -nIE \
  "sk-or-v1-[A-Za-z0-9]{20,}|sk_[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|csk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}|nvapi-[A-Za-z0-9]{20,}" \
  {} 2>/dev/null | sort -u
```

If any matches appear, follow the **Purge Historical Secrets** procedure below.

Latest scan result (as of consolidation):

- Historical leak found in commit `3770b2fa37494dfccfa1be56da8318f1ae597639` at `API_KEYS.md` lines 101–102.
- Current working tree no longer contains those leaked lines.

---

## Purge Historical Secrets (if scan finds any)

Use `git-filter-repo` on a clean working tree or fresh clone:

```bash
# 1) Create replacements.txt with one line per secret
#    format: OLD_VALUE==>REDACTED_VALUE

# 2) Rewrite history
git filter-repo --replace-text replacements.txt --force

# 3) Force-push rewritten history
git push --force-with-lease --all
git push --force-with-lease --tags
```

Then notify all contributors to re-clone or hard-reset to the rewritten history.

---

## Pre-commit Secret Scanner

Install and enable pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Configured in:
- `.pre-commit-config.yaml`
- `scripts/scan_secrets.py`

The hook blocks commits when likely API keys are detected.

---

## Secret Storage Policy

| Secret type | Where to store |
|---|---|
| **AI provider keys** | `backend/.env` (local) + Render/DO environment variables (prod) |
| **Django SECRET_KEY** | Same as above |
| **Razorpay keys** | Render env vars only |
| **Gmail App Password** | Render env vars only (rotate every 90 days) |
| **Supabase service role key** | Render env vars only — never expose to frontend |
| **Datadog client token** | Vercel env vars (frontend — safe to expose) |
| **Sentry DSN** | Vercel (frontend) + Render (backend) env vars |

### Never store secrets in

- ❌ `backend/.env.example` (use placeholder values like `gsk_...`)
- ❌ Source code or fixtures
- ❌ Documentation (`docs/`, `README.md`)
- ❌ Test files or test fixtures
- ❌ Commit messages or PR descriptions
- ❌ Screenshots or screen recordings

---

## Incident Response

### If a secret is leaked

1. **Revoke immediately** in the provider dashboard
2. **Generate replacement** key
3. **Update env vars** in all environments (local, staging, prod)
4. **Audit usage** in provider dashboard for unauthorized access
5. **Document** the incident in `docs/reports/INCIDENT_<date>.md`
6. **Purge from git history** if committed (see above)

### If credentials leak in public docs

1. **Edit the doc** to remove the secret
2. **Force-rotate** the affected credential
3. **Commit the doc fix** with message `security: scrub leaked <provider> key`
4. **Run history scan** to verify removal

---

## See Also

- [`../setup/AI_PROVIDERS.md`](../setup/AI_PROVIDERS.md) — provider setup
- [`../setup/EMAIL_SETUP.md`](../setup/EMAIL_SETUP.md) — Gmail App Password policy
- [`../SECURITY_AUDIT.md`](../SECURITY_AUDIT.md) — full security audit
