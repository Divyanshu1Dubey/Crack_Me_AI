import logging
import csv
import re
from pathlib import Path
from threading import Lock
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, F, Max, Q, Value
from django.db.models import Exists, OuterRef
from django.db.models.functions import Greatest
from accounts.permissions import IsControlTowerAdmin
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, DiscussionVote, Note, Flashcard, QuestionImportJob, QuestionExtractionItem, AdminAIPromptVersion, QuestionAIOperationLog, QuestionRevisionSnapshot, Announcement, ExamTrack, QuestionImage, QuestionSource, RecallSource, DuplicateCluster, DuplicateMember
from .serializers import (
    SubjectSerializer, TopicSerializer, AnnouncementSerializer, ExamTrackSerializer,
    QuestionListSerializer, QuestionAdminListSerializer, QuestionDetailSerializer,
    QuestionUploadSerializer, BookmarkSerializer,
    QuestionFeedbackSerializer, DiscussionSerializer,
    NoteSerializer, FlashcardSerializer, QuestionImportJobSerializer, QuestionExtractionItemSerializer,
    AdminAIPromptVersionSerializer, QuestionAIOperationLogSerializer, QuestionRevisionSnapshotSerializer
)
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


logger = logging.getLogger(__name__)
_QUESTION_BOOTSTRAP_LOCK = Lock()


def _ensure_question_bank_loaded():
    """Load fixture once if question bank is empty in a fresh deployment."""
    import sys
    if 'test' in sys.argv or 'test_all' in sys.argv:
        return

    if Question.objects.filter(is_active=True).count() >= 1800:
        return

    fixture_path = Path(settings.BASE_DIR) / 'questions_fixture.json'
    if not fixture_path.exists():
        return

    with _QUESTION_BOOTSTRAP_LOCK:
        if Question.objects.filter(is_active=True).count() >= 1800:
            return
        
        # 1. Run migrations to ensure database schema exists
        try:
            logger.info("Auto-running migrations on startup...")
            call_command('migrate', no_input=True, verbosity=0)
        except Exception:
            logger.exception("Auto-migration failed")
            
        # 2. Run seed_data to populate subjects and topics
        try:
            logger.info("Auto-running seed_data to populate subjects and topics...")
            call_command('seed_data', verbosity=0)
        except Exception:
            logger.exception("Auto-seeding failed")

        logger.warning('Question bank empty. Bootstrapping from fixture: %s', fixture_path)
        try:
            call_command('loaddata', str(fixture_path), verbosity=0)
            logger.info('Question bank bootstrap complete. Active questions=%s', Question.objects.filter(is_active=True).count())
        except Exception:
            logger.exception('Question bank bootstrap failed')


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

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAdminUser]
        else:
            self.permission_classes = [permissions.IsAuthenticated]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Announcement.objects.all()
        # Ensure we filter by target_exam_track if applicable (dummy logic here assumes 'all' or student's target exam)
        # Ideally, we filter based on user's exam track if they have one configured in their profile
        return Announcement.objects.all() # Keep simple for now, filter logic can be expanded

class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve subjects."""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['exam_type']


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve topics, filterable by subject."""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['subject', 'parent', 'importance']


