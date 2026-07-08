import logging
from .services import VideoGeneratorService

logger = logging.getLogger(__name__)

def generate_video_task(question_id: int):
    """
    Background task to generate a video for a given question.
    """
    logger.info(f"Starting video generation task for Q{question_id}")
    service = VideoGeneratorService()
    success = service.generate_for_question(question_id)
    
    if success:
        logger.info(f"Successfully generated video for Q{question_id}")
    else:
        logger.error(f"Failed to generate video for Q{question_id}")
