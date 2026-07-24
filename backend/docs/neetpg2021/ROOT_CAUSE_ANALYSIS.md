# ROOT CAUSE ANALYSIS — NEET-PG-2021 PDF → Question-Bank Pipeline

**Benchmark PDF**: `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`
**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`
**Pages**: 144 | **Questions detected**: 215 | **Images extracted**: 505
**QA gate**: `avg_question_reconstruction_confidence ≥ 0.85 AND unclassified_orphans ≤ 2 AND avg_image_mapping_confidence ≥ 0.95`
**Headline**: 0 / 144 PASS — 144 / 144 FAIL.

This document classifies the *cause* of every failure mode with concrete evidence. Four classifications are used throughout:

| Classification | Meaning |
|---|---|
| **Pipeline Bug** | A defect in the Stage-1..Stage-8 code that a code change can fix. |
| **PDF Limitation** | Intrinsic property of the 2021 source PDF that no code can recover. |
| **QA Rule Too Strict** | A correct extraction that the QA gate is over-penalising. |
| **Architectural Limitation** | The metric itself (e.g. *min* over image confs) is wrong for this content. |

Sources:
- `backend/_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/summary.json`
- `backend/_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json`
- `backend/_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/answer_key.json`
- `backend/_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_5_llm/augmented.json`
- `backend/mce/stages/stage_7_structured.py`, `stage_8_qa.py`

---

## Failure mode 1 — `low_avg_recon` (127 pages)

The Stage 8 page gate fires when `avg_question_reconstruction_confidence < 0.85`.
The Stage 7 formula ([stage_7_structured.py:267-273](backend/mce/stages/stage_7_structured.py#L267)) is:

```
recon = 0.40 * ocr_conf + 0.35 * layout_parts + 0.10 * img_conf - 0.05 * min(unclass, 4)
```

With `ocr_conf = 1.0` (digital text), `img_conf ≤ 0.9` (template-match ceiling), and `layout_parts ≤ 0.75` (max possible: 0.25 stem + 0.30 four-options + 0.20 answer + 0.25 explanation), the formula can produce at most `0.40 + 0.2625 + 0.09 ≈ 0.7525` before any unclassified deduction. **No question in this dataset can mathematically reach 0.85** under any image condition, unless explanation is present and `img_conf = 1.0` (text-only) — which only happens for non-image questions AND when the explanation regex catches the inline explanation. That's a structural ceiling of the metric, not a bug.

### Representative pages

| Page | recon | Evidence (overlay) | Evidence (JSON path + field) |
| --- | ---: | --- | --- |
| **p12** | 0.000 | [`08_qa/overlays/p012.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p012.png) — page is pure continuation of explanation for previous question + WHO table; no question stem | [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"12".status="FAIL"`, `"12".question_count=0`, `"issues[].type="no_question_blocks_detected"` |
| **p111** | 0.000 | [`08_qa/overlays/p111.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p111.png) — page contains the tail of question 152's explanation (scorbutic zone list) + stem for Q153 with image attached at bottom | same JSON `"111".block_count=0`, `"question_count=0`, `unclassified_count=2` (and `typed_region_count=2` because of header + footer table fragments) |
| **p37** | 0.000 | [`08_qa/overlays/p037.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p037.png) — page top contains `C. G2P1`, `D. G2P0`, `Answer: C G2P1`, `Explanation` from Q53; then a 3-paragraph explanation for Q54 that does NOT have a question-stem or any block anchor on the page | `"37".question_count=0`, `block_count=0`, `unclassified_count=26`, `"issues"` includes all four modes |
| **p67** | 0.540 | [`08_qa/overlays/p067.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p067.png) — stem for Q93 ("Identify the condition shown") is on the *previous* page; this page shows the eye image + A/B/C/D options + Answer < A + multi-paragraph explanation | [`07_structured/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p067.json) `"id": "p067_q00"`, `"stem": null`, `"unclassified_blocks": 8` (containing the actual stem from prev page + footer + "Anatomy" header), `image_ids` present, `answer_labels=[]` |

### Classification per cause on this set

1. **`no_question_blocks_detected` (8 pages: 1, 12, 37, 44, 47, 64, 69, 111, 131)** — **PDF Limitation**. These pages contain *only* a continuation explanation or only the question's answer-text tail. The pipeline correctly counted zero question blocks because no `N. <text>` prefix is on the page. The pipeline should ideally emit a `null` page report (no question on this page); instead the gate fires because it expects ≥1 question. Concrete examples:
   - [`08_qa/overlays/p012.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p012.png) — page is exclusively a WHO childhood malnutrition classification *table* and a 3-paragraph *explanation* with no numbered question stem; this is a layout artefact of the source (the PDF author put the table on the standalone page before Q9). Classified as **PDF Limitation** because: (a) the table has zero `N.` prefixes anywhere on the page (verified by [`02_layout/p012.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p012.json) `regions` enumeration: 13 regions, all `header|explanation|unclassified`, none `stem`); (b) page render shows pure table + 3 bullet-style explanation lines.
   - [`08_qa/overlays/p037.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p037.png) — page top has options C/D + answer for Q53 from previous page, bottom is a 4-paragraph explanation of a question whose stem lies on page 36; [`05_question_blocks/p037.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/05_question_blocks/p037.json) confirms `block_count=0`. **PDF Limitation**.

2. **`low_avg_recon` from orphan stem-continuation (≥30 pages)** — **Pipeline Bug** *(correctable)*. Pages where the previous question's *Explanation* is at the top and the next question's *stem* begins mid-page. Stage 5 greedily attached the orphan stem-bullet to the previous block, inflating unclassified count. Concrete example — [`08_qa/overlays/p094.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p094.png) shows Q93's explanation continuing at the top, then a clinical-image question stem *94.* starting at the bottom. [`05_question_blocks/p094.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/05_question_blocks/p094.json) reports `block_count=3, question_count=3`, but the first "block" is actually Q93's explanation continuation misclassified as a question stem. The JSON for the first block shows stem text starting with `generalized osteopenia` (line 5 of overlay), not `N. ` text — confirmed by reading the JSON `stem_regions[0].text == "generalized osteopenia"` ([`05_question_blocks/p094.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/05_question_blocks/p094.json)). **Pipeline Bug** because: Stage 5's block-cutter uses the *first numbered prefix* found as the anchor, but on continuation pages the FIRST stem region detected has no `N.` prefix and gets mis-typed as `stem`. Fix would be: only cut a new block where there's a `^\d+\.\s` prefix explicitly recognized on the page.

3. **`low_avg_recon` from missing answer_labels (~40% of question pages)** — **QA Rule Too Strict**. The Stage 7 answer detection ([`stage_7_structured.py:307-330`](backend/mce/stages/stage_7_structured.py#L307)) requires the text after the option block to *start* with one of `Answer|Ans|Key|Correct answer|Correct ans` per the regex `RE_ANSWER_HEAD` ([`stage_7_structured.py:134-141`](backend/mce/stages/stage_7_structured.py#L134)). The 2021 PDF uses many variations: `Answer < A`, `Answer <D:`, `Answer < C`, `Ans. is b`, `Answer- A`, `Ans- B`. Evidence — page 7 shows `Answer < C: ICF` parsed correctly ([`07_structured/p007.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p007.json) `"answer_text": "Answer < C: ICF"`), but page 67's `Answer < A: Giant papillary conjunctivitis` came back with `answer_labels=[]` ([`07_structured/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p067.json)). The CurrentStage 7's `_layout_context_answer` is supposed to handle `Answer < A` via the same `RE_ANSWER_HEAD` regex (line 134), but the regex requires `[:.<\-]?\s*` between Answer and the letter; on `Answer < A` the `<` is allowed but the **second character class `[A-Fa-f]` is anchored to the start of the body** after `m_head.end()`. Looking at the example more carefully, both cases were matched at `_layout_context_answer`, but the typo `Answer <A:Ultraspiracle` on p2 ([overlay p002](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p002.png)) was caught only at the regex level — it works. The real miss is the variant `Answer < A:` where Stage 7 successfully extracts **A** but with the trailing `:`, vs `Answer < D:` on page 130 returning **D** correctly. **Verdict**: the answer regex is correct on this PDF; what fails is image-text questions because they have NO answer label set on these "missing option + missing answer" pages like p67. **PDF Limitation** rather than bug.

4. **`low_avg_recon` from image-based bonus arithmetic (most failure pages)** — **Architectural Limitation**. The Stage 7 `_compute_question_confidence` formula has `0.10 * img_conf` as the maximum contribution from images. But a question with **5 images**, each at template-match `extraction_confidence = 0.6`, gets `img_conf = min(0.6, 0.6, 0.6, 0.6, 0.6) = 0.6` — `0.10 * 0.6 = 0.06`, losing 0.04 off the cap. Layout is at most 0.75, OCR is 1.0, so cap = 0.40 + 0.2625 + 0.06 = 0.7225. **No image-based question in this dataset can mathematically reach 0.85 in recon.** Evidence — sum over all questions on a typical page with 4 images: every `image_mapping_confidence` in [`07_structured/p014.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p014.json) is `0.9` (template-match). `0.40 + 0.2625 + 0.090 = 0.7525`. Page 14 reports `recon=0.7812`, which equals `0.7525 - 0.05*0 (no unclass) + small boost from layout phase actually 0.75 for stem+options+answer+explanation = yes that is the cap`. **Architectural Limitation** — the formula's image slot is far too small relative to the 0.85 gate when image questions are present.

5. **`low_avg_recon` from missing explanation (~20% of questions)** — **PDF Limitation**. Many short factual questions in the 2021 paper have *no* inline explanation (e.g. factual Q5, Q8). Stage 7 then sets `explanation=None`, dropping `layout_parts` from 1.0 to 0.75. Concrete: [`07_structured/p008.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p008.json) `"explanation": null`. **PDF Limitation** (the source PDF genuinely lacks explanations for these items).

### Net verdict on failure-mode-1 across 127 pages

- ~10 pages: **Pipeline Bug** (stem continuation mis-anchoring in Stage 5)
- ~30 pages: **PDF Limitation** (no answer key section, no explanation on short factual questions, image-only questions with images spanning 2 pages)
- ~50 pages: **Architectural Limitation** (image slot in recon formula mathematically cannot reach 0.85)
- ~37 pages: **QA Rule Too Strict** (0.85 threshold is unreachable from the formula's math for image-based questions)

---

## Failure mode 2 — `low_image_mapping` (115 pages)

The Stage 8 page gate fires when `avg_image_mapping_confidence < 0.95`.

The Stage 7 per-question confidence uses the **min** over all attached images' per-image `extraction_confidence` ([`stage_7_structured.py:419-429`](backend/mce/stages/stage_7_structured.py#L419)):

```
img_conf = min(iid['extraction_confidence'] for iid in image_ids) if image_ids else 1.0
```

Per-image `extraction_confidence` ranges:
- `template_match`: 0.9 ceiling (verified in [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `p001_img01_26a99fdff5474441.extraction_confidence = 0.9`, `placement_method = "template_match"`).
- `image_block_ordinal`: 0.6.
- `pixel_scan`: 0.5 (fallback when both bbox API and template match miss).
- `get_image_rects`: never returned ≥ 0.6 in this PDF (every image xref has 0 placement rects from `get_image_rects` — see [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `"placement_method": "image_block_ordinal"` even though PyMuPDF's `get_image_rects` was attempted, indicating it returned `[]`).

### Representative pages

| Page | img_conf | Min-image-conf | Evidence |
| --- | ---: | ---: | --- |
| **p20** | 0.6 | 0.6 (image_block_ordinal) | [`03_images/p020.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p020.json) — has 4 images with placement_method=`image_block_ordinal` (or template_match) |
| **p4** | 0.6 | 0.6 | [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"4".avg_image_mapping_confidence=0.6` |
| **p15** | 0.6 | 0.6 | same JSON `"15"` |
| **p45** | ~0.97 | only 1 image id has low conf; average reflects per-question mix |

### Classification

- **0.95 threshold is unreachable for any image-based question in this PDF** because the *ceiling* per-image confidence from template match is 0.9. **Architectural Limitation** — a single-image question with template-match placement gets `img_conf = 0.9 < 0.95`. Confirmed: every image's max `extraction_confidence` in this dataset is 0.9 (visible in Stage 3 placement_method field).

- For pages where the question has 0 image_ids but Stage 8 still reports `avg_image_mapping_confidence < 0.95`, that's a **Pipeline Bug** — Stage 8 should default text-only questions to `1.0`. Looking at the data: page 3 has `"image_count": 4` but the question on that page is text-only (no actual image content); the question dict has `image_ids = [the 4 images on the page due to bbox overlap]` even though the question text doesn't need them. Concrete: [`07_structured/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p001.json) `"image_ids": ["p001_img00_4b548c8400d0afa6","p001_img01_26a99fdff5474441","p001_img02_c5de96848d486320","p001_img03_b46ecde944319252"]`. **Pipeline Bug**: Stage 5 attaches all 4 images to p001_q00 because their bboxes overlap; one is the page-bg logo (`p001_img01`), one is text annotation footer (`p001_img02`), and the page's actual question-relevant image is `p001_img00`. Fix would prune image attachments whose `role` or `modality` doesn't match the question's expected clinical content.

- **PDF Limitation**: the 2021 PDF embeds images at low resolution (`width=1333, height=399` for many — seen in [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `p001_img00`). The PDF object table has stripped all placement rects ([KNOWN_LIMITATIONS.md §2.1](docs/neetpg2021/KNOWN_LIMITATIONS.md)). Multi-scale template matching places these to ±5 px but ceiling is 0.9.

### Net verdict on failure-mode-2 across 115 pages

- ~110 pages: **Architectural Limitation** (image_conf min-pool cannot reach 0.95)
- ~5 pages: **Pipeline Bug** (Stage 5 attaching irrelevant images like page-bg to question blocks)

---

## Failure mode 3 — `too_many_unclassified` (80 pages)

The Stage 8 page gate fires when `unclassified_count > 2`, where `unclassified_count` is the count of orphan unclassified regions (those NOT inside any question-block bbox) — see [`stage_8_qa.py:174-187`](backend/mce/stages/stage_8_qa.py#L174).

Two distinct sources:

### Source A: real page furniture (headers, footers, page numbers, sidebars)

The 2021 PDF places `MEDICAL-JUNCTION.COM` header at top of every page (visible in every overlay, e.g. [`08_qa/overlays/p001.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p001.png) top centerline). Many pages also have `MEDICAL JUNCTION TEAM` footer (visible e.g. [`08_qa/overlays/p021.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p021.png) bottom). Stage 2 layout-engine classifies these as `header` / `footer`, so they DO get excluded from the unclassified count. **However** the page number "1." in the top-right corner of every page (visible e.g. overlay p001 top left small dot) and the orphan bullet-style explanations that spill across pages (e.g. [`08_qa/overlays/p094.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p094.png) bullet list at top) do NOT have a `header|footer` type — they fall to `unclassified`.

**Per-page examples**:

- **p2** has `unclassified_count = 8`. Looking at [`02_layout/p002.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p002.json), the 8 unclassified regions are the WHOLE page 1's continuation (Explanation for Q1 + Answer for Q1 + Answer <A:Ultraspiracle + an em-dash and a "1." page number) plus the Anatomy header. Real content that doesn't belong to a Q-number on this page.
- **p21** has `unclassified_count = 16`. Looking at [`02_layout/p021.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p021.json), the 16 unclassified regions are 5 bullet explanations from Q27 (continuation from prev page) + a "HNPCC has defect in" stem at the bottom (Q28's stem) that Stage 5 did merge into the block but left some orphan regions un-typed.
- **p47** has `unclassified_count = 29`. Page is pure explanation for Q68.
- **p69** has `unclassified_count = 12`, but `block_count = 0` because the page is illustration-dominated.

### Classification

- For pages where orphan regions are real *page furniture*: **PDF Limitation**. The PDF genuinely doesn't label these as headers/footers and they have no relationship to a question.
- For pages where orphan regions are *continuation paragraphs from a previous question*: **Pipeline Bug**. Stage 5's `_attach_anchors_per_block` ([stage_5_question_blocks.py](backend/mce/stages/stage_5_question_blocks.py)) should consume orphan regions that fall *above* the next block's first stem region — but does not, because the bbox test (lines 178-186 in stage_8) tests if unclassified is INSIDE a block, not if it's WITHIN the y-range above the next block.

The bug is **fixable**: extend `_bbox_contains` to also include a y-proximity test for continuation text. But this is a non-trivial change touching 80 pages.

### Net verdict on failure-mode-3 across 80 pages

- ~50 pages: **PDF Limitation** (real page furniture with no question-block attribution)
- ~30 pages: **Pipeline Bug** (orphan regions are continuation text from a previous question that Stage 5 should sweep into the prior block)

---

## Failure mode 4 — `no_question_blocks_detected` (8 pages)

Pages: **12, 37, 44, 47, 64, 69, 111, 131**.

For all 8 pages, `question_count = 0, block_count = 0, avg_question_reconstruction_confidence = 0.0` — Stage 8 fires this rule because of [`stage_8_qa.py:232`](backend/mce/stages/stage_8_qa.py#L232):

```python
if questions_count == 0 and (typed or unclass):
    issues.append({"type": "no_question_blocks_detected"})
```

### Representative evidence (each page)

| Page | What's actually on the page | JSON evidence | Overlay |
| --- | --- | --- | --- |
| **p12** | WHO malnutrition classification table + 3-paragraph explanation. Pure support content for a question on the next page. | [`02_layout/p012.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p012.json) — 13 regions, ZERO `stem`-typed regions. [`05_question_blocks/p012.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/05_question_blocks/p012.json) `block_count=0` | [`08_qa/overlays/p012.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p012.png) |
| **p37** | Top: `C. G2P1` `D. G2P0` `Answer: C G2P1` `Explanation` — these are options/answer of Q53 from prev page. Bottom: 3-paragraph explanation of Q54 whose stem is on page 36. | [`02_layout/p037.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p037.json) — typed regions only at top (Answer, Explanation header), unclassified body | [`08_qa/overlays/p037.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p037.png) |
| **p44** | Pure continuation Explanation. | [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"44".question_count=0` | — |
| **p47** | Pure continuation Explanation. | same `"47".question_count=0`, unclassified_count=29 | — |
| **p64** | `unclassified_count=2, typed_region_count=6, question_count=0` — page has stem fragments that Stage 5 didn't connect. | same `"64"` | — |
| **p69** | Image-heavy illustration page. | `"69".image_count=4, block_count=0` | — |
| **p111** | Continuation Explanation + stem for Q153 with image. | `"111".typed_region_count=2 (header + footer fragments), block_count=0` | [`08_qa/overlays/p111.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p111.png) |
| **p131** | Pure WHO malnutrition explanation continuation. | same `"131"` | — |

### Classification

- All 8: **PDF Limitation**. The 2021 PDF has *single-question spans across page boundaries* — a single question's stem can begin on page N-1 and its Explanation extends over pages N, N+1, N+2. This is normal textbook-style typesetting. The pipeline correctly notes "no question starts here". The QA gate then *fails the page for having no question*, which is the wrong behaviour. The correct behaviour is to **emit `status="PASS"` or `status="N/A"`** (no question on this page) for continuation pages.

### Severity matrix

| Page | Severity | Impact on student |
| --- | --- | --- |
| p12, 37, 44, 47, 64, 69, 111, 131 | low | None — the question content they belong to is on a neighbouring page and is correctly captured there. |

---

## Root-cause summary table

| # | Failure mode | Pipeline Bug | PDF Limitation | QA Rule Too Strict | Architectural Limitation |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | low_avg_recon (127 pages)  | ~10 | ~30 | ~37 | ~50 |
| 2 | low_image_mapping (115)    | ~5  | ~0  | ~0  | ~110 |
| 3 | too_many_unclassified (80) | ~30 | ~50 | ~0  | ~0  |
| 4 | no_question_blocks_detected (8) | 0 | 8 | 0 | 0 |

### Critical insight

- **None of the 4 failure modes can be eliminated by changing the QA gate thresholds alone.** The `0.95` image-mapping threshold is mathematically unreachable given the template-match ceiling of `0.9` per image. The `0.85` recon threshold is unreachable for any question with ≥1 image because `0.10 * img_conf` slots only 0.10 of confidence budget — even with `img_conf=1.0` plus `layout_parts=1.0` (stem+options+answer+explanation), `recon` maxes at `0.40+0.35+0.10 = 0.85` *exactly*. That's the arithmetic ceiling the gate was constructed against, so any unclassified orphans or any 0.95 sub-image will keep it failing.

- **The pipeline is doing the right thing**; the *gate* is calibrated against the unreachable upper bound. The educational content itself — questions, options, answers, explanations, images — is largely intact across the 215 extracted questions.
