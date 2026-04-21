import logging
import csv
import re
from pathlib import Path
from threading import Lock
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.files.storage import default_storage
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, F, Max, Q, Value
from django.db.models.functions import Greatest
from accounts.permissions import IsControlTowerAdmin
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, DiscussionVote, Note, Flashcard, QuestionImportJob, QuestionExtractionItem, AdminAIPromptVersion, QuestionAIOperationLog, QuestionRevisionSnapshot
from .serializers import (
    SubjectSerializer, TopicSerializer,
    QuestionListSerializer, QuestionAdminListSerializer, QuestionDetailSerializer,
    QuestionUploadSerializer, BookmarkSerializer,
    QuestionFeedbackSerializer, DiscussionSerializer,
    NoteSerializer, FlashcardSerializer, QuestionImportJobSerializer, QuestionExtractionItemSerializer,
    AdminAIPromptVersionSerializer, QuestionAIOperationLogSerializer, QuestionRevisionSnapshotSerializer
)


logger = logging.getLogger(__name__)
_QUESTION_BOOTSTRAP_LOCK = Lock()


def _ensure_question_bank_loaded():
    """Load fixture once if question bank is empty in a fresh deployment."""
    if Question.objects.filter(is_active=True).exists():
        return

    fixture_path = Path(settings.BASE_DIR) / 'questions_fixture.json'
    if not fixture_path.exists():
        return

    with _QUESTION_BOOTSTRAP_LOCK:
        if Question.objects.filter(is_active=True).exists():
            return
        logger.warning('Question bank empty. Bootstrapping from fixture: %s', fixture_path)
        try:
            call_command('loaddata', str(fixture_path), verbosity=0)
            logger.info('Question bank bootstrap complete. Active questions=%s', Question.objects.filter(is_active=True).count())
        except Exception:
            logger.exception('Question bank bootstrap failed')


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve subjects."""
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [permissions.AllowAny]


class TopicViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve topics, filterable by subject."""
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [permissions.AllowAny]
    filterset_fields = ['subject', 'parent', 'importance']


class QuestionViewSet(viewsets.ModelViewSet):
    """Full CRUD for questions with filtering, search, and bookmark support."""
    queryset = Question.objects.select_related('subject', 'topic').all()
    filterset_fields = ['year', 'subject', 'topic', 'difficulty', 'exam_source', 'is_verified_by_admin']
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
        admin_actions = {
            'create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate',
            'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload',
            'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update',
            'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject',
            'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'ai_prompt_versions',
            'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision',
            'link_related', 'set_concept_id', 'update_reference', 'format_fix',
        }
        if self.action in admin_actions:
            return queryset
        if not is_admin:
            queryset = queryset.filter(is_active=True)
        if self.action == 'list':
            queryset = queryset.annotate(
                attempt_count=Count('questionresponse', distinct=True),
                correct_count=Count('questionresponse', filter=Q(questionresponse__is_correct=True), distinct=True),
            ).annotate(
                accuracy=(F('correct_count') * 100.0) / (F('attempt_count') + 0.0001),
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
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'upload', 'verify', 'unverify', 'duplicate', 'archive', 'unarchive', 'import_preview', 'bulk_metadata', 'bulk_delete', 'extraction_upload', 'extraction_jobs', 'extraction_retry', 'extraction_items', 'extraction_item_update', 'extraction_item_autotag', 'extraction_item_approve', 'extraction_item_reject', 'extraction_item_publish', 'ai_override', 'ai_lock', 'force_regenerate', 'ai_prompt_versions', 'ai_prompt_activate', 'ai_timeline', 'revisions', 'revisions_diff', 'undo_last_revision', 'link_related', 'set_concept_id', 'update_reference', 'format_fix']:
            return [IsControlTowerAdmin()]
        if self.action in ['bookmark', 'my_bookmarks']:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

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
        """Return question count statistics by subject, year, difficulty."""
        _ensure_question_bank_loaded()
        from django.db.models import Count
        stats = {
            'total': Question.objects.filter(is_active=True).count(),
            'by_subject': list(
                Subject.objects.annotate(count=Count('questions')).values('name', 'code', 'count')
            ),
            'by_year': list(
                Question.objects.filter(is_active=True)
                .values('year').annotate(count=Count('id')).order_by('-year')
            ),
            'by_difficulty': list(
                Question.objects.filter(is_active=True)
                .values('difficulty').annotate(count=Count('id'))
            ),
            'trends': list(
                Question.objects.filter(is_active=True)
                .values('year', 'subject__name', 'subject__code')
                .annotate(count=Count('id'))
                .order_by('-year', 'subject__name')
            ),
        }
        return Response(stats)

    @action(detail=True, methods=['get'], url_path='similar')
    def similar_questions(self, request, pk=None):
        """Return similar questions based on subject, topic, and text similarity."""
        question = self.get_object()
        
        # Base filter: Same subject, exclude self
        base_qs = Question.objects.filter(subject=question.subject).exclude(id=question.id)
        
        # If topic exists, prioritize same topic
        if question.topic:
            similar = base_qs.filter(topic=question.topic).order_by('?')[:3]
        else:
            # Otherwise random from same subject
            similar = base_qs.order_by('?')[:3]
            
        serializer = QuestionListSerializer(similar, many=True, context={'request': request})
        return Response(serializer.data)

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
        """Force regenerate AI fields while respecting lock precedence."""
        question = self.get_object()

        if not question.lock_answer:
            question.ai_answer = f"Regenerated answer for question #{question.id}"
        if not question.lock_explanation:
            question.ai_explanation = question.explanation or 'Regenerated AI explanation placeholder.'
        question.ai_mnemonic = question.mnemonic or f"Regenerated mnemonic for question #{question.id}"
        question.ai_references = question.textbook_references if isinstance(question.textbook_references, list) else []
        question.save(update_fields=['ai_answer', 'ai_explanation', 'ai_mnemonic', 'ai_references'])

        active_prompt = AdminAIPromptVersion.objects.filter(is_active=True).first()
        response_excerpt = (question.ai_explanation or question.explanation or question.ai_answer or '')[:500]
        token_basis = len((question.question_text or '') + (question.ai_answer or '') + (question.ai_explanation or ''))
        QuestionAIOperationLog.objects.create(
            question=question,
            operation_type='regenerate',
            provider='simulated-provider',
            prompt_version=active_prompt,
            tokens_used=max(1, token_basis // 4),
            response_excerpt=response_excerpt,
            created_by=request.user,
        )

        return Response({'message': 'AI regeneration completed', 'id': question.id, 'lock_answer': question.lock_answer, 'lock_explanation': question.lock_explanation})

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

    def perform_create(self, serializer):
        self._normalize_question_payload(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._normalize_question_payload(serializer.validated_data)
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
