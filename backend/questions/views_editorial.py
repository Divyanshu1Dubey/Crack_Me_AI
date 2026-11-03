"""API views for the question editor: answer-key changes, evidence explain, provenance (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group).
"""
from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.editorial import (
    change_answer_key,
    compute_explanation_status,
    mark_explanation_reviewed,
    rescore_key_change,
    save_explanation,
    unverify_question,
    verify_question,
)
from questions.explain_option import explain_selected_option
from questions.models import AnswerKeyChange, ExplanationSuggestion, Question
from questions.serializers_editorial import (
    AnswerKeyChangeSerializer,
    ChangeAnswerKeyRequestSerializer,
    ExplainOptionRequestSerializer,
    ExplanationSuggestionSerializer,
    SaveExplanationRequestSerializer,
)

logger = logging.getLogger("questions.views_editorial")


class ChangeAnswerKeyView(APIView):
    """Change a question's correct answer key with full audit trail."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        serializer = ChangeAnswerKeyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            change = change_answer_key(
                question,
                new_key=data["new_key"],
                actor=request.user,
                reason=data["reason"],
                evidence=data.get("evidence"),
                source=data.get("source", "editor"),
                explanation_fields=data.get("explanation_fields"),
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "ok": True,
                "question_id": question.id,
                "new_key": change.new_key,
                "change": AnswerKeyChangeSerializer(change).data,
            },
            status=status.HTTP_200_OK,
        )


class ExplainOptionView(APIView):
    """Retrieve or generate evidence-first explanation suggestion for a specific option."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        serializer = ExplainOptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            suggestion = explain_selected_option(
                question,
                selected=data["selected"],
                draft=data.get("draft"),
                actor=request.user,
                acknowledge_conflict=data.get("acknowledge_conflict", False),
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ExplanationSuggestionSerializer(suggestion).data, status=status.HTTP_200_OK)


class KeyHistoryListView(APIView):
    """List immutable answer-key change history for a question."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        changes = AnswerKeyChange.objects.filter(question=question).select_related("changed_by", "rescored_by")
        serializer = AnswerKeyChangeSerializer(changes, many=True)
        return Response({"question_id": question.id, "changes": serializer.data})


class SaveExplanationView(APIView):
    """Save an edited explanation with provenance and staleness checks."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        serializer = SaveExplanationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        suggestion = None
        if data.get("suggestion_id"):
            suggestion = ExplanationSuggestion.objects.filter(id=data["suggestion_id"], question=question).first()

        updated_q = save_explanation(
            question,
            fields=data["fields"],
            actor=request.user,
            for_key=data.get("for_key"),
            suggestion=suggestion,
        )

        status_str, reason_str = compute_explanation_status(updated_q)
        return Response(
            {
                "ok": True,
                "question_id": updated_q.id,
                "explanation_status": status_str,
                "explanation_status_reason": reason_str,
            },
            status=status.HTTP_200_OK,
        )


class VerifyQuestionView(APIView):
    """Verify or unverify question answer key."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        action_type = request.data.get("action", "verify")

        if action_type == "unverify":
            reason = request.data.get("reason", "")
            unverify_question(question, actor=request.user, reason=reason)
            return Response({"ok": True, "answer_key_status": "needs_review", "is_verified": False})

        verify_question(question, actor=request.user)
        return Response({"ok": True, "answer_key_status": "verified", "is_verified": True})


class ReviewExplanationView(APIView):
    """Mark a question's explanation as reviewed by staff."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        mark_explanation_reviewed(question, actor=request.user)
        return Response({"ok": True, "explanation_status": question.explanation_status})

