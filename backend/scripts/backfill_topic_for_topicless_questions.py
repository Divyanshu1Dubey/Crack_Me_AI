"""Backfill topic for expert-curated mocktest questions.

The mocktest ingestion (commit `65d7690`) imported 3,315 expert-curated
questions without running topic assignment. As a result, those questions
show "Topic unavailable" on the frontend question bank (see
`ExamQuestionBank.tsx`, topic badge fallback).

This script targets *only* questions where `topic IS NULL` and re-uses
the AI classifier pipeline already in `material_importer.ai_classifier`,
falling back to the heuristic classifier when AI keys are unavailable.

Usage:
    cd backend
    python manage.py shell < ../scripts/backfill_topic_for_topicless_questions.py
    # or as a standalone script via `python ...` with DJANGO_SETTINGS_MODULE

The script is idempotent: questions that already have a topic are skipped.
A single AI failure on one question never aborts the run.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import django
from django.apps import apps as django_apps

# Allow running as a standalone script: `python scripts/backfill_topic_...`
if not django_apps.ready:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
    django.setup()

from material_importer.ai_classifier import HeuristicClassifier, ClassificationResult  # noqa: E402
from material_importer.parser.dataclasses import ParsedQuestion  # noqa: E402
from questions.models import Question, Topic  # noqa: E402

log = logging.getLogger("backfill_topic")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _classify_via_ai(pq: ParsedQuestion) -> ClassificationResult | None:
    """Best-effort AI topic classification. Returns None on any failure."""
    try:
        from ai_engine.services import AIService  # type: ignore
        svc = AIService()
    except Exception as exc:  # pragma: no cover - service import edge cases
        log.warning("AI service unavailable: %s", exc)
        return None

    prompt = (
        "You are classifying a medical MCQ for the UPSC CMS exam bank.\n\n"
        f"Question: {pq.question_text or ''}\n\n"
        "Return ONLY a JSON object with these keys (no commentary):\n"
        '{"subject": "<known subject>", "topic": "<3-6 word topic>"}\n'
    )
    try:
        text = svc._call_ai(
            prompt,
            system="Return valid JSON only. No commentary.",
            temperature=0.1,
            max_tokens=200,
        )
    except Exception as exc:
        log.warning("AI call failed: %s", exc)
        return None

    if not text:
        return None

    import json
    import re

    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-z]*\n?", "", t).rstrip("`").strip()
    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    topic_name = str(data.get("topic") or "").strip()
    if not topic_name:
        return None
    return ClassificationResult(subject=str(data.get("subject") or ""), topic=topic_name, source="ai")


def run(limit: int = 500, use_ai: bool = True, sleep_ms: int = 250) -> dict:
    """Backfill `topic` for up to `limit` topic-less questions.

    Returns a stats dict {processed, topic_assigned, ai_calls, heuristic_only, skipped}.
    """
    qs = (
        Question.objects.filter(topic__isnull=True)
        .exclude(subject__isnull=True)
        .order_by("id")[:limit]
    )
    total = qs.count()
    if total == 0:
        log.info("No topic-less questions remain.")
        return {"processed": 0, "topic_assigned": 0, "ai_calls": 0, "heuristic_only": 0, "skipped": 0}

    log.info("Found %d topic-less questions (limit=%d).", total, limit)

    heuristic = HeuristicClassifier()
    stats = {"processed": 0, "topic_assigned": 0, "ai_calls": 0, "heuristic_only": 0, "skipped": 0}

    for q in qs:
        stats["processed"] += 1

        pq = ParsedQuestion(
            position_index=q.id,
            question_text=q.question_text or "",
            option_a=q.option_a or "",
            option_b=q.option_b or "",
            option_c=q.option_c or "",
            option_d=q.option_d or "",
            explanation=q.explanation or "",
        )

        # 1) Heuristic pass (always, free, never fails).
        result = heuristic.classify(pq)

        # 2) Optional AI refinement (slow, costs tokens, but topic-aware).
        if use_ai:
            ai_result = _classify_via_ai(pq)
            if ai_result and ai_result.topic:
                result.topic = ai_result.topic
                stats["ai_calls"] += 1
                time.sleep(max(0, sleep_ms) / 1000.0)
            else:
                stats["heuristic_only"] += 1
        else:
            stats["heuristic_only"] += 1

        topic_name = (result.topic or "").strip()
        if not topic_name:
            stats["skipped"] += 1
            log.debug("No topic for Q%s (subject=%s); skipping.", q.id, q.subject_id)
            continue

        # Reject obviously-bad topics: AI refusals, "n/a", single-character noise,
        # or anything shorter than 3 chars after stripping. Also skip rows
        # where the question text is empty — AI hallucinates a topic from
        # nothing and we end up with garbage like "Not provided".
        if topic_name.lower() in {"n/a", "na", "none", "null", "not provided", "not applicable", "unknown"}:
            stats["skipped"] += 1
            log.debug("Refused junk topic '%s' for Q%s; skipping.", topic_name, q.id)
            continue
        if len(topic_name) < 3:
            stats["skipped"] += 1
            log.debug("Topic '%s' too short for Q%s; skipping.", topic_name, q.id)
            continue
        if not (q.question_text or "").strip():
            stats["skipped"] += 1
            log.debug("Empty question_text for Q%s; skipping.", q.id)
            continue

        # 3) Persist under the question's existing subject so the topic_id
        #    matches what the frontend already sees for that question.
        topic, _ = Topic.objects.get_or_create(subject=q.subject, name=topic_name[:200])
        q.topic = topic
        q.save(update_fields=["topic"])
        stats["topic_assigned"] += 1
        log.info("Q%s → %s › %s", q.id, q.subject.name if q.subject_id else "?", topic.name)

    log.info("Done. stats=%s", stats)
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill topic for topic-less questions.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--no-ai", action="store_true", help="Heuristic only (no AI calls).")
    parser.add_argument("--sleep-ms", type=int, default=250)
    args = parser.parse_args()

    run(limit=args.limit, use_ai=not args.no_ai, sleep_ms=args.sleep_ms)
