# Admin Import Center — Architecture

The Import Center is built on top of the existing `material_importer` Django
app. It does not replace the parser pipeline; it adds a browser UI, a
background scheduler, and a richer REST surface so non-technical staff
can drive the pipeline without using the CLI.

```
┌────────────────┐  drag-drop  ┌──────────────────────┐
│   /admin/      │  / upload   │  POST /admin/import/ │   Multipart
│   import-center│────────────►│       upload/        │──────────────┐
│   (Next.js)    │             │                      │              │
└────────────────┘             └──────────────────────┘              │
        │ polls /api/.../batches/{id}/                                │
        │                                                              ▼
        │                              ┌──────────────────────────────────────┐
        │                              │  ingest_service.ingest_path()        │
        │                              │  (background thread per batch)        │
        │                              └──────────────────────────────────────┘
        │                                          │
        │                                          ▼
        │                              ┌──────────────────────────────────────┐
        │                              │  ParserFactory → docx_fidelity /     │
        │                              │  docx_parser / pdf_parser / pptx_     │
        │                              │  parser / text_parser                │
        │                              └──────────────────────────────────────┘
        │                                          │
        │                                          ▼
        │                              ┌──────────────────────────────────────┐
        │                              │  Database tables (staging):          │
        │                              │   • ImportBatch                      │
        │                              │   • ImportMaterial                   │
        │                              │   • ExtractedQuestion                │
        │                              │   • ExtractedTheory                  │
        │                              │   • ImportedImage                    │
        │                              │   • ImportAuditLog                   │
        │                              └──────────────────────────────────────┘
        │                                          │
        │   ┌──────────────────────────────────────┴──────────────────┐
        │   │                                                         │
        │   ▼                                                         ▼
┌────────────────┐                                          ┌────────────────┐
│ Review Queue   │   approve / reject / classify-ai          │  Publish step  │
│ (UI)           │─────────────────────────────────────────► │  mock_test_    │
│                │                                           │  builder       │
└────────────────┘                                           └────────────────┘
                                                                       │
                                                                       ▼
                                                          ┌──────────────────────┐
                                                          │  Live Question bank  │
                                                          │  + tests_engine.Test │
                                                          └──────────────────────┘
```

## Module layout

```
backend/material_importer/
├── api_views.py              ← NEW — REST endpoints (DRF APIViews + ViewSets)
├── sync_serializers.py       ← NEW — DRF serializers
├── urls.py                   ← NEW — URL routing under /api/admin/import/
├── ingest_service.py         ← existing — orchestrator (parse → persist)
├── mock_test_builder.py      ← existing — auto-tests + publish_batch
├── publishing.py             ← existing — ExtractedQuestion → Question promotion
├── duplicate_detector.py     ← existing — content_hash + shingle similarity
├── ai_classifier.py          ← existing — heuristic + AI fallback classifier
├── models.py                 ← existing — ImportBatch / ImportMaterial / etc.
├── parser/
│   ├── parser_factory.py     ← existing — chooses parser per file
│   ├── docx_fidelity.py      ← existing — high-fidelity DOCX parser
│   ├── docx_parser.py        ← existing — fallback DOCX parser
│   ├── pdf_parser.py         ← existing — PDF parser
│   ├── pptx_parser.py        ← existing — PPTX parser
│   └── text_parser.py        ← existing — TXT / MD parser
├── tests/test_api.py         ← NEW — DRF endpoint tests
└── migrations/0001..0004     ← existing
```

```
frontend/src/app/admin/import-center/
├── layout.tsx              ← NEW — auth gate + tab nav
├── page.tsx                ← NEW — dashboard
├── upload/page.tsx         ← NEW — drag/drop + multi-file + folder upload
├── batches/page.tsx        ← NEW — batches list
├── batches/[id]/page.tsx   ← NEW — batch detail with live polling
├── review/page.tsx         ← NEW — review queue + bulk actions + preview drawer
└── search/page.tsx         ← NEW — full-text search

frontend/src/lib/api.ts     ← MODIFIED — added `importCenterAPI` namespace
frontend/tests/e2e/import-center.spec.ts ← NEW — Playwright E2E
```

