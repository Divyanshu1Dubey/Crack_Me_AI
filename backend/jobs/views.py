from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from crack_cms.filters import BoundedSearchFilter
from .models import Job, JobCategory, JobBookmark
from .official_sources import approval_problems, public_filter
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
    # BoundedSearchFilter: ?search= (open to anonymous callers) keeps at most
    # 10 distinct terms of up to 100 characters; each term is an ILIKE per
    # search field.
    filter_backends = [DjangoFilterBackend, BoundedSearchFilter, OrderingFilter]
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
        if self.action in ['list', 'retrieve', 'bookmark']:
            is_admin = user.is_authenticated and (
                getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
            )
            if not is_admin:
                # Students see only listings an admin checked against the official notification and approved,
                # verified recently and still open (jobs.official_sources.public_filter).
                qs = qs.filter(public_filter())
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

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Admin: record that the listing was checked against its official notification just now.

        Body: ``{source_url?: the official notification, approve?: true to publish it}``. Refused (400, with the
        reasons) unless both links are on an official recruitment site."""
        job = self.get_object()
        source_url = str(request.data.get('source_url') or job.source_url or '').strip()
        now = timezone.now()
        problems = approval_problems(apply_link=job.apply_link, source_url=source_url, last_verified_at=now)
        if problems:
            return Response({'status': problems}, status=status.HTTP_400_BAD_REQUEST)
        job.source_url = source_url
        job.last_verified_at = now
        job.verified_by = request.user
        fields = ['source_url', 'last_verified_at', 'verified_by']
        if str(request.data.get('approve', '')).lower() in ('1', 'true', 'yes'):
            job.status, job.review_note = 'approved', ''
            fields += ['status', 'review_note']
        job.save(update_fields=fields)
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Admin: take a listing off the board (``note``: why, kept for the admins)."""
        job = self.get_object()
        job.status = 'rejected'
        job.review_note = str(request.data.get('note') or '')[:300]
        job.save(update_fields=['status', 'review_note'])
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def bookmark(self, request, pk=None):
        job = self.get_object()
        bookmark, created = JobBookmark.objects.get_or_create(user=request.user, job=job)
        if not created:
            bookmark.delete()
            return Response({'status': 'unbookmarked'})
        return Response({'status': 'bookmarked'})
