# NEET PG QA Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive `frontend-neetpg/` to production-ready quality via Playwright-driven QA crawl with one-at-a-time fix loop.

**Architecture:** Playwright MCP tools (`mcp__plugin_playwright_*`) drive a browser against `http://localhost:3000` and `http://localhost:8000/api`. Bugs are logged to `.playwright-mcp/qa-log.md`, triaged P0/P1/P2, and fixed one-at-a-time. Each fix is one commit. Each fix is re-verified by re-running Playwright on the affected surface only. Question content fixes flow through the fixture-first rule (JSON edit → `_export_fixture.py`).

**Tech Stack:** Playwright MCP, Next.js 16 (frontend-neetpg), React 19, Tailwind 4, Django 5 + DRF backend, Python 3.12.

## Global Constraints

- **Scope**: `frontend-neetpg/` only. Other frontends (`frontend/`, `frontend-fmge/`, `frontend-usmle/`, `mobile-app/`) are out of scope; bugs found there are logged but not fixed.
- **Backend code**: no changes. Only question-content JSON edits via fixture-first rule.
- **Commit convention**: `fix(neetpg): <surface> — <one-line summary>`. One bug per commit.
- **Sample size**: 20–30 random questions per category (PYQ, practice, flashcard).
- **Surfaces**: 9 total — `/`, `/auth/login`, `/auth/signup`, `/practice`, `/pyq`, `/simulator`, `/flashcards`, `/analytics`, `/bookmarks`, `/ai-tutor`.
- **Viewports**: 375×812 mobile, 768×1024 tablet, 1440×900 desktop.
- **Bug log path**: `.playwright-mcp/qa-log.md`.
- **Final report path**: `.playwright-mcp/qa-final-report.md`.
- **Definition of done**: zero P0/P1 bugs across all 9 surfaces, all 60–90 sampled questions pass content checks, final report written.
- **Pre-flight gate**: `npm run build` succeeds + `curl localhost:3000` returns 200 + `curl localhost:8000/api/questions/random/?count=1` returns valid JSON. If any fails → stop, report.

---

## Task 1: Pre-flight Environment Verification

**Files:**
- Read: `frontend-neetpg/package.json` (confirm `dev` script)
- Read: `backend/crack_cms/settings.py` (confirm DB config)
- Create: `.playwright-mcp/qa-log.md` (initial empty log file)

**Interfaces:**
- Consumes: nothing
- Produces: empty `qa-log.md` ready for entries

- [ ] **Step 1: Read frontend-neetpg/package.json to confirm dev script**

Read `frontend-neetpg/package.json` and locate the `scripts.dev` entry. Confirm it runs Next.js dev server on port 3000.

- [ ] **Step 2: Verify build succeeds**

Run: `cd frontend-neetpg && npm run build`
Expected: Build completes without TypeScript errors or missing imports. If it fails, STOP and report the build errors to the user — do not fix infra in this pass.

- [ ] **Step 3: Verify dev server is reachable**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/`
Expected: `200`. If not 200, instruct the user: "Start dev server with `cd frontend-neetpg && npm run dev` in a separate terminal."

- [ ] **Step 4: Verify backend API is reachable**

Run: `curl -s "http://localhost:8000/api/questions/random/?count=1" | head -c 500`
Expected: Valid JSON with at least one question object containing `id`, `stem`, `options`, `correctAnswer`. If not, instruct: "Start backend with `cd backend && python manage.py runserver` and ensure DB has data."

- [ ] **Step 5: Create empty bug log**

Run:
```bash
mkdir -p .playwright-mcp
cat > .playwright-mcp/qa-log.md << 'EOF'
# NEET PG QA Pass — Bug Log

**Started:** 2026-07-25
**Scope:** frontend-neetpg/
**Surfaces:** 9 (landing, auth/login, auth/signup, practice, pyq, simulator, flashcards, analytics, bookmarks, ai-tutor)

---

