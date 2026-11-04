from urllib.parse import urlsplit, urlunsplit

from rest_framework import serializers

from crack_cms.public_names import public_handle
from .models import (
    Subject, Topic, Question, QuestionBookmark, QuestionFeedback,
    Discussion, Note, Flashcard, QuestionImportJob,
    QuestionExtractionItem, AdminAIPromptVersion,
    QuestionAIOperationLog, QuestionRevisionSnapshot, Announcement, ExamTrack,
    TopicNote,
    StudyTimeBreakdown, UserQuest, QuestStreak, MistakeNotebook,
)
from .text_encoding import normalize_text
from .image_access import is_image_serve_url, with_image_token
from .answer_leak import redact_public_text, redact_stem_text, row_has_answer_label
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


# List-payload fields that point at answer-linked media: the generated
# explanation video and the "screenshot of the textbook page where the answer
# is discussed" (``page_screenshot``). Hidden from viewers who are not
# entitled to the row's answer.
_LIST_ANSWER_MEDIA_FIELDS = ('video_url', 'video_thumbnail', 'video_subtitles_url', 'page_screenshot')
_LIST_ANSWER_MEDIA_RESET_FIELDS = _LIST_ANSWER_MEDIA_FIELDS + ('video_status', 'video_duration')

# Textbook reference fields of a list row, blanked (same types) on rows the
# viewer is not entitled to: ``reference_text`` is "relevant textbook content
# that directly supports the answer", ``textbook_references`` holds excerpts
# and a chapter title can name the diagnosis (questions.views
# _ANSWER_REVEALING_DETAIL_FIELDS redacts the same fields in the detail).
_LIST_REFERENCE_TEXT_FIELDS = ('reference_text', 'book_name', 'chapter', 'page_number')
_LIST_REFERENCE_LIST_FIELDS = ('textbook_references',)

# concept_tags markers that say nothing about the answer and that the
# question-bank cards read (the "High yield" badge). Every other tag is a
# concept term ("ventricular aneurysm", "jones criteria") that can name the
# answer, so locked payloads keep only these.
NON_REVEALING_CONCEPT_TAGS = frozenset({'high_yield'})


# The material_importer fallback Subject is named "Imported" (Subject.name is
# unique); it is a bucket for loader-published questions whose source had no
# detectable subject, shown to students as "Expert Curated" everywhere.
LOADER_SUBJECT_NAME = 'Imported'
PUBLIC_LOADER_SUBJECT_NAME = 'Expert Curated'


def public_subject_name(name):
    """The subject name a student sees: "Expert Curated" for the loader's
    "Imported" bucket, every other name (or non-string) unchanged."""
    if isinstance(name, str) and name.strip().lower() == LOADER_SUBJECT_NAME.lower():
        return PUBLIC_LOADER_SUBJECT_NAME
    return name


class PublicSubjectNameField(serializers.CharField):
    """Read-only ``subject.name`` with the "Imported" -> "Expert Curated"
    display rule (``public_subject_name``)."""

    def to_representation(self, value):
        return public_subject_name(super().to_representation(value))


class PublicHandleField(serializers.Field):
    """A user as other learners see them (``crack_cms.public_names.
    public_handle``): a chosen username, or ``null`` for names derived from
    an email address."""

    def __init__(self, **kwargs):
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        return public_handle(value)


def handle_or_blank(user) -> str:
    """``public_handle`` of a nullable user FK for string fields: ``''`` when
    there is no user or the username is derived from an email address."""
    return (public_handle(user) or '') if user is not None else ''


def locked_concept_tags(tags):
    """``concept_tags`` as shown on a question the viewer is not entitled to."""
    if not isinstance(tags, (list, tuple)):
        return []
    return [tag for tag in tags if isinstance(tag, str) and tag in NON_REVEALING_CONCEPT_TAGS]


def _instance_role_cache(serializer) -> dict:
    """Per-serializer-instance memo for ``resolve_runtime_image_role``.

    With ``many=True`` the child serializer is shared by every row of one
    response, so this memoises per response -- never across requests.
    """
    cache = serializer.__dict__.get('_runtime_role_memo')
    if cache is None:
        cache = {}
        serializer.__dict__['_runtime_role_memo'] = cache
    return cache


def resolve_runtime_image_role(obj, img, memo=None) -> str:
    """The role ``img`` plays in ``obj``: ``questions.image_context.runtime_role`` (one rule for every
    payload). A token in the stem or in an option is never 'explanation', also when the explanation
    cites the same figure: the exam payload drops explanation figures for everyone, and this used to
    drop an option's figure that the explanation also referenced. A token only in the explanation /
    concept explanation / mnemonic means 'explanation'."""
    from .image_context import runtime_role
    return runtime_role(obj, img, memo)


