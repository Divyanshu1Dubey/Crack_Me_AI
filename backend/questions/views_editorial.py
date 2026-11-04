"""API views for the question editor: answer-key changes, evidence explain, provenance (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group). Admin only (``IsControlTowerAdmin``:
role admin or superuser, the same rule as the editor page, the review queue and the question
viewset's admin actions). Routes (``questions/urls_editorial.py``, under ``/api/questions/``):

  GET  <id>/provenance/          key, answer-key audit, verification, explanation provenance, printed
                                 source keys (for evidence), whether a reference store is available
  POST <id>/change-key/          {new_key, reason >= 10, evidence[], expected_key?, explanation_fields?}
                                 -> the change, the audit status it led to; 409 key_changed when the key
                                 is no longer ``expected_key``
  GET  <id>/key-history/         immutable AnswerKeyChange rows, newest first
  POST <id>/explain-option/      {selected, draft?, acknowledge_conflict?} -> ExplanationSuggestion
                                 (throttle scope ``admin_explain``)
  POST <id>/save-explanation/    {fields, for_key?, suggestion_id?, accepted_fields?, ai_fields?}; the
                                 explanation must be for the current key (409 key_changed otherwise)
  POST <id>/verify-key/          {action: verify | unverify, reason?} -> the audit status
  POST <id>/review-explanation/  mark the current explanation reviewed (not an empty / stale one)

A key changes only through ``questions.editorial.change_answer_key`` (source 'editor'). Nothing here
makes a key "verified" by itself: the answer-key audit re-classifies the question after every
decision, and only a decision that cites strong evidence gives "verified".
"""
from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions.content_hashes import stem_hash, valid_key
from questions.editorial import (
    change_answer_key,
    compute_explanation_status,
    mark_explanation_reviewed,
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
    VerifyKeyRequestSerializer,
)

logger = logging.getLogger("questions.views_editorial")


class _EditorView(APIView):
    permission_classes = [IsControlTowerAdmin]


def _messages(exc: DjangoValidationError) -> str:
    return " ".join(str(m) for m in exc.messages) or "Invalid request."


def _username(user) -> str:
    return getattr(user, "username", "") if user is not None else ""


def _key_changed(current: str, detail: str) -> Response:
    return Response({"code": "key_changed", "current_key": current, "detail": detail},
                    status=status.HTTP_409_CONFLICT)


def _audit_payload(question_id: int) -> dict | None:
    """The question's answer-key audit row, as the editor shows it (None when there is none)."""
    try:
        from key_audit.models import QuestionAudit
    except ImportError:  # pragma: no cover - key_audit not installed
        return None
    row = QuestionAudit.objects.filter(question_id=question_id).first()
    if row is None:
        return None
    open_signals = [s.get("code") for s in (row.signals or [])
                    if isinstance(s, dict) and s.get("opens_review") and not s.get("settled_by_review")]
    return {
        "status": row.status, "status_reason": row.status_reason, "stored_key": row.stored_key,
        "original_key": row.original_key, "key_provenance": row.key_provenance,
        "suggested_key": row.suggested_key, "suggested_from": (row.evidence_summary or {}).get("suggested_from", ""),
        "priority": row.priority, "is_stale": row.is_stale, "audited_at": row.audited_at,
        "open_signals": open_signals[:12],
    }


def _reaudit(question) -> str:
    """Re-audit after an editor change the audit reads (e.g. the explanation text); best effort."""
    try:
        from key_audit.services import audit_questions
        prepared = audit_questions([Question.objects.get(pk=question.pk)], save=True)
        return prepared[0].fields["status"] if prepared else ""
    except Exception:  # noqa: BLE001 - the saved change stands; the next audit run catches up
        logger.exception("re-audit after an editor change failed for question %s", question.pk)
        return ""


def _log_key_change(request, question, change) -> None:
    try:
        from accounts.models import AdminAuditLog
        with transaction.atomic():
            AdminAuditLog.objects.create(
                actor=request.user, action="answer_key_change", resource_type="question",
                resource_id=str(question.pk),
                detail=f"{change.old_key or '-'} -> {change.new_key} ({change.source}): {change.reason[:200]}",
                metadata={"key_change_id": change.pk, "old_key": change.old_key, "new_key": change.new_key,
                          "source": change.source,
                          "evidence_kinds": [item.get("kind") for item in change.evidence if isinstance(item, dict)]},
            )
    except Exception:  # noqa: BLE001 - the AnswerKeyChange row is the record; the log is extra
        logger.exception("admin audit log failed for the key change of question %s", question.pk)


def _explanation_payload(question) -> dict:
    status_str, reason = compute_explanation_status(question)
    return {
        "status": status_str,
        "status_reason": reason,
        "stored_status": question.explanation_status,
        "origin": question.explanation_origin,
        "for_key": question.explanation_for_key,
        "reviewed_by": _username(question.explanation_reviewed_by) if question.explanation_reviewed_by_id else "",
        "reviewed_at": question.explanation_reviewed_at,
        "suggestion_id": str(question.explanation_suggestion_id) if question.explanation_suggestion_id else None,
        "has_text": bool((question.explanation or "").strip()),
        "locked": bool(question.lock_explanation),
    }


