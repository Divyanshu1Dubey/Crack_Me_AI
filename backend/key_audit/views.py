"""API views for the answer-key audit and admin review queue."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from key_audit.models import AuditResolution, QuestionAudit, ReviewClaim
from key_audit.serializers import (
    QuestionAuditDetailSerializer,
    QuestionAuditListSerializer,
    ResolveAuditRequestSerializer,
)
from questions.editorial import change_answer_key
from questions.models import Question


class ReviewQueuePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class ReviewQueueListView(APIView):
    """List questions in the review queue ordered by priority (highest first)."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = QuestionAudit.objects.select_related("question", "question__subject").all()

        audit_status = request.query_params.get("status")
        if audit_status:
            qs = qs.filter(status=audit_status)

        reason = request.query_params.get("reason")
        if reason:
            qs = qs.filter(status_reason=reason)

        exam = request.query_params.get("exam")
        if exam:
            qs = qs.filter(question__exam_type=exam)

        has_suggestion = request.query_params.get("has_suggestion")
        if has_suggestion == "true":
            qs = qs.exclude(suggested_key="")

        paginator = ReviewQueuePagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = QuestionAuditListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ReviewQueueDetailView(APIView):
    """Retrieve complete audit, signals, question content, and source evidence for one question."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, question_id: int):
        audit = get_object_or_404(
            QuestionAudit.objects.select_related("question", "question__subject").prefetch_related("resolutions"),
            question_id=question_id,
        )
        serializer = QuestionAuditDetailSerializer(audit)
        return Response(serializer.data)


class ReviewClaimView(APIView):
    """Claim a question for 15 minutes to avoid two admins reviewing the same item simultaneously."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, question_id: int):
        question = get_object_or_404(Question, id=question_id)
        now = timezone.now()

        claim = ReviewClaim.objects.filter(question=question).first()
        if claim and claim.expires_at > now and claim.claimed_by != request.user:
            return Response(
                {
                    "error": "Question is currently claimed by another reviewer.",
                    "claimed_by": claim.claimed_by.username,
                    "expires_at": claim.expires_at.isoformat(),
                },
                status=status.HTTP_409_CONFLICT,
            )

        expires_at = now + timedelta(minutes=15)
        claim, _created = ReviewClaim.objects.update_or_create(
            question=question,
            defaults={"claimed_by": request.user, "claimed_at": now, "expires_at": expires_at},
        )
        return Response({
            "question_id": question.id,
            "claimed_by": request.user.username,
            "expires_at": claim.expires_at.isoformat(),
        })

    def delete(self, request, question_id: int):
        """Release claim."""
        question = get_object_or_404(Question, id=question_id)
        ReviewClaim.objects.filter(question=question, claimed_by=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewResolveView(APIView):
    """Resolve an audited question by confirming, changing, or fixing the key/explanation.

    Changing a key invokes questions.editorial.change_answer_key() and creates an
    immutable AuditResolution record.
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request, question_id: int):
        audit = get_object_or_404(QuestionAudit.objects.select_related("question"), question_id=question_id)
        question = audit.question

        serializer = ResolveAuditRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        resolution = data["resolution"]
        new_key = data.get("new_key")
        reason = data["reason"]
        evidence = data.get("evidence", [])
        explanation_fields = data.get("explanation_fields", {})

        status_before = audit.status
        key_change_record = None

        with transaction.atomic():
            if resolution == "key_changed":
                key_change_record = change_answer_key(
                    question,
                    new_key=new_key,
                    actor=request.user,
                    reason=reason,
                    evidence=evidence,
                    source="review_queue",
                    explanation_fields=explanation_fields if explanation_fields else None,
                )
                audit.status = "verified"
                audit.status_reason = "resolved_key_changed"
                audit.stored_key = new_key
                audit.priority = 0.0
                audit.save()

            elif resolution == "key_confirmed":
                audit.status = "verified"
                audit.status_reason = "resolved_key_confirmed"
                audit.priority = 0.0
                question.answer_key_status = "verified"
                question.is_disputed = False
                question.needs_review = False
                question.verified_by = request.user
                question.verified_at = timezone.now()
                question.save(update_fields=["answer_key_status", "is_disputed", "needs_review", "verified_by", "verified_at"])
                audit.save()

            elif resolution == "question_deactivated":
                question.is_active = False
                question.save(update_fields=["is_active"])
                audit.status = "verified"
                audit.priority = 0.0
                audit.save()

            elif resolution == "dropped":
                audit.status = "verified"
                audit.status_reason = "dropped_from_scoring"
                audit.priority = 0.0
                audit.save()

            # Create immutable AuditResolution record
            res_obj = AuditResolution.objects.create(
                question=question,
                audit=audit,
                resolution=resolution,
                reason=reason,
                evidence=evidence,
                key_change=key_change_record,
                status_before=status_before,
                resolved_by=request.user,
            )

            # Release any claim on the question
            ReviewClaim.objects.filter(question=question).delete()

        return Response(
            {
                "question_id": question.id,
                "resolution_id": res_obj.id,
                "resolution": resolution,
                "current_key": question.correct_answer,
                "audit_status": audit.status,
            },
            status=status.HTTP_200_OK,
        )

