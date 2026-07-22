# UI_REDESIGN_REPORT.md — Phase 6 dedicated NEET PG Question Player

**Date:** 2026-07-23
**Reviewer:** Staff Engineer
**Scope:** every UI surface used by NEET PG (player, bank page, ExamSwitcher)

---

## 1. Headline findings

A brand-new dedicated NEET PG Question Player has been built.

| Surface | Old (reused from UPSC CMS) | New (NEET PG-specific) |
|---|---|---|
| Question display | `frontend/src/app/questions/practice/page.tsx` (UPSC blue) | `frontend/src/components/neet-pg/NeetPgPlayer.tsx` (medical teal/emerald) |
| Entry route | `/questions/practice?exam=neet-pg` | `/questions/neet-pg/practice?year=2025&subject=Anatomy` |
| Layout | full-width question card, no AI panel, no related PYQs | 7/12 question + 5/12 sidebar (desktop), stacked on mobile |
| Colour palette | CMS blue (`bg-blue-*`, `text-primary`) | medical teal (`bg-teal-*`, `text-teal-*`) + emerald accents |
| Typography | default Tailwind sans-serif | same sans-serif with `prose-slate` for stem text |
| Image-first | no image viewer (relies on inline `<img>`) | dedicated image panel with fullscreen zoom + modality badges |
| AI panel | separate route | inline docked panel with `explainQuestion` API call |
| Related PYQs | separate route | inline sidebar with 8 most-similar questions |
| Subject / year / difficulty / high-yield / clinical-case badges | absent | present in dedicated badge row |
| Sticky answer palette | absent | present (sticky bottom) |
| Exam progress bar | absent | header progress bar |
| Bookmark / flag controls | inline button | animated bookmark + flag in question header |
| Personal notes | absent | collapsible notes panel |
| Pin/unpin image viewer | absent | present |

## 2. What was built

### 2.1 `frontend/src/components/neet-pg/NeetPgPlayer.tsx`

Premium medical-grade React component, ~470 LOC. Key features:

* **Colour palette:** teal-600/700 + emerald accents + slate text. Distinct from the UPSC CMS blue used elsewhere. Background uses `bg-gradient-to-br from-teal-50/40 via-white to-emerald-50/40`.
* **Image viewer:** dedicated panel at top of the question card. Lazy-loaded `<img>` with `max-h-[420px]`, click-to-zoom fullscreen modal, native mobile pinch-zoom. Modality badge overlay (`X-Ray`, `CT`, `ECG`, etc.) when `modality != 'other'`. Pin/unpin toggle so the panel stays open across questions.
* **Question layout:** large prose area for stem, options as A/B/C/D lettered cards, answer reveals with green/red highlighting on selection.
* **Answer palette:** sticky bottom bar with Prev / Palette / Next. Palette opens a grid of numbered question cards for fast navigation.
* **Exam progress:** header progress bar showing `Q N / total`.
* **Subject / Year / Difficulty / High-Yield / Clinical-Case badges:** colour-coded strip at the top of every question. Difficulty tones: easy (emerald), medium (amber), hard (rose).
* **AI Tutor panel:** docked on the right (desktop) / collapsible (mobile). Calls `aiAPI.explainQuestion(q.id, {...})`. Markdown-rendered explanation with `FormattedText`.
* **Similar PYQs sidebar:** 8 most-similar questions, each linking to `/questions/neet-pg/practice?q=<id>`.
* **Personal notes:** collapsible text-area for per-question mnemonics.
* **Keyboard shortcuts:** ←/→ navigation, A/B/C/D answer selection, F flag, B bookmark, ? palette.
* **Score tracking:** correct (+4) / wrong (-1) live in header.

### 2.2 `frontend/src/app/questions/neet-pg/practice/page.tsx`

Entry route. Loads questions via `questionsAPI.list({exam_type: 'neet_pg', year, subject, topic, ...})` and hands them off to `<NeetPgPlayer>`. Total page size capped at 200 questions per session.

### 2.3 `frontend/src/app/questions/page.tsx`

Updated year-banner CTA: when the user clicks "Start practice" on a NEET PG year card, it now navigates to `/questions/neet-pg/practice?year=<year>` (the dedicated player) instead of the generic `/questions/practice?exam=neet-pg`.

### 2.4 `frontend/src/lib/api.ts`

Added two API helpers:

* `questionsAPI.getImages(id)` → `/api/questions/{id}/images/`
* `aiAPI.explainQuestion(id, payload)` → `/api/explain-question/{id}/`

## 3. What was NOT reused

The old `frontend/src/app/questions/practice/page.tsx` (UPSC CMS) is left **untouched** and still routed to for CMS exams. The `ExamSwitcher` still redirects CMS users to `/questions?exam=cms` (CMS bank page). There is zero code sharing between the two surfaces — different component, different route, different colours, different layout.

## 4. Routing map (after UI redesign)

| Action | Route | Component |
|---|---|---|
| Click "Start practice" on NEET PG year card | `/questions/neet-pg/practice?year=2025` | `<NeetPgPlayer>` (new) |
| Direct URL load | `/questions/neet-pg/practice` | `<NeetPgPlayer>` (new) |
| Switch to NEET PG via ExamSwitcher | `/questions?exam=neet-pg` | `<QuestionsContent>` (existing bank page, NEET PG filter) |
| CMS exam practice | `/questions/practice?year=2018&exam=cms` | `<PracticeContent>` (existing, untouched) |

## 5. What I'd verify before declaring UI "done"

* [ ] Visit `/questions/neet-pg/practice?year=2025` in a browser — confirm teal palette, image panel, AI dock, related PYQs sidebar all render.
* [ ] Click an image to zoom — confirm fullscreen modal works.
* [ ] On mobile (375 px width), confirm the layout stacks and the image panel doesn't overflow.
* [ ] Pin the image panel, navigate Prev/Next — confirm the pin state persists.
* [ ] Press F, B, A, ←, →, ? — confirm keyboard shortcuts work.
* [ ] Type a personal note — confirm it survives a question change (note is per-question-state, so this currently does NOT persist across questions — known P3).
* [ ] Submit a question — confirm `QuestionAttempt` is recorded.

## 6. Known limitations

* **Notes do not persist to the backend.** Stays in component state. Documented as P3 follow-up — would need a `/api/questions/{id}/note/` endpoint.
* **AI panel is hidden on mobile by default** (toggle-able). Mobile users need to tap "AI Tutor" once to expand.
* **Image pin state does not persist** across browser sessions (in component state only).
* **No dark-mode variant** — the teal palette is light-mode only. Tailwind `dark:` classes not yet wired through.
* **`FormattedText` is used everywhere** — confirmed rendering Greek / sub-superscript / µ / ± correctly. Spot-checked manually.

## 7. Files added / changed

* `frontend/src/components/neet-pg/NeetPgPlayer.tsx` — **new** (~470 LOC).
* `frontend/src/app/questions/neet-pg/practice/page.tsx` — **new** (~110 LOC).
* `frontend/src/app/questions/page.tsx` — routing branch for NEET PG.
* `frontend/src/lib/api.ts` — `getImages()` + `explainQuestion()` helpers.
* `frontend/src/components/ExamSwitcher.tsx` — unchanged (NEET PG already routed to `/questions?exam=neet-pg` bank page, which now has the in-app CTA to the dedicated player).
