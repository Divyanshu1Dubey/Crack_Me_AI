# BUGFIX_REPORT.md — NEET-PG-2021 Importer

**Source PDF**: `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`
**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`
**Date**: 2026-07-24

This document records the engineering work that fixed the 5 confirmed extraction
bugs identified in [`ROOT_CAUSE_ANALYSIS.md`](ROOT_CAUSE_ANALYSIS.md). For every
bug we (1) state the root cause in 2-3 sentences, (2) describe the fix, and (3)
point at the regression test that proves the bug cannot reappear.

All regression tests live in
[`mce/tests/test_bugfixes_2021.py`](../../../mce/tests/test_bugfixes_2021.py)
and use the **exact PDF snippets** from the 2021 benchmark that originally
failed. The suite is permanent — any future change that re-introduces a phantom
question, broken answer, or cross-page issue will fail one of these tests
before the importer is considered production-ready.

---

## Summary

| Bug | What was wrong | Where | Status |
| --: | --- | --- | --- |
| 1 | Stage 5 question_prefix regex over-fired on numbered bullets inside explanation lists | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py) | ✅ Fixed |
| 2 | Continuation bullets / "Ans." / "Explanation" lines were appended as phantom options | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py) | ✅ Fixed |
| 3 | Answer detection only matched `Answer:` — failed on `Ans.`, `Correct Option`, `(B)`, `A and C`, `Ans. is b i.e. Plating` | [`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py) | ✅ Fixed |
| 4 | Image-only continuation pages lost the stem (no cross-page recovery) | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py) | ✅ Fixed |
| 5 | Unclassified regions after an "Explanation:" header were never attached to the block | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py) | ✅ Fixed |
| 6 | Typed `answer_key` regions retained the `"Answer: A ..."` prefix and the bare-letter extractor returned `[]`; post-answer unclassified regions were merged into `answer_regions` instead of `explanation_regions` | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py), [`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py) | ✅ Fixed |
| 7 | The Bug-1 continuation-bullet guard over-fired on real question stems once Bug 6 made `explanation_regions` non-empty, swallowing Q2 of the same page into Q1's explanation list | [`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py) | ✅ Fixed |

All 19 regression tests pass (`test_bugfixes_2021.py`).
Full MCE suite is 136/136 green.

---

## Bug 1 — Phantom question_prefix regex over-fired on numbered bullets

### Root cause

The Stage 5 question_prefix regex matched any region whose text starts with
`<digits>. <non-space>` — including legitimate numbered bullets inside an
explanation list (e.g. *"1. Measles is a childhood infection caused by a virus."*
appearing inside the explanation of p045_q00). The state machine then opened a
new question block with that bullet as the stem, producing a phantom question
with zero options, zero answer, and the explanation as its "stem".

### Fix

Added a guard `_looks_like_continuation_bullet(text, current)` that returns
True when:

1. The current block already has explanation regions, AND
2. The candidate text matches the numbered-bullet regex
   (`^\s*\(?(\d{1,3})[\.\)]\s+\S`), AND
3. Either the candidate number is in [1..9] (typical list-item range), or the
   candidate number is *within ±2* of any existing explanation bullet's
   number (a continuation of the existing list).

When the guard fires, the region is re-tagged `type="unclassified"` so
`append_region` folds it into `explanation_regions`.

### Code

[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L237-L294)
(`_RE_NUMBERED_BULLET`, `_looks_like_continuation_bullet`)

### Regression test

`test_bug1_measles_bullet_not_a_question` (real snippet from p045),
`test_bug1_je_vaccine_bullet_not_a_question` (real snippet from p051),
`test_bug1_continuation_bullet_helper_unit`.

---

## Bug 2 — Continuation bullets / "Ans." / "Explanation" became phantom options

### Root cause

Two distinct pathways produced phantom options:

1. **Stage 2's `RE_OPTION_PREFIX`** matched `"A."` at the start of
   `"Ans. is a i.e. Scurvy"` and tagged it `type="option"`. Stage 5 then
   appended it to `option_regions` of the same block.
2. **Stage 5's "merge with previous typed region"** branch in `append_region`
   silently merged *every* subsequent unclassified region into
   `option_regions` once `last_typed_kind == "option"`. Even when Stage 2
   correctly typed the region as `unclassified` (e.g. `"Explanation"`,
   `"Radiographic features"`, `"MEDICAL JUNCTION TEAM"`), the state
   machine's "fill in the last typed bucket" logic swallowed them as
   "extra options".

