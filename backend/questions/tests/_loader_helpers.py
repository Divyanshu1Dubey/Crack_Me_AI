"""
_loader_helpers.py — Tiny helpers for writing Django fixture rows in tests.

Used by ``test_load_exam_fixture_root_cause.py`` to build a minimal
fixture on disk without committing multi-megabyte JSON blobs. The
shape matches what ``load_exam_fixture`` expects:

    [
      {"model": "questions.subject", "pk": 1,
       "fields": {"code": "MED", "name": "Medicine", "exam_type": "cms", ...}},
      {"model": "questions.question", "pk": 100,
       "fields": {"subject": "MED", "question_text": "...", ...}},
    ]
"""
from __future__ import annotations

from typing import Any


def build_loader_fixture(
    *,
    subject_code: str = "MED",
    subject_name: str = "Medicine",
    question_text: str = "Stem text",
    option_a: str = "A",
    option_b: str = "B",
    option_c: str = "C",
    option_d: str = "D",
    correct_answer: str = "B",
    year: int = 2024,
    difficulty: str = "medium",
    exam_type: str = "cms",
    exam_track_code: str = "cms",
    question_pk: int | None = None,
) -> list[dict[str, Any]]:
    """Return a minimal valid Django fixture payload.

    We leave the Question's ``pk`` unset by default so the loader
    exercises the dedup-and-create branch (``subject_id`` is set
    explicitly there). The legacy ``pk is not None`` branch is left
    alone on purpose; it's a separate code path and not what these
    tests are validating.
    """
    return [
        {
            "model": "questions.examtrack",
            "pk": 1,
            "fields": {
                "code": exam_track_code,
                "name": "UPSC CMS",
                "conducting_body": "UPSC",
            },
        },
        {
            "model": "questions.subject",
            "pk": 1,
            "fields": {
                "code": subject_code,
                "name": subject_name,
                "exam_type": exam_type,
                "exam_track": 1,
                "paper": 0,
                "description": "",
                "icon": "",
                "color": "#10B981",
            },
        },
        {
            "model": "questions.question",
            "pk": question_pk,
            "fields": {
                "subject": subject_code,
                "exam_type": exam_type,
                "exam_track": 1,
                "question_text": question_text,
                "option_a": option_a,
                "option_b": option_b,
                "option_c": option_c,
                "option_d": option_d,
                "correct_answer": correct_answer,
                "year": year,
                "difficulty": difficulty,
            },
        },
    ]