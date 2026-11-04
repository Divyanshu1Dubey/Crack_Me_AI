from collections import defaultdict
import logging
import math
import random

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Count, F, FloatField, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Cast, Coalesce

from .entitlement import (
    LOCKED_TEST_FEATURE, answer_visibility, free_question_q, free_showcase_exists,
    has_full_access, has_locked_questions, lock_answer, locked_questions_exist,
    locked_test_response, strip_explanation_images,
)
from .models import FREE_TEST_MAX_QUESTIONS, Test, TestAttempt, QuestionResponse
from .serializers import (
    TestSerializer, TestDetailSerializer,
    TestAttemptSerializer, TestAttemptDetailSerializer,
    SubmitAnswerSerializer,
)
from questions.models import Question, Subject, Topic
from questions.serializers import (
    STALE_EXPLANATION_NOTICE, QuestionListSerializer, explanation_for_another_key, public_subject_name,
)
from accounts.permissions import IsControlTowerAdmin
from accounts.utils import is_premium as _is_premium

logger = logging.getLogger(__name__)

VALID_TEST_TYPES = frozenset(code for code, _ in Test.TEST_TYPES)
VALID_EXAM_TYPES = frozenset(code for code, _ in Test.EXAM_CHOICES)
EXAM_LABELS = dict(Test.EXAM_CHOICES)
# Generators that are not told which exam to use build UPSC CMS tests: the
# Test row defaults to exam_type='cms', so its questions must be CMS too.
DEFAULT_EXAM_TYPE = 'cms'

DAILY_TEST_QUESTIONS = 20      # "Daily Quick Test" is always 20 questions
FULL_PAPER_QUESTIONS = 120     # one UPSC CMS paper
CMS_PAPER_MINUTES = 120        # ... answered in 120 minutes
# Full paper mocks keep the real paper for every student; for a free student
# they stay premium (402 at /start/), as before. Every other generated test
# draws a free student's questions from the free showcase (entitlement.py).
FULL_PAPER_TYPES = ('paper1', 'paper2')

# (negative_marking, negative_mark_value) of each exam's real marking scheme,
# expressed per question (score = correct - incorrect * value).
EXAM_MARKING = {
    'cms': (True, 0.33),       # UPSC CMS: one third of a mark per wrong answer
    'neet_pg': (True, 0.25),   # NEET PG: +4 / -1
    'ini_cet': (True, 0.33),   # INI-CET: +1 / -1/3
    'fmge': (False, 0.0),      # no negative marking
    'usmle': (False, 0.0),     # no negative marking
}

# Test XP (see _xp_for_submission).
XP_PER_NEW_CORRECT = 10
XP_COMPLETION_BONUS = 5
COMPLETION_BONUS_DAILY_CAP = 10

# A submission later than started_at + time limit + this grace is still
# accepted and scored (the player auto-submits an expired attempt when it is
# resumed), but it is flagged late: no XP, off the leaderboard. The grace
# covers the 0:00 auto-submit round trip on a slow connection.
LATE_SUBMIT_GRACE_SECONDS = 120

# /generate-adaptive/: the weakest areas by accuracy, among those with enough
# answers for the accuracy to mean something.
ADAPTIVE_MIN_ATTEMPTS = 3
ADAPTIVE_WEAK_AREAS = 10

# Generated test titles (the card title is the only thing that tells two
# 20-question practice tests apart).
GENERATED_TITLES = {'daily': 'Daily Quick Test', 'mixed': 'Mixed Practice'}

# Fields of QuestionListSerializer that can give an answer away, left out of
# the exam payload (/start/, and GET /tests/<id>/ for students) for every
# viewer, premium included: the study aids (textbook excerpts, concept tags),
# the textbook pointers (a chapter title can name the diagnosis), the
# screenshot of the textbook page that discusses the answer and the generated
# explanation video. The explanation figures are dropped from the image lists
# as well (_without_exam_hidden_fields). After submit, /review/ returns the
# textbook pointers, the explanation figures and the video to a student who may
# see the answer (_review_media).
EXAM_HIDDEN_FIELDS = (
    'textbook_references', 'reference_text', 'concept_tags', 'concept_id',
    'book_name', 'chapter', 'page_number', 'page_screenshot',
    'video_url', 'video_status', 'video_thumbnail', 'video_duration', 'video_subtitles_url',
)

# Older importers (e.g. import_neet_pg) left Question.exam_type at its 'cms'
# default and recorded the real exam only in exam_source ('NEET PG',
# 'INI-CET (recall)', ...). These prefixes identify such rows.
_EXAM_SOURCE_PREFIXES = {
    'neet_pg': ('NEET',),
    'ini_cet': ('INI',),
    'usmle': ('USMLE',),
    'fmge': ('FMGE',),
}
_NON_CMS_SOURCE_PREFIXES = ('NEET', 'INI', 'USMLE', 'FMGE', 'PLAB')


def exam_scope_q(exam_type):
    """Q() selecting the questions of one exam.

    A non-default value in either exam_type or exam_source identifies the
    exam; UPSC CMS is what remains once every other exam is excluded.
    """
    if exam_type == 'cms':
        scope = Q(exam_type='cms')
        for prefix in _NON_CMS_SOURCE_PREFIXES:
            scope &= ~Q(exam_source__istartswith=prefix)
        return scope
    scope = Q(exam_type=exam_type)
    legacy = Q()
    for prefix in _EXAM_SOURCE_PREFIXES.get(exam_type, ()):
        legacy |= Q(exam_source__istartswith=prefix)
    if legacy:
        scope |= Q(exam_type='cms') & legacy
    return scope


def official_tests_q():
    """The published library: tests created by an admin / importer.

    Practice tests generated through /generate/, /generate-adaptive/ and
    /pyq-simulation/ are created unpublished, so an admin's own practice
    tests no longer leak into every student's library.
    """
    return Q(is_published=True) & (
        Q(created_by__isnull=True)
        | Q(created_by__role='admin')
        | Q(created_by__is_superuser=True)
    )


class _BadRequest(Exception):
    """Raised by the request parsers below; becomes a 400 response."""


def _optional_int(value, name, *, lo=None, hi=None, message=None):
    """Parse an optional integer field: None / '' -> None, junk -> 400."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise _BadRequest(message or f'{name} must be an integer')
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        raise _BadRequest(message or f'{name} must be an integer')
    if (lo is not None and parsed < lo) or (hi is not None and parsed > hi):
        raise _BadRequest(message or f'{name} is out of range')
    return parsed


def _exam_type_param(value):
    """Validated exam_type from a request body, DEFAULT_EXAM_TYPE if omitted."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_EXAM_TYPE
    if not isinstance(value, str) or value.strip() not in VALID_EXAM_TYPES:
        raise _BadRequest('Invalid exam_type')
    return value.strip()


def _time_limit_seconds(test):
    return max(0, int(test.time_limit_minutes or 0)) * 60


def _cms_paper_minutes(question_count, papers=1):
    """Real UPSC CMS timing, 120 minutes per paper, but never more than 1.5
    minutes per question so a small partial set is not given hours."""
    return max(10, min(CMS_PAPER_MINUTES * max(1, papers), math.ceil(question_count * 1.5)))


