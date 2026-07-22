# Phase 3 — Remaining Work (out of Phase 2 scope)

This document lists the follow-up work that is **explicitly out of
Phase 2 scope** per the user's mission. Phase 2 stops at the integration
point — every item below is Phase 3 territory unless the user reopens
scope.

---

## 1. Frontend opt-in components (deferred — touched practice flow)

The Phase-2 user mission said:

> "DO NOT TOUCH: authentication, payments, subscriptions, SEO,
> frontend UI, question practice flow (unless integration requires
> minor modification)."

So we ship no UI changes. The following components are designed but
not implemented:

* `frontend/src/components/recall/RecallBadge.tsx` — small badge that
  surfaces `Question.recall_status` next to question title.
* `frontend/src/components/recall/QuestionImageZoom.tsx` — zoom +
  fullscreen for `QuestionImage.file_url`.
* `frontend/src/components/recall/ProvenanceList.tsx` — paginated list
  of `QuestionSource` rows for a question (filename, sha16, page).
* `frontend/src/components/recall/ImageGallery.tsx` — multi-image
  grid with modality chips.
* `frontend/src/components/recall/RecallSearchBox.tsx` — explicit
  filter UI for `/api/questions/recall_search/?...`.

These will only land once Phase 3 begins and the user green-lights
practice-flow changes.

---

## 2. FTS5 mirror

`backend/questions/recall_search.py::build_fts_query()` already returns
FTS5 `MATCH` expressions. The DB-side mirror is deferred:

* Migration that creates `questions_question_fts`
  (FTS5 virtual table shadow) — needs a separate `python manage.py
  rebuild_question_fts` command.
* Signal handler that keeps the mirror in sync on Question save.
* Toggle: `ENABLE_FTS5_MIRROR` env var (off by default in v1).

Off-limits for Phase 2 because it touches `migrations/` again.

---

## 3. Re-OCR batch action

`QuestionImageAdmin.action_re_ocr` currently logs + counts. The wire
to `importers.neetpg.ocr_engine.ocr_image()` requires:

* threaded OCR worker (don't block admin threads);
* a per-job status row (currently not modelled — could reuse
  `QuestionImportJob` with `job_type='ocr-batch'`);
* update of `QuestionImage.ocr_text`, `QuestionImage.ocr_confidence`.

Phase 3.

---

## 4. Pre-OCR image normalization pipeline

The current `importers/neetpg/image_extractor.extract_embedded(...)`
writes whatever PyMuPDF decodes. A Phase-3 pass should:

* auto-rotate based on EXIF + tesseract hOCR deskew hints;
* strip scan watermarks via `is_watermarked=True` heuristic;
* generate a 1024px thumbnail + a high-res `file` upload;
* populate `QuestionImage.width/height` automatically.

---

## 5. Topic mapping ML model

`importers/neetpg/topic_mapper.map_subject(...)` and
`topic_mapper.map_topic_subject(...)` are keyword-driven. A Phase-3
pass should:

* plug in a single local embedding model (e.g. `bge-small-en-v1.5`,
  already loaded for RAG);
* add `confident` vs `needs_review` flags to `Question.subject_id` /
  `Question.topic_id`;
* emit unmatched stems as `QuestionExtractionItem` rows with `note=
  auto-topic failed`.

---

## 6. Bulk admin operations

`QuestionAdmin` already has `bulk-metadata` and `bulk-delete` actions
inherited from Phase-1. A Phase-3 pass should:

* add `bulk-archive-recall` (sets `recall_status='coaching_compiled'`
  on selected rows);
* add `bulk-canonicalize-duplicates` that promotes the highest-
  confidence row in a `DuplicateCluster` and links the others via
  `Question.similar_questions`;
* add `bulk-tag-subject` (Phase-1 topic mapper auto + admin override).

---

## 7. SQLite FTS maintenance endpoint

Will ship alongside the FTS5 mirror:

* `POST /api/admin/rebuild_fts/` — admin-only rebuild.
* `GET  /api/admin/fts_status/` — doc count + last-rebuild time.

---

## 8. Telemetry + recall-bank quality dashboard

* Per-run coverage stats (questions per page, OCR confidence trend).
* Per-source quality trend (does the same PDF re-run improve over
  time?).
* Reviewer load (count of `QuestionExtractionItem` rows by `status`).

Phase 3 likely lives under `analytics/` next to existing dashboards.

---

## 9. Mobile (Capacitor) recall UI

`mobile-app/` currently wraps the existing frontend. The recall
features will inherit for free once the frontend opt-in components
ship — but if the user wants a dedicated mobile-mode UI it needs:

* bottom-sheet question image viewer;
* off-line cache for `RecallSource` rows;
* push notification when a stuck import finishes.

---

## 10. Production hardening

Pre-launch checklist:

* [ ] Add `csat:9.5 ms` timing to recall_search.
* [ ] Add caching via `cache_middleware` on `GET /api/questions/recall_search/`.
* [ ] Add rate-limit bypass for `IsControlTowerAdmin` users (already in
      throttle classes — confirm).
* [ ] Tighten `Question.recall_text_hash` — currently 64 chars; verify
      Postgres index size in production.
* [ ] Add CI step that imports a tiny fixture (PDF + 3 questions) and
      asserts: 1 RecallSource row, 3 Question rows, 0 duplicates.

---

## 11. Pre-commit / Bandit sweep

```
bandit -r backend/importers/ -x backend/importers/__pycache__
bandit -r backend/questions/recall_serializers.py
bandit -r backend/questions/recall_search.py
```

Expected: clean.

---

## 12. Doc cross-links

After Phase 3 ships:
* Add recall bank section to `docs/PROJECT_OVERVIEW.md`.
* Add entry to `docs/INDEX.md` for `docs/neetpg/PHASE2_COMPLETION_REPORT.md`.
* Update `docs/API_REFERENCE.md` with the 9 new endpoints.

These are documentation-only updates; safe and quick.

---

**Bottom line:** Phase 2 is feature-complete at the integration
boundary. Every remaining item above is a Phase 3 deliverable, not a
Phase 2 gap.
