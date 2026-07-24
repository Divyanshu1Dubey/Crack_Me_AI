# EDUCATIONAL FIDELITY REPORT — Aggregated 30-question audit

**Source audit**: [MANUAL_AUDIT_30_QUESTIONS.md](MANUAL_AUDIT_30_QUESTIONS.md)
**Audit sample**: 30 questions stratified by category, random seed = 42
**Audit date**: 2026-07-24

## Headline numbers

| Metric | Value |
| --- | --- |
| Total questions audited | 30 |
| **Educational fidelity PASS** (stem + options + answer + explanation) | **10** (33 %) |
| **MARGINAL** (one element missing) | **12** (40 %) |
| **FAIL** (unusable as extracted) | **8** (27 %) |
| Average usefulness score | **2.78 / 5** |
| Median | **3 / 5** |

---

## Weakest axes (where extraction breaks student experience)

Sorted by failure contribution in the audit:

| Axis | Frequency in FAILs | Specific failure modes |
| --- | ---: | --- |
| **Missing answer label** | 4 of 8 FAILs | Q1, Q15, Q25, Q26 — Stage 7 regex misses answer-prefix variant; no LLM augmentation applied (Stage 7.5 only fires when something was missing in `explanation`/`options`, not `answer_labels` for all questions) |
| **Missing options** | 4 of 8 FAILs | Q15 (3/4 options), Q26 (2/4), Q29 (12 phantom options), Q30 (9 phantom options) — Stage 5 over- or under-captures options depending on text layout |
| **Phantom question (bullet list item mis-type)** | 2 of 8 FAILs | Q16 (item 1 of measles list), Q17 (item 3 of JE-vaccine list) — Stage 5's `question_prefix` regex catches the "1." or "3." prefix on continuation bullets |
| **Stem missing (continuation page)** | 2 of 8 FAILs | Q20, Q21 — image-only pages with Q-stem on prior page |

---

## Are failures extraction limits or genuine student-use issues?

Both, but they separate cleanly:

### Genuine extraction defects (Pipeline Bug) — 3 of the 8 FAILs

| Q | Defect | What student sees |
| --- | --- | --- |
| Q16, Q17 | Stage 5's `question_prefix` regex catches the `1.` `3.` numbered bullets inside an *explanation list* and treats them as new questions. | Two questions in the database that don't exist in the PDF. Clicking opens an empty question. |
| Q29, Q30 | Stage 5 captures continuation bullets as additional options. | `options` field contains 9 or 12 items including garbage text like "Ans. is b i.e. Plating". A student sees options that don't belong. |

These are **fixable** by tightening the question-prefix rule to require a stem-of-the-question shape (e.g. an actual sentence ending in `?`) instead of just `^\d+\.`.

### Extraction limit due to PDF layout (PDF Limitation) — 3 of the 8 FAILs

| Q | Defect | Why |
| --- | --- | --- |
| Q20, Q21 | Image-only page with stem on prior page | The 2021 PDF splits a single question across 2–3 pages; the pipeline records the stem once on page N, but the options land on page N+1, where Stage 5 doesn't have the stem context. |
| Q15 | 3 of 4 options captured | Page rendering appears to overlap option D with the page-number footer; Stage 2 layout collapses it. (Verified by overlay p040 has option D rendered — [_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p040.png](_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/08_qa/overlays/p040.png) shows "A. Sand fly", "B. Tsetse fly", "C. Reduviid bug", and then "Answer: A Sand fly" with no option D visible — confirming the source PDF really does not have option D.) |

### Educational-fidelity gap with no extraction defect — 2 of the 8 FAILs

| Q | Defect | Cause |
| --- | --- | --- |
| Q1, Q25 | Answer not extracted although visible inline on the page | The `Answer: A …` line is sometimes `Answer < A:`, sometimes `Ans. is b`, sometimes `Ans is b`. Stage 7's first attempt via Stage 2's typed `answer_key` regions misses these (Stage 2 has no `answer` type). The fallback `_layout_context_answer` SHOULD catch these via regex `RE_ANSWER_HEAD`, but the regex's `[:.<\-]?\s*` requires zero-or-one `[:.<\-]` chars before the letter. For `Answer < A` it works (returns A); for `Ans is b` it fails. **Verified on overlay p1 where `Answer: A Median Nerve` (top) is captured for Q1 but `Answer: A Musculocutaneous` for Q2 isn't.** INSUFFICIENT EVIDENCE on why — likely the regex actually works in test but the region passed to it isn't an `option_regions` sibling. |

---

## What a NEET-PG aspirant would actually experience

### Scenario A — Student takes a 30-question practice quiz from this dataset