class QuestionViewSet(viewsets.ModelViewSet):
    """Full CRUD for questions with filtering, search, and bookmark support."""
    queryset = Question.objects.select_related('subject', 'topic').all()
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
    search_fields = ['question_text', 'explanation', 'concept_tags']
    ordering_fields = ['year', 'difficulty', 'created_at']

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
            exam_q = Q(exam_source=exam_source_param)
            for prefix in ('NEET PG', 'UPSC CMS', 'INI-CET', 'USMLE', 'FMGE'):
                if exam_source_param.startswith(prefix):
                    exam_q = exam_q | Q(exam_source__startswith=prefix)
                    break
            queryset = queryset.filter(exam_q)
        admin_actions = {
            'create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate',
            'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload',
            'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update',
            'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject',
            'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'generate_video', 'ai_prompt_versions',
            'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision',
            'link_related', 'set_concept_id', 'update_reference', 'format_fix',
        }
        if self.action in admin_actions:
            return queryset
        if not is_admin:
            queryset = queryset.filter(is_active=True)
        if self.action == 'list':
            queryset = queryset.select_related('subject', 'topic', 'verified_by')
            queryset = queryset.annotate(
                attempt_count=Count('questionresponse', distinct=True),
                correct_count=Count('questionresponse', filter=Q(questionresponse__is_correct=True), distinct=True),
            ).annotate(
                accuracy=(F('correct_count') * 100.0) / (F('attempt_count') + 0.0001),
            )
            if user and getattr(user, 'is_authenticated', False):
                from django.db.models import Subquery
                from questions.models import QuestionAttempt
                queryset = queryset.annotate(
                    is_bookmarked=Exists(
                        QuestionBookmark.objects.filter(question_id=OuterRef('pk'), user=user)
                    ),
                    user_selected_answer=Subquery(
                        QuestionAttempt.objects.filter(question_id=OuterRef('pk'), user=user).values('selected_answer')[:1]
                    ),
                    user_is_correct=Subquery(
                        QuestionAttempt.objects.filter(question_id=OuterRef('pk'), user=user).values('is_correct')[:1]
                    )
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

        accuracy_min = self.request.query_params.get('accuracy_min')
        accuracy_max = self.request.query_params.get('accuracy_max')
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
        _ensure_question_bank_loaded()
        return super().list(request, *args, **kwargs)

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
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate', 'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload', 'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update', 'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject', 'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'generate_video', 'ai_prompt_versions', 'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision', 'link_related', 'set_concept_id', 'update_reference', 'format_fix']:
            return [IsControlTowerAdmin()]
        if self.action in ['bookmark', 'my_bookmarks', 'attempt', 'submit_feedback']:
            return [permissions.IsAuthenticated()]
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

    @action(detail=False, methods=['get'], url_path='recall_sources',
            permission_classes=[permissions.AllowAny])
    def recall_sources(self, request):
        """List RecallSource rows — useful for the recall bank landing page."""
        qs = RecallSource.objects.filter(is_active=True).order_by("-created_at")[:200]
        return Response(RecallSourceSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=False, methods=['get'], url_path='duplicate_clusters',
            permission_classes=[permissions.AllowAny])
    def duplicate_clusters(self, request):
        qs = DuplicateCluster.objects.all().order_by("-created_at")[:100]
        return Response(DuplicateClusterSerializer(qs, many=True, context={"request": request}).data)

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
            count = min(int(request.query_params.get("count", 30)), 100)
        except ValueError:
            count = 30
        try:
            seed = int(request.query_params.get("seed")) if request.query_params.get("seed") else None
        except ValueError:
            seed = None
        params = {"count": count, "seed": seed}
        for k in ("year", "subject_id", "topic_id", "difficulty",
                  "is_image_based", "has_explanation", "has_ai_enrichment"):
            v = request.query_params.get(k)
            if v:
                params[k] = v

        ids = _practice_modes.build_queue(mode, request.user, params)
        return Response({
            "mode": mode,
            "count": len(ids),
            "question_ids": ids,
        })

    @action(detail=True, methods=['get'], url_path='ai/concept',
            permission_classes=[permissions.AllowAny])
    def ai_concept(self, request, pk=None):
        q = self.get_object()
        return Response({"concept": _ai_per_question.concept(q)})

    @action(detail=True, methods=['get'], url_path='ai/why_correct',
            permission_classes=[permissions.AllowAny])
    def ai_why_correct(self, request, pk=None):
        q = self.get_object()
        return Response({"why_correct": _ai_per_question.why_correct(q)})

    @action(detail=True, methods=['get'], url_path='ai/why_incorrect',
            permission_classes=[permissions.AllowAny])
    def ai_why_incorrect(self, request, pk=None):
        q = self.get_object()
        return Response({"why_incorrect": _ai_per_question.why_incorrect(q)})

    @action(detail=True, methods=['get'], url_path='ai/clinical',
            permission_classes=[permissions.AllowAny])
    def ai_clinical(self, request, pk=None):
        q = self.get_object()
        return Response({"clinical_significance": _ai_per_question.clinical_significance(q)})

    @action(detail=True, methods=['get'], url_path='ai/mnemonic',
            permission_classes=[permissions.AllowAny])
    def ai_mnemonic(self, request, pk=None):
        q = self.get_object()
        return Response({"memory_trick": _ai_per_question.memory_trick(q)})

    @action(detail=True, methods=['get'], url_path='ai/related_pyqs',
            permission_classes=[permissions.AllowAny])
    def ai_related_pyqs(self, request, pk=None):
        q = self.get_object()
        try:
            limit = min(int(request.query_params.get("limit", 8)), 25)
        except ValueError:
            limit = 8
        return Response({"related_pyqs": _ai_per_question.related_pyqs(q, limit=limit)})

    @action(detail=True, methods=['get'], url_path='ai/related_topics',
            permission_classes=[permissions.AllowAny])
    def ai_related_topics(self, request, pk=None):
        q = self.get_object()
        try:
            limit = min(int(request.query_params.get("limit", 8)), 25)
        except ValueError:
            limit = 8
        return Response({"related_topics": _ai_per_question.related_topics(q, limit=limit)})

    @action(detail=True, methods=['get'], url_path='ai/exam_importance',
            permission_classes=[permissions.AllowAny])
    def ai_exam_importance(self, request, pk=None):
        q = self.get_object()
        return Response({"exam_importance": _ai_per_question.exam_importance(q)})

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
        flag = bool(request.data.get("flag", True))
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
        answer = (request.data.get("answer") or "").upper()[:1]
        try:
            time_spent = int(request.data.get("time_spent", 0))
        except (TypeError, ValueError):
            time_spent = 0
        try:
            confidence = int(request.data.get("confidence", 0)) or None
        except (TypeError, ValueError):
            confidence = None
        correct_answer = (q.correct_answer or "").upper()[:1]
        is_correct = answer == correct_answer
        return Response(_practice_experience.submit_attempt(
            q, request.user,
            answer=answer, correct=is_correct,
            time_spent=time_spent, confidence=confidence,
        ))

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
            self._capture_revision_snapshot(instance, request.user, reason='Before full update')
            return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
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
        """Soft delete selected questions with explicit confirmation token."""
        ids = request.data.get('ids', [])
        confirmation = str(request.data.get('confirm', '')).upper()
        if confirmation != 'DELETE':
            return Response({'error': "Provide confirm='DELETE' to execute bulk delete"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(ids, list) or not ids:
            return Response({'error': 'ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        updated = Question.objects.filter(id__in=ids).update(is_active=False)
        return Response({'message': 'Bulk delete complete (soft archived)', 'updated': updated})

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

        job_type = 'word' if ext in ['doc', 'docx'] else 'pdf'
        stored_path = default_storage.save(f'pyq_uploads/{timezone.now().strftime("%Y%m%d_%H%M%S")}_{filename}', file_obj)

        job = QuestionImportJob.objects.create(
            job_type=job_type,
            status='queued',
            source_filename=filename,
            stored_file_path=stored_path,
            summary={'message': 'File uploaded and queued for extraction'},
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

    @action(detail=False, methods=['post'], url_path=r'extraction/items/(?P<item_id>[^/.]+)/publish')
    def extraction_item_publish(self, request, item_id=None):
        """Publish approved extraction item as a live question."""
        with transaction.atomic():
            try:
                item = QuestionExtractionItem.objects.select_for_update().select_related('subject', 'topic').get(id=item_id)
            except QuestionExtractionItem.DoesNotExist:
                return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

            if item.published_question_id:
                serializer = QuestionExtractionItemSerializer(item)
                return Response(
                    {'message': 'Item already published', 'question_id': item.published_question_id, 'item': serializer.data},
                    status=status.HTTP_200_OK,
                )

            if not item.subject or not item.question_text:
                return Response({'error': 'Subject and question_text are required before publish'}, status=status.HTTP_400_BAD_REQUEST)

            question = Question.objects.create(
                question_text=item.question_text,
                option_a=item.option_a or '',
                option_b=item.option_b or '',
                option_c=item.option_c or '',
                option_d=item.option_d or '',
                correct_answer=item.correct_answer or 'A',
                year=item.year or timezone.now().year,
                subject=item.subject,
                topic=item.topic,
                difficulty='medium',
                concept_tags=item.tags if isinstance(item.tags, list) else [],
                explanation=item.explanation or '',
                paper=item.paper or 0,
                source=f'extraction_job_{item.job_id}_item_{item.id}',
                exam_source='UPSC CMS',
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
        selected_answer = request.data.get('selected_answer')
        if not selected_answer:
            return Response({'error': 'selected_answer is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        is_correct = (selected_answer == question.correct_answer)
        
        from questions.models import QuestionAttempt
        from analytics.models import UserTopicPerformance, DailyActivity
        
        attempt, created = QuestionAttempt.objects.update_or_create(
            user=request.user,
            question=question,
            defaults={
                'selected_answer': selected_answer,
                'is_correct': is_correct
            }
        )
        
        if created:
            # Update Subject/Topic performance
            if question.topic:
                perf, _ = UserTopicPerformance.objects.get_or_create(
                    user=request.user,
                    subject=question.subject,
                    topic=question.topic
                )
                perf.total_attempts += 1
                if is_correct:
                    perf.correct_answers += 1
                else:
                    perf.incorrect_answers += 1
                perf.last_attempted = timezone.now()
                perf.save()
            
            # General subject row
            perf_sub, _ = UserTopicPerformance.objects.get_or_create(
                user=request.user,
                subject=question.subject,
                topic=None
            )
            perf_sub.total_attempts += 1
            if is_correct:
                perf_sub.correct_answers += 1
            else:
                perf_sub.incorrect_answers += 1
            perf_sub.last_attempted = timezone.now()
            perf_sub.save()
            
            # Update DailyActivity
            today = timezone.localdate()
            activity, _ = DailyActivity.objects.get_or_create(
                user=request.user,
                date=today
            )
            activity.questions_attempted += 1
            if is_correct:
                activity.correct_answers += 1
            activity.save()
            
            # Update StudyStreak and grant XP points
            from analytics.models import StudyStreak
            streak, _ = StudyStreak.objects.get_or_create(user=request.user)
            streak.record_activity()
            xp_reward = 15 if is_correct else 5
            streak.add_xp(xp_reward)
            
        return Response({
            'is_correct': is_correct,
            'correct_answer': question.correct_answer,
            'is_subscribed': getattr(request.user, 'is_subscribed', False)
        })

    @action(detail=True, methods=['post'], url_path='bookmark')
    def bookmark(self, request, pk=None):
        """Toggle bookmark on a question."""
        question = self.get_object()
        bookmark, created = QuestionBookmark.objects.get_or_create(
            user=request.user, question=question
        )
        if not created:
            bookmark.delete()
            return Response({'bookmarked': False})
        return Response({'bookmarked': True}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='bookmarks')
    def my_bookmarks(self, request):
        """List current user's bookmarked questions."""
        bookmarks = QuestionBookmark.objects.filter(user=request.user).select_related('question')
        serializer = BookmarkSerializer(bookmarks, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='years')
    def available_years(self, request):
        """Return list of available PYQ years."""
        _ensure_question_bank_loaded()
        years = Question.objects.values_list('year', flat=True).distinct().order_by('-year')
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
        _ensure_question_bank_loaded()
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
        }
        # ``Question.exam_type`` enum → source. exam_type uses ``cms`` and
        # ``neet_pg`` (underscores) so this is just the slug→source map
        # restricted to enum keys.
        EXAM_TYPE_TO_SOURCE = {k: v for k, v in EXAM_SLUG_TO_SOURCE.items()
                               if k in {'cms', 'neet_pg', 'usmle', 'fmge'}}

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

        # Progress by year (one aggregate query)
        by_year_raw = list(
            total_qs.values('year').annotate(count=Count('id')).order_by('-year')
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
            if count == 0 and exam_source == 'NEET PG':
                # Skip 0 question subjects for NEET PG
                continue
            by_subject.append({
                'id': subject.id,
                'name': subject.name,
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

        # Bucket 1: explicit M2M curation (admin-set "questions testing
        # the same concept"). Always surface these first if present.
        curated_ids = list(question.similar_questions.values_list('id', flat=True))
        # Bucket 2: same concept_id (stable AI-assigned concept key).
        same_concept_ids = []
        if question.concept_id:
            same_concept_ids = list(
                Question.objects.filter(concept_id=question.concept_id)
                .exclude(id=question.id)
                .exclude(id__in=curated_ids)
                .values_list('id', flat=True)[:LIMIT]
            )
        # Bucket 3: shares an image (same sha256_short fingerprint).
        same_image_ids = []
        image_hashes = list(
            question.images.filter(is_active=True).values_list('sha256_short', flat=True)
        )
        if image_hashes:
            same_image_ids = list(
                QuestionImage.objects.filter(
                    is_active=True, sha256_short__in=image_hashes
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
                Question.objects.filter(topic_id=question.topic_id)
                .exclude(id=question.id)
                .exclude(id__in=curated_ids + same_concept_ids + same_image_ids)
                .values_list('id', flat=True)[:LIMIT]
            )
        # Bucket 5: same subject (fallback so we always return *something*
        # — better to suggest something than an empty sidebar).
        same_subject_ids = list(
            Question.objects.filter(subject_id=question.subject_id)
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

        # Re-hydrate in the priority order via a single query.
        from django.db.models import Case, When, IntegerField
        preserve = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)],
                        default=len(ordered_ids), output_field=IntegerField())
        qs = Question.objects.filter(pk__in=ordered_ids).order_by(preserve)
        data = QuestionListSerializer(qs, many=True, context={'request': request}).data

        # Attach the reason to each serialized item.
        for item, qid in zip(data, [d.id for d in qs]):
            item['similarity_reason'] = reasons.get(qid, 'same_subject')
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
            )
        except Exception as e:
            logger.error(f"force_regenerate AI call failed for question {question.id}: {e}")
            return Response(
                {'error': 'AI service temporarily unavailable; existing fields left unchanged.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not analysis:
            return Response(
                {'error': 'AI service returned an empty response; existing fields left unchanged.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Map the analysis sections back to Question fields, gated by lock flags.
        # analyze_question returns a free-form markdown explanation; we
        # use the same text for both answer and explanation rather than
        # fabricating distinct placeholders.
        updated_fields = []
        if not question.lock_answer:
            question.ai_answer = analysis
            updated_fields.append('ai_answer')
        if not question.lock_explanation:
            question.ai_explanation = analysis
            updated_fields.append('ai_explanation')

        # ai_mnemonic stays untouched — AIService has no mnemonic entry
        # point, and silently overwriting it with placeholder text
        # previously destroyed verified content. Admins use ai_override
        # for that.
        if not question.lock_explanation and isinstance(question.textbook_references, list):
            question.ai_references = question.textbook_references
            updated_fields.append('ai_references')

        if updated_fields:
            question.save(update_fields=updated_fields)

        active_prompt = AdminAIPromptVersion.objects.filter(is_active=True).first()
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
            'message': 'AI regeneration completed',
            'id': question.id,
            'lock_answer': question.lock_answer,
            'lock_explanation': question.lock_explanation,
            'updated_fields': updated_fields,
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
        for key in sorted(set(before.keys()) | set(current.keys())):
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
        corrected_answer = request.data.get('corrected_answer')
        justification = request.data.get('justification')
        
        if not corrected_answer or not justification:
            return Response({'error': 'Both corrected_answer and justification are required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        old_answer = question.correct_answer
        question.correct_answer = corrected_answer
        question.is_disputed = False
        question.save(update_fields=['correct_answer', 'is_disputed', 'updated_at'])

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

    def perform_create(self, serializer):
        self._normalize_question_payload(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        match = self.request.headers.get("If-Match")
        if match:
            current = self.get_object().updated_at.isoformat()
            if match != current:
                return Response(
                    {"detail": "Question was modified by another user", "current": QuestionDetailSerializer(self.get_object()).data},
                    status=status.HTTP_409_CONFLICT,
                )
        self._normalize_question_payload(serializer.validated_data)
        if 'correct_answer' in serializer.validated_data:
            serializer.validated_data['lock_answer'] = True
        if 'explanation' in serializer.validated_data:
            serializer.validated_data['lock_explanation'] = True
        serializer.save()


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

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'], url_path='admin-queue')
    def admin_queue(self, request):
        """Unified issue queue with impact sorting options."""
        sort = (request.query_params.get('sort') or 'most_reported').strip().lower()
        status_filter = (request.query_params.get('status') or '').strip().lower()

        queryset = QuestionFeedback.objects.select_related('question', 'user')
        if status_filter in ['new', 'in_progress', 'resolved']:
            queryset = queryset.filter(status=status_filter)

        rows = (
            queryset
            .values('question_id', 'question__question_text', 'question__subject__name')
            .annotate(
                feedback_id=Max('id'),
                status=Max('status'),
                reports=Count('id'),
                unresolved_reports=Count('id', filter=Q(is_resolved=False)),
                latest_created_at=Max('created_at'),
                attempts=Count('question__questionresponse', distinct=True),
                correct=Count('question__questionresponse', filter=Q(question__questionresponse__is_correct=True), distinct=True),
            )
            .annotate(accuracy=(F('correct') * 100.0) / (F('attempts') + 0.0001))
            .annotate(impact_score=F('reports') * 3 + F('attempts') * 0.2 + (100.0 - F('accuracy')))
        )

        if sort == 'most_attempted':
            rows = rows.order_by('-attempts', '-reports', '-latest_created_at')
        elif sort == 'highest_impact':
            rows = rows.order_by('-impact_score', '-reports', '-latest_created_at')
        else:
            rows = rows.order_by('-reports', '-latest_created_at')

        return Response({'count': len(rows[:200]), 'results': list(rows[:200])})

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        feedback = self.get_object()
        new_status = (request.data.get('status') or '').strip().lower()
        note = request.data.get('resolution_note', '')
        notify_user = bool(request.data.get('notify_user', False))

        if new_status not in ['new', 'in_progress', 'resolved']:
            return Response({'error': "status must be one of: new, in_progress, resolved"}, status=status.HTTP_400_BAD_REQUEST)

        feedback.status = new_status
        feedback.is_resolved = new_status == 'resolved'
        feedback.resolution_note = note or feedback.resolution_note
        if feedback.is_resolved:
            feedback.resolved_by = request.user
            feedback.resolved_at = timezone.now()
        feedback.notified_user = notify_user
        feedback.save(update_fields=['status', 'is_resolved', 'resolution_note', 'resolved_by', 'resolved_at', 'notified_user'])

        if notify_user and feedback.user:
            logger.info('Feedback resolution notice queued for user_id=%s feedback_id=%s', feedback.user_id, feedback.id)

        return Response(QuestionFeedbackSerializer(feedback, context={'request': request}).data)

    @action(detail=True, methods=['patch'], url_path='resolve')
    def resolve(self, request, pk=None):
        """
        Admin action: Mark feedback as resolved/correct.
        If the feedback was from a registered user, reward them with token credits.
        """
        feedback = self.get_object()
        if feedback.is_resolved:
            return Response({'message': 'Already resolved'}, status=400)

        feedback.status = 'resolved'
        feedback.is_resolved = True
        feedback.resolved_by = request.user
        feedback.resolved_at = timezone.now()
        feedback.save(update_fields=['status', 'is_resolved', 'resolved_by', 'resolved_at'])

        # Reward the reporter with token credits
        if feedback.user:
            from accounts.models import TokenBalance, TokenConfig, TokenTransaction
            balance, _ = TokenBalance.objects.get_or_create(user=feedback.user)
            config = TokenConfig.get_config()
            reward = config.feedback_reward
            balance.add_feedback_credit(reward)
            TokenTransaction.objects.create(
                user=feedback.user,
                transaction_type='feedback_reward',
                amount=reward,
                note=f'Reward for accepted feedback #{feedback.id}: {feedback.get_category_display()}',
            )
            return Response({
                'message': f'Feedback resolved. User {feedback.user.username} rewarded {reward} tokens.',
                'rewarded_user': feedback.user.username,
                'tokens_rewarded': reward,
            })

        return Response({'message': 'Feedback resolved (no user to reward).'})


class DiscussionListCreateView(generics.ListCreateAPIView):
    """List discussions for a question or create a new one."""
    serializer_class = DiscussionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        question_id = self.request.query_params.get('question')
        qs = Discussion.objects.select_related('user').filter(parent__isnull=True)
        if question_id:
            qs = qs.filter(question_id=question_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DiscussionRepliesView(generics.ListAPIView):
    """List replies to a discussion."""
    serializer_class = DiscussionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Discussion.objects.filter(parent_id=self.kwargs['pk']).select_related('user')


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

            DiscussionVote.objects.create(user=request.user, discussion=discussion, vote_type=vote_type)
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
        return Flashcard.objects.filter(user=self.request.user)


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
    """Spaced repetition analytics: retention rate, interval distribution, memory curves."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Avg, Q
        from django.utils import timezone

        cards = Flashcard.objects.filter(user=request.user)
        total = cards.count()
        if total == 0:
            return Response({
                'total_cards': 0, 'cards_due_today': 0, 'retention_rate': 0,
                'avg_ease_factor': 0, 'avg_interval': 0, 'interval_distribution': {},
            })

        now = timezone.now()
        due_today = cards.filter(Q(next_review__lte=now) | Q(next_review__isnull=True)).count()
        aggs = cards.aggregate(
            avg_ease=Avg('ease_factor'),
            avg_interval=Avg('interval_days'),
        )

        return Response({
            'total_cards': total,
            'cards_due_today': due_today,
            'retention_rate': round(cards.filter(ease_factor__gte=2.5).count() / total, 3),
            'avg_ease_factor': round(aggs['avg_ease'] or 0, 2),
            'avg_interval': round(aggs['avg_interval'] or 0, 1),
            'interval_distribution': {
                '1_day': cards.filter(interval_days=1).count(),
                '2_7_days': cards.filter(interval_days__range=(2, 7)).count(),
                '8_30_days': cards.filter(interval_days__range=(8, 30)).count(),
                '30_plus_days': cards.filter(interval_days__gt=30).count(),
            },
        })

class ChatAssistantView(APIView):
    """
    Handles unstructured queries from the Floating Ask-AI Dock.
    Passes contextual question text if provided.
    Uses the real AIService.ask_tutor() with RAG grounding.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        message = request.data.get('message', '').strip()
        context_question_id = request.data.get('context_question_id')

        if not message:
            return Response({"error": "Message is required."}, status=400)

        # Token check — admins bypass
        from ai_engine.views import consume_ai_token, refund_ai_token
        ok, err = consume_ai_token(request)
        if not ok:
            return err

        # Build context if a question ID is provided
        context_str = ""
        if context_question_id:
            try:
                question = Question.objects.get(id=context_question_id)
                context_str = f"Context Question: {question.question_text}\n"
                context_str += f"A: {question.option_a}, B: {question.option_b}, C: {question.option_c}, D: {question.option_d}\n"
                context_str += f"Correct Answer: {question.correct_answer}\n\n"
            except Question.DoesNotExist:
                pass

        try:
            from ai_engine.services import AIService
            service = AIService()
            reply = service.ask_tutor(message, context_str)
            return Response({"reply": reply})
        except Exception as e:
            logger.error(f"ChatAssistant AI failed: {e}")
            refund_ai_token(request)
            return Response({"reply": "AI service temporarily unavailable. Your token has been refunded. Please try again."})


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
    swapped). Auth-gated because the question bank is paywalled.

    **URL contract**:
        GET /api/questions/images/<int:image_id>/serve/?w=480&q=72

    Optional query params (best-effort, ignored if Pillow unavailable):
      - `w` : max width in px (preserves aspect ratio, never upscales)
      - `q` : JPEG quality 1-100 (default 80)

    Returns 404 if the row is missing or inactive. Returns 200 with the
    binary when the file exists locally. Returns 503 with a clear JSON
    error if the file is missing on disk (the 3,496-row DB has only 257
    files locally; remote prod may have a different mix).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, image_id: int):
        img = (
            QuestionImage.objects.filter(id=image_id, is_active=True)
            .only("id", "question_id", "file", "mime", "width", "height")
            .first()
        )
        if not img or not img.file:
            raise Http404("Question image not found")

        try:
            f = img.file.open("rb")
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

        # Best-effort resize via Pillow if requested. Failing open (serve
        # the raw bytes) is acceptable — the player still renders.
        w_param = request.query_params.get("w")
        q_param = request.query_params.get("q")
        if w_param or q_param:
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
                out_mime = (img.mime or "image/jpeg").lower()
                if out_mime in ("image/jpeg", "image/jpg") or out_mime == "image/png" and target_w:
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
                return resp
            except ImportError:
                # Pillow not installed — fall through to raw bytes
                pass
            except Exception as resize_exc:  # noqa: BLE001
                logger.warning("Image resize failed for #%s: %s", image_id, resize_exc)

        # Raw passthrough
        try:
            f.seek(0)
        except Exception:  # noqa: BLE001
            pass
        content_type = (img.mime or "application/octet-stream").strip()
        resp = FileResponse(f, content_type=content_type)
        resp["Cache-Control"] = "private, max-age=3600"
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
        try:
            uploaded = upload_image_to_supabase(
                file_obj=file_obj,
                question_id=question_id_int,
                content_type=file_obj.content_type or "application/octet-stream",
                original_filename=file_obj.name or "image.png",
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

    @action(detail=True, methods=["post"])
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
