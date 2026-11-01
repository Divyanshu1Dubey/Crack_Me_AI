from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Job, JobCategory, JobBookmark
from .serializers import JobSerializer, JobCategorySerializer

class JobCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobCategory.objects.all()
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.AllowAny]

class JobViewSet(viewsets.ModelViewSet):
    # select_related / prefetch_related + the Exists() annotation below keep a
    # page of jobs at a fixed number of queries (it used to run ~3 extra
    # queries per row: category name, exam tracks, bookmark lookup).
    queryset = Job.objects.select_related('category').prefetch_related('exam_tracks')
    serializer_class = JobSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['title', 'hospital', 'location', 'description']
    ordering_fields = ['posted_at', 'expires_at']
    ordering = ['-posted_at']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        # Students may bookmark jobs; this override previously ignored the
        # decorator and returned IsAdminUser (403 for everyone else).
        if self.action == 'bookmark':
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.action in ['list', 'retrieve']:
            is_admin = user.is_authenticated and (
                getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
            )
            if not is_admin:
                # Students never see inactive or expired postings.
                qs = qs.filter(is_active=True).filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
                )
            # ?exam_track=<code> (the jobs page's track selector; it used to
            # be ignored). Matches the M2M exam tracks or the JSON tag list.
            exam_track = (self.request.query_params.get('exam_track') or '').strip()
            if exam_track and exam_track != 'all':
                qs = qs.filter(
                    Q(exam_tracks__code=exam_track)
                    | Q(exam_track_tags__icontains=f'"{exam_track}"')
                ).distinct()
            if user.is_authenticated:
                qs = qs.annotate(_is_bookmarked=Exists(
                    JobBookmark.objects.filter(user=user, job=OuterRef('pk'))
                ))
        return qs

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bookmark(self, request, pk=None):
        job = self.get_object()
        bookmark, created = JobBookmark.objects.get_or_create(user=request.user, job=job)
        if not created:
            bookmark.delete()
            return Response({'status': 'unbookmarked'})
        return Response({'status': 'bookmarked'})
