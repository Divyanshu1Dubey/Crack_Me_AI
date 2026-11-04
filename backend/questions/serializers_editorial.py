"""Serializers for editorial actions: answer-key changes, suggestions, provenance (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group). Evidence items follow the review
queue's rules (``key_audit.serializers.clean_evidence_item``): only the known fields of the known
kinds, so a decision is "verified" only for a complete official key / errata / guideline / passage.
"""
from __future__ import annotations

from rest_framework import serializers

from key_audit.serializers import MAX_EVIDENCE_ITEMS, MAX_EXPLANATION, clean_evidence_item
from questions.editorial import EXPLANATION_FIELDS
from questions.explain_option import DRAFT_FIELDS
from questions.models import AnswerKeyChange, ExplanationSuggestion, Question

LETTERS = ["A", "B", "C", "D"]


def _explanation_fields(fields, *, require_one: bool) -> dict:
    unknown = sorted(set(fields) - set(EXPLANATION_FIELDS))
    if unknown:
        raise serializers.ValidationError(f'not an explanation field: {", ".join(unknown)}')
    if require_one and not fields:
        raise serializers.ValidationError("give at least one of " + ", ".join(EXPLANATION_FIELDS))
    return fields


class _ExpectedKeyField(serializers.CharField):
    """The key the editor loaded ('' = the question had none); compared with the current key."""

    def __init__(self, **kwargs):
        super().__init__(max_length=1, required=False, allow_blank=True, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data).strip().upper()
        if value and value not in LETTERS:
            raise serializers.ValidationError("expected_key must be A, B, C, D or blank.")
        return value


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
    """``source`` is not accepted: an editor change is always ``source='editor'`` (a client must not
    file its change as a management command, which the audit does not count as a decision)."""

    new_key = serializers.ChoiceField(choices=LETTERS)
    reason = serializers.CharField(min_length=10, max_length=1000)
    evidence = serializers.ListField(child=serializers.JSONField(), required=False, default=list,
                                     max_length=MAX_EVIDENCE_ITEMS)
    expected_key = _ExpectedKeyField()
    explanation_fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=MAX_EXPLANATION, trim_whitespace=False),
        required=False, default=dict)

    def validate_evidence(self, items):
        return [clean_evidence_item(item) for item in items]

    def validate_explanation_fields(self, fields):
        return _explanation_fields(fields, require_one=False)


class ExplainOptionRequestSerializer(serializers.Serializer):
    selected = serializers.ChoiceField(choices=LETTERS)
    draft = serializers.DictField(required=False, default=dict)
    acknowledge_conflict = serializers.BooleanField(required=False, default=False)

    def validate_draft(self, draft):
        out = {}
        for name, value in draft.items():
            if name not in DRAFT_FIELDS:
                continue   # other editor fields do not change the evidence check
            if name == "is_image_based":
                if not isinstance(value, bool):
                    raise serializers.ValidationError("is_image_based must be true or false.")
            elif name == "question_type":
                choices = {c for c, _ in Question.QUESTION_TYPE_CHOICES}
                if value not in choices:
                    raise serializers.ValidationError("unknown question_type.")
            elif not isinstance(value, str) or len(value) > MAX_EXPLANATION:
                raise serializers.ValidationError(f"{name} must be text of at most {MAX_EXPLANATION} characters.")
            out[name] = value
        return out


class ExplanationSuggestionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True, default="")
    accepted_by_username = serializers.CharField(source="accepted_by.username", read_only=True, default="")
    # The reference-store retrieval the decision used: 'none' = no reference store on this server.
    retrieval_mode = serializers.CharField(source="model", read_only=True)

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
            "retrieval_mode",
            "status",
            "fields",
            "field_citations",
            "citations",
            "dropped_claims",
            "option_evidence",
            "conflict",
            "image_context",
            "used_draft",
            "draft_stem_hash",
            "accepted_at",
            "accepted_by_username",
        ]
        read_only_fields = fields


class SaveExplanationRequestSerializer(serializers.Serializer):
    fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=MAX_EXPLANATION, trim_whitespace=False))
    # The key the explanation was written for; it must be the question's current key.
    for_key = serializers.ChoiceField(choices=LETTERS, required=False, allow_blank=True)
    suggestion_id = serializers.UUIDField(required=False, allow_null=True)
    # Fields whose text came from that suggestion / from the legacy AI generator (provenance 'mixed').
    accepted_fields = serializers.ListField(child=serializers.ChoiceField(choices=list(EXPLANATION_FIELDS)),
                                            required=False, default=list, max_length=len(EXPLANATION_FIELDS))
    ai_fields = serializers.ListField(child=serializers.ChoiceField(choices=list(EXPLANATION_FIELDS)),
                                      required=False, default=list, max_length=len(EXPLANATION_FIELDS))

    def validate_fields(self, fields):
        return _explanation_fields(fields, require_one=True)

    def validate(self, attrs):
        if attrs.get("accepted_fields") and not attrs.get("suggestion_id"):
            raise serializers.ValidationError({"accepted_fields": "accepted fields need the suggestion_id."})
        missing = sorted(set(attrs.get("accepted_fields") or ()) - set(attrs["fields"]))
        if missing:
            raise serializers.ValidationError({"accepted_fields": f'not in fields: {", ".join(missing)}'})
        return attrs


class VerifyKeyRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["verify", "unverify"], required=False, default="verify")
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")
