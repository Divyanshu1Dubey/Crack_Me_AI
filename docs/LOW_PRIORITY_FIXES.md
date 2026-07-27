# Low-Priority / Backlog Fixes

> Defer until after the high-priority pass lands. Ordered by effort-to-impact ratio.

## Material Importer — hardening

- [ ] Move ingest pipeline to a `django-q2` async task instead of synchronous `transaction.atomic` per file. Today's sync path makes the request thread sit during large batches.
- [ ] OCR pass on extracted images (`pytesseract` is heavy, but the dataset has many "diagram + label" images where text extraction would unlock semantic search).
- [ ] Per-file AI summary (one AI call per `ImportMaterial` to fill `subject_guess` + `topic_guess`) so the batch admin view shows reliable categories without per-question AI cost.
- [ ] Strip ZIP-only fallback for DOCX (already captured in H3).

## Frontend

- [ ] Tailwind 4 syntax sweep across the whole `frontend/src/**/*.tsx` tree, not just the 4 changed files.
- [ ] Bundle audit (`npm run build` should output sizes per route; ensure no route exceeds 250 kB JS).
- [ ] Replace any remaining `useEffect` + `useState` debouncers with `useDeferredValue` where appropriate.
- [ ] Lazy-load the AI tutor component (`/ai-tutor`) — it's likely heavy and rarely used in initial paint.
- [ ] Add `@vercel/analytics` or upgrade existing — the existing `DatadogInit` is component-side only.

## Backend

- [ ] Enable RAG in production behind a `RAG_ENABLED=1` env; today the `DEBUG` gate is hardcoded (per memory) — flip to env-driven.
- [ ] Add `admin:axes` rotation/reporting in Django admin to track failed-login patterns (django-axes already provides hooks).
- [ ] Replace `print()` in `scripts/inventory_mocktests.py` with structured JSON output (the output it produces is one-time scratch anyway).
- [ ] Document the `postgres/` dir — `ls backend/postgres` shows an empty dir under git but `backend/postgres/.gitkeep`-style artifact is unverified.
- [ ] Add `courseprogress` view to the analytics dashboard if missing (admin control tower currently shows aggregate; per-student progress drilldown is missing for support).
- [ ] Tokens: extend `TokenBalance` with a `last_consumed_at` index for analytics dashboards ("when did this user last spend?").

## AI services

- [ ] The `NVIDIA Mistral` and `DeepSeek` providers are initialized but unused (per `crackcms-master-knowledge.md`). Either activate them in rotation **or** delete the initialization to remove dead code paths.
- [ ] Add telemetry: every AI call should record `(provider, model, prompt_tokens, completion_tokens, latency_ms, success)` so we can graph per-provider quality over time.
- [ ] Add a tiny `EXPLAIN_PIPELINE_VERSION` constant so cached AI explanations can be invalidated when the prompt template changes.

## Tests / CI

- [ ] Playwright E2E for the new admin "publish to Question bank" flow.
- [ ] Playwright E2E for the load_exam_fixture dry-run path (verifies JSON validity without DB).
- [ ] Property-based test (hypothesis) for `DuplicateDetector` — randomize near-dupes and ensure threshold behavior is monotonic.
- [ ] Frontend unit tests for `FormattedText` (image-token + escape handling).

## DevEx

- [ ] Add a top-level `make` `Makefile` / `justfile` with `make dev`, `make seed-fixtures`, `make test-importer` targets — the team currently chains `python manage.py …` by hand.
- [ ] Pre-commit hook: validate `backend/fixtures/*.json` parses as JSON before allowing commits.
- [ ] Add a `docs/CONTRIBUTING.md` that says "if you change fixtures, run `python manage.py load_exam_fixture X --dry-run` before pushing".

## Content

- [ ] The `merged_notes-document (1).docx` fallback (H3) would surface roughly 100+ theoretical notes that today aren't queryable.
- [ ] Audit 480 questions with `missing_correct_answer` (from Batch #13 QA) — many are likely "Image-based" questions where the parser couldn't match an option letter; a follow-up AI pass for these would close most of the gap.

## Mobile

- [ ] Bump Capacitor to v8 if available (currently v7 per memory); check breaking-change docs.
- [ ] Add a "Today's review" push-notification job (`django-q2` scheduler) for students so they get a daily reminder.
- [ ] Instrument a mobile crash reporter (Sentry captures BE crashes but mobile JS errors may slip).
