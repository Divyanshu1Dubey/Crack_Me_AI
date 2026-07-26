from rest_framework import serializers

from .models import QuestionImage


class QuestionImageSerializer(serializers.ModelSerializer):
    """Admin-facing serializer for `QuestionImage`.

    Exposes every writable field including `uploaded_by_admin` and
    `url`. Read-only fields: `id`, `sha256`, `sha256_short`, `width`,
    `height`, `bytes`, `created_at`.
    """
    class Meta:
        model = QuestionImage
        fields = [
            "id", "question", "page_number", "image_index_in_page",
            "file", "mime", "width", "height", "bytes",
            "sha256", "sha256_short", "phash", "dhash",
            "modality", "modality_subtype", "body_region",
            "ocr_text", "caption", "caption_source", "ocr_confidence",
            "role", "url", "uploaded_by_admin",
        ]
        read_only_fields = [
            "id", "sha256", "sha256_short", "phash", "dhash",
            "width", "height", "bytes",
        ]