EOF
```
Expected: File created with header.

- [ ] **Step 6: Commit log scaffolding**

Run: `git add .playwright-mcp/qa-log.md && git commit -m "chore(qa): init NEET PG QA pass bug log"`
Expected: Commit created.

---

## Task 2: Landing Page Crawl (`/`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md` (add landing-page bug entries)
- Modify: any `frontend-neetpg/src/**` file flagged by Playwright (one commit per bug)

**Interfaces:**
- Consumes: pre-flight pass from Task 1
- Produces: landing-page bug entries in log + commits

- [ ] **Step 1: Navigate to landing page**

Tool: `mcp__plugin_playwright_playwright__browser_navigate`
URL: `http://localhost:3000/`

- [ ] **Step 2: Capture console errors**

Tool: `mcp__plugin_playwright_playwright__browser_console_messages`
Level: `error`
Expected: Empty list. Any errors → log as P0/P1 bug.

- [ ] **Step 3: Capture network requests**

Tool: `mcp__plugin_playwright_playwright__browser_network_requests`
Filter: `/api/`
Expected: All 2xx. Any 4xx/5xx → log as P0/P1 bug.

- [ ] **Step 4: Take DOM snapshot**

Tool: `mcp__plugin_playwright_playwright__browser_snapshot`
Expected: Full DOM with hero, features, CTAs, footer. Missing sections → log.

- [ ] **Step 5: Take desktop screenshot**

Tool: `mcp__plugin_playwright_playwright__browser_take_screenshot`
Viewport: 1440×900
Save to: `.playwright-mcp/qa-landing-desktop.png`

- [ ] **Step 6: Resize to mobile and re-screenshot**

```python
# Via browser_resize
browser_resize(width=375, height=812)
browser_take_screenshot(filename="qa-landing-mobile.png")
```
Save to: `.playwright-mcp/qa-landing-mobile.png`

- [ ] **Step 7: Resize to tablet and re-screenshot**

```python
browser_resize(width=768, height=1024)
browser_take_screenshot(filename="qa-landing-tablet.png")
```
Save to: `.playwright-mcp/qa-landing-tablet.png`

- [ ] **Step 8: Click each CTA button on landing page**

For each visible button/link in the snapshot:
- Tool: `mcp__plugin_playwright_playwright__browser_click`
- After click: re-check console + network for new errors
- If expected destination (e.g., `/practice`, `/auth/signup`) doesn't load → log as P1

- [ ] **Step 9: Log all bugs found in Task 2**

Append entries to `.playwright-mcp/qa-log.md` using the format from spec Section "Bug Log Format":
```
## [P0/P1/P2] [landing] YYYY-MM-DD HH:MM
- Repro: ...
- Expected: ...
- Actual: ...
- Console: ...
- Network: ...
- Fix: <commit hash or "pending">
- Verified: <timestamp + green check or "open">
```

- [ ] **Step 10: Stop here, report findings**

Tell the user: "Landing page crawl complete. Found N bugs (list). Proceeding to fix P0/P1 one at a time. Say 'stop' to pause, or just let me continue."

---

## Task 3: Auth Page Crawl (`/auth/login`, `/auth/signup`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any `frontend-neetpg/src/**` file flagged by Playwright

**Interfaces:**
- Consumes: bug log conventions from Task 2
- Produces: auth-page bug entries

- [ ] **Step 1: Navigate to login**

Tool: `mcp__plugin_playwright_playwright__browser_navigate`
URL: `http://localhost:3000/auth/login`

- [ ] **Step 2: Snapshot + console + network**

- `browser_snapshot`
- `browser_console_messages` (level=error)
- `browser_network_requests` (filter=/api/)

- [ ] **Step 3: Screenshot at 3 viewports**

375×812, 768×1024, 1440×900 — save to `.playwright-mcp/qa-login-{viewport}.png`

- [ ] **Step 4: Test form validation (empty submit)**

Click submit with empty fields → check that validation error appears. If app crashes or submits anyway → log P0.

- [ ] **Step 5: Test form validation (bad email)**

Fill email field with "notanemail" → submit → check error message. If no validation → log P1.

- [ ] **Step 6: Navigate to signup**

URL: `http://localhost:3000/auth/signup`

- [ ] **Step 7: Repeat steps 2-5 for signup page**

