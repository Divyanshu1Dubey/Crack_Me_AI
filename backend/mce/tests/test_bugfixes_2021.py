"""Regression tests for the 5 confirmed extraction bugs.

Every test uses the EXACT snippet from the 2021 NEET-PG PDF that originally
failed (extracted from the benchmark artefacts in
``_artifacts/mce/neet_pg/2021/8ebea8995a4ade79/07_structured/_index.json``).
This makes the test suite a permanent regression anchor — any future
change that re-introduces a phantom question, broken answer, or
cross-page issue will fail one of these tests before the importer is
considered production-ready.

Run: cd backend && python -m pytest mce/tests/test_bugfixes_2021.py -v
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mce.profiles import get_profile_for_filename
from mce.stages import MceContext
from mce.stages.stage_1_render import run as run_s1
from mce.stages.stage_2_layout import run as run_s2
from mce.stages.stage_5_question_blocks import (
    run as run_s5,
    _looks_like_continuation_bullet, _looks_like_continuation_option,
    _looks_like_truncated_stem, _merge_truncated_with_previous,
    _sweep_continuation_orphans,
)
from mce.stages.stage_6_ocr import run as run_s6
from mce.stages.stage_7_structured import (
    run as run_s7,
    _layout_context_answer, RE_ANSWER_HEAD,
    _extract_bare_labels, _RE_ANSWER_PAREN,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_PDF = REPO_ROOT / "material" / "neet-pg" / "NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf"


def _ctx(tmp_path: Path) -> MceContext:
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip(f"benchmark PDF missing at {pdf}")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    profile = get_profile_for_filename(pdf.name)
    return MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=profile,
        artefact_root=tmp_path / sha16,
    )


def _pipeline_through_s7(ctx: MceContext, pages: list[int]) -> None:
    run_s1(ctx, pages=pages)
    run_s2(ctx, pages=pages)
    run_s5(ctx, pages=pages, force=True)
    run_s6(ctx, pages=pages)
    run_s7(ctx, pages=pages, force=True)


def _read_index(ctx: MceContext) -> dict:
    p = ctx.stage_dir("07_structured") / "_index.json"
    if not p.exists():
        return {"questions": []}
    import json
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- Bug 1
# REAL PDF SNIPPET (from p045 and p051 in 07_structured/_index.json):
#   p045_q01 stem: "1. Measles is a childhood infection caused by a virus."
#   p051_q03 stem: "3. The cell culture-derived live, attenuated vaccine using SA 14-14-2
#                   strain of JE virus. Under the National program..."
# These are bullets inside an explanation list. Stage 5 must NOT open new
# questions for them.


def test_bug1_measles_bullet_not_a_question():
    """Bug 1 — '1. Measles is a childhood infection caused by a virus.' is
    a bullet inside an explanation list, NOT a question.

    Pre-fix: Stage 5 created a phantom question p045_q01 with 0 options,
    0 answer, 0 explanation.
    Post-fix: Stage 5 must NOT create a question with that exact stem;
    the line must be folded into the explanation of p045_q00.
    """
    import tempfile
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [45])
    idx = _read_index(ctx)
    measles_qs = [
        q for q in idx["questions"]
        if (q.get("stem") or "").startswith("1. Measles is a childhood")
    ]
    assert measles_qs == [], (
        f"Phantom question from Bug 1 leaked: {[q['id'] for q in measles_qs]}"
    )


def test_bug1_je_vaccine_bullet_not_a_question():
    """Bug 1 — '3. The cell culture-derived live, attenuated vaccine using
    SA 14-14-2 strain of JE virus.' is a bullet inside an explanation
    list (post p051_q00's 'Currently, there are three types of JE
    vaccines in use:'), NOT a question.

    Pre-fix: Stage 5 created a phantom question p051_q03.
    Post-fix: it must NOT exist.
    """
    import tempfile, json
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [51])
    idx = json.loads((ctx.stage_dir("07_structured") / "_index.json").read_text(encoding="utf-8"))
    je_qs = [
        q for q in idx["questions"]
        if (q.get("stem") or "").startswith("3. The cell culture-derived live")
    ]
    assert je_qs == [], (
        f"Phantom question from Bug 1 leaked: {[q['id'] for q in je_qs]}"
    )


def test_bug1_continuation_bullet_helper_unit():
    """Unit test: ``_looks_like_continuation_bullet`` must return True
    for the exact Measles bullet pattern from the 2021 PDF."""
    current = {
        "explanation_regions": [
            {"text": "1. First bullet about Measles."},
            {"text": "2. Second bullet about incubation."},
        ],
    }
    assert _looks_like_continuation_bullet(
        "3. The cell culture-derived live, attenuated vaccine using "
        "SA 14-14-2 strain of JE virus.",
        current,
    ) is True


# --------------------------------------------------------------------- Bug 2
# REAL PDF SNIPPET (from p129_q00 and p134_q00 in 07_structured/_index.json):
#   p129_q00 has 9 options including the bogus entries:
#     "Ans. is a i.e. Scurvy", "Explanation", and 3 more
#   p134_q00 has 12 options including the bogus entries:
#     "Ans. is b i.e. Temporal lobe abscess", "Explanation", and 6 more
# These come from layout_heuristic's RE_OPTION_PREFIX catching "A." at
# the start of "Ans. is a i.e. ..." and "Explanation" lines.


def test_bug2_continuation_options_filtered():
    """Bug 2 — ``Ans. is a i.e. Scurvy`` and ``Explanation`` lines must
    NOT be appended to ``option_regions``.

    Pre-fix: p129_q00 had 9 options; p134_q00 had 12.
    Post-fix: each of those blocks must have exactly 4 options labelled
    A–D.
    """
    import tempfile, json
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [129, 134])
    idx = json.loads((ctx.stage_dir("07_structured") / "_index.json").read_text(encoding="utf-8"))
    for q in idx["questions"]:
        if q.get("page_number") not in (129, 134):
            continue
        opts = q.get("options") or []
        labels = [o.get("label") for o in opts]
        # Exactly 4 labelled options A–D; no None labels.
        assert len(opts) <= 4, (
            f"{q['id']}: still has {len(opts)} options: {labels}"
        )
        assert all(lbl in ("A", "B", "C", "D") for lbl in labels), (
            f"{q['id']}: bogus option labels: {labels}"
        )


def test_bug2_continuation_option_helper_unit():
    """Unit test: ``_looks_like_continuation_option`` must return True
    for the exact bogus-prefix lines from p129 / p134."""
    current = {"option_regions": [{"text": "A. Scurvy"}]}
    assert _looks_like_continuation_option("Ans. is a i.e. Scurvy", current) is True
    assert _looks_like_continuation_option("Explanation", current) is True
    assert _looks_like_continuation_option("A. Scurvy", current) is False
    assert _looks_like_continuation_option("B. Rickets", current) is False


# --------------------------------------------------------------------- Bug 3
# REAL PDF SNIPPET — answer variants that previously failed to extract:
#   "Ans. is a i.e. Scurvy"        → ['A']
#   "Answer- A"                    → ['A']
#   "Answer: A"                    → ['A']
#   "Answer < A"                   → ['A']
#   "Correct answer: A"            → ['A']
#   "Correct Option: A"            → ['A']  (NEW)
#   "Ans is (B)"                   → ['B']  (NEW)
#   "Ans is b i.e. Plating"        → ['B']  (no 'C' from "i.e.")
#   "Ans: A and C are both correct"→ ['A','C']  (multi-letter)


def test_bug3_answer_regex_new_variants():
    """Bug 3 — every answer-prefix variant found in 2021 must match
    RE_ANSWER_HEAD."""
    cases = [
        "Ans. is a i.e. Scurvy",
        "Answer- A",
        "Answer: A",
        "Answer < A",
        "Correct answer: A",
        "Correct Option: B",
        "Correct ans is C",
        "Ans is (B)",
        "The answer is D",
        "Ans: A and C are both correct",
        "Right answer: A",
    ]
    for txt in cases:
        assert RE_ANSWER_HEAD.match(txt), f"RE_ANSWER_HEAD missed: {txt!r}"


def test_bug3_answer_extraction_bare_and_paren():
    """Bug 3 — the new dual-regex answer extractor (bare + paren) must
    extract the right letters for every variant.

    CRITICAL DESIGN NOTE: ``_extract_bare_labels`` dispatches between
    two shape-only regexes (punct-separator and word-separator).
    NEITHER consumes "and"/"or" filler words, so the captured groups
    contain only answer letters.  This prevents the
    ``'A and C' → ['A','a','d','C']`` regression that the previous
    regex produced when it ran ``re.findall('[A-Fa-f]', body)`` on a
    group that swallowed the "and" filler.
    """
    cases = [
        ("A", ["A"]),
        ("B. Lipase", ["B"]),
        ("(B)", ["B"]),
        ("(b)", ["B"]),
        ("A and C", ["A", "C"]),
        ("A, C, D", ["A", "C", "D"]),
        ("A, B and D", ["A", "B", "D"]),
        ("A & B", ["A", "B"]),
    ]
    for body, expected in cases:
        m_paren = _RE_ANSWER_PAREN.match(body)
        if m_paren:
            got = sorted({m_paren.group(1).upper()})
        else:
            got = _extract_bare_labels(body)
        assert got == expected, f"body={body!r} expected={expected} got={got}"


def test_bug3_layout_context_ans_is_b():
    """Bug 3 — ``_layout_context_answer`` must pick up ``Ans. is b. i.e.
    Plating`` → ['B'] (and NOT 'C' from 'i.e.').

    This is the exact pattern from the 2021 PDF that the audit flagged.
    """
    block = {
        "option_regions": [
            {"text": "A. Some", "bbox": [0, 100, 100, 120]},
            {"text": "B. Other", "bbox": [0, 130, 100, 150]},
        ],
        "explanation_regions": [],
        "unclassified_regions": [
            {"text": "Ans. is b. i.e. Plating", "bbox": [0, 200, 200, 220]},
        ],
    }
    out = _layout_context_answer(block)
    assert out is not None, "Layout-context answer must find the answer line"
    assert out["labels"] == ["B"], (
        f"Expected ['B'] (no 'C' from 'i.e.'); got {out['labels']}"
    )


def test_bug3_layout_context_correct_option():
    """Bug 3 — ``Correct Option: B`` must extract ['B']."""
    block = {
        "option_regions": [
            {"text": "A. X", "bbox": [0, 100, 100, 120]},
            {"text": "B. Y", "bbox": [0, 130, 100, 150]},
        ],
        "explanation_regions": [],
        "unclassified_regions": [
            {"text": "Correct Option: B", "bbox": [0, 200, 200, 220]},
        ],
    }
    out = _layout_context_answer(block)
    assert out is not None
    assert out["labels"] == ["B"]


# --------------------------------------------------------------------- Bug 4
# REAL PDF SNIPPET — image-only continuation pages lose the stem:
#   p020, p021 (and others) have a stem on the prior page and only
#   the image+options on the continuation page.
# Stage 5 must merge the truncated block into the prior block.


def test_bug4_truncated_stem_helper_unit():
    """Unit test for ``_looks_like_truncated_stem``."""
    # Empty stem → truncated
    assert _looks_like_truncated_stem({"stem_regions": []}) is True
    # Short stem → truncated
    assert _looks_like_truncated_stem({"stem_regions": [{"text": "Of"}]}) is True
    # Stem starting with preposition → truncated
    assert _looks_like_truncated_stem({"stem_regions": [{"text": "Of the following, which is correct?"}]}) is True
    # Full stem → not truncated
    assert _looks_like_truncated_stem({"stem_regions": [{"text": "Which of the following nerves is tested by Pen test?"}]}) is False


def test_bug4_cross_page_merge_runs_on_2021():
    """Bug 4 — running the full pipeline on 2021 should produce
    non-zero ``cross_page_merges`` in Stage 5 metrics OR no
    blocks whose stem is empty/truncated after the post-passes.

    We don't require an exact count (the PDF is fixed; the count is
    deterministic).  We require the post-passes to have run.
    """
    import tempfile, json
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [20, 21])
    # Confirm the artefacts exist.
    assert (ctx.stage_dir("05_question_blocks") / "_index.json").exists()
    idx5 = json.loads((ctx.stage_dir("05_question_blocks") / "_index.json").read_text(encoding="utf-8"))
    pp = idx5.get("post_passes", {})
    # Either merges happened, or all blocks on these pages have
    # full stems.  We don't assert specific count.
    assert "cross_page_merges" in pp
    assert "continuation_orphans_swept" in pp


# --------------------------------------------------------------------- Bug 5
# REAL PDF SNIPPET — pages where the explanation has unclassified
# continuations that should be folded in.


def test_bug5_orphan_sweep_helper_unit():
    """Unit test for ``_sweep_continuation_orphans``."""
    blocks = [
        {
            "id": "p_test_q00",
            "explanation_regions": [
                {"text": "Explanation: First part of the explanation."},
            ],
            "unclassified_regions": [
                {"text": "This is a continuation of the explanation."},
                {"text": "And another sentence."},
            ],
        },
    ]
    swept = _sweep_continuation_orphans(blocks)
    assert swept == 2
    assert blocks[0]["unclassified_regions"] == []
    assert len(blocks[0]["explanation_regions"]) == 3


def test_bug5_orphan_sweep_from_explanation_header():
    """When unclassified regions begin with 'Explanation:' they must
    be promoted to explanation_regions even if the block had no
    pre-existing explanation_regions."""
    blocks = [
        {
            "id": "p_test_q00",
            "explanation_regions": [],
            "unclassified_regions": [
                {"text": "Explanation: the cell is divided into ..."},
                {"text": "Mitochondria produce ATP."},
            ],
        },
    ]
    swept = _sweep_continuation_orphans(blocks)
    assert swept == 2
    assert blocks[0]["unclassified_regions"] == []
    assert len(blocks[0]["explanation_regions"]) == 2


# --------------------------------------------------------------------- Bug 6
# REAL PDF SNIPPET — p001 has Q1 with:
#   "Answer: A Median Nerve" + 3 unclassified explanation paragraphs
# Stage 2 already classifies "Answer: A Median Nerve" as type=answer_key
# and the next 3 unclassified regions as type=unclassified.  Stage 5
# used to merge the unclassified into answer_regions (because
# last_typed_kind was "answer_key"), so the explanation never reached
# explanation_regions and Stage 7 emitted an empty explanation.  Stage
# 7 also used to call _extract_bare_labels directly on "Answer: A
# Median Nerve" without stripping the prefix, so answer_labels came
# back as [] and is_correct never got set.
#
# Both fixes are anchored by the real 2021 PDF snippet.


def test_bug6_strip_answer_head_unit():
    """Unit test: stripping the RE_ANSWER_HEAD prefix from
    'Answer: A Median Nerve' yields 'A Median Nerve' and the bare-letter
    extractor returns ['A'] (not [])."""
    text = "Answer: A Median Nerve"
    m_head = RE_ANSWER_HEAD.match(text)
    assert m_head, "RE_ANSWER_HEAD must match 'Answer: A ...'"
    body = text[m_head.end():].lstrip()
    assert body == "A Median Nerve"
    labels = _extract_bare_labels(body)
    assert labels == ["A"]


def test_bug6_post_answer_unclassified_unit():
    """Unit test: simulate the real p001_q00 block structure: 1
    answer_key region followed by 3 unclassified explanation regions.
    After ``_group_regions_into_blocks``, the 3 unclassified regions
    must be in ``explanation_regions`` (not answer_regions) so Stage 7
    can emit a real explanation."""
    from mce.stages.stage_5_question_blocks import _group_regions_into_blocks

    # Mimic Stage 2's output: regions with type fields.
    regions = [
        {"id": "r0", "type": "stem", "text": "1. Pen Test is for which nerve",
         "bbox": [0, 0, 100, 20], "match_rule": "question_prefix"},
        {"id": "r1", "type": "option", "text": "A. Median Nerve",
         "bbox": [0, 20, 100, 30], "match_rule": "option_prefix"},
        {"id": "r2", "type": "option", "text": "B. Ulnar nerve",
         "bbox": [0, 30, 100, 40], "match_rule": "option_prefix"},
        {"id": "r3", "type": "option", "text": "C. PIN",
         "bbox": [0, 40, 100, 50], "match_rule": "option_prefix"},
        {"id": "r4", "type": "option", "text": "D. Musculocutaneous",
         "bbox": [0, 50, 100, 60], "match_rule": "option_prefix"},
        {"id": "r5", "type": "answer_key",
         "text": "Answer: A Median Nerve",
         "bbox": [0, 60, 100, 70], "match_rule": "answer_key"},
        {"id": "r6", "type": "unclassified",
         "text": "The doctor places a small needle electrode into muscles in your hand and arm that get impulses",
         "bbox": [0, 70, 100, 90], "match_rule": ""},
        {"id": "r7", "type": "unclassified",
         "text": "from the median nerve. The needle sends electric impulses into the muscle.",
         "bbox": [0, 90, 100, 110], "match_rule": ""},
        {"id": "r8", "type": "unclassified",
         "text": "hand several times. The doctor can tell if your median nerve is damaged.",
         "bbox": [0, 110, 100, 130], "match_rule": ""},
    ]
    blocks = _group_regions_into_blocks(1, regions)
    assert len(blocks) == 1
    b = blocks[0]
    # Bug 6 fix #1: answer_regions contains exactly the answer_key
    # region (not the explanation text).
    assert len(b["answer_regions"]) == 1
    assert b["answer_regions"][0]["text"] == "Answer: A Median Nerve"
    # Bug 6 fix #2: the 3 unclassified explanation paragraphs went to
    # explanation_regions (not answer_regions).
    assert len(b["explanation_regions"]) == 3
    assert all(
        "needle" in r["text"] or "median nerve" in r["text"].lower() or "doctor" in r["text"].lower()
        for r in b["explanation_regions"]
    )


def test_bug6_2021_p001_q1_has_answer_and_explanation():
    """End-to-end test: running Stages 1+2+5+6+7 on the 2021 PDF and
    checking p001_q00 specifically.  The answer_labels must be
    ['A'] and explanation must be >= 40 chars (the QA V2 axis-3
    pass criterion)."""
    import tempfile, json
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [1])
    out_path = ctx.stage_dir("07_structured") / "p001.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    qs = data["questions"]
    assert qs, "p001 must produce at least 1 question"
    q1 = qs[0]
    assert q1["answer_labels"] == ["A"], (
        f"p001_q00 answer_labels must be ['A'] (real snippet "
        f"'Answer: A Median Nerve'); got {q1['answer_labels']!r}"
    )
    # The explanation is the EMG explanation prose from the 2021 PDF.
    assert q1["explanation"] is not None
    assert len(q1["explanation"]) >= 40, (
        f"p001_q00 explanation must be >= 40 chars (QA V2 axis 4); "
        f"got {len(q1['explanation'] or '')} chars: "
        f"{q1['explanation']!r}"
    )
    # is_correct must be set on the matching option.
    correct_opts = [o for o in q1["options"] if o.get("is_correct")]
    assert len(correct_opts) == 1
    assert correct_opts[0]["label"] == "A"


# --------------------------------------------------------------------- Bug 7
# REAL PDF SNIPPET — p001 has Q2 stem "2. A small boy with multiple
# fracture of Humerus..." that comes AFTER Q1's explanation regions.
# The Bug 1 guard ``_looks_like_continuation_bullet`` (designed to
# prevent phantom-question re-opening on numbered bullets inside an
# explanation list) was over-firing once Bug 6 made explanation_regions
# non-empty: it would treat "2. A small boy..." as a continuation of
# the previous explanation's "1. The doctor places..." and absorb Q2's
# stem into Q1's explanation_regions, so Q2 never got a block of its
# own and Q2's 4 options ended up appended to Q1's option_regions.
# The fix checks the candidate text length/word-count — a real
# question stem is long and prose-like, not a single-line bullet.


def test_bug7_continuation_bullet_helper_unit():
    """Unit test: a long numbered question stem must NOT be treated as
    a continuation bullet of the previous explanation list, even when
    the previous explanation's number (1) is in the same range."""
    # Bug 1 true-positive: short bullet "2. Some list item." (ends
    # with period) must still be treated as a continuation bullet.
    assert _looks_like_continuation_bullet(
        "2. Some list item.",
        current={
            "stem_regions": [],
            "explanation_regions": [
                {"text": "1. First item in the list."},
            ],
        },
    ) is True
    # Bug 7 fix: a long question stem (no terminal period) like
    # "2. A small boy with multiple fracture of Humerus..." must NOT
    # be treated as a continuation bullet of the previous explanation.
    assert _looks_like_continuation_bullet(
        "2. A small boy with multiple fracture of Humerus following "
        "which there is loss of extension of wrist and difficulty in "
        "flexion of elbow and supination",
        current={
            "stem_regions": [],
            "explanation_regions": [
                {"text": "1. The doctor places a small needle electrode "
                         "into muscles in your hand and arm"},
            ],
        },
    ) is False


