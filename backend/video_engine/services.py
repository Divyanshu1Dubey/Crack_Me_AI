"""
CrackLabs AI - premium educational video generator.

V2 keeps the existing production contract intact:
  1. A Question is queued through django-q.
  2. The worker creates an MP4 once, uploads it, and stores the URL on Question.
  3. Future requests reuse the cached MP4 while the question content is unchanged.

The important change is educational quality. The engine now builds a teacher-style
lesson script, generates subtitles, renders concept/option-elimination visuals,
applies light motion in MoviePy, and runs a quality gate before marking a video
completed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from questions.models import Question

logger = logging.getLogger(__name__)

ENGINE_VERSION = "video-v2-professor-2026-07"
SCRIPT_SCHEMA_VERSION = "lesson-script-v2"
DEFAULT_BUCKET = "educational_videos"
MAX_SCENE_NARRATION_WORDS = 95


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _strip_markdown(text: str) -> str:
    t = _as_text(text)
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"__(.*?)__", r"\1", t)
    t = re.sub(r"\*(.*?)\*", r"\1", t)
    t = re.sub(r"#{1,6}\s+", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\|", " ", t)
    return " ".join(t.split()).strip()


def _clean_for_tts(text: str) -> str:
    """Convert study text into narration-safe prose.

    This avoids the old failure mode where markdown, option syntax, JSON braces,
    arrows, and punctuation were spoken literally.
    """
    t = _strip_markdown(text)
    replacements = {
        "->": " leads to ",
        "=>": " leads to ",
        ">=": " greater than or equal to ",
        "<=": " less than or equal to ",
        "+/-": " plus or minus ",
        "++": " strongly positive ",
        "+": " plus ",
        "&": " and ",
        "%": " percent ",
        "/": " per ",
        "vs.": " versus ",
        " vs ": " versus ",
        "↑": " increased ",
        "↓": " decreased ",
        "→": " leads to ",
        "←": " comes from ",
        "≥": " greater than or equal to ",
        "≤": " less than or equal to ",
        "±": " plus or minus ",
        "°": " degrees ",
    }
    for src, dst in replacements.items():
        t = t.replace(src, dst)

    pronunciation = {
        r"\bHbA1c\b": "H B A one C",
        r"\bECG\b": "E C G",
        r"\bEEG\b": "E E G",
        r"\bCSF\b": "C S F",
        r"\bCNS\b": "C N S",
        r"\bCKD\b": "C K D",
        r"\bAKI\b": "A K I",
        r"\bTB\b": "T B",
        r"\bHIV\b": "H I V",
        r"\bAIDS\b": "AIDS",
        r"\bIgG\b": "I G G",
        r"\bIgM\b": "I G M",
        r"\bLDL\b": "L D L",
        r"\bHDL\b": "H D L",
        r"\bUPSC\b": "U P S C",
        r"\bCMS\b": "C M S",
        r"\bNEET\b": "N E E T",
        r"\bMCQ\b": "M C Q",
    }
    for pattern, spoken in pronunciation.items():
        t = re.sub(pattern, spoken, t)

    # Remove option prefixes and structural characters that TTS often reads.
    t = re.sub(r"\bOption\s+([A-D])\s*[:.)-]?", r"choice \1", t, flags=re.I)
    t = re.sub(r"(^|\s)[A-D]\s*[:.)-]\s+", " ", t)
    t = re.sub(r"[{}\[\]\"'\\_*#<>|~^=]", " ", t)
    t = re.sub(r"\s*[-:;]\s*", ", ", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    return t.strip()


def _split_sentences(text: str, max_chars: int = 520) -> list[str]:
    text = _strip_markdown(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _truncate_words(text: str, limit: int = MAX_SCENE_NARRATION_WORDS) -> str:
    words = _clean_for_tts(text).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(",.;") + "."


def _safe_list(value: Any, limit: int = 6) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    else:
        items = re.split(r"[\n;]+", _as_text(value))
    cleaned = [_strip_markdown(_as_text(item)) for item in items]
    return [item for item in cleaned if item][:limit]


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if text.lower().startswith("json"):
        text = text[4:].strip()

    for candidate in (text, text[text.find("{"): text.rfind("}") + 1] if "{" in text and "}" in text else ""):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            continue
    return None


def _effective_explanation(q: Question) -> str:
    if q.lock_explanation:
        return q.admin_explanation_override or q.explanation or q.concept_explanation
    return (
        q.admin_explanation_override
        or q.concept_explanation
        or q.explanation
        or q.ai_explanation
        or ""
    )


def _effective_answer(q: Question) -> str:
    if q.lock_answer:
        return q.admin_answer_override or q.get_correct_option_text()
    return q.admin_answer_override or q.ai_answer or q.get_correct_option_text()


def _effective_mnemonic(q: Question) -> str:
    return q.admin_mnemonic_override or q.ai_mnemonic or q.mnemonic or ""


def _reference_text(q: Question, ai_payload: dict[str, Any]) -> str:
    override = q.admin_references_override or []
    refs = override or q.ai_references or q.textbook_references or []
    if isinstance(refs, list) and refs:
        first = refs[0]
        if isinstance(first, dict):
            parts = [
                first.get("book") or first.get("book_name"),
                first.get("chapter"),
                f"p. {first.get('page') or first.get('page_number')}" if first.get("page") or first.get("page_number") else "",
                first.get("section"),
            ]
            return ", ".join([_strip_markdown(p) for p in parts if p])
        return _strip_markdown(first)

    ai_ref = ai_payload.get("textbook_reference")
    if isinstance(ai_ref, dict):
        parts = [
            ai_ref.get("book"),
            ai_ref.get("chapter"),
            f"p. {ai_ref.get('page')}" if ai_ref.get("page") else "",
            ai_ref.get("section"),
        ]
        return ", ".join([_strip_markdown(p) for p in parts if p])

    parts = [
        q.book_name,
        q.chapter,
        f"p. {q.page_number}" if q.page_number else "",
    ]
    return ", ".join([_strip_markdown(p) for p in parts if p])


def _option_map(q: Question) -> dict[str, str]:
    return {
        "A": q.option_a or "",
        "B": q.option_b or "",
        "C": q.option_c or "",
        "D": q.option_d or "",
    }


def _format_vtt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class VideoGeneratorService:
    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="cracklabs_video_")
        self.bucket = os.getenv("VIDEO_STORAGE_BUCKET", DEFAULT_BUCKET)
        self._storage_client = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate_for_question(self, question_id: int, force: bool = False) -> bool:
        question: Question | None = None
        try:
            question = Question.objects.select_related("subject", "topic").get(id=question_id)
            content_hash = self._content_hash(question)
            expected_version = f"{ENGINE_VERSION}:{content_hash}"

            if (
                not force
                and question.video_status == "completed"
                and question.video_url
                and question.video_version == expected_version
            ):
                logger.info("Q%s: V2 video already cached; skipping render", question_id)
                return True

            question.video_status = "processing"
            question.video_error = ""
            question.save(update_fields=["video_status", "video_error"])

            script = self._build_or_load_script(question, content_hash)
            scenes = script.get("scenes", [])
            if not self._script_passes_quality(script):
                raise ValueError("Teaching script did not pass the internal quality checklist")

            from .slide_renderer import SlideRenderer

            renderer = SlideRenderer()
            metadata = script.get("metadata", {})
            slide_data: list[dict[str, Any]] = []

            for index, scene in enumerate(scenes, start=1):
                slide_path = os.path.join(self.tmp_dir, f"slide_{index:02d}.png")
                audio_path = os.path.join(self.tmp_dir, f"audio_{index:02d}.mp3")
                image = renderer.render_scene(scene, metadata, index, len(scenes))
                image.save(slide_path, "PNG")

                narration = _clean_for_tts(scene.get("narration", ""))
                audio_ok = self._tts(narration, audio_path)
                if not audio_ok:
                    raise RuntimeError(f"Narration audio failed for scene {index}: {scene.get('title', 'Untitled')}")

                slide_data.append({
                    "slide": slide_path,
                    "audio": audio_path,
                    "title": scene.get("title", ""),
                    "narration": narration,
                    "scene_type": scene.get("type", "lesson"),
                    "min_dur": float(scene.get("duration_hint") or 5.0),
                })

            video_name = f"q_{question_id}_{content_hash}_v2.mp4"
            vtt_name = f"q_{question_id}_{content_hash}_v2.vtt"
            thumbnail_name = f"q_{question_id}_{content_hash}_thumb.png"
            video_path = os.path.join(self.tmp_dir, video_name)
            vtt_path = os.path.join(self.tmp_dir, vtt_name)
            thumbnail_path = os.path.join(self.tmp_dir, thumbnail_name)

            duration = self._assemble(slide_data, video_path)
            self._write_vtt(slide_data, vtt_path)
            shutil.copyfile(slide_data[0]["slide"], thumbnail_path)

            self._quality_gate(slide_data, video_path, vtt_path, duration)

            video_url = self._upload(video_path, video_name, "video/mp4")
            if not video_url:
                raise RuntimeError("Supabase upload failed for MP4")

            thumb_url = self._upload(thumbnail_path, thumbnail_name, "image/png") or ""
            self._upload(vtt_path, vtt_name, "text/vtt")
            self._save_script_cache(script, content_hash)

            question.video_url = video_url
            question.video_thumbnail = thumb_url
            question.video_status = "completed"
            question.video_duration = int(round(duration))
            question.video_version = expected_version
            question.video_generated_at = timezone.now()
            question.video_error = ""
            question.save(update_fields=[
                "video_url",
                "video_thumbnail",
                "video_status",
                "video_duration",
                "video_version",
                "video_generated_at",
                "video_error",
            ])
            logger.info("Q%s: V2 video completed -> %s", question_id, video_url)
            return True

        except Exception as exc:
            logger.error("Video generation failed for Q%s: %s", question_id, exc, exc_info=True)
            if question:
                question.video_status = "failed"
                question.video_error = str(exc)[:500]
                question.save(update_fields=["video_status", "video_error"])
            return False
        finally:
            self._cleanup()

    # ------------------------------------------------------------------
    # Lesson script generation and caching
    # ------------------------------------------------------------------

    def _content_hash(self, q: Question) -> str:
        payload = {
            "engine": ENGINE_VERSION,
            "question": q.question_text,
            "options": _option_map(q),
            "correct": q.correct_answer,
            "answer": _effective_answer(q),
            "explanation": _effective_explanation(q),
            "mnemonic": _effective_mnemonic(q),
            "pearl": q.ai_clinical_pearl,
            "learning": q.learning_technique,
            "shortcut": q.shortcut_tip,
            "references": q.admin_references_override or q.ai_references or q.textbook_references,
            "subject": q.subject.name if q.subject else "",
            "topic": q.topic.name if q.topic else "",
            "year": q.year,
        }
        raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _script_object_name(self, question_id: int, content_hash: str) -> str:
        return f"scripts/q_{question_id}_{content_hash}_script.json"

    def _local_script_path(self, question_id: int, content_hash: str) -> Path:
        root = Path(getattr(settings, "MEDIA_ROOT", Path.cwd() / "media"))
        return root / "video_engine" / "scripts" / f"q_{question_id}_{content_hash}_script.json"

    def _build_or_load_script(self, q: Question, content_hash: str) -> dict[str, Any]:
        cached = self._load_script_cache(q.id, content_hash)
        if cached and cached.get("schema") == SCRIPT_SCHEMA_VERSION:
            return cached

        script = self._generate_ai_script(q, content_hash)
        if not self._script_passes_quality(script):
            logger.warning("Q%s: AI script quality low; using deterministic professor fallback", q.id)
            script = self._fallback_script(q, content_hash)

        self._save_script_cache(script, content_hash)
        return script

    def _load_script_cache(self, question_id: int, content_hash: str) -> dict[str, Any] | None:
        local_path = self._local_script_path(question_id, content_hash)
        if local_path.exists():
            try:
                return json.loads(local_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Local script cache unreadable for Q%s: %s", question_id, exc)

        text = self._download_text(self._script_object_name(question_id, content_hash))
        if text:
            try:
                script = json.loads(text)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(json.dumps(script, ensure_ascii=True, indent=2), encoding="utf-8")
                return script
            except Exception as exc:
                logger.warning("Remote script cache unreadable for Q%s: %s", question_id, exc)
        return None

    def _save_script_cache(self, script: dict[str, Any], content_hash: str) -> None:
        question_id = int(script.get("question_id") or 0)
        if not question_id:
            return
        text = json.dumps(script, ensure_ascii=True, indent=2)
        local_path = self._local_script_path(question_id, content_hash)
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write local script cache for Q%s: %s", question_id, exc)

        remote_path = os.path.join(self.tmp_dir, f"q_{question_id}_{content_hash}_script.json")
        try:
            Path(remote_path).write_text(text, encoding="utf-8")
            self._upload(remote_path, self._script_object_name(question_id, content_hash), "application/json")
        except Exception as exc:
            logger.warning("Could not upload script cache for Q%s: %s", question_id, exc)

    def _learning_payload(self, q: Question) -> dict[str, Any]:
        parsed = _extract_json_object(q.ai_explanation or "")
        if not parsed:
            parsed = {}
        explanation = _effective_explanation(q)
        if not parsed.get("why_correct"):
            parsed["why_correct"] = explanation
        if not parsed.get("mnemonic"):
            parsed["mnemonic"] = _effective_mnemonic(q)
        if not parsed.get("clinical_pearl"):
            parsed["clinical_pearl"] = q.ai_clinical_pearl or ""
        if not parsed.get("exam_tip"):
            parsed["exam_tip"] = q.learning_technique or q.shortcut_tip or ""
        if not parsed.get("core_concept"):
            parsed["core_concept"] = (
                (q.concept_tags[0] if isinstance(q.concept_tags, list) and q.concept_tags else "")
                or (q.topic.name if q.topic else "")
                or (q.subject.name if q.subject else "the tested medical concept")
            )
        return parsed

    def _generate_ai_script(self, q: Question, content_hash: str) -> dict[str, Any]:
        ai_payload = self._learning_payload(q)
        options = _option_map(q)
        prompt = f"""
Create a premium UPSC CMS / MBBS teaching video script as valid JSON only.

Rules:
- Do not read the raw question verbatim in narration.
- Narration must sound like an experienced Indian MBBS professor teaching a student.
- Explain the concept before revealing the answer.
- Include option elimination, clinical pearl, mnemonic, exam strategy, reference, and high-yield takeaway.
- Avoid markdown, emojis, bullets inside narration, and special characters that TTS might read aloud.
- Keep each narration under {MAX_SCENE_NARRATION_WORDS} words.
- Return JSON with exactly this shape:
{{
  "title": "...",
  "core_concept": "...",
  "scenes": [
    {{
      "type": "intro|question_focus|concept|mechanism|option_elimination|answer_reveal|clinical_pearl|mnemonic|exam_strategy|reference|takeaway",
      "title": "...",
      "subtitle": "...",
      "narration": "...",
      "bullets": ["...", "..."],
      "focus_terms": ["...", "..."],
      "duration_hint": 5
    }}
  ]
}}

Question data:
Subject: {q.subject.name if q.subject else ""}
Topic: {q.topic.name if q.topic else ""}
Year: {q.year}
Difficulty: {q.difficulty}
Question stem for visual display only: {q.question_text}
Options: {json.dumps(options, ensure_ascii=True)}
Correct answer letter: {q.correct_answer}
Correct answer text: {options.get(q.correct_answer, "")}
Existing teaching data: {json.dumps(ai_payload, ensure_ascii=True, default=str)[:5000]}
Reference: {_reference_text(q, ai_payload)}
"""
        try:
            from ai_engine.services import AIService

            raw = AIService()._call_ai(
                prompt,
                system=(
                    "You are CrackLabs AI's senior medical video scriptwriter. "
                    "You write accurate, memorable, exam-focused UPSC CMS lessons. "
                    "Return only valid JSON."
                ),
                temperature=0.25,
                max_tokens=3600,
            )
            parsed = _extract_json_object(raw)
            if parsed:
                return self._normalize_script(q, content_hash, parsed, ai_payload)
            logger.warning("Q%s: AI script JSON parse failed", q.id)
        except Exception as exc:
            logger.warning("Q%s: AI script generation unavailable: %s", q.id, exc)
        return self._fallback_script(q, content_hash)

    def _normalize_script(
        self,
        q: Question,
        content_hash: str,
        raw_script: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> dict[str, Any]:
        scenes: list[dict[str, Any]] = []
        for scene in raw_script.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            narration = _truncate_words(scene.get("narration", ""))
            if not narration:
                continue
            scenes.append({
                "type": _strip_markdown(scene.get("type") or "lesson").lower().replace(" ", "_"),
                "title": _strip_markdown(scene.get("title") or "Teaching Point")[:80],
                "subtitle": _strip_markdown(scene.get("subtitle") or "")[:120],
                "narration": narration,
                "bullets": _safe_list(scene.get("bullets"), 5),
                "focus_terms": _safe_list(scene.get("focus_terms"), 5),
                "duration_hint": max(4, min(float(scene.get("duration_hint") or 6), 12)),
            })

        if len(scenes) < 8:
            fallback = self._fallback_script(q, content_hash)
            existing_types = {s["type"] for s in scenes}
            for scene in fallback["scenes"]:
                if scene["type"] not in existing_types:
                    scenes.append(scene)
                if len(scenes) >= 10:
                    break

        return {
            "schema": SCRIPT_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "question_id": q.id,
            "content_hash": content_hash,
            "title": _strip_markdown(raw_script.get("title") or f"{q.subject.name if q.subject else 'Medical'} PYQ"),
            "core_concept": _strip_markdown(raw_script.get("core_concept") or ai_payload.get("core_concept") or ""),
            "metadata": self._metadata(q, ai_payload),
            "scenes": scenes[:11],
        }

    def _fallback_script(self, q: Question, content_hash: str) -> dict[str, Any]:
        ai_payload = self._learning_payload(q)
        options = _option_map(q)
        subject = q.subject.name if q.subject else "Medicine"
        topic = q.topic.name if q.topic else "High-yield concept"
        core = _strip_markdown(ai_payload.get("core_concept") or topic or subject)
        correct_text = _strip_markdown(options.get(q.correct_answer, ""))
        explanation = _strip_markdown(ai_payload.get("why_correct") or _effective_explanation(q) or _effective_answer(q))
        concept_text = _strip_markdown(q.concept_explanation or ai_payload.get("topic_deep_dive") or explanation)
        pearl = _strip_markdown(ai_payload.get("clinical_pearl") or q.ai_clinical_pearl or "")
        mnemonic = _strip_markdown(ai_payload.get("mnemonic") or _effective_mnemonic(q) or "")
        exam_tip = _strip_markdown(ai_payload.get("exam_tip") or q.learning_technique or q.shortcut_tip or "")
        reference = _reference_text(q, ai_payload)
        high_yield = _safe_list(ai_payload.get("high_yield_points"), 5)
        if not high_yield and explanation:
            high_yield = _split_sentences(explanation, 140)[:4]

        why_wrong = ai_payload.get("why_wrong") if isinstance(ai_payload.get("why_wrong"), dict) else {}
        elimination_lines = []
        for label, text in options.items():
            cleaned = _strip_markdown(text)
            if label == q.correct_answer:
                elimination_lines.append(f"Keep {label}: {cleaned} fits the key concept.")
            else:
                reason = _strip_markdown(why_wrong.get(label) or "This distractor does not match the core mechanism being tested.")
                elimination_lines.append(f"Eliminate {label}: {reason}")

        scenes = [
            {
                "type": "intro",
                "title": "CrackLabs AI Teaching Mode",
                "subtitle": f"{subject} | UPSC CMS {q.year}",
                "narration": _truncate_words(
                    f"Welcome to CrackLabs AI. This question is testing {core}. "
                    "We will solve it like a clinician, not like a screen reader."
                ),
                "bullets": [subject, topic, f"UPSC CMS {q.year}"],
                "focus_terms": [core],
                "duration_hint": 4,
            },
            {
                "type": "question_focus",
                "title": "Read The Stem, Find The Trap",
                "subtitle": "The question is on screen; listen for what to notice.",
                "narration": _truncate_words(
                    f"First, read the stem once and ask: what is UPSC really testing? "
                    f"The safest anchor here is {core}. Do not jump to options before identifying that anchor."
                ),
                "bullets": [q.question_text],
                "focus_terms": _safe_list(q.concept_tags, 4) or [core],
                "duration_hint": 6,
            },
            {
                "type": "concept",
                "title": "Concept Before Answer",
                "subtitle": core,
                "narration": _truncate_words(
                    f"Before the answer, understand the concept. {concept_text or explanation}"
                ),
                "bullets": _split_sentences(concept_text or explanation, 120)[:5],
                "focus_terms": [core, topic, subject],
                "duration_hint": 8,
            },
            {
                "type": "option_elimination",
                "title": "Option Elimination",
                "subtitle": "Remove distractors one by one.",
                "narration": _truncate_words(
                    "Now eliminate options actively. "
                    + " ".join(elimination_lines)
                ),
                "bullets": elimination_lines,
                "focus_terms": [f"Answer {q.correct_answer}", correct_text],
                "duration_hint": 10,
            },
            {
                "type": "answer_reveal",
                "title": f"Answer: {q.correct_answer}",
                "subtitle": correct_text,
                "narration": _truncate_words(
                    f"The correct answer is {q.correct_answer}, {correct_text}. "
                    f"It is correct because {explanation}"
                ),
                "bullets": _split_sentences(explanation, 130)[:4] or [correct_text],
                "focus_terms": [correct_text, core],
                "duration_hint": 8,
            },
        ]

        if pearl:
            scenes.append({
                "type": "clinical_pearl",
                "title": "Clinical Pearl",
                "subtitle": "Make it clinically memorable.",
                "narration": _truncate_words(f"Clinical pearl: {pearl}"),
                "bullets": _split_sentences(pearl, 120)[:4],
                "focus_terms": [core],
                "duration_hint": 6,
            })

        if mnemonic:
            scenes.append({
                "type": "mnemonic",
                "title": "Memory Trick",
                "subtitle": "Recall hook for the exam.",
                "narration": _truncate_words(f"To remember this, use this memory hook: {mnemonic}"),
                "bullets": _split_sentences(mnemonic, 120)[:5],
                "focus_terms": [core],
                "duration_hint": 6,
            })

        scenes.extend([
            {
                "type": "exam_strategy",
                "title": "Exam Strategy",
                "subtitle": "How to solve it under time pressure.",
                "narration": _truncate_words(
                    exam_tip
                    or f"In UPSC CMS, convert this into a pattern-recognition question. Identify {core}, eliminate mismatched options, then verify the best answer."
                ),
                "bullets": _split_sentences(exam_tip, 120)[:4] if exam_tip else [
                    f"Anchor the stem to {core}.",
                    "Eliminate options that answer a different mechanism.",
                    "Confirm the option that explains the key clue.",
                ],
                "focus_terms": [core, "elimination", "high yield"],
                "duration_hint": 6,
            },
            {
                "type": "reference",
                "title": "Reference Anchor",
                "subtitle": reference or "Standard MBBS reference",
                "narration": _truncate_words(
                    f"For revision, connect this with {reference or 'your standard textbook chapter for this topic'}. "
                    "Use references to strengthen accuracy, not to memorize isolated lines."
                ),
                "bullets": [reference or "Standard textbook reference", subject, topic],
                "focus_terms": [subject, topic],
                "duration_hint": 5,
            },
            {
                "type": "takeaway",
                "title": "UPSC CMS High-Yield Takeaway",
                "subtitle": "What you should remember in one minute.",
                "narration": _truncate_words(
                    "Final takeaway: "
                    + (" ".join(high_yield) if high_yield else f"Remember {core}, the correct answer {correct_text}, and the logic that eliminates the distractors.")
                ),
                "bullets": high_yield or [core, correct_text, "Use option elimination."],
                "focus_terms": [core, correct_text],
                "duration_hint": 6,
            },
        ])

        return {
            "schema": SCRIPT_SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "question_id": q.id,
            "content_hash": content_hash,
            "title": f"{subject}: {core}",
            "core_concept": core,
            "metadata": self._metadata(q, ai_payload),
            "scenes": scenes,
        }

    def _metadata(self, q: Question, ai_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_id": q.id,
            "subject": q.subject.name if q.subject else "General",
            "topic": q.topic.name if q.topic else "",
            "year": q.year,
            "difficulty": q.difficulty,
            "correct_answer": q.correct_answer,
            "correct_option_text": _option_map(q).get(q.correct_answer, ""),
            "question_text": q.question_text,
            "options": _option_map(q),
            "reference": _reference_text(q, ai_payload),
            "teacher": os.getenv("VIDEO_TEACHER_NAME", "Dr. Asha"),
        }

    def _script_passes_quality(self, script: dict[str, Any]) -> bool:
        scenes = script.get("scenes") or []
        scene_types = {scene.get("type") for scene in scenes if isinstance(scene, dict)}
        narration = " ".join(_as_text(scene.get("narration")) for scene in scenes if isinstance(scene, dict))
        required = {"intro", "question_focus", "concept", "option_elimination", "answer_reveal", "exam_strategy", "takeaway"}
        if len(scenes) < 8:
            return False
        if not required.issubset(scene_types):
            return False
        if len(narration.split()) < 140:
            return False
        if "All AI services are temporarily unavailable" in narration:
            return False
        noisy = sum(narration.count(ch) for ch in "{}[]`*_#|")
        return noisy <= 4

    # ------------------------------------------------------------------
    # Audio, assembly, subtitles, and quality
    # ------------------------------------------------------------------

    def _tts(self, text: str, output_path: str) -> bool:
        clean = _clean_for_tts(text)
        if not clean:
            return False

        try:
            import edge_tts
        except Exception as exc:
            logger.error("edge-tts is not installed: %s", exc)
            return False

        voice = os.getenv("VIDEO_TTS_VOICE", "en-IN-NeerjaNeural")
        rate = os.getenv("VIDEO_TTS_RATE", "-4%")
        pitch = os.getenv("VIDEO_TTS_PITCH", "+0Hz")

        async def _run():
            comm = edge_tts.Communicate(clean, voice, rate=rate, pitch=pitch)
            await comm.save(output_path)

        try:
            asyncio.run(_run())
            return os.path.exists(output_path) and os.path.getsize(output_path) > 1024
        except Exception as exc:
            logger.error("TTS error: %s", exc, exc_info=True)
            return False

    def _assemble(self, slide_data: list[dict[str, Any]], output_path: str) -> float:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        except Exception:
            from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        clips = []
        total_duration = 0.0
        try:
            for idx, sd in enumerate(slide_data):
                audio = AudioFileClip(sd["audio"])
                duration = max(float(getattr(audio, "duration", 0) or 0) + 0.45, float(sd.get("min_dur") or 5))
                sd["duration"] = duration
                sd["start"] = total_duration
                sd["end"] = total_duration + duration
                total_duration += duration

                clip = ImageClip(sd["slide"])
                clip = self._clip_with_duration(clip, duration)
                clip = self._clip_with_audio(clip, audio)
                clip = self._apply_motion(clip, idx, duration)
                clips.append(clip)

            final = concatenate_videoclips(clips, method="compose")
            final.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset=os.getenv("VIDEO_FFMPEG_PRESET", "medium"),
                threads=int(os.getenv("VIDEO_FFMPEG_THREADS", "2")),
                logger=None,
            )
            try:
                final.close()
            except Exception:
                pass
            return total_duration
        finally:
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass

    def _clip_with_duration(self, clip, duration: float):
        if hasattr(clip, "with_duration"):
            return clip.with_duration(duration)
        return clip.set_duration(duration)

    def _clip_with_audio(self, clip, audio):
        if hasattr(clip, "with_audio"):
            return clip.with_audio(audio)
        return clip.set_audio(audio)

    def _apply_motion(self, clip, index: int, duration: float):
        """Subtle Ken Burns style motion; gracefully falls back if MoviePy differs."""
        zoom_in = index % 2 == 0

        def scale(t):
            ratio = min(max(t / max(duration, 0.1), 0), 1)
            return 1.0 + (0.025 * ratio if zoom_in else 0.025 * (1 - ratio))

        try:
            if hasattr(clip, "resized"):
                return clip.resized(scale).with_position(("center", "center"))
            if hasattr(clip, "resize"):
                return clip.resize(scale).set_position(("center", "center"))
        except Exception as exc:
            logger.debug("Motion effect skipped: %s", exc)
        return clip

    def _write_vtt(self, slide_data: list[dict[str, Any]], output_path: str) -> None:
        lines = ["WEBVTT", "", "NOTE Generated by CrackLabs AI Video Engine V2", ""]
        cue_id = 1
        for sd in slide_data:
            start = float(sd.get("start") or 0)
            duration = float(sd.get("duration") or sd.get("min_dur") or 5)
            caption_chunks = self._caption_chunks(sd.get("narration", ""))
            chunk_duration = duration / max(len(caption_chunks), 1)
            for idx, caption in enumerate(caption_chunks):
                cue_start = start + idx * chunk_duration
                cue_end = min(start + duration, cue_start + chunk_duration)
                lines.extend([
                    str(cue_id),
                    f"{_format_vtt_time(cue_start)} --> {_format_vtt_time(cue_end)}",
                    caption,
                    "",
                ])
                cue_id += 1
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")

    def _caption_chunks(self, text: str) -> list[str]:
        clean = _clean_for_tts(text)
        sentences = re.split(r"(?<=[.!?])\s+", clean)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()
            if len(candidate) > 92 and current:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [clean[:92]]

    def _quality_gate(
        self,
        slide_data: list[dict[str, Any]],
        video_path: str,
        vtt_path: str,
        duration: float,
    ) -> None:
        failures = []
        if len(slide_data) < 8:
            failures.append("too few lesson scenes")
        if duration < 40:
            failures.append("video duration too short for a teaching solution")
        if not os.path.exists(video_path) or os.path.getsize(video_path) < 50_000:
            failures.append("rendered MP4 missing or too small")
        if not os.path.exists(vtt_path) or os.path.getsize(vtt_path) < 200:
            failures.append("subtitles missing")
        missing_audio = [sd.get("title") for sd in slide_data if not sd.get("audio") or not os.path.exists(sd["audio"])]
        if missing_audio:
            failures.append(f"missing narration audio: {', '.join(missing_audio[:3])}")
        if failures:
            raise RuntimeError("Video quality gate failed: " + "; ".join(failures))

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _get_storage_client(self):
        if self._storage_client is not None:
            return self._storage_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        from supabase import create_client

        self._storage_client = create_client(url, key)
        return self._storage_client

    def _upload(self, file_path: str, object_name: str, content_type: str) -> str | None:
        client = self._get_storage_client()
        if not client:
            logger.warning("Supabase creds missing. Returning dev URL for %s", object_name)
            return f"https://dev.local/videos/{Path(object_name).name}"

        try:
            with open(file_path, "rb") as handle:
                client.storage.from_(self.bucket).upload(
                    path=object_name,
                    file=handle,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
            return client.storage.from_(self.bucket).get_public_url(object_name)
        except Exception as exc:
            logger.error("Upload error for %s: %s", object_name, exc, exc_info=True)
            return None

    def _download_text(self, object_name: str) -> str:
        client = self._get_storage_client()
        if not client:
            return ""
        try:
            data = client.storage.from_(self.bucket).download(object_name)
            if isinstance(data, bytes):
                return data.decode("utf-8")
            if isinstance(data, str):
                return data
        except Exception:
            return ""
        return ""

    def _cleanup(self) -> None:
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass
