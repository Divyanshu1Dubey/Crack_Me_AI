from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback
from .serializers import (
    SubjectSerializer, TopicSerializer,
    QuestionListSerializer, QuestionDetailSerializer,
    QuestionUploadSerializer, BookmarkSerializer,
    QuestionFeedbackSerializer
)


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
    queryset = Question.objects.select_related('subject', 'topic').filter(is_active=True)
    filterset_fields = ['year', 'subject', 'topic', 'difficulty', 'exam_source']
    search_fields = ['question_text', 'explanation', 'concept_tags']
    ordering_fields = ['year', 'difficulty', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return QuestionListSerializer
        if self.action == 'upload':
            return QuestionUploadSerializer
        return QuestionDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'upload']:
            return [permissions.IsAdminUser()]
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
        years = Question.objects.values_list('year', flat=True).distinct().order_by('-year')
        return Response(list(years))

    @action(detail=False, methods=['get'], url_path='stats')
    def question_stats(self, request):
        """Return question count statistics by subject, year, difficulty."""
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


class QuestionFeedbackViewSet(viewsets.ModelViewSet):
    """ViewSet for students to report errors in questions."""
    queryset = QuestionFeedback.objects.all()
    serializer_class = QuestionFeedbackSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]  # Allow even guests to report? Or just authenticated?
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()
