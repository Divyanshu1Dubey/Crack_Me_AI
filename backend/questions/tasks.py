import json
import logging
from django.utils import timezone
from questions.models import Question
from ai_engine.services import AIService

logger = logging.getLogger(__name__)

def generate_ai_task(question_id: int):
    try:
        question = Question.objects.get(id=question_id)
        service = AIService()
        options_dict = {
            'A': question.option_a,
            'B': question.option_b,
            'C': question.option_c,
            'D': question.option_d,
        }
        
        result = service.explain_after_answer(
            question_text=question.question_text,
            options=options_dict,
            correct_answer=question.correct_answer,
            selected_answer=question.correct_answer,
            subject=question.subject.name if question.subject else '',
            topic=question.topic.name if question.topic else ''
        )
        
        question.ai_explanation = json.dumps(result)
        question.ai_answer = result.get('why_correct', '')
        question.ai_mnemonic = result.get('mnemonic', '')
        question.ai_clinical_pearl = result.get('clinical_pearl', '')
        question.learning_technique = result.get('exam_tip', '')
        
        textbook_ref = result.get('textbook_reference', {})
        if textbook_ref:
            question.ai_references = [textbook_ref]
            
        around_concepts = result.get('around_concepts', [])
        if around_concepts:
            question.concept_keywords = around_concepts
            
        question.ai_generated_at = timezone.now()
        question.ai_model = 'RoundRobin-11'
        question.ai_version = 'v1'
        question.save()
        logger.info(f"Generated AI for Q{question.id}")
        return True
    except Exception as e:
        logger.error(f"AI generation failed for Q{question_id}: {e}")
        return False
