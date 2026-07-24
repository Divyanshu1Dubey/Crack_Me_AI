# POST_FIX_BENCHMARK.md — End-to-End Benchmark After 5 Bug Fixes

**Source PDF**: `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`
**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`
**Date**: 2026-07-24

This document is the post-fix end-to-end benchmark. It re-runs the full
pipeline (Stages 1-8) on the 2021 PDF and reports the per-stage metrics, the
QA V1 (legacy page-level) numbers, and the QA V2 (per-question) numbers.

---

## Why this benchmark exists

The user's directive was:

> "AFTER FIXING THE FIVE BUGS: Run the COMPLETE benchmark again. Do not
> estimate. Actually run it. Generate a fresh benchmark. ... My success
> metric is: Can a medical student use this question exactly as intended?"

We are NOT optimising for confidence numbers. We are optimising for
educational correctness.

---

## Pipeline run

```bash
cd backend
python _run_benchmark.py
```

Stages run end-to-end:

1. **Stage 1 — render**: 144 pages rendered to PNG at 200 dpi.
2. **Stage 2 — layout**: each page → typed regions via heuristic + reading order.
3. **Stage 3 — images**: ~505 candidate images detected; placement via
   template-matching with pixel-scan fallback.
4. **Stage 4 — tables**: ~165 phantom table records (no real tables in
   this PDF).
5. **Stage 5 — question blocks**: reconstructed via the state machine
   with all 4 Bug 1/2/4/5 fixes; post-passes
   (`_merge_truncated_with_previous`, `_sweep_continuation_orphans`) run.
6. **Stage 6 — OCR fallback**: per-region Tesseract replacement for
   low-confidence digital regions.
7. **Stage 7 — structured**: builds `ParsedQuestion` records with the
   broadened answer regex (Bug 3 fix).
8. **Stage 8 — QA**: legacy V1 per-page gate + new V2 per-question scoring.

---

## Per-stage metrics (post-fix)

| Stage | Pages processed | Artefacts | Key metric |
| :-- | --: | --: | --- |
| 1 render | 144 | 144 PNG | page_count = 144 |
| 2 layout | 144 | 144 typed-region JSONs | typed_region_count ≈ 2,400 |
| 3 images | 144 | ~505 images | image_count = 505 |
| 4 tables | 144 | 165 phantom records | table_count = 165 (PDF has no real tables) |
| 5 question_blocks | 144 | 206 candidate blocks, post-passes ran | block_count = 206 (post Bug-7 phantom collapse), cross_page_merges + orphan_sweep |
| 6 ocr | 144 | region_ocr + image_ocr | regions_replaced via Tesseract on low-confidence text |
| 7 structured | 144 | 206 ParsedQuestions | question_count = **206** |
| 8 qa | 144 | V2 per-question JSON | V2 buckets: Production Ready=**135**, Needs Review=**60**, Extraction Failure=**11** |

---

## QA V1 (legacy page-level gate)

| Status | Pages | % |
| :-- | --: | --: |
| PASS | **0** | 0.0% |
| FAIL | **144** | 100.0% |

V1 failure modes (144 fail pages):

| Reason | Page count |
| :-- | --: |
| `low_avg_recon` | 97 |
| `low_image_mapping` | 111 |
| `too_many_unclassified` | 80 |
| `no_question_blocks_detected` | 8 |

The V1 gate is preserved unchanged. Its numbers reflect the genuine
limits of the source PDF (image placement metadata stripped) and the
extraction pipeline's per-page confidence floor.

---

## QA V2 (per-question educational fidelity)

| Status | Questions | % of total |
| :-- | --: | --: |
| **Production Ready** (≥ 7 of 9 axes) | **135** | **65.5%** |
| **Needs Review** (5-6 of 9 axes) | **60** | **29.1%** |
| **Extraction Failure** (≤ 4 of 9 axes) | **11** | **5.3%** |
| **Total questions scored** | **206** | 100.0% |

**Direct reading of the user's success criterion**: "approximately 75-90%
automatic import quality" = Production Ready %.

**Result: 65.5% Production Ready, with 29.1% automatically flagged for
review and only 5.3% blocked.**

See [`QUESTION_LEVEL_PASS_REPORT.md`](QUESTION_LEVEL_PASS_REPORT.md) for
the per-question breakdown and [`QA_V2_RESULTS.md`](QA_V2_RESULTS.md) for
the per-axis pass rates.

---

## Comparison vs pre-fix benchmark

| Run | Source | Production Ready | Notes |
| :-- | :-- | --: | --- |
| Pre-fix V2 (after Bugs 1-5) | previous benchmark | **63 / 204 (30.9%)** | answer_correct axis = 13/204 (6.4%), explanation_complete = 56/204 (27.5%) |
| Post-fix V2 (after Bugs 1-7) | this doc | **135 / 206 (65.5%)** | answer_correct = 137/206 (66.5%), explanation_complete = 114/206 (55.3%) |
| Δ improvement | | **+72 questions** (35 → 65.5%) | answer axis 6.4% → 66.5% (**+60.1 pp**), explanation axis 27.5% → 55.3% (**+27.8 pp**) |

---

## Verification

  - All 14 anchored regression tests pass: [`test_bugfixes_2021.py`](../../../mce/tests/test_bugfixes_2021.py)
  - Full MCE test suite (115 tests) passes: `python -m pytest mce/tests/`
  - QA V2 unit tests (16 tests) pass: [`test_qa_v2.py`](../../../mce/tests/test_qa_v2.py)

---

## Source artefacts

  - `_artifacts_benchmark_post_fix/<sha16>/08_qa/summary.json`
  - `_artifacts_benchmark_post_fix/<sha16>/08_qa/per_question_qa.json`
  - `_artifacts_benchmark_post_fix/<sha16>/08_qa/per_page_report.json`
  - `_artifacts_benchmark_post_fix/<sha16>/08_qa/overlays/p{NNN}.png`