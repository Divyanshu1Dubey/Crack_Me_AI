"""Serializers of the topic-notes builder routes (2026-11, notes group).

``PublishedTopicNoteSerializer`` is what students read (list and detail): the content comes from
``notes_builder.viewer_view`` (filtered per viewer, passed as ``context['view']``), never the stored
markdown of a note the viewer is not entitled to, and there is no author field.
"""
from __future__ import annotations

from rest_framework import serializers

from questions import notes_builder as nb
from questions.models import TopicNote, TopicNoteSource
from questions.serializers import PublicSubjectNameField


def _preview(content: str) -> str:
    content = content or ''
    return content if len(content) <= 300 else content[:300] + '...'


class PublishedTopicNoteSerializer(serializers.ModelSerializer):
    subject_name = PublicSubjectNameField(source='subject.name', read_only=True, default='')
    topic_name = serializers.CharField(source='topic.name', read_only=True, default='')
    content = serializers.SerializerMethodField()
    content_preview = serializers.SerializerMethodField()
    source_question_ids = serializers.SerializerMethodField()
    source_question_count = serializers.SerializerMethodField()
    answers_locked = serializers.SerializerMethodField()
    locked_points = serializers.SerializerMethodField()
    hidden_points = serializers.SerializerMethodField()

    class Meta:
        model = TopicNote
        fields = [
            'id', 'subject', 'subject_name', 'topic', 'topic_name', 'exam_type', 'is_combined', 'is_active',
            'title', 'content', 'content_preview', 'source_question_ids', 'source_question_count',
            'ai_generated', 'is_published', 'generation_method', 'builder_version', 'built_at', 'is_stale',
            'verified_source_count', 'provisional_source_count', 'answers_locked', 'locked_points',
            'hidden_points', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def _view(self, obj) -> dict:
        view = (self.context.get('views') or {}).get(obj.pk) or self.context.get('view')
        if view is None:   # no viewer context: the most restrictive reading
            view = nb.viewer_view(obj, full_access=False, free_ids=set())
        return view

    def get_content(self, obj):
        return self._view(obj)['content']

    def get_content_preview(self, obj):
        return _preview(self._view(obj)['content'])

    def get_source_question_ids(self, obj):
        return self._view(obj)['source_question_ids']

    def get_source_question_count(self, obj):
        return len(self._view(obj)['source_question_ids'])

    def get_answers_locked(self, obj):
        return bool(self._view(obj)['answers_locked'])

    def get_locked_points(self, obj):
        return self._view(obj)['locked_points']

    def get_hidden_points(self, obj):
        return self._view(obj)['hidden_points']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get('detail'):
            view = self._view(instance)
            data['sections'] = view['sections']
            data['points'] = view['points']
        return data


class TopicNoteSourceSerializer(serializers.ModelSerializer):
    """Admin view of one source question of a built note."""
    stem_preview = serializers.SerializerMethodField()
    asked_in = serializers.SerializerMethodField()
    current_key = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    changed_since_build = serializers.SerializerMethodField()

    class Meta:
        model = TopicNoteSource
        fields = ['question', 'key_status', 'reason', 'cited', 'answer_at_build', 'current_key', 'is_active',
                  'changed_since_build', 'stem_preview', 'asked_in', 'created_at']
        read_only_fields = fields

    def get_stem_preview(self, obj):
        return nb._cut(nb.clean_stem(obj.question.question_text), 160)

    def get_asked_in(self, obj):
        return nb.asked_in_label(obj.question)

    def get_current_key(self, obj):
        return (obj.question.correct_answer or '').strip().upper()[:1]

    def get_is_active(self, obj):
        return bool(obj.question.is_active and not obj.question.is_dropped)

    def get_changed_since_build(self, obj):
        return obj.question_id in (self.context.get('hidden') or set())
