# Phase 2 — Files Changed

**Status:** COMPLETE
**Phase 2 scope:** Wire Phase-1 NEET-PG / INI-CET / AIIMS-PG recall
importer into the existing CrackCMS Django app — additive only.

---

## A. NEW FILES

### Apps & integration

| Path | Lines | Purpose |
|---|---|---|
| `backend/importers/__init__.py` | small | Package marker with module docstring |
| `backend/importers/apps.py` | small | `ImportersConfig` (name='importers', verbose='Recall Importers') |
| `backend/importers/models.py` | small | Re-exports Phase-2 models for `importers.models` namespace |
| `backend/importers/admin.py` | ~110 | 5 new admin classes (Recall / Question / Image / Cluster / Member) |
| `backend/importers/neetpg/urls.py` | small | URL routes for `/api/imports/neetpg/...` |
| `backend/importers/neetpg/views.py` | ~125 | 4 view classes: list, detail, retry, reports |
| `backend/importers/neetpg/tasks.py` | small | `run_recall_import()` wrapper for django_q |
| `backend/importers/neetpg/db_writer.py` | ~360 | `DjangoWriter` — translates Phase-1 dataclasses to ORM rows |

### Question app extensions

| Path | Lines | Purpose |
|---|---|---|
| `backend/questions/recall_search.py` | ~170 | `recall_search` DRF action + image/sources helpers + FTS5 hook |
| `backend/questions/recall_serializers.py` | ~80 | 5 recall-specific ModelSerializers |
| `backend/questions/migrations/0023_recall_neetpg_fields_and_models.py` | ~470 | Add 9 fields + 5 new models + indexes |

### Management commands

| Path | Lines | Purpose |
|---|---|---|
| `backend/importers/neetpg/management/commands/neetpg_import_run.py` | ~50 | Production wrapper: create job + queue via django_q |
| `backend/importers/neetpg/management/commands/neetpg_status.py` | ~70 | Operator-visible job listing |
| `backend/importers/neetpg/management/commands/neetpg_retry.py` | ~40 | Re-queue failed/completed job |
| `backend/importers/neetpg/management/commands/neetpg_reconcile.py` | ~135 | Re-link Phase-1 JSONL into existing Question rows |
| `backend/importers/neetpg/management/commands/neetpg_rollback.py` | ~70 | Soft-delete Questions written by a job |

### Docs

| Path | Purpose |
|---|---|
| `docs/neetpg/PHASE2_COMPLETION_REPORT.md` | Phase 2 mission report (final) |
| `docs/neetpg/FILES_CHANGED.md` | This file |
| `docs/neetpg/REMAINING_WORK.md` | Phase 3 backlog |
| `docs/neetpg/ARCHITECTURE_ANALYSIS.md` | Pre-implementation architecture audit |
| `docs/neetpg/INTEGRATION_PLAN.md` | Pre-implementation strategy |
| `docs/neetpg/DATABASE_MIGRATION_PLAN.md` | Migration plan / indexes / rollback |
| `docs/neetpg/IMPORT_INTEGRATION_REPORT.md` | Importer wiring contract |
| `docs/neetpg/SEARCH_DESIGN.md` | `recall_search` action contract |
| `docs/neetpg/IMAGE_SYSTEM.md` | QuestionImage + dedup design |
| `docs/neetpg/ADMIN_UPGRADE.md` | New admin class surface |
| `docs/neetpg/QUALITY_REPORT.md` | Issue taxonomy + repair commands |

---

## B. EDITED FILES (strictly additive)

| Path | Change type | Details |
|---|---|---|
| `backend/questions/models.py` | additive | 9 AddField + 4 constant tuples + 5 new models appended |
| `backend/questions/views.py` | additive | 5 new `@action` methods + new serializer imports |
| `backend/crack_cms/settings.py` | additive | `'importers'` added to `INSTALLED_APPS` (after `knowledge_base`, before `axes`) |
| `backend/crack_cms/urls.py` | additive | `path("api/imports/neetpg/", include("importers.neetpg.urls"))` |
| `backend/importers/neetpg/runner.py` | additive | `process_one_pdf` now calls `_persist_into_db(...)` after JSONL write |

