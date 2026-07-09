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
from django.utils import timezone
from questions.models import Question

logger = logging.getLogger(__name__)


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

    def generate_for_question(self, question_id: int):
        question = None
        try:
            question = Question.objects.select_related('subject').get(id=question_id)
            question.video_status = 'processing'
            question.video_error = ''
            question.save(update_fields=['video_status', 'video_error'])

            explanation = _effective_explanation(question)
            answer_text = _effective_answer(question)

            if not explanation and not answer_text:
                question.video_status = 'failed'
                question.video_error = 'No content to narrate. Generate AI or add admin override.'
                question.save(update_fields=['video_status', 'video_error'])
                return False

            # 1. Build section list
            sections = self._build_sections(question, explanation, answer_text)
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
                })

            # 3. Assemble video
            video_path = os.path.join(self.tmp_dir, f'q_{question_id}.mp4')
            self._assemble(slide_data, video_path)
            logger.info(f'Q{question_id}: Video assembled')

            # 4. Upload
            video_url = self._upload(video_path, f'q_{question_id}_video.mp4')
            if not video_url:
                raise Exception('Supabase upload failed')

            question.video_url = video_url
            question.video_status = 'completed'
            question.video_generated_at = timezone.now()
            question.save(update_fields=['video_url', 'video_status', 'video_generated_at'])
            logger.info(f'Q{question_id}: Video completed -> {video_url}')

            self._cleanup()
            return True

        except Exception as e:
            logger.error(f'Video gen failed Q{question_id}: {e}', exc_info=True)
            if question:
                question.video_status = 'failed'
                question.video_error = str(e)[:500]
                question.save(update_fields=['video_status', 'video_error'])
            self._cleanup()
            return False

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
        for sd in slide_data:
            if sd['audio'] and os.path.exists(sd['audio']):
                try:
                    audio = AudioFileClip(sd['audio'])
                    duration = max(audio.duration + 0.8, sd['min_dur'])
                    clip = ImageClip(sd['slide']).with_duration(duration)
                    clip = clip.with_audio(audio)
                except Exception as e:
                    logger.warning(f"Audio load failed: {e}, using min duration")
                    clip = ImageClip(sd['slide']).with_duration(sd['min_dur'])
            else:
                clip = ImageClip(sd['slide']).with_duration(sd['min_dur'])
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

    # ── Supabase upload ──────────────────────────────────────

    def _upload(self, file_path, file_name):
        from supabase import create_client

        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

        if not url or not key:
            logger.warning('Supabase creds missing. Dev URL returned.')
            return f'https://dev.local/videos/{file_name}'

        try:
            client = create_client(url, key)
            bucket = 'educational_videos'

            with open(file_path, 'rb') as f:
                client.storage.from_(bucket).upload(
                    path=file_name, file=f,
                    file_options={'content-type': 'video/mp4', 'upsert': 'true'}
                )

            public_url = client.storage.from_(bucket).get_public_url(file_name)
            logger.info(f'Uploaded: {public_url}')
            return public_url
        except Exception as e:
            logger.error(f'Upload error: {e}', exc_info=True)
            return None

    # ── Cleanup ──────────────────────────────────────────────

    def _cleanup(self):
        import shutil
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass
