"""Editorial workflows for questions: changing answer keys with audit trail, explanations and verification.

All mutations to ``Question.correct_answer`` on existing rows MUST go through
``change_answer_key()`` to guarantee an immutable ``AnswerKeyChange`` record,
provenance preservation, explanation staleness checks, and triggering content hooks.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from questions.content_hashes import stem_hash, valid_key
from questions.content_hooks import on_question_changed
from questions.models import AnswerKeyChange, Question

logger = logging.getLogger("questions.editorial")

# The only fields ``change_answer_key(explanation_fields=...)`` and ``save_explanation`` write. Anything
# else in the dict (``correct_answer``, ``answer_key_status``, ``verified_by``, ``is_active``, ...) is
# rejected: the editor and review-queue endpoints pass the client's dict through.
EXPLANATION_FIELDS = ("explanation", "concept_explanation", "mnemonic")


def _audit_before(question) -> tuple[str, int | None]:
    """(status, id) of the question's answer-key audit, for the AnswerKeyChange record."""
    try:
        from key_audit.models import QuestionAudit
    except ImportError:  # pragma: no cover - key_audit not installed
        return "", None
    row = QuestionAudit.objects.filter(question_id=question.pk).values("status", "id").first()
    return (row["status"], row["id"]) if row else ("", None)


def change_answer_key(
    question: Question,
    new_key: str,
    *,
    actor=None,
    reason: str,
    evidence: Sequence[dict[str, Any]] | None = None,
    source: str = "editor",
    suggestion=None,
    explanation_fields: dict[str, str] | None = None,
    request_id: str = "",
) -> AnswerKeyChange:
    """Change the correct_answer of a question, recording an immutable AnswerKeyChange.

    Args:
        question: The Question instance to update.
        new_key: The new answer key ('A', 'B', 'C', or 'D').
        actor: The user making the change (admin/operator).
        reason: Explanation of why the key is being changed (minimum 10 characters).
        evidence: Optional list of structured evidence records supporting the change.
        source: Provenance of the change (e.g. 'editor', 'review_queue', 'resolve_dispute').
        suggestion: Optional ExplanationSuggestion that prompted this change.
        explanation_fields: Optional dict of explanation fields to update along with the key.
        request_id: Optional tracking request id.

    Returns:
        The created AnswerKeyChange instance.
    """
    clean_key = valid_key(new_key)
    if not clean_key:
        raise ValidationError(f"Invalid answer key: {new_key!r}. Must be A, B, C, or D.")

    clean_reason = (reason or "").strip()
    if len(clean_reason) < 10:
        raise ValidationError("Reason for key change must be at least 10 characters.")

    old_key = question.correct_answer or ""
    old_stem_hash = stem_hash(question)

    if old_key == clean_key:
        raise ValidationError(f"Question #{question.id} already has correct_answer={clean_key!r}.")
    unknown = sorted(set(explanation_fields or {}) - set(EXPLANATION_FIELDS))
    if unknown:
        raise ValidationError(f"Not an explanation field: {', '.join(unknown)}.")

    audit_status_before, audit_id = _audit_before(question)
    with transaction.atomic():
        # Determine explanation handling
        explanation_action = "kept_stale"
        if explanation_fields:
            explanation_action = "replaced"
            for k, v in explanation_fields.items():
                setattr(question, k, v if isinstance(v, str) else "")
            question.explanation_for_key = clean_key
            question.explanation_stem_hash = old_stem_hash
            question.explanation_status = "human_edited"
        elif question.explanation:
            # If key changed without updating explanation, mark it stale for the new key
            question.explanation_status = "stale"
            question.explanation_status_reason = f"Key changed from {old_key} to {clean_key}"

        # Update the question's answer key
        question.correct_answer = clean_key
        # Unset dispute and review flags upon an editorial key change
        question.is_disputed = False
        question.needs_review = False
        # The answer-key audit sets the status again on commit (key_audit.services.on_question_changed):
        # a change that cites strong evidence becomes "verified", one without "likely_correct".
        question.answer_key_status = "unaudited"

        # Save question updates
        question.save()

        # Create immutable AnswerKeyChange record
        change = AnswerKeyChange.objects.create(
            question=question,
            old_key=old_key,
            new_key=clean_key,
            changed_by=actor,
            source=source,
            reason=clean_reason,
            evidence=list(evidence or []),
            explanation_action=explanation_action,
            audit_status_before=audit_status_before,
            audit_id=audit_id,
        )

        # Trigger content hooks on transaction commit
        transaction.on_commit(
            lambda: on_question_changed(
                question,
                old_key=old_key,
                old_stem_hash=old_stem_hash,
                reason=clean_reason,
                actor=actor,
            )
        )

    return change


