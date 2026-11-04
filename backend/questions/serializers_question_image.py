from rest_framework import serializers

from .image_access import with_image_token
from .image_context import is_retired_storage_url
from .models import QuestionImage


class QuestionImageSerializer(serializers.ModelSerializer):
    """Admin-facing serializer for `QuestionImage`.

    Exposes every writable field including `uploaded_by_admin` and
    `url`. Read-only fields: `id`, `sha256`, `sha256_short`, `width`,
    `height`, `bytes`, `created_at`, `serve_url`.

    Adds a computed `serve_url` field (Bug #2026-07-27-fix) so the admin
    Questions Editor can always render a thumbnail even when the raw
    `file` URL is unreachable (e.g. `/media/recall_images/...` 404s in
    production because static(MEDIA_URL) is DEBUG-only). The proxy at
    `/api/questions/images/<id>/serve/` reads from whichever storage
    backend is configured and is the canonical reachable URL.
    Admin-uploaded images (uploaded_by_admin=True) prefer their public
    Supabase URL since that bucket is publicly readable and skips an
    auth roundtrip.
    """
    serve_url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionImage
        fields = [
            "id", "question", "page_number", "image_index_in_page",
            "file", "mime", "width", "height", "bytes",
            "sha256", "sha256_short", "phash", "dhash",
            "modality", "modality_subtype", "body_region",
            "ocr_text", "caption", "caption_source", "ocr_confidence",
            "role", "url", "uploaded_by_admin", "serve_url",
        ]
        read_only_fields = [
            "id", "sha256", "sha256_short", "phash", "dhash",
            "width", "height", "bytes", "serve_url",
        ]

    def get_serve_url(self, obj):
        # Preference order:
        #   1. uploaded_by_admin=True with an absolute public URL on a live
        #      host → that URL. Not a retired Supabase Storage URL (the host
        #      was shut down on 2026-11-03; the proxy serves those figures
        #      from the restored copy), and not a relative /media/ path
        #      (production does not serve /media/).
        #   2. Otherwise → the proxy URL, which reads from local disk (the
        #      file, MEDIA_ROOT or the storage mirror).
        #   The proxy URL carries a signed token (questions.image_access):
        #   the serve endpoint refuses explanation figures without one, and
        #   this serializer only backs the admin-only QuestionImageViewSet
        #   (a request from anyone but staff gets no token).
        request = self.context.get("request") if hasattr(self, "context") else None
        stored = (obj.url or "").strip()
        if (getattr(obj, "uploaded_by_admin", False) and stored.startswith(("http://", "https://"))
                and not is_retired_storage_url(stored)):
            return stored
        path = f"/api/questions/images/{obj.id}/serve/"
        url = path
        if request is not None:
            try:
                url = request.build_absolute_uri(path)
            except Exception:  # noqa: BLE001
                url = path
        user = getattr(request, "user", None)
        is_staff = any(getattr(user, flag, False) for flag in ("is_staff", "is_superuser", "is_admin"))
        if request is None or is_staff:
            url = with_image_token(url, obj.id)
        return url