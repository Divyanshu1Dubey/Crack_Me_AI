import os
import tempfile
import logging
from django.utils import timezone
from questions.models import Question
from django.conf import settings

logger = logging.getLogger(__name__)

class VideoGeneratorService:
    def __init__(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="crack_cms_videos_")
        
    def generate_for_question(self, question_id: int):
        try:
            question = Question.objects.get(id=question_id)
            question.video_status = 'processing'
            question.save()
            
            # Step 1: Ensure AI content exists
            if not question.ai_generated_at:
                logger.warning(f"Q{question_id} missing AI fields. Cannot generate video.")
                question.video_status = 'failed'
                question.video_error = 'AI content not found. Generate AI first.'
                question.save()
                return False
                
            # Step 2: Generate Audio (TTS)
            audio_path = self._generate_audio(question)
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
            question.save()
            
            # Cleanup
            self._cleanup()
            return True
            
        except Exception as e:
            logger.error(f"Video generation failed for Q{question_id}: {e}")
            if 'question' in locals():
                question.video_status = 'failed'
                question.video_error = str(e)
                question.save()
            self._cleanup()
            return False

    def _generate_audio(self, question):
        """Generates TTS using Edge TTS and returns the file path."""
        import edge_tts
        import asyncio
        
        audio_file = os.path.join(self.tmp_dir, f"audio_{question.id}.mp3")
        
        # Script generation
        script = f"Question: {question.question_text}\n"
        script += f"The correct answer is {question.correct_answer}.\n"
        script += f"Explanation: {question.ai_answer}\n"
        if question.ai_clinical_pearl:
            script += f"Clinical Pearl: {question.ai_clinical_pearl}\n"
        if question.ai_mnemonic:
            script += f"Mnemonic: {question.ai_mnemonic}\n"
            
        voice = "en-US-GuyNeural" # High quality male voice
        
        async def _run_tts():
            communicate = edge_tts.Communicate(script, voice)
            await communicate.save(audio_file)
            
        try:
            asyncio.run(_run_tts())
            return audio_file
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return None

    def _render_video(self, question, audio_path):
        """Renders video using MoviePy and Pillow."""
        from moviepy import ColorClip, TextClip, AudioFileClip, CompositeVideoClip
        # For simplicity, we'll use basic TextClip here.
        
        video_file = os.path.join(self.tmp_dir, f"video_{question.id}.mp4")
        audio_clip = None
        try:
            # Load audio
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            
            # Background
            bg_clip = ColorClip(size=(1280, 720), color=(15, 23, 42)).with_duration(duration)
            
            # Text (Simplified for now)
            txt_clip = TextClip(
                text="CrackLabs AI Educational Video\n" + question.question_text[:50] + "...", 
                font_size=50, color='white', size=(1000, 600), method='caption'
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
            return video_file
        except Exception as e:
            logger.error(f"MoviePy error: {e}")
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
                res = supabase.storage.from_(bucket_name).upload(
                    path=file_name,
                    file=f,
                    file_options={"content-type": "video/mp4"}
                )
                
            public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
            return public_url
        except Exception as e:
            logger.error(f"Supabase upload error: {e}")
            return None

    def _cleanup(self):
        """Removes temporary files."""
        import shutil
        try:
            shutil.rmtree(self.tmp_dir)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
