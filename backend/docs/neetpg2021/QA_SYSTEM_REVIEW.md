# QA SYSTEM REVIEW — current 3-rule gate

The current Stage 8 QA gate ([`stage_8_qa.py:32-33`](backend/mce/stages/stage_8_qa.py#L32)) is:

```python
PASS_THRESHOLD = 0.85
MAX_UNCLASSIFIED_BLOCKS = 2
IMAGE_MAPPING_THRESHOLD = 0.95   # implicit in line 230
```

A page PASSES only if **all three** rules hold simultaneously. Below, each rule is evaluated for correctness, fidelity, real-signal-vs-noise, and given a real page where it catches a real bug and a real page where it fires on harmless content.

---

## Rule 1 — `avg_question_reconstruction_confidence >= 0.85`

### Definition

Per page, compute the mean of `question_reconstruction_confidence` across all questions on that page. Page PASSES this rule iff the mean ≥ 0.85.

`question_reconstruction_confidence` is computed in [`stage_7_structured.py:267-273`](backend/mce/stages/stage_7_structured.py#L267):

```
recon = 0.40 * ocr_conf + 0.35 * layout_parts + 0.10 * img_conf - 0.05 * min(unclass, 4)
```

OCR confidence = 1.0 for digital text; `layout_parts ∈ {0, 0.25, 0.5, 0.55, 0.6, 0.7, 0.75, 0.85, 1.0}` depending on which of stem/options/answer/explanation are present; `img_conf = 1.0` for text-only or `min(per_image_extraction_confidence)` otherwise.

### Maximum possible recon for an image-based question

If `img_conf = 0.9` (template-match ceiling), `layout_parts = 1.0` (all four parts present), `ocr = 1.0`:
`recon_max = 0.40 + 0.35 + 0.09 = 0.84`.

If `img_conf = 0.9` and `layout_parts = 0.75` (no explanation):
`recon_max = 0.40 + 0.2625 + 0.09 = 0.7525`.

If `img_conf = 0.9` and `layout_parts = 1.0` *and* the page has even 1 unclassified orphan:
`recon = 0.84 - 0.05 = 0.79`.

**No image-based question can reach 0.85.** The threshold is mathematically unreachable when an image is involved.

### Does the rule reflect educational fidelity?

Yes for a *loose* definition of fidelity (all four parts present). No for a *strict* definition (a text+image clinical question that the student can use to learn from despite a missing explanation).

### What real failure does the rule prevent?

The rule would catch a case where:
- The OCR engine returns mostly blank text (`ocr_conf < 1`).
- The layout detector misses the options completely.
- Or a critical part of the question is silently dropped.

These are genuine student-blocking failures. But none of these failure modes exist on the 2021 PDF — `ocr_conf = 1.0` everywhere, and layout captures all of stem/options/answer for most pages.

### Real-signal vs noise

- **Real signal**: when a page truly has 0 explanations, 0 option-count in any question's `options` field. (Not present in this dataset.)
- **Noise**: when an image-based question has correct text + correct image but slightly low img_conf, the rule fires.

### Page where this rule catches a real bug

**`p130_q00`** ([`07_structured/p130.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p130.json)):
- `stem = "188. A 30 year old female with sterile Pyuria. Radiograph is shown. Diagnosis is MEDICAL JUNCTION TEAM"` — the footer `MEDICAL JUNCTION TEAM` is concatenated to the stem.
- `options = []` (empty).
- `answer_labels = []`.
- `layout_confidence = 0.25` (only stem typed, options/answer/explanation absent).
- `recon = 0.5875` — fails the rule.
- **This is a real extraction bug** — the question is stored with no options and no answer; a student clicking it sees only the stem-with-leakage and the image. The QA gate correctly flags this.

### Page where this rule fires on harmless content

**`p083_q00`** ([`07_structured/p083.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p083.json)) where `recon = 0.7125 < 0.85` ([overlay](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p083.png)):
- Q96 has stem + 4 options + answer + image. Explanation absent (matches `Answer: C` inline).
- The page-level `recon = 0.7125` is below the threshold only because layout is `0.75` (no explanation) — but the question is fully usable for student practice.

Verdict: **the rule is over-strict for image-based questions**. It conflates "image present" with "low fidelity" via the `0.10 * img_conf` slot, which mathematically caps image-Q confidence under 0.85 unless explanation is also present.

---

## Rule 2 — `unclassified_count <= 2`

### Definition

Stage 8 counts Stage 2's `type = "unclassified"` regions on a page that are NOT inside any question-block bbox. Page PASSES iff this orphan count ≤ 2.

Source: [`stage_8_qa.py:46-48`](backend/mce/stages/stage_8_qa.py#L46), [`stage_8_qa.py:174-187`](backend/mce/stages/stage_8_qa.py#L174).

### Does the rule reflect educational fidelity?

**No.** Educational fidelity cares about whether the question text is complete and the answer is correct; it doesn't care if a *continuation paragraph* or *page header* has been formally classified. A page can have 12 unclassified regions that are entirely "Anatomy subject header" + "MEDICAL-JUNCTION.COM" + continuation bullets — yet the question itself is intact and usable.

### What failure does the rule prevent?

It would catch a case where:
- Half of a question's content got left unclassified.
- A new question block was carved out of an unrelated paragraph.

These are real failures. But the rule is too coarse to catch them — 12 unclassified regions can be 100 % page furniture, or 100 % question content; the rule fires either way.

### Real-signal vs noise

- **Real signal**: ~30 pages where orphan regions are continuation paragraphs from a previous question (e.g. p21, p94, p111) — these signal that Stage 5 failed to sweep continuation text.
- **Noise**: ~50 pages where orphan regions are pure page furniture (headers, page numbers, footer, subject anchors) that don't impact the question at all.

### Page where this rule catches a real bug

**`p021`** ([overlay](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p021.png), [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"21".unclassified_count=16`):
- The page top has continuation bullets from Q27 ("Symptoms are due to the underproduction of red cells…"). These should logically be in the **previous** question's `explanation` field, not orphan.
- Q28's stem "28. HNPCC has defect in" is at the bottom — correctly captured as a block.
- The bug is that Stage 5 doesn't sweep the continuation paragraph into Q27's block, leaving it orphan. **The rule fires correctly here** — this is a real pipeline bug.

### Page where this rule fires on harmless content

**`p007`** ([overlay](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p007.png), [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"7".unclassified_count=4`):
- The page has Q9 (full), Q10 ("body fluid compartments" with `Na-10, K-140, Cl-15` lab values). The 4 unclassified regions are individual lab-value lines (`Na-10`, `K-140`, `Cl-15`, `values:` colon) that Stage 5 couldn't classify (because they lack a prefix). These were correctly *attached to Q10's stem region* (final stem reads "which showed the following values: Na-10 K-140 Cl-15 Name the fluid compartment."), but Stage 2 still counts them as unclassified.
- **The question is fully reconstructable from stem + options + answer.** Rule fires on harmless content.

Verdict: **the rule is over-strict** for pages where unclassified regions are continuation explanations or page furniture. It should be relaxed to "≤ 6" OR replaced with a semantic check that classifies orphan text as "continuation-or-furniture" vs "actual missing question content".

---

## Rule 3 — `avg_image_mapping_confidence >= 0.95`

### Definition

Per page, compute the mean of `image_mapping_confidence` across all questions on that page. Page PASSES iff mean ≥ 0.95.

`image_mapping_confidence` per question = `min(per_image.extraction_confidence for per_image in attached_image_ids)` or `1.0` for text-only.

Per-image `extraction_confidence` ceilings per placement method ([`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) and [`KNOWN_LIMITATIONS.md §2.1`](docs/neetpg2021/KNOWN_LIMITATIONS.md)):
- `template_match`: 0.9 ceiling
- `image_block_ordinal`: 0.6 ceiling
- `pixel_scan`: 0.5 ceiling
- `get_image_rects`: never returned ≥ 0.6 in this dataset.

**No image in this dataset has `extraction_confidence ≥ 0.95`.** Therefore **no image-based question in this dataset can reach `image_mapping_confidence ≥ 0.95`**.

### Does the rule reflect educational fidelity?

Only loosely. A clinically-correct image placed at template-match accuracy ± 5 px is educational-useful. The rule's "95 %" is a software-engineering target, not a student-outcome target.

### What real failure does the rule prevent?

A real failure this rule would catch is "image attached to the wrong question" or "image not attached at all" — both result in low image_mapping_confidence. But the *0.95* threshold catches these only when they're catastrophic. Lower-confidence misattachments (a question gets a 0.6 image when it should get a 0.9 one) would not be caught.

### Real-signal vs noise

- **Real signal**: pages where image placement is genuinely wrong (e.g. p67 — stem is null and the image attached is the right image but for the wrong question — but `img_mapping = 0.9` because the placement is correct). This case isn't actually flagged because the placement was successful.
- **Noise**: every image-based page in this dataset (the 0.95 threshold is unreachable due to template-match ceiling).

### Page where this rule catches a real bug

**`p003`** ([overlay](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p003.png), [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"3".avg_image_mapping_confidence=0.9`):
- Q4 has 4 attached images. Three are template-match (conf 0.9) and one is image_block_ordinal (conf 0.6). Question's `img_conf = min(0.9, 0.9, 0.9, 0.6) = 0.6`.
- Page-level is averaged with Q3 — gives 0.9.
- **Real bug**: the 4-image attach is itself a Stage 5 bug (L3 in PDF_LIMITATIONS) — page furniture images are attached. Even if all 4 were template-match, the rule would still fire (0.9 < 0.95). **The rule is mathematically incapable of passing on image-heavy questions.**

### Page where this rule fires on harmless content

**`p068`** ([overlay](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p068.png), [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"68".avg_image_mapping_confidence=0.9`):
- Q95 has a clinical radiology image of the knee, perfectly attached (visual inspection of the overlay shows the image inside the question block bbox), conf 0.9.
- Question text is fully correct. Student can use it.
- Rule fires because 0.9 < 0.95. **Pure noise**.

Verdict: **the rule is over-strict by at least 0.05 of the metric's theoretical maximum**. Either the threshold must drop to 0.85 (matching the recon threshold) or the per-image ceiling must rise to ~0.95+ via real placement metadata, neither of which the pipeline can do unilaterally.

---

## Composite verdict

The current 3-rule gate is correct in *intent* but **mathematically unreachable on this dataset** for two of the three rules:

| Rule | Mathematically reachable on this PDF? | Educational signal? | Verdict |
| --- | :---: | :---: | --- |
| recon ≥ 0.85 | **No** (image-Q math caps at 0.84) | Yes | **Over-strict** |
| unclassified ≤ 2 | Yes (some pages do pass it) | **Mixed** — fires on furniture | **Partially over-strict** |
| img_mapping ≥ 0.95 | **No** (template-match ceiling 0.9) | Yes | **Over-strict** |

### Recommendation

The QA gate cannot be passed on the 2021 PDF as constructed, regardless of how perfect the extraction is. It must either (a) be lowered to math-reachable thresholds (recon ≥ 0.80, img_mapping ≥ 0.85), or (b) be replaced with per-question semantic checks that measure educational fidelity directly.

See [PROPOSED_QA_V2.md](PROPOSED_QA_V2.md) for the proposed replacement.
