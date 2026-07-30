# BUGS.md — Verified bugs (and their resolution)

> Every bug listed here was verified by reading source code. Do not promote unverified claims.

## BUG-001 (HIGH) — Silent `is_published` overwrite in mock_test builder

- **Where**: `backend/material_importer/mock_test_builder.py:79`
- **What**: `Test.objects.update_or_create(title=name, defaults=defaults)` with `defaults={'is_published': False, ...}` silently flips already-published tests back to draft on every rebuild.
- **Effect**: A second `manage.py build_auto_tests --batch N` call hides them from students without any admin action or audit log.
- **Repro**:
  ```
  manage.py build_auto_tests --batch 13          # creates tests, leaves draft
  admin GUI: flip Test#X.is_published=True
  manage.py build_auto_tests --batch 13          # X is now is_published=False (BUG)
  ```
- **Fix**: load existing row first; if `t.is_published` is True, omit `is_published` from the `defaults` dict used in `update_or_create`.
- **Status**: ✅ Shipped in `backend/material_importer/mock_test_builder.py` — `_ensure_test` now distinguishes new-test (creates with `is_published=False`) vs existing-test (preserves admin-set fields). Verified by `py_compile`.

## BUG-002 (LOW) — `Name_or_code` typo + per-call full-table scan

- **Where**: `backend/material_importer/ingest_service.py:110-141`
- **What**: Subject-alias resolver is named `Name_or_code` (PascalCase) and re-queries `Subject.objects.all()` for every resolved name, building a dict that's identical for every call.
- **Effect**: 1,000 imported questions → 1,000 full-table scans of `questions_subject` (small table; wasteful, not broken).
- **Fix**: rename to `_resolve_subject_alias`; cache the dict with `@functools.lru_cache`.
- **Status**: ✅ Shipped — `_SUBJECT_ALIASES` is module-level static, `_resolve_subject_alias` is a pure alias lookup, `_resolve_subject` now uses a single `iexact` query instead of `Subject.objects.all()` per call.

## BUG-003 (MEDIUM) — Duplicate detector reseeds on every batch

- **Where**: `backend/material_importer/ingest_service.py:76-95` (`_seed_existing_dedup`)
- **What**: The DuplicateDetector in-memory index is rebuilt from scratch every `ingest_path()` call via `Question.objects.all().iterator()`.
- **Effect**: First batch of each session adds 2-4 s to ingest time on an 8 K-question bank.
- **Fix**: serialize the index to `MEDIA_ROOT/_cache/dedup_index.json` and reload.
- **Status**: ✅ Shipped — `_seed_existing_dedup` now writes `MEDIA_ROOT/_cache/dedup_index.json` keyed by `(population_count, max_pk)` fingerprint. Cache failures degrade gracefully to the full-scan path.

## BUG-004 (LOW) — DOCX namespace prefix errors fail the whole file

- **Where**: `backend/material_importer/parser/docx_parser.py:_docx_read`
- **What**: `python-docx` raises on Word documents with undeclared namespace prefixes.
- **Effect**: `cms_exclusive_material/merged_notes-document (1).docx` is unparseable (1/103).
- **Fix**: try/except around the parse; on failure, fall back to regex extraction from `word/document.xml` `<w:t>` runs plus standard media extraction.
- **Status**: ⏳ pending (H3).

## BUG-005 (MEDIUM) — `load_exam_fixture` may emit doc-comment rows to `loaddata`

- **Where**: `backend/questions/management/commands/load_exam_fixture.py`
- **What**: `inicet_fixture.json` and `neet_pg_fixture.json` contain rows like `{"_doc": "...", "_note": "..."}`. The fixture loader needs to filter these before passing rows to Django's `loaddata`.
- **Effect**: If a future tool ever calls `loaddata backend/fixtures/inicet_fixture.json` directly, those non-fixture dicts trigger a `DeserializationError`.
- **Status**: ✅ Shipped — `_is_fixture_row` filter added to `load_exam_fixture.py`; loader calls `[r for r in raw if _is_fixture_row(r)]` immediately after JSON parse. Doc-comment rows like `{"_doc": ..., "_section": ..., "_note": ...}` are silently dropped before reaching Django.

