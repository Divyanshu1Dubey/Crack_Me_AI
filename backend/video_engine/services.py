import os
import tempfile
import logging
from django.utils import timezone
from questions.models import Question
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_effective_answer(question):
    """Mirror the serializer logic: lock → admin override → AI → base."""
    if question.lock_answer:
        return question.admin_answer_override or question.get_correct_option_text()
    if question.admin_answer_override:
        return question.admin_answer_override
    return question.ai_answer or question.get_correct_option_text()


def _get_effective_explanation(question):
    """Mirror the serializer logic: lock → admin override → AI → base."""
    if question.lock_explanation:
        return question.admin_explanation_override or question.explanation
    if question.admin_explanation_override:
        return question.admin_explanation_override
    return question.ai_explanation or question.explanation


def _get_effective_mnemonic(question):
    if question.admin_mnemonic_override:
        return question.admin_mnemonic_override
    return question.ai_mnemonic or question.mnemonic


class VideoGeneratorService:
    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="crack_cms_videos_")

    def generate_for_question(self, question_id: int):
        try:
            question = Question.objects.get(id=question_id)
            question.video_status = 'processing'
            question.save(update_fields=['video_status'])

            # Step 1: Ensure we have SOME explanation content to narrate
            explanation = _get_effective_explanation(question)
            answer = _get_effective_answer(question)
            if not explanation and not answer:
                logger.warning(f"Q{question_id} has no explanation or answer content. Cannot generate video.")
                question.video_status = 'failed'
                question.video_error = 'No explanation content found. Generate AI or add an admin override first.'
                question.save(update_fields=['video_status', 'video_error'])
                return False

            # Step 2: Generate Audio (TTS)
            audio_path = self._generate_audio(question, answer, explanation)
            if not audio_path:
                raise Exception("Audio generation failed")

            # Step 3: Generate Slides & Animation (MoviePy)
            video_path = self._render_video(question, audio_path)
            if not video_path:
                raise Exception("Video rendering failed")

            # Step 4: Upload to Supabase
            video_url = self._upload_to_supabase(video_path, f"q_{question_id}_video.mp4")
            if not video_url:
                raise Exception("Upload to Supabase failed")

            # Finalize
            question.video_url = video_url
            question.video_status = 'completed'
            question.video_generated_at = timezone.now()
            question.save(update_fields=['video_url', 'video_status', 'video_generated_at'])

            # Cleanup
            self._cleanup()
            return True

        except Exception as e:
            logger.error(f"Video generation failed for Q{question_id}: {e}", exc_info=True)
            if 'question' in locals():
                question.video_status = 'failed'
                question.video_error = str(e)[:500]
                question.save(update_fields=['video_status', 'video_error'])
            self._cleanup()
            return False

    def _generate_audio(self, question, answer, explanation):
        """Generates TTS using Edge TTS and returns the file path."""
        import edge_tts
        import asyncio

        audio_file = os.path.join(self.tmp_dir, f"audio_{question.id}.mp3")

        # Build a narration script from effective content
        script = f"Question: {question.question_text}\n"
        script += f"The correct answer is {question.correct_answer}.\n"
        if answer:
            script += f"Answer: {answer}\n"
        if explanation:
            script += f"Explanation: {explanation}\n"

        mnemonic = _get_effective_mnemonic(question)
        if mnemonic:
            script += f"Mnemonic: {mnemonic}\n"

        if question.ai_clinical_pearl:
            script += f"Clinical Pearl: {question.ai_clinical_pearl}\n"

        voice = "en-US-GuyNeural"  # High quality male voice

        async def _run_tts():
            communicate = edge_tts.Communicate(script, voice)
            await communicate.save(audio_file)

        try:
            asyncio.run(_run_tts())
            logger.info(f"Audio generated for Q{question.id} ({len(script)} chars)")
            return audio_file
        except Exception as e:
            logger.error(f"Edge TTS error for Q{question.id}: {e}", exc_info=True)
            return None

    def _render_video(self, question, audio_path):
        """Renders video using MoviePy and Pillow."""
        from moviepy import ColorClip, TextClip, AudioFileClip, CompositeVideoClip

        video_file = os.path.join(self.tmp_dir, f"video_{question.id}.mp4")
        audio_clip = None
        try:
            # Load audio
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            # Background
            bg_clip = ColorClip(size=(1280, 720), color=(15, 23, 42)).with_duration(duration)

            # Text (Simplified for now)
            display_text = "CrackLabs AI Educational Video\n" + question.question_text[:100]
            if len(question.question_text) > 100:
                display_text += "..."

            txt_clip = TextClip(
                text=display_text,
                font_size=40, color='white', size=(1000, 600), method='caption'
            ).with_position('center').with_duration(duration)

            # Combine
            final_clip = CompositeVideoClip([bg_clip, txt_clip])
            final_clip = final_clip.with_audio(audio_clip)

            # Export
            final_clip.write_videofile(
                video_file,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                logger=None
            )
            logger.info(f"Video rendered for Q{question.id} ({duration:.1f}s)")
            return video_file
        except Exception as e:
            logger.error(f"MoviePy error for Q{question.id}: {e}", exc_info=True)
            return None
        finally:
            if audio_clip:
                audio_clip.close()

    def _upload_to_supabase(self, file_path, file_name):
        """Uploads the rendered MP4 to Supabase Storage."""
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not found. Returning fake URL for dev.")
            return f"https://dev.local/videos/{file_name}"

        try:
            supabase = create_client(supabase_url, supabase_key)
            bucket_name = 'educational_videos'

            with open(file_path, 'rb') as f:
                # Use upsert to allow re-generating videos
                res = supabase.storage.from_(bucket_name).upload(
                    path=file_name,
                    file=f,
                    file_options={"content-type": "video/mp4", "upsert": "true"}
                )

            public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
            logger.info(f"Video uploaded to Supabase: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Supabase upload error: {e}", exc_info=True)
            return None

    def _cleanup(self):
        """Removes temporary files."""
        import shutil
        try:
            shutil.rmtree(self.tmp_dir)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