- [ ] **Step 8: Test password strength meter (if present)**

Fill password field with "weak" vs "StrongP@ss123!" → check if meter reflects strength. If meter doesn't update or is missing → log.

- [ ] **Step 9: Test forgot password link (if present)**

Click "Forgot password" → verify it navigates to `/auth/forgot-password` or shows a modal. If link is broken → log P1.

- [ ] **Step 10: Log all bugs found**

Append to `.playwright-mcp/qa-log.md` with `[auth]` tag.

---

## Task 4: Practice Page Crawl (`/practice`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any `frontend-neetpg/src/**` file flagged by Playwright

- [ ] **Step 1: Navigate to /practice**

URL: `http://localhost:3000/practice`

- [ ] **Step 2: Snapshot + console + network**

Standard checks.

- [ ] **Step 3: Screenshot at 3 viewports**

- [ ] **Step 4: Click "Start Practice" / "Begin" CTA**

Verify a question loads. If blank/loading-spinner-forever → log P0.

- [ ] **Step 5: Verify question has: stem, 4 distinct options, no duplicates**

Use `browser_evaluate` to inspect DOM:
```js
() => {
  const stem = document.querySelector('[data-testid="question-stem"]')?.innerText;
  const options = Array.from(document.querySelectorAll('[data-testid^="option-"]')).map(o => o.innerText);
  return { stem, options, distinctOptions: new Set(options).size };
}
```
Expected: stem non-empty, 4 options, distinctOptions = 4. Otherwise → log content bug.

- [ ] **Step 6: Click each option, verify state change**

For each of 4 options: click → verify it highlights/selects → check console for errors.

- [ ] **Step 7: Click "Submit Answer"**

Verify feedback shows (correct/incorrect + explanation). If no feedback → log P1.

- [ ] **Step 8: Click "Next Question"**

Verify next question loads. If same question reloads or blank → log P1.

- [ ] **Step 9: Test topic filter dropdown (if present)**

Select a different topic → verify questions change to that topic. If filter doesn't apply → log P1.

- [ ] **Step 10: Test "back to question list" navigation**

If there's a list view, click into a question, then click back → verify state preserved or correctly reset. If broken → log.

- [ ] **Step 11: Sample 20-30 random question IDs**

Tool: `browser_evaluate`
```js
async () => {
  const res = await fetch('/api/questions/?exam=NEETPG&limit=500', { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }});
  const data = await res.json();
  const ids = (data.results || data).map(q => q.id);
  const sampled = ids.sort(() => Math.random() - 0.5).slice(0, 25);
  return sampled;
}
```
Save the returned list of IDs to `.playwright-mcp/qa-sampled-practice-ids.json` (use `Write` tool).

- [ ] **Step 12: Visit each sampled question**

For each ID in the list:
- `browser_navigate` to `/practice/{id}`
- `browser_evaluate` to check stem, options, correctAnswer, explanation, image presence
- Screenshot to `.playwright-mcp/qa-practice-{id}.png`
- Log any content bug (missing image, blank option, mojibake, etc.)

- [ ] **Step 13: Log all bugs**

Append to `qa-log.md` with `[practice]` tag.

---

## Task 5: PYQ Page Crawl (`/pyq`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Navigate to /pyq**

URL: `http://localhost:3000/pyq`

- [ ] **Step 2: Standard checks (snapshot, console, network, 3-viewport screenshots)**

- [ ] **Step 3: Verify year filter works**

Select a year (e.g., 2021) → verify only 2021 questions appear. If filter broken → log P1.

- [ ] **Step 4: Verify subject/topic filter (if present)**

- [ ] **Step 5: Click into a question, verify it loads**

- [ ] **Step 6: Verify "Mark for review" / "Bookmark" button**

Click bookmark → verify icon fills + API call succeeds. If API errors → log.

- [ ] **Step 7: Sample 20-30 PYQ IDs and verify each**

Same pattern as Task 4 Step 11-12, filtered by `exam=NEETPG&is_pyq=true`.

- [ ] **Step 8: Log all bugs**

---

## Task 6: Simulator Page Crawl (`/simulator`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Navigate to /simulator**

