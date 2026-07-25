# NEET PG QA Pass — Progress Ledger

**Branch:** main
**Plan:** docs/superpowers/plans/2026-07-25-neetpg-qa-pass.md (superseded)
**Spec:** docs/superpowers/specs/2026-07-25-neetpg-qa-pass-design.md (superseded)
**Started:** 2026-07-25
**Rescoped:** 2026-07-25 — User clarified: production app is single-domain (cracklabs.app). NEET PG is a section of main frontend, not a separate app. `frontend-neetpg/` was unused dead code and has been removed.

## Current State

- `frontend-neetpg/` deleted (commit `1a1b069`)
- Pre-P0 fix to landing CTAs committed as historical record (commit `f72b0b2`)
- Main frontend (`:3000`) confirmed healthy with `/exams/neet-pg`, `/inicet`, `/practice?exam=neet_pg` all returning 200
- Backend (`:8000`) healthy with 4490 questions

## Tasks (re-scoped to main app NEET PG + INICET flow)

- [ ] **T1**: Run Playwright on main app — landing (`/`), `/exams/neet-pg`, `/inicet`, `/practice?exam=neet_pg`, `/simulator?exam=neet_pg`, `/questions/neet-pg/practice`, `/login`, `/register`
- [ ] **T2**: Sample 20-30 random NEET PG questions for content correctness
- [ ] **T3**: Sample 20-30 random INICET questions for content correctness
- [ ] **T4**: Verify exam toggle UI (top bar / dropdown)
- [ ] **T5**: Fix loop — one bug at a time
- [ ] **T6**: Final report

## Commits so far in this session

- `9fab8d5` docs(qa): NEET PG QA pass design spec
- `0d53861` docs(qa): NEET PG QA pass implementation plan
- `f72b0b2` fix(neetpg-landing): CTA links to cracklabs.app + favicon (historical record; dir deleted)
- `1a1b069` chore: remove unused frontend-neetpg project