def effective_explanation_for(obj):
    """The explanation a student should see (admin lock / override, parsed
    AI explanation, then the curated explanation).

    A stored provider-failure sentence ("All AI services are temporarily
    unavailable...", persisted by older regenerate / backfill runs) is
    never served as the explanation.
    """
    if obj.lock_explanation:
        return obj.admin_explanation_override or obj.explanation
    if obj.admin_explanation_override:
        return obj.admin_explanation_override
    from .ai_per_question import usable_ai_text
    ai_exp = usable_ai_text(obj.ai_explanation)
    parsed = _parse_ai_explanation_to_markdown(ai_exp)
    if parsed and usable_ai_text(parsed):
        return parsed
    return ai_exp or obj.explanation


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
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'paper', 'description', 'icon', 'color', 'question_count']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The material_importer fallback Subject is named "Imported" so DB
        # integrity is preserved (Subject.name is unique). It is NOT a real
        # medical subject — it's a bucket for loader-published questions
        # whose source material had no detectable subject line. Rename it
        # at serialization time so the question-bank filter dropdown shows
        # a clean "Expert Curated" label instead of leaking the loader
        # literal. See: docs/audit/COMPREHENSIVE_AUDIT_2026_07_30.md.
        if 'name' in data:
            data['name'] = public_subject_name(data['name'])
        return data


