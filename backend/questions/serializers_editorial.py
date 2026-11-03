"""Serializers for editorial actions: answer-key changes, suggestions, provenance (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group).
"""
from __future__ import annotations

from rest_framework import serializers

from questions.models import AnswerKeyChange, ExplanationSuggestion, Question


class AnswerKeyChangeSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(source="changed_by.username", read_only=True, default="")
    rescored_by_username = serializers.CharField(source="rescored_by.username", read_only=True, default="")

    class Meta:
        model = AnswerKeyChange
        fields = [
            "id",
            "question_id",
            "old_key",
            "new_key",
            "changed_at",
            "changed_by_username",
            "source",
            "reason",
            "evidence",
            "explanation_action",
            "rescore_status",
            "rescored_at",
            "rescored_by_username",
        ]
        read_only_fields = fields


class ChangeAnswerKeyRequestSerializer(serializers.Serializer):
    new_key = serializers.ChoiceField(choices=["A", "B", "C", "D"])
    reason = serializers.CharField(min_length=10, max_length=1000)
    evidence = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    source = serializers.CharField(max_length=32, required=False, default="editor")
    explanation_fields = serializers.DictField(required=False, default=dict)


class ExplainOptionRequestSerializer(serializers.Serializer):
    selected = serializers.ChoiceField(choices=["A", "B", "C", "D"])
    draft = serializers.DictField(required=False, default=dict)
    acknowledge_conflict = serializers.BooleanField(required=False, default=False)


class ExplanationSuggestionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True, default="")

    class Meta:
        model = ExplanationSuggestion
        fields = [
            "id",
            "question_id",
            "requested_by_username",
            "created_at",
            "for_key",
            "stored_key",
            "mode",
            "provider",
            "model",
            "status",
            "fields",
            "field_citations",
            "citations",
            "dropped_claims",
            "option_evidence",
            "conflict",
            "image_context",
        ]
        read_only_fields = fields


class SaveExplanationRequestSerializer(serializers.Serializer):
    fields = serializers.DictField()
    for_key = serializers.ChoiceField(choices=["A", "B", "C", "D"], required=False, allow_blank=True)
    suggestion_id = serializers.UUIDField(required=False, allow_null=True)