URL: `http://localhost:3000/simulator`

- [ ] **Step 2: Standard checks**

- [ ] **Step 3: Verify timer counts down**

Wait 5 seconds → check timer decremented. If timer stuck → log P0.

- [ ] **Step 4: Start a mock test**

Click "Start Test" → verify question 1 loads + timer starts.

- [ ] **Step 5: Answer 5 questions in sequence**

Verify progression, timer keeps running, score accumulates.

- [ ] **Step 6: Test "Pause" / "Resume" (if present)**

- [ ] **Step 7: Test "Submit Test" before timer expires**

Verify result screen shows with score breakdown.

- [ ] **Step 8: Test auto-submit when timer hits 0**

Wait or fast-forward → verify auto-submit + result screen.

- [ ] **Step 9: Log all bugs**

---

## Task 7: Flashcards Page Crawl (`/flashcards`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Navigate to /flashcards**

URL: `http://localhost:3000/flashcards`

- [ ] **Step 2: Standard checks**

- [ ] **Step 3: Verify flashcard front/back flip on click**

Click card → verify back shows. Click again → verify front shows. If no flip → log P1.

- [ ] **Step 4: Test SM-2 rating buttons (Again / Hard / Good / Easy)**

Click each → verify next card loads + state persists.

- [ ] **Step 5: Sample 20-30 flashcard IDs and verify each**

- [ ] **Step 6: Log all bugs**

---

## Task 8: Analytics Page Crawl (`/analytics`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Navigate to /analytics**

URL: `http://localhost:3000/analytics`

- [ ] **Step 2: Standard checks**

- [ ] **Step 3: Verify charts render (not blank SVGs)**

Take screenshot → inspect. If chart area is empty → log P1.

- [ ] **Step 4: Click each tab/section (if multi-tab layout)**

Verify each loads data. If tab content blank → log.

- [ ] **Step 5: Check date range filter (if present)**

- [ ] **Step 6: Log all bugs**

---

## Task 9: Bookmarks Page Crawl (`/bookmarks`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Authenticate (login first)**

If unauthenticated, bookmarks will be empty/redirect. Login with a test account first.

- [ ] **Step 2: Navigate to /bookmarks**

URL: `http://localhost:3000/bookmarks`

- [ ] **Step 3: Standard checks**

- [ ] **Step 4: Bookmark a question from practice page**

Navigate to `/practice/{id}` → click bookmark → navigate to `/bookmarks` → verify it appears.

- [ ] **Step 5: Unbookmark from bookmarks page**

Click bookmark toggle → verify it disappears. If API errors → log.

- [ ] **Step 6: Log all bugs**

---

## Task 10: AI Tutor Page Crawl (`/ai-tutor`)

**Files:**
- Modify: `.playwright-mcp/qa-log.md`
- Modify: any flagged file

- [ ] **Step 1: Authenticate**

- [ ] **Step 2: Navigate to /ai-tutor**

URL: `http://localhost:3000/ai-tutor`

- [ ] **Step 3: Standard checks**

- [ ] **Step 4: Check token balance display**

Verify it shows current tokens. If shows "—" or stale number → log.

- [ ] **Step 5: Send a test message**

Type "What is the first-line treatment for migraine?" → submit → wait for response → verify AI responds.

**NOTE**: This may consume 1 token. If token wallet is empty, AI call will fail — log that as expected behavior, not a bug.

- [ ] **Step 6: Verify response renders (not raw JSON dump, not mojibake)**

This is a regression target — per recent commit `6dc1276 Fix UI/AI unreadable issues, raw JSON rendering, and garbled text`, verify those fixes still hold.

- [ ] **Step 7: Verify conversation history persists**

Refresh page → check previous messages still visible.

- [ ] **Step 8: Log all bugs**

---

## Task 11: Fix Loop (Iterative, runs after each Task 2-10)

**Files:**
- Modify: any `frontend-neetpg/src/**` file flagged
- Modify: `backend/questions_fixture.json` (for content fixes)
- Modify: `.playwright-mcp/qa-log.md`

