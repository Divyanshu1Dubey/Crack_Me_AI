import json
import logging
from django.utils import timezone
from questions.models import Question
from ai_engine.services import AIService

logger = logging.getLogger(__name__)


def _model_label(service) -> str:
    """``ai_model`` stamp, as ``ai_engine.views`` writes it."""
    provider = getattr(service, 'last_provider', None) if service is not None else None
    return f'roundrobin/{provider}' if isinstance(provider, str) and provider else 'roundrobin'


def apply_explain_result(question, result, service=None) -> list:
    """Copy a usable ``AIService.explain_after_answer`` result onto
    ``question`` (in memory) and return the updated field names.

    Shared by ``generate_ai_task`` and ``manage.py backfill_empty_ai`` /
    ``generate_missing_ai``:

    * a failed / unparsed result (provider outage: ``raw_response`` or the
      "All AI services are temporarily unavailable" sentence) changes
      nothing -- it used to become the question's official explanation;
    * ``lock_answer`` protects ``ai_answer``; ``lock_explanation`` protects
      every explanation-side field;
    * curated text is never replaced by an empty value, and the curated
      (non ``ai_``) fields ``learning_technique`` and ``concept_keywords``
      are only filled while they are still empty.
    """
    from questions.ai_per_question import usable_ai_text, usable_explain_result

    if not usable_explain_result(result):
        return []
    if question.lock_answer and question.lock_explanation:
        return []

    updated = []

    def _set(field, value):
        setattr(question, field, value)
        updated.append(field)

    why_correct = usable_ai_text(result.get('why_correct'))
    if not question.lock_answer and why_correct:
        _set('ai_answer', why_correct)

    if not question.lock_explanation:
        _set('ai_explanation', json.dumps(result))
        mnemonic = usable_ai_text(result.get('mnemonic'))
        if mnemonic:
            _set('ai_mnemonic', mnemonic)
        pearl = usable_ai_text(result.get('clinical_pearl'))
        if pearl:
            _set('ai_clinical_pearl', pearl)
        exam_tip = usable_ai_text(result.get('exam_tip'))
        if exam_tip and not (question.learning_technique or '').strip():
            _set('learning_technique', exam_tip)
        textbook_ref = result.get('textbook_reference', {})
        if textbook_ref:
            _set('ai_references', [textbook_ref])
        around_concepts = result.get('around_concepts', [])
        if around_concepts and not question.concept_keywords:
            _set('concept_keywords', around_concepts)

    if updated:
        question.ai_generated_at = timezone.now()
        question.ai_model = _model_label(service)
        question.ai_version = 'v1'
        updated += ['ai_generated_at', 'ai_model', 'ai_version']
    return updated


def generate_reveal_sections_task(question_id: int):
    """Fill one question's missing reveal-panel AI sections (why correct,
    clinical significance, memory trick, concept) with one LLM call.

    Queued by the per-question ``ai/*`` GET endpoints
    (``ai_per_question.queue_generation``), which never call an LLM in the
    request thread. Writes only empty fields.
    """
    from questions.ai_per_question import generate_missing_sections
    return generate_missing_sections(question_id)


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
            topic=question.topic.name if question.topic else '',
            # Cached under the question's own key, the one explain-answer reads.
            question_id=question.id,
        )

        fields = apply_explain_result(question, result, service)
        if not fields:
            logger.warning(f"AI generation for Q{question.id} produced no usable content; nothing saved")
            return False
        # Partial save: a long AI call must not write back stale copies of
        # fields an admin edited meanwhile.
        question.save(update_fields=fields)
        logger.info(f"Generated AI for Q{question.id}")
        return True
    except Exception as e:
        logger.error(f"AI generation failed for Q{question_id}: {e}")
        return False
