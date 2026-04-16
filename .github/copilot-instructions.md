# Copilot Instructions

This repository is a full-stack Crack CMS platform with:

- `frontend/`: Next.js app router frontend
- `backend/`: Django + DRF backend
- Supabase auth and database integration
- Vercel frontend deployment and DigitalOcean backend deployment

## Working Rules

- Prefer minimal, targeted changes.
- Do not revert user changes unless explicitly asked.
- Keep auth behavior consistent with the current Supabase-first flow.
- Preserve build stability for Next.js static generation.
- Use existing patterns before introducing new abstractions.
- Use `apply_patch` for edits.

## Preferred Tooling

### MCP Servers

Use the workspace MCP servers declared in `.vscode/mcp.json` when available:

- `filesystem` for workspace file access
- `github` for repository, issue, and PR context
- `playwright` for browser testing and UI checks
- `fetch` for reading external web content
- `icons8mcp` for icon lookup
- `supabase` for Supabase project context

### Repo Context Files

Treat the following as primary project context:

- `README.md`
- `ARCHITECTURE.md`
- `DOCUMENTATION.md`
- `plan-crackCmsPlatformFixAndEnhancement.prompt.md`
- `.github/skills/*`
- `.github/agents/*`

## Commands To Prefer

- Frontend build: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Backend tests or checks: use the existing backend scripts and test files

## Output Expectations

- Be concise and factual.
- Mention exact files changed.
- Verify changes with the relevant build or test command when practical.
