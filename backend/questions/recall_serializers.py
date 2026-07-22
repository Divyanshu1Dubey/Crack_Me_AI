"""Recall-specific serializers — additive, do not modify existing ones."""
from rest_framework import serializers

from .models import DuplicateCluster, DuplicateMember, QuestionImage, QuestionSource, RecallSource


class QuestionImageSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionImage
        fields = [
            "id", "question", "page_number", "image_index_in_page",
            "file_url", "mime", "width", "height",
            "sha256_short", "phash", "dhash",
            "modality", "modality_subtype", "body_region",
            "ocr_text", "caption", "caption_source",
            "ocr_confidence", "extraction_confidence",
            "has_diagram", "has_table", "is_watermarked",
            "role", "is_active", "created_at",
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        try:
            url = obj.file.url
        except Exception:
            return None
        return request.build_absolute_uri(url) if request else url


class QuestionSourceSerializer(serializers.ModelSerializer):
    recall_source_filename = serializers.CharField(source="recall_source.pdf_filename", read_only=True)
    recall_source_sha16 = serializers.CharField(source="recall_source.pdf_sha256_short", read_only=True)

    class Meta:
        model = QuestionSource
        fields = [
            "id", "question", "recall_source", "recall_source_filename",
            "recall_source_sha16", "page_number", "question_number_in_pdf",
            "original_text", "extracted_text",
            "ocr_confidence", "extraction_confidence",
            "import_job_id", "imported_at",
        ]


class RecallSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecallSource
        fields = [
            "id", "pdf_filename", "pdf_path", "pdf_sha256", "pdf_sha256_short",
            "pdf_size_bytes", "page_count", "page_start", "page_end",
            "question_count", "scan_type", "recall_status", "publisher",
            "import_job", "is_active", "created_at",
        ]


class DuplicateClusterSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = DuplicateCluster
        fields = [
            "id", "canonical_question", "similarity_threshold",
            "detection_method", "created_at", "member_count",
        ]

    def get_member_count(self, obj):
        return obj.members.count()


class DuplicateMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = DuplicateMember
        fields = ["id", "cluster", "question", "similarity_score", "created_at"]