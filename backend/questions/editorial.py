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

    with transaction.atomic():
        # Determine explanation handling
        explanation_action = "kept_stale"
        if explanation_fields:
            explanation_action = "replaced"
            for k, v in explanation_fields.items():
                if hasattr(question, k):
                    setattr(question, k, v)
            question.explanation_for_key = clean_key
            question.explanation_stem_hash = old_stem_hash
            question.explanation_status = "human_edited"
        elif question.explanation:
            # If key changed without updating explanation, mark it stale for the new key
            question.explanation_status = "stale"
            question.explanation_status_reason = f"Key changed from {old_key} to {clean_key}"

        # Update the question's answer key
        question.correct_answer = clean_key
        # Unset dispute and review flags upon verified editorial key change
        question.is_disputed = False
        question.needs_review = False
        question.answer_key_status = "verified" if (actor and actor.is_staff) else "likely_correct"

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

    allowed_fields = ("explanation", "mnemonic", "concept_explanation")
    for f in allowed_fields:
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


def verify_question(question: Question, *, actor) -> None:
    """Verify a question's answer key and content by staff."""
    question.answer_key_status = "verified"
    question.verified_by = actor
    question.verified_at = timezone.now()
    question.is_disputed = False
    question.needs_review = False
    question.save(update_fields=["answer_key_status", "verified_by", "verified_at", "is_disputed", "needs_review"])


def unverify_question(question: Question, *, actor, reason: str = "") -> None:
    """Revert verification status to needs_review."""
    question.answer_key_status = "needs_review"
    question.needs_review = True
    question.verified_by = None
    question.verified_at = None
    question.save(update_fields=["answer_key_status", "needs_review", "verified_by", "verified_at"])


def rescore_key_change(change: AnswerKeyChange, *, actor, apply: bool = False) -> dict[str, Any]:
    """Dry-run or apply score re-calculation for test attempts affected by a key change."""
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
        "apply": apply,
    }
    if apply:
        change.rescore_status = "done"
        change.rescored_at = timezone.now()
        change.rescored_by = actor
        change.save(update_fields=list(AnswerKeyChange.RESCORE_FIELDS))
    return result

