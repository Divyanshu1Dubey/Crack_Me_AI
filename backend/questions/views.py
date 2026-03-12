from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Subject, Topic, Question, QuestionBookmark, QuestionFeedback, Discussion, DiscussionVote, Note, Flashcard
from .serializers import (
    SubjectSerializer, TopicSerializer,
    QuestionListSerializer, QuestionDetailSerializer,
    QuestionUploadSerializer, BookmarkSerializer,
    QuestionFeedbackSerializer, DiscussionSerializer,
    NoteSerializer, FlashcardSerializer
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
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            serializer.save()

    @action(detail=True, methods=['patch'], url_path='resolve')
    def resolve(self, request, pk=None):
        """
        Admin action: Mark feedback as resolved/correct.
        If the feedback was from a registered user, reward them with token credits.
        """
        feedback = self.get_object()
        if feedback.is_resolved:
            return Response({'message': 'Already resolved'}, status=400)

        feedback.is_resolved = True
        feedback.save(update_fields=['is_resolved'])

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
        try:
            discussion = Discussion.objects.get(pk=pk)
        except Discussion.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        existing = DiscussionVote.objects.filter(user=request.user, discussion=discussion).first()
        if existing:
            if existing.vote_type == vote_type:
                # Remove vote
                if vote_type == 'up':
                    discussion.upvotes = max(0, discussion.upvotes - 1)
                else:
                    discussion.downvotes = max(0, discussion.downvotes - 1)
                discussion.save()
                existing.delete()
                return Response({'status': 'vote_removed', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})
            else:
                # Switch vote
                if vote_type == 'up':
                    discussion.upvotes += 1
                    discussion.downvotes = max(0, discussion.downvotes - 1)
                else:
                    discussion.downvotes += 1
                    discussion.upvotes = max(0, discussion.upvotes - 1)
                existing.vote_type = vote_type
                existing.save()
                discussion.save()
                return Response({'status': 'vote_switched', 'upvotes': discussion.upvotes, 'downvotes': discussion.downvotes})
        else:
            DiscussionVote.objects.create(user=request.user, discussion=discussion, vote_type=vote_type)
            if vote_type == 'up':
                discussion.upvotes += 1
            else:
                discussion.downvotes += 1
            discussion.save()
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
