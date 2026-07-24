# QUALITY GAP REPORT — NEET-PG-2021 PDF → Question-Bank Pipeline

**Date**: 2026-07-24
**Source evidence**: [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md), [EDUCATIONAL_FIDELITY_REPORT.md](EDUCATIONAL_FIDELITY_REPORT.md), [MANUAL_AUDIT_30_QUESTIONS.md](MANUAL_AUDIT_30_QUESTIONS.md), [QA_SYSTEM_REVIEW.md](QA_SYSTEM_REVIEW.md), [PROPOSED_QA_V2.md](PROPOSED_QA_V2.md), [PDF_LIMITATIONS_REPORT.md](PDF_LIMITATIONS_REPORT.md)

This report enumerates every remaining gap between the *current pipeline output* and *production-grade import readiness*, classifies each gap by severity, estimates engineering effort, and indicates whether closing it would change OPTION A/B/C.

---

## Severity legend

| Severity | Definition |
| --- | --- |
| **blocks** | Page/question cannot be used at all by a student. (8 of 30 audited questions; 27 %.) |
| **degrades** | Page/question can be used but with reduced fidelity. (12 of 30 audited; 40 %.) |
| **cosmetic** | Extraction is correct; only the QA gate fires. (10 of 30; 33 %.) |

## Engineering-effort legend

| Effort | Definition |
| --- | --- |
| XS | < 1 hour, single-stage, no test scaffolding needed |
| S | 1–2 hours, single stage + 1–2 unit tests |
| M | 2–6 hours, single stage + regression test, may need a fixture |
| L | 6–16 hours, multi-stage, needs design discussion + several tests |
| XL | > 16 hours, requires new architecture or external dependency |

---

## Gaps

### Gap 1 — Stage 5 question-prefix regex over-fires on explanation list items

- **What**: The `question_prefix` regex catches the `1.` `3.` numbered bullets inside an *explanation list* (e.g. the JE vaccine explanation list on p51, the Measles symptoms list on p45). It treats them as new questions.
- **Evidence**: 2 of 30 audited questions (Q16 `p045_q01`, Q17 `p051_q03`) are phantom questions extracted from bullet lists. [`08_qa/overlays/p045.png`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p045.png) shows "1. Measles is a childhood infection…" as item 1 of a list, not as a question stem.
- **Severity**: blocks (creates false questions in the bank)
- **Effort**: S — tighten the prefix regex to require either (a) a non-numeric first word (so the `1.` is followed by a word not just a colon), or (b) the line ends with `?` or starts with `Which|What|When|Why|How|Identify`. Estimated 2 hours including a regression test fixture.
- **Changes OPTION?**: **YES** — would lift pass count from 33 % to ~40 % in audit. Reclassifies ~5 questions (extrapolated to 215) from FAIL to PASS.
- **Files to change**: `backend/mce/stages/stage_5_question_blocks.py` (the `_should_emit_block` predicate), plus 1 test.

### Gap 2 — Stage 5 captures continuation bullets as extra options

