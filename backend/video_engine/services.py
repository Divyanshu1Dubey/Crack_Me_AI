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
REQUIRED_SCENE_TYPES = {
    "intro",
    "question_focus",
    "concept",
    "option_elimination",
    "answer_reveal",
    "clinical_pearl",
    "mnemonic",
    "exam_strategy",
    "reference",
    "takeaway",
}


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
    t = re.sub(r"`[\s\S]*?```", " ", t)
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
    replacements.update({
        "≥": " greater than or equal to ",
        "≤": " less than or equal to ",
        "→": " leads to ",
        "←": " comes from ",
        "↑": " increased ",
        "↓": " decreased ",
        "–": ", ",
        "—": ", ",
    })
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


def _chunk_for_subtitles(text: str, max_chars: int = 90) -> list[str]:
    clean = _clean_for_tts(text)
    if not clean:
        return []
    sentences = _split_sentences(clean, max_chars=max_chars)
    if sentences:
        return sentences
    words = clean.split()
    if not words:
        return []
    chunks: list[str] = []
    buffer: list[str] = []
    for word in words:
        buffer.append(word)
        candidate = " ".join(buffer)
        if len(candidate) >= max_chars:
            chunks.append(candidate)
            buffer = []
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks or [clean]


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
    if getattr(q, 'lock_explanation', False):
        return getattr(q, 'admin_explanation_override', None) or getattr(q, 'explanation', None) or getattr(q, 'concept_explanation', None) or ""
    return (
        getattr(q, 'admin_explanation_override', None)
        or getattr(q, 'concept_explanation', None)
        or getattr(q, 'explanation', None)
        or getattr(q, 'ai_explanation', None)
        or ""
    )


def _effective_answer(q: Question) -> str:
    if getattr(q, 'lock_answer', False):
        return getattr(q, 'admin_answer_override', None) or q.get_correct_option_text()
    return getattr(q, 'admin_answer_override', None) or getattr(q, 'ai_answer', None) or q.get_correct_option_text()


def _effective_mnemonic(q: Question) -> str:
    return getattr(q, 'admin_mnemonic_override', None) or getattr(q, 'ai_mnemonic', None) or getattr(q, 'mnemonic', None) or ""


def _reference_text(q: Question, ai_payload: dict[str, Any]) -> str:
    override = getattr(q, 'admin_references_override', None) or []
    refs = override or getattr(q, 'ai_references', None) or getattr(q, 'textbook_references', None) or []
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
        getattr(q, 'book_name', None),
        getattr(q, 'chapter', None),
        f"p. {getattr(q, 'page_number', None)}" if getattr(q, 'page_number', None) else "",
    ]
    return ", ".join([_strip_markdown(p) for p in parts if p])