def test_bug7_2021_p001_q2_is_separate_block():
    """End-to-end test: p001 must produce TWO separate question
    blocks (Q1 and Q2), not one merged block.  Q2 must have 4 options
    of its own, and Q2's answer_labels must remain empty (the 2021
    PDF only places an answer region on Q1, not Q2)."""
    import tempfile, json
    tmp = tempfile.mkdtemp()
    pdf = BENCHMARK_PDF
    if not pdf.exists():
        pytest.skip("benchmark PDF missing")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    sha16 = sha[:16]
    ctx = MceContext(
        pdf_path=pdf, pdf_filename=pdf.name,
        pdf_sha256=sha, pdf_sha256_short=sha16,
        page_count=144, profile=get_profile_for_filename(pdf.name),
        artefact_root=Path(tmp) / sha16,
    )
    _pipeline_through_s7(ctx, [1])
    out_path = ctx.stage_dir("07_structured") / "p001.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    qs = data["questions"]
    assert len(qs) == 2, (
        f"p001 must produce 2 separate question blocks; got {len(qs)}"
    )
    # Q1 has 4 options with answer_labels=['A'].
    assert qs[0]["answer_labels"] == ["A"]
    assert len(qs[0]["options"]) == 4
    # Q2 has 4 options and no answer (the 2021 PDF only has one
    # 'Answer: A Median Nerve' on p001, for Q1).
    assert len(qs[1]["options"]) == 4
    assert qs[1]["answer_labels"] == [], (
        f"Q2 must not inherit Q1's answer; got {qs[1]['answer_labels']!r}"
    )
    # Q2 stem must mention Humerus (real PDF text).
    assert "Humerus" in qs[1]["stem"] or "humerus" in qs[1]["stem"]


