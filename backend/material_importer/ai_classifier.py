"""AI classification for imported records.

Two-stage design:

  * Stage 1 — `HeuristicClassifier` (always runs, ~ms)
      Maps content keywords to subject labels. Used as the cheap first
      pass and as the answer when the AI service is unreachable (404,
      network failure, empty result).

  * Stage 2 — `AIClassifier` (opt-in, off by default in tests)
      Calls the existing RoundRobin AI service with a tight prompt so
      a single provider call returns subject/topic/difficulty/bloom.
      Wrapped in `try/except so a single failure never blocks an import.

This module is deliberately side-effect-light: nothing is written to the
DB here. Callers (`ingest_service.py`) persist the `ClassificationResult`
on the staged `ExtractedQuestion` row.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from .parser.dataclasses import ParsedQuestion
from .parser.subject_classifier import classify_difficulty, classify_subject

log = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    subject: str = ""
    topic: str = ""
    difficulty: str = "medium"
    bloom_level: str = "apply"
    clinical_importance: str = "moderate"
    exam_track: str = "cms"
    is_image_based: bool = False
    is_one_liner: bool = False
    is_high_yield: bool = False
    confidence: float = 0.0
    source: str = "heuristic"
    raw: dict | None = None


class HeuristicClassifier:
    """Pure-Python fallback. Never fails, always returns a result."""

    def classify(self, q: ParsedQuestion) -> ClassificationResult:
        stem = (q.question_text or "") + " " + (q.explanation or "")
        subject, confidence = classify_subject(stem)
        difficulty = classify_difficulty(q.question_text or "")
        one_liner = len(q.question_text or "") < 120
        image_based = bool(q.image_refs)
        return ClassificationResult(
            subject=subject or "",
            difficulty=difficulty,
            bloom_level="apply" if (q.question_text and len(q.question_text) > 200) else "recall",
            clinical_importance="moderate",
            exam_track="cms",
            is_image_based=image_based,
            is_one_liner=one_liner,
            is_high_yield=confidence > 0.15,
            confidence=confidence,
            source="heuristic",
            raw={"subject": subject, "difficulty": difficulty, "confidence": confidence},
        )


class AIClassifier:
    """Optional: calls the existing `ai_engine.services.AIService`."""

    _PROMPT = """You are classifying a medical MCQ for the UPSC CMS exam bank.

Question:
{stem}

Options:
A: {a}
B: {b}
C: {c}
D: {d}

Return ONLY a JSON object with these keys (no commentary):
{{
  "subject": "Medicine|Surgery|OBGY|Pediatrics|PSM|Anesthesia|Orthopaedics|Dermatology|Ophthalmology|ENT|Psychiatry",
  "topic": "<3-6 word topic>",
  "difficulty": "easy|medium|hard",
  "bloom_level": "recall|understand|apply|analyze|evaluate",
  "clinical_importance": "low|moderate|high",
  "is_image_based": true|false,
  "is_one_liner": true|false,
  "is_high_yield": true|false,
  "exam_track": "cms|neet_pg|ini_cet|inicet",
  "confidence": 0.0-1.0
}}
"""

    def __init__(self) -> None:
        # Lazy init so Django startup is fast.
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        try:
            from ai_engine.services import ai_service  # type: ignore
            self._service = ai_service
        except Exception as exc:  # pragma: no cover
            log.warning("AI service unavailable: %s", exc)
            self._service = None
        return self._service

    def classify(self, q: ParsedQuestion, fallback: ClassificationResult | None = None) -> ClassificationResult:
        svc = self._get_service()
        if svc is None:
            return fallback or HeuristicClassifier().classify(q)
        try:
            prompt = self._PROMPT.format(
                stem=q.question_text or "",
                a=q.option_a or "", b=q.option_b or "",
                c=q.option_c or "", d=q.option_d or "",
            )
            text = svc.ask(prompt, mode="classification")
            return self._parse_response(text, fallback)
        except Exception as exc:  # pragma: no cover - network/quota errors
            log.warning("AI classification failed: %s", exc)
            return fallback or HeuristicClassifier().classify(q)

    @staticmethod
    def _parse_response(text: str, fallback: ClassificationResult | None) -> ClassificationResult:
        if not text:
            return fallback or ClassificationResult()
        # Strip markdown fences if present.
        t = text.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-z]*\n?", "", t).rstrip("`").strip()
        # Pull first {...} block.
        m = re.search(r"\{[\s\S]*\}", t)
        if not m:
            return fallback or ClassificationResult()
        try:
            data = json.loads(m.group(0))
        except Exception:
            return fallback or ClassificationResult()
        return ClassificationResult(
            subject=str(data.get("subject") or (fallback.subject if fallback else "")),
            topic=str(data.get("topic") or ""),
            difficulty=str(data.get("difficulty") or (fallback.difficulty if fallback else "medium")),
            bloom_level=str(data.get("bloom_level") or (fallback.bloom_level if fallback else "apply")),
            clinical_importance=str(data.get("clinical_importance") or "moderate"),
            exam_track=str(data.get("exam_track") or "cms"),
            is_image_based=bool(data.get("is_image_based", False)),
            is_one_liner=bool(data.get("is_one_liner", False)),
            is_high_yield=bool(data.get("is_high_yield", False)),
            confidence=float(data.get("confidence") or (fallback.confidence if fallback else 0.0)),
            source="ai",
            raw=data,
        )


def classify_question(q: ParsedQuestion, use_ai: bool = False) -> ClassificationResult:
    """Public helper used by ingest_service.py."""
    heuristic = HeuristicClassifier().classify(q)
    if not use_ai:
        return heuristic
    return AIClassifier().classify(q, fallback=heuristic)