def _option_map(q: Question) -> dict[str, str]:
    return {
        "A": getattr(q, 'option_a', ""),
        "B": getattr(q, 'option_b', ""),
        "C": getattr(q, 'option_c', ""),
        "D": getattr(q, 'option_d', ""),
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
            vtt_url = self._upload(vtt_path, vtt_name, "text/vtt")
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
            "correct": getattr(q, 'correct_answer', ''),
            "answer": _effective_answer(q),
            "explanation": _effective_explanation(q),
            "mnemonic": _effective_mnemonic(q),
            "pearl": getattr(q, 'ai_clinical_pearl', ''),
            "learning": getattr(q, 'learning_technique', ''),
            "shortcut": getattr(q, 'shortcut_tip', ''),
            "references": getattr(q, 'admin_references_override', None) or getattr(q, 'ai_references', None) or getattr(q, 'textbook_references', None),
            "subject": q.subject.name if getattr(q, 'subject', None) else "",
            "topic": q.topic.name if getattr(q, 'topic', None) else "",
            "year": getattr(q, 'year', ''),
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
        parsed = _extract_json_object(getattr(q, 'ai_explanation', ""))
        if not parsed:
            parsed = {}
        explanation = _effective_explanation(q)
        if not parsed.get("why_correct"):
            parsed["why_correct"] = explanation
        if not parsed.get("mnemonic"):
            parsed["mnemonic"] = _effective_mnemonic(q)
        if not parsed.get("clinical_pearl"):
            parsed["clinical_pearl"] = getattr(q, 'ai_clinical_pearl', "") or ""
        if not parsed.get("exam_tip"):
            parsed["exam_tip"] = getattr(q, 'learning_technique', "") or getattr(q, 'shortcut_tip', "") or ""
        
        c_tags = getattr(q, 'concept_tags', [])
        if not parsed.get("core_concept"):
            parsed["core_concept"] = (
                (c_tags[0] if isinstance(c_tags, list) and c_tags else "")
                or (q.topic.name if getattr(q, 'topic', None) else "")
                or (q.subject.name if getattr(q, 'subject', None) else "the tested medical concept")
            )
        return parsed

    def _generate_ai_script(self, q: Question, content_hash: str) -> dict[str, Any]:
        ai_payload = self._learning_payload(q)
        options = _option_map(q)
        subject_name = q.subject.name if getattr(q, 'subject', None) else ""
        topic_name = q.topic.name if getattr(q, 'topic', None) else ""
        correct_letter = getattr(q, 'correct_answer', 'A')
        
        prompt = f"""
Create a premium UPSC CMS / MBBS teaching video script as valid JSON only.

Rules:
- Do not read the raw question verbatim in narration.
- Narration must sound like an experienced Indian MBBS professor teaching a student.
- Explain the concept before revealing the answer.
- Include option elimination, clinical pearl, mnemonic, exam strategy, reference, and high-yield takeaway.
- Include at least 10 scenes and cover these scene types: intro, question_focus, concept, mechanism, option_elimination, answer_reveal, clinical_pearl, mnemonic, exam_strategy, reference, takeaway.
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
Subject: {subject_name}
Topic: {topic_name}
Year: {getattr(q, 'year', '')}
Difficulty: {getattr(q, 'difficulty', 'medium')}
Question stem for visual display only: {q.question_text}
Options: {json.dumps(options, ensure_ascii=True)}
Correct answer letter: {correct_letter}
Correct answer text: {options.get(correct_letter, "")}
Existing teaching data: {json.dumps(ai_payload, ensure_ascii=True, default=str)[:5000]}
Reference: {_reference_text(q, ai_payload)}
"""
        try:
            from ai_engine.services import AIService
            raw = AIService()._call_ai(
                prompt,
                system=(
                    "You are CrackLabs AI's senior medical video scriptwriter. "
                    "You write accurate, memorable, professor-style narrations "
                    "for MBBS students and UPSC CMS aspirants. You format your output as valid JSON."
                )
            )
            parsed = _extract_json_object(raw)
            if parsed and "scenes" in parsed:
                parsed["schema"] = SCRIPT_SCHEMA_VERSION
                parsed["question_id"] = q.id
                parsed["metadata"] = {
                    "subject": subject_name,
                    "year": getattr(q, 'year', ''),
                    "difficulty": getattr(q, 'difficulty', 'medium'),
                    "question_text": q.question_text,
                    "options": options,
                    "correct_answer": correct_letter,
                }
                return parsed
        except Exception as exc:
            logger.warning("AI script generation failed for Q%s: %s", q.id, exc)

        return {}

    def _fallback_script(self, q: Question, content_hash: str) -> dict[str, Any]:
        """Deterministic professor fallback if AI fails or returns low quality."""
        options = _option_map(q)
        correct_letter = getattr(q, 'correct_answer', 'A')
        correct_text = options.get(correct_letter, "")
        subject_name = q.subject.name if getattr(q, 'subject', None) else "General Medicine"
        topic_name = q.topic.name if getattr(q, 'topic', None) else subject_name
        explanation = _effective_explanation(q) or _effective_answer(q) or correct_text
        explanation_chunks = _split_sentences(explanation, 150)[:4]
        mnemonic = _effective_mnemonic(q) or f"Link the key clue in the stem to {correct_text}."
        pearl = getattr(q, 'ai_clinical_pearl', "") or f"In CMS questions, identify the decisive clinical clue before looking at similar options."
        strategy = getattr(q, 'learning_technique', "") or getattr(q, 'shortcut_tip', "") or "First name the concept, then eliminate options that contradict the central clue."
        reference = _reference_text(q, self._learning_payload(q)) or "Standard MBBS textbooks and UPSC CMS high-yield concepts"
        wrong_bullets = [
            f"Option {label}: {text}" for label, text in options.items() if label != correct_letter and text
        ][:3]
        
        scenes = [
            {
                "type": "intro",
                "title": f"{topic_name} Review",
                "subtitle": "UPSC CMS High-Yield Topic",
                "narration": f"Welcome to CrackLabs AI. In this short professor-style lesson, we will convert a {subject_name} question into a clear clinical concept.",
                "bullets": ["Concept first", "Options second", "Exam takeaway last"],
                "duration_hint": 4
            },
            {
                "type": "question_focus",
                "title": "Question Overview",
                "subtitle": "Read the stem visually. Do not memorize words.",
                "narration": "First, read the stem silently and look for the single clue that changes management or diagnosis. We will not just read it aloud; we will decode it.",
                "focus_terms": _safe_list(getattr(q, 'concept_tags', []), 4),
                "duration_hint": 8
            },
            {
                "type": "concept",
                "title": "Core Concept Before Answer",
                "subtitle": topic_name,
                "narration": _truncate_words(f"The tested idea is {topic_name}. Before selecting an option, connect the clinical clue with the underlying mechanism. {explanation}", 80),
                "bullets": explanation_chunks or [f"Core idea: {topic_name}", f"Correct direction: {correct_text}"],
                "focus_terms": _safe_list(getattr(q, 'concept_keywords', []), 5),
                "duration_hint": 10
            },
            {
                "type": "mechanism",
                "title": "Mechanism Map",
                "subtitle": "Clue to concept to answer",
                "narration": _truncate_words(f"Think in a chain. The clinical clue points to {topic_name}. That mechanism supports {correct_text}. This is why the answer is not a random fact.", 70),
                "bullets": [f"Clinical clue: identify the trigger", f"Mechanism: {topic_name}", f"Answer direction: {correct_text}"],
                "duration_hint": 8
            },
            {
                "type": "option_elimination",
                "title": "Eliminate Wrong Options",
                "subtitle": "Remove distractors one by one",
                "narration": "Now eliminate distractors. In UPSC CMS, wrong options are usually close, but each one fails at one decisive clinical or conceptual step.",
                "bullets": wrong_bullets or ["Remove options that do not match the key clue.", "Keep the option that best explains the full stem."],
                "duration_hint": 10
            },
            {
                "type": "answer_reveal",
                "title": "Correct Answer",
                "subtitle": correct_text,
                "narration": _truncate_words(f"The correct answer is {correct_text}. The reason is not the option label; the reason is that it best matches the concept and clinical clue in the stem.", 55),
                "bullets": [f"Correct option: {correct_letter}", correct_text],
                "duration_hint": 6
            },
            {
                "type": "concept",
                "title": "Why It Is Correct",
                "narration": _truncate_words(explanation, 90),
                "bullets": explanation_chunks or [explanation],
                "duration_hint": 12
            },
            {
                "type": "clinical_pearl",
                "title": "Clinical Pearl",
                "subtitle": "What to remember on exam day",
                "narration": _truncate_words(pearl, 70),
                "bullets": _split_sentences(pearl, 120)[:3],
                "duration_hint": 7
            },
            {
                "type": "mnemonic",
                "title": "Memory Trick",
                "subtitle": "Make it stick",
                "narration": _truncate_words(mnemonic, 70),
                "bullets": _split_sentences(mnemonic, 120)[:3],
                "duration_hint": 7
            },
            {
                "type": "exam_strategy",
                "title": "Exam Strategy",
                "subtitle": "How to solve faster",
                "narration": _truncate_words(strategy, 75),
                "bullets": _split_sentences(strategy, 120)[:3],
                "duration_hint": 7
            },
            {
                "type": "reference",
                "title": "Reference Anchor",
                "subtitle": "Standard textbook linkage",
                "narration": _truncate_words(f"Anchor this explanation to {reference}. Use the reference to revise the concept, not to memorize the option label.", 65),
                "bullets": [reference],
                "duration_hint": 6
            },
            {
                "type": "takeaway",
                "title": "UPSC CMS High Yield Takeaway",
                "subtitle": correct_text,
                "narration": _truncate_words(f"Final takeaway: recognize {topic_name}, eliminate distractors, and choose {correct_text} when the stem points to this mechanism.", 55),
                "bullets": [f"Concept: {topic_name}", f"Answer: {correct_text}", "Revise the clue, not only the fact"],
                "duration_hint": 5
            }
        ]
        
        return {
            "schema": SCRIPT_SCHEMA_VERSION,
            "question_id": q.id,
            "title": f"{subject_name} Question",
            "scenes": scenes,
            "metadata": {
                "subject": subject_name,
                "year": getattr(q, 'year', ''),
                "difficulty": getattr(q, 'difficulty', 'medium'),
                "question_text": q.question_text,
                "options": options,
                "correct_answer": correct_letter,
            }
        }

    def _script_passes_quality(self, script: dict[str, Any]) -> bool:
        if not script or script.get("schema") != SCRIPT_SCHEMA_VERSION:
            return False
        scenes = script.get("scenes", [])
        if not isinstance(scenes, list) or len(scenes) < 10:
            return False
        scene_types = {scene.get("type") for scene in scenes if isinstance(scene, dict)}
        if not REQUIRED_SCENE_TYPES.issubset(scene_types):
            return False

        narration_words = 0
        for scene in scenes:
            if not isinstance(scene, dict):
                return False
            narration = _clean_for_tts(scene.get("narration", ""))
            if not narration:
                return False
            if len(narration.split()) > MAX_SCENE_NARRATION_WORDS + 20:
                return False
            narration_words += len(narration.split())
        return narration_words >= 120

    # ------------------------------------------------------------------
    # TTS, Video Assembly, Subtitles, Quality, Upload
    # ------------------------------------------------------------------

    def _tts(self, text: str, output_path: str) -> bool:
        import edge_tts

        clean = _clean_for_tts(text)
        if not clean:
            return False

        # Indian English Professor voice for CMS
        voice = 'en-IN-PrabhatNeural'

        async def _run():
            comm = edge_tts.Communicate(clean, voice)
            await comm.save(output_path)

        try:
            asyncio.run(_run())
            return True
        except Exception as e:
            logger.error(f'TTS error: {e}', exc_info=True)
            # Try fallback voice
            try:
                voice = 'en-US-GuyNeural'
                async def _run2():
                    comm = edge_tts.Communicate(clean, voice)
                    await comm.save(output_path)
                asyncio.run(_run2())
                return True
            except Exception as e2:
                logger.error(f'TTS fallback error: {e2}')
                return False

    def _assemble(self, slide_data: list[dict[str, Any]], output_path: str) -> float:
        try:
            from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
        except ImportError:
            from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

        clips = []
        total_duration = 0.0
        
        for sd in slide_data:
            # Subtle zoom effect could be added here if needed, but keeping static for ultra-fast generation
            if sd['audio'] and os.path.exists(sd['audio']):
                try:
                    audio = AudioFileClip(sd['audio'])
                    duration = max(audio.duration + 0.8, sd['min_dur'])
                    clip = ImageClip(sd['slide']).with_duration(duration)
                    clip = self._apply_motion(clip, sd.get("scene_type", "lesson"))
                    clip = clip.with_audio(audio)
                    total_duration += duration
                except Exception as e:
                    logger.warning(f"Audio load failed: {e}, using min duration")
                    clip = self._apply_motion(ImageClip(sd['slide']).with_duration(sd['min_dur']), sd.get("scene_type", "lesson"))
                    total_duration += sd['min_dur']
            else:
                clip = self._apply_motion(ImageClip(sd['slide']).with_duration(sd['min_dur']), sd.get("scene_type", "lesson"))
                total_duration += sd['min_dur']
                
            clips.append(clip)

        final = concatenate_videoclips(clips, method='compose')
        final.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            logger=None,
        )

        # Cleanup clips
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
                
        return total_duration

    def _apply_motion(self, clip: Any, scene_type: str) -> Any:
        """Apply subtle motion design without making rendering fragile."""
        try:
            if hasattr(clip, "resized"):
                clip = clip.resized(lambda t: 1.0 + min(t, 8) * 0.003)
            elif hasattr(clip, "resize"):
                clip = clip.resize(lambda t: 1.0 + min(t, 8) * 0.003)
        except Exception:
            pass

        for method_name, args in (("with_fps", (24,)), ("fadein", (0.25,)), ("fadeout", (0.25,))):
            try:
                method = getattr(clip, method_name, None)
                if method:
                    clip = method(*args)
            except Exception:
                pass
        return clip

    def _write_vtt(self, slide_data: list[dict[str, Any]], output_path: str) -> None:
        """Generate WebVTT subtitles based on scene timings."""
        lines = ["WEBVTT", ""]
        
        current_time = 0.0
        for i, sd in enumerate(slide_data):
            audio_path = sd.get('audio')
            duration = sd.get('min_dur', 5.0)
            if audio_path and os.path.exists(audio_path):
                try:
                    from moviepy import AudioFileClip
                except ImportError:
                    from moviepy.editor import AudioFileClip
                try:
                    audio = AudioFileClip(audio_path)
                    duration = max(audio.duration + 0.8, duration)
                    audio.close()
                except Exception:
                    pass
            
            start_str = _format_vtt_time(current_time)
            end_str = _format_vtt_time(current_time + duration)
            
            narration = sd.get('narration', '')
            if narration:
                parts = _chunk_for_subtitles(narration, max_chars=95)
                cue_count = max(1, len(parts))
                for part_index, part in enumerate(parts, start=1):
                    part_start = current_time + ((part_index - 1) * duration / cue_count)
                    part_end = current_time + (part_index * duration / cue_count)
                    lines.append(f"{i+1}.{part_index}")
                    lines.append(f"{_format_vtt_time(part_start)} --> {_format_vtt_time(part_end)}")
                    lines.append(part)
                    lines.append("")
                
            current_time += duration
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def _quality_gate(self, slide_data: list, video_path: str, vtt_path: str, duration: float) -> None:
        """Ensure the generated video meets standards before uploading."""
        if len(slide_data) < 8:
            raise ValueError("Video has too few teaching scenes for V2 quality.")
        if any(not sd.get("narration") for sd in slide_data):
            raise ValueError("One or more scenes are missing narration.")
        if any(not os.path.exists(sd.get("slide", "")) for sd in slide_data):
            raise ValueError("One or more rendered slides are missing.")
        if any(not os.path.exists(sd.get("audio", "")) for sd in slide_data):
            raise ValueError("One or more narration audio files are missing.")
        if not os.path.exists(video_path):
            raise FileNotFoundError("Video file was not created.")
        
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb < 0.1:
            raise ValueError(f"Video file is too small ({size_mb:.2f} MB). Assembly likely failed.")
            
        if duration < 45.0:
            raise ValueError(f"Video duration too short ({duration:.1f}s).")
            
        if not os.path.exists(vtt_path):
            raise FileNotFoundError("VTT subtitles file was not created.")
        if os.path.getsize(vtt_path) < 32:
            raise ValueError("VTT subtitles file is unexpectedly small.")

    def _upload(self, file_path: str, file_name: str, content_type: str = "video/mp4") -> str | None:
        from supabase import create_client

        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

        if not url or not key:
            logger.warning('Supabase creds missing. Returning mock dev URL.')
            return f'https://dev.local/{self.bucket}/{file_name}'

        try:
            client = create_client(url, key)
            with open(file_path, 'rb') as f:
                client.storage.from_(self.bucket).upload(
                    path=file_name, file=f,
                    file_options={'content-type': content_type, 'upsert': 'true'}
                )

            public_url = client.storage.from_(self.bucket).get_public_url(file_name)
            logger.info(f'Uploaded: {public_url}')
            return public_url
        except Exception as e:
            logger.error(f'Upload error: {e}', exc_info=True)
            return None
            
    def _download_text(self, file_name: str) -> str | None:
        from supabase import create_client

        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:
            return None
            
        try:
            client = create_client(url, key)
            response = client.storage.from_(self.bucket).download(file_name)
            return response.decode('utf-8')
        except Exception:
            return None

    def _cleanup(self):
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass
