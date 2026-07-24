"""Regression tests for MCE sub-stage 2.1.

Covers:
- ExamProfile registry round-trip
- detect_exam_from_filename + get_profile_for_filename
- SourceTrace immutability + confidence clamp [0, 1] + JSON round-trip
- ParsedQuestion preserves unclassified_blocks + clinical_pearl + mnemonic + bbox
- ImageRecord preserves role + modality + page_spans
- Frozen dataclasses (ExamProfile) reject mutation
- Keyword map drops in for the legacy topic_mapper

Run with: cd backend && python -m pytest mce/tests/test_profiles_and_types.py -v
"""
from __future__ import annotations

import json

import pytest

from mce.profiles import (
    ExamProfile,
    detect_exam_from_filename,
    get_profile,
    get_profile_for_filename,
    list_profiles,
)
from mce.types import ImageRecord, ParsedQuestion, Region, SourceTrace


# ----------------------------------------------------------- registry


@pytest.mark.parametrize("name", list_profiles())
def test_profile_registry_roundtrip(name: str):
    p = get_profile(name)
    assert isinstance(p, ExamProfile)
    assert p.name == name
    assert p.exam_type == name
    assert p.exam_source
    assert 0 < len(p.subjects) <= 25
    assert p.option_count_min >= 1
    assert p.option_count_max >= p.option_count_min
    assert p.color_accent.startswith("#") and len(p.color_accent) == 7
    assert p.icon


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf", "neet_pg"),
        ("NEET_PG_2020_PYQ.pdf", "neet_pg"),
        ("INI_CET_Nov_2023.pdf", "ini_cet"),
        ("AIIMS_PGI_2022_PYQ.pdf", "ini_cet"),
        ("FMGE_2023_Screening.pdf", "fmge"),
        ("USMLE_Step1_Rx.pdf", "usmle"),
        ("PLAB_Blueprint_2024.pdf", "plab"),
    ],
)
def test_detect_exam_from_filename(filename, expected):
    assert detect_exam_from_filename(filename) == expected


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("NEET-PG-2021-Question-Paper-With-Solutions-PDF-1.pdf", "neet_pg"),
        ("unknown_file.pdf", "neet_pg"),
        ("", "neet_pg"),
    ],
)
def test_get_profile_for_filename_fallback(filename, expected):
    assert get_profile_for_filename(filename).name == expected


def test_exam_profile_is_frozen():
    p = get_profile("neet_pg")
    with pytest.raises(Exception):
        p.exam_type = "ini_cet"  # type: ignore[misc]


# ----------------------------------------------------------- trace


def test_source_trace_frozen_and_confidence_clamped():
    t = SourceTrace.make(
        pdf_filename="NEET-PG-2021.pdf",
        pdf_sha256="8ebea8995a4ade7955822322fb94a502fdab280e9792c786c74bbdb95a544282",
        pdf_sha256_short="8ebea8995a4ade7",
        page_number=38,
        bbox=(72.0, 200.0, 524.0, 410.0),
        extraction_engine="layout_heuristic",
        pipeline_stage="stage_2_layout",
        confidence=0.92,
    )
    with pytest.raises(Exception):
        t.confidence = 0.5  # type: ignore[misc]

    d = t.to_dict()
    assert d["pdf_sha256_short"] == "8ebea8995a4ade7"
    assert d["bbox"] == [72.0, 200.0, 524.0, 410.0]
    assert d["confidence"] == 0.92

    t_low = SourceTrace.make(
        pdf_filename="x", pdf_sha256="y", pdf_sha256_short="y",
        page_number=1, bbox=(0, 0, 1, 1), extraction_engine="x",
        pipeline_stage="x", confidence=-0.5,
    )
    t_high = SourceTrace.make(
        pdf_filename="x", pdf_sha256="y", pdf_sha256_short="y",
        page_number=1, bbox=(0, 0, 1, 1), extraction_engine="x",
        pipeline_stage="x", confidence=99.0,
    )
    assert t_low.confidence == 0.0
    assert t_high.confidence == 1.0
    json.dumps(d)


# ----------------------------------------------------------- types


def test_parsed_question_preserves_unclassified_and_pearl():
    t = SourceTrace.make(
        pdf_filename="x", pdf_sha256="y", pdf_sha256_short="y",
        page_number=38, bbox=(72.0, 200.0, 524.0, 410.0),
        extraction_engine="layout_heuristic", pipeline_stage="stage_2_layout",
        confidence=0.92,
    )
    r = Region(
        id="p038.b7", type="stem", page_number=38,
        bbox=(72, 200, 524, 410), text="A 23-year-old male...",
        confidence=0.91, source_trace=t,
    )
    qd = ParsedQuestion(
        id="q38", source_sha16="8ebea8995a4ade7", page_number=38,
        stem="A 23-year-old male presents with chest pain",
        question_number_in_pdf=1,
    )
    qd.bbox = (72.0, 200.0, 524.0, 410.0)
    qd.image_ids = ["p038_img03"]
    qd.clinical_pearl = "Always rule out PE in pleuritic chest pain"
    qd.mnemonic = "PES - Pleuritic, Exertional, Sudden"
    qd.unclassified_blocks.append(r)

    d = qd.to_dict()
    assert d["unclassified_blocks"][0]["type"] == "stem"
    assert d["clinical_pearl"].startswith("Always")
    assert d["mnemonic"].startswith("PES")
    assert d["image_ids"] == ["p038_img03"]
    assert d["bbox"] == [72.0, 200.0, 524.0, 410.0]


def test_image_record_role_modality_page_spans():
    t = SourceTrace.make(
        pdf_filename="x", pdf_sha256="y", pdf_sha256_short="y",
        page_number=38, bbox=(0, 0, 1, 1),
        extraction_engine="stage_3_images", pipeline_stage="stage_3_images",
        confidence=0.9,
    )
    ir = ImageRecord(
        id="p038_img03", source_sha16="8ebea8995a4ade7",
        page_number=38, image_index_in_page=3, file_path="/tmp/x.png",
        role="stem", modality="ct", bbox=(100, 220, 300, 400),
        source_trace=t,
    )
    ir.page_spans.append((39, (300, 220, 500, 400)))
    d = ir.to_dict()
    assert d["role"] == "stem"
    assert d["modality"] == "ct"
    assert d["page_spans"] == [(39, [300.0, 220.0, 500.0, 400.0])]


# ----------------------------------------------------------- keyword map


@pytest.mark.parametrize(
    "stem,expected_subject",
    [
        (
            "Biopsy of lymph node shows Reed-Sternberg cell, neoplastic infiltrate",
            "Pathology",
        ),
        (
            "Mechanism of action of beta blocker, dose titration",
            "Pharmacology",
        ),
        (
            "Pregnancy with severe preeclampsia at 34 weeks gestation",
            "OBG",
        ),
    ],
)
def test_neet_pg_keyword_map_drop_in(stem, expected_subject):
    """The NEET_PG keyword map is a drop-in for the legacy topic_mapper.

    Note: the legacy table has known substring-collision bugs (e.g. ``ear``
    matches ``year``) that will be fixed in a later sub-stage. These cases
    are chosen so they avoid those collisions.
    """
    neet = get_profile("neet_pg")
    text = stem.lower()
    best = (0, None)
    for subj, kws in neet.subject_keywords.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best[0]:
            best = (score, subj)
    assert best[1] == expected_subject, (stem, best, expected_subject)
