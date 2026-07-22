# Database Migration Plan — Phase 2

> One additive migration: `questions/migrations/0023_recall_neetpg_fields_and_models.py`.
> Touches only `questions.models`. Existing rows continue to render.

---

## 1. Migration dependency graph

```
0001_initial                                ┐
0002_question_ai_explanation_…              │
0003_alter_subject_paper                    │
0004_questionfeedback                       │
0005_discussion_flashcard_note_…            │
0006_flashcard_personal_note                │
0007_question_verification_fields           │
0008_questionimportjob                      │  ← Phase 2 adds fields on
0009_questionextractionitem                 │     Question + 5 new models
0010_question_ai_override_lock_fields        │
0011_adminaipromptversion_questionaioperationlog
0012_questionrevisionsnapshot_and_more
0013_question_concept_id
0014_alter_question_admin_answer_override_and_more
0015_questionattempt
0016_question_ai_clinical_pearl_…
0017_question_exam_type_subject_exam_type
0018_question_admin_edited_question_display_number_and_more
0019_alter_question_uuid
0020_examtrack_announcement_exam_tracks_and_more
0021_question_is_controversial_and_more
0022_question_is_disputed
                                           │  ← NEW: 0023_recall_neetpg_fields_and_models
```

---

## 2. New fields on `Question`

All additive, all with sensible defaults. Existing rows remain valid.

| Field | Type | Default | Notes |
|---|---|---|---|
| `recall_status` | CharField(32) | `'official_compiled'` | choices: `recall / coaching_compiled / official_compiled` |
| `question_type` | CharField(32) | `'single_best'` | `single_best / multiple_correct / assertion_reason / match / image_based / numerical` |
| `clinical_category` | CharField(32) | `'clinical'` | `clinical / preclinical / paraclinical` |
| `session` | CharField(16) | `''` | `jan / jul / may / nov / none` |
| `confidence_score` | DecimalField(4,3) | `1.000` | 0..1 weighted blend |
| `ocr_confidence` | DecimalField(5,2) | null | 0..100 from tesseract |
| `extraction_confidence` | DecimalField(4,3) | `1.000` | parser score |
| `is_image_based` | BooleanField | `False` | image required to answer |
| `recall_source_id` | BigIntegerField | null | FK to `RecallSource` populated on bulk import |
| `recall_page_number` | IntegerField | null | primary source page |
| `recall_text_hash` | CharField(64) | `''` | sha256 of normalised text for cross-PDF dedup |

Add 4 indexes:

- `(recall_status)` — filter recall vs official.
- `(question_type)` — filter assertion-reason / image-based / multi-correct.
- `(clinical_category)` — analytics facets.
- `(recall_text_hash)` — dedup lookup.

---

## 3. New models (in `questions/models.py`)

### 3.1 `RecallSource`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField pk | |
| `pdf_filename` | CharField(255) | |
| `pdf_path` | CharField(512) | absolute |
| `pdf_sha256` | CharField(64) | full hex |
| `pdf_sha256_short` | CharField(16) | indexed |
| `pdf_size_bytes` | BigInteger | |
| `page_count` | Integer | |
| `page_start` | Integer | first page used (nullable) |
| `page_end` | Integer | last page used (nullable) |
| `question_count` | Integer | post-parse |
| `scan_type` | CharField(16) | `digital / scanned / hybrid` |
| `recall_status` | CharField(32) | `recall / coaching_compiled / official_compiled` |
| `publisher` | CharField(160) nullable | "Marrow / PrepLadder / Unknown" |
| `metadata` | JSONField | PDF metadata |
| `import_job` | FK → `QuestionImportJob` nullable | Phase 2 row that imported this source |
| `is_active` | BooleanField default True | |
| `created_at` | DateTimeField auto_now_add | |

Indexes: `(pdf_sha256_short)`, `(scan_type)`, `(recall_status)`.

Unique: `(pdf_sha256, page_start, page_end)` — same source imported twice with different page ranges is OK; identical (file, range) is not.

### 3.2 `QuestionSource`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField pk | |
| `question` | FK → `Question` (RESTRICT) | the canonical (or member) question |
| `recall_source` | FK → `RecallSource` (RESTRICT) | the source PDF |
| `page_number` | Integer | 1-indexed |
| `question_number_in_pdf` | Integer nullable | "Q.45" |
| `original_text` | TextField | raw extracted text |
| `extracted_text` | TextField | post-normalised |
| `ocr_confidence` | DecimalField(5,2) nullable | |
| `extraction_confidence` | DecimalField(4,3) | |
| `import_job_id` | CharField(64) nullable | Phase 1 runner id (string for portability) |
| `imported_at` | DateTimeField auto_now_add | |

Indexes: `(recall_source, page_number)`, `(question)`.

Unique: `(recall_source, page_number, question_number_in_pdf)` so the same source page can never claim the same question number twice.