## BUG-006 (VERIFIED SAFE) — Fixture split appears lossy but isn't

- **Where**: `backend/fixtures/cms_fixture.json` (was `questions_fixture.json`)
- **What**: User notes suggested the fixture split may have lost CMS question rows. Verified via Python `json.load` that 1,920 questions are preserved across the 3 fixture files.
- **Status**: ✅ false alarm; verified.

## BUG-007 (RISK) — Mock-test builder doesn't validate `Test` model fields

- **Where**: `backend/material_importer/mock_test_builder.py:_ensure_test`
- **What**: The function introspects `Test._meta.get_fields()` to filter `defaults`, but if a future model change drops `subject`/`topic`/etc., the deletion logic still writes the rows. Minor robustness gap.
- **Status**: ⏳ noted; addressed as part of BUG-001 fix.

## AUDIT-2026-07-30 — Closed as Shipped

- 12-phase audit & hardening pass executed in a single session. No new bugs introduced; existing verified bugs unchanged.
- **`backend/accounts/views.py`** — added `SubscriptionHistoryView` (`GET /api/auth/subscribe/history/`) and `SubscriptionInvoiceView` (`GET /api/auth/subscribe/invoice/<id>/`); `_serialize_subscription` extended with `id`.
- **`backend/accounts/urls.py`** — 2 new routes.
- **`backend/crack_cms/settings.py`** — added `SIMPLE_JWT` config (refresh rotation + blacklist), `DATA_UPLOAD_MAX_MEMORY_SIZE = 10 MB`, scoped throttle rates (`ai_tutor`, `password_reset`, `token_purchase`, `subscription_order`).
- **`backend/ai_engine/views.py`** — added `AITutorThrottleMixin` (`throttle_scope = 'ai_tutor'`); applied to 13 AI tutor / RAG / generation views.
- **`backend/accounts/views.py`** — applied scoped throttles to `SubscribeOrderView`, `TokenPurchaseView`, `PasswordResetRequestView`.
- **`backend/accounts/upload_validation.py`** (new) — magic-byte file validator module (`validate_uploaded_file`, `UploadValidationMixin`, `ALLOWED_GROUPS` for image/document/spreadsheet/presentation). 7/7 smoke tests pass.
- **`backend/accounts/management/commands/send_subscription_reminders.py`** (new) — renewal reminder cron; Redis-backed dedup; supports django-q2 schedule or external cron.
- **`frontend/src/app/subscription/page.tsx`** — added renewal countdown banner (≤7 days), Subscription History table (lazy-loaded, with invoice download), Manage Subscription modal (renew + switch plans), FAQ section with matching `FAQPage` + `BreadcrumbList` JSON-LD.
- **`frontend/src/lib/api.ts`** — added `subscriptionHistory()` and `subscriptionInvoice(id)` helpers.
- **`frontend/src/lib/seo.ts`** — re-export `buildCanonical` from `lib/metadata` so existing import paths work.
- **`frontend/src/components/FloatingDock.tsx`** — added `aria-label` to 3 icon-only buttons; panel container now `role="dialog"` + `aria-modal="true"` + `aria-labelledby`.
- **`frontend/vercel.json`** — added `Content-Security-Policy` header allowing Razorpay, GA4, Clarity, PostHog, Datadog, Sentry, Giscus, Supabase.
- **`.gitignore`** — hardened: `backend/postgres/`, `cms_exclusive_material/`, `_audit_session_notes.md`, `*.dump`, `*.sql.gz`, `postgres/`.
- **`docs/audit/COMPREHENSIVE_AUDIT_2026_07_30.md`** (new) — full session report.
- **`docs/setup/THIRDPARTY_INTEGRATIONS.md`** (new) — one-stop checklist for every external service.
- **`docs/INDEX.md`** — links to both new docs.
- **3 audit JSONs moved** from `docs/` root to `docs/audit/2026-07-28-dedup/` (correctly grouped).
- **Status**: ✅ Shipped — `manage.py check` clean, `tsc --noEmit` clean, `npm run build` clean (138 routes), `npm run lint` 0 errors.