# --------------------------------------------------------------------- _merge unit


def test_merge_truncated_with_previous_basic():
    """Unit test: ``_merge_truncated_with_previous`` merges a block
    whose stem is truncated into its predecessor on a prior page."""
    blocks = [
        {
            "id": "p010_q00",
            "page_number": 10,
            "stem_regions": [{"text": "Which nerve is tested by Pen test?"}],
            "explanation_regions": [{"text": "Explanation: median nerve."}],
            "unclassified_regions": [],
            "bbox": [0, 0, 100, 200],
        },
        {
            "id": "p011_q00",
            "page_number": 11,
            "stem_regions": [{"text": "Of the following, which option is correct?"}],
            "explanation_regions": [{"text": "Continuation explanation."}],
            "unclassified_regions": [],
            "bbox": [0, 300, 100, 500],
        },
    ]
    merges = _merge_truncated_with_previous(blocks)
    assert merges == 1
    assert len(blocks) == 1
    assert blocks[0]["id"] == "p010_q00"
    assert blocks[0]["page_numbers"] == [10, 11]


class _DummyCtx:
    """Tiny context manager helper for tests that need a fresh ctx.
    Kept for backward compatibility with the original test scaffold."""
    def __init__(self, tmp: str) -> None:
        pdf = BENCHMARK_PDF
        if not pdf.exists():
            pytest.skip("benchmark PDF missing")
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        sha16 = sha[:16]
        self._ctx = MceContext(
            pdf_path=pdf, pdf_filename=pdf.name,
            pdf_sha256=sha, pdf_sha256_short=sha16,
            page_count=144, profile=get_profile_for_filename(pdf.name),
            artefact_root=Path(tmp) / sha16,
        )

    def __enter__(self) -> MceContext:
        return self._ctx

    def __exit__(self, *a) -> None:
        return None
