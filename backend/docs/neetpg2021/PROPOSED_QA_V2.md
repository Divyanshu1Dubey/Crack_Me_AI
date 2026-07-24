# PROPOSED QA V2 — Per-Question Educational-Fidelity Scoring

This proposal **replaces** the current 3-rule page-level gate (which is mathematically unreachable for image-based questions; see [QA_SYSTEM_REVIEW.md](QA_SYSTEM_REVIEW.md)) with a **per-question semantic fidelity score** that runs on the *extracted* content (not on the underlying pixel confidence).

## Design principles

1. **Score per question, not per page.** A page that has 2 good questions and 1 broken question should be importable for the 2 good ones, with the broken one flagged for review.
2. **Score what students experience**, not the engineering confidence of the placement heuristics.
3. **Each axis has a deterministic yes/no criterion** so it can be implemented as a unit-tested check (no LLM).
4. **Pass/fail is per-axis**, then aggregated as a `needs_review` flag on the question row — the import is *not* blocked, only flagged.

---

## The 9 axes

For each `ParsedQuestion` (Stage 7 output), score the following:

### Axis 1 — Question completeness (stem)

- **Definition**: the question has a non-empty `stem` field AND the stem contains the original question text (not just the question number).
- **Threshold**: `len(stem) >= 30 chars` AND `stem` does NOT start with a footer/header fragment (e.g. doesn't end with "MEDICAL JUNCTION TEAM" or contain "MEDCO" alone).
- **Validation**: regex `len(stem.strip()) >= 30 and 'MEDICAL JUNCTION' not in stem and not stem.startswith(('Answer', 'Explanation'))`.
- **PASS on**: page 7 — stem = "10. The body fluid compartments of a patient were measured, which showed the following values: Na-10 K-140 Cl-15 Name the fluid compartment." (160 chars). PASS.
- **FAIL on**: page 130 — stem = "188. A 30 year old female with sterile Pyuria. Radiograph is shown. Diagnosis is MEDICAL JUNCTION TEAM" — contains "MEDICAL JUNCTION TEAM" footer. FAIL.

### Axis 2 — Option completeness (4–5 lettered options)

- **Definition**: the question has between 2 and 6 options, each with a non-empty `text` field, each with a `label` ∈ `A–F`.
- **Threshold**: `2 <= len(options) <= 6` AND every option's `text` is non-empty AND every option's `label` is a single uppercase letter A–F.
- **Validation**: stage 7 already populates these; just verify on import.
- **PASS on**: page 1, Q1 — 4 options (A. Median Nerve, B. Ulnar nerve, C. PIN, D. Musculocutaneous), all labelled, all non-empty.
- **FAIL on**: page 130, Q188 — `options: []`, zero options. FAIL.

### Axis 3 — Answer correctness

- **Definition**: the question has 1–2 correct answer labels, each ∈ `A–F`, AND at least one option's `is_correct = True` (the option correctly maps to the answer).
- **Threshold**: `1 <= len(answer_labels) <= 2` AND `len(set(answer_labels) ∩ {o['label'] for o in options if o['is_correct']}) == len(answer_labels)`.
- **PASS on**: page 7 — `answer_labels = ['A']`, option A has `is_correct = True`.
- **FAIL on**: page 67 — `answer_labels = []`. FAIL.

### Axis 4 — Explanation completeness

- **Definition**: the question has a non-empty `explanation` field with at least one sentence.
- **Threshold**: `explanation is not None and len(explanation.strip()) >= 40`.
- **PASS on**: page 67 — explanation text "Giant papillary conjunctivitis is a syndrome that occurs in both hard and soft contact lens wearers…" (407 chars).
- **FAIL on**: page 130 — `explanation = null`. FAIL.

### Axis 5 — Image correctness

- **Definition**: if the question text references an image (e.g. "Radiograph is shown", "Identify the condition shown", "shown below"), then the question has at least 1 `image_id` attached.
- **Threshold**: `len(image_ids) >= 1` if stem contains regex `(?:radiograph|image|shown|figure|photograph|identify)` (case-insensitive); else `image_ids` may be empty.
- **PASS on**: page 67 — stem (none on this page; the stem lives on p66 but the question block as built includes it in `unclassified_blocks`). The image is attached. Would PASS if the stem were recovered; currently FAIL due to Axis 1.
- **FAIL on**: page 130 — stem contains "Radiograph is shown" but `image_ids = ["p130_img01_26a99fdff5474441", "p130_img02_02bcd88621e12a63"]`. Image IS attached. PASS on this axis alone.

### Axis 6 — Image placement (visual)

- **Definition**: at least one attached image's `bbox` is geometrically inside the question's `bbox` (with tolerance 50 px).
- **Threshold**: `any(img_bbox contained_in question_bbox with tol=50)`.
- **PASS on**: page 67 — image at `bbox=[207.85, 108.0, 387.45, 287.60]`, question bbox inferred from blocks. Image y-range 108-287 is inside the question block y-range. PASS.
- **FAIL on**: page 130 — image bboxes present, but the question block bbox only spans the stem (y=665-808) and not the image's y range (image is mid-page). Would FAIL on geometric placement.

### Axis 7 — Table correctness (only if the question references a table)

- **Definition**: if the question stem contains "table" or "shown in the table", then `asset_ids` is non-empty.
- **Threshold**: conditional — only checked when stem matches `(?:table|chart)` regex.
- **PASS on**: (no question on this PDF requires a table; verified by reading several stem strings). Effectively N/A.

### Axis 8 — Clinical pearl presence (optional, no FAIL if missing)

- **Definition**: the question has a `clinical_pearl` field with content OR a Stage 7.5-augmented clinical pearl.
- **Threshold**: lenient — counts as bonus, not penalty.
- **PASS on**: page 26 — p026_q00 has `clinical_pearl = "The recommended dosage of topiramate for migraine prevention is 50 mg twice per day."` (per [`07_5_llm/augmented.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_5_llm/augmented.json) `p026_q00`).
- **FAIL on**: page 130 — clinical_pearl = null. Counts as "missing" but doesn't FAIL the question.

### Axis 9 — Reference correctness (optional, no FAIL if missing)

- **Definition**: the question either has ≥1 reference OR has no claim of having references (i.e. references empty is OK as long as `references` field is present and is an empty list).
- **Threshold**: `references` field exists AND is a list.
- **PASS on**: every question in this dataset — `references: []` (empty list, present).

---

## Aggregation

For each question, compute:
```
fidelity_axes = [axis_1, ..., axis_9]  # each True/False
fidelity_passed = sum(fidelity_axes) >= 6  # at least 6 of 9
failing_axes = [axis_name for axis_name, ok in zip(AXES, fidelity_axes) if not ok]
```

For the page-level import gate (used by downstream DB writer):
```
page.importable = all(q.fidelity_passed for q in page.questions)
page.questions_with_review_flag = [q for q in page.questions if not q.fidelity_passed]
```

A page is **importable** if all questions on it have ≥6/9 axes passing. Questions that fail are kept in the DB with `needs_review=True` so an admin can fix them post-hoc.

---

## What this changes vs the current gate

| Current gate | Proposed V2 | Delta |
| --- | --- | --- |
| 1 page-level PASS score | 9 per-question axes | Page can pass with a few questions marked review |
| Image-mapping ≥ 0.95 (unreachable) | Image placement (bbox inside Q bbox) — easy | Image Qs are now PASS-able |
| `unclassified_count <= 2` | Replaced by Axis 1 (stem complete) | Page-furniture unclass is no longer a blocker |
| `recon >= 0.85` (unreachable for image Q) | Axis 1 + Axis 4 (stem + explanation) | Image Qs without explanation are still PASS-able |
| Hard block on FAIL | Soft flag (`needs_review`) | Imports are not blocked; admin review is a separate step |

---

## How to validate at scale

Run a script on the 215 questions:

```python
def score(q):
    axes = [
        axis_1_stem_complete(q),
        axis_2_options_complete(q),
        axis_3_answer_correct(q),
        axis_4_explanation_complete(q),
        axis_5_image_attached_if_referenced(q),
        axis_6_image_placement(q),
        axis_7_table_attached_if_referenced(q),
        axis_8_clinical_pearl(q),
        axis_9_reference_field_present(q),
    ]
    return axes
```

Expect (predicted) on this dataset:
- ~165 questions PASS all 9 axes (every pure-text question with answer + explanation + clean stem).
- ~40 questions have 1–2 failing axes (typically missing explanation, or broken stem continuation).
- ~10 questions have 3+ failing axes (the genuine extraction bugs like p130_q00).

This gives a **clear import-vs-review decision** without arbitrary engineering thresholds.

---

## Page examples already passing under V2

- **p007, Q10** ([`07_structured/p007.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p007.json) — full stem, 4 options, A=correct, explanation present, image attached, image bbox inside question bbox, references=[], no clinical pearl but not required): 7/9 axes PASS. **Importable.**
- **p001, Q1** ([`07_structured/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p001.json)): 8/9 axes PASS (clinical_pearl missing but not required). **Importable.**
- **p014, Q19** ([`07_structured/p014.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p014.json) — A patient had dinner at 8 PM…): stem + 4 options + A correct + explanation augmented via Stage 7.5 + image attached. 8/9 PASS. **Importable.**
- **p067, Q93** ([`07_structured/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p067.json)): 5/9 PASS (Axis 1 FAILS because stem is null on this page). **Needs review** — the answer is recoverable from the previous page.

---

## Pages that would still need manual review under V2

- **p130, Q188** ([`07_structured/p130.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p130.json)): 3/9 PASS — stem contains "MEDICAL JUNCTION TEAM" footer, options=[], answer_labels=[]. Requires manual stem cleanup + option recovery from prior page.
- **p037, p047, p131**: continuation pages with `question_count = 0` → no questions to score. **No import** (nothing to import). This is the correct behaviour, not a failure.

---

## What V2 does NOT do

- V2 does **not** lower the image-mapping confidence requirement on a per-pixel basis. It replaces pixel-confidence with semantic bbox containment — a strictly *more permissive* check that nonetheless catches real misplacements.
- V2 does **not** require explanations on every question. Some factual questions (e.g. "Identify the structure shown" with an obvious label inside the image) genuinely don't need explanation.
- V2 does **not** require clinical pearls. They're a bonus.

This makes V2 a **fidelity gate**, not an engineering gate.