class TopicSerializer(serializers.ModelSerializer):
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Topic
        fields = ['id', 'name', 'subject', 'subject_name', 'parent',
                  'importance', 'description', 'question_count']


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    is_bookmarked = serializers.SerializerMethodField()
    is_showcase = serializers.SerializerMethodField()
    # Every visitor reads the list: the verifying admin's chosen username
    # only, never one derived from their email address.
    verified_by_username = serializers.SerializerMethodField()
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
    stem_images = serializers.SerializerMethodField()
    duplicate_count = serializers.SerializerMethodField()
    duplicate_cluster_id = serializers.SerializerMethodField()

    def _resolve_runtime_role(self, obj, img) -> str:
        """Reclassify `img.role` based on which text fields reference its id.

        Belt-and-suspenders for the explanation-image leak: even if a row
        was uploaded with the wrong role (e.g. via the pre-fix upload path
        that didn't forward `role=`), the API response can correct it on
        the fly. Heuristic:
          * If the question's `question_text` references this image via
            a `[[img:N]]` token, the row is a legitimate stem image.
          * Otherwise, if `explanation`, `concept_explanation`, or
            `mnemonic` references it, the row is explanation-attached.
          * Otherwise, leave the stored role alone.

        Memoised per serializer instance (i.e. per response) so a list of N
        rows only does the text-token scan once per question. It used to be
        a class-level dict that lived for the whole process, so role edits
        and new ``[[img:N]]`` tokens were ignored until a restart.
        """
        return resolve_runtime_image_role(obj, img, _instance_role_cache(self))

    def to_representation(self, instance):
        """Repair mojibake on every text field at the API boundary AND
        rename the loader-created "Imported" Subject to "Expert Curated".

        Without this pass, a Question row imported with a Windows-1252 /
        Latin-1 locale (the legacy fixture path) leaves `iÃ©iÃiÃ©` in the
        JSON payload — the frontend is then forced to call
        `decodeMojiB()` on every render. Normalizing here means the API
        ships clean text and the frontend guard becomes a true
        defence-in-depth (instead of the *only* line of defence).

        The SubjectSerializer handles the same rename for `/subjects/`,
        but `subject_name` on Question is a CharField that reads
        `subject.name` directly through the FK — bypassing the Subject
        serializer. Apply the same rename here so the question-bank list
        and detail payloads never leak the loader literal "Imported".
        See commit a4a96a5 for the original Subject fix and
        `merge_loader_fallback_subjects` for the underlying DB cleanup.
        """
        data = super().to_representation(instance)
        for field in _TEXT_FIELDS:
            if field in data and isinstance(data[field], str):
                data[field] = _clean_text(data[field])
        if 'subject_name' in data:
            data['subject_name'] = public_subject_name(data['subject_name'])
        # Some imports left the answer key or the explanation inside the
        # stem / an option ("... Correct Answer: B. ...", "Explanation: ...")
        # or flagged an option ("... ✔ (reason)", "(correct)"; also on the
        # options a stem lists): a locked row shows that text only up to the
        # first such label, without the flags (questions.answer_leak).
        leaky = row_has_answer_label(data)
        if (leaky or self._row_may_reveal(data)) and not self._row_answer_visible(instance):
            self._redact_locked_row(data)
            if leaky:
                redact_public_text(data)
        return data

    @staticmethod
    def _row_may_reveal(data) -> bool:
        """True when the row carries anything that is hidden on locked rows
        (most rows carry nothing, so the entitlement lookup is skipped)."""
        if any(data.get(field) for field in _LIST_ANSWER_MEDIA_FIELDS):
            return True
        if any(data.get(field) for field in _LIST_REFERENCE_TEXT_FIELDS + _LIST_REFERENCE_LIST_FIELDS):
            return True
        if data.get('user_is_correct') is not None or data.get('user_selected_answer'):
            return True
        tags = data.get('concept_tags')
        if isinstance(tags, list) and any(tag not in NON_REVEALING_CONCEPT_TAGS for tag in tags):
            return True
        return any((img or {}).get('role') == 'explanation' for img in (data.get('images') or []))

    @staticmethod
    def _redact_locked_row(data) -> None:
        """Hide answer-linked content of a row the viewer is not entitled to
        (premium / admin / free showcase), keeping each field's type."""
        # A generated explanation video explains the answer: same
        # entitlement as the answer itself.
        for field in _LIST_ANSWER_MEDIA_RESET_FIELDS:
            if field in data:
                data[field] = None
        for field in _LIST_REFERENCE_TEXT_FIELDS:
            if field in data:
                data[field] = ''
        for field in _LIST_REFERENCE_LIST_FIELDS:
            if field in data:
                data[field] = []
        if 'concept_tags' in data:
            data['concept_tags'] = locked_concept_tags(data.get('concept_tags'))
        # The viewer's own right / wrong on a locked row (answered while a
        # plan was active) names its answer. The pick goes too: the cards
        # render a pick without a verdict as "Incorrect".
        for field in ('user_is_correct', 'user_selected_answer'):
            if field in data:
                data[field] = None
        if isinstance(data.get('images'), list):
            # Explanation figures belong to the explanation (``stem_images``
            # never carries them).
            data['images'] = [img for img in data['images'] if (img or {}).get('role') != 'explanation']

    def _viewer_full_access(self) -> bool:
        """Premium / admin / staff viewer -- computed once per response."""
        context = self.context if hasattr(self, 'context') else {}
        cached = context.get('viewer_full_access')
        if cached is not None:
            return bool(cached)
        request = context.get('request')
        user = getattr(request, 'user', None)
        value = False
        if user is not None and getattr(user, 'is_authenticated', False):
            if self._is_admin():
                value = True
            else:
                try:
                    from accounts.utils import is_premium
                    value = bool(is_premium(user))
                except Exception:  # pragma: no cover - defensive
                    value = False
        try:
            context['viewer_full_access'] = value
        except TypeError:  # pragma: no cover - immutable context
            pass
        return value

    def _row_answer_visible(self, obj) -> bool:
        if self._viewer_full_access():
            return True
        showcase = getattr(obj, 'is_showcase', None)
        if showcase is None:
            # Not annotated (e.g. recall search / bookmarks / similar):
            # the free showcase ids are read once per response, not once
            # per row (only rows that carry answer media get here).
            showcase = bool(obj.pk) and obj.pk in self._free_showcase_ids()
        return bool(showcase)

    def _free_showcase_ids(self) -> set:
        """Ids of the free showcase questions, memoised in the (per-response)
        serializer context -- shared by nested / many=True children."""
        context = self.context if hasattr(self, 'context') else {}
        ids = context.get('_free_showcase_question_ids') if isinstance(context, dict) else None
        if ids is None:
            from accounts.models_freemium import FreeShowcaseQuestion
            # Same rule as questions.views.free_showcase_rows: scholarship
            # questions are never free content.
            ids = set(
                FreeShowcaseQuestion.objects.filter(question__is_scholarship_eligible=False)
                .values_list('question_id', flat=True)
            )
            if isinstance(context, dict):
                context['_free_showcase_question_ids'] = ids
        return ids

    class Meta:
        model = Question
        fields = ['id', 'uuid', 'display_number', 'is_dropped', 'admin_edited', 'needs_review',
                  'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'year', 'subject', 'subject_name',
                  'topic', 'topic_name', 'difficulty', 'exam_source',
                  'concept_tags', 'concept_id', 'book_name', 'chapter', 'page_number', 'reference_text',
                  'textbook_references', 'is_bookmarked', 'is_showcase', 'is_verified_by_admin',
                  'verified_at', 'verified_by', 'verified_by_username',
                  'effective_answer', 'effective_explanation',
                  'revision_count', 'last_revision_at', 'related_question_ids', 'accuracy',
                  'user_selected_answer', 'user_is_correct', 'video_url', 'video_status',
                  'video_thumbnail', 'video_duration', 'video_subtitles_url',
                  'is_image_based', 'page_screenshot', 'images', 'stem_images',
                  'duplicate_count', 'duplicate_cluster_id']

    def get_is_bookmarked(self, obj):
        return bool(getattr(obj, 'is_bookmarked', False))

    def get_is_showcase(self, obj):
        # `is_showcase` is annotated in QuestionViewSet.get_queryset via an
        # Exists() subquery on FreeShowcaseQuestion. Fallback to False for
        # serializers instantiated outside the list view (e.g. tests).
        return bool(getattr(obj, 'is_showcase', False))

    def get_verified_by_username(self, obj):
        return handle_or_blank(obj.verified_by) if obj.verified_by_id else ''

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
        from .ai_per_question import usable_ai_text
        return usable_ai_text(obj.ai_answer) or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        # Same leak as effective_answer — the full explanation text was
        # being returned in every list payload, defeating the
        # assessment for any student willing to open DevTools.
        if not self._is_admin():
            return None
        return effective_explanation_for(obj)

    def get_revision_count(self, obj):
        return getattr(obj, 'revision_count', 0) or 0

    def get_last_revision_at(self, obj):
        return getattr(obj, 'last_revision_at', None)

    def get_related_question_ids(self, obj):
        related_ids = getattr(obj, 'related_question_ids', None)
        if related_ids is not None:
            return list(related_ids)
        # The admin editor's "related PYQs" field: read the curated M2M from
        # the ``similar_questions`` prefetch (QuestionViewSet.queryset). The
        # old code only read a never-set attribute, so it was always [].
        # Without the prefetch nothing is queried (no per-row lookups).
        prefetched = (getattr(obj, '_prefetched_objects_cache', None) or {}).get('similar_questions')
        if prefetched is not None:
            return sorted(q.id for q in prefetched)
        return []

    def get_accuracy(self, obj):
        # Only annotated for admins / accuracy filters (see
        # QuestionViewSet.get_queryset); the missing return made the admin
        # "Acc: X%" badge never render.
        value = getattr(obj, 'accuracy', None)
        if value is None:
            return None
        try:
            return round(float(value), 1)
        except (TypeError, ValueError):
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
            # Bug fix 2026-08-01 (belt-and-suspenders): reclassify the role
            # at response time so stale admin uploads with the wrong role
            # are corrected before reaching the client. `get_stem_images`
            # then drops these rows from the stem-pane list. See
            # _resolve_runtime_role.
            role = self._resolve_runtime_role(obj, img)
            if role == 'explanation' and is_image_serve_url(url) and self._row_answer_visible(obj):
                # The serve endpoint returns an explanation figure only with
                # a signed token, issued to viewers entitled to the answer
                # (questions.image_access).
                url = with_image_token(url, img.id)
            out.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_index_in_page': img.image_index_in_page,
                'role': role,
                'modality': img.modality,
                'mime': img.mime,
                'width': img.width,
                'height': img.height,
                'url': url,
                'sha256_short': img.sha256_short,
            })
        return out

    def get_stem_images(self, obj):
        """List-serializer variant of `get_stem_images`.

        Same semantics as the detail-serializer version: returns the
        `images` list with `role='explanation'` rows filtered out so
        the list cards / previews don't show explanation figures. Full
        `images` list is still returned (for `[[img:N]]` token resolution).
        """
        return [img for img in self.get_images(obj) if img.get('role') != 'explanation']

    def get_duplicate_count(self, obj):
        """Total rows in the same DuplicateCluster (including self).

        Semantically "how many copies of this question exist in the bank" —
        the admin UI uses this to show "⚠ Duplicate ×N" and the merge
        modal derives the sibling list separately. Returns 0 when the row
        is not part of any cluster (the common case for unique questions).

        Reads the ``cluster_size`` annotation on the prefetched
        ``cluster_memberships`` (QuestionViewSet / bookmarks / similar
        prefetch it) so clustered rows cost no extra query; otherwise falls
        back to a single query.
        """
        cached = getattr(obj, '_cluster_member_count', None)
        if cached is not None:
            return max(0, int(cached))
        prefetched = (getattr(obj, '_prefetched_objects_cache', None) or {}).get('cluster_memberships')
        if prefetched is not None:
            members = list(prefetched)
            if not members:
                return 0
            newest = max(members, key=lambda m: (m.cluster_id, m.similarity_score or 0))
            size = getattr(newest, 'cluster_size', None)
            if size is not None:
                return max(0, int(size))
        from .models import DuplicateMember
        cluster_id = getattr(obj, '_cluster_id', None)
        if cluster_id is None:
            cluster_id = self.get_duplicate_cluster_id(obj)
            if cluster_id is None:
                return 0
        return DuplicateMember.objects.filter(cluster_id=cluster_id).count()

    def get_duplicate_cluster_id(self, obj):
        cached = getattr(obj, '_cluster_id', None)
        if cached is not None:
            return cached
        # Use the `cluster_memberships` prefetch from QuestionViewSet when
        # present -- the previous per-row query made the list endpoint
        # O(page_size) queries (N+1). Unique questions (the common case)
        # now cost zero extra queries.
        prefetched = (getattr(obj, '_prefetched_objects_cache', None) or {}).get('cluster_memberships')
        if prefetched is not None:
            members = list(prefetched)
            if not members:
                return None
            newest = max(members, key=lambda m: (m.cluster_id, m.similarity_score or 0))
            return newest.cluster_id
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
    """Admin list serializer that exposes lock controls + AI explanation fields."""

    class Meta(QuestionListSerializer.Meta):
        fields = QuestionListSerializer.Meta.fields + [
            'correct_answer', 'explanation', 'paper',
            'lock_answer', 'lock_explanation',
            'admin_answer_override', 'admin_explanation_override',
            'video_url', 'video_status',
            # AI explanation fields populated by admin AI generation
            'concept_explanation', 'mnemonic', 'concept_keywords',
            'book_name', 'chapter', 'page_number', 'reference_text',
            'shortcut_tip', 'why_correct',
            'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d',
            # The editor's checkbox starts from the real value, and the
            # first save of a list row can send ``If-Match: <updated_at>``.
            'is_controversial', 'updated_at',
            # Contract C10: the editor's drag-renumber refuses removed
            # (inactive) rows, so admin rows say whether they are active.
            'is_active',
        ]


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Full serializer with explanations, references, similar questions."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    similar = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    effective_answer = serializers.SerializerMethodField()
    effective_explanation = serializers.SerializerMethodField()
    explanation_overridden = serializers.SerializerMethodField()
    effective_mnemonic = serializers.SerializerMethodField()
    effective_references = serializers.SerializerMethodField()
    revision_count = serializers.SerializerMethodField()
    last_revision_at = serializers.SerializerMethodField()
    user_selected_answer = serializers.SerializerMethodField()
    user_is_correct = serializers.SerializerMethodField()
    video_subtitles_url = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    # Subset of `images` that should appear next to the question stem.
    # Excludes `role='explanation'` so admin-uploaded explanation figures
    # stop leaking into the stem pane before the student has even picked
    # an answer. `images` is still returned (unchanged) so `[[img:N]]`
    # tokens inside the explanation text still resolve via the
    # `resolveImageTokensForMarkdown` resolver — admins only lose the
    # *duplicate* render of those figures, not their inline rendering.
    # Bug: 2026-08-01 admin-uploaded explanation image shown next to
    # the question stem before any attempt.
    stem_images = serializers.SerializerMethodField()

    def _resolve_runtime_role(self, obj, img) -> str:
        # Per-response memo (was a process-wide class attribute).
        return resolve_runtime_image_role(obj, img, _instance_role_cache(self))

    def to_representation(self, instance):
        """Repair mojibake on every text field at the API boundary AND
        rename the loader-created "Imported" Subject to "Expert Curated".

        Mirror of QuestionListSerializer.to_representation — the detail
        endpoint is what powers the modal in ExamQuestionBank, so the
        Similar-PYQs sidebar (the one that was rendering
        `iÃ©iÃiÃ©iÃiÃ©`) gets clean text without a frontend pass.

        Also rename the loader's "Imported" Subject name to "Expert Curated"
        on the way out so the right-panel detail card's chips never leak
        the loader literal. See the same change in QuestionListSerializer.
        """
        data = super().to_representation(instance)
        for field in _TEXT_FIELDS:
            if field in data and isinstance(data[field], str):
                data[field] = _clean_text(data[field])
        if 'subject_name' in data:
            data['subject_name'] = public_subject_name(data['subject_name'])
        # Answer key / explanation text or a correctness flag an import left
        # in the stem or an option (questions.answer_leak): cut for a viewer
        # who may not read this question's answer, like the answer fields.
        if row_has_answer_label(data) and not self._viewer_can_view_answer(instance):
            redact_public_text(data)
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
            'is_image_based', 'images', 'stem_images',
            # Per-option rationale + review flag: written by the admin editor
            # (PATCH /questions/<id>/), redacted for non-entitled readers.
            'why_correct', 'why_wrong_a', 'why_wrong_b', 'why_wrong_c', 'why_wrong_d',
            'is_controversial',
            'concept_keywords', 'ai_explanation', 'ai_answer', 'ai_mnemonic', 'ai_references',
            'is_verified_by_admin', 'verified_by', 'verified_at', 'verified_note',
            'similar', 'is_bookmarked', 'effective_answer', 'effective_explanation',
            'explanation_overridden',
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
            # Bug fix 2026-08-01 (belt-and-suspenders): reclassify the role
            # at response time so stale admin uploads with the wrong role
            # are corrected before reaching the client. See
            # _resolve_runtime_role.
            role = self._resolve_runtime_role(obj, img)
            if role == 'explanation' and is_image_serve_url(url) and self._viewer_can_view_answer(obj):
                # Explanation figures are served only with a signed token
                # (questions.image_access), issued to entitled viewers.
                url = with_image_token(url, img.id)
            out.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_index_in_page': img.image_index_in_page,
                'role': role,
                'modality': img.modality,
                'mime': img.mime,
                'width': img.width,
                'height': img.height,
                'url': url,
                'sha256_short': img.sha256_short,
            })
        return out

    def get_stem_images(self, obj):
        """Return only the images that belong next to the question stem.

        Excludes `role='explanation'` so admin-uploaded explanation
        figures (which the admin editor's `[[img:N]]` token already
        renders inside the explanation text) do not get double-rendered
        in the stem pane before the student attempts the question.

        `images` is kept untouched so `resolveImageTokensForMarkdown`
        can still resolve the `[[img:N]]` tokens in explanation /
        mnemonic / concept_explanation text via the same ID lookup.
        """
        return [img for img in self.get_images(obj) if img.get('role') != 'explanation']

    def _viewer_can_view_answer(self, obj) -> bool:
        """``questions.views.user_can_view_answer`` for the requesting user,
        memoised per question for this response (``get_images`` runs for
        both ``images`` and ``stem_images``)."""
        memo = self.__dict__.setdefault('_viewer_answer_access_memo', {})
        if obj.pk not in memo:
            from .views import user_can_view_answer  # views imports this module
            context = self.context if hasattr(self, 'context') else {}
            request = context.get('request')
            # QuestionViewSet puts "staff or premium" in the context.
            full_access = context.get('viewer_full_access')
            memo[obj.pk] = bool(full_access) or user_can_view_answer(
                getattr(request, 'user', None), obj,
                premium=None if full_access is None else bool(full_access),
            )
        return memo[obj.pk]

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
        from django.db.models import Count, Prefetch
        from .models import DuplicateMember
        similar_qs = (
            obj.similar_questions.filter(is_active=True)
            .select_related('subject', 'topic', 'verified_by')
            .prefetch_related(
                'images',
                Prefetch('cluster_memberships',
                         queryset=DuplicateMember.objects.annotate(cluster_size=Count('cluster__members'))),
            )[:5]
        )
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
        from .ai_per_question import usable_ai_text
        return usable_ai_text(obj.ai_answer) or obj.get_correct_option_text()

    def get_effective_explanation(self, obj):
        return effective_explanation_for(obj)

    def get_explanation_overridden(self, obj):
        # An admin lock / override decides the explanation
        # (effective_explanation_for serves it first), so the practice UI
        # (frontend practiceData.pickExplanation) shows effective_explanation
        # ahead of the raw curated ``explanation`` when this is true.
        return bool(obj.lock_explanation or (obj.admin_explanation_override or '').strip())

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
        # Moderation fields are set only by the admin status / resolve
        # actions -- reporters (including anonymous ones) could create a
        # report that was already "resolved" with their own note.
        read_only_fields = ['id', 'created_at', 'user', 'status', 'resolution_note', 'resolved_by',
                            'resolved_at', 'notified_user', 'is_resolved']

    # Anyone may report a question (QuestionFeedbackViewSet.create is
    # AllowAny) and the 201 echoed the raw stem: one spam report read the
    # unredacted stem of any row -- a locked one with a ticked option / an
    # "Ans: (b)" line, or a removed / held one (is_active=False). Only staff
    # (the moderation queue) see the raw stem; other reporters report on the
    # active bank and get the stem as the question bank shows it to them.

    def _viewer(self):
        return getattr(self.context.get('request'), 'user', None)

    def _viewer_is_staff(self) -> bool:
        from .views import _is_staff_user  # lazy: views imports this module
        return _is_staff_user(self._viewer())

    def get_fields(self):
        fields = super().get_fields()
        question = fields.get('question')
        if question is not None and not question.read_only and not self._viewer_is_staff():
            question.queryset = Question.objects.filter(is_active=True)
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        text = data.get('question_text')
        if text and not self._viewer_is_staff():
            from .views import user_can_view_answer  # lazy: views imports this module
            question = getattr(instance, 'question', None)
            if question is None or not question.is_active:
                data['question_text'] = ''
            elif not user_can_view_answer(self._viewer(), question):
                data['question_text'] = redact_stem_text(text)
        return data