def _reference_store_available() -> bool:
    try:
        from reference_corpus import api
        return bool(api.store_available())
    except Exception:  # noqa: BLE001
        return False


class ProvenanceView(_EditorView):
    """Everything the editor's provenance and key-change panels show about one question."""

    def get(self, request, pk: int):
        question = get_object_or_404(
            Question.objects.select_related("verified_by", "explanation_reviewed_by"), pk=pk)
        current_hash = stem_hash(question)
        source_keys = []
        try:
            from key_audit.serializers import SourceKeySerializer
            rows = list(question.source_keys.all().order_by("id"))
            for row, data in zip(rows, SourceKeySerializer(rows, many=True).data):
                source_keys.append({**data, "current_content": row.stem_hash == current_hash})
        except Exception:  # noqa: BLE001 - optional signal
            logger.exception("source keys failed for question %s", question.pk)
        return Response({
            "question_id": question.pk,
            "correct_answer": valid_key(question.correct_answer),
            "stem_hash": current_hash,
            "updated_at": question.updated_at,
            "is_active": question.is_active,
            "is_dropped": question.is_dropped,
            "is_disputed": question.is_disputed,
            "needs_review": question.needs_review,
            "lock_answer": question.lock_answer,
            "answer_key_status": question.answer_key_status,
            "audit": _audit_payload(question.pk),
            "verification": {
                "verified_by": _username(question.verified_by) if question.verified_by_id else "",
                "verified_at": question.verified_at,
                "is_verified_by_admin": question.is_verified_by_admin,
                "verified_note": question.verified_note,
            },
            "explanation": _explanation_payload(question),
            "key_change_count": AnswerKeyChange.objects.filter(question=question).count(),
            "source_keys": source_keys,
            "reference_store_available": _reference_store_available(),
        })


class ChangeAnswerKeyView(_EditorView):
    """Change a question's correct answer key with full audit trail."""

    def post(self, request, pk: int):
        from key_audit.reviews import has_strong_evidence
        from key_audit.views import check_source_key_evidence

        serializer = ChangeAnswerKeyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=pk)
            current = valid_key(question.correct_answer)
            if "expected_key" in data and data["expected_key"] != current:
                return _key_changed(current, f"The key is now {current or 'not set'}, not "
                                             f"{data['expected_key'] or 'unset'}: reload the question.")
            bad = check_source_key_evidence(question, data["evidence"])
            if bad:
                return Response({"evidence": [bad]}, status=status.HTTP_400_BAD_REQUEST)
            try:
                change = change_answer_key(
                    question,
                    new_key=data["new_key"],
                    actor=request.user,
                    reason=data["reason"],
                    evidence=data["evidence"],
                    source="editor",
                    explanation_fields=data["explanation_fields"] or None,
                )
            except DjangoValidationError as exc:
                return Response({"detail": _messages(exc)}, status=status.HTTP_400_BAD_REQUEST)
            _log_key_change(request, question, change)
        # The content hooks re-audited the question when the change was committed; auditing once more
        # here keeps the answer independent of how the request's transaction is set up.
        audit_status = _reaudit(question)
        question.refresh_from_db()
        return Response(
            {
                "ok": True,
                "question_id": question.id,
                "old_key": change.old_key,
                "new_key": change.new_key,
                "strong_evidence": has_strong_evidence(change.evidence),
                "answer_key_status": audit_status or question.answer_key_status,
                "audit": _audit_payload(question.pk),
                "explanation": _explanation_payload(question),
                # The change clears these flags: an editor form must not PATCH its old values back.
                "needs_review": question.needs_review,
                "is_disputed": question.is_disputed,
                "updated_at": question.updated_at,
                "change": AnswerKeyChangeSerializer(change).data,
            },
            status=status.HTTP_200_OK,
        )


