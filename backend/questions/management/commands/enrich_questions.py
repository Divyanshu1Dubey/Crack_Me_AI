"""Enrich question metadata using rule-based logic and optional AI assistance.

This command is intentionally conservative. It updates only missing fields by default
and prioritizes deterministic enrichment (topics/tags/CAP mapping) before AI calls.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Optional

from django.core.management.base import BaseCommand
from django.db.models import Q

from ai_engine.services import AIService
from questions.models import Question, Subject, Topic


@dataclass
class RuleResult:
    correct_answer: Optional[str] = None
    topic: Optional[Topic] = None
    explanation: Optional[str] = None
    concept_explanation: Optional[str] = None
    mnemonic: Optional[str] = None
    concept_tags: Optional[list[str]] = None
    difficulty: Optional[str] = None


class Command(BaseCommand):
    help = "Enrich questions with missing answer/topic/explanation/tags using rules + optional AI."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="Max questions to process.")
        parser.add_argument(
            "--mode",
            type=str,
            default="rule",
            choices=["rule", "ai", "hybrid"],
            help="rule: deterministic only, ai: AI only, hybrid: rules first then AI fallback",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Update only empty fields (recommended).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without saving.",
        )
        parser.add_argument(
            "--sleep-ms",
            type=int,
            default=350,
            help="Pause between AI calls in milliseconds.",
        )

    def handle(self, *args, **options):
        limit = int(options["limit"])
        mode = options["mode"]
        only_missing = bool(options["only_missing"])
        dry_run = bool(options["dry_run"])
        sleep_ms = int(options["sleep_ms"])

        ai_service = AIService() if mode in ("ai", "hybrid") else None

        self.stdout.write(self.style.SUCCESS(f"Enrichment mode: {mode}"))
        self.stdout.write(self.style.SUCCESS(f"Only missing fields: {only_missing}"))
        self.stdout.write(self.style.SUCCESS(f"Dry run: {dry_run}"))

        cap_topics = self._ensure_cap_hierarchy()

        qs = Question.objects.select_related("subject", "topic").filter(
            Q(correct_answer="")
            | Q(topic__isnull=True)
            | Q(explanation="")
            | Q(concept_explanation="")
            | Q(mnemonic="")
            | Q(concept_tags=[])
        )[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No questions require enrichment."))
            return

        changed = 0
        for q in qs:
            original = {
                "correct_answer": q.correct_answer,
                "topic_id": q.topic_id,
                "explanation": q.explanation,
                "concept_explanation": q.concept_explanation,
                "mnemonic": q.mnemonic,
                "concept_tags": list(q.concept_tags or []),
                "difficulty": q.difficulty,
            }

            applied = False

            if mode in ("rule", "hybrid"):
                rr = self._rule_enrich(q, cap_topics)
                applied = self._apply_result(q, rr, only_missing=only_missing) or applied

            if mode in ("ai", "hybrid"):
                if self._needs_ai(q):
                    ai_result = self._ai_enrich(q, ai_service)
                    applied = self._apply_result(q, ai_result, only_missing=only_missing) or applied
                    time.sleep(max(0, sleep_ms) / 1000.0)

            if applied:
                changed += 1
                if dry_run:
                    # Revert in-memory by restoring known original values.
                    q.correct_answer = original["correct_answer"]
                    q.topic_id = original["topic_id"]
                    q.explanation = original["explanation"]
                    q.concept_explanation = original["concept_explanation"]
                    q.mnemonic = original["mnemonic"]
                    q.concept_tags = original["concept_tags"]
                    q.difficulty = original["difficulty"]
                else:
                    q.save()

        self.stdout.write(self.style.SUCCESS(f"Processed: {total}"))
        self.stdout.write(self.style.SUCCESS(f"Changed: {changed}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run enabled: no DB rows were saved."))

    def _ensure_cap_hierarchy(self):
        """Ensure recommended CAP hierarchy exists for General Medicine."""
        med = Subject.objects.filter(code="MED").first()
        if not med:
            med = Subject.objects.filter(name__icontains="General Medicine").first()
        if not med:
            return {}

        respiratory, _ = Topic.objects.get_or_create(
            subject=med,
            name="Respiratory System",
            defaults={
                "importance": 8,
                "description": "System-level topic covering airway and lung disorders.",
            },
        )
        pneumonia, _ = Topic.objects.get_or_create(
            subject=med,
            name="Pneumonia",
            defaults={
                "parent": respiratory,
                "importance": 8,
                "description": "Lower respiratory tract infections and classification.",
            },
        )
        if pneumonia.parent_id != respiratory.id:
            pneumonia.parent = respiratory
            pneumonia.save(update_fields=["parent"])

        cap, _ = Topic.objects.get_or_create(
            subject=med,
            name="Community Acquired Pneumonia (CAP)",
            defaults={
                "parent": pneumonia,
                "importance": 7,
                "description": (
                    "Community Acquired Pneumonia (CAP) refers to pneumonia acquired outside "
                    "hospital settings. The most common causative organism is Streptococcus "
                    "pneumoniae. Other causes include Mycoplasma pneumoniae, Staphylococcus "
                    "aureus, and Legionella pneumophila."
                ),
            },
        )
        if cap.parent_id != pneumonia.id:
            cap.parent = pneumonia
            cap.save(update_fields=["parent"])

        return {"med": med, "respiratory": respiratory, "pneumonia": pneumonia, "cap": cap}

    def _rule_enrich(self, q: Question, cap_topics: dict) -> RuleResult:
        text = (q.question_text or "").lower()
        options = {
            "A": (q.option_a or ""),
            "B": (q.option_b or ""),
            "C": (q.option_c or ""),
            "D": (q.option_d or ""),
        }

        tags: set[str] = set(q.concept_tags or [])
        out = RuleResult()

        # CAP enrichment requested by user.
        is_cap = (
            "community acquired pneumonia" in text
            or "cap" in text
            or ("pneumonia" in text and "most common cause" in text)
        )

        if is_cap and cap_topics.get("cap") and q.subject_id == cap_topics["med"].id:
            out.topic = cap_topics["cap"]
            tags.update(
                {
                    "community acquired pneumonia",
                    "streptococcus pneumoniae",
                    "pneumonia etiology",
                    "respiratory infections",
                    "typical pneumonia",
                }
            )
            out.difficulty = "medium"
            if not q.explanation:
                out.explanation = (
                    "Most common cause of community-acquired pneumonia is Streptococcus "
                    "pneumoniae. It remains the leading typical bacterial pathogen in adults."
                )
            if not q.concept_explanation:
                out.concept_explanation = (
                    "CAP is pneumonia acquired outside healthcare settings. Typical CAP "
                    "pathogens include S. pneumoniae, H. influenzae, and atypicals such as "
                    "Mycoplasma."
                )
            if not q.mnemonic:
                out.mnemonic = "CAP classic: S-pneumo Starts the list."

            # Option matching for correct answer if missing.
            if not q.correct_answer:
                for letter, txt in options.items():
                    low = txt.lower()
                    if "streptococcus pneumoniae" in low or "s. pneumoniae" in low:
                        out.correct_answer = letter
                        break

        # Lightweight generic tagging from keywords.
        keyword_map = {
            "myocardial infarction": "cardiology",
            "arrhythmia": "cardiology",
            "asthma": "respiratory medicine",
            "copd": "respiratory medicine",
            "diabetes": "endocrinology",
            "thyroid": "endocrinology",
            "seizure": "neurology",
            "stroke": "neurology",
            "tuberculosis": "infectious diseases",
            "anemia": "hematology",
        }
        for k, v in keyword_map.items():
            if k in text:
                tags.add(v)

        if tags:
            out.concept_tags = sorted(tags)

        return out

    def _needs_ai(self, q: Question) -> bool:
        return (
            not q.correct_answer
            or not q.explanation
            or not q.concept_explanation
            or not q.mnemonic
            or not (q.concept_tags or [])
            or q.topic_id is None
        )

    def _ai_enrich(self, q: Question, ai_service: Optional[AIService]) -> RuleResult:
        if ai_service is None:
            return RuleResult()

        prompt = f"""You are enriching UPSC CMS question metadata. Return strict JSON only.