def _active_attempt(user, test):
    return (
        TestAttempt.objects
        .filter(user=user, test=test, is_completed=False)
        .order_by('-started_at')
        .first()
    )


def _questions_for_attempt(test, attempt):
    """The test's questions in this attempt's order, ready to serialize.

    The order is a shuffle seeded by the attempt id: each attempt gets its own
    random order and a resumed attempt gets exactly the same one, with no
    schema change. Relations the serializer reads are loaded up front (the
    old per-question subject/topic/images/duplicate queries made starting a
    120-question mock cost several hundred queries); `is_showcase` is
    annotated the way QuestionViewSet does (free showcase rows only, never
    a scholarship question), so the serializer never has to look it up per
    row.
    """
    questions = list(
        test.questions
        .select_related('subject', 'topic', 'verified_by')
        .prefetch_related('images', 'cluster_memberships')
        .annotate(is_showcase=free_showcase_exists())
        .order_by('id')
    )
    random.Random(attempt.pk).shuffle(questions)
    _attach_duplicate_clusters(questions)
    return questions


def _attach_duplicate_clusters(questions):
    """Pre-compute the duplicate-cluster fields QuestionListSerializer would
    otherwise look up with one query per clustered question."""
    from questions.models import DuplicateMember

    cluster_of = {}
    for question in questions:
        members = list(question.cluster_memberships.all())  # prefetched
        if members:
            newest = max(members, key=lambda m: (m.cluster_id, m.similarity_score or 0))
            cluster_of[question.pk] = newest.cluster_id
    sizes = {}
    if cluster_of:
        sizes = dict(
            DuplicateMember.objects
            .filter(cluster_id__in=set(cluster_of.values()))
            .order_by()
            .values('cluster_id')
            .annotate(n=Count('id'))
            .values_list('cluster_id', 'n')
        )
    for question in questions:
        cluster_id = cluster_of.get(question.pk)
        if cluster_id is not None:
            question._cluster_id = cluster_id
        question._cluster_member_count = sizes.get(cluster_id, 0) if cluster_id is not None else 0


def _without_exam_hidden_fields(question_rows):
    """Serialized exam questions without what can give the answer away
    (EXAM_HIDDEN_FIELDS) and without explanation figures (role
    'explanation'), whoever the viewer is: the player shows the question
    side only. /review/ returns the answer media after submit."""
    for row in question_rows:
        for field in EXAM_HIDDEN_FIELDS:
            row.pop(field, None)
        strip_explanation_images(row)
    return question_rows


# Explanation video fields of a /review/ row (_review_media).
REVIEW_VIDEO_FIELDS = ('video_url', 'video_status', 'video_thumbnail', 'video_duration', 'video_subtitles_url')


def _review_media(question, *, visible, request, memo):
    """The figures and the explanation video of one /review/ row.

    * ``stem_images``: the question-side figures (runtime role not
      'explanation', ``questions.image_context.runtime_role``, the rule the
      image serve view applies), with the caption only after the reveal.
    * ``explanation_images``: the explanation figures with their signed URL
      (``serialize_image_for_student(img, revealed=True)``), only when the
      student may see this question's answer (``visible``,
      ``entitlement.answer_visibility``); ``[]`` otherwise.
    * the video fields: the finished explanation video under the same
      entitlement (``video_status`` without a URL while it is not finished),
      ``None`` for a locked row, as QuestionListSerializer blanks them.

    Reads the ``images`` prefetch (no query per row); ``memo`` caches the
    runtime roles for one response.
    """
    from questions.image_context import active_images, runtime_role, serialize_image_for_student
    from questions.serializers import _derive_subtitles_url

    stem_images, explanation_images = [], []
    for img in active_images(question):
        role = runtime_role(question, img, memo)
        if role == 'explanation':
            if visible:
                explanation_images.append(serialize_image_for_student(
                    img, revealed=True, question=question, request=request, role=role, memo=memo))
            continue
        stem_images.append(serialize_image_for_student(
            img, revealed=visible, question=question, request=request, role=role, memo=memo))
    media = {'stem_images': stem_images, 'explanation_images': explanation_images}
    media.update(dict.fromkeys(REVIEW_VIDEO_FIELDS))
    if visible:
        media['video_status'] = question.video_status or None
        video_url = (question.video_url or '').strip()
        if video_url and question.video_status == 'completed':
            media.update({
                'video_url': video_url,
                'video_thumbnail': (question.video_thumbnail or '').strip() or None,
                'video_duration': question.video_duration,
                'video_subtitles_url': _derive_subtitles_url(video_url) or None,
            })
    return media


def _no_free_questions_response():
    """402 for a free student whose selection has questions, none of them free."""
    return Response(
        {
            'code': 'upgrade_required',
            'feature': LOCKED_TEST_FEATURE,
            'message': (
                'Free practice tests use the free question set, which has no questions '
                'for this selection yet. Subscribe to practise the full question bank.'
            ),
        },
        status=402,
    )


def _attempt_result(attempt, request, **extra):
    data = TestAttemptSerializer(attempt, context={'request': request}).data
    data.update(extra)
    return data


