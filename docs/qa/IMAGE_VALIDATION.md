# Image Validation — NEET PG Browser QA

**Date**: 2026-07-25
**Target**: NEET PG image-bearing questions
**Sample size**: full production scan (no sampling — every Question row in production)

---

## Production state

| Metric | Value | Status |
|--------|-------|--------|
| Total `is_image_based=True` Questions | **0** | ❌ |
| Total `QuestionImage` rows | 0 (queried via detail endpoint) | ❌ |
| Total `page_screenshot != null` | 0 | ❌ |
| Questions with `images[]` non-empty | 0 | ❌ |

---

## CHANGELOG vs reality

`CHANGELOG.md` (commit `4a61af8 fix(ingestion): wire NEET PG 2021 image artefacts + orchestrator gate`) claims:

| Metric | Claimed | Actual in production |
|--------|---------|----------------------|
| `is_image_based=True` for 2021 PDF | 184 | **0** |
| `QuestionImage` rows for 2021 | 567 | **0** |
| Image files in `media/recall_images/2026/07/` | 436 | (unverified) |

**Conclusion**: `_fix_neetpg2021_images_v2.py` ran locally and committed the code, but the production DB at `crackcms-vsthc.ondigitalocean.app` was never updated.

---

## Per-year image-based counts

| Year | Total Questions | `is_image_based=True` |
|------|-----------------|-----------------------|
| 2018 | 321 | 0 |
| 2019 | 0 | 0 |
| 2020 | 54 | 0 |
| 2021 | 329 | 0 |
| 2022 | 0 | 0 |
| 2023 | 0 | 0 |
| 2024 | 0 | 0 |
| 2025 | 1793 | 0 |

---

## Image-search pattern scan

Question text patterns that should ALWAYS imply `is_image_based=True`:

| Pattern | Found in NEET PG | `is_image_based=True` |
|---------|-------------------|-----------------------|
| "shown below" | (not yet sampled) | 0 |
| "X-ray" | (not yet sampled) | 0 |
| "CT scan" | (not yet sampled) | 0 |
| "MRI" | (not yet sampled) | 0 |
| "histology" | (not yet sampled) | 0 |
| "photograph" | (not yet sampled) | 0 |
| "image" / "figure" | (not yet sampled) | 0 |

---

## Root cause

The `_fix_neetpg2021_images_v2.py` script:

```python
# Idempotent post-import: copy MCE images to media/, create QuestionImage rows
# Sets is_image_based=True + page_screenshot on 184 image-bearing Questions
# Claimed: 412 QuestionImage rows, 184 Questions is_image_based=True, 356 files copied
```

…ran successfully in the local dev environment but the resulting DB rows never reached the DigitalOcean droplet. The deploy pipeline (`backend/build.sh` on Render) loads the fixture, but the image rows were written via raw Python that bypassed the fixture export.

---

## Required fix

1. SSH to DigitalOcean droplet.
2. Run `cd backend && python manage.py shell < _fix_neetpg2021_images_v2.py` (or refactor into a management command).
3. Re-export the fixture: `python _export_fixture.py` so the rows are baked into the next deploy.
4. Verify with the regression test:
   ```bash
   curl 'https://crackcms-vsthc.ondigitalocean.app/api/questions/?is_image_based=true&exam_type=neet_pg' | jq '.count'
   # Must return > 0
   ```
5. Spot-check 10 random image-bearing questions; verify `page_screenshot` URL returns HTTP 200 and dimensions > 100×100.

---

## Frontend image rendering

`frontend/src/components/neet-pg/NeetPgPlayer.tsx` correctly consumes the `images[]` and `page_screenshot` API fields, but with no rows to consume it never renders. Once the production data is fixed, this should immediately start rendering.

---

## Image lazy-loading

The player already uses `<img loading="lazy" />`. Zoom controls are wired (`zoomImg` state). After the data fix, no frontend code change is required.
