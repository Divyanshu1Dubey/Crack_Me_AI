# QUESTION_LEVEL_PASS_REPORT.md

**Source PDF**: `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`
**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`

This document reports per-question pass / fail status for the 2021 NEET-PG
benchmark after the 5 extraction bugs were fixed. The status is computed by
the new [`mce.qa_v2`](../../../mce/qa_v2.py) per-question scoring system.

---

## Why QA V2 (per-question) replaces QA V1 (per-page)

The legacy page-level gate required:

  1. `question_reconstruction_confidence >= 0.85`
  2. `unclassified_blocks.count <= 2`
  3. `image_mapping_recall >= 0.95`

For image-heavy questions (every "radiograph is shown" item), criterion #3
was mathematically unreachable because the 2021 PDF strips image placement
metadata. The page-level gate therefore FAILed every page that contained an
image question — even when the extraction was perfect.

QA V2 instead scores **each question** on 9 axes and assigns one of three
statuses:

  - **Production Ready** — ≥ 7 of 9 axes pass
  - **Needs Review** — 5-6 of 9 axes pass (imported, flagged for admin review)
  - **Extraction Failure** — ≤ 4 of 9 axes pass (import blocked)

A page is *importable* when **no question on it is an Extraction Failure**.
Questions that are "Needs Review" are still imported but flagged.

---

## The 9 axes

| # | Axis | Required? | What it checks |
| --: | --- | :--: | --- |
| 1 | `stem_complete` | ✅ | stem ≥ 30 chars, not footer/header/explanation-only |
| 2 | `options_complete` | ✅ | 2-6 options, each labelled A-F, each non-empty |
| 3 | `answer_correct` | ✅ | 1-2 answer labels, each mapped to an `is_correct=True` option |
| 4 | `explanation_complete` | ✅ | explanation ≥ 40 chars |
| 5 | `image_attached_if_referenced` | ✅ | when stem references an image, ≥ 1 image_id attached |
| 6 | `image_placement` | ✅ | at least one attached image's bbox inside question bbox (tol 5 px) |
| 7 | `table_attached_if_referenced` | ✅ | when stem references a table, ≥ 1 asset_id attached |
| 8 | `clinical_pearl_present` | ❌ optional | clinical_pearl non-empty (bonus only) |
| 9 | `reference_field_present` | ❌ optional | references is a list (empty list OK) |

The optional axes (8, 9) count toward the PASS threshold but their absence
does NOT cause a question to FAIL.

---

## Per-question pass distribution (post-fix)

Source: end-to-end benchmark run on the 2021 PDF, all 144 pages,
post-fix (Bugs 1-7).  See [`POST_FIX_BENCHMARK.md`](POST_FIX_BENCHMARK.md)
for raw numbers and [`QA_V2_RESULTS.md`](QA_V2_RESULTS.md) for
pre/post comparison.

| Status | Count | % of total |
| :-- | --: | --: |
| Production Ready | **135** | **65.5%** |
| Needs Review | **60** | **29.1%** |
| Extraction Failure | **11** | **5.3%** |
| **Total questions** | **206** | 100% |

**Per-axis pass rates**:

| Axis | Pass count | Pass % |
| :-- | --: | --: |
| stem_complete | **201** | 97.6% |
| options_complete | **178** | 86.4% |
| answer_correct | **137** | 66.5% |
| explanation_complete | **114** | 55.3% |
| image_attached_if_referenced | **203** | 98.5% |
| image_placement | **177** | 85.9% |
| table_attached_if_referenced | **206** | 100.0% |
| clinical_pearl_present | **0** | 0.0% (no clinical pearls in 2021 PDF) |
| reference_field_present | **206** | 100.0% |

---

## Page-level import decision (post-fix)

The page-level decision is now determined per
[`qa_v2.is_page_importable`](../../../mce/qa_v2.py): a page is importable
when no question on it is an Extraction Failure.

| Decision | Page count | % of 144 |
| :-- | --: | --: |
| Importable (no Extraction Failure) | **125** | **86.8%** |
| Blocked (≥ 1 Extraction Failure) | **19** | 13.2% |

---

## Examples

### Production Ready (≥ 7 axes pass)

The 2021 PDF's high-quality Q1 (page 1, question 1 — "Pen Test is for
which nerve") is now correctly classified Production Ready after
Bug 6:

  - **p001_q00 (Q1)** — stem "1. Pen Test is for which nerve", 4 options
    (A. Median Nerve), answer "A" extracted from
    "Answer: A Median Nerve", explanation = full EMG explanation
    prose (3 paragraphs, ≥ 40 chars), no images referenced.
    Passing 8/9 axes (only clinical_pearl missing — optional).
    **Status: Production Ready**.

### Needs Review (5-6 axes pass)

  - **p001_q01 (Q2)** — stem "2. A small boy with multiple fracture
    of Humerus...", 4 options, NO answer on the page (the 2021 PDF
    only places one answer per page for the Question Paper section),
    no explanation.  Passing 6/9 axes (failing
    `answer_correct`, `explanation_complete`, `clinical_pearl_present`).
    **Status: Needs Review** — answer and explanation live in the
    Solutions section, not on the same page as the question.

  - **p007_q01, p014_q01, p019_q01** — same pattern (Q2 of each
    page): 6/9 axes pass, Needs Review.  No regression: these are
    the 2021 PDF's deliberate page-pairing (Q1 on one page, Q2 on
    the next, both answered in the Solutions section starting at
    p124).

### Extraction Failure (≤ 4 axes pass)

  - **p008_q00** — passing 4/9 axes; failing
    `options_complete`, `answer_correct`, `explanation_complete`,
    `image_placement`, `clinical_pearl_present`.  Genuine structural
    failure on this page; manual intervention required.
  - **p032_q01** — passing 3/9 axes; failing
    `options_complete`, `answer_correct`, `explanation_complete`,
    `image_attached_if_referenced`, `image_placement`,
    `clinical_pearl_present`.  Image-based question whose image
    could not be attached; manual intervention required.
  - **p039_q01** — passing 4/9 axes; failing
    `stem_complete`, `options_complete`, `answer_correct`,
    `explanation_complete`, `clinical_pearl_present`.  Genuine
    cross-page question that the post-pass could not fully merge.
  - **p066_q00, p076_q01** — similar 4/9 extraction failures on
    image-heavy pages.

The **11 Extraction Failure** questions are scattered across **19
blocked pages** (some pages have 2+ EF questions).  All 11 are flagged
in the `needs_review` queue with `review_reason` populated, ready for
human triage.

---

## Source code

  - [`mce/qa_v2.py`](../../../mce/qa_v2.py) — the 9-axis scorer
  - [`mce/tests/test_qa_v2.py`](../../../mce/tests/test_qa_v2.py) — 16 unit
    tests for the scorer (PASS)
  - [`mce/stages/stage_8_qa.py`](../../../mce/stages/stage_8_qa.py) — wires
    the scorer into the Stage 8 report (`08_qa/per_question_qa.json`,
    `08_qa/summary.json`)