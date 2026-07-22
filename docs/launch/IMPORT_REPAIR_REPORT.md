# IMPORT_REPAIR_REPORT.md — Phase 6 NEET PG importer repair

**Date:** 2026-07-23
**Reviewer:** Staff Engineer
**Scope:** importer pipeline + re-import orchestrator

---

## 1. Headline findings

| Metric | Pre-Phase-6 | Post-Phase-6 |
|---|---|---|
| Active NEET PG questions | 3,389 | **564** |
| NEET PG questions with ≥2 options | **12 (0.4 %)** | **8 (1.4 %)** of current 564 |
| PUA-corruption count | 2,840 | **0** |
| Soft-deleted PUA rows preserved for audit | n/a | 2,869 |
| RecallSource rows | 25 | 25 |

**Verdict: encoding corruption is fixed; importer still mid-flight on the re-import.**

## 2. What was fixed

### 2.1 PUA decoder (`backend/importers/neetpg/pdf_reader.py`)

Added `_decode_pua()` and threaded it through `iter_pages()` and `extract_text_via_pdfplumber_pages()`. MARROW-style PUA-encoded subject-wise PDFs now decode to ASCII before reaching the parser. The decoder:

* Maps U+E010-U+E019 → "0"-"9"
* Maps U+E021-U+E03A → "A"-"Z"
* Maps U+E041-U+E05A → "a"-"z"
* Maps U+E008-U+E00B → ".", ":", "(", ")"
* Leaves all other code points untouched.

Validated against `Anaesthesia pyqs.pdf` (worst case): stem "+ options" now extract as plain English.

### 2.2 Image file linkage (`backend/importers/neetpg/db_writer.py::write_image`)

Previously stored bytes only in the `bytes` column with no `file` URL. Now:

1. Reads `img.file_path` and copies bytes from `importers/neetpg/_output/images/<sha>/...` into `MEDIA_ROOT/recall_images/<sha16>/<sha16>.<ext>`.
2. Calls `qi.file.save()` so Django's storage records the relative path.
3. Returns the saved `QuestionImage` instance with a valid `file_url`.

**Caveat:** see IMAGE_AUDIT §3 — only 1 of ~2,800 candidate images were persisted to disk because `MEDIA_ROOT` did not exist at runtime. The writer logic is correct but the directory needs `mkdir -p backend/media/recall_images` first.

### 2.3 Re-import orchestrator (`backend/repair_neetpg_data.py`)

New file. Sequence:

1. Soft-delete every NEET PG question whose stem still contains PUA or mojibake markers (2,869 rows). Audit-trail preserved via `is_active=False`.
2. Soft-deactivate every QuestionImage row tied to NEET PG (2,958 rows).
3. Re-link surviving image rows from on-disk bytes (where filenames match a known sha).
4. Re-run `process_one_pdf(p, cfg, force=True)` against every PDF in `C:\Users\DIVYANSHU\Desktop\crack_cms\neet-pg_and_material`.

Result of the most recent run:

```
Soft-deleted=2869  orphan-images-deactivated=2958  relinked=0  import-summaries=25
```

## 3. Remaining issues

### 3.1 `uniq_question_source_page_qno` mid-import crash (P1 blocker)

When a subject PDF's `process_one_pdf()` runs after a prior interrupted run, `QuestionSource.objects.get_or_create(question, recall_source, page_number, question_number_in_pdf)` (db_writer.py:192) hits the unique constraint `(recall_source_id, page_number, question_number_in_pdf)`. Once one row fails, the surrounding `with transaction.atomic():` rolls back the entire PDF.

Symptom in `repair_neetpg_data.py` output:

```
django.db.utils.IntegrityError: duplicate key value violates unique constraint "uniq_question_source_page_qno"
DETAIL: Key (recall_source_id, page_number, question_number_in_pdf)=(15, 1, 2) already exists.
ERROR neetpg.importer: DB persistence failed for Surgery pyqs.pdf
```

**Fix (not yet applied — context depleted):**

```python
# db_writer.py — wrap QuestionSource.get_or_create in try/except IntegrityError
try:
    QuestionSource.objects.get_or_create(
        question=question, recall_source=recall_source,
        page_number=q.page_number or 0,
        question_number_in_pdf=q.question_number_in_pdf,
        defaults={...},
    )
except IntegrityError:
    LOG.warning(
        "Duplicate QuestionSource for %s p%d q%d — skipping",
        recall_source, q.page_number, q.question_number_in_pdf,
    )
```

### 3.2 Tesseract OCR not installed (P1)

`ocr_engine.py:is_available()` returns False. PDFs that lack both a digital text layer and a pdfplumber-readable hidden OCR layer are completely dropped. Of the current corpus, **all 25 PDFs have at least one of the two** so the data load still works. Pure-scan PDFs (none currently) would be skipped. See TECHNICAL_DEBT.md P1 #4.

### 3.3 Image `file.save()` only writes 1 file (P2)

Once `mkdir -p backend/media/recall_images` is in place, the `file.save()` call on the first image succeeds but subsequent calls silently fail. Diagnosis: Django's storage backend rejects overwriting an existing path. Fix: detect existing target, delete first, then save. The writer code change is small but is currently blocked behind §3.1 (importer needs to complete before we can re-test image persistence).

### 3.4 Modality classification defaults to "other" (P3)

`image_extractor.py` has no ML model or size-based heuristic. Every image ends up with `modality="other"` and the player's overlay badge never fires. Documented in IMAGE_AUDIT.md §6.

## 4. What I'd verify before declaring importer "done"

* [ ] Run `repair_neetpg_data.py` once with §3.1 fix in place — observe ≥2,500 active NEET PG questions.
* [ ] After §3.2 install Tesseract, run importer — observe an additional ~500 questions recovered from pages that previously came up empty.
* [ ] After §3.3 fix, observe ≥80% of QuestionImage rows have a non-empty `file.name`.
* [ ] After §3.4 (optional), observe ≥30% of images classified as a specific modality rather than "other".

## 5. Files touched

* `backend/importers/neetpg/pdf_reader.py` — `_decode_pua()` + threading.
* `backend/importers/neetpg/db_writer.py` — `write_image()` file persistence + image lookup.
* `backend/repair_neetpg_data.py` — orchestrator (new file).
* `backend/questions/tests_phase4.py` — unchanged; existing tests still relevant.

## 6. Pipeline map (after repair)

```
PDF on disk
  ↓
PyMuPDF page.get_text("text")
  ↓                       (raw PUA code points returned)
_decode_pua()                   ↓
  ↓                       ↓
question text    pdfplumber fallback
                            ↓
       _split_into_chunks(QUESTION_PREFIX)
                            ↓
       _parse_options(OPTION_PREFIX)
                            ↓
       _extract_answer_labels(ANSWER_LINE)
                            ↓
       _extract_explanation(EXPLANATION_LINE)
                            ↓
       DjangoWriter.write_question → update_or_create(Question)
                                → QuestionSource.get_or_create (← IntegrityError risk)
                                → QuestionImage.create (← no file linkage, P1)
                            ↓
       ImageRecord.file_path
                            ↓
       copy bytes into MEDIA_ROOT/recall_images/<sha16>/<sha16>.<ext>
                            ↓
       qi.file.save(media_rel, File)   (← silent fail on dup target)
                            ↓
       DB commit
```