**Interfaces:**
- Consumes: bug entries from Tasks 2-10
- Produces: commits per bug + log updates

- [ ] **Step 1: Pick next unfixed P0/P1 bug from log**

Read `.playwright-mcp/qa-log.md`, find first entry with `Fix: pending` and severity P0 or P1.

- [ ] **Step 2: Investigate root cause**

Use Grep/Read to locate the offending code in `frontend-neetpg/src/`. For content bugs, locate the question in `backend/questions_fixture.json`.

- [ ] **Step 3: Write the minimal fix**

Apply minimal targeted change. Per `CLAUDE.md`: "Prefer minimal, targeted changes; do not revert user changes." Do NOT refactor unrelated code.

- [ ] **Step 4: Verify build still passes**

Run: `cd frontend-neetpg && npm run build`
Expected: Success. If fails → revert and investigate.

- [ ] **Step 5: Re-run Playwright on the affected surface only**

Re-do the steps from the Task (e.g., Task 4 for practice-page bugs) that revealed the bug. Verify it's gone.

- [ ] **Step 6: Update bug log entry**

Replace `Fix: pending` with `Fix: <commit hash>` and `Verified: <timestamp>`.

- [ ] **Step 7: Commit**

For UI/UX fixes:
```bash
git add frontend-neetpg/src/<path>
git commit -m "fix(neetpg): <surface> — <one-line summary>"
```

For content fixes:
```bash
git add backend/questions_fixture.json
git commit -m "fix(neetpg-content): <question-id> — <one-line summary>"
```

- [ ] **Step 8: Loop back to Step 1**

Continue until all P0/P1 bugs are fixed.

---

## Task 12: Final Report

**Files:**
- Create: `.playwright-mcp/qa-final-report.md`

- [ ] **Step 1: Count bug entries by severity from log**

Read `qa-log.md` → tally P0, P1, P2 → compute totals.

- [ ] **Step 2: List all commits made**

Run: `git log --oneline <first-commit-of-pass>..HEAD`
Expected: List of `fix(neetpg): ...` commits.

- [ ] **Step 3: Capture final screenshots of all 9 surfaces**

Re-take landing, login, practice, pyq, simulator, flashcards, analytics, bookmarks, ai-tutor screenshots at 1440×900.

- [ ] **Step 4: Write final report**

Create `.playwright-mcp/qa-final-report.md`:
```markdown
# NEET PG QA Pass — Final Report

**Completed:** YYYY-MM-DD
**Scope:** frontend-neetpg/
**Bugs Found:** N total (X P0, Y P1, Z P2)
**Bugs Fixed:** N
**Commits:** M total

## Bugs by Surface
| Surface | P0 | P1 | P2 | Fixed |
|---|---|---|---|---|
| Landing | 0 | 2 | 1 | 2 |
| Auth | ... |

## Commits
- `<hash>` fix(neetpg): ...
- ...

## Remaining P2 / Punted Issues
- ...

## Final Screenshots
- ![Landing](qa-final-landing.png)
- ...
```

- [ ] **Step 5: Commit final report**

```bash
git add .playwright-mcp/qa-final-report.md
git commit -m "docs(qa): NEET PG QA pass final report"
```

- [ ] **Step 6: Report summary to user**

Tell the user the totals and stop. Let them decide if more passes are needed (INICET, other frontends, etc.).

---

## Self-Review

**1. Spec coverage:**
- 9 surfaces ✓ (Tasks 2-10 cover all of them)
- 20-30 random Qs per category ✓ (Tasks 4, 5, 7 include sampling steps)
- One-at-a-time fix loop ✓ (Task 11)
- Pre-flight checks ✓ (Task 1)
- Bug log format ✓ (referenced in every Task)
- Final report ✓ (Task 12)
- Scope guardrails (no backend code, no refactoring) ✓ (Global Constraints)

**2. Placeholder scan:** No TBD/TODO. All steps have concrete actions.

**3. Type consistency:** All bug entries use same `Fix:` / `Verified:` fields. All commits use `fix(neetpg):` or `fix(neetpg-content):` prefix consistently.

**No fixes needed.**