class ExplainOptionView(_EditorView):
    """Evidence-first explanation suggestion for one option (nothing is written to the question)."""

    throttle_scope = "admin_explain"

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
        except DjangoValidationError as exc:
            return Response({"detail": _messages(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ExplanationSuggestionSerializer(suggestion).data, status=status.HTTP_200_OK)


class KeyHistoryListView(_EditorView):
    """List immutable answer-key change history for a question."""

    def get(self, request, pk: int):
        question = get_object_or_404(Question, pk=pk)
        changes = AnswerKeyChange.objects.filter(question=question).select_related("changed_by", "rescored_by")
        serializer = AnswerKeyChangeSerializer(changes, many=True)
        return Response({"question_id": question.id, "current_key": valid_key(question.correct_answer),
                         "changes": serializer.data})


class SaveExplanationView(_EditorView):
    """Save an edited explanation with provenance, for the question's current key."""

    def post(self, request, pk: int):
        serializer = SaveExplanationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=pk)
            current = valid_key(question.correct_answer)
            if not current:
                return Response({"code": "no_key", "detail": "Set the answer key first: an explanation is "
                                                             "written for a key."},
                                status=status.HTTP_400_BAD_REQUEST)
            for_key = data.get("for_key") or current
            if for_key != current:
                return _key_changed(current, f"This explanation was written for option {for_key}, but the key is "
                                             f"{current}. Change the key first, or reload.")
            suggestion = None
            if data.get("suggestion_id"):
                suggestion = ExplanationSuggestion.objects.filter(id=data["suggestion_id"], question=question).first()
                if suggestion is None:
                    return Response({"suggestion_id": ["Not a suggestion for this question."]},
                                    status=status.HTTP_400_BAD_REQUEST)
            accepted = data.get("accepted_fields") or []
            if accepted:
                if suggestion.status != "ok":
                    return Response({"code": "suggestion_not_supported",
                                     "detail": "Only a suggestion the evidence supports can be accepted."},
                                    status=status.HTTP_400_BAD_REQUEST)
                if suggestion.for_key != current:
                    return Response({"code": "suggestion_for_other_key",
                                     "detail": f"The suggestion explains option {suggestion.for_key}; the key is "
                                               f"{current}."}, status=status.HTTP_409_CONFLICT)
                if suggestion.draft_stem_hash and suggestion.draft_stem_hash != stem_hash(question):
                    return Response({"code": "suggestion_for_other_content",
                                     "detail": "The suggestion was made for other question text. Save the "
                                               "question first, then check the evidence again."},
                                    status=status.HTTP_409_CONFLICT)
            save_explanation(
                question,
                fields=data["fields"],
                actor=request.user,
                for_key=current,
                suggestion=suggestion,
                accepted_fields=accepted,
                ai_fields=data.get("ai_fields") or [],
            )

        question.refresh_from_db()
        # The explanation text is an audit signal (an explanation that names another option).
        audit_status = _reaudit(question)
        explanation = _explanation_payload(question)
        return Response(
            {
                "ok": True,
                "question_id": question.id,
                "explanation_status": explanation["status"],
                "explanation_status_reason": explanation["status_reason"],
                "explanation": explanation,
                "answer_key_status": audit_status or question.answer_key_status,
                "updated_at": question.updated_at,   # the re-audit does not touch updated_at
            },
            status=status.HTTP_200_OK,
        )


class VerifyQuestionView(_EditorView):
    """Confirm the stored key (``verify``) or send the question back to review (``unverify``)."""

    def post(self, request, pk: int):
        serializer = VerifyKeyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_type = serializer.validated_data["action"]

        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=pk)
            try:
                if action_type == "unverify":
                    new_status = unverify_question(question, actor=request.user,
                                                   reason=serializer.validated_data.get("reason", ""))
                else:
                    # The audit decides the status: a confirmation without cited evidence is "likely_correct".
                    new_status = verify_question(question, actor=request.user)
            except DjangoValidationError as exc:
                return Response({"code": "no_key", "detail": _messages(exc)}, status=status.HTTP_400_BAD_REQUEST)

        question.refresh_from_db()
        fallback = "needs_review" if action_type == "unverify" else "likely_correct"
        return Response({
            "ok": True,
            "action": action_type,
            "answer_key_status": new_status or fallback,
            "is_verified": action_type == "verify",
            "verification": {
                "verified_by": _username(question.verified_by) if question.verified_by_id else "",
                "verified_at": question.verified_at,
                "is_verified_by_admin": question.is_verified_by_admin,
                "verified_note": question.verified_note,
            },
            "audit": _audit_payload(question.pk),
            "needs_review": question.needs_review,
            "is_disputed": question.is_disputed,
            "updated_at": question.updated_at,
        })


class ReviewExplanationView(_EditorView):
    """Mark a question's explanation as reviewed by staff (for the current key and content)."""

    def post(self, request, pk: int):
        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=pk)
            status_str, reason = compute_explanation_status(question)
            if status_str == "absent":
                return Response({"code": "no_explanation", "detail": "There is no explanation to review."},
                                status=status.HTTP_400_BAD_REQUEST)
            if status_str in ("stale", "conflict"):
                why = reason or question.explanation_status_reason or "The key or the question changed since it was written"
                return Response({"code": f"explanation_{status_str}",
                                 "detail": f"{why}. Rewrite it for the current key and content first."},
                                status=status.HTTP_409_CONFLICT)
            if not valid_key(question.correct_answer):
                return Response({"code": "no_key", "detail": "Set the answer key first."},
                                status=status.HTTP_400_BAD_REQUEST)
            mark_explanation_reviewed(question, actor=request.user)
        question.refresh_from_db()
        return Response({"ok": True, "explanation_status": question.explanation_status,
                         "explanation": _explanation_payload(question), "updated_at": question.updated_at})