### Diff snapshot for `views.py`

Before:
```python
from .recall_serializers import (
    QuestionImageSerializer, QuestionSourceSerializer,
    RecallSourceSerializer, DuplicateClusterSerializer, DuplicateMemberSerializer,
)
```

After:
```python
from .recall_serializers import (
    # Used directly here:
    RecallSourceSerializer,
    DuplicateClusterSerializer,
    # Imported indirectly via `questions.recall_search`:
    # - QuestionImageSerializer (recall_question_images)
    # - QuestionSourceSerializer (recall_question_sources)
)
```

### Diff snapshot for `settings.py`

```diff
 INSTALLED_APPS = [
     ...
     'knowledge_base',
+    'importers',
     # Security
     'axes',
 ]
```

### Diff snapshot for `urls.py`

```diff
 urlpatterns = [
     ...
     path("api/jobs/", include("jobs.urls")),
+    path("api/imports/neetpg/", include("importers.neetpg.urls")),
 ]
```

### Diff snapshot for `runner.py`

Adds `_persist_into_db(...)` helper that:

1. Imports `DjangoWriter` lazily.
2. Creates or fetches the `QuestionImportJob` by `import_job_id`.
3. Calls `upsert_recall_source(...)` then `write_question(...)` for every parsed question.
4. Calls `write_image(...)` per image (best-effort linking to a Question row).
5. Returns a stats dict folded into `summary['db']`.

All inside a `try/except` so a DB error never blocks Phase-1 JSONL output.

---

## C. NOT TOUCHED (intentional)

```
backend/questions_fixture.json
backend/Medura_Train/...
backend/build.sh
backend/ai_engine/*
backend/accounts/*
backend/tests_engine/*
backend/analytics/*
backend/textbooks/*
backend/resources/*
backend/video_engine/*
backend/jobs/*
backend/knowledge_base/*
backend/chroma_db/*

frontend/src/app/questions/                  # practice flow / SEO — forbidden
frontend/src/app/ai-tutor/                   # AI tutor UI — forbidden
frontend/src/app/dashboard/                  # dashboard — forbidden
frontend/src/app/tests/, simulator/, analytics/, tokens/, books/, papers/
frontend/src/components/Sidebar.tsx
frontend/src/lib/auth.tsx                    # auth context — forbidden
frontend/src/lib/api.ts                      # axios — forbidden

.github/copilot-instructions.md              # unchanged
README.md
CLAUDE.md
docs/seo/*                                   # SEO reports — Phase 2 scope excludes
```

---

## D. Migration summary

File: `backend/questions/migrations/0023_recall_neetpg_fields_and_models.py`

Operations (in order):

1. AddField `Question.recall_status` (default='official_compiled', indexed)
2. AddField `Question.question_type` (default='single_best', indexed)
3. AddField `Question.clinical_category` (default='clinical', indexed)
4. AddField `Question.session` (default='', blank)
5. AddField `Question.confidence_score` (default=1.000)
6. AddField `Question.ocr_confidence` (nullable)
7. AddField `Question.extraction_confidence` (default=1.000)
8. AddField `Question.is_image_based` (default=False)
9. AddField `Question.recall_text_hash` (default='', blank, indexed)
10. AddIndex `Question` (`question_type`, named `ix_question_type`)
11. AddIndex `Question` (`clinical_category`, named `ix_question_clinical`)
12. CreateModel `RecallSource` + UniqueConstraint (sha256+page_range) + 3 AddIndex
13. CreateModel `QuestionSource` + UniqueConstraint (recall_source+page+question_number) + 3 AddIndex
14. CreateModel `QuestionImage` + 4 AddIndex (question / modality / phash / is_active)
15. CreateModel `DuplicateCluster` + 1 AddIndex
16. CreateModel `DuplicateMember` + UniqueConstraint (cluster+question) + 1 AddIndex

Dependencies: `("questions", "0022_question_is_disputed")`,
`migrations.swappable_dependency(settings.AUTH_USER_MODEL)`.