## Why we kept the parser pipeline untouched

`material_importer.ingest_path()` already:

- Walks a folder, picks a parser per file, persists `ImportMaterial`,
  `ExtractedQuestion`, `ExtractedTheory`, `ImportedImage`, `ImportAuditLog`.
- Computes per-row provenance, content hashes, and dedup.
- Seeds an on-disk dedup cache so 10k-question batches finish in seconds.

Wrapping it behind the REST upload endpoint (instead of rewriting the
pipeline) means:

1. Every CLI workflow keeps working — `python manage.py ingest_cms_material`
   still works.
2. Parser regressions in the UI are detected with the same code path as
   the CLI, so QA effort stays concentrated.
3. Future parser improvements (e.g. better table extraction) automatically
   reach the UI without further wiring.

## Why a background thread (not django-q2)

`django-q2` is configured on the platform, but for the Import Center we
spawn a single daemon thread per batch:

- Simpler operational model — no broker to wake up, no `Q_CLUSTER`
  configuration drift.
- Threads survive `manage.py runserver` reloads and behave predictably on
  Render free / low-cost instances.
- A 4-second polling loop in the UI gives the admin real-time feedback.

For a higher-volume deployment, swap `threading.Thread` for
`django_q.Conf.enqueue` in `api_views.UploadCreateBatchView.post` — the
endpoint contract is unchanged.

## Database touchpoints

The Import Center only **reads** and **updates** the staging tables. The
only mutation that escapes into the live system is `publish_batch()` (see
`material_importer/publishing.py`), which is invoked explicitly via the
**Publish** button.

Tables the UI reads:

- `ImportBatch`, `ImportMaterial`, `ExtractedQuestion`, `ExtractedTheory`,
  `ImportedImage`, `ImportAuditLog`, `Subject`, `Topic`.

Tables the UI writes:

- `ImportBatch` (cancel status, finished_at, summary, error_report)
- `ImportMaterial` (parsed_at, counts, warnings, errors)
- `ExtractedQuestion` (status, review_note, inferred_*)
- `ImportAuditLog` (one row per state-changing action)

The live `Question` and `tests_engine.Test` tables are only written by
`publish_batch()` / `build_for_batch()`, which are triggered by the
**Publish** button.

## Image storage

Two backends:

1. **Supabase Storage** (default in production) — bucket
   `crack-cms-question-images`, path `question_images/{qid}/{short_sha}.{ext}`.
2. **Django `MEDIA_ROOT`** — fallback when Supabase env vars are missing.

The selector lives in `ingest_service._store_image()` and the question-image
upload helper in `backend/questions/image_upload.py`. Image URLs in the
question_text use the `[[img:N]]` token scheme resolved by the
`FormattedText` component.

## Authorization

- `IsAdminUser` on every endpoint.
- Frontend `/admin/import-center/*` layout checks `user.role === 'admin'`
  before rendering; redirects to `/login` if not.
- Server-side RBAC is authoritative — even an authenticated token without
  `is_staff` gets a 403.

## Audit trail

Every state-changing action writes one `ImportAuditLog` row with
`level ∈ {info, warning, error}`. The batch detail page shows the last 25
entries; the audit endpoint is paginated.

Bulk decisions write one row per *batch* (not per row) so the log stays
readable at scale.

## Performance

- Background thread per batch → HTTP request returns immediately with the
  new `batch_id`.
- Batch detail page polls `/api/admin/import/batches/{id}/` every 4 seconds
  while `status ∈ {processing, queued}`.
- `bulk_create(batch_size=200)` for every staging write.
- Dedup index cached on disk (`ingest_service._seed_existing_dedup`).
- AI classifier falls back to a deterministic heuristic when
  `use_ai=False` — uploads finish in seconds, not minutes.

## Backward compatibility

The previous CLI workflow (`python manage.py import_mocktests`,
`python manage.py ingest_cms_material`, etc.) is unchanged. Anyone still
using the CLI to push content into the live DB can keep doing so; the
Import Center is purely additive on top of the same staging tables.