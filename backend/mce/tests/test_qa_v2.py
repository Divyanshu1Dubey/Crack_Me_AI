"""Tests for QA V2 — per-question 9-axis educational-fidelity scoring.

Run: cd backend && python -m pytest mce/tests/test_qa_v2.py -v
"""
from __future__ import annotations

from mce.qa_v2 import (
    score_question, is_page_importable,
    axis_1_stem_complete, axis_2_options_complete, axis_3_answer_correct,
    axis_4_explanation_complete, axis_5_image_attached_if_referenced,
    axis_6_image_placement, axis_8_clinical_pearl, axis_9_reference_field_present,
)


def _good_question() -> dict:
    """A fully populated question that should pass all 9 axes."""
    return {
        "stem": ("A 30-year-old patient presents with hypertension and was "
                 "prescribed amlodipine 5 mg once daily. What is the drug's "
                 "mechanism of action?"),
        "options": [
            {"label": "A", "text": "Calcium channel blocker", "is_correct": True},
            {"label": "B", "text": "Beta blocker", "is_correct": False},
            {"label": "C", "text": "ACE inhibitor", "is_correct": False},
            {"label": "D", "text": "Diuretic", "is_correct": False},
        ],
        "answer_labels": ["A"],
        "explanation": ("Amlodipine is a dihydropyridine calcium channel "
                        "blocker that inhibits L-type calcium channels in "
                        "vascular smooth muscle, reducing peripheral "
                        "vascular resistance and lowering blood pressure."),
        "image_ids": [],
        "image_bboxes": [],
        "asset_ids": [],
        "clinical_pearl": "Always check for peripheral edema with amlodipine.",
        "references": [{"citation_text": "Harrison 21e p.1245"}],
        "bbox": [0, 0, 100, 100],
    }


def test_perfect_question_is_production_ready():
    s = score_question(_good_question())
    assert s["status"] == "Production Ready", s
    assert s["passing_count"] == 9, s


def test_short_stem_fails_axis_1():
    q = _good_question()
    q["stem"] = "What is X?"
    s = score_question(q)
    assert s["axes"]["stem_complete"] is False
    assert "stem_complete" in s["failing_axes"]


def test_footer_in_stem_fails_axis_1():
    q = _good_question()
    q["stem"] = ("A 30-year-old patient presents with hypertension. "
                 "MEDICAL JUNCTION TEAM")
    s = score_question(q)
    assert s["axes"]["stem_complete"] is False


def test_missing_options_fails_axis_2():
    q = _good_question()
    q["options"] = []
    s = score_question(q)
    assert s["axes"]["options_complete"] is False


def test_unlabeled_option_fails_axis_2():
    q = _good_question()
    q["options"] = [
        {"label": "A", "text": "Calcium channel blocker", "is_correct": True},
        {"label": "B", "text": "Beta blocker", "is_correct": False},
        {"label": None, "text": "Some phantom option", "is_correct": False},
        {"label": "D", "text": "Diuretic", "is_correct": False},
    ]
    s = score_question(q)
    assert s["axes"]["options_complete"] is False


def test_missing_answer_fails_axis_3():
    q = _good_question()
    q["answer_labels"] = []
    # Mark no option correct.
    for o in q["options"]:
        o["is_correct"] = False
    s = score_question(q)
    assert s["axes"]["answer_correct"] is False


def test_answer_mismatched_to_options_fails_axis_3():
    q = _good_question()
    q["answer_labels"] = ["B"]   # but option B has is_correct=False
    s = score_question(q)
    assert s["axes"]["answer_correct"] is False


def test_short_explanation_fails_axis_4():
    q = _good_question()
    q["explanation"] = "It's a CCB."
    s = score_question(q)
    assert s["axes"]["explanation_complete"] is False


def test_image_referenced_but_not_attached_fails_axis_5():
    q = _good_question()
    q["stem"] = ("A 30-year-old patient. Identify the abnormality shown "
                 "in the radiograph.")
    q["image_ids"] = []
    s = score_question(q)
    assert s["axes"]["image_attached_if_referenced"] is False


def test_image_referenced_and_attached_passes_axis_5_and_6():
    q = _good_question()
    q["stem"] = ("A 30-year-old patient. Identify the abnormality shown "
                 "in the radiograph.")
    q["image_ids"] = ["img_001"]
    q["image_bboxes"] = [[10, 10, 90, 90]]  # inside q.bbox [0,0,100,100]
    s = score_question(q)
    assert s["axes"]["image_attached_if_referenced"] is True
    assert s["axes"]["image_placement"] is True


def test_image_attached_but_outside_question_bbox_fails_axis_6():
    q = _good_question()
    q["stem"] = ("A 30-year-old patient. Identify the abnormality shown "
                 "in the radiograph.")
    q["image_ids"] = ["img_001"]
    q["image_bboxes"] = [[500, 500, 600, 600]]  # outside q.bbox
    s = score_question(q)
    assert s["axes"]["image_placement"] is False


def test_missing_clinical_pearl_still_passes_when_optional_axis():
    q = _good_question()
    q["clinical_pearl"] = ""
    s = score_question(q)
    # Optional axis failing shouldn't drop below Production Ready.
    assert s["status"] == "Production Ready"


def test_status_thresholds():
    # 9 axes pass → Production Ready
    q = _good_question()
    assert score_question(q)["status"] == "Production Ready"
    # 5 axes pass → Needs Review
    q = _good_question()
    q["stem"] = "tiny"  # fails axis 1
    q["explanation"] = ""  # fails axis 4
    q["image_ids"] = []  # ok (no image ref)
    q["clinical_pearl"] = ""  # fails axis 8
    q["references"] = None  # fails axis 9
    s = score_question(q)
    assert s["status"] == "Needs Review", s
    # < 5 axes pass → Extraction Failure
    q = _good_question()
    q["stem"] = "tiny"
    q["options"] = []
    q["answer_labels"] = []
    q["explanation"] = ""
    q["references"] = None
    s = score_question(q)
    assert s["status"] == "Extraction Failure", s


def test_is_page_importable_blocks_extraction_failures():
    scores = [
        score_question(_good_question()),
        score_question(_good_question()),
        score_question({}),  # Extraction Failure
    ]
    assert is_page_importable(scores) is False


def test_is_page_importable_allows_needs_review():
    q = _good_question()
    q["explanation"] = ""  # needs review
    scores = [score_question(q), score_question(_good_question())]
    assert is_page_importable(scores) is True


def test_real_p130_q188_from_proposal_is_extraction_failure():
    """Per PROPOSED_QA_V2.md: p130 Q188 has stem containing
    'MEDICAL JUNCTION TEAM' footer, options=[], answer_labels=[].
    All required axes must fail → Extraction Failure.
    """
    q = {
        "stem": "188. A 30 year old female with sterile Pyuria. Radiograph is shown. "
                "Diagnosis is MEDICAL JUNCTION TEAM",
        "options": [],
        "answer_labels": [],
        "explanation": None,
        "image_ids": ["p130_img01_26a99fdff5474441"],
        "image_bboxes": [[100, 100, 200, 200]],
        "asset_ids": [],
        "clinical_pearl": None,
        "references": [],
        "bbox": [0, 600, 600, 800],   # image is mid-page; not inside q bbox
    }
    s = score_question(q)
    assert s["status"] == "Extraction Failure", s
    # Stem, options, answer, explanation must all be in failing list.
    failing = set(s["failing_axes"])
    assert "stem_complete" in failing
    assert "options_complete" in failing
    assert "answer_correct" in failing
    assert "explanation_complete" in failing