def _already_submitted(attempt, request):
    """Repeated submit of a completed attempt: keep the 400, but hand back the
    stored result so the player can show it instead of a dead retry."""
    return Response(
        {
            'error': 'Test already submitted',
            'code': 'already_submitted',
            'attempt_id': attempt.id,
            'result': _attempt_result(attempt, request),
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _xp_for_submission(user, attempt, clean_answers):
    """XP for a scored, non-empty test attempt. Earned once per question and
    once per test, so retakes and re-generated tests cannot farm it:

    * 10 XP per correct answer on a question the student has not seen in an
      earlier completed test attempt (once /review/ has revealed a question's
      answer it can never earn test XP again);
    * a 5 XP completion bonus the first time the student completes this test,
      at most COMPLETION_BONUS_DAILY_CAP times a day (counted over all of
      today's non-empty completions, including retakes).
    """
    earlier = TestAttempt.objects.filter(user=user, is_completed=True).exclude(pk=attempt.pk)
    xp = 0
    correct_ids = [qid for qid, ans in clean_answers.items() if ans.get('is_correct')]
    if correct_ids:
        seen = set(
            QuestionResponse.objects
            .filter(attempt__in=earlier, question_id__in=correct_ids)
            .values_list('question_id', flat=True)
        )
        xp += XP_PER_NEW_CORRECT * sum(1 for qid in correct_ids if qid not in seen)
    if not earlier.filter(test_id=attempt.test_id).exists():
        day_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        completions_today = (
            earlier.filter(completed_at__gte=day_start)
            .filter(Q(correct_count__gt=0) | Q(incorrect_count__gt=0))
            .count()
        )
        if completions_today < COMPLETION_BONUS_DAILY_CAP:
            xp += XP_COMPLETION_BONUS
    return xp


def _answer_seconds(clean_answers, budget_seconds):
    """{question_id: seconds} for the answered questions of a submission.

    The client's per-question timings are untrusted: each is clamped like
    the study-time figures, and they are scaled down proportionally when
    they add up to more than the attempt actually lasted.
    """
    from questions.study_time import clamp_seconds

    seconds = {
        qid: clamp_seconds(ans.get('time_taken'))
        for qid, ans in clean_answers.items() if ans.get('selected')
    }
    reported = sum(seconds.values())
    budget = max(0, int(budget_seconds or 0))
    if reported > budget:
        seconds = {qid: value * budget // reported for qid, value in seconds.items()}
    return seconds


def _bump_topic_performance(user, subject_id, topic_id, total, correct, incorrect, now, seconds=0):
    """Atomic (F()) increment of one UserTopicPerformance row (attempt
    counts and the answer time behind the /analytics "Avg Time" column).

    Looks the row up with filter().first(): with topic=None the unique
    constraint does not stop duplicate rows (NULLs are distinct), and
    get_or_create() then raised MultipleObjectsReturned.
    """
    from analytics.models import UserTopicPerformance

    row_id = (
        UserTopicPerformance.objects
        .filter(user=user, subject_id=subject_id, topic_id=topic_id)
        .order_by('pk')
        .values_list('pk', flat=True)
        .first()
    )
    if row_id is None:
        row_id = UserTopicPerformance.objects.get_or_create(
            user=user, subject_id=subject_id, topic_id=topic_id,
        )[0].pk
    UserTopicPerformance.objects.filter(pk=row_id).update(
        total_attempts=F('total_attempts') + total,
        correct_answers=F('correct_answers') + correct,
        incorrect_answers=F('incorrect_answers') + incorrect,
        total_time_seconds=F('total_time_seconds') + max(0, int(seconds or 0)),
        last_attempted=now,
    )


def _record_submission_analytics(user, attempt, clean_answers, questions_map, correct, answered):
    """Dashboard analytics for a scored, non-empty attempt; returns the XP
    earned. Runs inside the submit transaction with F() increments so
    concurrent writers (QBank answers, a second tab) cannot lose updates.

    A late attempt (attempt.is_late) still counts as practice (activity,
    streak, topic accuracy) but earns no XP, which also keeps it off the
    XP-ranked leaderboard."""
    from analytics.models import DailyActivity, StudyStreak

    daily, _ = DailyActivity.objects.get_or_create(user=user, date=timezone.localdate())
    DailyActivity.objects.filter(pk=daily.pk).update(
        questions_attempted=F('questions_attempted') + answered,
        correct_answers=F('correct_answers') + correct,
        tests_completed=F('tests_completed') + 1,
        time_spent_minutes=F('time_spent_minutes') + max(1, int((attempt.time_taken_seconds or 0) / 60)),
    )

    xp_earned = 0 if attempt.is_late else _xp_for_submission(user, attempt, clean_answers)
    streak, _ = StudyStreak.objects.get_or_create(user=user)
    streak.record_activity()
    if xp_earned:
        streak.add_xp(xp_earned)

    seconds_by_question = _answer_seconds(clean_answers, attempt.time_taken_seconds)
    # subject_id -> [total, correct, incorrect, seconds]; same per (subject_id, topic_id).
    subject_counts = defaultdict(lambda: [0, 0, 0, 0])
    topic_counts = defaultdict(lambda: [0, 0, 0, 0])
    for qid, ans in clean_answers.items():
        question = questions_map.get(qid)
        if not ans['selected'] or question is None or not question.subject_id:
            continue
        slot = 1 if ans.get('is_correct') else 2
        buckets = [subject_counts[question.subject_id]]
        if question.topic_id:
            buckets.append(topic_counts[(question.subject_id, question.topic_id)])
        for bucket in buckets:
            bucket[0] += 1
            bucket[slot] += 1
            bucket[3] += seconds_by_question.get(qid, 0)

    now = timezone.now()
    for subject_id, (total, ok, bad, seconds) in subject_counts.items():
        _bump_topic_performance(user, subject_id, None, total, ok, bad, now, seconds)
    for (subject_id, topic_id), (total, ok, bad, seconds) in topic_counts.items():
        _bump_topic_performance(user, subject_id, topic_id, total, ok, bad, now, seconds)
    return xp_earned


class TestViewSet(viewsets.ModelViewSet):
    """Test CRUD with start, submit, and result actions."""
    queryset = Test.objects.filter(is_published=True)
    filterset_fields = ['test_type', 'subject', 'topic', 'exam_type', 'is_published']

    def get_queryset(self):
        queryset = (
            Test.objects.select_related('subject', 'topic')
            .annotate(_question_count=Count('questions', distinct=True))
            # Explicit: Meta.ordering is ignored once the Count adds a GROUP
            # BY, which left the paginated library in arbitrary order.
            .order_by('-created_at', '-pk')
        )
        user = getattr(self.request, 'user', None)
        authenticated = bool(user and user.is_authenticated)
        if authenticated:
            # The viewer's attempt count, in the same query (TestSerializer
            # used to run one COUNT per listed test).
            attempts = (
                TestAttempt.objects.filter(test=OuterRef('pk'), user=user)
                .order_by().values('test').annotate(n=Count('id')).values('n')
            )
            queryset = queryset.annotate(
                _user_attempt_count=Coalesce(Subquery(attempts, output_field=IntegerField()), Value(0)),
                # Has a question outside the free set: a free student may not
                # take the test (start gate, is_free_for_current_user).
                _has_locked_questions=locked_questions_exist(),
            )
        is_staff_user = authenticated and (
            getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
        )
        if not is_staff_user:
            # Students see the official, published library (created by an
            # admin / importer) plus the practice tests they generated
            # themselves -- never other students' generated tests and never
            # unpublished drafts. Applies to every action (list, retrieve,
            # start, results), not just list/retrieve. Submit and review look
            # the attempt up by (id, user) instead, so unpublishing a test
            # does not break an in-flight attempt or a past review.
            visible = official_tests_q()
            if authenticated:
                visible |= Q(created_by=user)
            queryset = queryset.filter(visible)
        if self.action == 'list':
            # ?scope=library -> the official library only; ?scope=mine -> the
            # viewer's own generated tests. Listing them separately keeps the
            # library reachable however many practice tests a student makes.
            scope = (self.request.query_params.get('scope') or '').strip().lower()
            if scope == 'mine':
                queryset = queryset.filter(created_by=user) if authenticated else queryset.none()
            elif scope == 'library':
                queryset = queryset.filter(official_tests_q())
        elif self.action == 'retrieve':
            queryset = queryset.prefetch_related(Prefetch(
                'questions',
                queryset=Question.objects.select_related('subject', 'topic', 'verified_by')
                .prefetch_related('images', 'cluster_memberships')
                .annotate(is_showcase=free_showcase_exists()),
            ))
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestDetailSerializer
        return TestSerializer

    def get_permissions(self):
        if self.action in [
            'create', 'update', 'partial_update', 'destroy',
            'create_manual', 'set_questions', 'publish', 'unpublish', 'duplicate_test', 'safe_update'
        ]:
            return [IsControlTowerAdmin()]
        return [permissions.IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        """Test detail with its questions (prefetched in get_queryset).

        The duplicate-cluster fields are computed for all questions at once
        -- QuestionListSerializer otherwise runs one COUNT per clustered
        question -- and, as in /start/, students (premium included) get no
        answer media: no study aids, textbook pointers, page screenshot,
        explanation video or explanation figures (EXAM_HIDDEN_FIELDS).
        Admins get the stored payload (test preview).
        """
        test = self.get_object()
        _attach_duplicate_clusters(list(test.questions.all()))
        data = self.get_serializer(test).data
        user = request.user
        if not (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
            _without_exam_hidden_fields(data.get('questions') or [])
        return Response(data)

    @action(detail=False, methods=['post'], url_path='create-manual')
    def create_manual(self, request):
        """Create manual draft test with explicit question selection."""
        def parse_int(value, default):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def parse_float(value, default):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        def parse_bool(value, default):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ['true', '1', 'yes']:
                    return True
                if lowered in ['false', '0', 'no']:
                    return False
            return default

        title = (request.data.get('title') or '').strip()
        question_ids = request.data.get('question_ids', [])
        if not title:
            return Response({'error': 'title is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(question_ids, list):
            return Response({'error': 'question_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        subject_id = request.data.get('subject_id') or None
        topic_id = request.data.get('topic_id') or None
        if subject_id and not Subject.objects.filter(id=subject_id).exists():
            return Response({'error': 'subject_id is invalid'}, status=status.HTTP_400_BAD_REQUEST)
        if topic_id and not Topic.objects.filter(id=topic_id).exists():
            return Response({'error': 'topic_id is invalid'}, status=status.HTTP_400_BAD_REQUEST)

        validated_questions = Question.objects.filter(id__in=question_ids, is_active=True)

        test = Test.objects.create(
            title=title,
            test_type=request.data.get('test_type', 'mixed'),
            description=request.data.get('description', ''),
            subject_id=subject_id,
            topic_id=topic_id,
            num_questions=max(validated_questions.count(), parse_int(request.data.get('num_questions', validated_questions.count() or 20), validated_questions.count() or 20)),
            time_limit_minutes=parse_int(request.data.get('time_limit_minutes', 30), 30),
            negative_marking=parse_bool(request.data.get('negative_marking', True), True),
            negative_mark_value=parse_float(request.data.get('negative_mark_value', 0.33), 0.33),
            is_published=False,
            created_by=request.user,
        )
        if validated_questions.exists():
            test.questions.set(validated_questions)
            test.num_questions = test.questions.count()
            test.save(update_fields=['num_questions'])

        serializer = TestSerializer(test, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='set-questions')
    def set_questions(self, request, pk=None):
        """Replace test question set using search-filtered IDs from admin."""
        test = self.get_object()
        question_ids = request.data.get('question_ids', [])
        if not isinstance(question_ids, list):
            return Response({'error': 'question_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            test.questions.set(Question.objects.filter(id__in=question_ids, is_active=True))
            num_questions = test.questions.count()
            Test.objects.filter(pk=test.pk).update(num_questions=num_questions, version=F('version') + 1, updated_at=timezone.now())
            test.refresh_from_db(fields=['num_questions', 'version', 'updated_at'])
        serializer = TestSerializer(test, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='publish')
    def publish(self, request, pk=None):
        test = self.get_object()
        if test.questions.count() == 0:
            return Response({'error': 'Cannot publish a test with no questions'}, status=status.HTTP_400_BAD_REQUEST)
        Test.objects.filter(pk=test.pk).update(is_published=True, version=F('version') + 1, updated_at=timezone.now())
        test.refresh_from_db(fields=['id', 'is_published', 'version'])
        return Response({'message': 'Test published', 'id': test.id, 'is_published': True, 'version': test.version})

    @action(detail=True, methods=['patch'], url_path='unpublish')
    def unpublish(self, request, pk=None):
        test = self.get_object()
        Test.objects.filter(pk=test.pk).update(is_published=False, version=F('version') + 1, updated_at=timezone.now())
        test.refresh_from_db(fields=['id', 'is_published', 'version'])
        return Response({'message': 'Test unpublished', 'id': test.id, 'is_published': False, 'version': test.version})

    @action(detail=True, methods=['post'], url_path='duplicate')
    def duplicate_test(self, request, pk=None):
        """Duplicate a test as draft for safe edits."""
        source = self.get_object()
        duplicate = Test.objects.create(
            title=f"{source.title} (Copy)",
            test_type=source.test_type,
            description=source.description,
            subject=source.subject,
            topic=source.topic,
            num_questions=source.num_questions,
            time_limit_minutes=source.time_limit_minutes,
            negative_marking=source.negative_marking,
            negative_mark_value=source.negative_mark_value,
            is_published=False,
            created_by=request.user,
        )
        duplicate.questions.set(source.questions.all())
        serializer = TestSerializer(duplicate, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='safe-update')
    def safe_update(self, request, pk=None):
        """Safeguarded update for live tests; requires force=true if attempts exist."""
        test = self.get_object()
        has_attempts = test.attempts.exists()
        force_raw = request.data.get('force', False)
        if isinstance(force_raw, bool):
            force = force_raw
        elif isinstance(force_raw, str):
            normalized_force = force_raw.strip().lower()
            if normalized_force not in ['true', '1', 'yes', 'false', '0', 'no']:
                return Response({'error': 'force must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)
            force = normalized_force in ['true', '1', 'yes']
        else:
            return Response({'error': 'force must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)

        if test.is_published and has_attempts and not force:
            return Response(
                {'error': 'Live test has attempts. Pass force=true to apply versioned update.'},
                status=status.HTTP_409_CONFLICT,
            )

        editable = ['title', 'description', 'test_type', 'time_limit_minutes', 'negative_marking', 'negative_mark_value', 'subject', 'topic']
        dirty = False
        for field in editable:
            if field in request.data:
                value = request.data.get(field)
                if field in ['subject', 'topic']:
                    if value and ((field == 'subject' and not Subject.objects.filter(id=value).exists()) or (field == 'topic' and not Topic.objects.filter(id=value).exists())):
                        return Response({'error': f'{field} is invalid'}, status=status.HTTP_400_BAD_REQUEST)
                    setattr(test, f'{field}_id', value or None)
                elif field == 'time_limit_minutes':
                    try:
                        setattr(test, field, int(value))
                    except (TypeError, ValueError):
                        return Response({'error': 'time_limit_minutes must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
                elif field == 'negative_mark_value':
                    try:
                        setattr(test, field, float(value))
                    except (TypeError, ValueError):
                        return Response({'error': 'negative_mark_value must be a number'}, status=status.HTTP_400_BAD_REQUEST)
                elif field == 'negative_marking':
                    if isinstance(value, bool):
                        setattr(test, field, value)
                    elif isinstance(value, str) and value.strip().lower() in ['true', '1', 'yes', 'false', '0', 'no']:
                        setattr(test, field, value.strip().lower() in ['true', '1', 'yes'])
                    else:
                        return Response({'error': 'negative_marking must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    setattr(test, field, value)
                dirty = True

        if dirty:
            with transaction.atomic():
                Test.objects.select_for_update().get(pk=test.pk)
                test.save()
                Test.objects.filter(pk=test.pk).update(version=F('version') + 1, updated_at=timezone.now())
                test.refresh_from_db()

        serializer = TestSerializer(test, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate_test(self, request):
        """Generate a practice test from the question bank.

        Rules enforced here, whatever the client sends:
          * test_type must be one of Test.TEST_TYPES (an arbitrary string used
            to be stored, and test_type='daily' with 500 questions slipped
            past the free-test limit);
          * 'daily' is always 20 questions; paper1 / paper2 are always a full
            120-question paper with the real 120-minute CMS limit;
          * questions come from one exam (exam_type, default 'cms');
          * a UPSC CMS paper mock goes by each question's own paper (subject
            paper only for rows without one); other exams have no real
            papers (import_neet_pg sets paper=1 on every row), so their
            paper mocks follow the subject's paper;
          * ids and years are validated (400, not a 500);
          * the test is private to its creator (is_published=False);
          * a student without full access (entitlement.has_full_access) is
            only ever scored on free questions: their tests draw from the
            free showcase (never a scholarship question), and a selection
            with questions but no free ones is a 402 upgrade_required. Full
            paper mocks keep the real paper (minus scholarship questions)
            and stay premium: /start/ answers 402, as before.
        """
        data = request.data
        if not isinstance(data, dict):
            return Response({'error': 'Request body must be an object'}, status=status.HTTP_400_BAD_REQUEST)
        test_type = data.get('test_type') or 'mixed'
        if not isinstance(test_type, str) or test_type not in VALID_TEST_TYPES:
            return Response({'error': 'Invalid test_type'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            num_questions = int(data.get('num_questions', 20))
        except (TypeError, ValueError):
            return Response({'error': 'num_questions must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        if num_questions <= 0:
            return Response({'error': 'num_questions must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)
        if num_questions > 500:
            return Response({'error': 'num_questions must be less than or equal to 500'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exam_type = _exam_type_param(data.get('exam_type'))
            subject_id = _optional_int(data.get('subject_id'), 'subject_id', lo=1)
            topic_id = _optional_int(data.get('topic_id'), 'topic_id', lo=1)
            year = _optional_int(data.get('year'), 'year', lo=1900, hi=2100)
        except _BadRequest as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        q_filter = Q(is_active=True) & exam_scope_q(exam_type)
        title_parts = []
        subject = topic = None

        if test_type == 'subject':
            if subject_id is None:
                return Response({'error': 'subject_id is required for a subject test'}, status=status.HTTP_400_BAD_REQUEST)
            subject = Subject.objects.filter(pk=subject_id).first()
            if subject is None:
                return Response({'error': 'Invalid subject_id'}, status=status.HTTP_400_BAD_REQUEST)
            q_filter &= Q(subject_id=subject.pk)
            title_parts.append(public_subject_name(subject.name))
        elif test_type == 'topic':
            if topic_id is None:
                return Response({'error': 'topic_id is required for a topic test'}, status=status.HTTP_400_BAD_REQUEST)
            topic = Topic.objects.select_related('subject').filter(pk=topic_id).first()
            if topic is None:
                return Response({'error': 'Invalid topic_id'}, status=status.HTTP_400_BAD_REQUEST)
            q_filter &= Q(topic_id=topic.pk)
            subject = topic.subject
            title_parts.append(topic.name)
        elif test_type == 'pyq_year':
            if year is None:
                return Response({'error': 'year is required for a previous-year test'}, status=status.HTTP_400_BAD_REQUEST)
            q_filter &= Q(year=year)
            title_parts.append(f"PYQ {year}")
        elif test_type in ('paper1', 'paper2'):
            paper_no = 1 if test_type == 'paper1' else 2
            if exam_type == 'cms':
                # A question's own paper wins; the subject's paper is only
                # the fallback for rows without one (Subject.paper defaults
                # to 1, so "subject paper OR question paper" put paper-2
                # PYQs into the Paper 1 mock).
                q_filter &= (Q(paper=paper_no) | (~Q(paper__in=(1, 2)) & Q(subject__paper=paper_no)))
            else:
                q_filter &= Q(subject__paper=paper_no)
            title_parts.append(f"Paper {paper_no} Mock")
            num_questions = FULL_PAPER_QUESTIONS
        elif test_type == 'daily':
            num_questions = DAILY_TEST_QUESTIONS
            title_parts.append(GENERATED_TITLES['daily'])
        elif test_type == 'mixed':
            title_parts.append(GENERATED_TITLES['mixed'])

        pool = q_filter
        free_pool = False
        if not has_full_access(request.user):
            free_pool = test_type not in FULL_PAPER_TYPES
            pool = q_filter & (free_question_q() if free_pool else ~Q(is_scholarship_eligible=True))

        questions = list(Question.objects.filter(pool).values_list('id', flat=True))
        if not questions:
            if free_pool and Question.objects.filter(q_filter).exists():
                return _no_free_questions_response()
            return Response(
                {'error': 'No active questions found for this simulation type. Please check question imports and paper mapping.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(questions) > num_questions:
            questions = random.sample(questions, num_questions)

        title = ' | '.join(title_parts) if title_parts else 'Practice Test'
        title = f"{title} — {len(questions)} Questions"

        if test_type in ('paper1', 'paper2'):
            time_limit = _cms_paper_minutes(len(questions))
        else:
            time_limit = max(len(questions) * 1.5, 10)  # 1.5 min per question
        negative_marking, negative_mark_value = EXAM_MARKING.get(exam_type, EXAM_MARKING['cms'])

        test = Test.objects.create(
            title=title,
            test_type=test_type,
            exam_type=exam_type,
            subject=subject,
            topic=topic,
            num_questions=len(questions),
            time_limit_minutes=int(time_limit),
            negative_marking=negative_marking,
            negative_mark_value=negative_mark_value,
            is_published=False,
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='start')
    def start_attempt(self, request, pk=None):
        """Start (or resume) a test attempt.

        Previously this endpoint created a fresh TestAttempt and
        re-shuffled the question pool on every call. Two side effects
        that hurt students:

        1. Reloading the page (or a network blip that triggered a
           re-fetch from the frontend's useEffect) destroyed the
           student's current answers and current question index, then
           showed them a completely different paper.
        2. The unique_together on QuestionResponse(attempt, question)
           was fine in isolation, but the lack of a one-active-attempt
           constraint let two attempts target the same question pool
           from different devices, double-charging analytics and
           double-counting XP on submit.

        Fix: if an in-flight attempt already exists for this
        (user, test), resume it (same attempt_id, same started_at and,
        because the order is a shuffle seeded by the attempt id, the same
        question order). Otherwise create a new attempt. The
        one_active_test_attempt_per_user partial unique constraint on
        TestAttempt enforces the "at most one active attempt" invariant at
        the DB level; two racing starts (double click, two tabs) both
        resume the attempt that won the insert instead of one getting a
        500 IntegrityError.

        The response carries ``remaining_seconds`` (time limit minus the
        time elapsed since ``started_at``) so a reload continues the clock
        instead of granting a fresh full timer, and
        ``last_completed_attempt_id`` (the student's latest completed attempt
        of this test, or null): when a submit went through but its response
        was lost, a reload starts a fresh attempt, and this lets the player
        still show the stored result.
        """
        test = self.get_object()

        # Freemium gate (Task 7, 2026-08-04): a non-premium user may start a
        # test ONLY if it has at most FREE_TEST_MAX_QUESTIONS (20) questions,
        # which covers the Daily Quick Test, Mixed Practice and Subject-wise
        # generated tests. The count is the *real* number of attached
        # questions (`num_questions` is not maintained by every creator) and
        # nothing the client sends affects it: the old test_type == 'daily'
        # exemption let a client-chosen 500-question "daily" test through.
        # The `is_free_preview` admin flag stays retired (admins had marked
        # full Paper-1 / PYQ-year simulations free). Premium and admin users
        # bypass the gate.
        user = request.user
        question_count = getattr(test, '_question_count', None)
        if question_count is None:
            question_count = test.questions.count()
        if (
            int(question_count or 0) > FREE_TEST_MAX_QUESTIONS
            and not (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False))
            and not _is_premium(user)
        ):
            return Response(
                {
                    'code': 'upgrade_required',
                    'feature': LOCKED_TEST_FEATURE,
                    'message': (
                        'This mock test is part of the Premium library. '
                        'Subscribe to unlock all 100+ tests from just ₹129/month.'
                    ),
                },
                status=402,
            )
        # ... and only if every question is one whose answer they may see:
        # scoring any other question (right / wrong, retake after retake)
        # gives its answer away. This also locks older generated tests drawn
        # from the whole bank, and in-flight attempts of them (entitlement.py).
        full_access = has_full_access(user)
        if has_locked_questions(user, test, full_access=full_access):
            return locked_test_response()

        attempt = _active_attempt(user, test)
        created = False
        if attempt is None:
            try:
                # Savepoint: select_for_update() on a row that does not exist
                # yet locks nothing, so a concurrent start can win the insert.
                with transaction.atomic():
                    attempt = TestAttempt.objects.create(user=user, test=test)
                created = True
            except IntegrityError:
                attempt = _active_attempt(user, test)
                if attempt is None:
                    raise
        if created and getattr(test, '_user_attempt_count', None) is not None:
            test._user_attempt_count += 1

        questions = _questions_for_attempt(test, attempt)
        last_completed_id = (
            TestAttempt.objects.filter(user=user, test=test, is_completed=True)
            .order_by('-completed_at', '-pk')
            .values_list('id', flat=True)
            .first()
        )
        now = timezone.now()
        limit_seconds = _time_limit_seconds(test)
        elapsed = max(0, int((now - attempt.started_at).total_seconds()))

        return Response({
            'attempt_id': attempt.id,
            'test': TestSerializer(test, context={'request': request}).data,
            # No answer media for anyone during the test; /review/ has them.
            'questions': _without_exam_hidden_fields(
                QuestionListSerializer(
                    questions, many=True,
                    context={'request': request, 'viewer_full_access': full_access},
                ).data
            ),
            'started_at': attempt.started_at,
            'resumed': not created,
            'server_time': now,
            'time_limit_seconds': limit_seconds,
            'remaining_seconds': max(0, limit_seconds - elapsed),
            'last_completed_attempt_id': last_completed_id,
        })

    @action(detail=True, methods=['post'], url_path='submit')
    def submit_attempt(self, request, pk=None):
        """Score a test attempt.

        * The attempt is looked up by (id, user, test) rather than through
          get_object(): unpublishing a test must not 404 an attempt a student
          started legitimately (start is where visibility and the paywall
          are checked).
        * A repeated submit of a completed attempt returns 400 with
          code='already_submitted' and the stored result, so a client whose
          first response was lost can still show the results.
        * Scoring, the attempt row and the dashboard analytics (F()
          increments) commit in one transaction; analytics run in a
          savepoint so a failure there can never block or lose the attempt.
        * The recorded duration is capped at the time limit: the player
          auto-submits at 0:00 and a resumed attempt keeps its original
          clock, so a late submit is accepted, but an attempt abandoned and
          finished days later no longer books days of study time.
        * A submit later than the time limit + LATE_SUBMIT_GRACE_SECONDS is
          still scored (that keeps the expired-resume auto-submit working)
          but stored with is_late=True: it earns no XP and stays off the
          leaderboard, so it is never recorded as an on-time attempt.
        * An empty submission (nothing answered) completes the attempt but
          earns no XP, streak, tests_completed or study time. XP rules: see
          _xp_for_submission.
        * A student without full access is never scored on a question whose
          answer they may not see (entitlement.py): such a test is a 402
          upgrade_required and the attempt stays open (e.g. one started
          before that rule, or while the student was premium).
        """
        if not isinstance(request.data, dict):
            return Response({'error': 'Invalid attempt'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            attempt = TestAttempt.objects.select_related('test').get(
                id=request.data.get('attempt_id'), user=request.user, test_id=pk,
            )
        except (TestAttempt.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'Invalid attempt'}, status=status.HTTP_400_BAD_REQUEST)
        test = attempt.test

        if attempt.is_completed:
            return _already_submitted(attempt, request)
        if has_locked_questions(request.user, test):
            return locked_test_response('submit')

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        def _opt_int(value, lo, hi):
            try:
                return max(lo, min(hi, int(value)))
            except (TypeError, ValueError):
                return None

        # The client-supplied answer list is untrusted: only score questions
        # that belong to this test, each at most once. Foreign question ids,
        # duplicates (which used to 500 on the unique constraint) and
        # omitted wrong answers can no longer inflate score / accuracy / XP.
        test_question_ids = set(test.questions.values_list('id', flat=True))
        clean_answers = {}
        for ans_data in serializer.validated_data['answers']:
            try:
                qid = int(ans_data.get('question_id'))
            except (TypeError, ValueError):
                continue
            if qid not in test_question_ids or qid in clean_answers:
                continue
            raw_selected = ans_data.get('selected_answer')
            selected = raw_selected.strip().upper()[:1] if isinstance(raw_selected, str) else ''
            clean_answers[qid] = {
                'selected': selected,
                'time_taken': _opt_int(ans_data.get('time_taken_seconds'), 0, 24 * 3600),
                'confidence': _opt_int(ans_data.get('confidence_level'), 1, 5),
            }

        questions_map = Question.objects.in_bulk(list(clean_answers))

        xp_earned = 0
        with transaction.atomic():
            # Row lock: two concurrent submits (double click / timer firing
            # during a manual submit) must not both score the attempt.
            attempt = TestAttempt.objects.select_for_update().get(pk=attempt.pk)
            attempt.test = test
            if attempt.is_completed:
                return _already_submitted(attempt, request)

            correct = 0
            incorrect = 0
            responses_to_create = []
            wrong_answers = []
            for qid, ans in clean_answers.items():
                question = questions_map.get(qid)
                if not question:
                    continue
                selected = ans['selected']
                is_correct = None
                if selected:
                    is_correct = selected == (question.correct_answer or '').strip().upper()[:1]
                    if is_correct:
                        correct += 1
                    else:
                        incorrect += 1
                ans['is_correct'] = is_correct
                if is_correct is False:
                    wrong_answers.append((question, selected))
                responses_to_create.append(QuestionResponse(
                    attempt=attempt,
                    question=question,
                    selected_answer=selected or None,
                    is_correct=is_correct,
                    time_taken_seconds=ans['time_taken'],
                    confidence_level=ans['confidence'],
                ))

            if responses_to_create:
                QuestionResponse.objects.bulk_create(responses_to_create, ignore_conflicts=True)

            # Calculate score against the full paper, not just the answers
            # the client chose to send.
            total_questions = len(test_question_ids)
            unanswered = max(0, total_questions - correct - incorrect)
            score = correct - (incorrect * test.negative_mark_value if test.negative_marking else 0)
            total_marks = total_questions

            now = timezone.now()
            elapsed = max(0.0, (now - attempt.started_at).total_seconds())
            limit_seconds = _time_limit_seconds(test)
            is_late = bool(limit_seconds) and elapsed > limit_seconds + LATE_SUBMIT_GRACE_SECONDS
            if limit_seconds:
                elapsed = min(elapsed, limit_seconds)

            attempt.score = score
            attempt.total_marks = total_marks
            attempt.correct_count = correct
            attempt.incorrect_count = incorrect
            attempt.unanswered_count = unanswered
            attempt.is_completed = True
            attempt.completed_at = now
            attempt.time_taken_seconds = int(elapsed)
            attempt.is_late = is_late
            attempt.save()

            answered = correct + incorrect
            if answered:
                try:
                    with transaction.atomic():
                        xp_earned = _record_submission_analytics(
                            request.user, attempt, clean_answers, questions_map, correct, answered,
                        )
                except Exception:  # analytics must never block or lose a submission
                    xp_earned = 0
                    logger.exception('Test submit analytics failed for attempt %s', attempt.pk)

        # Wrong answers feed the student's Mistake Notebook.
        from questions.mistakes import record_mistakes_bulk
        record_mistakes_bulk(request.user, wrong_answers)

        # Per-subject study time (Study Time page, dashboard weekly totals).
        # Skipped for an empty submission, like the other analytics. The
        # helper treats an elapsed time of 0 as "unknown, do not scale", so
        # pass the precise elapsed time (a sub-second instant submit must
        # still scale the client's per-question timings down to ~0).
        if answered:
            from questions.study_time import record_study_time, rows_for_test_submission
            record_study_time(request.user, rows_for_test_submission(
                [
                    (questions_map[qid].subject_id, ans['time_taken'], bool(ans['selected']))
                    for qid, ans in clean_answers.items() if qid in questions_map
                ],
                max(elapsed, 0.001),
                test.time_limit_minutes,
            ))

        from django.core.cache import cache
        from analytics.dashboard_v3 import invalidate_user_cache
        cache.delete(f'dashboard:{request.user.id}')
        cache.delete(f'dashboard_bundle:{request.user.id}')
        # ... and /api/analytics/dashboard_v3/ with its sub-endpoints, which
        # otherwise showed the submitted test only after their 60 s cache.
        invalidate_user_cache(request.user.id)

        # The player only reads the totals and fetches /review/ separately;
        # the old nested per-question detail payload cost >1,000 queries.
        return Response(_attempt_result(attempt, request, xp_earned=xp_earned))

    @action(detail=True, methods=['get'], url_path='review')
    def review(self, request, pk=None):
        """Detailed post-test review with per-question analysis.

        Looked up by (attempt id, user, test) like submit, so a completed
        attempt stays reviewable after its test is unpublished.

        The answer key and the explanations follow the question bank's
        entitlement (tests_engine.entitlement.answer_visibility): for a
        question the student may not see, the row carries
        ``answer_locked: true`` instead of correct_answer, explanation,
        mnemonic, concept_explanation, textbook_references and the textbook
        pointers (scholarship questions included); its concept_tags keep
        only markers such as "high_yield", and its stem and options are cut
        as on locked question-bank rows, at any answer / explanation label
        or correctness flag an import left in them (entitlement.lock_answer).
        Since /start/ and /submit/ refuse such tests to a student without
        full access (submit re-checks the questions, so one that left the
        free set after /start/ is refused too), a locked row only appears in
        an attempt scored earlier (before that rule, or while premium): its
        selected_answer and is_correct are what the student was already
        shown, so they stay.

        The answer media the exam payload leaves out come back here
        (_review_media): ``stem_images`` for every row, and on a row whose
        answer the student may see the ``explanation_images`` (signed URLs)
        and the finished explanation video (``video_url`` ...); a locked row
        has ``explanation_images: []`` and no video.
        """
        attempt_id = request.query_params.get('attempt_id')

        try:
            attempt = TestAttempt.objects.get(
                id=attempt_id, user=request.user, test_id=pk, is_completed=True
            )
        except (TestAttempt.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'No completed attempt found'}, status=400)

        responses = list(
            QuestionResponse.objects.filter(attempt=attempt)
            .select_related('question', 'question__subject', 'question__topic')
            .prefetch_related('question__images')
        )
        visible = answer_visibility(request.user, [resp.question_id for resp in responses])
        role_memo = {}

        questions_review = []
        subject_breakdown = {}

        for resp in responses:
            q = resp.question
            subj = public_subject_name(q.subject.name) if q.subject else 'Unknown'

            if subj not in subject_breakdown:
                subject_breakdown[subj] = {'correct': 0, 'incorrect': 0, 'unanswered': 0}

            if resp.is_correct:
                subject_breakdown[subj]['correct'] += 1
            elif resp.is_correct is False:
                subject_breakdown[subj]['incorrect'] += 1
            else:
                subject_breakdown[subj]['unanswered'] += 1

            row = {
                'question_id': q.id,
                'question_text': q.question_text,
                'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
                'correct_answer': q.correct_answer,
                'selected_answer': resp.selected_answer,
                'is_correct': resp.is_correct,
                # Text written for another key than the current one (a corrected key) is not shown.
                'explanation': '' if explanation_for_another_key(q) else (q.explanation or q.ai_explanation or ''),
                'explanation_notice': STALE_EXPLANATION_NOTICE if explanation_for_another_key(q) else '',
                'mnemonic': q.mnemonic or '',
                'subject': subj,
                'topic': q.topic.name if q.topic else '',
                'difficulty': q.difficulty,
                'book_reference': q.book_name,
                'chapter': q.chapter or '',
                'page_number': q.page_number or '',
                'year': q.year,
                'paper': q.paper,
                'times_asked': q.times_asked,
                'concept_explanation': q.concept_explanation or '',
                'textbook_references': q.textbook_references or [],
                'time_taken': resp.time_taken_seconds,
                'confidence': resp.confidence_level,
                'concept_tags': q.concept_tags or [],
                'answer_locked': False,
            }
            answer_visible = visible.get(q.id, False)
            row.update(_review_media(q, visible=answer_visible, request=request, memo=role_memo))
            if not answer_visible:
                lock_answer(row)
            questions_review.append(row)

        return Response({
            'attempt_id': attempt.id,
            'score': attempt.score,
            'total_marks': attempt.total_marks,
            'accuracy': attempt.accuracy,
            'total_time': attempt.time_taken_seconds,
            'correct': attempt.correct_count,
            'incorrect': attempt.incorrect_count,
            'unanswered': attempt.unanswered_count,
            'is_late': attempt.is_late,
            'subject_breakdown': subject_breakdown,
            'questions': questions_review,
        })

    @action(detail=False, methods=['post'], url_path='generate-adaptive')
    def generate_adaptive(self, request):
        """Generate an AI adaptive test that focuses on weak areas.

        Scoped to one exam (exam_type, default 'cms') and private to its
        creator, like the other generators.

        Weak areas are the ADAPTIVE_WEAK_AREAS lowest-accuracy
        UserTopicPerformance rows with at least ADAPTIVE_MIN_ATTEMPTS
        answers (ordering by the raw correct count used to pick the least
        practised topics, not the weakest). A weak topic row targets that
        topic; a weak subject-level row (topic=None) targets the subject.

        A student without full access gets free questions only (as in
        /generate/); an exam with questions but no free ones is a 402, an
        exam with no questions at all a 400 (it used to create an empty
        test).
        """
        try:
            num_questions = int(request.data.get('num_questions', 30))
        except (TypeError, ValueError, AttributeError):
            return Response({'error': 'num_questions must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        num_questions = max(1, min(num_questions, 200))
        try:
            exam_type = _exam_type_param(request.data.get('exam_type'))
        except _BadRequest as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        exam_scope = Q(is_active=True) & exam_scope_q(exam_type)
        full_access = has_full_access(request.user)
        exam_q = exam_scope if full_access else exam_scope & free_question_q()

        # Weakest areas of the user's answer history, by accuracy.
        from analytics.models import UserTopicPerformance
        weak_perfs = list(
            UserTopicPerformance.objects
            .filter(user=request.user, total_attempts__gte=ADAPTIVE_MIN_ATTEMPTS)
            .annotate(accuracy_ratio=Cast('correct_answers', FloatField()) / Cast('total_attempts', FloatField()))
            .order_by('accuracy_ratio', '-total_attempts', 'pk')[:ADAPTIVE_WEAK_AREAS]
        )

        q_filter = exam_q
        weak_topic_ids = [p.topic_id for p in weak_perfs if p.topic_id]
        weak_subject_ids = [p.subject_id for p in weak_perfs if not p.topic_id]
        if weak_topic_ids or weak_subject_ids:
            q_filter &= (Q(topic_id__in=weak_topic_ids) | Q(subject_id__in=weak_subject_ids))

        questions = list(Question.objects.filter(q_filter).values_list('id', flat=True))
        if len(questions) < num_questions:
            extra = list(
                Question.objects.filter(exam_q)
                .exclude(id__in=questions)
                .values_list('id', flat=True)
            )
            questions.extend(extra[:num_questions - len(questions)])

        if len(questions) > num_questions:
            questions = random.sample(questions, num_questions)
        if not questions:
            if not full_access and Question.objects.filter(exam_scope).exists():
                return _no_free_questions_response()
            return Response({'error': 'No active questions found for this exam.'},
                            status=status.HTTP_400_BAD_REQUEST)
        negative_marking, negative_mark_value = EXAM_MARKING.get(exam_type, EXAM_MARKING['cms'])

        test = Test.objects.create(
            title=f"AI Adaptive Test — {len(questions)} Questions",
            test_type='adaptive',
            exam_type=exam_type,
            num_questions=len(questions),
            time_limit_minutes=int(len(questions) * 1.5),
            negative_marking=negative_marking,
            negative_mark_value=negative_mark_value,
            is_published=False,
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='pyq-simulation')
    def pyq_simulation(self, request):
        """Generate a previous-year paper simulation for one exam and year.

        ``exam_type`` (default 'cms') scopes the questions: the year filter
        alone used to mix UPSC CMS, NEET PG and INI-CET questions under a
        "UPSC CMS {year}" title. The time limit follows the exam (CMS: 120
        minutes per paper, so a combined two-paper set gets 240) and so does
        the negative marking. The test is private to its creator.

        A simulation is the real paper for every student, so for a student
        without full access it stays premium: /start/ answers 402 (as for
        any test with questions whose answers they may not see), and it never
        contains a scholarship question.
        """
        if not isinstance(request.data, dict):
            return Response({'error': 'Year is required'}, status=400)
        try:
            exam_type = _exam_type_param(request.data.get('exam_type'))
            year = _optional_int(request.data.get('year'), 'year', lo=1900, hi=2100,
                                 message='year must be a valid year')
            paper = _optional_int(request.data.get('paper'), 'paper', lo=1, hi=2,
                                  message='paper must be 1 or 2')
        except _BadRequest as exc:
            return Response({'error': str(exc)}, status=400)
        if year is None:
            return Response({'error': 'Year is required'}, status=400)

        q_filter = Q(is_active=True, year=year) & exam_scope_q(exam_type)
        if paper:
            q_filter &= Q(paper=paper)
        if not has_full_access(request.user):
            q_filter &= ~Q(is_scholarship_eligible=True)

        rows = list(Question.objects.filter(q_filter).values_list('id', 'paper'))
        exam_label = EXAM_LABELS.get(exam_type, exam_type)

        if not rows:
            return Response({'error': f'No {exam_label} questions found for {year}'}, status=404)

        questions = [qid for qid, _ in rows]
        if exam_type == 'cms':
            # Papers present (a real year has ~240 questions over 2 papers);
            # rows without a paper number are estimated from the count.
            known_papers = {p for _, p in rows if p in (1, 2)}
            papers = 1 if paper else (len(known_papers) or max(1, round(len(rows) / FULL_PAPER_QUESTIONS)))
            time_limit = _cms_paper_minutes(len(rows), papers)
        else:
            # NEET PG pace: 200 questions in 210 minutes.
            time_limit = max(10, math.ceil(len(rows) * 1.05))
        negative_marking, negative_mark_value = EXAM_MARKING.get(exam_type, EXAM_MARKING['cms'])

        paper_label = f"Paper {paper}" if paper else "Combined"
        short_label = 'CMS' if exam_type == 'cms' else exam_label
        test = Test.objects.create(
            title=f"{exam_label} {year} — {paper_label} Simulation",
            test_type='pyq_year',
            exam_type=exam_type,
            description=f"Full {short_label} {year} {paper_label} examination simulation with actual PYQ questions.",
            num_questions=len(questions),
            time_limit_minutes=time_limit,
            negative_marking=negative_marking,
            negative_mark_value=negative_mark_value,
            is_published=False,
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


class TestAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve user's test attempts."""
    serializer_class = TestAttemptSerializer

    def get_queryset(self):
        queryset = TestAttempt.objects.filter(user=self.request.user).select_related('test')
        if self.action == 'retrieve':
            # TestAttemptDetailSerializer reads each response's question,
            # subject and topic: load them in bulk.
            queryset = queryset.prefetch_related(Prefetch(
                'responses',
                queryset=QuestionResponse.objects.select_related(
                    'question__subject', 'question__topic',
                ).order_by('pk'),
            ))
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestAttemptDetailSerializer
        return TestAttemptSerializer

    def retrieve(self, request, *args, **kwargs):
        """One attempt with its responses; the answer key and explanations
        follow the question bank's entitlement, as in /tests/<id>/review/."""
        attempt = self.get_object()
        context = self.get_serializer_context()
        context['answer_visibility'] = answer_visibility(
            request.user, [resp.question_id for resp in attempt.responses.all()],
        )
        return Response(TestAttemptDetailSerializer(attempt, context=context).data)
