"""Which test questions' answers a student may see after a test.

Tests reuse the question bank's rule (``questions.views.user_can_view_answer``):
staff and premium users see every answer and explanation, everyone else only
the admin-curated showcase questions. A free student who finishes a generated
test therefore learns right / wrong per question, but not the answer key or
the explanations -- otherwise generating and submitting tests would be an
unlimited way around the question bank's paywall.
"""
from accounts.utils import is_premium

# Values /review/ and the attempt detail return in place of the answer parts
# of a question the student may not see. ``answer_locked`` tells the client.
LOCKED_REVIEW_VALUES = {
    'correct_answer': None,
    'explanation': '',
    'mnemonic': '',
    'concept_explanation': '',
    'textbook_references': [],
    'reference_text': '',
}


def answer_visibility(user, question_ids) -> dict:
    """``{question_id: bool}``: may ``user`` see each question's answer?

    ``is_premium`` runs once and the showcase lookup is one query for the
    whole test (not one per question). Showcase questions are still passed
    through ``user_can_view_answer``, so any narrowing the shared rule
    applies (for example to scholarship questions) applies here too.
    """
    from accounts.models_freemium import FreeShowcaseQuestion
    from questions.views import user_can_view_answer

    ids = [qid for qid in dict.fromkeys(question_ids) if qid is not None]
    authenticated = bool(user is not None and getattr(user, 'is_authenticated', False))
    premium = bool(is_premium(user)) if authenticated else False
    # The shared rule's first two cases: premium users (is_premium already
    # counts admins and superusers) and staff see every answer.
    if premium or (authenticated and getattr(user, 'is_staff', False)):
        return dict.fromkeys(ids, True)
    showcase = set(
        FreeShowcaseQuestion.objects.filter(question_id__in=ids).values_list('question_id', flat=True)
    )
    return {
        qid: qid in showcase and user_can_view_answer(user, qid, premium=premium)
        for qid in ids
    }


def lock_answer(row: dict) -> dict:
    """Blank the answer parts of one review row (in place) and mark it."""
    for key, value in LOCKED_REVIEW_VALUES.items():
        if key in row:
            row[key] = list(value) if isinstance(value, list) else value
    row['answer_locked'] = True
    return row
