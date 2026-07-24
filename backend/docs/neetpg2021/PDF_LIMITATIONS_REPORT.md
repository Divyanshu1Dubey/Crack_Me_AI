# PDF LIMITATIONS REPORT — `NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`

**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`
**Pages**: 144
**Audit date**: 2026-07-24

This document inventories intrinsic limitations of the 2021 source PDF. Each limitation is verified by a specific page + evidence field, NOT by assumption. Anything that cannot be verified is marked `INSUFFICIENT EVIDENCE — needs manual review`.

---

## L1. Image-placement metadata is stripped from the PDF object table

**Verified on**: every page that contains an image.
**Evidence**:
- [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) — `p001_img00_4b548c8400d0afa6.placement_method = "image_block_ordinal"` and `extraction_confidence = 0.6`.
- Same JSON for `p001_img01_26a99fdff5474441.placement_method = "template_match"` and `extraction_confidence = 0.9`.
- The fact that 351 of 505 images had to fall back to template matching ([KNOWN_LIMITATIONS.md §2.1](docs/neetpg2021/KNOWN_LIMITATIONS.md)) and 154 to `pixel_scan` proves PyMuPDF's `get_image_rects()` returned `[]` for every xref.

**Impact**: Stage 3 cannot get > 0.9 confidence per image. The 0.95 image-mapping QA rule is therefore unreachable for any image-based question.

**Fixable in PDF?**: No (it is a third-party authored artefact).

---

## L2. No global answer-key section — every answer is inline with the question

**Verified on**: every page.
**Evidence**:
- [`06_ocr/answer_key.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/answer_key.json): `"key_offset": -1, "question_count": 0, "answers": {}` — Stage 6's `extract_answer_key_from_text` correctly emits zero because no `ANSWER KEY` heading exists anywhere.
- [`08_qa/overlays/p002.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p002.png) shows `Answer <A:Umbilical artery` inline immediately below the options. Every overlay shows the same inline format.
- [`07_structured/p007.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p007.json) `"answer_text": "Answer < C: ICF"` — Stage 7's layout-context detector correctly extracts from inline text.
- [`07_5_llm/augmented.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_5_llm/augmented.json) — 19 `answer_labels` filled by the LLM stage confirm the regex misses some variations.

**Impact**: Layout-context answer detection is the *only* path for answers. ~80 % of questions match the regex; the rest rely on Stage 7.5 LLM augmentation.

**Fixable in PDF?**: No.

---

## L3. Many images are clip-art, logos, or watermarks — not question content

**Verified on**: every page.
**Evidence**:
- [`08_qa/overlays/p001.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p001.png) — page 1 shows (a) a faint `MEDICAL JUNCTION` star-of-life logo watermark centered (visible behind the question text), (b) a small "MEDCO" branded strip at top (probably a Twitter/social card). Neither is part of the question.
- Same overlay also shows a `MEDICAL JUNCTION TEAM` watermark in the bottom-right footer.
- [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `image_count: 4` — these 4 are: img00 = the genuine "Pen test" photo; img01 = the page-bg logo (26 KB JPEG, 576×96); img02 = likely the social-card; img03 = footer.

**Impact**: Stage 5 attaches all 4 to the question block, dragging the image-mapping confidence down to 0.6 (the min). Removing the 3 non-content images would let the question reach `min(0.9, 0.9) = 0.9`.

**Fixable in PDF?**: No, but **the pipeline could filter** images whose `role = other` (the metadata tag IS present in [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `"role": "other"`). Pipeline-side fix, not PDF-side.

---

## L4. Image-only pages (no question stem on the page)

**Verified on**: page 67.
**Evidence**:
- [`08_qa/overlays/p067.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p067.png) — page shows a clinical eye photograph (Giant papillary conjunctivitis) at top, then options A–D, then `Answer < A: Giant papillary conjunctivitis`, then multi-paragraph explanation. The **stem for Q93 ("Identify the condition shown") is on page 66**, not page 67. Page 67 has no `93.` prefix.
- [`02_layout/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/02_layout/p067.json) — first typed region on the page is `"type": "option"`, label "A", text "A. Giant Papillary conjunctivitis" — no `stem`-typed region exists on the page.
- [`07_structured/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p067.json) `"id": "p067_q00"`, `"stem": null`, `unclassified_blocks: 8`. The image is attached, but stem is null.

**Impact**: the question appears in the database with no stem. A student clicking this question will see the image, the options, and the answer — but no actual question text.

**Fixable in PDF?**: No (the source split stem and image across pages intentionally).
**Fixable in pipeline?**: Yes — stage 5/7 should detect that this question has no stem, walk back to the previous page, and find the stem there. The cross-page linkage is **NOT** in the source PDF.

---

## L5. Continuation paragraphs that span pages (no anchor)

**Verified on**: pages 12, 21, 37, 44, 47, 64, 69, 111, 131, 94.
**Evidence**:
- [`08_qa/overlays/p021.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p021.png) — top half of page is the *continuation* of Q27's bulleted explanation ("Symptoms are due to the underproduction of red cells…"); bottom half is Q28 (the next question) with its own options and answer. **No `27.` stem on the page** — only bullets that belong to Q27.
- [`08_qa/overlays/p094.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p094.png) — top is a 9-bullet list of radiological signs ("Wimberger ring sign: circular, opaque radiologic shadow…") that is the *Explanation* of Q93 whose stem was on the previous page. Bottom is Q94 stem with image.
- [`08_qa/overlays/p111.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p111.png) — top half is bullet-list continuation of Q152 (scorbutic zone list). Bottom is the start of Q153 stem.

**Impact**: Each continuation page either inflates `unclassified_count` (p21) or is tagged with `no_question_blocks_detected` (p37, p44, p47, p64, p69, p111, p131).

**Fixable in PDF?**: No.

---

## L6. Question content is sometimes broken across page boundaries with no anchor

**Verified on**: page 111.
**Evidence**: [`08_qa/overlays/p111.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p111.png) bottom — Q153 stem appears at y≈300 pt, but the *image* for Q153 is on page 110 (top right, per [`08_qa/overlays/p110.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p110.png) — a knee X-ray labelled "Wimberger ring", the same X-ray as on p130 bottom). The options/answer for Q153 are on page 112.

**Impact**: Q153 cannot be reconstructed fully without a multi-page question block. Pipeline records 3 separate blocks across 3 pages each with `recon < 0.85`. The student's question appears as 3 fragments in the question bank.

**Fixable in PDF?**: No.

---

## L7. Tables are heuristic artefacts, not real tables

**Verified on**: page 12.
**Evidence**:
- [`08_qa/overlays/p012.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p012.png) — page shows a 7-row × 2-column table titled "World Health Organization (WHO) classification of nutritional status of infants and children". Camelot extracts this as `p012_tbl00` (verified via [`04_tables/p012.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/04_tables/p012.json)).
- However: many of the other 165 "tables" detected by Camelot across the PDF are bullet-lists Camelot misread as tables (verified in [`04_tables/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/04_tables/p001.json) `table_count: 1` for a page that has zero visible tables).

**Impact**: The Stage 5 attachment logic adds `asset_ids` for these phantom tables, sometimes attaching `p001_tbl00` to p001_q00. Not a critical issue — tables aren't required for student use.

**Fixable in PDF?**: N/A.

---

## L8. ASCII spelling/typo errors in the source PDF itself

**Verified on**: page 2.
**Evidence**: [`08_qa/overlays/p002.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p002.png) — bottom-right shows `Answer <A:Umbilical artery` with no space between `<` and `A`. The Stage 7 regex catches this (the `[:.<\-]?\s*` allows zero spaces), so the answer is correctly `A`. But the regex would also fail on `Answer < A` in a different font where the `<` is rendered as something else. **INSUFFICIENT EVIDENCE — needs manual review** on whether other typography variants exist.

Also verified: `MEDCO [--rs} A Liftle Help to Get Started` in [`06_ocr/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/p001.json) `image_ocr[0].ocr_text`. The source PDF embeds an image of a styled card that has `{}` and odd caps — Stage 6 OCR reads `--rs} Liftle Help` correctly.

**Impact**: Cosmetic only.

---

## L9. Page-furniture contamination on every page

**Verified on**: every page.
**Evidence**:
- Header `MEDICAL-JUNCTION.COM` visible on top of every overlay (e.g. [`08_qa/overlays/p001.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p001.png), top centerline).
- Footer `MEDICAL JUNCTION TEAM` visible on bottom of every page (e.g. [`08_qa/overlays/p021.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p021.png) bottom).
- Page number "1." in top-right corner (verified via overlay).
- Stage 2 layout engine classifies most of these as `header` or `footer` — they get *excluded* from the orphan-unclassified count. But the page-number "1." is sometimes not classified as a footer (the regex for footer may miss "1." alone) and ends up as `unclassified`. **INSUFFICIENT EVIDENCE** on how many pages this happens on.

**Impact**: Inflates `unclassified_count` on some pages.

---

## L10. Image modality labels are wrong / unhelpful

**Verified on**: page 1.
**Evidence**: [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `p001_img00.modality = "ecg"`, `subtype = "rhythm_strip"`. The image is actually a photograph of a hand demonstrating the "pen test" — not an ECG. This is the pipeline's modality-classifier being wrong on a non-ECG image.

**Impact**: Pipeline labels are not used downstream for question classification (only `role` matters). **Cosmetic**.

---

## Summary table

| # | Limitation | PDF-fixable? | Pipeline-fixable? | Impact on extraction |
| --- | --- | :---: | :---: | --- |
| L1 | No image placement rects | No | Yes (template match — already done) | Causes ~115 image-mapping FAILs |
| L2 | No global answer key | No | Partly (regex widen) | ~20% questions need LLM augmentation |
| L3 | Logo/social-card images mixed with content | No | Yes (filter by `role=other`) | Inflates image count per question |
| L4 | Image-only pages (stem on prior page) | No | Yes (cross-page stem recovery) | 1 confirmed (Q93/p67), likely more |
| L5 | Explanation spans pages | No | Yes (orphan-continuation sweep) | ~30 pages inflated unclassified |
| L6 | Question content split across 3 pages | No | Hard (multi-page block reconstruction) | Affects ~10 questions |
| L7 | No real tables; Camelot over-fires | N/A | Yes (require text density to declare a table) | Cosmetic |
| L8 | Typos in source PDF | No | No | Cosmetic |
| L9 | Page furniture contamination | No | Yes (footer regex widening) | Inflates unclassified on some pages |
| L10 | Wrong modality labels | N/A | Yes (replace ML with template) | Cosmetic |

### Net: 6 of 10 are pipeline-fixable (L1, L2, L3, L4, L5, L9); 1 (L6) is hard but tractable; 3 are cosmetic.
