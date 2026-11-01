"""Which test questions' answers a student may see, and which tests they may take.

Tests follow the question bank's ONE rule (``questions.views``:
``user_can_view_answer`` / ``free_showcase_rows``): staff, admins and premium
users see every answer; everyone else only the admin-curated free showcase
questions, and never a scholarship-challenge question.

A finished test gives away more than its review shows. Its score is a
right / wrong signal, and a completed attempt can always be retaken:
submitting all-A, then all-B, ... (or one answered question at a time)
reveals the whole answer key. So a student is never scored on a question
whose answer they may not see:

* ``/generate/`` and ``/generate-adaptive/`` draw such a student's questions
  from the free showcase only (``free_question_q``). Full paper mocks and
  PYQ-year simulations keep the real paper and stay premium, as before;
* ``/start/`` and ``/submit/`` answer 402 ``upgrade_required`` for a test
  with any question whose answer the student may not see
  (``has_locked_questions``). That also closes retakes of older tests;
* ``/review/`` and the attempt detail still lock the answer parts of such
  rows (attempts finished before this rule, or while the student was
  premium). Their stem and options are cut as on locked question-bank rows
  (``questions.answer_leak.redact_public_text``): at any answer /
  explanation label an import left in them, and at a correctness flag
  such as "(correct)" or a tick, together with the reason printed after
  it (``lock_answer``). The student's own pick and its right / wrong stay:
  they are that attempt's result, shown when it was scored, and no new
  attempt can be scored on such a question (the 402s above).
"""
from django.db.models import Exists, OuterRef, Q

from accounts.utils import is_premium
from questions.answer_leak import redact_public_text

# Values /review/ and the attempt detail return in place of the answer parts
# of a question the student may not see. ``answer_locked`` tells the client.
LOCKED_REVIEW_VALUES = {
    'correct_answer': None,
    'explanation': '',
    'mnemonic': '',
    'concept_explanation': '',
    'textbook_references': [],
    'reference_text': '',
    # Textbook pointers: a chapter title can name the diagnosis (locked
    # question-bank rows blank the same fields, see questions.views
    # _ANSWER_REVEALING_DETAIL_FIELDS).
    'book_reference': '',
    'chapter': '',
    'page_number': '',
}

LOCKED_TEST_FEATURE = 'Mock Tests'


def has_full_access(user) -> bool:
    """Staff, admins, superusers and premium users see every answer.

    The first two cases of ``questions.views.user_can_view_answer``
    (``is_premium`` already counts admins and superusers).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if any(getattr(user, flag, False) for flag in ('is_staff', 'is_admin', 'is_superuser')):
        return True
    return bool(is_premium(user))


def free_question_ids():
    """Subquery: ids of the questions whose answers every student may see
    (``questions.views.free_showcase_rows``, never a scholarship question)."""
    from questions.views import free_showcase_rows

    return free_showcase_rows().values('question_id')


def free_question_q():
    """Q() on Question selecting the free questions (see free_question_ids)."""
    return Q(pk__in=free_question_ids()) & Q(is_scholarship_eligible=False)


def free_showcase_exists():
    """Exists() for Question querysets: is this row a free question?

    Used for the ``is_showcase`` annotation QuestionListSerializer reads to
    decide whether a row's answer media may be shown.
    """
    from questions.views import free_showcase_rows

    return Exists(free_showcase_rows().filter(question_id=OuterRef('pk')))


def locked_questions_exist():
    """Exists() for Test querysets: does the test have a question outside the
    free set? (``_has_locked_questions``, read by has_locked_questions.)"""
    from .models import Test

    return Exists(
        Test.questions.through.objects
        .filter(test_id=OuterRef('pk'))
        .exclude(question_id__in=free_question_ids())
    )


def has_locked_questions(user, test, *, full_access=None) -> bool:
    """True when ``test`` has a question whose answer ``user`` may not see,
    i.e. when scoring the test would give that answer away."""
    if full_access is None:
        full_access = has_full_access(user)
    if full_access:
        return False
    annotated = getattr(test, '_has_locked_questions', None)
    if annotated is not None:
        return bool(annotated)
    return test.questions.exclude(pk__in=free_question_ids()).exists()


def answer_visibility(user, question_ids, *, full_access=None) -> dict:
    """``{question_id: bool}``: may ``user`` see each question's answer?

    One query for the whole test (not one per question). Free questions are
    exactly ``free_showcase_rows`` -- the set ``user_can_view_answer`` checks
    -- so scholarship questions stay locked here too, and /start/ and
    /review/ can never disagree about a row.
    """
    from questions.views import free_showcase_rows

    ids = [qid for qid in dict.fromkeys(question_ids) if qid is not None]
    if full_access is None:
        full_access = has_full_access(user)
    if full_access:
        return dict.fromkeys(ids, True)
    free = set(free_showcase_rows().filter(question_id__in=ids).values_list('question_id', flat=True))
    return {qid: qid in free for qid in ids}


def _redact_locked_text(row: dict) -> None:
    """Cut the stem and the options of a locked row (in place) as on locked
    question-bank rows: ``questions.answer_leak.redact_public_text``, the one
    rule for every surface. A stem stops at its first answer / explanation
    label and loses the flags (ticks, "(correct)") on the options it lists;
    an option stops at its first label or correctness flag, the reason
    printed after a flag goes with it ("Conjunctival xerosis <tick> (...)"
    -> "Conjunctival xerosis"), and a flag that leads it is dropped. Rows carry
    the options as ``option_a``..``option_d`` (attempt detail, the mistake
    notebook of analytics.serializers) or as ``options`` ``{'A': ..}``
    (/review/)."""
    redact_public_text(row)


def lock_answer(row: dict) -> dict:
    """Blank the answer parts of one review row (in place) and mark it."""
    from questions.serializers import locked_concept_tags

    for key, value in LOCKED_REVIEW_VALUES.items():
        if key in row:
            row[key] = list(value) if isinstance(value, list) else value
    if 'concept_tags' in row:
        # Concept terms can name the answer: only markers such as
        # "high_yield" stay, as on locked question-bank rows.
        row['concept_tags'] = locked_concept_tags(row['concept_tags'])
    _redact_locked_text(row)
    row['answer_locked'] = True
    return row


def strip_explanation_images(row: dict) -> dict:
    """Drop explanation figures (part of the answer) from a serialized
    question, as the question bank's detail redaction does."""
    for key in ('images', 'stem_images'):
        if isinstance(row.get(key), list):
            row[key] = [img for img in row[key] if (img or {}).get('role') != 'explanation']
    return row


def locked_test_response(action='take'):
    """402 for a test with questions the student may not see (see module
    docstring). ``action`` is 'take' (start) or 'submit'."""
    from rest_framework.response import Response

    what = 'submit it and see your result' if action == 'submit' else 'take it'
    return Response(
        {
            'code': 'upgrade_required',
            'feature': LOCKED_TEST_FEATURE,
            'message': (
                'This test includes questions from the premium question bank. '
                f'Subscribe to {what}, with answers and explanations for every question.'
            ),
        },
        status=402,
    )
