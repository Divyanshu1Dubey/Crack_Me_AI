"""Editorial workflows for questions: changing answer keys with audit trail, explanations and verification.

All mutations to ``Question.correct_answer`` on existing rows MUST go through
``change_answer_key()`` to guarantee an immutable ``AnswerKeyChange`` record,
provenance preservation, explanation staleness checks, and triggering content hooks.
"""
from __future__ import annotations

import hashlib
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


def _is_admin(actor) -> bool:
    """An admin account (role admin, superuser or staff): its saves count as a human review."""
    return bool(
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and (getattr(actor, "is_admin", False) or getattr(actor, "is_superuser", False)
             or getattr(actor, "is_staff", False))
    )


def explanation_hash(question) -> str:
    """sha256 over the explanation fields (Question.explanation_hash / explanation_reviewed_hash)."""
    parts = [(getattr(question, name, "") or "").strip() for name in EXPLANATION_FIELDS]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


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
            question.explanation_status_reason = ""
            question.explanation_origin = "human"
            question.explanation_hash = explanation_hash(question)
            # As a PATCH of the explanation: students see this text, not an older AI explanation
            # (serializers.effective_explanation_for), and AI regeneration leaves it alone.
            question.lock_explanation = True
        elif (question.explanation or "").strip() or (question.ai_explanation or "").strip():
            # If key changed without updating explanation, mark it stale for the new key (curated or AI
            # text alike: both argue for the old key; students are not shown it, see
            # serializers.explanation_for_another_key)
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
    ai_fields: Sequence[str] | None = None,
) -> Question:
    """Save updated explanation text and provenance metadata.

    ``accepted_fields``: fields whose text the admin took from ``suggestion``; ``ai_fields``: fields
    the legacy AI generator filled and the admin saved. Either makes the origin 'mixed' (else
    'human'). Only the explanation fields and their provenance are written (``update_fields``), so a
    concurrent change of the key or the stem is never overwritten with this instance's values.
    """
    current_stem_hash = stem_hash(question)
    target_key = for_key or question.correct_answer
    human = bool(actor) and not getattr(actor, "is_ai", False)

    for f in EXPLANATION_FIELDS:
        if f in fields:
            setattr(question, f, fields[f])

    accepted = [f for f in (accepted_fields or ()) if f in EXPLANATION_FIELDS]
    used_suggestion = suggestion if (suggestion is not None and accepted) else None
    ai_used = [f for f in (ai_fields or ()) if f in EXPLANATION_FIELDS]
    question.explanation_for_key = target_key
    question.explanation_stem_hash = current_stem_hash
    question.explanation_status = "human_edited" if human else "ai_generated"
    question.explanation_status_reason = ""
    question.explanation_origin = ("mixed" if (used_suggestion is not None or ai_used) else "human") if human else "ai"
    question.explanation_hash = explanation_hash(question)
    update_fields = [*[f for f in EXPLANATION_FIELDS if f in fields], "explanation_for_key", "explanation_stem_hash",
                     "explanation_status", "explanation_status_reason", "explanation_origin", "explanation_hash"]
    if used_suggestion is not None:
        question.explanation_suggestion = used_suggestion
        update_fields.append("explanation_suggestion")
    if human:
        # As a PATCH of the explanation (QuestionViewSet.perform_update): students see this text rather
        # than an older AI explanation, and AI regeneration does not overwrite it.
        question.lock_explanation = True
        update_fields.append("lock_explanation")
    if _is_admin(actor):
        question.explanation_reviewed_by = actor
        question.explanation_reviewed_at = timezone.now()
        question.explanation_reviewed_hash = question.explanation_hash
        update_fields += ["explanation_reviewed_by", "explanation_reviewed_at", "explanation_reviewed_hash"]

    question.save(update_fields=[*update_fields, "updated_at"])
    if used_suggestion is not None and used_suggestion.accepted_at is None:
        type(used_suggestion).objects.filter(pk=used_suggestion.pk).update(
            accepted_at=timezone.now(), accepted_by=actor if getattr(actor, "is_authenticated", False) else None)
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

    stored = getattr(question, "explanation_status", "") or ""
    if stored in ("", "none"):
        # Text saved before provenance was recorded (or by a path that records none): nobody has
        # reviewed it for the current key and content.
        return "pending_review", "No provenance recorded for this explanation"
    return stored, ""


