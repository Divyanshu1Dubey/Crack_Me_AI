import logging
import csv
import os
import re
from io import StringIO

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, F, Max, Q, Subquery, Sum, Value, OuterRef, IntegerField, Case, When, Exists
from django.db.models.functions import Greatest
from accounts.permissions import IsControlTowerAdmin
from accounts.utils import is_premium as _is_premium
from crack_cms.filters import BoundedSearchFilter
from accounts.models_freemium import FreeShowcaseQuestion
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, DiscussionVote, Note, Flashcard, QuestionImportJob, QuestionExtractionItem, AdminAIPromptVersion, QuestionAIOperationLog, QuestionRevisionSnapshot, Announcement, ExamTrack, QuestionImage, QuestionSource, RecallSource, DuplicateCluster, DuplicateMember, RemovedQuestion, TopicNote, StudyTimeBreakdown, UserQuest, QuestStreak, compute_stem_hash
from .serializers import (
    SubjectSerializer, TopicSerializer, AnnouncementSerializer, ExamTrackSerializer,
    QuestionListSerializer, QuestionAdminListSerializer, QuestionDetailSerializer,
    QuestionUploadSerializer, BookmarkSerializer,
    QuestionFeedbackSerializer, DiscussionSerializer,
    NoteSerializer, FlashcardSerializer, QuestionImportJobSerializer, QuestionExtractionItemSerializer,
    AdminAIPromptVersionSerializer, QuestionAIOperationLogSerializer, QuestionRevisionSnapshotSerializer,
    TopicNoteSerializer, StudyTimeBreakdownSerializer,
    UserQuestSerializer, UserQuestAdminSerializer, QuestStreakSerializer,
    effective_explanation_for, _clean_text, locked_concept_tags, resolve_runtime_image_role,
    public_subject_name,
)
from .image_access import TOKEN_PARAM as IMAGE_TOKEN_PARAM, image_token_is_valid
from .answer_leak import redact_public_text, redact_stem_text, row_has_answer_label
from .locked_text_search import terms_visible_in_stem, without_hidden_matches
from .recall_serializers import (
    # Used directly here:
    RecallSourceSerializer,
    DuplicateClusterSerializer,
    # Imported indirectly via `questions.recall_search`:
    # - QuestionImageSerializer (recall_question_images)
    # - QuestionSourceSerializer (recall_question_sources)
)
from . import recall_search as _recall_search
from . import recall_images as _recall_images  # Phase 3 image facets
from . import practice_modes as _practice_modes  # Phase 3 practice queues
from . import ai_per_question as _ai_per_question  # Phase 3 AI endpoints
from . import practice_experience as _practice_experience  # Phase 3 flag/confidence/time
from .import_protection import pre_check_create as _pre_check_remove


logger = logging.getLogger(__name__)


def _truthy(value) -> bool:
    """Request flag parsing: ``bool('false')`` is True, so strings are read
    as words (1 / true / yes / on)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _stored_value_differs(stored, value) -> bool:
    """True when writing ``value`` changes the stored field content
    (text compared without surrounding whitespace)."""
    if stored == value:
        return False
    if isinstance(stored, (list, dict)) or isinstance(value, (list, dict)):
        return True
    return str(stored or '').strip() != str(value or '').strip()


def _question_list_cache_version(user_id) -> int:
    try:
        return int(cache.get(f'qlist_ver:{user_id}') or 0)
    except (TypeError, ValueError):
        return 0


def _bump_question_list_cache_version(user_id) -> None:
    """Invalidate every cached question-list page for one user."""
    key = f'qlist_ver:{user_id}'
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, None)
    except Exception:  # pragma: no cover - cache backend hiccup
        logger.debug('qlist cache version bump failed for %s', user_id)


# NOTE (QB-15): a request-time ``_ensure_question_bank_loaded`` used to run
# ``seed_data`` + ``loaddata cms_fixture.json`` from the public ``years`` /
# ``stats`` GETs whenever fewer than 1800 active questions existed. That
# silently overwrote admin edits and revived archived / removed questions
# (loaddata ignores RemovedQuestion tombstones). Seeding is a deploy step
# (build.sh), never a side effect of a web request.


# ``exam_source`` labels of one exam's bank. Recall imports add a suffix
# ("NEET PG (recall)", "INI-CET (recall)"), and older INI-CET imports stored
# the unhyphenated "INICET".
INI_CET_SOURCE_PREFIXES = ('INI-CET', 'INICET')
_EXAM_SOURCE_FILTER_PREFIXES = (
    ('NEET PG', ('NEET PG',)),
    ('UPSC CMS', ('UPSC CMS',)),
    ('INI-CET', INI_CET_SOURCE_PREFIXES),
    ('INICET', INI_CET_SOURCE_PREFIXES),
    ('USMLE', ('USMLE',)),
    ('FMGE', ('FMGE',)),
)


def exam_source_filter_q(exam_source: str) -> Q:
    """``?exam_source=`` of the question list and years endpoints: the exact
    label, or -- for a known exam -- every label of that exam's bank, so
    ``NEET PG`` also matches ``NEET PG (recall)`` and ``INI-CET`` also
    matches ``INI-CET (recall)`` and ``INICET``."""
    exam_q = Q(exam_source=exam_source)
    for label, prefixes in _EXAM_SOURCE_FILTER_PREFIXES:
        if exam_source.startswith(label):
            for prefix in prefixes:
                exam_q |= Q(exam_source__startswith=prefix)
            break
    return exam_q


# ── Question-bank entitlement (freemium) ─────────────────────────────────
#
# ONE rule for every endpoint that reveals a question's answer, explanation
# or AI-generated study text:
#   * admins / staff / superusers   -> always
#   * premium subscribers           -> always (accounts.utils.is_premium)
#   * everyone else (free accounts and anonymous visitors)
#                                   -> only admin-curated showcase questions
#                                      (accounts.FreeShowcaseQuestion)
# Answer-submission endpoints answer a non-entitled caller with 402
# ``{"code": "upgrade_required"}``; read endpoints redact the answer parts.

UPGRADE_REQUIRED_FEATURE = 'PYQ answers'


def _is_staff_user(user) -> bool:
    return bool(
        user is not None
        and getattr(user, 'is_authenticated', False)
        and (
            getattr(user, 'is_admin', False)
            or getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)
        )
    )


def free_showcase_rows():
    """FreeShowcaseQuestion rows that really are free content.

    Scholarship-challenge questions (``is_scholarship_eligible``) are never
    free, even when an admin also put them in the showcase: the challenge
    (accounts ScholarshipStartView) serves five of them and checks the
    answers, so revealing their keys to a free user would let anyone pass it.
    """
    return FreeShowcaseQuestion.objects.filter(question__is_scholarship_eligible=False)


def user_can_view_answer(user, question, *, premium=None) -> bool:
    """True when ``user`` may see the answer / explanation of ``question``.

    ``question`` may be a Question instance or a primary key. ``premium``
    lets callers pass an already-computed ``is_premium(user)`` result.
    Free / anonymous callers: showcase questions only, never a
    scholarship-challenge question (see ``free_showcase_rows``).
    """
    if _is_staff_user(user):
        return True
    if user is not None and getattr(user, 'is_authenticated', False):
        if premium is None:
            premium = _is_premium(user)
        if premium:
            return True
    question_id = getattr(question, 'pk', question)
    if question_id in (None, ''):
        return False
    if getattr(question, 'is_scholarship_eligible', False) is True:
        return False
    return free_showcase_rows().filter(question_id=question_id).exists()


def _upgrade_required_response(feature: str = UPGRADE_REQUIRED_FEATURE):
    """Paywall envelope understood by the frontend api.ts interceptor."""
    return Response(
        {
            'code': 'upgrade_required',
            'feature': feature,
            'message': (
                'This question is part of the premium question bank. '
                'Subscribe to see answers and explanations.'
            ),
        },
        status=status.HTTP_402_PAYMENT_REQUIRED,
    )


# Detail-payload fields that reveal the answer or the explanation. Redacted
# for callers who are not entitled to the question (see user_can_view_answer).
_ANSWER_REVEALING_DETAIL_FIELDS = (
    'correct_answer', 'explanation', 'concept_explanation', 'mnemonic',
    'learning_technique', 'shortcut_tip', 'concept_keywords',
    'why_correct', 'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d',
    'ai_explanation', 'ai_answer', 'ai_mnemonic', 'ai_references',
    'effective_answer', 'effective_explanation', 'effective_mnemonic',
    'effective_references', 'verified_note',
    # Part of the explanation payload (an admin lock / override decides the
    # explanation); the practice UI treats anything but ``true`` as false.
    'explanation_overridden',
    'video_url', 'video_status', 'video_thumbnail', 'video_duration',
    'video_version', 'video_error', 'video_generated_at', 'video_subtitles_url',
    # "Screenshot of textbook page where answer is discussed" (model help).
    'page_screenshot',
    # Textbook reference: ``reference_text`` is "relevant textbook content
    # that directly supports the answer" (admin AI generation fills it),
    # ``textbook_references`` holds excerpts, and a chapter title can name
    # the diagnosis.
    'reference_text', 'textbook_references', 'book_name', 'chapter', 'page_number',
    # The caller's own verdict on a locked question identifies its answer.
    'user_is_correct',
)


def _redact_question_detail(data: dict) -> dict:
    """Strip answer / explanation / AI / video content from a detail payload."""
    data = dict(data)
    for field in _ANSWER_REVEALING_DETAIL_FIELDS:
        if field in data:
            data[field] = None
    if 'concept_tags' in data:
        data['concept_tags'] = locked_concept_tags(data.get('concept_tags'))
    # Explanation figures belong to the explanation, not to the stem.
    for key in ('images', 'stem_images'):
        if isinstance(data.get(key), list):
            data[key] = [img for img in data[key] if (img or {}).get('role') != 'explanation']
    data['answer_locked'] = True
    return data


def _invalidate_user_question_caches(user_id) -> None:
    """After an answer: refresh the dashboard (also /api/analytics/dashboard_v3/
    and its sub-endpoints, which otherwise lagged by up to their 60 s cache)
    and the per-user list cache (``attempted`` / ``incorrect`` filters,
    ``user_selected_answer``)."""
    cache.delete(f'dashboard:{user_id}')
    cache.delete(f'dashboard_bundle:{user_id}')
    try:
        from analytics.dashboard_v3 import invalidate_user_cache
    except ImportError:  # pragma: no cover - analytics app not installed
        invalidate_user_cache = None
    if invalidate_user_cache is not None:
        invalidate_user_cache(user_id)
    _bump_question_list_cache_version(user_id)


def _answer_fallback_explanation(question) -> str:
    """Honest stand-in when a question has no explanation yet, so the reveal
    never renders an empty explanation panel."""
    letter = (question.correct_answer or '').strip().upper()[:1]
    option_text = getattr(question, f'option_{letter.lower()}', '') if letter in 'ABCDE' and letter else ''
    option_text = _clean_text(option_text or '').strip()
    if letter and option_text:
        answer = f'The correct answer is {letter}: {option_text}.'
    elif letter:
        answer = f'The correct answer is {letter}.'
    else:
        answer = ''
    return ' '.join(part for part in (
        answer, 'A detailed explanation for this question has not been added yet.',
    ) if part)


def _question_explanation_payload(question) -> dict:
    """Answer-reveal fields of the answer-submission responses (contract C1),
    so the UI can show the explanation right after a pick without a second
    request:

    * ``explanation`` -- the curated text ('' when there is none), or the
      admin's explanation override when one is set (locked or not): the
      practice UI prefers a non-blank ``explanation``, so an admin
      correction of a curated explanation must arrive here as well;
    * ``effective_explanation`` -- what a student should read (admin
      override / parsed AI explanation / curated text), never blank: a
      short "correct answer is X" note when nothing has been written yet;
    * ``explanation_overridden`` -- True when an admin lock or a non-blank
      override decides the explanation (the detail serializer's flag of the
      same name), so the practice UI (practiceData.pickExplanation) shows
      ``effective_explanation`` ahead of the curated text;
    * ``mnemonic`` -- the effective mnemonic (admin override, usable AI
      mnemonic, curated), '' when there is none.

    Only called after ``user_can_view_answer`` allowed the caller.
    """
    from .ai_per_question import usable_ai_text

    override = (question.admin_explanation_override or '').strip()
    explanation = _clean_text(override or question.explanation or '')
    effective = _clean_text(usable_ai_text(effective_explanation_for(question)) or '')
    mnemonic = (
        usable_ai_text(question.admin_mnemonic_override)
        or usable_ai_text(question.ai_mnemonic)
        or usable_ai_text(question.mnemonic)
    )
    return {
        'explanation': explanation,
        'effective_explanation': (
            effective.strip() or explanation.strip() or _answer_fallback_explanation(question)
        ),
        'explanation_overridden': bool(question.lock_explanation or override),
        'mnemonic': _clean_text(mnemonic or ''),
    }


class ExamTrackViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve exam tracks."""
    queryset = ExamTrack.objects.all()
    serializer_class = ExamTrackSerializer
    permission_classes = [permissions.AllowAny]


class AnnouncementViewSet(viewsets.ModelViewSet):
    """ViewSet for Admin Notes / Announcements."""
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    # Cache the list response for 5 minutes — announcements rarely change
    # but are read on every dashboard load (240ms → <5ms). The queryset is
    # per user (``target_users``), so the cache key is per user (and per
    # query string, for pagination); writes bump a global version instead
    # of deleting one shared key (which served one user's list to all).
    LIST_CACHE_VERSION_KEY = 'announcements:list:ver'
    LIST_CACHE_TTL = 300  # 5 minutes

    # CustomUser.target_exam stores display labels ("UPSC CMS", "NEET PG",
    # ...) while Announcement.target_exam_track stores slugs ("cms", ...).
    TARGET_EXAM_TO_TRACK = {
        'upsc cms': 'cms', 'cms': 'cms',
        'neet pg': 'neet_pg', 'neet_pg': 'neet_pg', 'neet-pg': 'neet_pg',
        'usmle': 'usmle',
        'fmge': 'fmge',
    }

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAdminUser]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    @classmethod
    def _track_for_user(cls, user) -> str:
        raw = str(getattr(user, 'target_exam', '') or '').strip().lower()
        return cls.TARGET_EXAM_TO_TRACK.get(raw, raw)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Announcement.objects.all()

        now = timezone.now()
        user_track = self._track_for_user(user)

        return Announcement.objects.filter(
            # Not expired
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            # ``target_users`` overrides the exam track (model help text):
            # a user-targeted announcement keeps the default track 'all',
            # so OR-ing it in showed personal notices to every student.
            Q(target_users=user) |
            (
                Q(target_users__isnull=True)
                & (Q(target_exam_track='all') | Q(target_exam_track=user_track))
            )
        ).distinct().order_by('-created_at')

    def _list_cache_key(self, request) -> str:
        import hashlib
        try:
            version = int(cache.get(self.LIST_CACHE_VERSION_KEY) or 0)
        except (TypeError, ValueError):
            version = 0
        query = request.META.get('QUERY_STRING') or ''
        digest = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()  # cache key, not security
        return f'announcements:list:v{version}:u{request.user.pk}:{digest}'

    def _invalidate_list_cache(self):
        try:
            cache.incr(self.LIST_CACHE_VERSION_KEY)
        except ValueError:
            cache.set(self.LIST_CACHE_VERSION_KEY, 1, None)
        except Exception:  # pragma: no cover - cache backend hiccup
            logger.debug('announcement cache version bump failed')

    def list(self, request, *args, **kwargs):
        """Cached per-user list — bypass for staff (always fresh)."""
        if request.user.is_staff:
            return super().list(request, *args, **kwargs)

        cache_key = self._list_cache_key(request)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, self.LIST_CACHE_TTL)
        return response

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._invalidate_list_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._invalidate_list_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidate_list_cache()

class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve subjects.

    The loader's "Imported" fallback Subject row has historically been
    duplicated by exam_type (one row per exam_track the importer ran
    against). To keep the public Question Bank filter dropdown readable,
    the serializer (``SubjectSerializer.to_representation``) renames
    "Imported" → "Expert Curated" so the loader literal never leaks to
    the UI.

    The underlying Subject rows are NOT merged here — each one is still
    returned separately with its own ``question_count``. To physically
    collapse duplicate "Imported" Subject rows in the DB into a single
    canonical row (so the filter shows ONE "Expert Curated" entry
    instead of N identical ones), run the
    ``merge_loader_fallback_subjects`` management command.
    """
    # Read-only taxonomy (~40 rows): one unpaginated array (contract C7).
    # Clients read only page 1 of the 20-row default, so dropdowns lost
    # subjects. The explicit order replaces Meta.ordering, which Django
    # ignores on this GROUP BY (annotate) query.
    queryset = Subject.objects.annotate(question_count=Count('questions')).order_by('paper', 'name', 'id')
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['exam_type']
    pagination_class = None


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve topics, filterable by subject.

    Unpaginated like subjects (contract C7; ~2,000 rows unfiltered, a few
    dozen per ``?subject=``), in an explicit stable order.
    """
    queryset = (
        Topic.objects.annotate(question_count=Count('questions')).select_related('subject')
        .order_by('subject__name', 'name', 'id')
    )
    serializer_class = TopicSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['subject', 'parent', 'importance']
    pagination_class = None


def _cluster_memberships_prefetch(prefix: str = ''):
    """Prefetch DuplicateMember rows annotated with their cluster's size, so
    ``duplicate_cluster_id`` / ``duplicate_count`` cost no per-row query."""
    from django.db.models import Prefetch
    return Prefetch(
        f'{prefix}cluster_memberships',
        queryset=DuplicateMember.objects.annotate(cluster_size=Count('cluster__members')),
    )


def _question_list_related(queryset, prefix: str = ''):
    """select/prefetch everything QuestionListSerializer reads per row."""
    return queryset.select_related(
        f'{prefix}subject', f'{prefix}topic', f'{prefix}verified_by',
    ).prefetch_related(f'{prefix}images', _cluster_memberships_prefetch(prefix))


class IdTiebreakOrderingFilter(filters.OrderingFilter):
    """``?ordering=`` with a final ``id`` tiebreak.

    ``ordering=paper,display_number`` leaves rows that share a number (or
    have none) in an arbitrary database order, so page N and page N+1 could
    overlap or skip rows -- the admin editor's drag-renumber relies on pages
    being stable, contiguous slices. Requests that already order by id keep
    their own direction.
    """

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if ordering and not any(str(term).lstrip('-') in ('id', 'pk') for term in ordering):
            ordering = [*ordering, 'id']
        return ordering


