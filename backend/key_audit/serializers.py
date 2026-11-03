"""Serializers for the answer-key audit and review queue."""
from __future__ import annotations

from rest_framework import serializers

from key_audit.models import AuditResolution, QuestionAudit, ReviewClaim
from questions.content_hashes import valid_key
from questions.models import Question


class QuestionAuditListSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.question_text", read_only=True)
    exam_type = serializers.CharField(source="question.exam_type", read_only=True)
    year = serializers.IntegerField(source="question.year", read_only=True)
    subject = serializers.CharField(source="question.subject.name", default="", read_only=True)

    class Meta:
        model = QuestionAudit
        fields = [
            "id",
            "question_id",
            "status",
            "status_reason",
            "stored_key",
            "suggested_key",
            "priority",
            "confidence",
            "signals",
            "evidence_summary",
            "is_stale",
            "audited_at",
            "question_text",
            "exam_type",
            "year",
            "subject",
        ]


class AuditResolutionSerializer(serializers.ModelSerializer):
    resolved_by_username = serializers.CharField(source="resolved_by.username", default="", read_only=True)

    class Meta:
        model = AuditResolution
        fields = [
            "id",
            "resolution",
            "reason",
            "evidence",
            "status_before",
            "resolved_by_username",
            "resolved_at",
        ]


class QuestionAuditDetailSerializer(serializers.ModelSerializer):
    question_details = serializers.SerializerMethodField()
    resolutions = AuditResolutionSerializer(many=True, read_only=True)
    claimed_by_username = serializers.CharField(source="question.review_claim.claimed_by.username", default=None, read_only=True)

    class Meta:
        model = QuestionAudit
        fields = [
            "id",
            "question_id",
            "status",
            "status_reason",
            "stored_key",
            "original_key",
            "key_provenance",
            "suggested_key",
            "confidence",
            "priority",
            "signals",
            "reviews",
            "evidence_summary",
            "is_stale",
            "audited_at",
            "question_details",
            "resolutions",
            "claimed_by_username",
        ]

    def get_question_details(self, obj: QuestionAudit) -> dict:
        q = obj.question
        return {
            "id": q.id,
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "mnemonic": q.mnemonic,
            "concept_explanation": q.concept_explanation,
            "exam_type": q.exam_type,
            "year": q.year,
            "subject": q.subject.name if q.subject else "",
            "is_disputed": q.is_disputed,
            "needs_review": q.needs_review,
            "answer_key_status": getattr(q, "answer_key_status", ""),
        }


class ResolveAuditRequestSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=AuditResolution.RESOLUTION_CHOICES)
    new_key = serializers.CharField(max_length=1, required=False, allow_blank=True, default="")
    reason = serializers.CharField(min_length=10)
    evidence = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    explanation_fields = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        res = attrs["resolution"]
        if res == "key_changed":
            new_key = valid_key(attrs.get("new_key"))
            if not new_key:
                raise serializers.ValidationError({"new_key": "new_key (A, B, C, or D) is required when resolution is key_changed."})
            attrs["new_key"] = new_key
        return attrs

