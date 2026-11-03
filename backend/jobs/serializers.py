from rest_framework import serializers
from .models import Job, JobCategory, JobBookmark

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
            'is_active', 'is_bookmarked', 'eligibility_summary', 'exam_track_tags', 'exam_tracks', 'admin_edited'
        ]

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
