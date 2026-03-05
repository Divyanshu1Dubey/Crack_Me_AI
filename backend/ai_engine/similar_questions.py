"""
Similar Questions Engine — finds questions testing the same medical concept.
Uses concept tags and keyword overlap for similarity matching.
"""
import logging
from collections import defaultdict

from django.db.models import Q

logger = logging.getLogger(__name__)


def find_similar_questions(question, max_results=5):
    """
    Find questions that test the same concept as the given question.
    Uses concept_tags overlap and topic matching.
    """
    from questions.models import Question

    similar_ids = set()
    results = []

    # 1. Same topic, different year
    if question.topic_id:
        topic_matches = (
            Question.objects
            .filter(topic=question.topic, is_active=True)
            .exclude(id=question.id)
            .order_by('-year')[:max_results]
        )
        for q in topic_matches:
            if q.id not in similar_ids:
                similar_ids.add(q.id)
                results.append(q)

    # 2. Overlapping concept_tags
    if question.concept_tags:
        tags = question.concept_tags if isinstance(question.concept_tags, list) else []
        if tags:
            tag_q = Q()
            for tag in tags:
                tag_q |= Q(concept_tags__icontains=tag)
            tag_matches = (
                Question.objects
                .filter(tag_q, is_active=True)
                .exclude(id=question.id)
                .exclude(id__in=similar_ids)
                .order_by('-year')[:max_results]
            )
            for q in tag_matches:
                if q.id not in similar_ids:
                    similar_ids.add(q.id)
                    results.append(q)

    # 3. Same subject + keyword overlap in question text
    if len(results) < max_results and question.subject_id:
        keywords = _extract_keywords(question.question_text)
        if keywords:
            kw_q = Q()
            for kw in keywords[:5]:
                kw_q |= Q(question_text__icontains=kw)
            kw_matches = (
                Question.objects
                .filter(kw_q, subject=question.subject, is_active=True)
                .exclude(id=question.id)
                .exclude(id__in=similar_ids)
                .order_by('-year')[:max_results - len(results)]
            )
            for q in kw_matches:
                if q.id not in similar_ids:
                    similar_ids.add(q.id)
                    results.append(q)

    return results[:max_results]


def populate_similar_questions():
    """
    Batch job: Populate similar_questions M2M field for all questions.
    Run after importing PYQs: python manage.py shell -c "from ai_engine.similar_questions import populate_similar_questions; populate_similar_questions()"
    """
    from questions.models import Question

    questions = Question.objects.filter(is_active=True)
    total = questions.count()
    updated = 0

    for i, question in enumerate(questions):
        similar = find_similar_questions(question, max_results=5)
        if similar:
            question.similar_questions.set(similar)
            updated += 1

        if (i + 1) % 50 == 0:
            logger.info(f"Processed {i + 1}/{total} questions, {updated} updated")

    logger.info(f"Done: {updated}/{total} questions have similar questions linked")
    return updated


def _extract_keywords(text):
    """Extract meaningful medical keywords from question text."""
    # Common medical stop words to filter out
    stop_words = {
        'the', 'is', 'in', 'of', 'and', 'a', 'to', 'for', 'with', 'on', 'by',
        'an', 'are', 'was', 'which', 'following', 'most', 'common', 'all',
        'except', 'true', 'false', 'regarding', 'about', 'not', 'what',
        'that', 'this', 'from', 'or', 'as', 'be', 'at', 'it', 'can', 'has',
        'have', 'may', 'include', 'includes', 'one', 'seen', 'found',
        'patient', 'year', 'old', 'presents', 'history', 'shows',
    }

    words = text.lower().split()
    keywords = []
    for word in words:
        cleaned = ''.join(c for c in word if c.isalnum())
        if cleaned and len(cleaned) > 3 and cleaned not in stop_words:
            keywords.append(cleaned)

    # Return unique keywords sorted by length (longer = more specific)
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return sorted(unique, key=len, reverse=True)[:10]
