# Secret Handling and Incident Response

## Current Status

- Exposed key lines were removed from API_KEYS.md.
- Secrets are documented as environment variables only.
- Commit-time secret scanning is now configured via pre-commit.

## Required Rotation Actions

Rotate and revoke these credentials immediately in provider dashboards:

1. OpenRouter key that was exposed in API_KEYS.md
2. ElevenLabs key that was exposed in API_KEYS.md

After rotation, update only environment variables (never docs or source files):

- OPENROUTER_API_KEY
- OPENROUTER_API_KEY2 (if used)
- ELEVENLABS_API_KEY (if used)

## History Scan Command

Run from repository root:

```powershell
git rev-list --all | ForEach-Object { git grep -nEI "sk-or-v1-[A-Za-z0-9]{20,}|sk_[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|csk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}" $_ } | Sort-Object -Unique
```

Latest scan result:

- Historical leak found in commit 3770b2fa37494dfccfa1be56da8318f1ae597639 at API_KEYS.md lines 101-102.
- Current working tree no longer contains those leaked lines.

## Purge Historical Secrets (if scan finds any)

Use git-filter-repo on a clean working tree or fresh clone:

```powershell
# 1) Create replacements.txt with one line per secret
#    format: OLD_VALUE==>REDACTED_VALUE
# 2) Rewrite history
git filter-repo --replace-text replacements.txt --force

# 3) Force-push rewritten history
git push --force-with-lease --all
git push --force-with-lease --tags
```

Then notify all contributors to re-clone or hard-reset to the rewritten history.

## Pre-commit Secret Scanner

Install and enable pre-commit hooks:

```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Configured hook file:

- .pre-commit-config.yaml
- scripts/scan_secrets.py

The hook blocks commits when likely API keys are detected.