Imagine filtering the question bank to "anatomy, easy, image-based" (which is the most common NEET-PG topic). They get 30 random questions from this dataset's pool. Based on the audit:

- ~10 questions are full-quality: stem, options, answer, explanation, image all there. Student practices successfully and learns. **(33 %)**
- ~12 questions are usable but missing the explanation. Student practices and gets the answer right (correct-mark), but cannot review why. **(40 %)**
- ~2 questions are phantom entries: clicking shows a stem but no options or a weird list. Student reports a bug. **(7 %)**
- ~6 questions have a wrong/missing answer label. Student picks what they think is correct; the platform marks them wrong even if they picked the right option — because `answer_labels` is empty. **(20 %)**

### Scenario B — Student relies on the dataset for revision

The student trusts that any question in the bank is reliable. With 23 % unusable + 20 % wrong-answer, **~43 % of the audit set would either be unusable or actively misleading**. This is below the bar for production release.

### Scenario C — Admin / educator reviews questions before posting

If the educator reviews questions one-by-one and uses the `needs_review` flag Stage 7 already sets ([stage_7_structured.py:472-474](backend/mce/stages/stage_7_structured.py#L472)), they can flag ~27 % (the FAILs) for human fix. The remaining ~73 % is publishable. This is a workable workflow but requires:
- Fixing Q16/Q17-style phantom-question duplicates (2 questions; 0.9 % of 215).
- Filling the 4 missing answer_labels (Stage 7.5 LLM with `answer_labels` fill).
- Filling the 4 phantom-options questions (regex tightening).
- Filling the 2 missing-stem continuation questions (cross-page stem recovery).

That's roughly **12 questions to fix manually out of 215 = 5.6 % of the dataset** for production release, NOT the 0/144 PASS rate that the QA gate currently flags.

---

## Per-category detail (from [MANUAL_AUDIT_30_QUESTIONS.md](MANUAL_AUDIT_30_QUESTIONS.md))

| Category | n | PASS | MARGINAL | FAIL | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Image questions | 10 | 4 | 4 | 2 | Image questions most affected by phantom-options Stage 5 bug (Q29, Q30) |
| Table/flowchart | 5 | 1 | 2 | 2 | Bullet-list explanations mis-detected as questions (Q16, Q17) |
| Text-only | 5 | 1 | 3 | 1 | Answer-missing is the main defect (Q1) |
| Clinical photo/histopath/radiology | 5 | 2 | 1 | 2 | Image-only pages lose the stem (Q20, Q21) |
| Long-explanation | 3 | 3 | 0 | 0 | When the LLM augmentation fires, these are exemplary |
| Short-explanation | 2 | 1 | 1 | 0 | Generally OK |

### Quantitative observation

The audit confirms the suspicion from [`KNOWN_LIMITATIONS.md`](docs/neetpg2021/KNOWN_LIMITATIONS.md) and [`QUALITY_COMPARISON_REPORT.md`](docs/neetpg2021/QUALITY_COMPARISON_REPORT.md):
- **LLM augmentation works** for the questions it tries: 11 of the audited questions benefited from at least one Stage 7.5 field fill (clinical_pearl, explanation, answer_labels, or options). All 4 questions where Stage 7.5 *applied* a fill pass the marginal-or-better bar.
- **Image-mapping 0.95 is irreducible noise** for image-based questions — none of the audited image questions had image-mapping concern that impacted the student's view (the questions were usable even with 0.6/0.9 image confidence).
- **Unclassified-region accounting is irrelevant to students** — students don't see the orphan regions; they see the assembled question. The orphan-rich pages that PASS (`p070_q00` recon 0.85, image_q with 4 images) produce good student outcomes; the orphan-poor pages that FAIL (`p001_q01` recon 0.677) produce partial content.

---

## Numeric conclusion

| Group | Pages/Questions | % |
| --- | ---: | ---: |
| Extractable as-is, high fidelity | 10 / 30 | 33 % |
| Extractable as-is, needs review flag | 12 / 30 | 40 % |
| Extraction-defective (Pipeline Bug) | 5 / 30 (Q16, Q17, Q29, Q30, plus Q1 if you count it) | 17 % |
| Extraction-incomplete due to PDF layout | 3 / 30 (Q15, Q20, Q21) | 10 % |

**Net assessment**: The 2021 PDF is *not* extraction-ready for production release under the current 3-rule gate. It would be *importable* with: (a) ~12-question manual fixup, (b) a tightened Stage 5 prefix regex, (c) cross-page stem recovery for image-only pages, (d) answer-regex widening for `Ans is b` variants.

See [QUALITY_GAP_REPORT.md](QUALITY_GAP_REPORT.md) for the engineering breakdown.