class DiscussionSerializer(serializers.ModelSerializer):
    # Other learners read these threads: a chosen username, or null when the
    # username is derived from the author's email (the UI shows a neutral label).
    username = PublicHandleField(source='user')
    reply_count = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Discussion
        fields = ['id', 'question', 'user', 'username', 'parent', 'text',
                  'upvotes', 'downvotes', 'is_pinned', 'reply_count', 'user_vote',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'username', 'upvotes', 'downvotes',
                            'is_pinned', 'created_at', 'updated_at']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parent = attrs.get('parent', getattr(self.instance, 'parent', None))
        question = attrs.get('question', getattr(self.instance, 'question', None))
        if parent is not None and question is not None and parent.question_id != question.id:
            raise serializers.ValidationError({'parent': 'A reply must belong to the same question as its parent.'})
        return attrs

    def get_reply_count(self, obj):
        # Annotated by the discussion list views (one query per page
        # instead of one per thread).
        annotated = getattr(obj, 'reply_count_annotated', None)
        if annotated is not None:
            return annotated
        return obj.replies.count()

    def get_user_vote(self, obj):
        viewer_votes = getattr(obj, 'viewer_votes', None)
        if viewer_votes is not None:
            return viewer_votes[0].vote_type if viewer_votes else None
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
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')

    class Meta:
        model = Flashcard
        fields = ['id', 'question', 'subject', 'subject_name', 'front', 'back',
                  'difficulty', 'personal_note', 'next_review', 'review_count', 'ease_factor',
                  'interval_days', 'total_reviews', 'lapses', 'created_at']
        read_only_fields = ['id', 'review_count', 'ease_factor', 'interval_days',
                            'total_reviews', 'lapses', 'next_review', 'created_at']


class QuestionImportJobSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = QuestionImportJob
        # ``stored_file_path`` is left out: recall-import jobs store server
        # filesystem paths there (importers.neetpg), and this list shows
        # every QuestionImportJob.
        fields = [
            'id', 'job_type', 'status', 'source_filename',
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


class TopicNoteSerializer(serializers.ModelSerializer):
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    # Published notes are listed to students: no email-derived author name.
    created_by_username = serializers.SerializerMethodField()

    class Meta:
        model = TopicNote
        fields = [
            'id', 'subject', 'subject_name', 'topic', 'topic_name',
            'exam_type', 'is_combined', 'is_active', 'title', 'content',
            'content_preview', 'source_question_ids', 'source_question_count',
            'ai_generated', 'is_published',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by',
                            'content_preview', 'source_question_count', 'ai_generated']
        # An admin may save an empty draft (and fill it with AI later); the
        # notes page used to send placeholder text because '' was rejected.
        extra_kwargs = {'content': {'allow_blank': True, 'required': False}}

    def get_created_by_username(self, obj):
        return handle_or_blank(obj.created_by) if obj.created_by_id else ''

    def validate(self, attrs):
        attrs = super().validate(attrs)
        content = attrs.get('content', getattr(self.instance, 'content', '') or '')
        published = attrs.get('is_published', getattr(self.instance, 'is_published', False))
        if published and not str(content or '').strip():
            raise serializers.ValidationError({'content': 'A published note needs content.'})
        return attrs

    def validate_source_question_ids(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Must be a list of question ids.')
        cleaned = []
        for item in value:
            try:
                cleaned.append(int(item))
            except (TypeError, ValueError):
                raise serializers.ValidationError('Question ids must be integers.')
        return sorted(set(cleaned))[:500]


# ════════════════════════════════════════════════════════════════════════════
# Student Experience — Study Analytics & Gamification Serializers
# ════════════════════════════════════════════════════════════════════════════

class StudyTimeBreakdownSerializer(serializers.ModelSerializer):
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')
    subject_code = serializers.CharField(source='subject.code', read_only=True, default='')
    subject_color = serializers.CharField(source='subject.color', read_only=True, default='')

    class Meta:
        model = StudyTimeBreakdown
        fields = ['id', 'user', 'subject', 'subject_name', 'subject_code', 'subject_color',
                  'date', 'seconds', 'question_count']
        read_only_fields = ['id', 'user']


class UserQuestSerializer(serializers.ModelSerializer):
    progress_percent = serializers.IntegerField(read_only=True)
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')

    class Meta:
        model = UserQuest
        fields = ['id', 'user', 'quest_type', 'difficulty', 'title', 'description',
                  'target_value', 'current_value', 'xp_reward', 'is_completed', 'is_claimed',
                  'progress_percent', 'subject_name', 'quest_date', 'expires_at',
                  'completed_at', 'created_at']
        # Everything is server-controlled: students can only *claim* a
        # quest via the detail endpoint (see questions.quest_service).
        read_only_fields = fields


class UserQuestAdminSerializer(serializers.ModelSerializer):
    """Admin-only quest creation (can target any user)."""

    class Meta:
        model = UserQuest
        fields = ['id', 'user', 'quest_type', 'difficulty', 'title', 'description',
                  'target_value', 'xp_reward', 'quest_date', 'expires_at']
        read_only_fields = ['id']
        extra_kwargs = {'user': {'required': False}}


class QuestStreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestStreak
        fields = ['id', 'user', 'current_streak', 'longest_streak', 'total_quests_completed',
                  'total_xp_earned', 'last_quest_date', 'streak_frozen', 'updated_at']
        read_only_fields = ['id', 'user']


class MistakeNotebookSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True, default='')
    option_a = serializers.CharField(source='question.option_a', read_only=True, default='')
    option_b = serializers.CharField(source='question.option_b', read_only=True, default='')
    option_c = serializers.CharField(source='question.option_c', read_only=True, default='')
    option_d = serializers.CharField(source='question.option_d', read_only=True, default='')
    correct_answer = serializers.CharField(source='question.correct_answer', read_only=True, default='')
    explanation = serializers.CharField(source='question.explanation', read_only=True, default='')
    subject_name = PublicSubjectNameField(source='question.subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='question.topic.name', read_only=True, default='')
    exam_type = serializers.CharField(source='question.exam_type', read_only=True, default='')

    class Meta:
        model = MistakeNotebook
        fields = ['id', 'user', 'question', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                  'selected_answer', 'correct_answer', 'is_correct', 'review_status',
                  'review_count', 'last_reviewed_at', 'next_review_at', 'is_flagged',
                  'user_note', 'explanation', 'subject_name', 'topic_name', 'exam_type', 'created_at']
        # Review bookkeeping is server-side (the review endpoint) -- a PATCH
        # could set ``last_reviewed_at`` / ``review_status`` and complete the
        # "Review 5 mistakes" quest, or re-point the entry at another question.
        read_only_fields = ['id', 'user', 'question', 'selected_answer', 'correct_answer', 'is_correct',
                            'review_status', 'review_count', 'last_reviewed_at', 'next_review_at',
                            'created_at']


class MistakeNotebookCreateSerializer(serializers.ModelSerializer):
    """Create a mistake entry directly from a question attempt."""
    class Meta:
        model = MistakeNotebook
        fields = ['question', 'selected_answer', 'correct_answer', 'is_correct',
                  'attempt', 'review_status', 'user_note']
        read_only_fields = ['user']


class TopicNoteListSerializer(serializers.ModelSerializer):
    """Lite serializer for listing notes without full content."""
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    # Published notes are listed to students: no email-derived author name.
    created_by_username = serializers.SerializerMethodField()

    class Meta:
        model = TopicNote
        fields = ['id', 'exam_type', 'subject', 'subject_name', 'topic', 'topic_name',
                  'title', 'content_preview', 'ai_generated', 'source_question_count',
                  'created_by_username', 'is_published', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_username(self, obj):
        return handle_or_blank(obj.created_by) if obj.created_by_id else ''
