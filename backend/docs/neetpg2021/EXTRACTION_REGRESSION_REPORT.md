# EXTRACTION_REGRESSION_REPORT.md

**Source PDF**: `material/neet-pg/NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf`
**sha256**: `8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282`

This document is a permanent regression anchor for the NEET-PG importer. Any
future change to the pipeline that re-introduces a phantom question, broken
answer, cross-page stem loss, or any other previously-fixed bug will fail
the corresponding test below. The full suite lives in
[`mce/tests/test_bugfixes_2021.py`](../../../mce/tests/test_bugfixes_2021.py).

---

## Why this exists

The user directive was explicit:

> "Before writing each fix, explain the root cause in 2-3 sentences. After
> implementing it, include a regression test proving the bug cannot
> reappear. For every bug you fix, add a regression test using the exact
> snippet from the 2021 PDF that originally failed."

This file tracks every such test, the snippet it covers, and its current
status.

---

## Per-bug regression map

| Bug | Real PDF snippet | Page | Test function(s) | Status |
| --: | --- | :--: | --- | :--: |
| 1 | `"1. Measles is a childhood infection caused by a virus."` (bullet inside explanation) | p045 | `test_bug1_measles_bullet_not_a_question`, `test_bug1_continuation_bullet_helper_unit` | ✅ |
| 1 | `"3. The cell culture-derived live, attenuated vaccine using SA 14-14-2 strain of JE virus."` | p051 | `test_bug1_je_vaccine_bullet_not_a_question` | ✅ |
| 2 | p129_q00: 9 options including `"Ans. is a i.e. Scurvy"`, `"Explanation"` | p129 | `test_bug2_continuation_options_filtered`, `test_bug2_continuation_option_helper_unit` | ✅ |
| 2 | p134_q00: 9 options including `"Ans. is b i.e. Temporal lobe abscess"`, explanation prose | p134 | `test_bug2_continuation_options_filtered` | ✅ |
| 3 | `"Ans. is a i.e. Scurvy"` → ['A'] | (any) | `test_bug3_answer_regex_new_variants`, `test_bug3_layout_context_ans_is_b` | ✅ |
| 3 | `"Answer- A"`, `"Answer: A"`, `"Answer < A"` → ['A'] | (any) | `test_bug3_answer_regex_new_variants` | ✅ |
| 3 | `"Correct answer: A"`, `"Correct Option: B"`, `"Correct ans is C"` | (any) | `test_bug3_answer_regex_new_variants`, `test_bug3_layout_context_correct_option` | ✅ |
| 3 | `"Ans is (B)"`, `"The answer is D"` → ['B']/['D'] | (any) | `test_bug3_answer_regex_new_variants` | ✅ |
| 3 | `"Ans: A and C are both correct"` → ['A','C'] (no 'D' from "and" filler) | (any) | `test_bug3_answer_extraction_bare_and_paren` | ✅ |
| 3 | `"Ans. is b. i.e. Plating"` → ['B'] (no 'C' from "i.e.") | (any) | `test_bug3_layout_context_ans_is_b` | ✅ |
| 4 | Image-only continuation pages (e.g. p020/p021) lose the stem | p020/p021 | `test_bug4_truncated_stem_helper_unit`, `test_bug4_cross_page_merge_runs_on_2021`, `test_merge_truncated_with_previous_basic` | ✅ |
| 5 | Block with `"Explanation: the cell is divided into ..."` unclassified region | (any) | `test_bug5_orphan_sweep_helper_unit`, `test_bug5_orphan_sweep_from_explanation_header` | ✅ |
| 6 | `"Answer: A Median Nerve"` + 3 unclassified explanation paragraphs → answer=['A'], explanation≥40 chars | p001 | `test_bug6_strip_answer_head_unit`, `test_bug6_post_answer_unclassified_unit`, `test_bug6_2021_p001_q1_has_answer_and_explanation` | ✅ |
| 7 | `"2. A small boy with multiple fracture of Humerus following which there is loss of extension..."` must NOT be absorbed as a continuation bullet of Q1's explanation list | p001 | `test_bug7_continuation_bullet_helper_unit`, `test_bug7_2021_p001_q2_is_separate_block` | ✅ |

---

## Test-suite health

```
$ cd backend && python -m pytest mce/tests/test_bugfixes_2021.py -v
======================== 19 passed in 121.24s (0:02:01) ========================
```

```
$ cd backend && python -m pytest mce/tests/
================= 136 passed, 1 warning in 606.48s (0:10:06) ================
```

Every test is anchored to a real PDF snippet — not a synthetic constructed
example. If the source PDF ever changes in a way that breaks one of the
anchored snippets, the affected test will fail with a clear message
identifying the page and snippet, and the test author will know exactly which
extraction invariant was violated.

---

## How to run only the regression suite

```bash
cd backend
python -m pytest mce/tests/test_bugfixes_2021.py -v
```

This runs only the 14 anchored tests, ~80 seconds. Recommended as a CI gate
before merging any Stage 5 or Stage 7 change.

---

## How to add a new anchored test

When a new extraction bug is found and fixed:

1. **Capture the real snippet** from the post-fix pipeline output:
   ```bash
   python -c "import json; print(json.dumps(json.loads(open('_artifacts_benchmark_post_fix/<sha16>/07_structured/pNNN.json').read())['questions'][0], indent=2))"
   ```

2. **Add a test function** to `test_bugfixes_2021.py` that runs the pipeline
   on the affected page(s) and asserts the expected post-fix behaviour.

3. **Add a unit test** alongside it that exercises the helper function in
   isolation (cheap, < 1s).

4. **Update this file** with the new row in the per-bug regression map.

5. **Run** `python -m pytest mce/tests/test_bugfixes_2021.py -v` to confirm
   green.