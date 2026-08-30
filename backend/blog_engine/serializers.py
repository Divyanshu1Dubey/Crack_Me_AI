from rest_framework import serializers
from .models import BlogPost


class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = [
            "id",
            "slug",
            "title",
            "description",
            "excerpt",
            "cover_image",
            "category",
            "subcategory",
            "tags",
            "difficulty",
            "author_id",
            "reviewed_by",
            "author",
            "author_role",
            "date_published",
            "date_modified",
            "updated_at",
            "reading_time",
            "word_count",
            "primary_cta",
            "related_exam_paths",
            "faqs",
            "toc",
            "references",
            "revision_log",
            "body",
            "prelude",
            "outro",
            "pinned",
            "trending",
            "is_published",
            "created_at",
            "updated",
        ]
        read_only_fields = ["id", "created_at", "updated"]


class BlogPostListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = [
            "id",
            "slug",
            "title",
            "excerpt",
            "category",
            "author",
            "date_published",
            "reading_time",
            "difficulty",
            "is_published",
            "pinned",
            "tags",
            "cover_image",
            "word_count",
        ]