The combined effect was catastrophic: p129_q00 ended up with 9 options
including `"Ans. is a i.e. Scurvy"` and `"Explanation"`, and p134_q00 ended
up with 9 options including the explanation prose.

### Fix

Two-part fix:

1. **Primary guard** (`_looks_like_continuation_option`):
   recognizes lines that start with `Ans.`, `Answer:`, `Answer-`, `Answer<`,
   `Explanation`, `Exp:`, `Explain:`, `Clinical Pearl`, `High Yield`,
   `Mnemonic`, `Reference`, `Ref:`, `Source:`, `Textbook`,
   `MEDICAL JUNCTION` / `MEDICAL-JUNCTION` (footer), and a handful of
   section headers that follow the answer+explanation block
   (`Radiographic features`, `Pediatric`, `Adult`). When the guard fires,
   the region is re-tagged `unclassified` so `append_region` does NOT
   append it to `option_regions`.

2. **Hard cap** in `append_region`: NEET-PG questions never have more than
   4 options (A-D). Once `len(option_regions) >= 4`, any further
   unclassified region is forced into `unclassified_regions` regardless
   of `last_typed_kind`. This catches any future "extra option" leak that
   slips past the primary guard.

### Code

[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L297-L319)
(`_looks_like_continuation_option`),
[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L407-L420)
(4-option cap in `append_region`).

### Regression test

`test_bug2_continuation_options_filtered` (real pipeline run on pages 129 and
134), `test_bug2_continuation_option_helper_unit`.

---

## Bug 3 — Answer detection only matched `Answer:` prefix

### Root cause

The original `RE_ANSWER_HEAD` accepted only `Answer:`. The 2021 PDF uses
*many* other prefixes:

  - `Ans. is b. i.e. Plating`        → ['B']
  - `Answer- A`                       → ['A']
  - `Answer < A`                      → ['A']
  - `Correct Option: B`               → ['B']
  - `Correct answer: A`               → ['A']
  - `Correct ans is C`                → ['C']
  - `Ans is (B)`                      → ['B']
  - `The answer is D`                 → ['D']
  - `Ans: A and C are both correct`   → ['A', 'C']
  - `Right answer: A`                 → ['A']

Plus a subtler bug: when the answer run was `"A and C"`, the original regex
captured the full span (including the `and` filler), and the test code
applied `re.findall(r"[A-Fa-f]", matched_string)` to extract letters — which
*also* pulled the `a` and `d` from `"and"` (because `[A-Fa-f]` is a
character class that matches every individual letter A-F / a-f). The result
was `['A', 'a', 'd', 'C']` (with `a`/`d` collapsed to uppercase) — `'D'` is
a false positive answer.

### Fix

Two-part fix:

1. **Broadened `RE_ANSWER_HEAD`** to accept every variant found in the 2021
   PDF (`Ans`, `Answer`, `Key`, `Correct answer`, `Correct ans`, `Correct
   option`, `The answer is`, `Right answer`), with an optional `(?:is\s+)?`
   to support both `Answer: A` and `Correct ans is C`.

2. **Replaced the bare-letter regex** with a unified answer extractor
   (`_extract_bare_labels`) that:
   - First tries a **punctuation-separator regex**
     (`[A-Fa-f](?:\s*[ ,&/+]\s*[A-Fa-f])*`) for `A, B, C` / `A/B` / `A&B`.
     The separator class is restricted to non-alphabetic characters so
     the matched span contains ONLY answer letters.
   - Then tries a **word-separator regex**
     (`[A-Fa-f](?:\s+(?:and|or)\s+[A-Fa-f])*`) for `A and B` / `A or B`.
     Each letter is captured in its own group so the filler word
     (`and`/`or`) is **never** included in the answer set.
   - Returns a deduplicated, uppercased list of letters via
     `m.groups()` — never via `re.findall` on a substring (which is what
     caused the false-positive `D` in the original bug).

   The paren-letter form `(B)` is matched first by `_RE_ANSWER_PAREN`.

### Code

[`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py#L136-L191)
(`RE_ANSWER_HEAD`, `_RE_ANSWER_BARE`, `_RE_ANSWER_PAREN`, `_extract_bare_labels`),
both call sites at [`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py#L222-L237)
and [`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py#L354-L367).

### Regression test

`test_bug3_answer_regex_new_variants` (11 prefix variants),
`test_bug3_answer_extraction_bare_and_paren` (8 answer-body forms including
`A and C`), `test_bug3_layout_context_ans_is_b` (real snippet
`"Ans. is b. i.e. Plating"`), `test_bug3_layout_context_correct_option`.

---

## Bug 4 — Image-only continuation pages lost the stem

### Root cause

When a question's stem is on page N and only the image + options are on page
N+1 (a common layout for "see radiograph on previous page" questions), Stage
5's per-page grouping logic opened a *new* question block on page N+1 with an
empty / truncated stem. The truncated block had stem text like `"Of"` or
`"Following"` — fragments left over from the page break — and was
subsequently exported as a broken question.

### Fix

Two-step post-pass after the per-page grouping completes:

1. `_looks_like_truncated_stem(block)` returns True when the block's
   `stem_regions` is empty OR the stem is < 30 chars OR the stem starts with
   a preposition (`Of the following`, `From the above`, etc.) — all signs
   that the stem was clipped at a page boundary.

2. `_merge_truncated_with_previous(blocks)` walks blocks in page order and,
   for every truncated block whose previous block is on a *prior* page,
   merges the two — appending the truncated block's option_regions /
   explanation_regions / unclassified_regions to the previous block's
   corresponding lists, then deleting the truncated block. The merged block
   gets the union of page_numbers in `page_numbers`.

The post-pass runs in `Stage 5.run()` after `_group_regions_into_blocks` and
records the merge count in `index["post_passes"]["cross_page_merges"]`.

### Code

[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L323-L343)
(`_looks_like_truncated_stem`),
[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L597-L611)
(`_merge_truncated_with_previous` + run-loop wiring).

### Regression test

`test_bug4_truncated_stem_helper_unit`, `test_bug4_cross_page_merge_runs_on_2021`,
`test_merge_truncated_with_previous_basic`.

---

## Bug 5 — Unclassified regions after an "Explanation:" header were never attached

### Root cause

When a block has no `explanation_regions` yet but a subsequent unclassified
region begins with `"Explanation:"`, the state machine neither routed it into
`explanation_regions` (because the region's `type` is `unclassified`) nor
flagged it as a continuation. The explanation prose ended up in
`unclassified_regions` forever — invisible to Stage 7, which only reads from
typed regions.

### Fix

`_sweep_continuation_orphans(blocks)` post-pass runs after the per-page
grouping:

- For each block, scans `unclassified_regions` in order.
- When the *first* unclassified region begins with `"Explanation:"` (case-
  insensitive), promotes the entire unclassified tail to `explanation_regions`.
- When the first unclassified region is plain prose AND the block already
  has at least one `explanation_regions` entry, appends the rest to
  `explanation_regions` (continuation).
- Returns the count of swept regions; the metric is recorded in
  `index["post_passes"]["continuation_orphans_swept"]`.

### Code

[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L588-L598)
(`_sweep_continuation_orphans`).

### Regression test

`test_bug5_orphan_sweep_helper_unit`, `test_bug5_orphan_sweep_from_explanation_header`.

---

## Bug 6 — Typed `answer_key` regions kept the "Answer: A ..." prefix; post-answer unclassified regions were merged into `answer_regions` instead of `explanation_regions`

### Root cause

Two distinct problems, both surfaced by the post-fix benchmark
(`axis_3_answer_correct = 13/204` and `axis_4_explanation_complete = 56/204`):

1. **Stage 7** iterated over `block.get("answer_regions", [])` and called
   `_extract_bare_labels(text.lstrip())` directly on the raw text.  But
   the 2021 PDF's answer regions almost always carry the prefix
   (`"Answer: A Median Nerve"`, `"Ans. is b i.e. Snowman heart"`,
   `"Answer <A:Umbilical artery"`).  The bare-letter regex
   `_RE_ANSWER_BARE` requires the text to *start* with a single
   letter A-F, so the prefix caused the regex to return `[]` and
   `answer_labels` came back empty for 191 of 204 questions.  This is
   why `axis_3_answer_correct` failed so badly despite the answer
   region being correctly typed in Stage 2.

2. **Stage 5**'s `append_region` had a fallback branch
   `elif last_typed_kind == "answer_key": current["answer_regions"].append(region)`
   that absorbed every subsequent unclassified region into
   `answer_regions`.  In the 2021 PDF the answer line is followed by
   1-3 unclassified paragraphs of *explanation prose* (e.g. on p001 the
   "Answer: A Median Nerve" line is followed by 3 paragraphs of EMG
   explanation).  All three paragraphs were silently absorbed into
   `answer_regions`, so the explanation never reached
   `explanation_regions` and Stage 7 emitted `explanation=None`.  This
   is why `axis_4_explanation_complete` failed.

### Fix

Two-part fix:

1. **Stage 7** (`_build_parsed_question`): strip the answer prefix
   with `RE_ANSWER_HEAD` before calling the bare-letter / paren
   extractors.  This is exactly what the
   `_layout_context_answer` helper already does for the layout-context
   fallback; we just apply the same logic to the typed-answer-key path.

2. **Stage 5** (`append_region`): once the block has captured at
   least one `answer_key` region, route subsequent unclassified
   regions to `explanation_regions` instead of `answer_regions`.
   This mirrors the design used by the option-list path (after a
   4-option cap, further unclassified regions go to the unclassified
   bucket) but goes one step further: the post-answer unclassified
   regions ARE the explanation, so route them there directly.

### Code

[`stage_7_structured.py`](../../../mce/stages/stage_7_structured.py#L360-L390)
(`_build_parsed_question` answer-region handling, with RE_ANSWER_HEAD
prefix strip),
[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L429-L439)
(post-answer unclassified routing).

### Regression test

`test_bug6_strip_answer_head_unit` (unit),
`test_bug6_post_answer_unclassified_unit` (unit, with real 2021 PDF
p001 region structure), `test_bug6_2021_p001_q1_has_answer_and_explanation`
(end-to-end on the actual p001_q00 region).

---

## Bug 7 — The Bug-1 continuation-bullet guard over-fired on real question stems once Bug 6 made `explanation_regions` non-empty

### Root cause

Bug 6's fix meant that the explanation bucket on a real question
block is now non-empty (whereas before Bug 6 it was empty for most
blocks).  The Bug 1 guard `_looks_like_continuation_bullet` returns
`True` when the current block already has `explanation_regions` AND
the candidate text is a numbered bullet.  On p001 the candidate is
Q2's stem `"2. A small boy with multiple fracture of Humerus
following which there is loss of extension of wrist and difficulty
in flexion of elbow and supination"` — a long, prose-like clinical
question stem.  The guard's heuristic (`cand_n <= max(prev_numbers) + 2`)
saw `cand_n=2`, `prev_numbers=[1]`, and returned `True`, absorbing
Q2's stem into Q1's explanation list.  Q2 never opened a new block;
its 4 options (A. Musculocutaneous nerve, B. Median nerve, C. Axillary,
D. Radial nerve) were appended to Q1's `option_regions` and both
questions were emitted as a single 8-option block with `is_correct=True`
on the first A option of each row.

This bug ONLY manifests once Bug 6 is fixed (Bug 6 makes
`explanation_regions` non-empty, which is the precondition Bug 7's
guard checks).

### Fix

Tighten `_looks_like_continuation_bullet` to recognise a real
question stem: a long body (> 60 chars) without a terminal period
is almost always a clinical scenario description, not a list bullet.
A bullet always ends with a period (or with a question mark, but
then the original guard's `endswith("?")` branch already handles
it).  When the candidate body is > 60 chars and does NOT end with
a period, return `False` early — this bypasses the
"matches previous explanation's number range" check that over-fired.

### Code

[`stage_5_question_blocks.py`](../../../mce/stages/stage_5_question_blocks.py#L276-L294)
(`_looks_like_continuation_bullet` early-return for long
non-bullet bodies).

### Regression test

`test_bug7_continuation_bullet_helper_unit` (unit, with the real
2021 PDF p001_q00 stem and explanation structure),
`test_bug7_2021_p001_q2_is_separate_block` (end-to-end on p001,
asserting Q1 and Q2 are separate blocks with their own 4 options
each).

---

## Verification

```
$ cd backend && python -m pytest mce/tests/test_bugfixes_2021.py -v
======================== 19 passed in 121.24s (0:02:01) ========================

$ cd backend && python -m pytest mce/tests/
================= 136 passed, 1 warning in 606.48s (0:10:06) ================
```

Every bug has at least one **unit test** (cheap, isolated, runs in < 1s) and
at least one **integration test** (full pipeline run on the exact pages that
originally failed). The integration tests use the real 2021 PDF — if the PDF
ever changes in a way that affects these snippets, the tests will catch it.

---

## Non-changes (deliberately preserved)

The QA gate thresholds in Stage 8 (`PASS_THRESHOLD = 0.85`,
`MAX_UNCLASSIFIED_BLOCKS = 2`, `image_mapping_recall >= 0.95`) were NOT
modified. The user's directive was clear: do NOT lower thresholds, do NOT
inflate confidence. The bugfixes fix the *extraction* so the existing gate
measures genuine quality.

Instead, a **new** QA V2 system (per-question 9-axis scoring) was added on
top of the legacy gate. See [`QA_V2_RESULTS.md`](QA_V2_RESULTS.md) for the
post-fix fidelity measurement.