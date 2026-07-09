"""
CrackLabs AI - Multi-slide educational video generator.

Pipeline:
  1. Build sections (title, question, options, answer, explanation, pearl, mnemonic, outro)
  2. Render each section as a professional slide (Pillow)
  3. Generate section narration audio (Edge TTS)
  4. Assemble slides + audio into final MP4 (MoviePy)
  5. Upload to Supabase Storage
"""
import os
import re
import tempfile
import logging
import asyncio
import json
import hashlib
import shutil
from pathlib import Path
from typing import Any
from django.conf import settings
from django.utils import timezone
from questions.models import Question

logger = logging.getLogger(__name__)
ENGINE_VERSION = 'video-engine-v2'


# ── Content helpers ──────────────────────────────────────────

def _effective_explanation(q):
    """Mirror serializer: lock → admin → AI → base."""
    if q.lock_explanation:
        return q.admin_explanation_override or q.explanation
    return q.admin_explanation_override or q.ai_explanation or q.explanation


def _effective_answer(q):
    if q.lock_answer:
        return q.admin_answer_override or q.get_correct_option_text()
    return q.admin_answer_override or q.ai_answer or q.get_correct_option_text()


def _effective_mnemonic(q):
    return q.admin_mnemonic_override or q.ai_mnemonic or q.mnemonic


def _clean_for_tts(text):
    """Remove markdown & special chars for natural-sounding narration."""
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'#{1,6}\s+', '', t)
    t = re.sub(r'`(.*?)`', r'\1', t)
    t = re.sub(r'\\u\d{4}', ' ', t)
    t = re.sub(r'[{}\[\]"\'\\]', '', t)
    t = ' '.join(t.split())
    return t.strip()