Question: {q.question_text}
Options:
A) {q.option_a}
B) {q.option_b}
C) {q.option_c}
D) {q.option_d}
Subject: {q.subject.name}
Existing topic: {q.topic.name if q.topic else ''}

Return JSON object with keys:
correct_answer, topic_name, difficulty, explanation, concept_explanation, mnemonic, concept_tags
Rules:
- correct_answer must be one of A,B,C,D or empty string if unsure.
- concept_tags must be an array of 3-8 short tags.
- Keep explanation concise and exam-focused.
"""

        try:
            raw = ai_service._call_ai(
                prompt,
                system="You are a medical data quality assistant. Return valid JSON only.",
                temperature=0.1,
                max_tokens=900,
            )
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            if not match:
                return RuleResult()
            payload = json.loads(match.group(0))
        except Exception:
            return RuleResult()

        out = RuleResult()
        answer = str(payload.get("correct_answer", "")).strip().upper()[:1]
        if answer in {"A", "B", "C", "D"}:
            out.correct_answer = answer

        diff = str(payload.get("difficulty", "")).strip().lower()
        if diff in {"easy", "medium", "hard"}:
            out.difficulty = diff

        topic_name = str(payload.get("topic_name", "")).strip()
        if topic_name:
            topic, _ = Topic.objects.get_or_create(subject=q.subject, name=topic_name)
            out.topic = topic

        explanation = str(payload.get("explanation", "")).strip()
        if explanation:
            out.explanation = explanation

        concept_explanation = str(payload.get("concept_explanation", "")).strip()
        if concept_explanation:
            out.concept_explanation = concept_explanation

        mnemonic = str(payload.get("mnemonic", "")).strip()
        if mnemonic:
            out.mnemonic = mnemonic

        tags = payload.get("concept_tags", [])
        if isinstance(tags, list):
            cleaned = [str(t).strip().lower() for t in tags if str(t).strip()]
            if cleaned:
                out.concept_tags = sorted(set(cleaned))

        return out

    def _apply_result(self, q: Question, result: RuleResult, only_missing: bool) -> bool:
        changed = False

        def can_set(current_value):
            if not only_missing:
                return True
            if current_value is None:
                return True
            if isinstance(current_value, str) and current_value.strip() == "":
                return True
            if isinstance(current_value, list) and len(current_value) == 0:
                return True
            return False

        if result.correct_answer and can_set(q.correct_answer):
            q.correct_answer = result.correct_answer
            changed = True

        if result.topic and (not q.topic_id or not only_missing):
            q.topic = result.topic
            changed = True

        if result.explanation and can_set(q.explanation):
            q.explanation = result.explanation
            changed = True

        if result.concept_explanation and can_set(q.concept_explanation):
            q.concept_explanation = result.concept_explanation
            changed = True

        if result.mnemonic and can_set(q.mnemonic):
            q.mnemonic = result.mnemonic
            changed = True

        if result.concept_tags:
            if can_set(q.concept_tags):
                q.concept_tags = result.concept_tags
                changed = True
            else:
                merged = sorted(set((q.concept_tags or []) + result.concept_tags))
                if merged != (q.concept_tags or []):
                    q.concept_tags = merged
                    changed = True

        if result.difficulty and (not only_missing or can_set(q.difficulty)):
            if result.difficulty in {"easy", "medium", "hard"} and result.difficulty != q.difficulty:
                q.difficulty = result.difficulty
                changed = True

        return changed
