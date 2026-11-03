# Medical accuracy mission — progress log

_Last updated: 2026-11-03. Every number below was measured on that date unless marked otherwise. The earlier
version of this file (2026-11-02) described wave 1 as complete and verified; it was not, see "Corrections"._

## Where the work lives

- Branch **`medical-accuracy-2`** (from `main` 4fd92f8): the wave-0 schema and the wave-1 work of
  `medical-accuracy` (29fcdd8, 35eb346) ported onto main. `accounts/**` keeps main's version (the sign-in work
  shipped through PRs #43, #45–#48); `crack_cms/settings.py` and `requirements.txt` were merged by hand
  (main's sign-in settings, plus the mission's apps, flags and throttle scopes).
- Contract: `docs/audit/MEDICAL_ACCURACY_DESIGN.md`. Local data (outside the repository):
  `C:\Users\DIVYANSHU\crack_local\` (`reference_corpus\`, `key_audit\`).

## Verified state of the port (2026-11-03)

- Backend full suite: **1,901 tests OK** (9 skipped); `makemigrations --check` clean.
- Every new path is behind a default-off flag (`REFERENCE_STORE_PATH` empty, `RAG_STORE=legacy`,
  `EVIDENCE_FIRST=0`), so deploying the branch changes nothing until switched on.
- New apps and routes (backend only): `key_audit` (`/api/key-audit/` review queue), `evidence`
  (`/api/evidence/`), `reference_corpus` (`/api/reference/`), the editor endpoints
  (`questions/urls_editorial.py`) and the PYQ notes builder (`questions/urls_notes.py`).
- Migrations not yet applied anywhere but local databases: `questions.0042_medical_accuracy_schema`,
  `evidence.0001`, `key_audit.0001`, `reference_corpus.0001`.

## Data (local)

- Reference corpus `reference_corpus\reference_corpus.sqlite3` (204 MB): 241 sources registered (217 built,
  19 duplicates, 5 failed), 27,483 pages, 60,651 chunks, full-text (FTS5) index built. Embeddings: 512 of
  60,651 chunks (the 2026-11-01 build stopped in the embedding stage; ~2 chunks/s on this CPU, about 8 h for
  the rest). OCR deferred for 26 sources (image-only pages).
- Answer-key review: `key_audit\questions.jsonl` (10,013 questions); AI first pass (`claude-subagent (review
  signal)`, never a source, never applied to keys) on **2,634** questions: agree 1,121, unanswerable from the
  text 1,043, disagree 416, uncertain 54. Not yet reviewed: 7,379.
- Publisher answer tables recovered from the coaching compilations (Unicode Private Use Area glyph repair):
  on the earlier run 3,742 questions located confidently, 1,305 matching the stored key and 2,615 differing;
  the recovered keys agreed with the AI review 90.2 % of the time against 37 % for the stored keys (measured
  2026-11-02; the recovery script is not yet a management command).

## Corrections to the 2026-11-02 version

- "All waves implemented, tested and verified" was not true: the full suite had 2 failures
  (`tests_engine.tests_wave3_engine.LockedPayloadTests`). Cause: the exam payload stopped carrying explanation
  figures and the explanation video for every viewer, but the post-test review never received them back
  (`exam_review_media` was never called) and the results page reads them from the exam payload. The port keeps
  main's behaviour; the change returns with the review payload and the frontend switch (follow-up below).
- "Reduced test submission queries from 906 statements to constant bulk operations" was not true:
  `tests_engine/scoring_writes.py` was never imported anywhere and had no tests. It is not in the port.
- The sign-in figures quoted there (75 hashes, 126 links, 21 created) were a local run. Production
  (`cracklabs`, 2026-11-03): 77 hashes, 124 links, 22 created, 78 Google identities.
- No frontend work exists yet: no admin review-queue page, editor panels, evidence components or notes UI.

## Next

1. Wave 2 (frontend + wiring): admin review queue (`app/admin/review-queue`), editor panels (key change,
   explanation suggestion, provenance), evidence components (student citations ≤ 240 chars, admin page
   viewer), notes UI; post-test review media (backend + results page).
2. Answer-key audit on real data: AI first pass for the remaining 7,379 questions; source-key recovery as a
   management command; both feed the review queue as signals (never automatic key changes).
3. Corpus: OCR for the 26 deferred sources, the remaining embeddings (or BM25-only with a benchmark), the
   retrieval / answer benchmarks.
4. Production: apply the four migrations on `cracklabs` (Railway does not run `release.sh` yet), then switch
   the flags on step by step.
