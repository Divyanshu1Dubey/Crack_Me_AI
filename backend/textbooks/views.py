from rest_framework import viewsets, permissions, parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Avg
from questions.models import Question
from .models import Textbook, Chapter, PDFUpload, TextbookChunk, QuestionReferenceOverride
from .serializers import (
    TextbookSerializer,
    ChapterSerializer,
    PDFUploadSerializer,
    TextbookChunkSerializer,
    QuestionReferenceOverrideSerializer,
)
from accounts.permissions import IsControlTowerAdmin


class TextbookViewSet(viewsets.ModelViewSet):
    queryset = Textbook.objects.all()
    serializer_class = TextbookSerializer

    def get_permissions(self):
        if self.action in [
            'create', 'update', 'partial_update', 'destroy',
            'chunks', 'chunk_delete', 'chunk_merge', 'chunk_rechunk', 'chunk_diagnostics', 'chunk_mark',
            'question_reference_map', 'question_reference_overrides'
        ]:
            return [IsControlTowerAdmin()]
        return [permissions.AllowAny()]

    @action(detail=False, methods=['get'], url_path='chunks')
    def chunks(self, request):
        """Chunk explorer for RAG governance with optional filters."""
        queryset = TextbookChunk.objects.select_related('textbook', 'upload').all()
        textbook_id = request.query_params.get('textbook_id')
        page_number = request.query_params.get('page_number')
        query = request.query_params.get('q', '').strip()
        only_approved = request.query_params.get('approved')

        if textbook_id:
            queryset = queryset.filter(textbook_id=textbook_id)
        if page_number:
            try:
                parsed_page_number = int(page_number)
                if parsed_page_number <= 0:
                    return Response({'error': 'page_number must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
                queryset = queryset.filter(page_number=parsed_page_number)
            except (TypeError, ValueError):
                return Response({'error': 'page_number must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        if query:
            queryset = queryset.filter(Q(chunk_text__icontains=query) | Q(book_name__icontains=query))
        if only_approved in ['true', '1', 'yes']:
            queryset = queryset.filter(is_approved=True)
        if only_approved in ['false', '0', 'no']:
            queryset = queryset.filter(is_approved=False)

        rows = queryset[:300]
        serializer = TextbookChunkSerializer(rows, many=True, context={'request': request})
        return Response({'count': len(serializer.data), 'results': serializer.data})

    @action(detail=False, methods=['post'], url_path='chunks/delete')
    def chunk_delete(self, request):
        chunk_id = request.data.get('chunk_id')
        if not chunk_id:
            return Response({'error': 'chunk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = TextbookChunk.objects.filter(id=chunk_id).delete()
        if deleted == 0:
            return Response({'error': 'Chunk not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'message': 'Chunk deleted', 'deleted': deleted})

    @action(detail=False, methods=['post'], url_path='chunks/merge')
    def chunk_merge(self, request):
        chunk_ids = request.data.get('chunk_ids', [])
        if not isinstance(chunk_ids, list) or len(chunk_ids) < 2:
            return Response({'error': 'Provide at least 2 chunk_ids'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            chunks = list(TextbookChunk.objects.select_for_update().filter(id__in=chunk_ids).order_by('page_number', 'id'))
            if len(chunks) < 2:
                return Response({'error': 'Chunks not found'}, status=status.HTTP_404_NOT_FOUND)

            head = chunks[0]
            merged_text = '\n\n'.join([c.chunk_text for c in chunks if c.chunk_text])
            merged_chunk = TextbookChunk.objects.create(
                textbook=head.textbook,
                upload=head.upload,
                book_name=head.book_name,
                page_number=head.page_number,
                chunk_text=merged_text,
                quality_score=max([c.quality_score for c in chunks]),
                is_approved=all(c.is_approved for c in chunks),
                merged_from_ids=[c.id for c in chunks],
            )
            TextbookChunk.objects.filter(id__in=chunk_ids).delete()
        serializer = TextbookChunkSerializer(merged_chunk, context={'request': request})
        return Response({'message': 'Chunks merged', 'chunk': serializer.data})

    @action(detail=False, methods=['post'], url_path='chunks/rechunk')
    def chunk_rechunk(self, request):
        """Re-chunk long chunks using simple word-window splitting."""
        chunk_ids = request.data.get('chunk_ids', [])
        try:
            chunk_size = max(100, min(int(request.data.get('chunk_size', 500)), 2000))
            overlap = max(0, min(int(request.data.get('overlap', 50)), 400))
        except (TypeError, ValueError):
            return Response({'error': 'chunk_size and overlap must be integers'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(chunk_ids, list) or not chunk_ids:
            return Response({'error': 'chunk_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        with transaction.atomic():
            target_chunks = list(TextbookChunk.objects.select_for_update().filter(id__in=chunk_ids))
            if not target_chunks:
                return Response({'error': 'No chunks found'}, status=status.HTTP_404_NOT_FOUND)

            for chunk in target_chunks:
                words = (chunk.chunk_text or '').split()
                if not words:
                    continue
                step = max(1, chunk_size - overlap)
                for i in range(0, len(words), step):
                    part = words[i:i + chunk_size]
                    if not part:
                        continue
                    TextbookChunk.objects.create(
                        textbook=chunk.textbook,
                        upload=chunk.upload,
                        book_name=chunk.book_name,
                        page_number=chunk.page_number,
                        chunk_text=' '.join(part),
                        quality_score=chunk.quality_score,
                        merged_from_ids=[chunk.id],
                    )
                    created += 1

            TextbookChunk.objects.filter(id__in=chunk_ids).delete()
        return Response({'message': 'Re-chunk completed', 'created': created, 'deleted': len(target_chunks)})

    @action(detail=False, methods=['get'], url_path='chunks/diagnostics')
    def chunk_diagnostics(self, request):
        queryset = TextbookChunk.objects.all()
        total = queryset.count()
        approved = queryset.filter(is_approved=True).count()
        rejected = queryset.filter(is_rejected=True).count()
        avg_quality = queryset.aggregate(v=Avg('quality_score')).get('v') or 0
        return Response({
            'total_chunks': total,
            'approved_chunks': approved,
            'rejected_chunks': rejected,
            'approval_rate': round((approved / total) * 100, 2) if total else 0,
            'avg_quality_score': round(avg_quality, 2),
        })

    @action(detail=False, methods=['post'], url_path='chunks/mark')
    def chunk_mark(self, request):
        chunk_id = request.data.get('chunk_id')
        status_value = str(request.data.get('status', '')).lower()
        if not chunk_id or status_value not in ['approved', 'rejected', 'pending']:
            return Response({'error': 'chunk_id and status=[approved|rejected|pending] are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            chunk = TextbookChunk.objects.get(id=chunk_id)
        except TextbookChunk.DoesNotExist:
            return Response({'error': 'Chunk not found'}, status=status.HTTP_404_NOT_FOUND)

        if status_value == 'approved':
            chunk.is_approved = True
            chunk.is_rejected = False
        elif status_value == 'rejected':
            chunk.is_approved = False
            chunk.is_rejected = True
        else:
            chunk.is_approved = False
            chunk.is_rejected = False

        chunk.save(update_fields=['is_approved', 'is_rejected', 'updated_at'])
        serializer = TextbookChunkSerializer(chunk, context={'request': request})
        return Response({'message': 'Chunk status updated', 'chunk': serializer.data})

    @action(detail=False, methods=['get'], url_path='question-reference-overrides')
    def question_reference_overrides(self, request):
        raw_limit = request.query_params.get('limit', 100)
        try:
            parsed_limit = int(raw_limit)
        except (TypeError, ValueError):
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        if parsed_limit <= 0:
            return Response({'error': 'limit must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
        limit = min(parsed_limit, 500)
        rows = QuestionReferenceOverride.objects.select_related('question', 'textbook', 'created_by').all()[:limit]
        serializer = QuestionReferenceOverrideSerializer(rows, many=True, context={'request': request})
        return Response({'count': len(serializer.data), 'results': serializer.data})

    @action(detail=False, methods=['post'], url_path='question-reference-map', parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def question_reference_map(self, request):
        """Manual Question -> Book/Page/Screenshot mapping override."""
        question_id = request.data.get('question_id')
        if not question_id:
            return Response({'error': 'question_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)

        textbook_id = request.data.get('textbook_id')
        chapter = request.data.get('chapter', '')
        page_number = str(request.data.get('page_number', '') or '')
        excerpt = request.data.get('excerpt', '')
        screenshot = request.FILES.get('screenshot')

        textbook = None
        if textbook_id:
            textbook = Textbook.objects.filter(id=textbook_id).first()
            if not textbook:
                return Response({'error': 'Textbook not found'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            override = QuestionReferenceOverride.objects.create(
                question=question,
                textbook=textbook,
                chapter=chapter,
                page_number=page_number,
                excerpt=excerpt,
                screenshot=screenshot,
                created_by=request.user if request.user.is_authenticated else None,
                is_active=True,
            )

            # Persist override precedence to Question fields used in retrieval/response.
            references = [{
                'book': textbook.name if textbook else question.book_name,
                'chapter': chapter,
                'page': page_number,
                'excerpt': excerpt,
                'override_id': override.id,
            }]
            question.book_name = textbook.name if textbook else question.book_name
            question.chapter = chapter
            question.page_number = page_number
            question.reference_text = excerpt
            question.admin_references_override = references
            update_fields = ['book_name', 'chapter', 'page_number', 'reference_text', 'admin_references_override']
            if screenshot:
                question.page_screenshot = screenshot
                update_fields.append('page_screenshot')
            question.save(update_fields=update_fields)

        serializer = QuestionReferenceOverrideSerializer(override, context={'request': request})
        return Response({'message': 'Reference override saved', 'override': serializer.data})


class PDFUploadViewSet(viewsets.ModelViewSet):
    serializer_class = PDFUploadSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return PDFUpload.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        upload = serializer.save(user=self.request.user)
        # Seed an initial chunk record for manual governance workflows.
        TextbookChunk.objects.create(
            textbook=upload.textbook,
            upload=upload,
            book_name=upload.textbook.name if upload.textbook else upload.title,
            page_number=1,
            chunk_text=f"Uploaded source placeholder for {upload.title}. Replace with parser-derived chunks.",
            quality_score=0.5,
        )
