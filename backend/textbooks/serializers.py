import os

from rest_framework import serializers
from .models import Textbook, Chapter, PDFUpload, TextbookChunk, QuestionReferenceOverride

# "My Uploads" limits. Uploads are personal reference files (they are not
# processed or indexed), so they only need to be safe and bounded.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024          # per file
MAX_UPLOADS_PER_USER = 30
MAX_UPLOAD_BYTES_PER_USER = 200 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md"}

DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def _check_upload_content(upload) -> None:
    """Reject files whose content does not match an allowed type.

    PDF / DOC / DOCX are checked by magic bytes (shared helper); TXT / MD
    must be UTF-8 text without NUL bytes. Raises ValidationError.
    """
    ext = os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise serializers.ValidationError(
            f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}."
        )
    if upload.size > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError(
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )
    if ext in {'.txt', '.md'}:
        head = upload.read(64 * 1024)
        upload.seek(0)
        if b'\x00' in head:
            raise serializers.ValidationError('Text files must not contain binary data.')
        try:
            head.decode('utf-8')
        except UnicodeDecodeError as exc:
            # A multi-byte character cut at the 64 KB boundary is fine.
            if exc.start < len(head) - 4:
                raise serializers.ValidationError('Text files must be UTF-8 encoded.')
        return

    from django.core.exceptions import ValidationError as DjangoValidationError
    from accounts.upload_validation import validate_uploaded_file

    expected = {
        '.pdf': {'application/pdf'},
        '.docx': {DOCX_MIME},
        '.doc': {'application/msword'},
    }[ext]
    try:
        detected = validate_uploaded_file(upload, allowed_types={'document'}, max_bytes=MAX_UPLOAD_BYTES)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(' '.join(exc.messages))
    if detected not in expected:
        raise serializers.ValidationError('File content does not match its extension.')


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ['id', 'number', 'title', 'textbook']


class TextbookSerializer(serializers.ModelSerializer):
    chapters = ChapterSerializer(many=True, read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = Textbook
        fields = ['id', 'name', 'author', 'edition', 'subject',
                  'subject_name', 'description', 'chapters']


class PDFUploadSerializer(serializers.ModelSerializer):
    """A student's personal upload.

    ``textbook`` is read-only: a student cannot attach a file to an official
    library textbook. Files are fetched through the authenticated
    ``download_url`` (the raw media URL is not served in production).
    """

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = PDFUpload
        fields = ['id', 'title', 'file', 'download_url', 'textbook', 'subject', 'is_processed', 'uploaded_at']
        read_only_fields = ['textbook', 'is_processed', 'uploaded_at', 'download_url']

    def get_download_url(self, obj):
        return f'/api/textbooks/uploads/{obj.id}/download/' if obj.id else ''

    def validate_file(self, upload):
        _check_upload_content(upload)
        return upload

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if self.instance is None and user is not None and user.is_authenticated:
            existing = PDFUpload.objects.filter(user=user)
            if existing.count() >= MAX_UPLOADS_PER_USER:
                raise serializers.ValidationError(
                    f'Upload limit reached ({MAX_UPLOADS_PER_USER} files). Delete an old upload first.'
                )
            used = 0
            for f in existing.only('file'):
                try:
                    used += f.file.size if f.file else 0
                except (OSError, ValueError):
                    continue
            incoming = getattr(attrs.get('file'), 'size', 0) or 0
            if used + incoming > MAX_UPLOAD_BYTES_PER_USER:
                raise serializers.ValidationError(
                    f'Storage limit reached ({MAX_UPLOAD_BYTES_PER_USER // (1024 * 1024)} MB). '
                    'Delete an old upload first.'
                )
        return attrs


class TextbookChunkSerializer(serializers.ModelSerializer):
    textbook_name = serializers.CharField(source='textbook.name', read_only=True, default='')
    upload_title = serializers.CharField(source='upload.title', read_only=True, default='')

    class Meta:
        model = TextbookChunk
        fields = [
            'id', 'textbook', 'textbook_name', 'upload', 'upload_title', 'book_name', 'page_number',
            'chunk_text', 'quality_score', 'is_approved', 'is_rejected', 'merged_from_ids', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'merged_from_ids', 'textbook_name', 'upload_title']


class QuestionReferenceOverrideSerializer(serializers.ModelSerializer):
    textbook_name = serializers.CharField(source='textbook.name', read_only=True, default='')
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = QuestionReferenceOverride
        fields = [
            'id', 'question', 'textbook', 'textbook_name', 'chapter', 'page_number', 'excerpt',
            'screenshot', 'screenshot_url', 'is_active', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at', 'updated_at', 'textbook_name', 'screenshot_url']

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return ''
