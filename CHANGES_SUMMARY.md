# Recent fixes — 2026-07-21

Four end-to-end fixes applied in this session. Run the commands below
after pulling to apply DB-level cleanup.

## 1. "Show Year Stats" — year-wise practice/exam

**Symptom**: clicking a year in the year grid opened a modal with
"Practice Mode" / "Exam Mode" buttons, but Practice Mode loaded ALL
exams for that year (CMS + NEET PG + USMLE questions mixed).

**Root cause**: `frontend/src/app/questions/practice/page.tsx` called
`questionsAPI.list({ year, page_size: 200 })` without `exam_type`, so the
backend returned every question with `year == X`.

**Fix**:
- `frontend/src/app/questions/practice/page.tsx` now reads `?exam=` from
  the URL (or `useExamTrack().activeTrack`) and passes `exam_type` to the
  backend filter.
- `frontend/src/app/questions/page.tsx` year modal now navigates with
  `/questions/practice?year=${modalYear}&exam=${selectedExam}` so the
  exam track survives the modal click.

## 2. Unreadable characters (ΓÇÿ / Ã© / â€™ Mojibake)

**Symptom**: PYQ text rendered as ΓÇÿ, ΓÇÖ, Ã©, â€™ etc. on the live site,
even though the source `backend/pyq/2019` file was valid UTF-8 and the
`backend/questions_fixture.json` already contained the correct Unicode
curly quotes.

**Root cause**: Python importers opened text files with `open(path, "r",
encoding="utf-8")` BUT the `Question.save()` method never re-encoded
already-stored text, and any non-UTF-8 default-locale read (e.g. Windows
cp1252 during a manual CSV import) double-encoded the bytes. The
`backend/questions_fixture.json` itself was clean — the corruption
happened at import time on a non-UTF-8 system.

**Fix** — three layers:

1. `backend/questions/text_encoding.py` (new) — centralized
   `normalize_text()` / `fix_mojibake()` / `read_text_file()` helpers.
   Includes a `MOJIBAKE_TABLE` that maps every sequence the user
   reported (ΓÇÿ → ‘, ΓÇÖ → ’, Ã© → é, â€™ → ’, …).

2. `backend/questions/models.py` `Question.save()` now calls
   `normalize_text()` on every text field. From now on, ANY question
   that gets saved is repaired automatically. Idempotent.

3. `backend/questions/management/commands/fix_mojibake.py` (new) —
   one-shot cleanup. Walk every Question row, normalize text fields,
   and rewrite `questions_fixture.json`. Usage:
   ```
   cd backend
   python manage.py fix_mojibake --apply --fixture questions_fixture.json
   ```
   (dry-run first to inspect counts)

4. `import_2018_2019_pyqs.py` and `import_neet_pg.py` now read source
   files via `read_text_file()` and pass every text field through
   `normalize_text()` before saving.

## 3. NEET PG microsite at /exams/neet-pg

**What landed**:
- `frontend/src/app/exams/neet-pg/page.tsx` — NEW standalone page,
  emerald/teal theme, 19 PG subjects, year-wise NEET PG PYQ grid (2020
  – 2025).
- `frontend/src/components/exams/ExamMicrosite.tsx` — shared shell that
  all three exam microsites render with their own theme + content.
- `frontend/src/app/exams/_data.ts` — central config: each exam has
  distinct theme, hero copy, eligibility, subjects, high-yield topics,
  PYQ years, stats.
- Existing `ExamSwitcher` already routed `neet_pg` → `/exams/neet-pg`,
  no change needed.
- Homepage has a new "Pick your exam microsite" chooser section
  (`#exam-microsites`) that links to all three microsites.
- Footer chips for UPSC CMS / NEET PG / USMLE now link to the new
  microsites.

## 4. Three-exam microsite architecture

**What landed**:
- `/exams/cms` — UPSC CMS (cyan/sky blue, 5 subjects, PYQs 2018-2025).
- `/exams/neet-pg` — NEET PG (emerald/teal, 19 PG subjects, PYQs
  2020-2025).
- `/exams/usmle` — USMLE beta (indigo/violet, waitlist).
- `frontend/src/app/exams/[slug]/page.tsx` — dispatcher that redirects
  legacy aliases (`/exams/upsc-cms` → `/exams/cms`, `/exams/neetpg` →
  `/exams/neet-pg`) and renders an "exam not found" for unknown slugs
  (so `ini-cet`, `fmge` keep their old behavior unless explicitly
  rewritten).

Each microsite owns its own Metadata (title, description, OG tags,
canonical URL pointing at https://www.cracklabs.app/exams/<slug>) so
search engines treat them as distinct destinations while they share one
product shell and one AI tutor backend.