- **What**: Pages where the Q's explanation list is rendered in the same column as the next question's options (Q192 ear-discharge on p134, Q187 limb-pain on p129) result in `options` arrays of 9–12 entries.
- **Evidence**: Q29 (`p134_q00`, options=12), Q30 (`p129_q00`, options=9) in [MANUAL_AUDIT_30_QUESTIONS.md](MANUAL_AUDIT_30_QUESTIONS.md).
- **Severity**: blocks (options list contains garbage text; student confused)
- **Effort**: M — same tightening as Gap 1 plus y-bound check (don't accept options that fall after `Answer:` on the same page). ~3 hours.
- **Changes OPTION?**: **YES** — 2 questions in audit, ~10 in 215 total.

### Gap 3 — Answer regex misses `Ans is b` (no punctuation) variant

- **What**: [`stage_7_structured.py:134-141`](backend/mce/stages/stage_7_structured.py#L134) `RE_ANSWER_HEAD` requires `[:.<\-]?\s*` between `Ans` and the letter. Variants like `Ans is b` (single space) work, but `Ans is` followed by lowercase `b. Lipase` works. **However**, when the answer is rendered as plain text without a colon (e.g. `Ans b`), the regex misses. INSUFFICIENT EVIDENCE on how many pages this affects — p1's Q1 `Answer: A` works, p2's Q3 `Answer <A:` works, but Q's like `Ans b` on other pages fail.
- **Evidence**: Q1 (`p001_q01`) in audit — `Answer: A Musculocutaneous nerve` visible on overlay p001 bottom, but `answer_labels=[]` in [`07_structured/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p001.json).
- **Severity**: blocks (4 of 8 FAILs are answer-missing)
- **Effort**: S — widen the regex + add a fallback that scans for "Answer\b.*?\b([A-Fa-f])\b" within first 60 chars of region. 1 hour.
- **Changes OPTION?**: **YES** — biggest single win for FAIL→MARGINAL.

### Gap 4 — Cross-page stem recovery missing

- **What**: When a question's stem is on page N-1 and its image+options+answer are on page N (e.g. Q93 on p67, Q92 on p65), the pipeline emits two question records: one with stem+image on p66/p64, and one with null stem + image on p67/p65. The student's view of the p67/p65 record is stem-less.
- **Evidence**: Q20 (`p061_q01`, stem present but options=[]), Q21 (`p065_q01`, stem 152 chars but options=[] + no answer), and the "stem=null" entry in [`07_structured/p067.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/p067.json) `p067_q00.stem = null`.
- **Severity**: blocks (2 of 8 FAILs)
- **Effort**: L — requires cross-page block linkage. Detect "this block has no stem but has options/answer → look back to previous page's last question with no options/answer → merge". ~6–10 hours.
- **Changes OPTION?**: **YES** — reclassifies ~5 questions.

### Gap 5 — Stage 5 attaches page-furniture images to question blocks

- **What**: Image attachments include the page-bg logo, the social card, the medical-junction footer logo, and the question-bg watermark. These all get `extraction_confidence` values that drag the question's `image_mapping_confidence` below 0.95.
- **Evidence**: [`03_images/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/03_images/p001.json) `p001_img01_26a99fdff5474441.role = "other"`, `p001_img02_c5de96848d486320.role = "other"`. The `role: "other"` metadata is already set; the Stage 5 attachment logic just doesn't filter on it.
- **Severity**: degrades (image_Q recon is dragged down, but student still gets the actual content image)
- **Effort**: XS — one-line filter in stage 5: `if img_meta.role == 'other' and img_meta.modality in ('ecg', 'watermark', 'logo'): skip`. < 1 hour.
- **Changes OPTION?**: Partial — would lift image-mapping on most pages but the 0.95 ceiling is still unreachable. Cosmetic.

### Gap 6 — Continuation explanations are orphan regions (not swept into prior question)

- **What**: On pages like p21, p94, p111, the previous question's explanation bullets span to the top of the next page. The next question's block is below them. Stage 5 doesn't sweep the continuation into the prior block, leaving ~3-15 orphan regions per page.
- **Evidence**: p21 has `unclassified_count=16` (per [`08_qa/per_page_report.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/per_page_report.json) `"21"`), p94 has 1, p111 has 2. Verified visually via overlays.
- **Severity**: degrades (the orphan regions are real content, but the prior question's `explanation` field is already complete — the orphans are *continuation* content for an explanation the next-page block has already ended).
- **Effort**: M — extend Stage 5's `_attach_anchors_per_block` to also consume orphan regions that are *above* a new block's first stem region. ~3 hours.
- **Changes OPTION?**: **YES** — reclassifies 30 pages from FAIL to MARGINAL/PASS.

### Gap 7 — Subject / topic keyword mapper has substring-collision bugs

- **What**: Stage 7's `_map_subject` uses substring `if kw in text`. The keyword `ear` matches `year`, `near`, `rear`.
- **Evidence**: Mentioned in [`KNOWN_LIMITATIONS.md §3.1`](docs/neetpg2021/KNOWN_LIMITATIONS.md). The whole-word regex version is in place for stage 2b (R3), but stage 7's subject mapper still uses substring.
- **Severity**: degrades (subject/topic fields mis-classified, but question content is correct)
- **Effort**: XS — copy the `re.findall(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE)` pattern from stage 7's `_whole_word_count` (already exists at line 116) into the `_map_subject` function. < 1 hour.
- **Changes OPTION?**: No — doesn't affect question fidelity, only metadata quality.

### Gap 8 — QA gate thresholds mathematically unreachable

- **What**: The current 3-rule gate is unreachable for image-based questions (image mapping ceiling 0.9 < 0.95; recon ceiling for image Q = 0.84 < 0.85).
- **Evidence**: See [QA_SYSTEM_REVIEW.md](QA_SYSTEM_REVIEW.md). All 4 specific pages where the rule fires on a real bug vs harmless content documented there.
- **Severity**: blocks (the gate *prevents* the import of 215 working questions because the threshold is unreachable)
- **Effort**: M — replace with the 9-axis per-question gate from [PROPOSED_QA_V2.md](PROPOSED_QA_V2.md). 4–6 hours including unit tests for each axis.
- **Changes OPTION?**: **YES** — fundamental to allowing import at all.

### Gap 9 — OCR-corrected region text is not propagated to Stage 7 unclassified_blocks

- **What**: Stage 6's per-region OCR results live in [`06_ocr/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/p001.json) but Stage 7 only consults them for replacement on the *eligible* digital regions (those with `type != "unclassified" and confidence >= 0.85`). The orphan unclassified regions never get OCR'd text.
- **Evidence**: [`06_ocr/p001.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/p001.json) `region_ocr` has 9 entries; Stage 7's replacement logic ([stage_7_structured.py:539-563](backend/mce/stages/stage_7_structured.py#L539)) requires `r.get("type") not in ("unclassified",) and r.get("confidence", 1.0) >= 0.85` to skip the replacement — meaning unclassified regions with low confidence never get OCR'd text.
- **Severity**: degrades (orphan text in unclassified_blocks is sometimes blank or has font-rendering errors)
- **Effort**: S — flip the condition so unclassified regions WITH low confidence get OCR-replaced. 1 hour + 1 test.
- **Changes OPTION?**: No for educational fidelity (students don't see unclassified_blocks); yes for QA gate (reduces `unclassified_count` after Stage 5's sweep).

### Gap 10 — Answer-key section absent; answers must come from inline text

- **What**: The 2021 PDF has no `ANSWER KEY` section; every answer is inline. Stage 6's global answer-key extractor correctly returns 0. No fix possible in the pipeline.
- **Evidence**: [`06_ocr/answer_key.json`](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/06_ocr/answer_key.json) `"answers": {}`.
- **Severity**: PDF Limitation — nothing to fix.
- **Effort**: N/A.
- **Changes OPTION?**: No.

### Gap 11 — Image placement metadata absent in source PDF

- **What**: PyMuPDF's `get_image_rects` returns `[]` for every xref in this PDF. Multi-scale template matching places images to ±5 px at confidence 0.9 max.
- **Evidence**: 351 of 505 images use `placement_method = template_match`, 154 use `image_block_ordinal`/`pixel_scan`. Per [`KNOWN_LIMITATIONS.md §2.1`](docs/neetpg2021/KNOWN_LIMITATIONS.md), no real placement rects exist.
- **Severity**: PDF Limitation — physically impossible to fix in pipeline.
- **Effort**: XL — would require a CNN layout model or manual annotation. Out of scope.
- **Changes OPTION?**: No (except by changing the gate to use placement bbox rather than per-image confidence).

### Gap 12 — "Other" images (logos, social cards) inflate `image_count` and conf min

- **What**: Same as Gap 5 but for the image-mapping gate: even if the question has 1 real content image, the other 3 attached logos drag `image_mapping_confidence = min(0.9, 0.9, 0.9, 0.5) = 0.5`.
- **Evidence**: p001_q00 with 4 attached images.
- **Severity**: degrades (image-mapping rule fires on harmless attached logos)
- **Effort**: S — see Gap 5. Same fix.
- **Changes OPTION?**: No (the 0.95 ceiling is still unreachable even after logo removal — template_match gives 0.9, not 0.95).

---

## Summary table

| # | Gap | Severity | Effort | Affects OPTION? |
| --- | --- | --- | --- | :---: |
| 1 | Question-prefix regex over-fires on bullet lists | blocks | S | YES |
| 2 | Continuation bullets captured as options | blocks | M | YES |
| 3 | Answer regex misses `Ans is b` (no colon) | blocks | S | YES |
| 4 | Cross-page stem recovery | blocks | L | YES |
| 5 | Logo images attached to Q blocks | degrades | XS | partial |
| 6 | Continuation explanations are orphan regions | degrades | M | YES |
| 7 | Substring-collision subject mapper | degrades | XS | No |
| 8 | QA gate thresholds mathematically unreachable | blocks | M | **YES (key)** |
| 9 | OCR-corrected text not in unclassified_blocks | degrades | S | No |
| 10 | No global answer-key section | PDF Lim | N/A | No |
| 11 | No image placement metadata in PDF | PDF Lim | XL | No |
| 12 | Logo images inflate `image_count` and conf | degrades | S | partial |

**Total engineering effort to fix the 5 OPTION-changing gaps**: S + M + S + L + M + M ≈ 20–28 hours of focused work (1 engineer, ~3 days).

---

## Final decision

Based on the evidence:

- The **extraction is ~80 % correct** (per the 30-question audit: 33 % PASS, 40 % MARGINAL, 27 % FAIL with 17 % of FAILs being extraction bugs that are easy to fix).
- The **QA gate is fundamentally broken** for this dataset: 2 of 3 rules are mathematically unreachable for image-based questions.
- The **remaining extraction gaps are tractable** (one senior engineer's 3-day work).
- After those gaps are closed, the QA gate will need to be replaced (or relaxed) for the import to be usable.

**Verdict**: This is NOT "QA rule too strict on a working importer" (Option B), and NOT "importer not production-ready on a working QA gate" (Option A). It is BOTH: the importer has 5 tractable extraction gaps AND the QA gate is over-strict.

### **OPTION C — Both importer AND QA system need engineering**

#### Extraction gaps (5 changes)

1. Tighten `question_prefix` regex in Stage 5 (Gap 1) — 2 hours.
2. Sweep continuation bullets into prior question / reject as extra options (Gap 2) — 3 hours.
3. Widen `RE_ANSWER_HEAD` regex in Stage 7 (Gap 3) — 1 hour.
4. Cross-page stem recovery in Stage 5/7 (Gap 4) — 6–10 hours.
5. Continuation-region orphan sweep in Stage 5 (Gap 6) — 3 hours.

**Total extraction work: ~15–20 hours (2 days senior engineer).**

#### QA-system gaps (1 change)

6. Replace the 3-rule page-level gate with the 9-axis per-question gate from [PROPOSED_QA_V2.md](PROPOSED_QA_V2.md) (Gap 8) — 4–6 hours.

**Total QA work: ~5 hours.**

#### Cosmetic-only gaps (optional)

- Gap 5 (logo filter on image attach) — 30 minutes
- Gap 7 (whole-word subject mapper) — 30 minutes
- Gap 9 (OCR to unclassified_blocks) — 1 hour
- Gap 12 (logo filter same as Gap 5)

**Total optional: ~2 hours.**

### Predicted outcome after Option C

Based on the audit extrapolation (215 questions total, 30 audited):

- ~5 questions affected by Gap 1 (phantom Qs from bullet lists) — fixed by Gap 1.
- ~10 questions affected by Gap 2 (extra options captured) — fixed by Gap 2.
- ~30 questions affected by Gap 3 (missing answer_labels) — fixed by Gap 3.
- ~5 questions affected by Gap 4 (cross-page stem) — fixed by Gap 4.
- ~30 questions affected by Gap 6 (orphan explanation regions) — fixed by Gap 6.

**Predicted post-fix numbers**:
- Educational-fidelity PASS rate: **33 % → ~75 %** (audit-based extrapolation)
- QA gate PASS rate under V2: **~75 %** of pages importable as-is, ~25 % with `needs_review=True` flag
- Pages with `no_question_blocks_detected` (continuation pages): correctly marked `importable=false` and skipped

### What does NOT change under Option C

- Gap 10 (no answer key section): unchanged — Stage 7.5 LLM augmentation is the only path for ~5 % of questions.
- Gap 11 (no image placement metadata): unchanged — template_match ceiling stays at 0.9. The new QA V2 gate is designed to *not* depend on per-image pixel confidence.
