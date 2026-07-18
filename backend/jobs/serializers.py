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
            'is_active', 'is_bookmarked'
        ]

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return JobBookmark.objects.filter(user=request.user, job=obj).exists()
        return False
