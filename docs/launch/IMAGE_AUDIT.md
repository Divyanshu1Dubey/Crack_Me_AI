# IMAGE_AUDIT.md — Phase 6 NEET PG image pipeline audit

**Date:** 2026-07-23
**Reviewer:** Staff Engineer
**Scope:** every QuestionImage row, image bytes, storage link, API exposure, frontend rendering

---

## 1. Headline findings

| Metric | Pre-Phase-6 | Post-Phase-6 (this commit) |
|---|---|---|
| `QuestionImage` rows (NEET PG) | 2,958 | 2,959 |
| Rows with `file` field set | **0 (broken)** | **1 (broken — see §3)** |
| Bytes stored in `bytes` column | ~150 MB | ~150 MB |
| Files actually on disk under `MEDIA_ROOT/recall_images/` | 0 | **1** |
| Distinct sha256_short values | ~2,800 | ~2,800 |
| Modality-classified rows | 0 | 0 (modality defaults to "other") |
| Images with OCR text | 0 | 0 (no Tesseract installed) |

**Verdict: image pipeline is still broken.** The previous Phase-5 audit claimed "images extracted and stored", which was technically true (bytes column populated) but practically false (no file URL exposed to the browser).

## 2. Root cause

### 2.1 Bytes were extracted to `importers/neetpg/_output/images/<sha>/...` but never copied to `MEDIA_ROOT`

`image_extractor.py::extract_embedded()` (line 80) writes the raw bytes to `out_dir / fname` — the importer's scratch directory. It populates an `ImageRecord.file_path` field. But `db_writer.py::write_image()` never reads `img.file_path` and never sets the `file` ImageField. The Phase-2 commit landed the model with a `file` ImageField but no writer code to populate it.

### 2.2 No idempotency check on duplicate-image ingest

When two PDFs share an image (e.g. a question appearing in two recall sources), the writer's `existing = QuestionImage.objects.filter(sha256_short=...).first()` (line 229) does dedup, but the candidate image hasn't been linked to the question yet — so the dedup just returns an orphan row that no question references.

### 2.3 Frontend has no way to render the bytes

`QuestionImageSerializer.file_url` (recall_serializers.py:23) returns `obj.file.url` only when `obj.file` is set. With `file` always empty, every frontend image render falls back to the empty-state icon. The `QuestionListSerializer` does not include images at all — the practice page has to call `/questions/{id}/images/` separately, which it does (correct), but the response is always empty `[]`.

## 3. What was fixed in Phase 6

* **Edited** `importers/neetpg/pdf_reader.py` — added `_decode_pua()` so any image-mapped text from a PUA font still decodes to ASCII (this is unrelated to images but matters for image `caption` extraction).
* **Edited** `importers/neetpg/db_writer.py::write_image()` — now copies the on-disk bytes from `img.file_path` into `MEDIA_ROOT/recall_images/<sha16>/<sha16>.<ext>` and calls `qi.file.save(...)` to register the path with Django's storage.

**Result of the partial run:** the writer only wrote 1 file out of ~2,800 candidates. Two failures observed:

* `MEDIA_ROOT` (`backend/media/`) was missing — Django didn't auto-create it. Fix: `mkdir -p backend/media/recall_images` before the run. **Documented as a pre-req below.**
* The `file.save(name, File(f))` call silently swallows a `SuspiciousFileOperation` when the destination path already exists in storage. Fix: check `qi.file.name` before save; idempotent overwrite requires deleting first.

## 4. Pre-reqs to actually serve images in production

1. `mkdir -p backend/media/recall_images/` (deploy-time). Production uses Render's persistent disk — must exist before any image write.
2. Configure `MEDIA_URL` + `MEDIA_ROOT` to be served. Currently `if settings.DEBUG: urlpatterns += static(...)` — production needs `whitenoise` or a CDN pointing at `MEDIA_ROOT`.
3. Install Tesseract OCR (TECHNICAL_DEBT.md P1 #4) so `image_extractor.py` can populate `ocr_text` for question stems that *describe* the figure.

## 5. Frontend rendering — what's correct vs broken

| Concern | Status | Notes |
|---|---|---|
| `<img src={file_url} loading="lazy">` in player | ✓ correct code | Backend currently returns `null` for every image; component shows `<ImageIcon />` empty state. |
| Fullscreen zoom (desktop) | ✓ correct code | Click image → modal at z-50; click backdrop → close. |
| Mobile pinch zoom | ✓ works natively | Modal `<img>` honours browser default `user-zoom`. No `user-scalable=no` in viewport meta. |
| Modality badge (`X-Ray`, `CT`, `ECG`) overlay | ⚠ partial | `modality` defaults to `"other"` so badge never renders. Needs classifier on extraction. |
| Skeleton / loading state | ✓ implemented | `<ImageIcon />` icon while bytes load. |
| Fallback if image missing | ✓ implemented | Empty-state icon. |
| `alt` text for a11y | ✓ implemented | Falls back to "Question N image" when `caption` is empty. |

## 6. P1 issues to ship before launch

1. **Make the writer idempotent on the `file` save call** — re-running the same image currently fails silently. Wrap in `try/except` and skip.
2. **Fix the unique-violation on `QuestionSource` for re-runs** — `force=True` re-import hits `uniq_question_source_page_qno` when only some questions from a PDF were ingested before a previous crash. Add `IntegrityError` catch + skip in `db_writer.write_question()`.
3. **Run `mkdir -p backend/media/recall_images` once** before invoking the importer.
4. **Replace `modality='other'` default with a classifier** — at minimum, classify PNG vs JPEG, and use the file-size heuristic (large → likely X-Ray, small → likely diagram).

## 7. What I'd verify before declaring image-pipeline "done"

* [ ] Every QuestionImage row has a non-empty `file.name`.
* [ ] Every `file.name` resolves to a real file under `MEDIA_ROOT`.
* [ ] `GET /api/questions/{id}/images/` returns ≥1 image for image-based questions.
* [ ] `curl http://.../media/recall_images/<sha>.<ext>` returns 200.
* [ ] Lazy-loaded `<img>` on the player shows the image (not the empty-state icon) for at least 3 sampled image-based questions.