def _split_text(text, max_chars=550):
    """Split long text into chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Normalize sentence endings
    normalized = text.replace('. ', '.|').replace('? ', '?|').replace('! ', '!|')
    sentences = [s.strip() for s in normalized.split('|') if s.strip()]

    chunks, current = [], ''
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = f'{current} {sent}'.strip()
    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:max_chars]]


# ── Main service ─────────────────────────────────────────────

class VideoGeneratorService:
    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp(prefix='cracklabs_video_')
        self.bucket = 'educational_videos'

    def generate_for_question(self, question_id: int):
        question = None
        try:
            question = Question.objects.select_related('subject').get(id=question_id)
            question.video_status = 'processing'
            question.video_error = ''
            question.save(update_fields=['video_status', 'video_error'])

            explanation = _effective_explanation(question)
            answer_text = _effective_answer(question)
            expected_version = ENGINE_VERSION

            if not explanation and not answer_text:
                question.video_status = 'failed'
                question.video_error = 'No content to narrate. Generate AI or add admin override.'
                question.save(update_fields=['video_status', 'video_error'])
                return False

            # 1. Build section list
            sections = self._build_sections(question, explanation, answer_text)
            content_hash = self._content_hash(question)
            script = {
                'question_id': question.id,
                'content_hash': content_hash,
                'engine_version': expected_version,
                'scene_count': len(sections),
            }
            logger.info(f'Q{question_id}: Built {len(sections)} slides')

            # 2. Render slides & generate audio
            slide_data = []
            for i, sec in enumerate(sections):
                slide_path = os.path.join(self.tmp_dir, f'slide_{i:02d}.png')
                audio_path = os.path.join(self.tmp_dir, f'audio_{i:02d}.mp3')

                sec['slide'].save(slide_path, 'PNG')
                audio_ok = self._tts(sec['narration'], audio_path)

                slide_data.append({
                    'slide': slide_path,
                    'audio': audio_path if audio_ok else None,
                    'min_dur': sec.get('min_dur', 5),
                    'title': sec.get('title', ''),
                    'narration': sec.get('narration', ''),
                })

            # 3. Assemble video
            video_path = os.path.join(self.tmp_dir, f'q_{question_id}.mp4')
            duration = self._assemble(slide_data, video_path)
            vtt_path = os.path.join(self.tmp_dir, f'q_{question_id}.vtt')
            self._write_vtt(slide_data, vtt_path)
            logger.info(f'Q{question_id}: Video assembled')

            # 4. Upload
            video_name = f'q_{question_id}_{content_hash}_video.mp4'
            thumbnail_name = f'q_{question_id}_{content_hash}_thumb.png'
            vtt_name = f'q_{question_id}_{content_hash}.vtt'

            video_url = self._upload(video_path, video_name, 'video/mp4')
            if not video_url:
                raise Exception('Supabase upload failed')

            thumbnail_path = slide_data[0]['slide'] if slide_data else ''
            thumb_url = self._upload(thumbnail_path, thumbnail_name, 'image/png') or ''
            self._upload(vtt_path, vtt_name, 'text/vtt')
            self._save_script_cache(script, content_hash)

            question.video_url = video_url
            question.video_thumbnail = thumb_url
            question.video_status = 'completed'
            question.video_duration = int(round(duration))
            question.video_version = expected_version
            question.video_generated_at = timezone.now()
            question.video_error = ''
            question.save(update_fields=[
                'video_url',
                'video_thumbnail',
                'video_status',
                'video_duration',
                'video_version',
                'video_generated_at',
                'video_error',
            ])
            logger.info(f'Q{question_id}: Video completed -> {video_url}')
            return True

        except Exception as e:
            logger.error(f'Video gen failed Q{question_id}: {e}', exc_info=True)
            if question:
                question.video_status = 'failed'
                question.video_error = str(e)[:500]
                question.save(update_fields=['video_status', 'video_error'])
            return False
        finally:
            self._cleanup()

    def _content_hash(self, q: Question) -> str:
        payload = {
            'engine': ENGINE_VERSION,
            'question': q.question_text,
            'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
            'correct': q.correct_answer,
            'answer': _effective_answer(q),
            'explanation': _effective_explanation(q),
            'mnemonic': _effective_mnemonic(q),
            'subject': q.subject.name if q.subject else '',
            'topic': q.topic.name if q.topic else '',
            'year': q.year,
        }
        raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    def _script_object_name(self, question_id: int, content_hash: str) -> str:
        return f'scripts/q_{question_id}_{content_hash}_script.json'

    def _local_script_path(self, question_id: int, content_hash: str) -> Path:
        root = Path(getattr(settings, 'MEDIA_ROOT', Path.cwd() / 'media'))
        return root / 'video_engine' / 'scripts' / f'q_{question_id}_{content_hash}_script.json'

    def _save_script_cache(self, script: dict[str, Any], content_hash: str) -> None:
        question_id = int(script.get('question_id') or 0)
        if not question_id:
            return

        text = json.dumps(script, ensure_ascii=True, indent=2)
        local_path = self._local_script_path(question_id, content_hash)
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(text, encoding='utf-8')
        except Exception as exc:
            logger.warning('Could not write local script cache for Q%s: %s', question_id, exc)

        remote_path = os.path.join(self.tmp_dir, f'q_{question_id}_{content_hash}_script.json')
        try:
            Path(remote_path).write_text(text, encoding='utf-8')
            self._upload(remote_path, self._script_object_name(question_id, content_hash), 'application/json')
        except Exception as exc:
            logger.warning('Could not upload script cache for Q%s: %s', question_id, exc)

    # ── Section builder ──────────────────────────────────────

    def _build_sections(self, q, explanation, answer_text):
        from .slide_renderer import SlideRenderer
        renderer = SlideRenderer()

        options = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
        mnemonic = _effective_mnemonic(q)
        pearl = q.ai_clinical_pearl or ''
        subj = q.subject.name if q.subject else 'General'
        exp_chunks = _split_text(explanation) if explanation else []

        # Calculate total slide count for progress bar
        total = 4 + len(exp_chunks)  # title + question + options + answer + explanations
        if pearl:
            total += 1
        if mnemonic:
            total += 1
        total += 1  # outro

        sections = []
        step = 1

        # ── 1. Title ──
        sections.append({
            'slide': renderer.render_title(subj, q.year, q.difficulty, q.id, step, total),
            'narration': (
                f'Welcome to CrackLabs AI. '
                f"Today we'll study a {q.difficulty} {subj} question from UPSC CMS {q.year}. "
                f"Let's break it down step by step."
            ),
            'min_dur': 5,
        })
        step += 1

        # ── 2. Question ──
        sections.append({
            'slide': renderer.render_question(q.question_text, step, total),
            'narration': f'Here is the question. {_clean_for_tts(q.question_text)}',
            'min_dur': 5,
        })
        step += 1

        # ── 3. Options ──
        opts_narration = "Let's look at the options. "
        for lbl in ['A', 'B', 'C', 'D']:
            opts_narration += f'Option {lbl}: {_clean_for_tts(options[lbl])}. '
        opts_narration += 'Take a moment to think about your answer.'
        sections.append({
            'slide': renderer.render_options(options, step, total),
            'narration': opts_narration,
            'min_dur': 8,
        })
        step += 1

        # ── 4. Answer reveal ──
        correct_text = options.get(q.correct_answer, '')
        sections.append({
            'slide': renderer.render_answer(options, q.correct_answer, step, total),
            'narration': (
                f'The correct answer is {q.correct_answer}: {_clean_for_tts(correct_text)}. '
                f"Now let's understand why."
            ),
            'min_dur': 4,
        })
        step += 1

        # ── 5. Explanation (may span multiple slides) ──
        for i, chunk in enumerate(exp_chunks):
            sections.append({
                'slide': renderer.render_explanation(chunk, i + 1, len(exp_chunks), step, total),
                'narration': _clean_for_tts(chunk),
                'min_dur': 6,
            })
            step += 1

        # ── 6. Clinical pearl (optional) ──
        if pearl:
            sections.append({
                'slide': renderer.render_clinical_pearl(pearl, step, total),
                'narration': f'Here is an important clinical pearl. {_clean_for_tts(pearl)}',
                'min_dur': 5,
            })
            step += 1

        # ── 7. Mnemonic (optional) ──
        if mnemonic:
            sections.append({
                'slide': renderer.render_mnemonic(mnemonic, step, total),
                'narration': f'To help you remember, here is a mnemonic. {_clean_for_tts(mnemonic)}',
                'min_dur': 5,
            })
            step += 1

        # ── 8. Outro ──
        sections.append({
            'slide': renderer.render_outro(step, total),
            'narration': (
                'Thank you for learning with CrackLabs AI. '
                'Keep practicing, keep learning. '
                'Visit cracklabs dot app for more questions and AI-powered study tools.'
            ),
            'min_dur': 5,
        })

        return sections

    # ── Audio (Edge TTS) ─────────────────────────────────────

    def _tts(self, text, output_path):
        import edge_tts

        clean = _clean_for_tts(text)
        if not clean:
            return False

        voice = 'en-US-GuyNeural'

        async def _run():
            comm = edge_tts.Communicate(clean, voice)
            await comm.save(output_path)

        try:
            asyncio.run(_run())
            return True
        except Exception as e:
            logger.error(f'TTS error: {e}', exc_info=True)
            return False

    # ── Video assembly (MoviePy) ─────────────────────────────

    def _assemble(self, slide_data, output_path):
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

        clips = []
        total_duration = 0.0
        for sd in slide_data:
            if sd['audio'] and os.path.exists(sd['audio']):
                try:
                    audio = AudioFileClip(sd['audio'])
                    duration = max(audio.duration + 0.8, sd['min_dur'])
                    clip = ImageClip(sd['slide']).with_duration(duration)
                    clip = clip.with_audio(audio)
                except Exception as e:
                    logger.warning(f"Audio load failed: {e}, using min duration")
                    duration = float(sd['min_dur'])
                    clip = ImageClip(sd['slide']).with_duration(duration)
            else:
                duration = float(sd['min_dur'])
                clip = ImageClip(sd['slide']).with_duration(duration)
            sd['duration'] = float(duration)
            total_duration += float(duration)
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

    def _write_vtt(self, slide_data: list[dict[str, Any]], output_path: str) -> None:
        lines = ['WEBVTT', '', 'NOTE Generated by CrackLabs AI Video Engine', '']
        cursor = 0.0
        cue_id = 1
        for sd in slide_data:
            duration = float(sd.get('duration') or sd.get('min_dur') or 5)
            narration = _clean_for_tts(sd.get('narration') or '')
            if not narration:
                narration = sd.get('title') or 'Lesson scene'
            start = cursor
            end = cursor + duration
            lines.extend([
                str(cue_id),
                f'{self._format_vtt_time(start)} --> {self._format_vtt_time(end)}',
                narration[:180],
                '',
            ])
            cue_id += 1
            cursor = end

        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')

    def _format_vtt_time(self, total_seconds: float) -> str:
        total_ms = int(round(max(total_seconds, 0) * 1000))
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        seconds, ms = divmod(rem, 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}'

    # ── Supabase upload ──────────────────────────────────────

    def _upload(self, file_path, file_name, content_type='application/octet-stream'):
        from supabase import create_client

        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

        if not url or not key:
            logger.warning('Supabase creds missing. Dev URL returned.')
            return f'https://dev.local/videos/{file_name}'

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

    # ── Cleanup ──────────────────────────────────────────────

    def _cleanup(self):
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass
