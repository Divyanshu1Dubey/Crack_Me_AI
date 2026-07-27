from urllib.parse import urlsplit, urlunsplit

from rest_framework import serializers
from .models import (
    Subject, Topic, Question, QuestionBookmark, QuestionFeedback,
    Discussion, Note, Flashcard, QuestionImportJob,
    QuestionExtractionItem, AdminAIPromptVersion,
    QuestionAIOperationLog, QuestionRevisionSnapshot, Announcement, ExamTrack
)
from .text_encoding import normalize_text
import json as _json


# Fields that may contain user-visible text. Every serializer that emits
# one of these MUST pass the value through `_clean_text()` so legacy
# mojibake (`iÃ©`, `â€™`, `ΓÇÿ`) and stray whitespace is repaired at the
# API boundary. This is defence-in-depth alongside the
# `manage.py fix_mojibake` one-shot — new / mid-import rows can still
# carry a few bad rows, and the frontend's `decodeMojiB()` is the second
# safety net.
_TEXT_FIELDS = (
    "question_text",
    "option_a", "option_b", "option_c", "option_d",
    "explanation", "concept_explanation", "mnemonic",
    "ai_explanation", "ai_mnemonic", "ai_clinical_pearl",
    "learning_technique", "shortcut_tip", "concept_keywords",
)


def _clean_text(value):
    """Repair mojibake + normalize NFC + collapse whitespace at the API boundary.

    Returns the input unchanged when it isn't a string (None stays None,
    ints stay ints) so serializers that pass through non-string values
    don't crash.
    """
    if not isinstance(value, str):
        return value
    return normalize_text(value)


def _parse_ai_explanation_to_markdown(ai_exp: str) -> str | None:
    """Parse a JSON-encoded ai_explanation into a readable markdown string.

    Handles two cache formats:
      1. ExplainQuestionView: {"analysis": "<markdown>", "context": {...}}
         → return the analysis value directly (it's already markdown).
      2. ExplainAfterAnswerView: {"core_concept": ..., "why_correct": ..., ...}
         → stitch structured fields into a markdown document.
    Returns None if parsing fails or if the input isn't valid JSON.
    """
    if not ai_exp or not isinstance(ai_exp, str):
        return None
    stripped = ai_exp.strip()
    if not stripped:
        return None
    # Known admin placeholder: when an admin hits the
    # `force-regenerate` endpoint without locking the explanation,
    # `ai_explanation` is seeded with a placeholder like
    # "Regenerated AI explanation placeholder." It must NOT be
    # surfaced to end-users as if it were a real answer — treat it
    # as unparseable so callers fall through to the regular
    # `explanation` field (or empty).
    placeholder_markers = (
        "regenerated ai explanation placeholder",
        "regenerated mnemonic for question",
        "regenerated answer for question",
    )
    lowered = stripped.lower()
    if any(marker in lowered for marker in placeholder_markers):
        return None
    if not stripped.startswith('{'):
        return None
    try:
        data = _json.loads(stripped)
    except Exception:
        return None

    # Fast-path: ExplainQuestionView wraps everything in an "analysis" key.
    analysis_val = data.get("analysis")
    if analysis_val and isinstance(analysis_val, str):
        # If the analysis value is itself JSON, try parsing recursively.
        inner_stripped = analysis_val.strip()
        if inner_stripped.startswith('{'):
            try:
                inner = _json.loads(inner_stripped)
                if isinstance(inner, dict):
                    result = _parse_ai_explanation_to_markdown(_json.dumps(inner))
                    if result:
                        return result
            except (ValueError, _json.JSONDecodeError):
                pass
        # Plain markdown from analyze_question() — use directly.
        return analysis_val

    # Structured format: stitch known fields into markdown.
    parts: list[str] = []
    core = data.get("core_concept") or data.get("ai_verified_answer")
    if core:
        parts.append(f"**Core concept:** {core}")
    why_correct = data.get("why_correct")
    if why_correct:
        parts.append(f"**Why the correct answer is right:**\n{why_correct}")
    why_wrong = data.get("why_wrong")
    if why_wrong:
        parts.append(f"**Why other options are wrong:**\n{why_wrong}")
    pearl = data.get("clinical_pearl")
    if pearl:
        parts.append(f"**Clinical pearl:** {pearl}")
    high_yield = data.get("high_yield_points") or []
    if high_yield:
        if isinstance(high_yield, list):
            parts.append("**High-yield points:**\n" + "\n".join(f"- {p}" for p in high_yield))
        else:
            parts.append(f"**High-yield points:**\n{high_yield}")
    mnemonic = data.get("mnemonic")
    if mnemonic:
        parts.append(f"**Mnemonic:** {mnemonic}")
    tip = data.get("exam_tip")
    if tip:
        parts.append(f"**Exam tip:** {tip}")
    ref = data.get("textbook_reference")
    if ref:
        parts.append(f"**Textbook reference:** {ref}")
    if parts:
        return "\n\n".join(parts)
    return None


class ExamTrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamTrack
        fields = '__all__'


def _derive_subtitles_url(video_url: str) -> str:
    if not video_url:
        return ''
    parsed = urlsplit(video_url)
    path = parsed.path or ''
    if not path.endswith('.mp4'):
        return ''
    subtitles_path = f"{path[:-4]}.vtt"
    return urlunsplit((parsed.scheme, parsed.netloc, subtitles_path, parsed.query, parsed.fragment))


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = '__all__'

class SubjectSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'paper', 'description', 'icon', 'color', 'question_count']

    def get_question_count(self, obj):
        return obj.questions.count()


class TopicSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = ['id', 'name', 'subject', 'subject_name', 'parent',
                  'importance', 'description', 'question_count']

    def get_question_count(self, obj):
        return obj.questions.count()


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    is_bookmarked = serializers.SerializerMethodField()
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True, default='')
    effective_answer = serializers.SerializerMethodField()
    effective_explanation = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    last_revision_at = serializers.SerializerMethodField()
    related_question_ids = serializers.SerializerMethodField()
    accuracy = serializers.SerializerMethodField()
    user_selected_answer = serializers.CharField(read_only=True, required=False)
    user_is_correct = serializers.BooleanField(read_only=True, required=False)
    video_subtitles_url = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    duplicate_count = serializers.SerializerMethodField()
    duplicate_cluster_id = serializers.SerializerMethodField()

    def to_representation(self, instance):
        """Repair mojibake on every text field at the API boundary.

        Without this pass, a Question row imported with a Windows-1252 /
        Latin-1 locale (the legacy fixture path) leaves `iÃ©iÃiÃ©` in the
        JSON payload — the frontend is then forced to call
        `decodeMojiB()` on every render. Normalizing here means the API
        ships clean text and the frontend guard becomes a true
        defence-in-depth (instead of the *only* line of defence).
        """
        data = super().to_representation(instance)
        for field in _TEXT_FIELDS:
            if field in data and isinstance(data[field], str):
                data[field] = _clean_text(data[field])
        return data

    class Meta:
        model = Question
        fields = ['id', 'uuid', 'display_number', 'is_dropped', 'admin_edited', 'needs_review',
                  'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'year', 'subject', 'subject_name',
                  'topic', 'topic_name', 'difficulty', 'exam_source',
                  'concept_tags', 'concept_id', 'book_name', 'chapter', 'page_number', 'reference_text',
                  'textbook_references', 'is_bookmarked', 'is_verified_by_admin',
                  'verified_at', 'verified_by', 'verified_by_username',
                  'effective_answer', 'effective_explanation',
                  'revision_count', 'last_revision_at', 'related_question_ids', 'accuracy',
                  'user_selected_answer', 'user_is_correct', 'video_url', 'video_status',
                  'video_thumbnail', 'video_duration', 'video_subtitles_url',
                  'is_image_based', 'page_screenshot', 'images',
                  'duplicate_count', 'duplicate_cluster_id']

    def get_is_bookmarked(self, obj):
        return bool(getattr(obj, 'is_bookmarked', False))

    def _is_admin(self):
        """True when the requesting user is staff / admin.

        Used to gate the answer / explanation getters so the list
        endpoint (and the mock-test start_attempt endpoint, which
        re-uses this serializer) does not leak the correct answer
        to non-admin users via DevTools.
        """
        request = self.context.get('request') if hasattr(self, 'context') else None
        if not request or not getattr(request, 'user', None):
            return False
        user = request.user
        return bool(
            getattr(user, 'is_authenticated', False)
            and (
                getattr(user, 'is_admin', False)
                or getattr(user, 'is_superuser', False)
                or getattr(user, 'is_staff', False)
            )
        )

    def get_effective_answer(self, obj):
        # Bug #3 (question-bank sweep, 2026-07-27): the list endpoint
        # previously returned the correct answer text to every
        # non-admin user. The detail endpoint (QuestionDetailSerializer)
        # is the right place to surface it, since the user has
        # explicitly opened that question to study it.
        if not self._is_admin():
            return None
        if obj.lock_answer:
            return obj.admin_answer_override or obj.get_correct_option_text()
        if obj.admin_answer_override:
            return obj.admin_answer_override
        return obj.ai_answer or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        # Same leak as effective_answer — the full explanation text was
        # being returned in every list payload, defeating the
        # assessment for any student willing to open DevTools.
        if not self._is_admin():
            return None
        if obj.lock_explanation:
            return obj.admin_explanation_override or obj.explanation
        if obj.admin_explanation_override:
            return obj.admin_explanation_override
        ai_exp = obj.ai_explanation
        parsed = _parse_ai_explanation_to_markdown(ai_exp)
        if parsed:
            return parsed
        return ai_exp or obj.explanation

    def get_revision_count(self, obj):
        return getattr(obj, 'revision_count', 0) or 0

    def get_last_revision_at(self, obj):
        return getattr(obj, 'last_revision_at', None)

    def get_related_question_ids(self, obj):
        related_ids = getattr(obj, 'related_question_ids', None)
        if related_ids is None:
            return []
        return list(related_ids)

    def get_accuracy(self, obj):
        value = getattr(obj, 'accuracy', None)
        if value is None:
            return None

    def get_video_subtitles_url(self, obj):
        return _derive_subtitles_url(getattr(obj, 'video_url', '') or '')

    def get_images(self, obj):
        out = []
        for img in obj.images.all():
            if not img.is_active:
                continue
            # Bug #P0-2 (2026-07-25): /media/... URLs 404 in production
            # because static(MEDIA_URL) is DEBUG-only and the render
            # container doesn't ship the local PNGs. Emit the
            # auth-gated /api/questions/images/<id>/serve/ proxy URL
            # instead so the player always has a reachable target.
            #
            # 2026-07-27: even when the ImageField is empty (e.g. the
            # material_importer publish path failed to re-load bytes
            # into `qi.file`), the row still has a usable URL in
            # `img.url` (the public Supabase / /media/ path recorded
            # at ingest time). Without this fallback, the frontend
            # renders a broken image box. See `image_url` below.
            try:
                url = self._build_image_serve_url(img)
                if not url:
                    url = self._resolve_image_url(img)
            except Exception:
                url = self._resolve_image_url(img) or ''
            out.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_index_in_page': img.image_index_in_page,
                'role': img.role,
                'modality': img.modality,
                'mime': img.mime,
                'width': img.width,
                'height': img.height,
                'url': url,
                'sha256_short': img.sha256_short,
            })
        return out

    def get_duplicate_count(self, obj):
        """Number of OTHER active Question rows in the same DuplicateCluster.

        Reads from a prefetched `_cluster_member_count` annotation when the
        queryset was annotated (admin list view does this for O(1) reads),
        otherwise falls back to a single query.
        """
        cached = getattr(obj, '_cluster_member_count', None)
        if cached is not None:
            return max(0, int(cached) - 1)
        from .models import DuplicateMember
        cluster_id = getattr(obj, '_cluster_id', None)
        if cluster_id is None:
            m = DuplicateMember.objects.filter(question_id=obj.id).values_list('cluster_id', flat=True).first()
            if m is None:
                return 0
            cluster_id = m
        return DuplicateMember.objects.filter(cluster_id=cluster_id).exclude(question_id=obj.id).count()

    def get_duplicate_cluster_id(self, obj):
        cached = getattr(obj, '_cluster_id', None)
        if cached is not None:
            return cached
        from .models import DuplicateMember
        return DuplicateMember.objects.filter(question_id=obj.id).values_list('cluster_id', flat=True).first()

    def _build_image_serve_url(self, img):
        """Return the prod-safe proxy URL for a QuestionImage.

        Uses request.build_absolute_uri when available so the player
        always hits the same origin as the API. Falls back to a
        relative path so a missing context (e.g. management shell)
        still produces a usable URL.
        """
        path = f"/api/questions/images/{img.id}/serve/"
        request = self.context.get('request') if hasattr(self, 'context') else None
        if request is not None:
            try:
                return request.build_absolute_uri(path)
            except Exception:  # noqa: BLE001
                return path
        return path

    def _resolve_image_url(self, img):
        """Pick the best URL for a QuestionImage — proxy or stored public URL."""
        # Local MEDIA / Supabase URL recorded at ingest time. These are
        # already absolute or already rooted paths. Return as-is so the
        # frontend can hit them directly without going through the proxy.
        url = (getattr(img, 'url', '') or '').strip()
        if not url:
            return ''
        if url.startswith(('http://', 'https://', '/')):
            return url
        return f"/{url.lstrip('/')}"


class QuestionAdminListSerializer(QuestionListSerializer):
    """Admin list serializer that exposes lock controls."""

    class Meta(QuestionListSerializer.Meta):
        fields = QuestionListSerializer.Meta.fields + [
            'correct_answer', 'explanation', 'paper', 
            'lock_answer', 'lock_explanation', 
            'admin_answer_override', 'admin_explanation_override',
            'video_url', 'video_status'
        ]


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with explanations, references, similar questions."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    similar = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    effective_answer = serializers.SerializerMethodField()
    effective_explanation = serializers.SerializerMethodField()
    effective_mnemonic = serializers.SerializerMethodField()
    effective_references = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    last_revision_at = serializers.SerializerMethodField()
    user_selected_answer = serializers.SerializerMethodField()
    user_is_correct = serializers.SerializerMethodField()
    video_subtitles_url = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    def to_representation(self, instance):
        """Repair mojibake on every text field at the API boundary.

        Mirror of QuestionListSerializer.to_representation — the detail
        endpoint is what powers the modal in ExamQuestionBank, so the
        Similar-PYQs sidebar (the one that was rendering
        `iÃ©iÃiÃ©iÃiÃ©`) gets clean text without a frontend pass.
        """
        data = super().to_representation(instance)
        for field in _TEXT_FIELDS:
            if field in data and isinstance(data[field], str):
                data[field] = _clean_text(data[field])
        return data

    class Meta:
        model = Question
        fields = [
            'id', 'uuid', 'display_number', 'is_dropped', 'admin_edited', 'needs_review', 'is_disputed',
            'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'year', 'subject', 'subject_name', 'topic', 'topic_name',
            'difficulty', 'concept_tags', 'concept_id', 'explanation', 'concept_explanation',
            'mnemonic', 'book_name', 'chapter', 'page_number', 'reference_text', 'paper',
            'source', 'exam_source', 'times_asked', 'is_active', 'created_at', 'updated_at',
            'textbook_references', 'learning_technique', 'shortcut_tip', 'page_screenshot',
            'is_image_based', 'images',
            'concept_keywords', 'ai_explanation', 'ai_answer', 'ai_mnemonic', 'ai_references',
            'is_verified_by_admin', 'verified_by', 'verified_at', 'verified_note',
            'similar', 'is_bookmarked', 'effective_answer', 'effective_explanation',
            'effective_mnemonic', 'effective_references', 'revision_count', 'last_revision_at',
            'user_selected_answer', 'user_is_correct', 'video_url', 'video_status',
            'video_thumbnail', 'video_duration', 'video_version', 'video_error',
            'video_generated_at', 'video_subtitles_url',
        ]

    def get_images(self, obj):
        out = []
        for img in obj.images.all():
            if not img.is_active:
                continue
            # Bug #P0-2 (2026-07-25): /media/... URLs 404 in production
            # because static(MEDIA_URL) is DEBUG-only and the render
            # container doesn't ship the local PNGs. Emit the
            # auth-gated /api/questions/images/<id>/serve/ proxy URL
            # instead so the player always has a reachable target.
            #
            # 2026-07-27: prefer `img.url` (Supabase public URL for admin
            # uploads) when present — the proxy can redirect there, but
            # handing the browser the absolute URL avoids the redirect hop
            # entirely. Falls back to proxy for recall-imported images.
            url = ''
            try:
                stored = (getattr(img, 'url', '') or '').strip()
                if stored.startswith(('http://', 'https://')):
                    url = stored
                else:
                    url = self._build_image_serve_url(img) or self._resolve_image_url(img)
            except Exception:
                url = self._resolve_image_url(img) or ''
            out.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_index_in_page': img.image_index_in_page,
                'role': img.role,
                'modality': img.modality,
                'mime': img.mime,
                'width': img.width,
                'height': img.height,
                'url': url,
                'sha256_short': img.sha256_short,
            })
        return out

    def _resolve_image_url(self, img):
        """Pick the best URL for a QuestionImage — proxy or stored public URL."""
        url = (getattr(img, 'url', '') or '').strip()
        if not url:
            return ''
        if url.startswith(('http://', 'https://', '/')):
            return url
        return f"/{url.lstrip('/')}"

    def _build_image_serve_url(self, img):
        """Return the prod-safe proxy URL for a QuestionImage.

        Uses request.build_absolute_uri when available so the player
        always hits the same origin as the API. Falls back to a
        relative path so a missing context (e.g. management shell)
        still produces a usable URL.
        """
        path = f"/api/questions/images/{img.id}/serve/"
        request = self.context.get('request') if hasattr(self, 'context') else None
        if request is not None:
            try:
                return request.build_absolute_uri(path)
            except Exception:  # noqa: BLE001
                return path
        return path

    def get_user_selected_answer(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from questions.models import QuestionAttempt
            attempt = QuestionAttempt.objects.filter(user=request.user, question=obj).first()
            if attempt:
                return attempt.selected_answer
        return None

    def get_user_is_correct(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from questions.models import QuestionAttempt
            attempt = QuestionAttempt.objects.filter(user=request.user, question=obj).first()
            if attempt:
                return attempt.is_correct
        return None

    def get_video_subtitles_url(self, obj):
        return _derive_subtitles_url(getattr(obj, 'video_url', '') or '')

    def get_similar(self, obj):
        similar_qs = obj.similar_questions.filter(is_active=True)[:5]
        return QuestionListSerializer(similar_qs, many=True, context=self.context).data

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmarks.filter(user=request.user).exists()
        return False

    def get_effective_answer(self, obj):
        if obj.lock_answer:
            return obj.admin_answer_override or obj.get_correct_option_text()
        if obj.admin_answer_override:
            return obj.admin_answer_override
        return obj.ai_answer or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        if obj.lock_explanation:
            return obj.admin_explanation_override or obj.explanation
        if obj.admin_explanation_override:
            return obj.admin_explanation_override
        ai_exp = obj.ai_explanation
        parsed = _parse_ai_explanation_to_markdown(ai_exp)
        if parsed:
            return parsed
        return ai_exp or obj.explanation

    def get_effective_mnemonic(self, obj):
        if obj.admin_mnemonic_override:
            return obj.admin_mnemonic_override
        return obj.ai_mnemonic or obj.mnemonic

    def get_effective_references(self, obj):
        if obj.admin_references_override:
            return obj.admin_references_override
        return obj.ai_references or obj.textbook_references

    def get_revision_count(self, obj):
        return obj.revision_snapshots.count()

    def get_last_revision_at(self, obj):
        latest = obj.revision_snapshots.order_by('-created_at').values_list('created_at', flat=True).first()
        return latest


class QuestionUploadSerializer(serializers.ModelSerializer):
    """Serializer for admin bulk upload."""
    class Meta:
        model = Question
        fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'correct_answer', 'year', 'subject', 'topic', 'difficulty',
                  'concept_tags', 'explanation', 'concept_explanation', 'mnemonic',
                  'book_name', 'chapter', 'page_number', 'reference_text',
                  'textbook_references', 'concept_id', 'exam_source', 'is_verified_by_admin', 'verified_note']


class BookmarkSerializer(serializers.ModelSerializer):
    question_detail = QuestionListSerializer(source='question', read_only=True)

    class Meta:
        model = QuestionBookmark
        fields = ['id', 'question', 'question_detail', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class QuestionFeedbackSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True, default='')
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = QuestionFeedback
        fields = [
            'id', 'question', 'question_text', 'user', 'username', 'category', 'comment',
            'status', 'is_resolved', 'resolution_note', 'resolved_by', 'resolved_at', 'notified_user', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'user', 'resolved_by', 'resolved_at', 'notified_user', 'is_resolved']


class DiscussionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    reply_count = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Discussion
        fields = ['id', 'question', 'user', 'username', 'parent', 'text',
                  'upvotes', 'downvotes', 'is_pinned', 'reply_count', 'user_vote',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'username', 'upvotes', 'downvotes',
                            'is_pinned', 'created_at', 'updated_at']

    def get_reply_count(self, obj):
        return obj.replies.count()

    def get_user_vote(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            vote = obj.votes.filter(user=request.user).first()
            return vote.vote_type if vote else None
        return None


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'question', 'topic', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FlashcardSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')

    class Meta:
        model = Flashcard
        fields = ['id', 'question', 'subject', 'subject_name', 'front', 'back',
                  'difficulty', 'next_review', 'review_count', 'ease_factor',
                  'interval_days', 'created_at']
        read_only_fields = ['id', 'review_count', 'ease_factor', 'interval_days',
                            'next_review', 'created_at']


class QuestionImportJobSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = QuestionImportJob
        fields = [
            'id', 'job_type', 'status', 'source_filename', 'stored_file_path',
            'summary', 'error_report', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]


class QuestionExtractionItemSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')

    class Meta:
        model = QuestionExtractionItem
        fields = [
            'id', 'job', 'status', 'raw_text', 'question_text',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'year', 'paper',
            'subject', 'subject_name', 'topic', 'topic_name',
            'tags', 'published_question', 'review_note', 'created_at', 'updated_at'
        ]


class AdminAIPromptVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = AdminAIPromptVersion
        fields = ['id', 'name', 'prompt_text', 'is_active', 'created_by', 'created_by_username', 'created_at']


class QuestionAIOperationLogSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    prompt_version_name = serializers.CharField(source='prompt_version.name', read_only=True, default='')

    class Meta:
        model = QuestionAIOperationLog
        fields = [
            'id', 'question', 'operation_type', 'provider', 'prompt_version', 'prompt_version_name',
            'tokens_used', 'response_excerpt', 'created_by', 'created_by_username', 'created_at'
        ]


class QuestionRevisionSnapshotSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source='changed_by.username', read_only=True, default='')

    class Meta:
        model = QuestionRevisionSnapshot
        fields = ['id', 'question', 'changed_by', 'changed_by_username', 'reason', 'snapshot', 'created_at']
