from rest_framework import serializers

from .models import Job, JobCategory, JobBookmark
from .official_sources import approval_problems

ADMIN_ONLY_FIELDS = ('review_note',)


def _is_admin(user):
    return bool(user and user.is_authenticated and (
        getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False)))


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ['id', 'name', 'slug']

class JobSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'hospital', 'location', 'category', 'category_name',
            'description', 'salary', 'apply_link', 'posted_at', 'expires_at',
            'is_active', 'is_bookmarked', 'eligibility_summary', 'exam_track_tags', 'exam_tracks', 'admin_edited',
            'source_url', 'status', 'last_verified_at', 'review_note',
        ]
        # verified by the verify action only (jobs.views.JobViewSet.verify), never typed in
        read_only_fields = ['last_verified_at']

    def validate(self, attrs):
        """An approved listing keeps official links and a recent verification (jobs.official_sources)."""
        instance = self.instance
        status = attrs.get('status', getattr(instance, 'status', 'draft'))
        if status == 'approved':
            problems = approval_problems(
                apply_link=attrs.get('apply_link', getattr(instance, 'apply_link', '')),
                source_url=attrs.get('source_url', getattr(instance, 'source_url', '')),
                last_verified_at=getattr(instance, 'last_verified_at', None),
            )
            if problems:
                raise serializers.ValidationError({'status': problems})
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        request = self.context.get('request')
        if not _is_admin(getattr(request, 'user', None)):
            for field in ADMIN_ONLY_FIELDS:
                data.pop(field, None)
        return data

    def get_is_bookmarked(self, obj):
        # The list/retrieve queryset annotates this with Exists(), so no
        # per-row query; fall back to a lookup for other call sites.
        annotated = getattr(obj, '_is_bookmarked', None)
        if annotated is not None:
            return bool(annotated)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return JobBookmark.objects.filter(user=request.user, job=obj).exists()
        return False