class QuestionViewSet(viewsets.ModelViewSet):
    """Full CRUD for questions with filtering, search, and bookmark support."""
    queryset = Question.objects.select_related('subject', 'topic', 'verified_by').prefetch_related(
        'images', 'recall_sources', 'feedbacks', 'similar_questions', _cluster_memberships_prefetch(),
        'revision_snapshots',
    ).all()
    # BoundedSearchFilter: ?search= keeps at most 10 distinct terms (an
    # anonymous caller could send ~2,000, each one more ILIKE per row).
    filter_backends = [DjangoFilterBackend, BoundedSearchFilter, IdTiebreakOrderingFilter]
    # NOTE: exam_source is NOT in filterset_fields on purpose — Bug #6
    # (2026-07-25) discovered that DjangoFilterBackend's exact-match
    # behaviour rejects valid labels like 'NEET PG (recall)' when the
    # client passes 'NEET PG'. Prefix-match fallback is implemented in
    # get_queryset() instead.
    filterset_fields = [
        'year', 'subject', 'topic', 'difficulty', 'exam_type',
        'is_image_based', 'is_verified_by_admin', 'is_scholarship_eligible',
        'needs_review', 'is_controversial', 'display_number', 'is_active',
        'page_number',
    ]
    # ``display_number`` / ``paper``: the admin questions editor orders a
    # paper by ``?ordering=paper,display_number`` (OrderingFilter dropped
    # unknown fields, so rows came back -id). IdTiebreakOrderingFilter adds
    # the final ``id`` when the request does not order by it.
    ordering_fields = ['year', 'difficulty', 'created_at', 'paper', 'display_number', 'id']

    # Text search. ``explanation`` and ``concept_tags`` are searchable only
    # for callers who may read them: otherwise ``?search=<option text>``
    # worked as an oracle on a locked question's explanation or concept
    # tags (a tag such as "ventricular aneurysm" can be the answer).
    _SEARCH_FIELDS_PUBLIC = ['question_text']
    _SEARCH_FIELDS_FULL = ['question_text', 'explanation', 'concept_tags']

    @property
    def search_fields(self):
        request = getattr(self, 'request', None)
        user = getattr(request, 'user', None)
        if request is not None and (_is_staff_user(user) or self._user_is_premium()):
            return self._SEARCH_FIELDS_FULL
        return self._SEARCH_FIELDS_PUBLIC

    def filter_queryset(self, queryset):
        # Query-param filters / search / ordering describe lists. On a
        # detail route they only turned get_object() into a 200-vs-404
        # probe (e.g. /questions/<locked id>/?search=...).
        if getattr(self, 'detail', False):
            return queryset
        return self._without_hidden_search_matches(super().filter_queryset(queryset))

    def _without_hidden_search_matches(self, queryset):
        """``?search=`` for a caller without full access: drop the locked
        rows it matched only inside an answer label / flag the caller does
        not see (``?search="Schwannoma ✅"`` named the ticked option; see
        ``questions.locked_text_search``)."""
        request = getattr(self, 'request', None)
        if request is None or not (request.query_params.get(BoundedSearchFilter.search_param) or '').strip():
            return queryset
        if _is_staff_user(getattr(request, 'user', None)) or self._user_is_premium():
            return queryset
        terms = BoundedSearchFilter().get_search_terms(request)
        if not terms:
            return queryset
        return without_hidden_matches(queryset, terms_visible_in_stem(terms))

    def _guess_year_paper_from_filename(self, filename):
        year = None
        paper = 0
        digits = ''.join([ch if ch.isdigit() else ' ' for ch in filename]).split()
        for token in digits:
            if len(token) == 4:
                try:
                    value = int(token)
                    if 1900 <= value <= 2100:
                        year = value
                        break
                except ValueError:
                    continue
        lower_name = filename.lower()
        if 'paper1' in lower_name or 'paper_1' in lower_name or 'paper-1' in lower_name:
            paper = 1
        elif 'paper2' in lower_name or 'paper_2' in lower_name or 'paper-2' in lower_name:
            paper = 2
        return year, paper

    def _parse_related_ids(self, value):
        if isinstance(value, str):
            tokens = [part.strip() for part in value.split(',') if part.strip()]
            parsed = []
            for token in tokens:
                try:
                    parsed.append(int(token))
                except ValueError:
                    continue
            return parsed
        if isinstance(value, list):
            parsed = []
            for item in value:
                try:
                    parsed.append(int(item))
                except (TypeError, ValueError):
                    continue
            return parsed
        return []

    def _normalize_field_text(self, value):
        text = (value or '').replace('\r\n', '\n').replace('\r', '\n')
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        text = text.replace(' ,', ',').replace(' .', '.').replace(' ;', ';').replace(' :', ':')
        return text.strip()

    def _normalize_question_text(self, value):
        text = self._normalize_field_text(value)
        # Keep statement-code blocks readable by placing coded statements on separate lines.
        text = re.sub(r';\s*(?=((?:[IVXLCDM]{1,8}|\d{1,2})\.\s))', ';\n', text)

        markers = list(re.finditer(r'(?:[IVXLCDM]{1,8}|\d{1,2})\.\s', text))
        if len(markers) >= 2:
            first_marker_index = markers[0].start()
            if first_marker_index > 0 and text[first_marker_index - 1] != '\n':
                text = f"{text[:first_marker_index].rstrip()}\n{text[first_marker_index:]}"

        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        return text

    def _normalize_question_payload(self, validated_data):
        if 'question_text' in validated_data:
            validated_data['question_text'] = self._normalize_question_text(validated_data.get('question_text'))
        for option_field in ['option_a', 'option_b', 'option_c', 'option_d']:
            if option_field in validated_data:
                validated_data[option_field] = self._normalize_option(validated_data.get(option_field))
        if 'explanation' in validated_data:
            validated_data['explanation'] = self._normalize_field_text(validated_data.get('explanation'))

    def _normalize_option(self, value):
        text = self._normalize_field_text(value)
        for prefix in ['A)', 'B)', 'C)', 'D)', 'A.', 'B.', 'C.', 'D.', '(A)', '(B)', '(C)', '(D)']:
            if text.upper().startswith(prefix):
                return text[len(prefix):].strip()
        return text

    def _user_is_premium(self) -> bool:
        """`is_premium` for the requesting user, evaluated once per request
        (it costs a Subscription query and is consulted several times)."""
        if not hasattr(self, '_cached_user_is_premium'):
            user = getattr(self.request, 'user', None)
            self._cached_user_is_premium = bool(
                user is not None and getattr(user, 'is_authenticated', False) and _is_premium(user)
            )
        return self._cached_user_is_premium

    def _can_view_answer(self, question) -> bool:
        """Entitlement check shared by every answer-revealing detail action."""
        user = getattr(self.request, 'user', None)
        return user_can_view_answer(user, question, premium=self._user_is_premium())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = getattr(self.request, 'user', None)
        # Lets QuestionListSerializer decide per row whether answer-linked
        # media (explanation videos) may be shown, without a query per row.
        context['viewer_full_access'] = bool(_is_staff_user(user) or self._user_is_premium())
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        if not self._can_view_answer(instance):
            # Only anonymous visitors reach this (free accounts get 404 from
            # get_queryset): keep the stem public, hide the answer.
            data = _redact_question_detail(data)
        return Response(data)

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-id')
        user = getattr(self.request, 'user', None)
        is_admin = bool(user and getattr(user, 'is_authenticated', False) and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)))

        # Bug #6 (2026-07-25): exam_source filter silently returned 0 results
        # because Question.exam_source stores labels like "NEET PG (recall)"
        # while the API client passes "NEET PG". DjangoFilter's default
        # exact-match mode rejected everything. Match the prefix the same
        # way the stats endpoint already does (see _exam_source_q()).
        exam_source_param = self.request.query_params.get('exam_source')
        if exam_source_param:
            queryset = queryset.filter(exam_source_filter_q(exam_source_param))
        admin_actions = {
            'create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate',
            'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload',
            'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update',
            'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject',
            'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'generate_video', 'ai_prompt_versions',
            'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision',
            'link_related', 'set_concept_id', 'update_reference', 'format_fix',
            'generate_explanation',
        }
        if self.action in admin_actions:
            return queryset
        if not is_admin:
            queryset = queryset.filter(is_active=True)

        # Freemium gate (Task 6 + Phase 4 audit): free users see only the
        # admin-curated showcase questions (10/year by default). The gate
        # applies to BOTH the list endpoint AND the detail/retrieve
        # endpoint — without the retrieve check, a free user can deep-link
        # to /api/questions/{id}/ for any question and bypass the gate.
        # Premium and admin users continue to see the full set. Anonymous
        # requests also get the full set — public SEO/showroom value is
        # intentional — but ``retrieve`` redacts the answer, explanation,
        # AI text and video for anything they are not entitled to (see
        # ``user_can_view_answer``); the list serializer never exposes them.
        #
        # UX update: we now return ALL active questions for free users on the
        # LIST endpoint (with is_showcase annotation), and rely on the
        # frontend to render a locked / blurred overlay on non-showcase
        # rows. The reasoning: a free user who only sees 10/yr thinks the
        # platform has almost no content — which kills conversion. Showing
        # the full catalog with locked badges makes the value proposition
        # obvious ("2,277 questions waiting for you") while keeping the
        # hard server-side gate on retrieve + answer-submit endpoints.
        # RETRIEVE remains gated — a free user cannot deep-link to a
        # non-showcase question via /api/questions/{id}/.
        if (
            self.action == 'retrieve'
            and user is not None
            and getattr(user, 'is_authenticated', False)
            and not _is_staff_user(user)
            and not self._user_is_premium()
        ):
            showcase_filter = free_showcase_rows().filter(
                question_id=OuterRef('pk'),
            )
            queryset = queryset.filter(Exists(showcase_filter))

        # Anonymous visitors are NOT filtered here (the public detail page
        # keeps working for SEO); ``retrieve`` redacts the answer /
        # explanation for them unless the question is a showcase question.
        # Every other answer-revealing detail action checks
        # ``self._can_view_answer(question)`` after ``get_object()``.

        if self.action == 'retrieve':
            queryset = queryset.select_related('subject', 'topic', 'verified_by')

        if self.action == 'list':
            queryset = queryset.select_related('subject', 'topic', 'verified_by')
            # Global accuracy (GROUP BY over every test response) is only
            # shown on the admin list and only needed to filter by it --
            # students used to pay for it on every list request.
            wants_accuracy = is_admin or any(
                self.request.query_params.get(p) not in (None, '')
                for p in ('accuracy_min', 'accuracy_max')
            )
            if wants_accuracy:
                queryset = queryset.annotate(
                    attempt_count=Count('questionresponse', distinct=True),
                    correct_count=Count('questionresponse', filter=Q(questionresponse__is_correct=True), distinct=True),
                ).annotate(
                    accuracy=(F('correct_count') * 100.0) / (F('attempt_count') + 0.0001),
                )
            # NOTE: DuplicateCluster annotations removed — they caused
            # 2 correlated subqueries per row (slow on 8k+ questions).
            # The admin duplicate page computes these on demand instead.
            # Freemium annotation: `is_showcase=True` when this row is in
            # accounts.FreeShowcaseQuestion. Used by the frontend to render
            # a "Premium" badge on non-showcase rows for free users.
            queryset = queryset.annotate(
                is_showcase=Exists(
                    free_showcase_rows().filter(question_id=OuterRef('pk'))
                ),
            )
            # UX update (2026-08-04): for free users, sprinkle showcase
            # questions across the bank so a free card appears every ~10
            # paid cards (matches the user's "3 free then paid up to 10"
            # rhythm). Strategy:
            #   paid rows    ->  sort by a shuffled id position: `(id * 7) % 13 + 13`
            #   showcase rows -> sort by a slot 0..12:               `(id * 11) % 13`
            # so a showcase row that hashes to slot 5 lands at slot 5 of
            # the global timeline, and the paid row whose id hashes to 5
            # gets pushed to slot 18 (5 + 13) — naturally alternating.
            # This works for both SQLite and Postgres.
            #
            # `extra(select=...)` is the simplest cross-DB way to expose a
            # computed column to order_by.
            if (
                user is not None
                and getattr(user, 'is_authenticated', False)
                and not is_admin
                and not self._user_is_premium()
            ):
                queryset = queryset.annotate(
                    shuffle_slot=Case(
                        When(is_showcase=True, then=F('id') % 23),
                        default=F('id') % 23 + 23,
                        output_field=IntegerField(),
                    ),
                ).order_by('shuffle_slot', '-id')
            if user and getattr(user, 'is_authenticated', False):
                from django.db.models import BooleanField
                from questions.models import QuestionAttempt
                user_is_correct = Subquery(
                    QuestionAttempt.objects.filter(question_id=OuterRef('pk'), user=user).values('is_correct')[:1]
                )
                if not (is_admin or _is_staff_user(user) or self._user_is_premium()):
                    # Right / wrong on a question outside the free showcase
                    # (e.g. answered while a plan was active) identifies its
                    # answer: hidden from the row and from ?incorrect=.
                    user_is_correct = Case(
                        When(is_showcase=True, then=user_is_correct),
                        default=Value(None),
                        output_field=BooleanField(),
                    )
                queryset = queryset.annotate(
                    is_bookmarked=Exists(
                        QuestionBookmark.objects.filter(question_id=OuterRef('pk'), user=user)
                    ),
                    user_selected_answer=Subquery(
                        QuestionAttempt.objects.filter(question_id=OuterRef('pk'), user=user).values('selected_answer')[:1]
                    ),
                    user_is_correct=user_is_correct,
                )

        question_id = self.request.query_params.get('question_id')
        if question_id not in [None, '']:
            try:
                queryset = queryset.filter(id=int(question_id))
            except (TypeError, ValueError):
                queryset = queryset.none()

        flagged = self.request.query_params.get('flagged')
        if flagged in ['true', '1', 'yes']:
            queryset = queryset.filter(feedbacks__is_resolved=False).distinct()
        if flagged in ['false', '0', 'no']:
            queryset = queryset.exclude(feedbacks__is_resolved=False).distinct()

        # The accuracy annotation only exists on the list queryset.
        accuracy_min = self.request.query_params.get('accuracy_min') if self.action == 'list' else None
        accuracy_max = self.request.query_params.get('accuracy_max') if self.action == 'list' else None
        try:
            if accuracy_min not in [None, '']:
                queryset = queryset.filter(accuracy__gte=float(accuracy_min))
        except (TypeError, ValueError):
            pass
        try:
            if accuracy_max not in [None, '']:
                queryset = queryset.filter(accuracy__lte=float(accuracy_max))
        except (TypeError, ValueError):
            pass

        # PHASE 3 — user-state filters (2026-07-25).
        # The annotations above already compute `is_bookmarked`,
        # `user_selected_answer`, and `user_is_correct` per-user. These
        # query params let the client filter on them without needing
        # a separate /me/questions/ endpoint. All require an
        # authenticated user; unauth requests get back an unfiltered
        # list rather than 403 so the page is still usable when the
        # auth cookie is missing (graceful degradation).
        if user and getattr(user, 'is_authenticated', False):
            attempted = self.request.query_params.get('attempted')
            if attempted in ('true', '1', 'yes'):
                queryset = queryset.filter(user_selected_answer__isnull=False)
            elif attempted in ('false', '0', 'no'):
                queryset = queryset.filter(user_selected_answer__isnull=True)

            incorrect = self.request.query_params.get('incorrect')
            if incorrect in ('true', '1', 'yes'):
                queryset = queryset.filter(user_is_correct=False)
            elif incorrect in ('false', '0', 'no'):
                queryset = queryset.filter(user_is_correct=True)

            bookmarked = self.request.query_params.get('bookmarked')
            if bookmarked in ('true', '1', 'yes'):
                queryset = queryset.filter(is_bookmarked=True)
            elif bookmarked in ('false', '0', 'no'):
                queryset = queryset.filter(is_bookmarked=False)

            # last_attempted_within=N (days). 0/empty means "any".
            last_within = self.request.query_params.get('last_attempted_within')
            if last_within not in (None, ''):
                try:
                    days = int(last_within)
                    if days > 0:
                        from datetime import timedelta
                        from django.utils import timezone
                        cutoff = timezone.now() - timedelta(days=days)
                        from questions.models import QuestionAttempt
                        # Re-use the same Exists pattern as the annotate
                        # above; this re-filters by recency on the attempt
                        # rather than on the question row.
                        recent_qs = QuestionAttempt.objects.filter(
                            question_id=OuterRef('pk'),
                            user=user,
                            attempted_at__gte=cutoff,
                        )
                        queryset = queryset.filter(Exists(recent_qs))
                except (TypeError, ValueError):
                    pass

        # has_explanation — quick check for the empty-state CTA
        # "no questions have explanations yet" without fetching the body.
        has_expl = self.request.query_params.get('has_explanation')
        if has_expl in ('true', '1', 'yes'):
            queryset = queryset.exclude(explanation='') | queryset.exclude(ai_explanation='')
        elif has_expl in ('false', '0', 'no'):
            queryset = queryset.filter(explanation='', ai_explanation='')

        # has_ai_enrichment — same shape, narrower (excludes
        # admin-edited explanations, only counts AI-generated ones).
        has_ai = self.request.query_params.get('has_ai_enrichment')
        if has_ai in ('true', '1', 'yes'):
            queryset = queryset.exclude(ai_explanation='')
        elif has_ai in ('false', '0', 'no'):
            queryset = queryset.filter(ai_explanation='')

        return queryset

    def list(self, request, *args, **kwargs):
        # Per-user list cache: 5 min TTL. Questions change rarely. The key
        # includes the user, their access tier, a per-user version (bumped
        # on bookmark / attempt so `is_bookmarked` and the user's answer
        # state are fresh) and the full filter set (names AND values --
        # hashing values alone made `?year=2024` collide with
        # `?subject=2024`). Admins are never served from / written to it.
        import hashlib
        user = request.user
        is_authenticated = getattr(user, 'is_authenticated', False)
        is_staff_user = is_authenticated and (
            getattr(user, 'is_admin', False) or getattr(user, 'is_staff', False)
            or getattr(user, 'is_superuser', False)
        )
        if is_staff_user:
            return super().list(request, *args, **kwargs)
        user_id = user.id if is_authenticated else 'anon'
        tier = 'premium' if (is_authenticated and self._user_is_premium()) else 'free'
        version = _question_list_cache_version(user_id) if is_authenticated else 0
        filter_parts = [f'{k}={request.query_params.get(k, "")}' for k in sorted(request.query_params.keys())]
        digest = hashlib.md5('&'.join(filter_parts).encode(), usedforsecurity=False).hexdigest()  # cache key
        cache_key = f'qlist:{user_id}:{tier}:v{version}:{digest}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 300)
        return response

    def get_serializer_class(self):
        if self.action == 'list':
            user = getattr(self.request, 'user', None)
            if user and getattr(user, 'is_authenticated', False) and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)):
                return QuestionAdminListSerializer
            return QuestionListSerializer
        if self.action == 'upload':
            return QuestionUploadSerializer
        return QuestionDetailSerializer

    def get_permissions(self):
        # SECURITY: this override used to ignore the `permission_classes=`
        # declared on @action decorators, so every action missing from the
        # lists below was AllowAny -- anonymous users could remove questions
        # from the bank, merge duplicates and rewrite correct answers
        # (resolve-dispute). Admin actions are listed explicitly; any other
        # action now honours its decorator; the remainder stays public.
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate', 'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload', 'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update', 'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject', 'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'generate_video', 'ai_prompt_versions', 'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision', 'link_related', 'set_concept_id', 'update_reference', 'format_fix', 'merge_duplicates', 'remove_from_bank', 'unremove_from_bank', 'resolve_dispute', 'generate_explanation', 'recall_sources', 'duplicate_clusters']:
            return [IsControlTowerAdmin()]
        if self.action in ['bookmark', 'my_bookmarks', 'attempt', 'submit_feedback']:
            return [permissions.IsAuthenticated()]
        handler = getattr(self, self.action, None) if self.action else None
        declared = getattr(handler, 'kwargs', {}).get('permission_classes') if handler is not None else None
        if declared:
            return [permission() for permission in declared]
        return [permissions.AllowAny()]

    # ── Phase 2: recall-aware endpoints (additive) ──────────────────────

    @action(detail=False, methods=['get'], url_path='recall_search',
            permission_classes=[permissions.AllowAny])
    def recall_search(self, request):
        return _recall_search.recall_search(self, request)

    @action(detail=True, methods=['get'], url_path='images',
            permission_classes=[permissions.AllowAny])
    def images(self, request, pk=None):
        return _recall_search.recall_question_images(self, request, pk=pk)

    @action(detail=True, methods=['get'], url_path='sources',
            permission_classes=[permissions.AllowAny])
    def sources(self, request, pk=None):
        return _recall_search.recall_question_sources(self, request, pk=pk)

    # Admin-only: RecallSource rows carry server filesystem paths
    # (``pdf_path``) and import-job ids; only app/admin/recall uses these.
    @action(detail=False, methods=['get'], url_path='recall_sources',
            permission_classes=[IsControlTowerAdmin])
    def recall_sources(self, request):
        """List RecallSource rows for the admin recall dashboard."""
        qs = RecallSource.objects.filter(is_active=True).order_by("-created_at")[:200]
        return Response(RecallSourceSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=False, methods=['get'], url_path='duplicate_clusters',
            permission_classes=[IsControlTowerAdmin])
    def duplicate_clusters(self, request):
        qs = (
            DuplicateCluster.objects.annotate(member_count_annotated=Count('members'))
            .order_by("-created_at")[:100]
        )
        return Response(DuplicateClusterSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=True, methods=['get'], url_path='duplicates',
            permission_classes=[permissions.IsAuthenticated])
    def list_duplicates(self, request, pk=None):
        """Return every Question row that shares a DuplicateCluster with pk.

        Falls back to live text-similarity matching when no cluster exists
        yet (e.g. for questions ingested after the last detection pass).
        """
        question = self.get_object()
        full_access = _is_staff_user(request.user) or self._user_is_premium()
        free_ids = None

        def _preview(q) -> str:
            # An answer label / correctness flag an import left in a stem is
            # cut (questions.answer_leak) for a member whose answer this
            # viewer may not read, as in the list and detail payloads.
            nonlocal free_ids
            text = q.question_text or ''
            if not full_access and row_has_answer_label({'question_text': text}):
                if free_ids is None:
                    free_ids = set(free_showcase_rows().values_list('question_id', flat=True))
                if q.id not in free_ids:
                    text = redact_stem_text(text)
            return text[:120]

        def _serialize(q, canonical_id_for_member: int) -> dict:
            return {
                'id': q.id,
                'is_canonical': q.id == canonical_id_for_member,
                'is_active': q.is_active,
                'is_dropped': q.is_dropped,
                'admin_edited': bool(getattr(q, 'admin_edited', False)),
                'subject_name': public_subject_name(q.subject.name) if q.subject_id else '',
                'topic_name': q.topic.name if q.topic_id else '',
                'year': q.year,
                'exam_source': q.exam_source or '',
                'question_text_preview': _preview(q),
            }

        membership = (
            DuplicateMember.objects.filter(question_id=question.id)
            .select_related('cluster')
            .first()
        )
        members_qs = []
        cluster_id = None
        canonical_id = question.id
        if membership:
            cluster_id = membership.cluster_id
            canonical_id = membership.cluster.canonical_question_id
            members_qs = (
                DuplicateMember.objects.filter(cluster_id=cluster_id)
                .select_related('question', 'question__subject', 'question__topic')
                .order_by('-similarity_score', 'question_id')
            )

        members = []
        if members_qs:
            for m in members_qs:
                members.append(_serialize(m.question, canonical_id))

            # Bug fix: ensure the cluster's canonical row is always present
            # in `members`, even if it has no DuplicateMember row. Without
            # this, the admin's "Soft-drop selected" click sends the
            # canonical id back as a duplicate_id and trips `merge_duplicates`
            # with 400 "canonical id cannot appear in duplicate_ids".
            if not any(m['id'] == canonical_id for m in members):
                canonical_q = (
                    Question.objects
                    .select_related('subject', 'topic')
                    .filter(pk=canonical_id)
                    .first()
                )
                if canonical_q is not None:
                    members.insert(0, _serialize(canonical_q, canonical_id))
        else:
            # Live fallback: find active rows with the same normalized text
            # + year + exam_source, even if no cluster exists.
            for q in self._text_duplicate_candidates(question):
                members.append(_serialize(q, question.id))
            canonical_id = question.id

        return Response({
            'question_id': question.id,
            'cluster_id': cluster_id,
            'canonical_id': canonical_id,
            'member_count': len(members),
            'members': members,
        })

    @staticmethod
    def _normalize_stem_for_match(text: str) -> str:
        s = (text or '').lower()
        s = re.sub(r'[^a-z0-9\s]+', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    def _text_duplicate_candidates(self, question):
        """Active rows with the same normalized stem + year + exam_source
        (the live fallback ``list_duplicates`` shows when no cluster exists).
        Includes ``question`` itself."""
        norm = self._normalize_stem_for_match(question.question_text)
        fallback = Question.objects.filter(
            is_active=True,
            year=question.year,
            exam_source=question.exam_source or '',
        ).select_related('subject', 'topic').only(
            'id', 'question_text', 'is_active', 'is_dropped', 'admin_edited',
            'subject', 'topic', 'year', 'exam_source',
            'subject__name', 'topic__name',
        )[:200]
        return [q for q in fallback if self._normalize_stem_for_match(q.question_text) == norm]

    @action(detail=True, methods=['post'], url_path='merge-duplicates',
            permission_classes=[IsControlTowerAdmin])
    def merge_duplicates(self, request, pk=None):
        """Soft-drop duplicates (``is_dropped=True, is_active=False``) and
        keep exactly one row of the cluster as its canonical.

        Body: { "duplicate_ids": [<int>, ...] }

        Keeper: the cluster's canonical row, unless it is itself listed in
        ``duplicate_ids`` -- then ``pk``. (The admin dialog pre-selects
        every member except the canonical, so opening it from a
        non-canonical member used to 400 by default.) The cluster's
        ``canonical_question`` is repointed at the keeper.

        Without an existing cluster, ``duplicate_ids`` must be rows that
        ``list_duplicates`` offered through its text-match fallback; the
        cluster is created atomically (a rejected request leaves nothing
        behind).

          - 400 if every row of the cluster would be dropped.
          - 400 if any duplicate_id is outside the cluster / text matches.
          - Dropped rows stay in the DB for audits. No RemovedQuestion
            tombstone is written: duplicates share the keeper's stem hash,
            so a stem tombstone would also suppress the keeper on re-import.
        """
        question = self.get_object()
        body = request.data or {}
        dup_ids = body.get('duplicate_ids') or []
        if not isinstance(dup_ids, list) or not dup_ids:
            return Response({'detail': 'duplicate_ids must be a non-empty list'}, status=400)
        try:
            dup_ids = sorted({int(x) for x in dup_ids})
        except (TypeError, ValueError):
            return Response({'detail': 'duplicate_ids must be integers'}, status=400)

        with transaction.atomic():
            membership = (
                DuplicateMember.objects.filter(question_id=question.id)
                .select_related('cluster')
                .order_by('-cluster_id')
                .first()
            )
            cluster = membership.cluster if membership else None
            if cluster is not None:
                valid_ids = set(
                    DuplicateMember.objects.filter(cluster_id=cluster.id)
                    .values_list('question_id', flat=True)
                )
                valid_ids.add(cluster.canonical_question_id)
                current_canonical = cluster.canonical_question_id
            else:
                valid_ids = {q.id for q in self._text_duplicate_candidates(question)}
                valid_ids.add(question.id)
                current_canonical = question.id

            bad = [d for d in dup_ids if d not in valid_ids]
            if bad:
                return Response(
                    {'detail': f'these ids are not in the same cluster: {bad}'},
                    status=400,
                )

            if current_canonical not in dup_ids:
                keeper_id = current_canonical
            elif question.id not in dup_ids:
                keeper_id = question.id
            else:
                return Response(
                    {'detail': 'at least one row (the canonical) must be kept; '
                               'remove it or this question from duplicate_ids'},
                    status=400,
                )

            if cluster is None:
                cluster = DuplicateCluster.objects.create(
                    canonical_question_id=keeper_id,
                    similarity_threshold='1.000',
                    detection_method='manual-merge',
                )
            elif cluster.canonical_question_id != keeper_id:
                cluster.canonical_question_id = keeper_id
                cluster.save(update_fields=['canonical_question'])
            for member_id in {keeper_id, question.id, *dup_ids}:
                DuplicateMember.objects.get_or_create(
                    cluster=cluster,
                    question_id=member_id,
                    defaults={'similarity_score': 1.0},
                )

            dropped = Question.objects.filter(id__in=dup_ids).exclude(id=keeper_id).update(
                is_dropped=True,
                is_active=False,
            )

        return Response({
            'canonical_id': keeper_id,
            'cluster_id': cluster.id,
            'dropped': dropped,
        })

    @action(detail=True, methods=['post'], url_path='remove-from-bank',
            permission_classes=[IsControlTowerAdmin])
    def remove_from_bank(self, request, pk=None):
        """Soft-delete a question and record its identity in `RemovedQuestion`
        so the next `import_neet_pg` / `load_exam_fixture` deploy won't
        re-create it.

        Body: { "reason": "<optional free text>" }

        The Question row stays in the DB (`is_active=False`,
        `is_dropped=True`, `admin_edited=True`) so user history
        (bookmarks, attempts, notes, flashcards, discussions) keeps a
        stable reference and no FK cascade fires (some Question FKs use
        `on_delete=PROTECT`, so a true hard-delete would fail). Use
        `unremove_from_bank` to undo a removal.
        """
        question = self.get_object()
        reason = (request.data or {}).get('reason', '') or ''
        removed, _created = self._remove_question_from_bank(question, request.user, reason=reason)
        return Response({
            'id': question.id,
            'is_active': False,
            'is_dropped': True,
            'removed_question_id': removed.id,
            'was_already_removed': not _created,
        })

    def _remove_question_from_bank(self, question, actor, reason=''):
        """Soft-delete + RemovedQuestion tombstone (shared by
        ``remove-from-bank`` and ``DELETE``). Returns (tombstone, created)."""
        reason = str(reason or '')
        stem_hash = compute_stem_hash(question.question_text or '')
        with transaction.atomic():
            removed, created = RemovedQuestion.objects.get_or_create(
                exam_source=question.exam_source or '',
                year=question.year,
                source_number=getattr(question, 'display_number', None),
                question_text_hash=stem_hash,
                defaults={
                    'original_question_id': question.id,
                    'reason': reason[:1000],
                    'removed_by': actor if getattr(actor, 'is_authenticated', False) else None,
                },
            )
            # Capture a pre-removal revision snapshot so the admin can
            # diff before/after. Idempotent w.r.t. flags because the row
            # is only soft-mutated once.
            self._capture_revision_snapshot(
                question, actor,
                reason=f'Before remove-from-bank (reason={reason!r})'[:200],
            )
            question.is_active = False
            question.is_dropped = True
            question.admin_edited = True
            question.save(update_fields=['is_active', 'is_dropped', 'admin_edited'])

        # Best-effort audit log via the existing helper.
        try:
            from accounts.views import create_admin_audit_log
            create_admin_audit_log(
                actor=actor,
                action='REMOVE_FROM_BANK',
                resource_type='Question',
                resource_id=str(question.id),
                detail=f'Removed Q{question.id} ({question.exam_source}, year={question.year})',
                metadata={'reason': reason, 'stem_hash': stem_hash[:16]},
            )
        except Exception as e:
            logger.error(f'Failed to log remove_from_bank: {e}')
        return removed, created

    @action(detail=True, methods=['post'], url_path='unremove-from-bank',
            permission_classes=[IsControlTowerAdmin])
    def unremove_from_bank(self, request, pk=None):
        """Restore a previously removed question by deleting its
        `RemovedQuestion` tombstone and un-soft-deleting the row.

        Body: {}

        Idempotent: if no `RemovedQuestion` matches, returns 200 with
        `was_already_removed=False` instead of 404.
        """
        question = self.get_object()
        deleted_count, _ = RemovedQuestion.objects.filter(
            original_question_id=question.id,
        ).delete()
        # Also clear any hash-based tombstones that match this row's stem,
        # so a future re-import of the same stem won't be blocked by an
        # earlier removal from a different deployment id.
        stem_hash = compute_stem_hash(question.question_text or '')
        if stem_hash:
            RemovedQuestion.objects.filter(
                question_text_hash=stem_hash,
            ).delete()

        question.is_active = True
        question.is_dropped = False
        question.admin_edited = False
        question.save(update_fields=['is_active', 'is_dropped', 'admin_edited'])

        try:
            from accounts.views import create_admin_audit_log
            create_admin_audit_log(
                actor=request.user,
                action='UNREMOVE_FROM_BANK',
                resource_type='Question',
                resource_id=str(question.id),
                detail=f'Restored Q{question.id} from removed-question tombstones ({deleted_count} deleted)',
                metadata={},
            )
        except Exception as e:
            logger.error(f'Failed to log unremove_from_bank: {e}')

        return Response({
            'id': question.id,
            'is_active': True,
            'is_dropped': False,
            'tombstones_deleted': deleted_count,
        })

    # ── Phase 3: image facets + practice queues + AI per question ───────

    @action(detail=False, methods=['get'], url_path='images/facets',
            permission_classes=[permissions.AllowAny])
    def images_facets(self, request):
        """`GET /api/questions/images/facets/` — aggregate image counts."""
        return Response(_recall_images.list_images_facets(self, request))

    @action(detail=False, methods=['get'], url_path='practice_modes',
            permission_classes=[permissions.AllowAny])
    def practice_modes(self, request):
        """`GET /api/questions/practice_modes/` — supported mode catalogue."""
        return Response({"modes": _practice_modes.list_modes()})

    @action(detail=False, methods=['get'], url_path='practice_queue',
            permission_classes=[permissions.IsAuthenticated])
    def practice_queue(self, request):
        """`GET /api/questions/practice_queue/?mode=weak_topics&year=2023...`

        Returns ordered question ids the client should request in
        sequence. Existing `list` action is unaffected.
        """
        mode = request.query_params.get("mode", "random")
        try:
            count = max(1, min(int(request.query_params.get("count", 30)), 100))
        except (TypeError, ValueError):
            count = 30
        try:
            seed = int(request.query_params.get("seed")) if request.query_params.get("seed") else None
        except (TypeError, ValueError):
            seed = None
        params = {"count": count, "seed": seed}
        for k in ("year", "subject_id", "topic_id"):
            v = request.query_params.get(k)
            if v:
                try:
                    params[k] = int(v)
                except (TypeError, ValueError):
                    return Response({"error": f"{k} must be an integer"}, status=status.HTTP_400_BAD_REQUEST)
        for k in ("difficulty", "is_image_based", "has_explanation", "has_ai_enrichment"):
            v = request.query_params.get(k)
            if v:
                params[k] = v

        try:
            ids = _practice_modes.build_queue(mode, request.user, params)
        except Exception:
            # Never 500 the practice page on a queue-builder bug; the
            # logged exception still reaches error monitoring.
            logger.exception("practice_queue failed (mode=%s, user=%s)", mode, request.user.pk)
            ids = []

        # Freemium filter: free (non-premium, non-admin) users only get
        # admin-curated showcase questions in their practice queue.
        # Premium users and admins see the full queue.
        user = request.user
        is_free_user = (
            user is not None
            and getattr(user, 'is_authenticated', False)
            and not _is_staff_user(user)
            and not _is_premium(user)
        )
        if is_free_user and ids:
            showcase_ids = set(
                free_showcase_rows().filter(
                    question_id__in=ids
                ).values_list('question_id', flat=True)
            )
            ids = [qid for qid in ids if qid in showcase_ids]
            if len(ids) == 0:
                # Graceful fallback: return first 3 showcase questions
                # so the free user sees SOMETHING even if no showcase
                # matches the selected mode/filters.
                ids = list(
                    free_showcase_rows().filter(question__is_active=True).order_by('year', 'position')
                    .values_list('question_id', flat=True)[:3]
                )

        return Response({
            "mode": mode,
            "count": len(ids),
            "question_ids": ids,
            "freemium": is_free_user,
            "showcase_count": free_showcase_rows().count() if is_free_user else 0,
        })

    # Per-question AI text (why correct / why the distractors fail / clinical
    # pearl / mnemonic / concept) reveals the answer, so it follows the same
    # entitlement rule as the answer itself. Callers who are not entitled
    # get ``{<field>: null, "locked": true}`` (the reveal panel hides empty
    # sections).
    #
    # These GETs never wait on an LLM: they serve stored or cached text. On a
    # miss an authenticated, entitled caller queues ONE background generation
    # for the question (ai_per_question.queue_generation: single-flight,
    # charged to the caller's hourly budget) and gets HTTP 202
    # ``{<field>: null, "pending": true}``; a spent budget answers
    # ``{<field>: null, "rate_limited": true}``. Everyone else gets stored
    # content only.

    def _ai_text_response(self, request, field: str, producer, *, generate: bool = True):
        q = self.get_object()
        if not self._can_view_answer(q):
            return Response({field: None, "locked": True})
        value = producer(q)
        user = request.user
        if value is not None or not generate or not getattr(user, 'is_authenticated', False):
            return Response({field: value})
        outcome = _ai_per_question.queue_generation(q, user, field, unlimited=_is_staff_user(user))
        if outcome in ('queued', 'pending'):
            return Response({field: None, 'pending': True}, status=status.HTTP_202_ACCEPTED)
        payload = {field: None}
        if outcome == 'rate_limited':
            # The hourly generation budget is spent: say so instead of a
            # silently empty section.
            payload['rate_limited'] = True
        return Response(payload)

    # ``fallback=False``: no template boilerplate -- ``null`` when there is
    # no genuine content (the reveal panel hides empty sections). The
    # producers get no ``allow_ai``: stored / cached text only.

    @action(detail=True, methods=['get'], url_path='ai/concept',
            permission_classes=[permissions.AllowAny])
    def ai_concept(self, request, pk=None):
        return self._ai_text_response(
            request, "concept", lambda q: _ai_per_question.concept(q, fallback=False))

    @action(detail=True, methods=['get'], url_path='ai/why_correct',
            permission_classes=[permissions.AllowAny])
    def ai_why_correct(self, request, pk=None):
        return self._ai_text_response(
            request, "why_correct", lambda q: _ai_per_question.why_correct(q, fallback=False))

    @action(detail=True, methods=['get'], url_path='ai/why_incorrect',
            permission_classes=[permissions.AllowAny])
    def ai_why_incorrect(self, request, pk=None):
        # Curated / stored reasons only; nothing generates them.
        return self._ai_text_response(
            request, "why_incorrect", lambda q: _ai_per_question.why_incorrect(q, fallback=False),
            generate=False)

    @action(detail=True, methods=['get'], url_path='ai/clinical',
            permission_classes=[permissions.AllowAny])
    def ai_clinical(self, request, pk=None):
        return self._ai_text_response(
            request, "clinical_significance",
            lambda q: _ai_per_question.clinical_significance(q, fallback=False))

    @action(detail=True, methods=['get'], url_path='ai/mnemonic',
            permission_classes=[permissions.AllowAny])
    def ai_mnemonic(self, request, pk=None):
        return self._ai_text_response(
            request, "memory_trick", lambda q: _ai_per_question.memory_trick(q, fallback=False))

    @staticmethod
    def _limit_param(request, default: int = 8, maximum: int = 25) -> int:
        try:
            return max(1, min(int(request.query_params.get("limit", default)), maximum))
        except (TypeError, ValueError):
            return default

    @action(detail=True, methods=['get'], url_path='ai/related_pyqs',
            permission_classes=[permissions.AllowAny])
    def ai_related_pyqs(self, request, pk=None):
        q = self.get_object()
        limit = self._limit_param(request)
        rows = _ai_per_question.related_pyqs(q, limit=limit)
        return Response({"related_pyqs": self._stems_for_viewer(rows)})

    def _stems_for_viewer(self, rows):
        """Related-question dicts (``id`` / ``question_text``) for this viewer:
        a stem holding an answer / explanation label or a correctness flag on
        an option it lists, left there by an import (questions.answer_leak),
        is redacted on a question whose answer the viewer may not read."""
        user = getattr(self.request, 'user', None)
        if _is_staff_user(user) or self._user_is_premium():
            return rows
        leaky_ids = {row.get('id') for row in rows if row_has_answer_label(row)}
        if not leaky_ids:
            return rows
        free_ids = set(
            free_showcase_rows().filter(question_id__in=leaky_ids).values_list('question_id', flat=True)
        )
        out = []
        for row in rows:
            if row.get('id') in leaky_ids and row.get('id') not in free_ids:
                row = dict(row)
                redact_public_text(row)
            out.append(row)
        return out

    @action(detail=True, methods=['get'], url_path='ai/related_topics',
            permission_classes=[permissions.AllowAny])
    def ai_related_topics(self, request, pk=None):
        q = self.get_object()
        limit = self._limit_param(request)
        return Response({"related_topics": _ai_per_question.related_topics(q, limit=limit)})

    @action(detail=True, methods=['get'], url_path='ai/exam_importance',
            permission_classes=[permissions.AllowAny])
    def ai_exam_importance(self, request, pk=None):
        q = self.get_object()
        return Response({"exam_importance": _ai_per_question.exam_importance(q, fallback=False)})

    # ── Phase 3: question experience endpoints (flag / time / conf / elim) ──

    @action(detail=True, methods=['get'], url_path='practice/state',
            permission_classes=[permissions.IsAuthenticated])
    def practice_state(self, request, pk=None):
        q = self.get_object()
        return Response(_practice_experience.get_state(q, request.user))

    @action(detail=True, methods=['post'], url_path='practice/flag',
            permission_classes=[permissions.IsAuthenticated])
    def practice_flag(self, request, pk=None):
        q = self.get_object()
        raw_flag = request.data.get("flag", True)
        flag = raw_flag if isinstance(raw_flag, bool) else str(raw_flag).strip().lower() in ("1", "true", "yes", "on")
        return Response(_practice_experience.set_flag(q, request.user, flag))

    @action(detail=True, methods=['post'], url_path='practice/confidence',
            permission_classes=[permissions.IsAuthenticated])
    def practice_confidence(self, request, pk=None):
        q = self.get_object()
        try:
            rating = int(request.data.get("rating", 3))
        except (TypeError, ValueError):
            rating = 3
        return Response(_practice_experience.set_confidence(q, request.user, rating))

    @action(detail=True, methods=['post'], url_path='practice/eliminate',
            permission_classes=[permissions.IsAuthenticated])
    def practice_eliminate(self, request, pk=None):
        q = self.get_object()
        opts = request.data.get("options") or []
        return Response(_practice_experience.set_elimination(q, request.user, opts))

    @action(detail=True, methods=['post'], url_path='practice/time',
            permission_classes=[permissions.IsAuthenticated])
    def practice_time(self, request, pk=None):
        q = self.get_object()
        try:
            seconds = int(request.data.get("seconds", 0))
        except (TypeError, ValueError):
            seconds = 0
        total = _practice_experience.add_time_spent(q, request.user, seconds)
        return Response({"time_spent_seconds": total, "question_id": q.id})

    @action(detail=True, methods=['post'], url_path='practice/attempt',
            permission_classes=[permissions.IsAuthenticated])
    def practice_attempt(self, request, pk=None):
        q = self.get_object()
        raw_answer = request.data.get("answer")
        answer = raw_answer.strip().upper()[:1] if isinstance(raw_answer, str) else ""
        if answer and answer not in "ABCDE":
            return Response({"error": "answer must be one of A-E"}, status=status.HTTP_400_BAD_REQUEST)
        # Telling a caller whether a pick is right reveals the answer.
        if not self._can_view_answer(q):
            return _upgrade_required_response()
        try:
            time_spent = int(request.data.get("time_spent", 0))
        except (TypeError, ValueError):
            time_spent = 0
        try:
            confidence = int(request.data.get("confidence", 0)) or None
        except (TypeError, ValueError):
            confidence = None
        correct_answer = (q.correct_answer or "").strip().upper()[:1]
        # No answer key: the pick cannot be graded. Nothing is recorded as an
        # attempt or a mistake (the time still counts as study time); the
        # response carries ``correct_answer: ''`` and ``is_correct: null``.
        gradable = bool(correct_answer)
        is_correct = bool(answer) and gradable and answer == correct_answer
        payload = _practice_experience.submit_attempt(
            q, request.user,
            answer=answer if gradable else "", correct=is_correct,
            time_spent=time_spent, confidence=confidence,
        )
        created = payload.pop("created", False)
        if answer and gradable:
            _invalidate_user_question_caches(request.user.id)
        payload.update({
            "is_correct": is_correct if gradable else None,
            "correct_answer": correct_answer,
            "created": created,
            **_question_explanation_payload(q),
        })
        return Response(payload)

    @action(detail=True, methods=["post"], url_path='generate-explanation',
            permission_classes=[IsControlTowerAdmin])
    def generate_explanation(self, request, pk=None):
        """Generate an AI explanation for this question.

        Admin workflow: open question → verify correct answer → click "AI
        Generate Explanation" → AI fills ALL explanation fields → admin
        reviews → makes corrections → saves → next question.

        Request body:
        {
            "correct_answer": "A" | "B" | "C" | "D",   // required: which option is correct
            "regenerate_if_exists": false,                 // if true, overwrite existing explanation
            "update_correct_answer": false,                // store correct_answer (and lock it)
            "dry_run": false                               // generate only; nothing is saved
        }

        The AI's prompt explicitly locks on the selected correct_answer as
        the source of truth. It never silently changes the admin's choice;
        a missing or invalid ``correct_answer`` is a 400 (it used to fall
        back to the stored answer, or 'A').

        If an explanation already exists and regenerate_if_exists is false,
        the endpoint returns 409 with the existing data so the admin can
        confirm before overwriting (not for ``dry_run``: nothing is
        overwritten then).

        ``dry_run`` returns ``generated_fields`` without touching the row so
        the admin reviews them and the editor's Save stores them. Otherwise
        the fields are saved (after a revision snapshot) -- but never marked
        "Verified by Admin": unreviewed AI output must not carry that
        student-facing badge (verification is the separate ``verify``
        action), so a verified question whose content changes loses the
        mark (``verification_cleared`` in the response). The active admin
        prompt version leads the prompt and is recorded in the AI timeline
        (QuestionAIOperationLog), for dry runs too.
        """
        from ai_engine.services import AIService
        question = self.get_object()
        data = request.data if hasattr(request.data, 'get') else {}
        correct_answer = str(data.get('correct_answer') or '').strip().upper()
        if correct_answer.startswith('OPTION '):
            correct_answer = correct_answer[len('OPTION '):].strip()
        if correct_answer not in ('A', 'B', 'C', 'D'):
            return Response(
                {'detail': 'correct_answer is required and must be one of A, B, C, D.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        regenerate = _truthy(data.get('regenerate_if_exists'))
        update_answer = _truthy(data.get('update_correct_answer'))
        dry_run = _truthy(data.get('dry_run'))

        # Protection: don't silently overwrite existing manually-reviewed content
        existing_fields = ['explanation', 'concept_explanation', 'mnemonic',
                           'book_name', 'chapter', 'reference_text', 'shortcut_tip']
        has_existing = any(getattr(question, f, '') for f in existing_fields)
        if has_existing and not regenerate and not dry_run:
            return Response({
                'detail': 'This question already has an explanation. Set regenerate_if_exists=true to overwrite.',
                'existing_fields': {f: getattr(question, f, '') for f in existing_fields if getattr(question, f, '')},
                'requires_confirmation': True,
            }, status=status.HTTP_409_CONFLICT)
        active_prompt = AdminAIPromptVersion.objects.filter(is_active=True).first()

        options = {
            'A': question.option_a or '',
            'B': question.option_b or '',
            'C': question.option_c or '',
            'D': question.option_d or '',
        }

        try:
            # Collect images for AI context. QuestionImage has no alt_text
            # (the old `img.alt_text` raised AttributeError -> 500 for every
            # image without a caption, outside this try block); fall back to
            # the OCR text instead.
            image_descriptions = []
            for img in question.images.filter(is_active=True).order_by('image_index_in_page', 'id')[:6]:
                description = (img.caption or '').strip() or (img.ocr_text or '').strip()
                if description:
                    image_descriptions.append(description[:1000])

            ai_service = AIService()
            result = ai_service.generate_admin_explanation(
                question_text=question.question_text or '',
                options=options,
                correct_answer=correct_answer,
                subject=str(question.subject or ''),
                topic=str(question.topic or ''),
                exam_type=str(question.exam_type or 'cms'),
                existing_explanation=question.explanation or '',
                image_descriptions=image_descriptions if image_descriptions else None,
                user_prompt=(active_prompt.prompt_text if active_prompt else ''),
            )

            if not isinstance(result, dict) or result.get('_failed'):
                return Response({
                    'detail': 'AI generation failed. No changes were saved to the question.',
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            # Apply only the fields that were generated — never overwrite
            # unrelated admin data, and never store an outage sentence.
            updatable_fields = [
                'explanation', 'concept_explanation', 'mnemonic',
                'book_name', 'chapter', 'page_number', 'reference_text',
                'shortcut_tip', 'concept_keywords',
                'why_correct', 'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d',
            ]
            generated = {}
            for field in updatable_fields:
                value = result.get(field)
                if isinstance(value, str):
                    value = _usable_ai_text(value)
                if value:
                    generated[field] = value
            if not generated:
                return Response({
                    'detail': 'AI generation returned no usable content. No changes were saved to the question.',
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            def log_operation(provider):
                # QB-34: the AI timeline records which admin prompt version
                # led the generation, as force-regenerate does.
                QuestionAIOperationLog.objects.create(
                    question=question,
                    operation_type='regenerate',
                    provider=provider,
                    prompt_version=active_prompt,
                    tokens_used=max(1, sum(len(str(v)) for v in generated.values()) // 4),
                    response_excerpt=str(generated.get('explanation') or next(iter(generated.values())))[:500],
                    created_by=request.user,
                )

            if dry_run:
                log_operation('aiservice:generate-explanation:dry-run')
                return Response({
                    'detail': 'Explanation generated but not saved. Review it, then Save to store it.',
                    'generated_fields': generated,
                    'saved': False,
                    'dry_run': True,
                    'question': QuestionAdminListSerializer(question, context={'request': request}).data,
                })

            verification_cleared = False
            with transaction.atomic():
                self._capture_revision_snapshot(question, request.user, reason='Before AI generate-explanation')
                changed = []
                content_changed = False
                for field, value in generated.items():
                    content_changed = content_changed or _stored_value_differs(getattr(question, field, None), value)
                    setattr(question, field, value)
                    changed.append(field)
                # Optionally store the admin's answer: a human decision, so it
                # is locked against AI regeneration, verifiers and re-imports
                # (as a PATCH of correct_answer is).
                if update_answer and correct_answer != (question.correct_answer or '').strip().upper():
                    question.correct_answer = correct_answer
                    question.lock_answer = True
                    changed += ['correct_answer', 'lock_answer']
                    content_changed = True
                # QE-03: unreviewed AI text must not sit under an earlier
                # "Verified by Admin" badge. Saving new content clears the
                # mark (as the ``unverify`` action does; the revision
                # snapshot above keeps the verified state for undo). Verify
                # again after reviewing the text.
                if question.is_verified_by_admin and content_changed:
                    question.is_verified_by_admin = False
                    question.verified_by = None
                    question.verified_at = None
                    changed += ['is_verified_by_admin', 'verified_by', 'verified_at']
                    verification_cleared = True
                # Partial save: never write back stale copies of other fields.
                question.save(update_fields=changed + ['updated_at'])
                log_operation('aiservice:generate-explanation')
            question.refresh_from_db()

            if verification_cleared:
                detail = ('Explanation generated and saved. The earlier "Verified by Admin" mark was removed: '
                          'review the new text and verify again.')
            elif question.is_verified_by_admin:
                # Output identical to the stored text keeps the mark.
                detail = ('Explanation generated and saved; the stored text did not change, so it keeps its '
                          '"Verified by Admin" mark.')
            else:
                detail = 'Explanation generated and saved (not marked verified).'
            return Response({
                'detail': detail,
                'generated_fields': generated,
                'saved': True,
                'dry_run': False,
                'verification_cleared': verification_cleared,
                'question': QuestionAdminListSerializer(question, context={'request': request}).data,
            })
        except Exception:
            logger.exception("Admin explanation generation failed for Q%s", question.id)
            return Response({
                'detail': 'AI generation failed. No changes were saved to the question.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """Bulk upload questions (admin only)."""
        data = request.data if isinstance(request.data, list) else [request.data]
        serializer = QuestionUploadSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        questions = serializer.save()
        return Response(
            {'uploaded': len(questions), 'message': f'{len(questions)} questions uploaded successfully.'},
            status=status.HTTP_201_CREATED
        )

    def _serialize_revision_state(self, question):
        return {
            'question_text': question.question_text,
            'option_a': question.option_a,
            'option_b': question.option_b,
            'option_c': question.option_c,
            'option_d': question.option_d,
            'correct_answer': question.correct_answer,
            'year': question.year,
            'subject_id': question.subject_id,
            'topic_id': question.topic_id,
            'difficulty': question.difficulty,
            'paper': question.paper,
            'concept_id': question.concept_id,
            'explanation': question.explanation,
            'concept_explanation': question.concept_explanation,
            'mnemonic': question.mnemonic,
            'book_name': question.book_name,
            'chapter': question.chapter,
            'page_number': question.page_number,
            'reference_text': question.reference_text,
            'textbook_references': question.textbook_references,
            'concept_tags': question.concept_tags,
            # Students read the AI answer / explanation unless an admin locks
            # or overrides them, and force-regenerate rewrites them: undo must
            # restore them together with the verified flag (else undoing a
            # regenerate re-verified the new, unreviewed text).
            'ai_answer': question.ai_answer,
            'ai_explanation': question.ai_explanation,
            'ai_references': question.ai_references,
            'is_verified_by_admin': question.is_verified_by_admin,
            'verified_note': question.verified_note,
            'is_active': question.is_active,
        }

    def _capture_revision_snapshot(self, question, changed_by, reason=''):
        QuestionRevisionSnapshot.objects.create(
            question=question,
            changed_by=changed_by if getattr(changed_by, 'is_authenticated', False) else None,
            reason=reason or 'Pre-update snapshot',
            snapshot=self._serialize_revision_state(question),
        )

    def _apply_revision_state(self, question, snapshot):
        for field, value in snapshot.items():
            if field == 'subject_id':
                question.subject_id = value
            elif field == 'topic_id':
                question.topic_id = value
            else:
                setattr(question, field, value)
        question.save()

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            conflict = self._check_if_match_or_conflict(instance)
            if conflict is not None:
                return conflict
            self._capture_revision_snapshot(instance, request.user, reason='Before full update')
            return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            conflict = self._check_if_match_or_conflict(instance)
            if conflict is not None:
                return conflict
            self._capture_revision_snapshot(instance, request.user, reason='Before partial update')
            return super().partial_update(request, *args, **kwargs)

    def _extract_import_rows(self, request):
        """Return normalized import rows from JSON or CSV payload."""
        payload = request.data
        import_format = str(payload.get('format', 'json')).lower()
        if import_format == 'csv':
            csv_text = payload.get('csv_text', '')
            if not csv_text:
                return [], import_format
            reader = csv.DictReader(StringIO(csv_text))
            return list(reader), import_format

        rows = payload.get('rows', payload)
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            rows = []
        return rows, 'json'

    @action(detail=False, methods=['post'], url_path='import-preview')
    def import_preview(self, request):
        """Preview import result with schema validation and row-level errors."""
        rows, import_format = self._extract_import_rows(request)
        if not rows:
            return Response({'format': import_format, 'total_rows': 0, 'valid_rows': 0, 'invalid_rows': 0, 'to_create': 0, 'to_update': 0, 'errors': []})

        errors = []
        to_create = 0
        to_update = 0

        for idx, row in enumerate(rows, start=1):
            serializer = QuestionUploadSerializer(data=row)
            if not serializer.is_valid():
                errors.append({'row': idx, 'errors': serializer.errors})
                continue

            validated = serializer.validated_data
            existing = Question.objects.filter(
                year=validated.get('year'),
                subject=validated.get('subject'),
                question_text=validated.get('question_text', '')
            ).first()
            if existing:
                to_update += 1
            else:
                to_create += 1

        valid_rows = len(rows) - len(errors)
        return Response({
            'format': import_format,
            'total_rows': len(rows),
            'valid_rows': valid_rows,
            'invalid_rows': len(errors),
            'to_create': to_create,
            'to_update': to_update,
            'errors': errors,
        })

    @action(detail=False, methods=['patch'], url_path='bulk-metadata')
    def bulk_metadata(self, request):
        """Bulk edit metadata for selected questions."""
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            parsed_ids = [int(qid) for qid in ids]
        except (TypeError, ValueError):
            return Response({'error': 'ids must be a list of integers'}, status=status.HTTP_400_BAD_REQUEST)

        allowed_fields = ['subject', 'topic', 'difficulty', 'year', 'paper']
        update_data = {}
        for field in allowed_fields:
            if field in request.data:
                update_data[field] = request.data.get(field)

        if not update_data:
            return Response({'error': 'No metadata fields supplied'}, status=status.HTTP_400_BAD_REQUEST)

        if 'subject' in update_data:
            try:
                subject_id = int(update_data['subject'])
            except (TypeError, ValueError):
                return Response({'error': 'subject must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
            if not Subject.objects.filter(id=subject_id).exists():
                return Response({'error': 'subject is invalid'}, status=status.HTTP_400_BAD_REQUEST)
            update_data['subject_id'] = subject_id
            update_data.pop('subject', None)

        if 'topic' in update_data:
            try:
                topic_id = int(update_data['topic'])
            except (TypeError, ValueError):
                return Response({'error': 'topic must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
            if not Topic.objects.filter(id=topic_id).exists():
                return Response({'error': 'topic is invalid'}, status=status.HTTP_400_BAD_REQUEST)
            update_data['topic_id'] = topic_id
            update_data.pop('topic', None)

        if 'difficulty' in update_data and update_data['difficulty'] not in ['easy', 'medium', 'hard']:
            return Response({'error': 'difficulty must be one of: easy, medium, hard'}, status=status.HTTP_400_BAD_REQUEST)

        if 'year' in update_data:
            try:
                update_data['year'] = int(update_data['year'])
            except (TypeError, ValueError):
                return Response({'error': 'year must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

        if 'paper' in update_data:
            try:
                update_data['paper'] = int(update_data['paper'])
            except (TypeError, ValueError):
                return Response({'error': 'paper must be an integer'}, status=status.HTTP_400_BAD_REQUEST)

        updated = Question.objects.filter(id__in=parsed_ids).update(**update_data)
        return Response({'message': 'Bulk metadata update complete', 'updated': updated})

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """Soft delete selected questions with explicit confirmation token.

        Guards against accidental / malicious mass-archive:
        - Each id must parse to a positive integer (no strings, no dicts,
          no None).
        - List length is capped at 500 per request so a compromised
          admin token cannot archive the entire 8,000+ question bank in
          a single call.
        - Forensic audit log entry is written for every invocation, with
          a count and stable hash of the requested ids.
        """
        ids = request.data.get('ids', [])
        confirmation = str(request.data.get('confirm', '')).upper()
        if confirmation != 'DELETE':
            return Response({'error': "Provide confirm='DELETE' to execute bulk delete"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Cap batch size — soft-archiving >500 questions in a single
        # request is almost certainly an error or an attack.
        BULK_DELETE_MAX = 500
        if len(ids) > BULK_DELETE_MAX:
            return Response(
                {'error': f'Cannot bulk-delete more than {BULK_DELETE_MAX} questions per request. Split into smaller batches.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate each id is a positive integer.
        try:
            parsed_ids = [int(qid) for qid in ids]
        except (TypeError, ValueError):
            return Response({'error': 'ids must be a list of integers'}, status=status.HTTP_400_BAD_REQUEST)
        if any(qid <= 0 for qid in parsed_ids):
            return Response({'error': 'ids must be positive integers'}, status=status.HTTP_400_BAD_REQUEST)
        # Dedupe so audit log reflects the actual work performed.
        parsed_ids = sorted(set(parsed_ids))

        updated = Question.objects.filter(id__in=parsed_ids).update(is_active=False)

        # Best-effort audit log — same pattern as the dispute-resolve
        # action above. We log a stable hash of the requested ids so a
        # later DB restore can be cross-referenced without storing every
        # id in plaintext (which could leak the entire bank id
        # space).
        import hashlib
        ids_hash = hashlib.sha256(','.join(str(qid) for qid in parsed_ids).encode('utf-8')).hexdigest()[:16]
        try:
            from accounts.views import create_admin_audit_log
            create_admin_audit_log(
                actor=request.user,
                action='BULK_SOFT_DELETE',
                resource_type='Question',
                resource_id='bulk',
                detail=f'Soft-archived {updated} of {len(parsed_ids)} requested questions',
                metadata={
                    'requested_count': len(parsed_ids),
                    'updated_count': updated,
                    'ids_hash': ids_hash,
                },
            )
        except Exception as e:
            logger.error(f'Failed to log bulk soft-delete: {e}')

        return Response({
            'message': 'Bulk delete complete (soft archived)',
            'updated': updated,
            'requested': len(parsed_ids),
            'ids_hash': ids_hash,
        })

    @action(detail=False, methods=['post'], url_path='extraction/upload')
    def extraction_upload(self, request):
        """Upload a PYQ Word/PDF file and register extraction job."""
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'file is required'}, status=status.HTTP_400_BAD_REQUEST)

        filename = file_obj.name or ''
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        if ext not in ['doc', 'docx', 'pdf']:
            return Response({'error': 'Only .doc, .docx, .pdf files are supported'}, status=status.HTTP_400_BAD_REQUEST)
        # The extension is client-controlled: check the bytes too.
        from django.core.exceptions import ValidationError as DjangoValidationError
        from accounts.upload_validation import validate_uploaded_file
        try:
            validate_uploaded_file(file_obj, allowed_types={'document'}, max_bytes=50 * 1024 * 1024)
        except DjangoValidationError as exc:
            return Response({'error': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        job_type = 'word' if ext in ['doc', 'docx'] else 'pdf'
        stored_path = default_storage.save(f'pyq_uploads/{timezone.now().strftime("%Y%m%d_%H%M%S")}_{filename}', file_obj)

        job = QuestionImportJob.objects.create(
            job_type=job_type,
            status='queued',
            source_filename=filename,
            stored_file_path=stored_path,
            # Honest status: no worker parses these jobs. The placeholder
            # item below must be filled in by hand (and approved) before it
            # can be published; real PDF/DOCX ingestion is the Admin Import
            # Center (material_importer).
            summary={
                'message': 'File stored. Automatic extraction is not available for this queue; '
                           'enter the questions manually or use the Admin Import Center.',
                'parser': 'none',
            },
            created_by=request.user if request.user.is_authenticated else None,
        )

        guessed_year, guessed_paper = self._guess_year_paper_from_filename(filename)
        QuestionExtractionItem.objects.create(
            job=job,
            status='pending',
            raw_text=f'Extraction placeholder for file: {filename}',
            question_text='Extracted content pending parser review',
            year=guessed_year,
            paper=guessed_paper,
            tags=[f'auto_year:{guessed_year}'] if guessed_year else [],
            review_note='Auto-generated placeholder item. Replace with parsed extraction output.',
        )

        serializer = QuestionImportJobSerializer(job)
        return Response({'message': 'Extraction job queued', 'job': serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='extraction/jobs')
    def extraction_jobs(self, request):
        """List extraction/import jobs for admin monitoring."""
        raw_limit = request.query_params.get('limit', 100)
        try:
            parsed_limit = int(raw_limit)
        except (TypeError, ValueError):
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        if parsed_limit <= 0:
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        limit = min(parsed_limit, 500)
        jobs = QuestionImportJob.objects.select_related('created_by').all()[:limit]
        serializer = QuestionImportJobSerializer(jobs, many=True)
        return Response({'count': len(serializer.data), 'results': serializer.data})

    @action(detail=False, methods=['get'], url_path=r'extraction/jobs/(?P<job_id>[^/.]+)/items')
    def extraction_items(self, request, job_id=None):
        """List staged extraction items for a specific job."""
        items = QuestionExtractionItem.objects.select_related('subject', 'topic').filter(job_id=job_id)
        serializer = QuestionExtractionItemSerializer(items, many=True)
        return Response({'count': len(serializer.data), 'results': serializer.data})

    @action(detail=False, methods=['patch'], url_path=r'extraction/items/(?P<item_id>[^/.]+)')
    def extraction_item_update(self, request, item_id=None):
        """Edit extraction item fields before approval/publish."""
        try:
            item = QuestionExtractionItem.objects.get(id=item_id)
        except QuestionExtractionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        allowed_fields = [
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'year', 'paper', 'subject',
            'topic', 'tags', 'review_note'
        ]
        update_data = {k: request.data.get(k) for k in allowed_fields if k in request.data}
        serializer = QuestionExtractionItemSerializer(item, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Extraction item updated', 'item': serializer.data})

    @action(detail=True, methods=['post'], url_path='generate-video')
    def generate_video(self, request, pk=None):
        """Enqueue video generation task for the question."""
        from django_q.tasks import async_task
        question = self.get_object()
        force = bool(request.data.get('force', False))
        question.video_status = 'pending'
        question.video_error = ''
        question.save(update_fields=['video_status', 'video_error'])
        try:
            async_task('video_engine.tasks.generate_video_task', question.id, force)
        except Exception as exc:
            question.video_status = 'failed'
            question.video_error = str(exc)[:500]
            question.save(update_fields=['video_status', 'video_error'])
            return Response(
                {'error': 'Video generation could not be queued', 'detail': str(exc)[:500]},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'message': 'Video generation queued', 'id': question.id, 'video_status': 'pending', 'force': force})

    @action(detail=False, methods=['post'], url_path=r'extraction/items/(?P<item_id>[^/.]+)/autotag')
    def extraction_item_autotag(self, request, item_id=None):
        """Auto-tag extraction item by inferred year/paper from source filename."""
        try:
            item = QuestionExtractionItem.objects.select_related('job').get(id=item_id)
        except QuestionExtractionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        year, paper = self._guess_year_paper_from_filename(item.job.source_filename or '')
        if year:
            item.year = year
        if paper:
            item.paper = paper
        tags = item.tags if isinstance(item.tags, list) else []
        if year and f'auto_year:{year}' not in tags:
            tags.append(f'auto_year:{year}')
        if paper and f'auto_paper:{paper}' not in tags:
            tags.append(f'auto_paper:{paper}')
        item.tags = tags
        item.save(update_fields=['year', 'paper', 'tags', 'updated_at'])
        serializer = QuestionExtractionItemSerializer(item)
        return Response({'message': 'Auto-tag complete', 'item': serializer.data})

    @action(detail=False, methods=['post'], url_path=r'extraction/items/(?P<item_id>[^/.]+)/approve')
    def extraction_item_approve(self, request, item_id=None):
        """Mark extraction item approved for publish."""
        try:
            item = QuestionExtractionItem.objects.get(id=item_id)
        except QuestionExtractionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        item.status = 'approved'
        item.save(update_fields=['status', 'updated_at'])
        serializer = QuestionExtractionItemSerializer(item)
        return Response({'message': 'Item approved', 'item': serializer.data})

    @action(detail=False, methods=['post'], url_path=r'extraction/items/(?P<item_id>[^/.]+)/reject')
    def extraction_item_reject(self, request, item_id=None):
        """Reject extraction item during review."""
        try:
            item = QuestionExtractionItem.objects.get(id=item_id)
        except QuestionExtractionItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        note = request.data.get('review_note', '')
        item.status = 'rejected'
        if note:
            item.review_note = note
        item.save(update_fields=['status', 'review_note', 'updated_at'])
        serializer = QuestionExtractionItemSerializer(item)
        return Response({'message': 'Item rejected', 'item': serializer.data})

    _EXAM_TYPE_TO_SOURCE = {
        'cms': 'UPSC CMS', 'neet_pg': 'NEET PG', 'ini_cet': 'INI-CET',
        'usmle': 'USMLE', 'fmge': 'FMGE',
    }

    def _extraction_exam_for(self, request, item):
        """(exam_source, exam_type) for a published extraction item: an
        explicit ``exam_type`` in the request body, else the item subject's
        exam, else UPSC CMS (the old hard-coded value)."""
        requested = str((request.data or {}).get('exam_type') or '').strip().lower()
        exam_type = requested if requested in self._EXAM_TYPE_TO_SOURCE else ''
        if not exam_type:
            exam_type = getattr(item.subject, 'exam_type', '') or 'cms'
            if exam_type not in self._EXAM_TYPE_TO_SOURCE:
                exam_type = 'cms'
        return self._EXAM_TYPE_TO_SOURCE[exam_type], exam_type

    @action(detail=False, methods=['post'], url_path=r'extraction/items/(?P<item_id>[^/.]+)/publish')
    def extraction_item_publish(self, request, item_id=None):
        """Publish approved extraction item as a live question."""
        with transaction.atomic():
            try:
                # of=('self',): subject / topic are nullable FKs (outer join).
                item = QuestionExtractionItem.objects.select_for_update(of=('self',)).select_related('subject', 'topic').get(id=item_id)
            except QuestionExtractionItem.DoesNotExist:
                return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

            if item.published_question_id:
                serializer = QuestionExtractionItemSerializer(item)
                return Response(
                    {'message': 'Item already published', 'question_id': item.published_question_id, 'item': serializer.data},
                    status=status.HTTP_200_OK,
                )

            # Only reviewed, complete items may go live. The upload step
            # creates a placeholder item (no parser consumes these jobs), and
            # publishing it used to create a live question with empty
            # options and a hard-coded answer 'A'.
            if item.status != 'approved':
                return Response(
                    {'error': f'Only approved items can be published (status is {item.status!r}).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not item.subject or not (item.question_text or '').strip():
                return Response({'error': 'Subject and question_text are required before publish'}, status=status.HTTP_400_BAD_REQUEST)
            if item.question_text.strip() == 'Extracted content pending parser review':
                return Response({'error': 'This is an unparsed placeholder item; enter the real question first.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if not all((getattr(item, f) or '').strip() for f in ('option_a', 'option_b', 'option_c', 'option_d')):
                return Response({'error': 'All four options are required before publish'}, status=status.HTTP_400_BAD_REQUEST)
            publish_answer = (item.correct_answer or '').strip().upper()
            if publish_answer not in ('A', 'B', 'C', 'D'):
                return Response({'error': 'An explicit correct_answer (A-D) is required before publish'},
                                status=status.HTTP_400_BAD_REQUEST)
            exam_source, exam_type = self._extraction_exam_for(request, item)

            # Honor admin "Remove from bank" tombstones — if this stem was
            # previously removed, refuse to publish it back into the bank.
            if _pre_check_remove(item.question_text, where="questions.views.publish_question"):
                return Response(
                    {'error': 'Stem matches a previously-removed question; un-remove first.'},
                    status=status.HTTP_409_CONFLICT,
                )

            question = Question.objects.create(
                question_text=item.question_text,
                option_a=item.option_a or '',
                option_b=item.option_b or '',
                option_c=item.option_c or '',
                option_d=item.option_d or '',
                correct_answer=publish_answer,
                year=item.year or timezone.now().year,
                subject=item.subject,
                topic=item.topic,
                difficulty='medium',
                concept_tags=item.tags if isinstance(item.tags, list) else [],
                explanation=item.explanation or '',
                paper=item.paper or 0,
                source=f'extraction_job_{item.job_id}_item_{item.id}',
                exam_source=exam_source,
                exam_type=exam_type,
                is_active=True,
            )

            item.status = 'published'
            item.published_question = question
            item.save(update_fields=['status', 'published_question', 'updated_at'])

        serializer = QuestionExtractionItemSerializer(item)
        return Response({'message': 'Item published as question', 'question_id': question.id, 'item': serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path=r'extraction/jobs/(?P<job_id>[^/.]+)/retry')
    def extraction_retry(self, request, job_id=None):
        """Mark a failed/completed extraction job for retry."""
        try:
            job = QuestionImportJob.objects.get(id=job_id)
        except QuestionImportJob.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        job.status = 'queued'
        job.summary = {**(job.summary or {}), 'retry_requested_at': timezone.now().isoformat()}
        job.save(update_fields=['status', 'summary', 'updated_at'])
        serializer = QuestionImportJobSerializer(job)
        return Response({'message': 'Extraction job queued for retry', 'job': serializer.data})

    @action(detail=True, methods=['post'], url_path='attempt')
    def attempt(self, request, pk=None):
        """Record an attempt on a QBank question and update statistics."""
        question = self.get_object()
        raw_answer = request.data.get('selected_answer')
        # Normalise: the column is CharField(max_length=1) (longer values made
        # Postgres reject the insert -> 500) and the comparison used to be
        # case-sensitive ('a' was marked wrong).
        selected_answer = str(raw_answer).strip().upper()[:1] if isinstance(raw_answer, str) else ''
        if not selected_answer or selected_answer not in 'ABCDE':
            return Response({'error': 'selected_answer must be one of A-E'}, status=status.HTTP_400_BAD_REQUEST)

        # The response reveals the answer: free users may only submit on
        # showcase questions (premium / admin: everything).
        if not self._can_view_answer(question):
            return _upgrade_required_response()

        from questions.study_time import clamp_seconds, record_study_time
        seconds = clamp_seconds(request.data.get('time_spent_seconds'))
        correct_answer = (question.correct_answer or '').strip().upper()[:1]

        if not correct_answer:
            # No answer key: the pick cannot be graded, so it is neither an
            # attempt nor a mistake (it used to be stored as a wrong answer
            # and filed in the mistake notebook). The time still counts as
            # study time. ``correct_answer: ''`` tells the UI "no key".
            record_study_time(request.user, [(question.subject_id, seconds, 0)])
            return Response({
                'is_correct': None,
                'correct_answer': '',
                **_question_explanation_payload(question),
                # Premium entitlement (Subscription rows), not the legacy
                # CustomUser.is_subscribed flag, which no longer means premium.
                'is_subscribed': self._user_is_premium(),
            })

        is_correct = selected_answer == correct_answer

        from questions.models import QuestionAttempt

        attempt, created = QuestionAttempt.objects.update_or_create(
            user=request.user,
            question=question,
            defaults={
                'selected_answer': selected_answer,
                'is_correct': is_correct
            }
        )
        if not is_correct:
            from questions.mistakes import record_mistake
            record_mistake(request.user, question, selected_answer, attempt=attempt)

        record_study_time(request.user, [(question.subject_id, seconds, 1)])

        # Invalidate per-user caches so dashboard + question list stay fresh.
        _invalidate_user_question_caches(request.user.id)

        if created:
            # Topic / subject performance (attempts and, AN-30, the answer
            # time behind /analytics "Avg Time"), daily activity (quests) and
            # streak XP -- atomic F() increments (two tabs used to race).
            _practice_experience.record_attempt_stats(request.user, question, is_correct, seconds=seconds)

        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            **_question_explanation_payload(question),
            'is_subscribed': self._user_is_premium(),
        })

    @action(detail=True, methods=['post'], url_path='bookmark')
    def bookmark(self, request, pk=None):
        """Toggle bookmark on a question."""
        question = self.get_object()
        bookmark, created = QuestionBookmark.objects.get_or_create(
            user=request.user, question=question
        )
        _bump_question_list_cache_version(request.user.id)
        if not created:
            bookmark.delete()
            return Response({'bookmarked': False})
        return Response({'bookmarked': True}, status=status.HTTP_201_CREATED)

    BOOKMARKS_MAX = 500

    @action(detail=False, methods=['get'], url_path='bookmarks')
    def my_bookmarks(self, request):
        """List current user's bookmarked questions (newest first).

        Without ``?page=`` the response stays a plain array (what the
        bookmarks page expects), capped at ``BOOKMARKS_MAX`` rows; with
        ``?page=`` it is paginated (``count`` / ``results``). The nested
        question rows are fully select/prefetch-related -- the old version
        ran ~7 queries per bookmark.
        """
        bookmarks = _question_list_related(
            QuestionBookmark.objects.filter(user=request.user), prefix='question__',
        ).order_by('-created_at', '-id')
        context = self.get_serializer_context()
        if request.query_params.get('page'):
            page = self.paginate_queryset(bookmarks)
            if page is not None:
                serializer = BookmarkSerializer(page, many=True, context=context)
                return self.get_paginated_response(serializer.data)
        serializer = BookmarkSerializer(bookmarks[:self.BOOKMARKS_MAX], many=True, context=context)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='years')
    def available_years(self, request):
        """Years that have questions, newest first (a plain array).

        Optional filters: ``exam_type`` (``cms`` / ``neet_pg`` / ...) and
        ``exam_source`` (label, prefix-matched like the list filter, so
        ``NEET PG`` also covers ``NEET PG (recall)``). Year 0 / negative
        ("unknown year") is never listed, and only active questions count
        for students (admins also see years that only archived rows have).
        It used to list every year of every exam, archived rows and 0.
        """
        user = request.user
        qs = Question.objects.filter(year__gt=0)
        if not (getattr(user, 'is_authenticated', False)
                and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False))):
            qs = qs.filter(is_active=True)
        exam_type = (request.query_params.get('exam_type') or '').strip()
        if exam_type:
            qs = qs.filter(exam_type=exam_type)
        exam_source = (request.query_params.get('exam_source') or '').strip()
        if exam_source:
            qs = qs.filter(exam_source_filter_q(exam_source))
        years = qs.order_by('-year').values_list('year', flat=True).distinct()
        return Response(list(years))

    @action(detail=False, methods=['get'], url_path='stats')
    def question_stats(self, request):
        """Return question count statistics by subject, year, difficulty with user progress.

        Accepts either:
          - ``exam_source`` (full DB label, e.g. ``"UPSC CMS"``, ``"NEET PG"``) — direct match
          - ``exam_type``   (enum slug, e.g. ``"cms"``, ``"neet_pg"``)        — mapped
          - ``exam``        (URL slug,  e.g. ``"cms"``, ``"neet-pg"``)        — mapped

        The mapping collapses two distinct data-model concepts:
          * ``Question.exam_type``   (enum: cms/neet_pg/usmle/fmge)
          * ``Question.exam_source`` (free text: "UPSC CMS", "NEET PG", ...)

        Older clients sent the short slug directly to ``exam_source`` which produced
        an empty ``by_year`` array (the bug). The normaliser below resolves the
        incoming key to the correct ``exam_source`` value before filtering so both
        old and new client conventions Just Work.
        """
        from django.db.models import Count

        # Slug → human label stored in Question.exam_source. Keep in sync with
        # seed_data.py / import_neet_pg.py / import_txt.py --exam-source.
        EXAM_SLUG_TO_SOURCE = {
            'cms': 'UPSC CMS',
            'upsc_cms': 'UPSC CMS',
            'upsc-cms': 'UPSC CMS',
            'neet_pg': 'NEET PG',
            'neet-pg': 'NEET PG',
            'neetpg': 'NEET PG',
            'ini_cet': 'INI-CET',
            'ini-cet': 'INI-CET',
            'inicet': 'INI-CET',
            'fmge': 'FMGE',
            'usmle': 'USMLE',
            'medical_officer': 'Medical Officer',
            'medical-officer': 'Medical Officer',
            'medicalofficer': 'Medical Officer',
        }
        # Extra alias table — recall imports and legacy imports use
        # "(recall)" / "(official)" suffixes that the dashboard needs
        # to fold back to the same bucket. When the slug resolves to
        # "NEET PG", we additionally match anything starting with that
        # label (without the LIKE wildcard). See the filtering block
        # below — `_startswith` is applied directly to the bare prefix.
        EXAM_SOURCE_PREFIXES = {
            'NEET PG': ('NEET PG',),
            'UPSC CMS': ('UPSC CMS',),
            # The INI-CET bank is stored as 'INI-CET (recall)' and, by older
            # imports, 'INICET': an exact 'INI-CET' match found no rows.
            # Either label selects the whole bank (as the list filter does).
            'INI-CET': INI_CET_SOURCE_PREFIXES,
            'INICET': INI_CET_SOURCE_PREFIXES,
        }
        # ``Question.exam_type`` enum → source. exam_type uses ``cms`` and
        # ``neet_pg`` (underscores) so this is just the slug→source map
        # restricted to enum keys.
        EXAM_TYPE_TO_SOURCE = {k: v for k, v in EXAM_SLUG_TO_SOURCE.items()
                               if k in {'cms', 'neet_pg', 'ini_cet', 'usmle', 'fmge'}}

        user = request.user
        has_user = user and user.is_authenticated

        # Resolve whichever key the caller sent. Priority: explicit exam_source
        # (literal DB label) wins; otherwise we accept exam_type or exam.
        exam_source_param = request.query_params.get('exam_source')
        exam_type_param = request.query_params.get('exam_type')
        exam_slug_param = request.query_params.get('exam')

        exam_source = None
        if exam_source_param:
            exam_source = exam_source_param
        elif exam_type_param and exam_type_param in EXAM_TYPE_TO_SOURCE:
            exam_source = EXAM_TYPE_TO_SOURCE[exam_type_param]
        elif exam_slug_param and exam_slug_param in EXAM_SLUG_TO_SOURCE:
            exam_source = EXAM_SLUG_TO_SOURCE[exam_slug_param]

        from questions.models import QuestionAttempt

        # Build a single base Q filter for exam_source and reuse it everywhere
        # (no N+1 across years/subjects/difficulties). This kills the previous
        # N+4 queries that timed out the endpoint under load.
        def _exam_source_q() -> Q:
            if not exam_source:
                return Q()
            prefixes = EXAM_SOURCE_PREFIXES.get(exam_source, ())
            q = Q(exam_source=exam_source)
            for pat in prefixes:
                q |= Q(exam_source__startswith=pat)
            return q

        # Base count
        total_qs = Question.objects.filter(is_active=True).filter(_exam_source_q())
        total_count = total_qs.count()

        # Total solved
        if has_user:
            solved_qs = QuestionAttempt.objects.filter(user=user).filter(
                Q(question__exam_source=exam_source) if exam_source else Q()
            )
            # Add prefix matches (e.g. NEET PG recall)
            if exam_source:
                prefixes = EXAM_SOURCE_PREFIXES.get(exam_source, ())
                for pat in prefixes:
                    solved_qs = solved_qs | QuestionAttempt.objects.filter(
                        user=user, question__exam_source__startswith=pat
                    )
            total_solved = solved_qs.distinct().count()
        else:
            total_solved = 0

        # Progress by year (one aggregate query). Year 0 / NULL is the
        # "unknown year" / Expert Curated bucket, not a paper year (the
        # years endpoint never lists it either).
        by_year_raw = list(
            total_qs.filter(year__gt=0).values('year').annotate(count=Count('id')).order_by('-year')
        )
        # Pre-compute solved counts per year in ONE aggregate query.
        solved_by_year_map = {}
        if has_user and by_year_raw:
            years = [row['year'] for row in by_year_raw]
            qa_year = QuestionAttempt.objects.filter(user=user, question__year__in=years)
            if exam_source:
                prefixes = EXAM_SOURCE_PREFIXES.get(exam_source, ())
                qa_q = Q(question__exam_source=exam_source)
                for pat in prefixes:
                    qa_q |= Q(question__exam_source__startswith=pat)
                qa_year = qa_year.filter(qa_q)
            for row in qa_year.values('question__year').annotate(c=Count('id')):
                solved_by_year_map[row['question__year']] = row['c']
        by_year = [
            {'year': row['year'], 'count': row['count'], 'solved': solved_by_year_map.get(row['year'], 0)}
            for row in by_year_raw
        ]

        # Progress by subject — bulk query (no per-subject round-trip)
        subject_counts = dict(
            total_qs.values_list('subject_id').annotate(c=Count('id')).values_list('subject_id', 'c')
        )
        # Subject-solved counts in one aggregate
        solved_by_subject_map = {}
        if has_user:
            qa_sub = QuestionAttempt.objects.filter(user=user).filter(
                Q(question__exam_source=exam_source) if exam_source else Q()
            )
            if exam_source:
                prefixes = EXAM_SOURCE_PREFIXES.get(exam_source, ())
                for pat in prefixes:
                    qa_sub = qa_sub | QuestionAttempt.objects.filter(
                        user=user, question__exam_source__startswith=pat
                    )
            for row in qa_sub.values_list('question__subject_id').annotate(c=Count('id')):
                solved_by_subject_map[row[0]] = row[1]

        by_subject = []
        for subject in Subject.objects.all():
            count = subject_counts.get(subject.id, 0)
            if count == 0:
                # A subject without active questions in this bank is not a
                # row of its progress table (it used to be skipped for NEET
                # PG only, so every other exam listed all other exams'
                # subjects at 0).
                continue
            by_subject.append({
                'id': subject.id,
                # The loader's "Imported" bucket is "Expert Curated" to students.
                'name': public_subject_name(subject.name),
                'code': subject.code,
                'count': count,
                'solved': solved_by_subject_map.get(subject.id, 0),
            })

        # Progress by difficulty — bulk
        by_difficulty_raw = list(
            total_qs.values('difficulty').annotate(count=Count('id'))
        )
        solved_by_diff_map = {}
        if has_user:
            qa_diff = QuestionAttempt.objects.filter(user=user).filter(
                Q(question__exam_source=exam_source) if exam_source else Q()
            )
            if exam_source:
                prefixes = EXAM_SOURCE_PREFIXES.get(exam_source, ())
                for pat in prefixes:
                    qa_diff = qa_diff | QuestionAttempt.objects.filter(
                        user=user, question__exam_source__startswith=pat
                    )
            for row in qa_diff.values_list('question__difficulty').annotate(c=Count('id')):
                solved_by_diff_map[row[0]] = row[1]
        by_difficulty = [
            {'difficulty': row['difficulty'], 'count': row['count'],
             'solved': solved_by_diff_map.get(row['difficulty'], 0)}
            for row in by_difficulty_raw
        ]

        stats = {
            'total': total_count,
            'total_solved': total_solved,
            'by_subject': by_subject,
            'by_year': by_year,
            'by_difficulty': by_difficulty,
        }
        return Response(stats)

    @action(detail=True, methods=['get'], url_path='similar')
    def similar_questions(self, request, pk=None):
        """Return similar questions with an attached similarity_reason.

        PHASE 5 (2026-07-25): each item now carries a `similarity_reason`
        one of:
          - 'same_concept'        — same `concept_id`
          - 'same_topic'          — same `topic` FK
          - 'same_subject'        — same `subject` FK only
          - 'same_image'          — shares a QuestionImage sha256_short
          - 'curated'             — listed in `similar_questions` M2M

        Ranking: curated M2M > same_concept > same_image > same_topic >
        same_subject. Capped at 8 results.
        """
        question = self.get_object()
        LIMIT = 8
        # Removed / archived / dropped questions must never be recommended.
        active = Question.objects.filter(is_active=True)

        # Bucket 1: explicit M2M curation (admin-set "questions testing
        # the same concept"). Always surface these first if present.
        curated_ids = list(question.similar_questions.filter(is_active=True).values_list('id', flat=True))
        # Bucket 2: same concept_id (stable AI-assigned concept key).
        same_concept_ids = []
        if question.concept_id:
            same_concept_ids = list(
                active.filter(concept_id=question.concept_id)
                .exclude(id=question.id)
                .exclude(id__in=curated_ids)
                .values_list('id', flat=True)[:LIMIT]
            )
        # Bucket 3: shares an image (same sha256_short fingerprint).
        same_image_ids = []
        image_hashes = [
            h for h in question.images.filter(is_active=True).values_list('sha256_short', flat=True) if h
        ]
        if image_hashes:
            same_image_ids = list(
                QuestionImage.objects.filter(
                    is_active=True, sha256_short__in=image_hashes, question__is_active=True,
                )
                .exclude(question_id=question.id)
                .exclude(question_id__in=curated_ids + same_concept_ids)
                .values_list('question_id', flat=True)
                .distinct()[:LIMIT]
            )
        # Bucket 4: same topic.
        same_topic_ids = []
        if question.topic_id:
            same_topic_ids = list(
                active.filter(topic_id=question.topic_id)
                .exclude(id=question.id)
                .exclude(id__in=curated_ids + same_concept_ids + same_image_ids)
                .values_list('id', flat=True)[:LIMIT]
            )
        # Bucket 5: same subject (fallback so we always return *something*
        # — better to suggest something than an empty sidebar).
        same_subject_ids = list(
            active.filter(subject_id=question.subject_id)
            .exclude(id=question.id)
            .exclude(id__in=curated_ids + same_concept_ids + same_image_ids + same_topic_ids)
            .values_list('id', flat=True)[: max(0, LIMIT - len(curated_ids) - len(same_concept_ids) - len(same_image_ids) - len(same_topic_ids))]
        )

        # Stitch the buckets in priority order. The dict preserves
        # order (Python 3.7+) so the first occurrence wins.
        ordered_ids: list[int] = []
        reasons: dict[int, str] = {}
        for bid, reason in (
            (curated_ids, 'curated'),
            (same_concept_ids, 'same_concept'),
            (same_image_ids, 'same_image'),
            (same_topic_ids, 'same_topic'),
            (same_subject_ids, 'same_subject'),
        ):
            for qid in bid:
                if qid in reasons:
                    continue  # already ranked higher
                reasons[qid] = reason
                ordered_ids.append(qid)
                if len(ordered_ids) >= LIMIT:
                    break
            if len(ordered_ids) >= LIMIT:
                break

        # Re-hydrate in the priority order via a single query (plus the
        # prefetches the list serializer needs -- it used to cost ~7
        # queries per row).
        if not ordered_ids:
            return Response([])
        preserve = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)],
                        default=len(ordered_ids), output_field=IntegerField())
        rows = list(_question_list_related(active.filter(pk__in=ordered_ids)).order_by(preserve))
        data = QuestionListSerializer(rows, many=True, context=self.get_serializer_context()).data

        # Attach the reason to each serialized item.
        for item, row in zip(data, rows):
            item['similarity_reason'] = reasons.get(row.id, 'same_subject')
        return Response(data)

    @action(detail=True, methods=['patch'], url_path='verify')
    def verify(self, request, pk=None):
        """Mark a question as verified by admin with optional note."""
        question = self.get_object()
        note = request.data.get('verified_note', '')
        question.is_verified_by_admin = True
        question.verified_by = request.user
        question.verified_at = timezone.now()
        if note:
            question.verified_note = note
        question.save(update_fields=['is_verified_by_admin', 'verified_by', 'verified_at', 'verified_note'])
        return Response({'message': 'Question verified by admin', 'id': question.id, 'is_verified_by_admin': True})

    @action(detail=True, methods=['patch'], url_path='unverify')
    def unverify(self, request, pk=None):
        """Remove verified-by-admin marker from a question."""
        question = self.get_object()
        question.is_verified_by_admin = False
        question.verified_by = None
        question.verified_at = None
        question.save(update_fields=['is_verified_by_admin', 'verified_by', 'verified_at'])
        return Response({'message': 'Question unverified', 'id': question.id, 'is_verified_by_admin': False})

    @action(detail=True, methods=['patch'], url_path='ai-override')
    def ai_override(self, request, pk=None):
        """Override AI outputs with admin-provided values."""
        question = self.get_object()
        fields = []

        if 'admin_answer_override' in request.data:
            question.admin_answer_override = request.data.get('admin_answer_override', '')
            fields.append('admin_answer_override')
        if 'admin_explanation_override' in request.data:
            question.admin_explanation_override = request.data.get('admin_explanation_override', '')
            fields.append('admin_explanation_override')
        if 'admin_mnemonic_override' in request.data:
            question.admin_mnemonic_override = request.data.get('admin_mnemonic_override', '')
            fields.append('admin_mnemonic_override')
        if 'admin_references_override' in request.data:
            value = request.data.get('admin_references_override', [])
            question.admin_references_override = value if isinstance(value, list) else []
            fields.append('admin_references_override')

        if not fields:
            return Response({'error': 'No override fields supplied'}, status=status.HTTP_400_BAD_REQUEST)

        question.save(update_fields=fields)

        payload_text = (
            (request.data.get('admin_answer_override', '') or '')
            + (request.data.get('admin_explanation_override', '') or '')
            + (request.data.get('admin_mnemonic_override', '') or '')
            + ' '.join(request.data.get('admin_references_override', []) or [])
        )
        QuestionAIOperationLog.objects.create(
            question=question,
            operation_type='override',
            provider='admin-manual',
            tokens_used=max(1, len(payload_text) // 4),
            response_excerpt=payload_text[:500],
            created_by=request.user,
        )

        return Response({'message': 'AI overrides updated', 'id': question.id})

    @action(detail=True, methods=['patch'], url_path='ai-lock')
    def ai_lock(self, request, pk=None):
        """Lock/unlock answer and explanation fields against AI overwrite."""
        question = self.get_object()
        fields = []

        if 'lock_answer' in request.data:
            question.lock_answer = bool(request.data.get('lock_answer'))
            fields.append('lock_answer')
        if 'lock_explanation' in request.data:
            question.lock_explanation = bool(request.data.get('lock_explanation'))
            fields.append('lock_explanation')

        if not fields:
            return Response({'error': 'No lock fields supplied'}, status=status.HTTP_400_BAD_REQUEST)

        question.save(update_fields=fields)
        return Response({'message': 'AI lock settings updated', 'id': question.id, 'lock_answer': question.lock_answer, 'lock_explanation': question.lock_explanation})

    @action(detail=True, methods=['post'], url_path='force-regenerate')
    def force_regenerate(self, request, pk=None):
        """Force regenerate AI fields while respecting lock precedence.

        Calls the real AIService.analyze_question() — never writes
        placeholder text. If the AI service is unavailable, returns 503
        and leaves the existing ai_* fields intact.

        Students read ``ai_answer`` / ``ai_explanation`` (effective answer /
        explanation) unless the admin locked or overrode them, so the save
        follows generate-explanation (QE-03): a revision snapshot first (undo
        restores the earlier AI text and the verified state), and a verified
        question whose AI content changes loses its "Verified by Admin" mark
        (``verification_cleared``) until an admin reviews it again.
        """
        question = self.get_object()

        # Nothing to do if every AI field is locked — surface a clear 4xx
        # so admins don't trigger an empty round-trip audit log entry.
        if question.lock_answer and question.lock_explanation:
            return Response(
                {'error': 'All AI fields are locked; nothing to regenerate.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from ai_engine.services import AIService
        # The admin-managed active prompt version (ai-prompt-versions) is fed
        # to the model as the leading instruction; before it was stored and
        # "activated" but never used by any AI call.
        active_prompt = AdminAIPromptVersion.objects.filter(is_active=True).first()
        try:
            service = AIService()
            options = {
                'A': question.option_a or '',
                'B': question.option_b or '',
                'C': question.option_c or '',
                'D': question.option_d or '',
            }
            analysis = service.analyze_question(
                question_text=question.question_text or '',
                options=options,
                correct_answer=question.correct_answer or '',
                user_prompt=(active_prompt.prompt_text if active_prompt else ''),
            )
        except Exception as e:
            logger.error(f"force_regenerate AI call failed for question {question.id}: {e}")
            return Response(
                {'error': 'AI service temporarily unavailable; existing fields left unchanged.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # The provider rotation returns a human-readable failure sentence
        # ("All AI services are temporarily unavailable...") instead of
        # raising; saving it made that sentence the official explanation.
        analysis = _usable_ai_text(analysis)
        if not analysis:
            return Response(
                {'error': 'AI service returned no usable response; existing fields left unchanged.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Map the analysis sections back to Question fields, gated by lock flags.
        # analyze_question returns a free-form markdown explanation; we
        # use the same text for both answer and explanation rather than
        # fabricating distinct placeholders.
        new_values = {}
        if not question.lock_answer:
            new_values['ai_answer'] = analysis
        if not question.lock_explanation:
            new_values['ai_explanation'] = analysis

        # ai_mnemonic stays untouched — AIService has no mnemonic entry
        # point, and silently overwriting it with placeholder text
        # previously destroyed verified content. Admins use ai_override
        # for that.
        if not question.lock_explanation and isinstance(question.textbook_references, list):
            new_values['ai_references'] = question.textbook_references

        updated_fields = list(new_values)
        verification_cleared = False
        with transaction.atomic():
            self._capture_revision_snapshot(question, request.user, reason='Before AI force-regenerate')
            content_changed = any(
                _stored_value_differs(getattr(question, field, None), value)
                for field, value in new_values.items()
            )
            for field, value in new_values.items():
                setattr(question, field, value)
            save_fields = list(updated_fields)
            # QE-03 (as generate-explanation): unreviewed AI text must not sit
            # under an earlier "Verified by Admin" badge.
            if question.is_verified_by_admin and content_changed:
                question.is_verified_by_admin = False
                question.verified_by = None
                question.verified_at = None
                save_fields += ['is_verified_by_admin', 'verified_by', 'verified_at']
                verification_cleared = True
            if save_fields:
                question.save(update_fields=save_fields + ['updated_at'])

            response_excerpt = (question.ai_explanation or question.ai_answer or '')[:500]
            QuestionAIOperationLog.objects.create(
                question=question,
                operation_type='regenerate',
                provider='aiservice',
                prompt_version=active_prompt,
                tokens_used=max(1, len(analysis) // 4),
                response_excerpt=response_excerpt,
                created_by=request.user,
            )

        return Response({
            'message': (
                'AI regeneration completed. The earlier "Verified by Admin" mark was removed: '
                'review the new text and verify again.'
                if verification_cleared else
                'AI regeneration completed'
            ),
            'id': question.id,
            'lock_answer': question.lock_answer,
            'lock_explanation': question.lock_explanation,
            'updated_fields': updated_fields,
            'verification_cleared': verification_cleared,
            'active_prompt_version': active_prompt.id if active_prompt else None,
        })

    @action(detail=False, methods=['get', 'post'], url_path='ai-prompt-versions')
    def ai_prompt_versions(self, request):
        if request.method == 'GET':
            versions = AdminAIPromptVersion.objects.select_related('created_by').all()
            serializer = AdminAIPromptVersionSerializer(versions, many=True)
            return Response(serializer.data)

        name = (request.data.get('name') or '').strip()
        prompt_text = (request.data.get('prompt_text') or '').strip()
        activate = bool(request.data.get('activate', True))

        if not name or not prompt_text:
            return Response({'error': 'name and prompt_text are required'}, status=status.HTTP_400_BAD_REQUEST)

        if activate:
            AdminAIPromptVersion.objects.filter(is_active=True).update(is_active=False)

        version = AdminAIPromptVersion.objects.create(
            name=name,
            prompt_text=prompt_text,
            is_active=activate,
            created_by=request.user,
        )
        serializer = AdminAIPromptVersionSerializer(version)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path=r'ai-prompt-versions/(?P<version_id>[^/.]+)/activate')
    def ai_prompt_activate(self, request, version_id=None):
        try:
            version = AdminAIPromptVersion.objects.get(pk=version_id)
        except AdminAIPromptVersion.DoesNotExist:
            return Response({'error': 'Prompt version not found'}, status=status.HTTP_404_NOT_FOUND)

        AdminAIPromptVersion.objects.filter(is_active=True).exclude(pk=version.id).update(is_active=False)
        version.is_active = True
        version.save(update_fields=['is_active'])
        serializer = AdminAIPromptVersionSerializer(version)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='ai-timeline')
    def ai_timeline(self, request, pk=None):
        question = self.get_object()
        logs = question.ai_operation_logs.select_related('created_by', 'prompt_version').all()[:50]
        serializer = QuestionAIOperationLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='duplicate')
    def duplicate(self, request, pk=None):
        """Create a duplicate of the selected question."""
        question = self.get_object()
        # Tombstone guard: an admin can no longer resurrect a previously-removed
        # question by duplicating it. Restore via unremove_from_bank first.
        if _pre_check_remove(question.question_text, where='questions.views.duplicate'):
            return Response(
                {'error': 'Stem matches a previously-removed question; un-remove first.'},
                status=status.HTTP_409_CONFLICT,
            )
        duplicate_stem = f"{question.question_text}\n\n[Duplicate of Q#{question.id}]"
        duplicate_question = Question.objects.create(
            question_text=duplicate_stem,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_answer=question.correct_answer,
            year=question.year,
            subject=question.subject,
            topic=question.topic,
            difficulty=question.difficulty,
            concept_tags=question.concept_tags,
            concept_id=question.concept_id,
            explanation=question.explanation,
            concept_explanation=question.concept_explanation,
            mnemonic=question.mnemonic,
            book_name=question.book_name,
            chapter=question.chapter,
            page_number=question.page_number,
            reference_text=question.reference_text,
            paper=question.paper,
            source=question.source,
            exam_source=question.exam_source,
            times_asked=question.times_asked,
            textbook_references=question.textbook_references,
            learning_technique=question.learning_technique,
            shortcut_tip=question.shortcut_tip,
            concept_keywords=question.concept_keywords,
            ai_explanation=question.ai_explanation,
            is_verified_by_admin=False,
            verified_by=None,
            verified_at=None,
            verified_note='',
            is_active=True,
        )
        serializer = QuestionDetailSerializer(duplicate_question, context={'request': request})
        return Response({'message': 'Question duplicated', 'question': serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='related-pyqs')
    def link_related(self, request, pk=None):
        question = self.get_object()
        related_ids = self._parse_related_ids(request.data.get('related_ids', []))
        related_qs = Question.objects.filter(id__in=related_ids).exclude(id=question.id)
        question.similar_questions.set(related_qs)
        return Response({'message': 'Related PYQs updated', 'id': question.id, 'related_ids': list(related_qs.values_list('id', flat=True))})

    @action(detail=True, methods=['patch'], url_path='concept-id')
    def set_concept_id(self, request, pk=None):
        question = self.get_object()
        concept_id = str(request.data.get('concept_id', '') or '').strip()
        question.concept_id = concept_id
        question.save(update_fields=['concept_id'])
        return Response({'message': 'Concept ID updated', 'id': question.id, 'concept_id': question.concept_id})

    @action(detail=True, methods=['patch'], url_path='reference')
    def update_reference(self, request, pk=None):
        question = self.get_object()
        fields = []
        for key in ['book_name', 'chapter', 'page_number', 'reference_text', 'textbook_references']:
            if key in request.data:
                setattr(question, key, request.data.get(key))
                fields.append(key)
        if not fields:
            return Response({'error': 'No reference fields supplied'}, status=status.HTTP_400_BAD_REQUEST)
        question.save(update_fields=fields)
        return Response({'message': 'Textbook reference updated', 'id': question.id})

    @action(detail=True, methods=['patch'], url_path='format-fix')
    def format_fix(self, request, pk=None):
        question = self.get_object()

        question.question_text = self._normalize_question_text(question.question_text)
        question.option_a = self._normalize_option(question.option_a)
        question.option_b = self._normalize_option(question.option_b)
        question.option_c = self._normalize_option(question.option_c)
        question.option_d = self._normalize_option(question.option_d)
        question.explanation = self._normalize_field_text(question.explanation)

        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'explanation']
        question.save(update_fields=fields)
        return Response({'message': 'Formatting normalized', 'id': question.id})

    @action(detail=True, methods=['patch'], url_path='archive')
    def archive(self, request, pk=None):
        """Soft archive a question by marking it inactive."""
        question = self.get_object()
        question.is_active = False
        question.save(update_fields=['is_active'])
        return Response({'message': 'Question archived', 'id': question.id, 'is_active': False})

    @action(detail=True, methods=['patch'], url_path='unarchive')
    def unarchive(self, request, pk=None):
        """Restore a soft archived question by marking it active."""
        question = Question.objects.select_related('subject', 'topic').get(pk=pk)
        question.is_active = True
        question.save(update_fields=['is_active'])
        return Response({'message': 'Question unarchived', 'id': question.id, 'is_active': True})

    @action(detail=True, methods=['get'], url_path='revisions')
    def revisions(self, request, pk=None):
        question = self.get_object()
        rows = question.revision_snapshots.select_related('changed_by').all()[:100]
        serializer = QuestionRevisionSnapshotSerializer(rows, many=True)
        return Response({'count': len(serializer.data), 'results': serializer.data})

    @action(detail=True, methods=['get'], url_path='revisions-diff')
    def revisions_diff(self, request, pk=None):
        question = self.get_object()
        revision_id = request.query_params.get('revision_id')

        base = question.revision_snapshots.first()
        if revision_id:
            base = question.revision_snapshots.filter(id=revision_id).first()
        if not base:
            return Response({'error': 'No revision snapshot found'}, status=status.HTTP_404_NOT_FOUND)

        current = self._serialize_revision_state(question)
        before = base.snapshot or {}
        changed_fields = []
        # Only the fields the snapshot recorded: older snapshots predate the
        # AI fields, and a field they never captured is not a change.
        for key in sorted(before.keys()):
            if before.get(key) != current.get(key):
                changed_fields.append({'field': key, 'before': before.get(key), 'after': current.get(key)})

        return Response({'question_id': question.id, 'revision_id': base.id, 'changed_fields': changed_fields})

    @action(detail=True, methods=['post'], url_path='undo-last-revision')
    def undo_last_revision(self, request, pk=None):
        question = self.get_object()
        revision_id = request.data.get('revision_id')

        target = question.revision_snapshots.first()
        if revision_id:
            target = question.revision_snapshots.filter(id=revision_id).first()
        if not target:
            return Response({'error': 'No revision snapshot found'}, status=status.HTTP_404_NOT_FOUND)

        # Save current state before undo for future revert.
        self._capture_revision_snapshot(question, request.user, reason=f'Before undo to revision #{target.id}')
        self._apply_revision_state(question, target.snapshot or {})
        return Response({'message': 'Question reverted to selected revision snapshot', 'question_id': question.id, 'revision_id': target.id})

    @action(detail=True, methods=['post'], url_path='resolve-dispute')
    def resolve_dispute(self, request, pk=None):
        question = self.get_object()
        raw_answer = request.data.get('corrected_answer')
        justification = request.data.get('justification')

        if not raw_answer or not justification:
            return Response({'error': 'Both corrected_answer and justification are required.'}, status=status.HTTP_400_BAD_REQUEST)
        # Answers are compared as a single upper-case letter; storing 'b' or
        # 'Option B' marked every student wrong.
        corrected_answer = str(raw_answer).strip().upper()
        if corrected_answer.startswith('OPTION '):
            corrected_answer = corrected_answer[len('OPTION '):].strip()
        if corrected_answer not in ('A', 'B', 'C', 'D'):
            return Response({'error': 'corrected_answer must be one of A, B, C, D.'}, status=status.HTTP_400_BAD_REQUEST)

        old_answer = question.correct_answer
        with transaction.atomic():
            self._capture_revision_snapshot(
                question, request.user, reason=f'Before resolve-dispute ({old_answer} -> {corrected_answer})',
            )
            question.correct_answer = corrected_answer
            question.is_disputed = False
            # A human decision: protect it from AI regeneration, verifiers
            # (verify_answers --fix) and fixture re-imports.
            question.lock_answer = True
            question.admin_edited = True
            question.save(update_fields=['correct_answer', 'is_disputed', 'lock_answer', 'admin_edited', 'updated_at'])

        try:
            from accounts.views import create_admin_audit_log
            create_admin_audit_log(
                actor=request.user,
                action='RESOLVE_DISPUTE',
                resource_type='Question',
                resource_id=str(question.id),
                detail=f"Resolved dispute. Changed answer from {old_answer} to {corrected_answer}",
                metadata={'old_answer': old_answer, 'new_answer': corrected_answer, 'justification': justification}
            )
        except Exception as e:
            logger.error(f"Failed to log dispute resolution: {e}")

        return Response({'message': 'Dispute resolved successfully', 'new_answer': corrected_answer})

    def destroy(self, request, *args, **kwargs):
        """``DELETE /api/questions/<id>/`` -- remove from the bank (soft).

        A hard ``instance.delete()`` cascaded away every student's attempts,
        bookmarks, flashcards, notes and test responses for the question,
        wrote no RemovedQuestion tombstone (so fixture loaders recreated it)
        and 500'd on PROTECT relations (images, sources, duplicate
        clusters). DELETE now has ``remove-from-bank`` semantics: the row is
        hidden and tombstoned, history is kept, ``unremove-from-bank``
        restores it.
        """
        question = self.get_object()
        self._remove_question_from_bank(question, request.user, reason='Deleted via admin DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        # Tombstone guard: refuse to recreate an admin-removed question.
        text = serializer.validated_data.get('question_text', '') or ''
        if _pre_check_remove(text, where='questions.views.perform_create'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Stem matches a previously-removed question; un-remove first.'
            )
        self._normalize_question_payload(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        # Tombstone guard: refuse to update a question's stem to one that
        # matches an admin-removed tombstone. (A non-stem PATCH is allowed.)
        new_text = serializer.validated_data.get('question_text', None)
        if new_text is not None and _pre_check_remove(
            new_text, where='questions.views.perform_update'
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Updated stem matches a previously-removed question; un-remove first.'
            )
        # If-Match optimistic-lock check: handled in update()/partial_update() so
        # we can return a 409 Response directly. (Returning a Response from
        # perform_update is silently discarded by DRF and the save is lost.)
        self._normalize_question_payload(serializer.validated_data)
        if 'correct_answer' in serializer.validated_data:
            serializer.validated_data['lock_answer'] = True
        if 'explanation' in serializer.validated_data:
            serializer.validated_data['lock_explanation'] = True
        serializer.save()

    @staticmethod
    def _if_match_timestamp(raw):
        """The datetime an ``If-Match`` header carries, or None.

        The editor echoes ``updated_at`` exactly as DRF serialised it -- in
        ``TIME_ZONE`` (``...+05:30``) -- while the old check compared the raw
        header with ``updated_at.isoformat()`` in UTC (``...+00:00``), so
        every guarded save was a false 409. ETag-style quoting and a ``W/``
        prefix are tolerated; a naive value is read in the current zone.
        """
        from django.utils.dateparse import parse_datetime

        value = str(raw or '').strip()
        if value.upper().startswith('W/'):
            value = value[2:].strip()
        value = value.strip('"').strip()
        if not value:
            return None
        try:
            parsed = parse_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed is not None and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def _check_if_match_or_conflict(self, instance):
        """Return a 409 Response if If-Match header doesn't match instance.updated_at,
        else None. Caller is responsible for returning this Response from update()/
        partial_update() if not None.

        The header and ``updated_at`` are compared as instants, not strings
        (see ``_if_match_timestamp``)."""
        match = self.request.headers.get("If-Match")
        if not match:
            return None
        current = instance.updated_at
        expected = self._if_match_timestamp(match)
        if current is not None and expected is not None and expected == current:
            return None
        if current is not None and match.strip() == current.isoformat():
            return None
        return Response(
            {"detail": "Question was modified by another user",
             "current": QuestionDetailSerializer(instance, context={'request': self.request}).data},
            status=status.HTTP_409_CONFLICT,
        )


class QuestionFeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for students to report errors in questions.
    
    POST /questions/feedback/ — Submit feedback (any authenticated user).
    PATCH /questions/feedback/{id}/resolve/ — Admin marks feedback as correct & rewards tokens.
    """
    queryset = QuestionFeedback.objects.all()
    serializer_class = QuestionFeedbackSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [IsControlTowerAdmin()]

    def get_throttles(self):
        """Rate-limit unauthenticated feedback to prevent spam."""
        from rest_framework.throttling import AnonRateThrottle
        if self.action == 'create' and not self.request.user.is_authenticated:
            return [AnonRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            # Unauthenticated submissions are allowed (public flagging) but
            # are rate-limited via AnonRateThrottle and flagged in the
            # serializer for admin moderation.
            serializer.save()

    @action(detail=False, methods=['get'], url_path='admin-queue')
    def admin_queue(self, request):
        """Unified issue queue with impact sorting options."""
        sort = (request.query_params.get('sort') or 'most_reported').strip().lower()
        status_filter = (request.query_params.get('status') or '').strip().lower()

        queryset = QuestionFeedback.objects.select_related('question', 'user')
        if status_filter in ['new', 'in_progress', 'resolved']:
            queryset = queryset.filter(status=status_filter)

        # Counts must be DISTINCT: the questionresponse join multiplies every
        # feedback row by the question's test responses. The queue status is
        # derived from the open reports (MAX('status') compared strings, so
        # one resolved report made the whole question look "resolved").
        rows = (
            queryset
            .values('question_id', 'question__question_text', 'question__subject__name')
            .annotate(
                feedback_id=Max('id'),
                reports=Count('id', distinct=True),
                unresolved_reports=Count('id', filter=Q(is_resolved=False), distinct=True),
                in_progress_reports=Count('id', filter=Q(is_resolved=False, status='in_progress'), distinct=True),
                latest_created_at=Max('created_at'),
                attempts=Count('question__questionresponse', distinct=True),
                correct=Count('question__questionresponse', filter=Q(question__questionresponse__is_correct=True), distinct=True),
            )
            .annotate(queue_status=Case(
                When(unresolved_reports=0, then=Value('resolved')),
                When(in_progress_reports__gt=0, then=Value('in_progress')),
                default=Value('new'),
            ))
            .annotate(accuracy=(F('correct') * 100.0) / (F('attempts') + 0.0001))
            .annotate(impact_score=F('reports') * 3 + F('attempts') * 0.2 + (100.0 - F('accuracy')))
        )

        if sort == 'most_attempted':
            rows = rows.order_by('-attempts', '-reports', '-latest_created_at')
        elif sort == 'highest_impact':
            rows = rows.order_by('-impact_score', '-reports', '-latest_created_at')
        else:
            rows = rows.order_by('-reports', '-latest_created_at')

        results = []
        for row in rows[:200]:
            row = dict(row)
            # ``status`` cannot be the annotation name (it clashes with the
            # model field); keep the key the admin UI reads.
            row['status'] = row.pop('queue_status')
            row.pop('in_progress_reports', None)
            results.append(row)
        return Response({'count': len(results), 'results': results})

    _REWARD_NOTE_PREFIX = 'Reward for accepted feedback #'

    @classmethod
    def _rewarded_feedback_q(cls, feedback_ids):
        q = Q()
        for fid in feedback_ids:
            q |= Q(note__startswith=f'{cls._REWARD_NOTE_PREFIX}{fid}:')
        return q

    def _reward_already_paid(self, feedback) -> bool:
        """True when this reporter was already rewarded for a report on the
        same question (the reward transaction is the durable marker)."""
        from accounts.models import TokenTransaction
        if not feedback.user_id:
            return False
        sibling_ids = list(
            QuestionFeedback.objects.filter(user_id=feedback.user_id, question_id=feedback.question_id)
            .values_list('id', flat=True)[:100]
        ) or [feedback.id]
        return TokenTransaction.objects.filter(
            self._rewarded_feedback_q(sibling_ids),
            user_id=feedback.user_id, transaction_type='feedback_reward',
        ).exists()

    def _pay_feedback_reward(self, feedback) -> int:
        """Pay the "+N tokens for accepted feedback" reward at most once per
        reporter per question -- idempotent across both resolve paths,
        re-resolves after a status toggle and double clicks (callers hold
        row locks on the reports)."""
        if not feedback.user_id or self._reward_already_paid(feedback):
            return 0
        from accounts.models import TokenBalance, TokenConfig, TokenTransaction
        reward = TokenConfig.get_config().feedback_reward
        balance, _ = TokenBalance.objects.get_or_create(user_id=feedback.user_id)
        balance.add_feedback_credit(reward)
        TokenTransaction.objects.create(
            user_id=feedback.user_id,
            transaction_type='feedback_reward',
            amount=reward,
            note=f'{self._REWARD_NOTE_PREFIX}{feedback.id}: {feedback.get_category_display()}',
        )
        return reward

    def _resolve_question_reports(self, feedback, admin, note: str = '', notify: bool = False) -> dict:
        """Resolve ``feedback`` and every other open report on the same
        question, paying each reporter once (and e-mailing them when
        ``notify``). Returns {report_id: tokens}."""
        now = timezone.now()
        paid = {}
        with transaction.atomic():
            # of=('self',): PostgreSQL rejects FOR UPDATE on the nullable
            # side of the outer join select_related('user') adds.
            reports = list(
                QuestionFeedback.objects.select_for_update(of=('self',))
                .filter(Q(pk=feedback.pk) | Q(question_id=feedback.question_id, is_resolved=False))
                .select_related('user')
                .order_by('id')
            )
            for report in reports:
                if not report.is_resolved or report.status != 'resolved':
                    report.status = 'resolved'
                    report.is_resolved = True
                    report.resolved_by = admin
                    report.resolved_at = now
                    if note:
                        report.resolution_note = note
                    report.save(update_fields=['status', 'is_resolved', 'resolved_by', 'resolved_at', 'resolution_note'])
                tokens = self._pay_feedback_reward(report)
                if tokens:
                    paid[report.id] = tokens
                if notify and not report.notified_user and self._notify_reporter(report, tokens):
                    report.notified_user = True
                    report.save(update_fields=['notified_user'])
        return paid

    @staticmethod
    def _notify_reporter(report, tokens: int = 0) -> bool:
        """E-mail the reporter that their report was resolved (sent after
        commit, off the request thread). Returns False when there is nobody
        to notify -- ``notified_user`` used to be set although only a log
        line was written."""
        email = (getattr(report.user, 'email', '') or '').strip() if report.user_id else ''
        if not email:
            return False
        from django.core.mail import send_mail
        import threading
        lines = [
            f'Thanks for reporting an issue with question #{report.question_id}.',
            'Our team has reviewed and resolved it.',
        ]
        if report.resolution_note:
            lines.append(f'Note from the reviewer: {report.resolution_note}')
        if tokens:
            lines.append(f'{tokens} bonus AI tokens have been added to your account.')
        message = '\n\n'.join(lines)
        subject = f'Your report on question #{report.question_id} was resolved'

        def _send():
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            except Exception:  # pragma: no cover - mail backend hiccup
                logger.warning('Feedback notification e-mail failed (feedback_id=%s)', report.id)

        transaction.on_commit(lambda: threading.Thread(target=_send, daemon=True).start())
        return True

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        feedback = self.get_object()
        new_status = (request.data.get('status') or '').strip().lower()
        note = request.data.get('resolution_note', '') or ''

        if new_status not in ['new', 'in_progress', 'resolved']:
            return Response({'error': "status must be one of: new, in_progress, resolved"}, status=status.HTTP_400_BAD_REQUEST)

        raw_notify = request.data.get('notify_user', False)
        notify_user = raw_notify if isinstance(raw_notify, bool) else (
            str(raw_notify).strip().lower() in ('1', 'true', 'yes', 'on')
        )

        if new_status == 'resolved':
            # The queue acts per question: resolve all of its open reports,
            # pay the advertised reward (this path never paid before) and
            # notify the reporters when asked.
            self._resolve_question_reports(feedback, request.user, note=note, notify=notify_user)
            feedback.refresh_from_db()
        else:
            feedback.status = new_status
            feedback.is_resolved = False
            feedback.resolution_note = note or feedback.resolution_note
            feedback.save(update_fields=['status', 'is_resolved', 'resolution_note'])

        return Response(QuestionFeedbackSerializer(feedback, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='resolve')
    def resolve(self, request, pk=None):
        """
        Admin action: Mark feedback as resolved/correct.
        If the feedback was from a registered user, reward them with token credits.
        """
        feedback = self.get_object()
        # A report resolved through the queue before rewards were paid there
        # can still be resolved here once to pay its reporter.
        if feedback.is_resolved and (not feedback.user_id or self._reward_already_paid(feedback)):
            return Response({'message': 'Already resolved'}, status=400)

        paid = self._resolve_question_reports(feedback, request.user)
        own = paid.get(feedback.id, 0)
        if feedback.user_id and own:
            return Response({
                'message': f'Feedback resolved. User {feedback.user.username} rewarded {own} tokens.',
                'rewarded_user': feedback.user.username,
                'tokens_rewarded': own,
            })
        if feedback.user_id:
            return Response({'message': 'Feedback resolved (reporter was already rewarded for this question).'})
        return Response({'message': 'Feedback resolved (no user to reward).'})


#: Thread order (``Discussion.Meta.ordering`` plus a unique tie-break). The
#: reply-count annotation makes the query a GROUP BY, and Django ignores
#: ``Meta.ordering`` there, so it must be explicit: pinned threads first,
#: and a stable order so pages never repeat or skip a thread.
DISCUSSION_THREAD_ORDER = ('-is_pinned', '-upvotes', '-created_at', '-id')
#: Replies read top to bottom (the thread UI appends new replies at the end).
DISCUSSION_REPLY_ORDER = ('created_at', 'id')


def _discussion_queryset(user):
    """Discussions with reply counts and the viewer's own vote preloaded
    (the serializer used to run two queries per thread).

    Threads discuss the answer ("C, because ..."), so they follow the
    question-bank entitlement rule (``user_can_view_answer``): a viewer who
    is not entitled to a question's answer -- a free account outside the
    free showcase, or any scholarship-challenge question -- sees only their
    own posts on it. Admins / staff and premium subscribers see everything.
    """
    from django.db.models import Prefetch
    queryset = Discussion.objects.all()
    if not (_is_staff_user(user) or _is_premium(user)):
        queryset = queryset.filter(
            Q(Exists(free_showcase_rows().filter(question_id=OuterRef('question_id'))))
            | Q(user_id=getattr(user, 'pk', None))
        )
    return (
        queryset.select_related('user', 'question')
        .annotate(reply_count_annotated=Count('replies', distinct=True))
        .prefetch_related(Prefetch(
            'votes', queryset=DiscussionVote.objects.filter(user=user), to_attr='viewer_votes',
        ))
        .order_by(*DISCUSSION_THREAD_ORDER)
    )


class DiscussionListCreateView(generics.ListCreateAPIView):
    """List discussions for a question or create a new one."""
    serializer_class = DiscussionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        question_id = self.request.query_params.get('question')
        qs = _discussion_queryset(self.request.user).filter(parent__isnull=True)
        if question_id:
            try:
                qs = qs.filter(question_id=int(question_id))
            except (TypeError, ValueError):
                return qs.none()
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DiscussionRepliesView(generics.ListAPIView):
    """List replies to a discussion."""
    serializer_class = DiscussionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            _discussion_queryset(self.request.user)
            .filter(parent_id=self.kwargs['pk'])
            .order_by(*DISCUSSION_REPLY_ORDER)
        )


class DiscussionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """``GET/PATCH/DELETE /api/questions/discussions/<pk>/``.

    Authors may edit the text of (PATCH) or delete their own posts; admins /
    staff may delete any post (moderation). Before this there was no way to
    remove an abusive or wrong post without shell access.
    """
    serializer_class = DiscussionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return _discussion_queryset(self.request.user)

    def perform_update(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        if serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied('You can only edit your own posts.')
        # Only the text is editable; a post cannot be moved to another
        # question or thread.
        for key in list(serializer.validated_data):
            if key != 'text':
                serializer.validated_data.pop(key)
        serializer.save()

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        if instance.user_id != self.request.user.id and not _is_staff_user(self.request.user):
            raise PermissionDenied('You can only delete your own posts.')
        instance.delete()


class DiscussionVoteView(generics.GenericAPIView):
    """Upvote or downvote a discussion."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        vote_type = request.data.get('vote_type')
        if vote_type not in ('up', 'down'):
            return Response({'error': 'vote_type must be "up" or "down"'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            try:
                discussion = Discussion.objects.select_for_update().get(pk=pk)
            except Discussion.DoesNotExist:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

            existing = DiscussionVote.objects.filter(user=request.user, discussion=discussion).first()
            if existing:
                if existing.vote_type == vote_type:
                    if vote_type == 'up':
                        Discussion.objects.filter(pk=discussion.pk).update(upvotes=Greatest(F('upvotes') - 1, Value(0)))
                    else:
                        Discussion.objects.filter(pk=discussion.pk).update(downvotes=Greatest(F('downvotes') - 1, Value(0)))
                    existing.delete()
                    discussion.refresh_from_db(fields=['upvotes', 'downvotes'])
                    return Response({'status': 'vote_removed', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})

                if vote_type == 'up':
                    Discussion.objects.filter(pk=discussion.pk).update(
                        upvotes=F('upvotes') + 1,
                        downvotes=Greatest(F('downvotes') - 1, Value(0)),
                    )
                else:
                    Discussion.objects.filter(pk=discussion.pk).update(
                        downvotes=F('downvotes') + 1,
                        upvotes=Greatest(F('upvotes') - 1, Value(0)),
                    )
                existing.vote_type = vote_type
                existing.save(update_fields=['vote_type'])
                discussion.refresh_from_db(fields=['upvotes', 'downvotes'])
                return Response({'status': 'vote_switched', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})

            # No existing vote — create one. On Postgres the discussion
            # row lock above doesn't cover DiscussionVote, so two rapid
            # POSTs from the same user can both reach this line. The
            # unique_together (user, discussion) constraint on the model
            # will reject the second one; catch the IntegrityError and
            # re-enter the "existing" branch so the second request is
            # idempotent (toggle off / switch) instead of 500-ing.
            try:
                DiscussionVote.objects.create(user=request.user, discussion=discussion, vote_type=vote_type)
            except IntegrityError:
                existing = DiscussionVote.objects.get(user=request.user, discussion=discussion)
                # Recurse via the toggle/switch paths. We re-evaluate
                # vote_type against the row that just got committed; if
                # it matches, treat as a no-op so the second request
                # doesn't double-count.
                if existing.vote_type == vote_type:
                    discussion.refresh_from_db(fields=['upvotes', 'downvotes'])
                    return Response({'status': 'already_voted', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})
                if vote_type == 'up':
                    Discussion.objects.filter(pk=discussion.pk).update(
                        upvotes=F('upvotes') + 1,
                        downvotes=Greatest(F('downvotes') - 1, Value(0)),
                    )
                else:
                    Discussion.objects.filter(pk=discussion.pk).update(
                        downvotes=F('downvotes') + 1,
                        upvotes=Greatest(F('upvotes') - 1, Value(0)),
                    )
                existing.vote_type = vote_type
                existing.save(update_fields=['vote_type'])
                discussion.refresh_from_db(fields=['upvotes', 'downvotes'])
                return Response({'status': 'vote_switched', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})

            if vote_type == 'up':
                Discussion.objects.filter(pk=discussion.pk).update(upvotes=F('upvotes') + 1)
            else:
                Discussion.objects.filter(pk=discussion.pk).update(downvotes=F('downvotes') + 1)
            discussion.refresh_from_db(fields=['upvotes', 'downvotes'])
            return Response({'status': 'voted', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})


class NoteListCreateView(generics.ListCreateAPIView):
    """List and create personal notes."""
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Note.objects.filter(user=self.request.user)
        question_id = self.request.query_params.get('question')
        topic_id = self.request.query_params.get('topic')
        if question_id:
            qs = qs.filter(question_id=question_id)
        if topic_id:
            qs = qs.filter(topic_id=topic_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a note."""
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)


class FlashcardListCreateView(generics.ListCreateAPIView):
    """List and create flashcards."""
    serializer_class = FlashcardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Flashcard.objects.filter(user=self.request.user).select_related('subject')
        subject_id = self.request.query_params.get('subject')
        due = self.request.query_params.get('due')
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        if due == 'true':
            from django.utils import timezone
            from django.db.models import Q
            qs = qs.filter(Q(next_review__lte=timezone.now()) | Q(next_review__isnull=True))
        return qs

    def perform_create(self, serializer):
        from django.utils import timezone
        serializer.save(user=self.request.user, next_review=timezone.now())


class FlashcardDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a flashcard."""
    serializer_class = FlashcardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Flashcard.objects.filter(user=self.request.user).select_related('subject')


class FlashcardReviewView(generics.GenericAPIView):
    """Submit a review result for spaced repetition scheduling."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        quality = request.data.get('quality', 3)
        if not isinstance(quality, int) or quality < 0 or quality > 5:
            return Response({'error': 'quality must be 0-5'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            card = Flashcard.objects.get(pk=pk, user=request.user)
        except Flashcard.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        card.schedule_next_review(quality)
        return Response(FlashcardSerializer(card).data)


class FlashcardAnalyticsView(generics.GenericAPIView):
    """Spaced-repetition stats over ALL of the user's cards (one query).

    * ``retention_rate`` = 1 - lapses / total_reviews over every review the
      user submitted (``Flashcard.total_reviews`` / ``lapses``); ``null``
      until the first review. It used to be the share of cards with
      ``ease_factor >= 2.5`` -- which every brand-new card has.
    * ``reviewed_cards``: cards with at least one review on record (cards
      reviewed before the counters existed count through ``review_count``).
    * ``due_today``: due now or never scheduled; ``cards_due_today`` is the
      older name of the same number.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Avg

        now = timezone.now()
        aggs = Flashcard.objects.filter(user=request.user).aggregate(
            total=Count('id'),
            due=Count('id', filter=Q(next_review__lte=now) | Q(next_review__isnull=True)),
            reviewed=Count('id', filter=Q(total_reviews__gt=0) | Q(review_count__gt=0)),
            reviews=Sum('total_reviews'),
            lapses=Sum('lapses'),
            avg_ease=Avg('ease_factor'),
            avg_interval=Avg('interval_days'),
            one_day=Count('id', filter=Q(interval_days__lte=1)),
            two_to_seven=Count('id', filter=Q(interval_days__range=(2, 7))),
            eight_to_thirty=Count('id', filter=Q(interval_days__range=(8, 30))),
            thirty_plus=Count('id', filter=Q(interval_days__gt=30)),
        )
        total = aggs['total'] or 0
        reviews = aggs['reviews'] or 0
        lapses = min(aggs['lapses'] or 0, reviews)
        due = aggs['due'] or 0
        return Response({
            'total_cards': total,
            'due_today': due,
            'cards_due_today': due,
            'reviewed_cards': aggs['reviewed'] or 0,
            'total_reviews': reviews,
            'lapses': lapses,
            'retention_rate': round(1 - lapses / reviews, 3) if reviews else None,
            'avg_ease_factor': round(aggs['avg_ease'] or 0, 2),
            'avg_interval': round(aggs['avg_interval'] or 0, 1),
            'interval_distribution': {
                '1_day': aggs['one_day'] or 0,
                '2_7_days': aggs['two_to_seven'] or 0,
                '8_30_days': aggs['eight_to_thirty'] or 0,
                '30_plus_days': aggs['thirty_plus'] or 0,
            } if total else {},
        })


# Fallback for ChatAssistantView when ai_engine.views has no
# MAX_AI_INPUT_CHARS (the AI Tutor's limit, 4000).
CHAT_MESSAGE_MAX_CHARS = 4000


class ChatAssistantView(APIView):
    """
    Handles unstructured queries from the Floating Ask-AI Dock.
    Passes contextual question text if provided.
    Uses the real AIService.ask_tutor() with RAG grounding.

    Same metering as the AI Tutor (``ai_engine.views.AskTutorView``): the
    'ai_tutor' scoped throttle, the free-tier daily cap and the token
    economy, with a refund when every provider failed. A context question
    is only injected when it is active and the user is entitled to its
    answer.
    """
    permission_classes = [permissions.IsAuthenticated]
    # Mirrors ai_engine.views.AITutorThrottleMixin (that module imports the
    # whole AI provider stack, which questions.views only loads lazily).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_tutor'

    UNAVAILABLE_REPLY = "AI service temporarily unavailable. Your token has been refunded. Please try again."

    def _context_for(self, request, raw_question_id) -> str:
        if raw_question_id in (None, ''):
            return ''
        try:
            question_id = int(raw_question_id)
        except (TypeError, ValueError):
            return ''
        question = Question.objects.filter(id=question_id, is_active=True).first()
        if question is None:
            return ''
        if not user_can_view_answer(request.user, question):
            # Locked question: never hand its stem + answer key to the
            # model (the reply would reveal the answer).
            return ''
        context_str = f"Context Question: {question.question_text}\n"
        context_str += f"A: {question.option_a}, B: {question.option_b}, C: {question.option_c}, D: {question.option_d}\n"
        context_str += f"Correct Answer: {question.correct_answer}\n\n"
        return context_str

    def post(self, request, *args, **kwargs):
        raw_message = request.data.get('message', '')
        message = raw_message.strip() if isinstance(raw_message, str) else ''
        context_question_id = request.data.get('context_question_id')

        if not message:
            return Response({"error": "Message is required."}, status=400)

        from ai_engine import views as ai_views

        # Same input cap as the AI Tutor (ai_engine.views._required_text),
        # checked before any charge: an unbounded message went into every
        # provider prompt and the RAG query, and -- refunded when the
        # providers failed -- into the offline composer, whose term de-dupe
        # is quadratic in the message length.
        max_chars = getattr(ai_views, 'MAX_AI_INPUT_CHARS', CHAT_MESSAGE_MAX_CHARS)
        if len(message) > max_chars:
            return Response(
                {"error": f"Message is too long (max {max_chars} characters)."}, status=400,
            )

        # Same failure contract as the AI Tutor (ai_engine.views
        # ._run_text_endpoint): no outage sentence is ever handed over as the
        # assistant's reply -- a grounded offline answer (labelled, free) or
        # a 503 ``{code: 'ai_unavailable'}``.
        offline_response = getattr(ai_views, '_offline_text_response', None)
        offline_mode = getattr(ai_views, 'ai_offline_mode', None)
        if offline_response is not None and offline_mode is not None and offline_mode():
            return offline_response(request, message, key='reply', reason=ai_views.REASON_OFFLINE_MODE)

        # Free-tier daily AI Tutor cap (premium / admin bypass) + 1 token,
        # exactly like AskTutorView. Newer ai_engine builds bundle both in
        # ``_charge_ai_call`` / ``_refund_ai_call`` (which also give the
        # free daily slot back on failure).
        charge = getattr(ai_views, '_charge_ai_call', None)
        if charge is not None:
            charge_err = charge(request, amount=1, freemium=True)
            if charge_err is not None:
                return charge_err

            def refund():
                ai_views._refund_ai_call(request, amount=1)
        else:  # pragma: no cover - older ai_engine.views
            freemium_err = ai_views._check_freemium_ai_quota(request)
            if freemium_err is not None:
                return freemium_err
            ok, err = ai_views.consume_ai_token(request)
            if not ok:
                return err

            def refund():
                ai_views.refund_ai_token(request)

        context_str = self._context_for(request, context_question_id)

        from ai_engine import services as ai_services
        unavailable_error = getattr(ai_services, 'AIUnavailable', None)
        try:
            service = ai_services.AIService()
            reply = service.ask_tutor(message, context_str)
        except Exception as e:
            refund()
            if offline_response is not None and unavailable_error is not None and isinstance(e, unavailable_error):
                reason = (ai_views.REASON_OFFLINE_MODE if getattr(e, 'offline', False)
                          else ai_views.REASON_PROVIDERS_DOWN)
                return offline_response(request, message, key='reply', reason=reason,
                                        passages=getattr(e, 'passages', None))
            logger.error(f"ChatAssistant AI failed: {e}")
            return self._unavailable(ai_views)
        # Older provider rotations return a failure sentence instead of
        # raising; treat it like an exception so the token is refunded.
        if not _usable_ai_text(reply):
            refund()
            if offline_response is not None:
                return offline_response(request, message, key='reply', reason=ai_views.REASON_PROVIDERS_DOWN)
            return self._unavailable(ai_views)
        return Response({"reply": reply})

    def _unavailable(self, ai_views):
        make = getattr(ai_views, '_ai_unavailable_response', None)
        if make is not None:
            return make()
        return Response({"reply": self.UNAVAILABLE_REPLY})  # pragma: no cover - older ai_engine.views


_SUPABASE_PUBLIC_URL_RE = re.compile(r'^https://[^/]+\.supabase\.co/storage/v1/object/public/(.+)$')


def _supabase_storage_mirror_path(url: str):
    """Map a Supabase public-storage URL onto ``SUPABASE_STORAGE_MIRROR_DIR``.

    Returns an absolute file path inside the mirror, or None (mirror not
    configured, URL not a Supabase public URL, traversal attempt, or file
    missing). Used for local development on a restored storage backup.
    """
    from django.conf import settings as _dj_settings

    mirror = getattr(_dj_settings, 'SUPABASE_STORAGE_MIRROR_DIR', '')
    if not mirror or not url:
        return None
    match = _SUPABASE_PUBLIC_URL_RE.match(url.split('?', 1)[0])
    if not match:
        return None
    parts = [p for p in match.group(1).split('/') if p]
    if not parts or any(p in ('.', '..') for p in parts):
        return None
    root = os.path.realpath(mirror)
    candidate = os.path.realpath(os.path.join(root, *parts))
    if not candidate.startswith(root + os.sep):
        return None
    return candidate if os.path.isfile(candidate) else None


def _image_serve_allowed(request, img) -> bool:
    """Stem figures: always. Explanation figures (runtime role): with a
    valid signed token for this image id, or when the caller's own
    credentials (an API client's Authorization header, a staff session)
    make it entitled to the question's answer. See QuestionImageServeView."""
    question = img.question
    if resolve_runtime_image_role(question, img) != "explanation":
        return True
    if image_token_is_valid(img.id, request.query_params.get(IMAGE_TOKEN_PARAM)):
        return True
    return user_can_view_answer(getattr(request, "user", None), question)


class QuestionImageServeView(APIView):
    """Serve a `QuestionImage.file` binary through Django.

    **Why this exists**: `/media/recall_images/...` 404s in production
    because (a) Django's `static(MEDIA_URL, ...)` helper is gated behind
    `DEBUG=True` in `crack_cms/urls.py`, and (b) gunicorn does not serve
    user uploads out of the box. The render container doesn't ship
    3,000+ PNG files in git either, so the file physically exists on the
    origin but the URL is unreachable.

    **What this does**: streams the file from whichever storage backend
    is configured (FileSystemStorage locally; will transparently work
    with S3 / DigitalOcean Spaces once `DEFAULT_FILE_STORAGE` is
    swapped).

    **URL contract**:
        GET /api/questions/images/<int:image_id>/serve/?w=480&q=72

    Optional query params (best-effort, ignored if Pillow unavailable):
      - `w` : max width in px (preserves aspect ratio, never upscales)
      - `q` : JPEG quality 1-100 (default 80)
    and `t`, the signed token an explanation figure needs (see below).

    Returns 404 if the row is missing or inactive. Returns 200 with the
    binary when the file exists locally. Returns 503 with a clear JSON
    error if the file is missing on disk (the 3,496-row DB has only 257
    files locally; remote prod may have a different mix).

    **Auth model** (2026-07-30): this endpoint is **public** (`AllowAny`).
    The original commit gated it behind `IsAuthenticated` because the
    question bank is paywalled, but that broke every image-bearing
    question on the live site: HTML `<img src>` tags cannot send a
    custom `Authorization: Bearer ...` header, so even logged-in users
    were getting 403 from every inline image. The question text and
    metadata returned by `QuestionViewSet` are themselves public via
    the same API, so gating only the binary image bytes made the
    implementation inconsistent with the rest of the contract. Stem
    figures stay public, like the stem text.

    **Explanation figures** (runtime role 'explanation': stored role, or
    referenced only from the explanation / concept explanation / mnemonic,
    see ``resolve_runtime_image_role``) belong to the answer. Image ids are
    sequential, so they are served only with a valid signed ``?t=`` token
    for that image id (``questions.image_access``; payloads built for a
    viewer entitled to the answer carry it in the image URL) or to a caller
    whose own credentials make it entitled (``user_can_view_answer``).
    Anyone else gets 403 ``{"code": "image_token_required"}``.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, image_id: int):
        img = (
            QuestionImage.objects.filter(id=image_id, is_active=True)
            .select_related("question")
            .only(
                "id", "question", "file", "url", "mime", "width", "height", "role",
                # resolve_runtime_image_role + user_can_view_answer
                "question__question_text", "question__explanation",
                "question__concept_explanation", "question__mnemonic",
                "question__is_scholarship_eligible",
            )
            .first()
        )
        if not img:
            raise Http404("Question image not found")
        if not _image_serve_allowed(request, img):
            return Response(
                {
                    "code": "image_token_required",
                    "detail": "Explanation figures load through the link in the question data; "
                              "reload the question for a fresh link.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # 2026-07-27 fallback chain:
        #   1. `img.file` (ImageField) — recall imports ship bytes here.
        #   2. `img.url` starting with /media/ — recall path failed to
        #      hydrate the ImageField but the row still points at MEDIA_ROOT.
        #   3. `img.url` is an absolute http(s) URL (Supabase public URL for
        #      admin uploads) — proxy the request as a 302 redirect so the
        #      browser fetches directly from Supabase instead of round-tripping
        #      through Django. Saves bandwidth and avoids needing to re-stream.
        serve_path = None
        if img.file:
            try:
                serve_path = img.file.path
            except (ValueError, NotImplementedError):
                serve_path = None
        if not serve_path and img.url and img.url.startswith("/media/"):
            from django.conf import settings as _dj_settings
            rel = img.url[len("/media/"):]
            media_root = os.path.realpath(_dj_settings.MEDIA_ROOT)
            candidate = os.path.realpath(os.path.join(media_root, rel))
            # Never leave MEDIA_ROOT (a stored "/media/../.." URL).
            if candidate.startswith(media_root + os.sep) and os.path.isfile(candidate):
                serve_path = candidate
        if not serve_path and img.url and img.url.startswith(("http://", "https://")):
            serve_path = _supabase_storage_mirror_path(img.url)
            if not serve_path:
                from django.http import HttpResponseRedirect
                return _harden_image_response(HttpResponseRedirect(img.url))
        if not serve_path:
            raise Http404("Question image not found")

        try:
            f = open(serve_path, "rb")
        except (FileNotFoundError, OSError, ValueError):
            logger.warning("QuestionImage #%s file missing on disk", image_id)
            return Response(
                {
                    "error": "image file missing on server",
                    "image_id": image_id,
                    "hint": "re-upload via admin or importer",
                },
                status=503,
            )

        # Only real raster bytes are served inline, typed from the content
        # (not the stored ``mime``). Anything else -- e.g. an SVG from an
        # older import, which a browser would run as an active document on
        # the API origin -- is sent as an opaque download. Every response
        # also carries ``Content-Security-Policy: default-src 'none'; sandbox``
        # and ``nosniff`` (see ``_harden_image_response``).
        try:
            head = f.read(16)
            f.seek(0)
        except (OSError, ValueError):
            head = b''
        raster_mime = _sniff_raster_mime(head)

        # Best-effort resize via Pillow if requested. Failing open (serve
        # the raw bytes) is acceptable — the player still renders.
        w_param = request.query_params.get("w")
        q_param = request.query_params.get("q")
        if raster_mime and (w_param or q_param):
            raw = None
            try:
                from io import BytesIO
                from PIL import Image

                try:
                    target_w = max(1, min(int(w_param), 4096)) if w_param else None
                    quality = max(1, min(int(q_param), 100)) if q_param else 80
                except ValueError:
                    target_w, quality = None, 80

                raw = f.read()
                f.close()
                pil_img = Image.open(BytesIO(raw))
                if target_w and pil_img.width > target_w:
                    ratio = target_w / float(pil_img.width)
                    new_size = (target_w, max(1, int(pil_img.height * ratio)))
                    pil_img = pil_img.resize(new_size, Image.LANCZOS)
                if raster_mime == "image/jpeg" or raster_mime == "image/png" and target_w:
                    buf = BytesIO()
                    save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
                    pil_img = pil_img.convert("RGB")
                    pil_img.save(buf, **save_kwargs)
                    out_mime = "image/jpeg"
                else:
                    buf = BytesIO()
                    pil_img.save(buf, format="PNG", optimize=True)
                    out_mime = "image/png"
                buf.seek(0)
                resp = HttpResponse(buf.read(), content_type=out_mime)
                resp["Content-Length"] = buf.tell()
                resp["Cache-Control"] = "private, max-age=3600"
                return _harden_image_response(resp)
            except ImportError:
                # Pillow not installed — fall through to raw bytes
                pass
            except Exception as resize_exc:  # noqa: BLE001
                logger.warning("Image resize failed for #%s: %s", image_id, resize_exc)
            if raw is not None:
                # The file was already read (and closed): serve those bytes.
                resp = HttpResponse(raw, content_type=raster_mime)
                resp["Cache-Control"] = "private, max-age=3600"
                return _harden_image_response(resp)

        # Raw passthrough
        try:
            f.seek(0)
        except Exception:  # noqa: BLE001
            pass
        if raster_mime:
            resp = FileResponse(f, content_type=raster_mime)
        else:
            logger.info("QuestionImage #%s (stored mime %s) is not a PNG/JPEG/GIF/WebP; sent as a download",
                        image_id, img.mime or 'unknown')
            resp = FileResponse(
                f, content_type="application/octet-stream",
                as_attachment=True, filename=f"question-image-{image_id}",
            )
        resp["Cache-Control"] = "private, max-age=3600"
        return _harden_image_response(resp)


#: Raster formats the image endpoint serves inline (magic bytes -> type).
_RASTER_SIGNATURES = (
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
)
#: Image responses are inert documents even when opened directly.
IMAGE_RESPONSE_CSP = "default-src 'none'; sandbox"


def _sniff_raster_mime(head: bytes):
    """'image/png' / 'image/jpeg' / 'image/gif' / 'image/webp' from the first
    bytes of a file, or None (SVG, HTML, anything unknown)."""
    head = head or b''
    for signature, mime in _RASTER_SIGNATURES:
        if head.startswith(signature):
            return mime
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _harden_image_response(resp):
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = IMAGE_RESPONSE_CSP
    return resp


from .image_upload import upload_image_to_supabase
from .serializers_question_image import QuestionImageSerializer


class QuestionImageViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for `QuestionImage`. Supports direct upload via
    `POST /questions/images/` with multipart `question_id` + `file`.

    **Auth**: `IsAdminUser`. Non-admins get 403.
    **Optimistic lock**: PATCH / DELETE accept `If-Match: <updated_at>`
    on the parent Question to prevent concurrent overwrites — but since
    images live on their own resource, image PATCH uses image
    `updated_at` via the same `If-Match` header.
    """
    queryset = QuestionImage.objects.all().order_by("-id")
    serializer_class = QuestionImageSerializer
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        question_id = request.data.get("question_id")
        file_obj = request.FILES.get("file")
        if not question_id or not file_obj:
            return Response(
                {"detail": "question_id and file are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            question_id_int = int(question_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "question_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Optional `role` from the admin editor. Defaults to 'illustration'
        # inside the helper; we pass through whatever the admin sent (after
        # validating it against the choice set) so uploads from the
        # explanation / concept editor get the correct role. This is the
        # upload-end half of the explanation-image-in-stem bug fix; the
        # read-end half lives in the question serializer's `stem_images`
        # getter.
        from .image_upload import ALLOWED_ROLES
        requested_role = request.data.get("role")
        if requested_role is not None and requested_role not in ALLOWED_ROLES:
            return Response(
                {"detail": (
                    f"Unsupported role {requested_role!r}. Allowed: "
                    f"{sorted(ALLOWED_ROLES)}"
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Type from the bytes, not the client's Content-Type: an SVG / HTML
        # file declared as image/png used to be stored as-is.
        from django.core.exceptions import ValidationError as DjangoValidationError
        from accounts.upload_validation import validate_uploaded_file
        from .image_upload import MAX_BYTES as IMAGE_MAX_BYTES
        try:
            detected_type = validate_uploaded_file(file_obj, allowed_types={"image"}, max_bytes=IMAGE_MAX_BYTES)
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            uploaded = upload_image_to_supabase(
                file_obj=file_obj,
                question_id=question_id_int,
                content_type=detected_type,
                original_filename=file_obj.name or "image.png",
                role=requested_role,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            logger.error("Image upload failed: %s", exc)
            return Response(
                {"detail": "Upload failed", "hint": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        row = QuestionImage.objects.get(id=uploaded.id)
        return Response(
            QuestionImageSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='reorder')
    def reorder(self, request, pk=None):
        """Reorder images within a question. Body: `{question_id, new_index_in_page}`."""
        image = self.get_object()
        new_index = request.data.get("new_index_in_page")
        try:
            new_index = int(new_index)
        except (TypeError, ValueError):
            return Response({"detail": "new_index_in_page must be an integer"}, status=400)
        image.image_index_in_page = new_index
        image.save(update_fields=["image_index_in_page"])
        return Response(QuestionImageSerializer(image).data)


# ─── Topic Notes (PYQ explanation → revision notes pipeline) ──────────────────

from rest_framework.permissions import IsAdminUser

class TopicNoteViewSet(viewsets.ModelViewSet):
    """Admin CRUD for topic-wise notes compiled from PYQ explanations.

    The notes-generation pipeline groups questions by (subject, topic, exam_type)
    and synthesizes their reviewed explanations into concise revision notes.
    This viewset exposes the resulting notes for admin editing and publishing.
    """
    queryset = TopicNote.objects.select_related('subject', 'topic', 'created_by').order_by('-updated_at')
    permission_classes = [IsControlTowerAdmin]
    serializer_class = TopicNoteSerializer
    filterset_fields = ['subject', 'topic', 'exam_type', 'is_published', 'ai_generated']
    search_fields = ['title', 'content']

    def perform_create(self, serializer):
        note = serializer.save(created_by=self.request.user)
        _refresh_topic_note_derived_fields(note)

    def perform_update(self, serializer):
        note = serializer.save()
        _refresh_topic_note_derived_fields(note)

    @action(detail=True, methods=["post"], url_path="generate")
    def generate_from_topic(self, request, pk=None):
        """Generate a note from all questions in the same topic.

        Uses the AI to synthesize explanations from questions sharing
        this note's subject + topic + exam_type into a concise note.
        """
        note = self.get_object()
        from ai_engine.services import AIService
        from questions.models import Question

        qs = Question.objects.filter(
            subject=note.subject, topic=note.topic,
            exam_type=note.exam_type, is_active=True,
        ).exclude(explanation='')[:20]

        if not qs.exists():
            return Response({'detail': 'No questions with explanations found for this topic.'}, status=400)

        explanations = []
        for q in qs:
            explanations.append(f"Q: {q.question_text[:200]}\nA: {q.correct_answer}\nExplanation: {q.explanation[:500]}")

        # The topic's name, not str(topic) ("<SUBJECT CODE> → <name>"): the
        # model echoes it into a note students read, and the code of the
        # loader's "Imported" bucket is "IMPORTED".
        topic_name = getattr(note.topic, 'name', '') or ''
        prompt = f"""You are a medical educator. Compile the following question explanations into concise, revision-friendly notes for the topic "{topic_name}" in {note.exam_type}.

Organize the notes as:
1. Key Concepts (core principles)
2. Important Facts (high-yield points)
3. Clinical Correlations
4. Exam Tips

Keep it concise — bullet points, not paragraphs. Focus on medically important information.

Explanations to synthesize:
{chr(10).join(explanations[:15])}

Respond with structured content in markdown format."""

        try:
            ai_service = AIService()
            content = _usable_ai_text(ai_service._call_ai(prompt, max_tokens=3000, temperature=0.3))
        except Exception:
            logger.exception('TopicNote generation failed (note=%s)', note.pk)
            content = ''
        if not content:
            return Response({'detail': 'AI generation is temporarily unavailable. Please try again shortly.'}, status=503)
        note.content = content
        note.ai_generated = True
        note.source_question_ids = [q.id for q in qs]
        note.save()
        _refresh_topic_note_derived_fields(note)
        return Response({'detail': 'Note generated.', 'content': note.content})


# ════════════════════════════════════════════════════════════════════════════
# Student Experience — Study & Gamification Views
# ════════════════════════════════════════════════════════════════════════════

# The questions-app Mistake Notebook views (list / add / detail / review /
# due / stats) were duplicates of analytics.views; the routes now live only
# under /api/analytics/mistake-notebook/ (see questions/urls.py).


class UserQuestListView(APIView):
    """List the user's quests. Today's daily quests are generated on demand
    and their progress is computed from real activity (server-side)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from questions.quest_service import ensure_daily_quests, refresh_progress

        ensure_daily_quests(request.user)
        quests = UserQuest.objects.filter(user=request.user)
        status_filter = request.query_params.get('status')
        if status_filter == 'active':
            quests = quests.filter(is_completed=False, expires_at__gt=timezone.now())
        elif status_filter == 'completed':
            quests = quests.filter(is_completed=True)
        elif status_filter == 'expired':
            quests = quests.filter(expires_at__lt=timezone.now(), is_completed=False)
        quests = list(quests.order_by('-quest_date', 'quest_type')[:20])
        refresh_progress(request.user, quests)
        serializer = UserQuestSerializer(quests, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a custom quest for a user (admin only)."""
        if not getattr(request.user, 'is_admin', False):
            return Response({'error': 'Admin only'}, status=403)
        serializer = UserQuestAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=serializer.validated_data.get('user') or request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserQuestDetailView(APIView):
    """Read or claim a quest. PATCH ``{"is_completed": true}`` claims it --
    the server checks progress and awards the server-defined XP once."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_object(self, request, pk):
        try:
            return UserQuest.objects.get(pk=pk, user=request.user)
        except UserQuest.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        from questions.quest_service import refresh_progress
        obj = self._get_object(request, pk)
        refresh_progress(request.user, [obj])
        return Response(UserQuestSerializer(obj).data)

    def patch(self, request, pk):
        from questions.quest_service import QuestClaimError, claim_quest

        raw = request.data.get('is_completed')
        wants_claim = raw is True or str(raw).strip().lower() in ('1', 'true', 'yes')
        if not wants_claim:
            return Response({'error': 'Only claiming a finished quest is supported.'}, status=400)
        try:
            quest = claim_quest(request.user, pk)
        except QuestClaimError as exc:
            return Response({'error': exc.message}, status=exc.status)
        return Response(UserQuestSerializer(quest).data)

    def post(self, request, pk):
        """Alias: ``POST .../<pk>/`` with no body also claims."""
        return self.patch(request, pk)

    def delete(self, request, pk):
        # Deleting a claimed daily quest would let it be regenerated and
        # claimed again for more XP, so only admins may delete.
        if not getattr(request.user, 'is_admin', False):
            return Response({'error': 'Admin only'}, status=403)
        try:
            obj = UserQuest.objects.get(pk=pk)
        except UserQuest.DoesNotExist:
            raise Http404
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestStreakView(APIView):
    """Get quest streak info."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak, _ = QuestStreak.objects.get_or_create(user=request.user)
        serializer = QuestStreakSerializer(streak)
        return Response(serializer.data)


class QuestStreakFreezeView(APIView):
    """Toggle streak freeze."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        raw = request.data.get('streak_frozen', True)
        # bool('false') is True -- the string 'false' used to freeze.
        freeze = raw if isinstance(raw, bool) else str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
        streak, _ = QuestStreak.objects.get_or_create(user=request.user)
        streak.streak_frozen = freeze
        streak.save(update_fields=['streak_frozen'])
        serializer = QuestStreakSerializer(streak)
        return Response(serializer.data)


class StudyTimeView(APIView):
    """Record and retrieve study time per subject."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = StudyTimeBreakdown.objects.filter(user=request.user)
        start = request.query_params.get('start')
        end = request.query_params.get('end')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)
        serializer = StudyTimeBreakdownSerializer(qs, many=True)
        totals = qs.values('subject').annotate(
            total_seconds=Sum('seconds'),
            total_questions=Sum('question_count'),
        )
        return Response({
            'breakdown': serializer.data,
            'totals': list(totals),
        })

    def post(self, request):
        subject_id = request.data.get('subject')
        try:
            seconds = max(0, min(int(request.data.get('seconds', 0)), 24 * 3600))
            question_count = max(0, min(int(request.data.get('question_count', 0)), 1000))
        except (TypeError, ValueError):
            return Response({'error': 'seconds and question_count must be integers'}, status=400)
        import datetime as _dt
        raw_date = request.data.get('date')
        try:
            date_str = _dt.date.fromisoformat(str(raw_date)) if raw_date else timezone.localdate()
        except ValueError:
            return Response({'error': 'date must be in YYYY-MM-DD format'}, status=400)
        if date_str > timezone.localdate():
            return Response({'error': 'date cannot be in the future'}, status=400)
        try:
            subject = Subject.objects.get(pk=int(subject_id))
        except (Subject.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'Subject not found'}, status=404)
        obj, _ = StudyTimeBreakdown.objects.get_or_create(
            user=request.user, subject=subject, date=date_str,
            defaults={'seconds': 0, 'question_count': 0},
        )
        # Atomic increments (two tabs posting at once used to lose time).
        StudyTimeBreakdown.objects.filter(pk=obj.pk).update(
            seconds=F('seconds') + seconds,
            question_count=F('question_count') + question_count,
        )
        obj.refresh_from_db(fields=['seconds', 'question_count'])
        serializer = StudyTimeBreakdownSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


def _usable_ai_text(raw) -> str:
    """Return AI output, or '' when every provider failed (the rotation
    returns a human-readable failure sentence that must never be saved).
    Single implementation: ``ai_per_question.usable_ai_text``."""
    return _ai_per_question.usable_ai_text(raw)


def _refresh_topic_note_derived_fields(note) -> None:
    content = note.content or ''
    preview = content if len(content) <= 300 else content[:300] + '...'
    count = len(note.source_question_ids or [])
    TopicNote.objects.filter(pk=note.pk).update(content_preview=preview, source_question_count=count)
    note.content_preview = preview
    note.source_question_count = count


class TopicNoteCreateView(APIView):
    """Create (or update by subject/topic/exam/title) an admin topic note."""
    permission_classes = [IsControlTowerAdmin]

    @staticmethod
    def _existing_note(data):
        """The note this request refers to, keyed like the DB constraint
        ``uniq_topic_note`` (topic, exam_type, is_combined)."""
        topic_id = data.get('topic')
        if topic_id in (None, ''):
            return None
        try:
            topic_id = int(topic_id)
        except (TypeError, ValueError):
            return None
        raw_combined = data.get('is_combined', False)
        is_combined = raw_combined if isinstance(raw_combined, bool) else (
            str(raw_combined).strip().lower() in ('1', 'true', 'yes', 'on')
        )
        return TopicNote.objects.filter(
            topic_id=topic_id,
            exam_type=data.get('exam_type') or 'cms',
            is_combined=is_combined,
        ).first()

    def post(self, request):
        # Update in place when a note already exists for this topic: DRF
        # turns ``uniq_topic_note`` into a UniqueTogetherValidator, so
        # validating as a *create* returned 400 before the update branch
        # could ever run.
        existing = self._existing_note(request.data)
        if existing is not None:
            serializer = TopicNoteSerializer(existing, data=request.data, partial=True)
        else:
            serializer = TopicNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subject = serializer.validated_data.get('subject', getattr(existing, 'subject', None))
        topic = serializer.validated_data.get('topic', getattr(existing, 'topic', None))
        if not subject or not topic:
            return Response({'error': 'subject and topic are required'}, status=400)

        if existing is not None:
            note = serializer.save()
            created = False
        else:
            note = serializer.save(created_by=request.user)
            created = True
        _refresh_topic_note_derived_fields(note)

        out = TopicNoteSerializer(note)
        return Response(out.data, status=status.HTTP_201_CREATED if created else 200)


class PublishedTopicNoteListView(generics.ListAPIView):
    """Read-only list of published topic notes for students
    (``GET /api/questions/topic-notes/published/?subject=&topic=&exam_type=``).

    The admin CRUD is admin-only, so the student "Topic Notes" page had no
    way to read notes even when they were marked ``is_published``.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TopicNoteSerializer

    def get_queryset(self):
        qs = TopicNote.objects.filter(is_published=True, is_active=True).select_related(
            'subject', 'topic', 'created_by',
        ).order_by('-updated_at')
        params = self.request.query_params
        for param, lookup in (('subject', 'subject_id'), ('topic', 'topic_id')):
            value = params.get(param)
            if value not in (None, ''):
                try:
                    qs = qs.filter(**{lookup: int(value)})
                except (TypeError, ValueError):
                    return qs.none()
        if params.get('exam_type'):
            qs = qs.filter(exam_type=params['exam_type'])
        return qs


class AITopicNoteGenerationView(APIView):
    """Generate topic note from similar question explanations using AI.

    Routed as ``topic-notes/<pk>/generate/``; ``topic_note_id`` in the body
    is still accepted for older clients.
    """
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'ai_heavy'

    def post(self, request, pk=None):
        topic_note_id = pk or request.data.get('topic_note_id')
        if topic_note_id:
            try:
                note = TopicNote.objects.select_related('subject', 'topic').get(pk=int(topic_note_id))
            except (TopicNote.DoesNotExist, TypeError, ValueError):
                return Response({'error': 'TopicNote not found'}, status=404)
        else:
            exam_type = request.data.get('exam_type', 'cms')
            subject_id = request.data.get('subject')
            topic_id = request.data.get('topic')
            title = request.data.get('title', '')
            if not all([subject_id, topic_id]):
                return Response({'error': 'subject and topic are required'}, status=400)
            try:
                subject_id, topic_id = int(subject_id), int(topic_id)
            except (TypeError, ValueError):
                return Response({'error': 'subject and topic must be integers'}, status=400)
            if not Topic.objects.filter(pk=topic_id, subject_id=subject_id).exists():
                return Response({'error': 'topic not found for this subject'}, status=404)
            # One note per (topic, exam_type, is_combined) -- reuse it
            # whatever its title (get_or_create keyed on the title raised
            # IntegrityError -> 500 when the note existed under another one).
            note = TopicNote.objects.filter(
                topic_id=topic_id, exam_type=exam_type, is_combined=False,
            ).select_related('subject', 'topic').first()
            if note is None:
                note = TopicNote.objects.create(
                    exam_type=exam_type,
                    subject_id=subject_id,
                    topic_id=topic_id,
                    title=title or str(Topic.objects.get(pk=topic_id).name),
                    content='',
                    content_preview='',
                    created_by=request.user,
                )

        if not note.subject or not note.topic:
            return Response({'error': 'This note has no subject/topic to generate from.'}, status=400)

        # Gather explanations from similar questions
        qs = Question.objects.filter(
            subject=note.subject,
            topic=note.topic,
            exam_type=note.exam_type,
            explanation__isnull=False,
        ).exclude(explanation='').order_by('-year')[:20]
        explanations = [q.explanation for q in qs if q.explanation]
        question_ids = list(qs.values_list('id', flat=True))
        note.source_question_count = len(explanations)

        if not explanations:
            return Response({'error': 'No explanations found for this topic. Please generate explanations for questions first.'}, status=400)

        # Build prompt for AI synthesis
        from ai_engine.services import AIService
        ai_service = AIService()
        context = "\n\n---\n\n".join(explanations[:15])
        prompt = (
            f"You are a medical education expert. Synthesize the following explanations "
            # The note is published to students: the prompt carries the
            # student-facing subject label ("Imported" -> "Expert Curated").
            f"for '{note.topic.name}' (Subject: {public_subject_name(note.subject.name)}) into concise, "
            f"well-structured topic notes for exam preparation.\n\n"
            f"Guidelines:\n"
            f"- Combine repeated concepts, remove redundancy\n"
            f"- Organize logically with clear headings\n"
            f"- Retain all medically important facts and clinical correlations\n"
            f"- Use bullet points and short paragraphs\n"
            f"- Make it revision-friendly\n"
            f"- Do NOT copy-paste; rewrite in your own words\n"
            f"- Focus on exam-relevant information\n\n"
            f"Source explanations:\n{context}\n\n"
            f"Write comprehensive topic notes:"
        )
        try:
            content = _usable_ai_text(ai_service._call_ai(prompt, max_tokens=4000, temperature=0.3))
        except Exception:
            logger.exception('Topic note AI generation failed (note=%s)', note.pk)
            content = ''
        if not content:
            return Response({'detail': 'AI generation is temporarily unavailable. Please try again shortly.'}, status=503)
        note.content = content
        note.ai_generated = True
        note.source_question_ids = question_ids
        note.save(update_fields=['content', 'ai_generated', 'source_question_ids', 'updated_at'])
        _refresh_topic_note_derived_fields(note)
        return Response(TopicNoteSerializer(note).data)