def mark_explanation_reviewed(question: Question, *, actor) -> None:
    """Mark an explanation as human-reviewed by staff, for the question's current key and content."""
    question.explanation_reviewed_by = actor
    question.explanation_reviewed_at = timezone.now()
    question.explanation_status = "reviewed"
    question.explanation_status_reason = ""
    # The review is for what the admin saw: the current key and stem / options (so a later change
    # shows the explanation as stale again) and the current text.
    question.explanation_for_key = valid_key(question.correct_answer)
    question.explanation_stem_hash = stem_hash(question)
    question.explanation_hash = explanation_hash(question)
    question.explanation_reviewed_hash = question.explanation_hash
    fields = ["explanation_reviewed_by", "explanation_reviewed_at", "explanation_status", "explanation_status_reason",
              "explanation_for_key", "explanation_stem_hash", "explanation_hash", "explanation_reviewed_hash"]
    if not question.explanation_origin:
        question.explanation_origin = "legacy"
        fields.append("explanation_origin")
    question.save(update_fields=fields)


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
    """Record a staff confirmation of the question's key; returns the audit status it leads to.

    A key that is not A-D cannot be confirmed (raises ``ValidationError``): change it instead.
    """
    if not valid_key(question.correct_answer):
        raise ValidationError("The stored key is not A-D: change it instead of confirming it.")
    question.verified_by = actor
    question.verified_at = timezone.now()
    question.is_disputed = False
    question.needs_review = False
    question.save(update_fields=["verified_by", "verified_at", "is_disputed", "needs_review"])
    return _record_decision(question, actor=actor, resolution="key_confirmed",
                            reason="Key confirmed in the question editor (no evidence cited).")


def unverify_question(question: Question, *, actor, reason: str = "") -> str:
    """Withdraw a verification: the question goes back to the review queue.

    The student-facing "Verified by Admin" badge goes too: it must not sit on a question an admin
    just sent back for review.
    """
    question.needs_review = True
    question.verified_by = None
    question.verified_at = None
    question.is_verified_by_admin = False
    question.verified_hash = ""
    question.save(update_fields=["needs_review", "verified_by", "verified_at", "is_verified_by_admin", "verified_hash"])
    text = (reason or "").strip()
    return _record_decision(question, actor=actor, resolution="deferred",
                            reason=text if len(text) >= 10 else "Verification withdrawn in the question editor.")


def rescore_key_change(change: AnswerKeyChange, *, actor, apply: bool = False) -> dict[str, Any]:
    """Score again the test attempts and question-bank answers one pending key change touches
    (tests_engine.scoring; dry run unless ``apply``). The attempts keep their first score and an AttemptRescore
    row per change; the key change is marked done. ``python manage.py rescore_key_changes`` does every pending one.
    """
    from tests_engine.scoring import rescore_pending_key_changes

    stats = rescore_pending_key_changes(apply=apply, change_ids=[change.pk])
    if apply and getattr(actor, "is_authenticated", False) and stats.get("key changes marked done"):
        change.refresh_from_db()
        change.rescored_by = actor
        change.save(update_fields=["rescored_by"])
    return {
        "change_id": change.id,
        "question_id": change.question_id,
        "old_key": change.old_key,
        "new_key": change.new_key,
        "attempts_rescored": stats.get("attempts rescored", 0),
        "answers_re_marked": stats.get("answers re-marked", 0),
        "qbank_answers_re_marked": stats.get("question-bank answers re-marked", 0),
        "apply": apply,
    }