### 3.3 `QuestionImage`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField pk | |
| `question` | FK → `Question` (RESTRICT) | |
| `recall_source` | FK → `RecallSource` nullable | null for non-recall images |
| `page_number` | Integer | source PDF page |
| `image_index_in_page` | Integer | sequence on the page |
| `file` | ImageField upload_to=`recall_images/%Y/%m/` | local storage; prod upload later |
| `mime` | CharField(32) | `image/png` etc. |
| `width` / `height` | Integer | px |
| `bytes` | BigInteger | |
| `sha256` | CharField(64) | full hex |
| `sha256_short` | CharField(16) | indexed |
| `phash` | CharField(16) | perceptual hash |
| `dhash` | CharField(16) | difference hash |
| `modality` | CharField(32) | `radiology / histopathology / gross_pathology / ecg / ct / mri / x_ray / ultrasound / clinical_photo / instrument / chart / flowchart / microbiology / slide / embryology / anatomy / biochem_pathway / dermatology / ophthalmology_fundus / other` |
| `modality_subtype` | CharField(64) nullable | "T1 MRI" / "H&E stain" / "12-lead ECG" |
| `body_region` | CharField(64) nullable | chest / abdomen / knee / fundus |
| `ocr_text` | TextField | text within image |
| `caption` | TextField | human-or-AI description |
| `caption_source` | CharField(32) | `in_pdf / ai_blip2 / ai_florence2 / human / none` |
| `ocr_confidence` | DecimalField(5,2) nullable | 0..100 |
| `extraction_confidence` | DecimalField(4,3) | 0..1 |
| `has_diagram` | BooleanField default False | |
| `has_table` | BooleanField default False | |
| `is_watermarked` | BooleanField default False | |
| `role` | CharField(16) | `primary / option / illustration / explanation` |
| `is_active` | BooleanField default True | |
| `created_at` | DateTimeField auto_now_add | |

Indexes: `(question)`, `(sha256_short)`, `(phash)`, `(modality)`.

### 3.4 `DuplicateCluster`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField pk | |
| `canonical_question` | FK → `Question` (RESTRICT) | |
| `similarity_threshold` | DecimalField(4,3) | 0..1 |
| `detection_method` | CharField(32) | `sha / rapidfuzz / embedding / image_hash` |
| `created_at` | DateTimeField auto_now_add | |

### 3.5 `DuplicateMember`

| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField pk | |
| `cluster` | FK → `DuplicateCluster` (CASCADE) | |
| `question` | FK → `Question` (RESTRICT) | the member question |
| `similarity_score` | DecimalField(4,3) | 0..1 |
| `created_at` | DateTimeField auto_now_add | |

Unique: `(cluster, question)`.

---

## 4. Migration file body (preview)

```python
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0022_question_is_disputed'),
    ]

    operations = [
        # 1. New fields on Question
        migrations.AddField(
            model_name='question',
            name='recall_status',
            field=models.CharField(
                choices=[
                    ('recall', 'Recall'),
                    ('coaching_compiled', 'Coaching Compiled'),
                    ('official_compiled', 'Official / Compiled'),
                ],
                default='official_compiled',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='question',
            name='question_type',
            field=models.CharField(
                choices=[
                    ('single_best', 'Single Best Answer'),
                    ('multiple_correct', 'Multiple Correct'),
                    ('assertion_reason', 'Assertion-Reason'),
                    ('match', 'Match the Following'),
                    ('image_based', 'Image-Based'),
                    ('numerical', 'Numerical'),
                ],
                default='single_best',
                max_length=32,
            ),
        ),
        # ... (rest of fields; see questions/models.py add)

        # 2. New indexes
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['recall_status'], name='ix_question_recall_status'),
        ),
        # ...

        # 3. New models
        migrations.CreateModel(
            name='RecallSource',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('pdf_filename', models.CharField(max_length=255)),
                ('pdf_path', models.CharField(max_length=512)),
                ('pdf_sha256', models.CharField(max_length=64)),
                ('pdf_sha256_short', models.CharField(max_length=16, db_index=True)),
                # ... etc.
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(name='QuestionSource', fields=[...]),
        migrations.CreateModel(name='QuestionImage', fields=[...]),
        migrations.CreateModel(name='DuplicateCluster', fields=[...]),
        migrations.CreateModel(name='DuplicateMember', fields=[...]),
    ]
```

(Actual implementation lives at [questions/migrations/0023_recall_neetpg_fields_and_models.py](../../backend/questions/migrations/0023_recall_neetpg_fields_and_models.py) — full file below.)

---

## 5. Safety checks

- All new fields have a default → no NOT NULL violation on existing rows.
- All new FKs are nullable or default-restrict with `on_delete=PROTECT` (we use `RESTRICT` for safety).
- The new migration only ADDS — it does not drop, rename, or alter existing columns.
- Existing indexes stay; new indexes are appended.
- `MEDIA_ROOT`/`MEDIA_URL` are reused — no new storage backend.
- No `python manage.py makemigrations` will detect drift because the migration is hand-authored.

---

## 6. Rollback strategy

- The migration is reversible. Each `AddField` and `CreateModel` has a corresponding reverse operation auto-generated.
- For production rollback we instead ship a `0024_revert_recall_neetpg` migration that drops the new tables + fields.
- **No data loss** — Question rows persist; only the new tables / fields are removed. QuestionImportJob rows created by the recall importer stay in place.

---

## 7. Test plan

1. `python manage.py makemigrations --check --dry-run` — must report "No changes detected".
2. `python manage.py migrate questions 0023` — must apply cleanly on the current SQLite db.
3. `python manage.py check` — must pass.
4. Existing tests: `python manage.py test questions.tests` — must remain green.
5. New unit tests in `questions/tests_recall.py`:
   - Create `RecallSource`, verify unique constraint.
   - Create `QuestionImage`, verify phash index works.
   - Round-trip a recall question via `QuestionSource`.
   - Soft-delete behaviour for `DuplicateMember`.

---

## 8. Out of scope (deliberately)

- We do not migrate the existing `Question.page_screenshot` data into `QuestionImage`. It stays as the primary slot.
- We do not change `Question.correct_answer` to a multi-value field — `multiple_correct` is encoded in `question_type` + `admin_answer_override` if needed.
- We do not introduce vector columns (`pgvector`) in this migration — that's a separate optional migration once we wire embeddings.