def save_explanation(
    question: Question,
    fields: dict[str, str],
    *,
    actor=None,
    for_key: str | None = None,
    suggestion=None,
    accepted_fields: Sequence[str] | None = None,
) -> Question:
    """Save updated explanation text and provenance metadata."""
    current_stem_hash = stem_hash(question)
    target_key = for_key or question.correct_answer

    for f in EXPLANATION_FIELDS:
        if f in fields:
            setattr(question, f, fields[f])

    question.explanation_for_key = target_key
    question.explanation_stem_hash = current_stem_hash
    question.explanation_status = "human_edited" if (actor and not getattr(actor, "is_ai", False)) else "ai_generated"
    if actor and actor.is_staff:
        question.explanation_reviewed_by = actor
        question.explanation_reviewed_at = timezone.now()

    question.save()
    return question


def compute_explanation_status(question: Question, suggestion=None) -> tuple[str, str]:
    """Compute (status, reason) for a question's explanation."""
    if not (question.explanation or "").strip():
        return "absent", "No explanation text stored"

    current_stem_hash = stem_hash(question)
    if question.explanation_stem_hash and question.explanation_stem_hash != current_stem_hash:
        return "stale", "Question stem or options modified since explanation was saved"

    if question.explanation_for_key and question.explanation_for_key != question.correct_answer:
        return "conflict", f"Explanation was written for option {question.explanation_for_key}, but key is {question.correct_answer}"

    return getattr(question, "explanation_status", "human_edited") or "human_edited", ""


def mark_explanation_reviewed(question: Question, *, actor) -> None:
    """Mark an explanation as human-reviewed by staff."""
    question.explanation_reviewed_by = actor
    question.explanation_reviewed_at = timezone.now()
    question.explanation_status = "reviewed"
    question.save(update_fields=["explanation_reviewed_by", "explanation_reviewed_at", "explanation_status"])


def _record_decision(question: Question, *, actor, resolution: str, reason: str) -> str:
    """Record an editor decision for the answer-key audit and re-audit the question.

    The decision is an immutable ``key_audit.AuditResolution``; the audit turns it into the status
    (a confirmation without cited evidence is "likely_correct", never "verified"). Returns the new
    ``answer_key_status`` ('' when the audit is not installed).
    """
    try:
        from key_audit.models import AuditResolution, QuestionAudit
        from key_audit.services import audit_questions
    except ImportError:  # pragma: no cover - key_audit not installed
        return ""
    audit = QuestionAudit.objects.filter(question_id=question.pk).first()
    AuditResolution.objects.create(
        question=question, audit=audit, resolution=resolution, reason=reason, evidence=[],
        status_before=audit.status if audit else "", stored_key=valid_key(question.correct_answer),
        stem_hash=stem_hash(question), resolved_by=actor,
    )
    prepared = audit_questions([Question.objects.get(pk=question.pk)], save=True)[0]
    return prepared.fields["status"]


def verify_question(question: Question, *, actor) -> str:
    """Record a staff confirmation of the question's key; returns the audit status it leads to."""
    question.verified_by = actor
    question.verified_at = timezone.now()
    question.is_disputed = False
    question.needs_review = False
    question.save(update_fields=["verified_by", "verified_at", "is_disputed", "needs_review"])
    return _record_decision(question, actor=actor, resolution="key_confirmed",
                            reason="Key confirmed in the question editor (no evidence cited).")


def unverify_question(question: Question, *, actor, reason: str = "") -> str:
    """Withdraw a verification: the question goes back to the review queue."""
    question.needs_review = True
    question.verified_by = None
    question.verified_at = None
    question.save(update_fields=["needs_review", "verified_by", "verified_at"])
    text = (reason or "").strip()
    return _record_decision(question, actor=actor, resolution="deferred",
                            reason=text if len(text) >= 10 else "Verification withdrawn in the question editor.")


def rescore_key_change(change: AnswerKeyChange, *, actor, apply: bool = False) -> dict[str, Any]:
    """Count the test submissions a key change affects (dry run only).

    Re-scoring is not implemented: ``apply=True`` raises instead of marking the change "done" without
    recomputing a single score.
    """
    if apply:
        raise NotImplementedError("Re-scoring test submissions after a key change is not implemented yet.")
    # Counts attempts that had selected either old_key or new_key
    from tests_engine.models import TestSubmission
    affected_submissions = TestSubmission.objects.filter(
        test__test_questions__question=change.question
    ).count()

    result = {
        "change_id": change.id,
        "question_id": change.question_id,
        "old_key": change.old_key,
        "new_key": change.new_key,
        "affected_submissions_count": affected_submissions,
        "apply": False,
    }
    return result

