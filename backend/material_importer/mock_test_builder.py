"""Auto-generate `tests_engine.Test` records from imported material.

Given a batch id, the builder creates:

  * Subject test  — a `Test` per inferred subject
  * Topic test    — a `Test` per (subject, topic) pair
  * Mixed test    — one omnibus `Test` with N questions across subjects
  * PYQ test      — one per PYQ-named material

The questions are pulled from `ExtractedQuestion.status=approved` (or
`published`) rows that have the right `subject` (or matching filters).

Each generated test is idempotent: re-running replaces the question set
rather than creating a duplicate Test.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable, List

log = logging.getLogger(__name__)


_SUBJECT_CANON = {
    "medicine": "General Medicine",
    "general medicine": "General Medicine",
    "internal medicine": "General Medicine",
    "surgery": "Surgery",
    "obgy": "Obstetrics & Gynecology",
    "obstetrics": "Obstetrics & Gynecology",
    "gyne": "Obstetrics & Gynecology",
    "gynae": "Obstetrics & Gynecology",
    "gynaecology": "Obstetrics & Gynecology",
    "gynecology": "Obstetrics & Gynecology",
    "obstetrics & gynaecology": "Obstetrics & Gynecology",
    "pediatrics": "Pediatrics",
    "paediatrics": "Pediatrics",
    "psm": "Preventive & Social Medicine",
    "preventive": "Preventive & Social Medicine",
    "preventive & social medicine": "Preventive & Social Medicine",
    "orthopaedics": "Orthopaedics",
    "ortho": "Orthopaedics",
    "anesthesia": "Anaesthesia",
    "anaesthesia": "Anaesthesia",
    "dermatology": "Dermatology",
    "psychiatry": "Psychiatry",
    "ophthalmology": "Ophthalmology",
    "ent": "ENT",
}


def _resolve_subject_canon(inferred: str):
    from questions.models import Subject
    if not inferred:
        return None
    canon = _SUBJECT_CANON.get(inferred.strip().lower())
    if canon:
        subj = Subject.objects.filter(name__iexact=canon).first()
        if subj:
            return subj
    # Fallback: case-insensitive exact match directly.
    return Subject.objects.filter(name__iexact=inferred).first()


def _ensure_test(name: str, kind: str, description: str, subject=None, topic=None):
    """Idempotently upsert a Test row, preserving admin-set flags on rebuild.

    We NEVER blow away `is_published` on an existing row — admin/QA may have
    manually published the test between runs, and the importer must respect
    that. Same logic for `version`/`paper` if those exist on the model.
    """
    from tests_engine.models import Test

    field_names = {f.name for f in Test._meta.get_fields()}
    # Defaults only describe fields safe to overwrite on a rebuild.
    defaults = {
        "test_type": kind,
        "description": description,
        "time_limit_minutes": 60,
        "negative_marking": False,
        "subject": subject,
        "topic": topic,
    }
    defaults = {k: v for k, v in defaults.items() if k in field_names}

    existing = Test.objects.filter(title=name).first()
    if existing is not None:
        # Update only the safe-to-overwrite fields. Leave flags like
        # `is_published`, `version`, `paper` to whatever the admin set.
        for k, v in defaults.items():
            setattr(existing, k, v)
        existing.save()
        return existing

    # Brand-new test — set sensible defaults including is_published=False.
    defaults.setdefault("is_published", False)
    t = Test.objects.create(title=name, **defaults)
    return t


def build_for_batch(batch_id: int, max_per_test: int = 100) -> int:
    """Generate every auto-test the given batch supports. Returns count of tests built."""
    from tests_engine.models import Test
    from .models import ExtractedQuestion, ImportMaterial

    materials = ImportMaterial.objects.filter(batch_id=batch_id)
    if not materials.exists():
        return 0
    qs = ExtractedQuestion.objects.filter(material__in=materials, status__in=["pending", "approved", "published"])
    # Pre-clean any prior auto-tests for this batch so we never duplicate.
    Test.objects.filter(title__icontains=f"batch {batch_id}").delete()

    by_subject = defaultdict(list)
    by_topic = defaultdict(list)
    by_pyq_year = defaultdict(list)
    mixed: list = []
    test_count = 0

    for eq in qs.select_related("subject", "topic", "material"):
        subj = eq.subject.name if eq.subject_id else (eq.inferred_subject or "Imported")
        topic = eq.topic.name if eq.topic_id else (eq.inferred_topic or "")
        by_subject[subj].append(eq.id)
        by_topic[(subj, topic)].append(eq.id)
        mixed.append(eq.id)
        # PYQ year bucket.
        fn = (eq.material.original_filename or "").upper()
        if "PYQ" in fn:
            import re
            ym = re.search(r"(20\d{2})", eq.question_text or fn)
            year = ym.group(1) if ym else "unknown"
            by_pyq_year[year].append(eq.id)

    for subj, ids in by_subject.items():
        from questions.models import Subject
        subject_obj = (
            Subject.objects.filter(name__iexact=subj).first()
            or _resolve_subject_canon(subj)
        )
        t = _ensure_test(
            name=f"Auto • {subj} • batch {batch_id}",
            kind="subject",
            description=f"Auto-generated subject test from import batch {batch_id} ({subj}).",
            subject=subject_obj,
            topic=None,
        )
        _safe_set_questions(t, ids, max_per_test)
        test_count += 1

    for (subj, topic), ids in by_topic.items():
        if not topic:
            continue
        from questions.models import Subject, Topic
        subject_obj = (
            Subject.objects.filter(name__iexact=subj).first()
            or _resolve_subject_canon(subj)
        )
        topic_obj = (
            Topic.objects.filter(subject=subject_obj, name__iexact=topic).first()
            if subject_obj else None
        )
        t = _ensure_test(
            name=f"Auto • {subj} → {topic} • batch {batch_id}",
            kind="topic",
            description=f"Auto-generated topic test: {subj} → {topic}.",
            subject=subject_obj,
            topic=topic_obj,
        )
        _safe_set_questions(t, ids, max_per_test)
        test_count += 1

    for year, ids in by_pyq_year.items():
        if not ids:
            continue
        t = _ensure_test(
            name=f"Auto • PYQ {year} • batch {batch_id}",
            kind="pyq_year",
            description=f"Auto-generated PYQ test for year {year}.",
            subject=None,
            topic=None,
        )
        _safe_set_questions(t, ids, max_per_test)
        test_count += 1

    # Mixed omnibus test.
    if mixed:
        t = _ensure_test(
            name=f"Auto • Mixed • batch {batch_id}",
            kind="mixed",
            description=f"Mixed-source test from import batch {batch_id}.",
            subject=None,
            topic=None,
        )
        _safe_set_questions(t, mixed, max_per_test)
        test_count += 1

    log.info("Generated %d auto-tests for batch %d", test_count, batch_id)
    return test_count


# === ARCH-2: End-to-end "publish batch" pipeline ==========================
#
# Admin flow we want:
#   1. Admin imports material via `ingest_cms_material`.
#   2. Admin reviews the staging rows in Django admin
#      (`ExtractedQuestion` → "Approve selected" → "Publish selected to Question bank").
#   3. **OR** Admin clicks "Publish + Build Tests" once for the entire batch.
#
# The third step is what `publish_batch_and_build_tests` does. It is a
# convenience wrapper around:
#   * publishing every approved ExtractedQuestion → questions.Question
#   * then building the auto-tests from the resulting questions.
#
# The function is intentionally idempotent: re-running it adds nothing
# new (publishing skips rows that already have a `published_question`,
# and the test builder pre-deletes its own auto-tests by title pattern).
#
# This is the "ARCH-2" deliverable documented in
# `docs/MOCK_TEST_ARCHITECTURE.md` §3.


def publish_batch(batch_id: int, limit: int | None = None) -> int:
    """Publish every approved `ExtractedQuestion` in a batch to the live
    `questions.Question` table. Returns the number of *new* Questions
    created (re-publishing an already-published row counts as 0).
    """
    from .models import ExtractedQuestion
    from .publishing import publish_extracted_question

    qs = ExtractedQuestion.objects.filter(
        material__batch_id=batch_id, status="approved", published_question__isnull=True
    ).select_related("subject")
    if limit:
        qs = qs[:limit]
    n = 0
    for eq in qs:
        try:
            if publish_extracted_question(eq):
                n += 1
        except Exception as exc:  # pragma: no cover - DB edge case
            log.warning("publish_extracted_question(%s) failed: %s", eq.id, exc)
    return n


def publish_batch_and_build_tests(batch_id: int, max_per_test: int = 100) -> dict:
    """One-shot "publish this batch and build its mock tests" command.

    Returns a dict with `{"published": int, "tests_built": int}` for callers
    (admin action, management command, REST endpoint).
    """
    published = publish_batch(batch_id)
    tests_built = build_for_batch(batch_id, max_per_test=max_per_test)
    return {"published": published, "tests_built": tests_built}


def delete_batch(batch_id: int, *, delete_published: bool = False) -> dict:
    """Rollback / cleanup helper for an import batch.

    Default behaviour (safe): cascade-delete ImportMaterial (which
    cascade-deletes ExtractedQuestion, ExtractedTheory, ImportedImage via
    Django's on_delete=CASCADE) and the auto-generated Test rows whose
    title contains 'batch <id>'. *Leaves published Question rows alone* by
    default — set ``delete_published=True`` to also unlink them and delete
    the published Question rows.

    Returns: ``{"materials": int, "questions": int, "tests": int}``.
    """
    from django.db import transaction
    from .models import ExtractedQuestion, ImportMaterial, ImportBatch

    @transaction.atomic
    def _do():
        batch = ImportBatch.objects.filter(id=batch_id).first()
        if batch is None:
            return {"materials": 0, "questions": 0, "tests": 0}
        materials = list(ImportMaterial.objects.filter(batch_id=batch_id))
        eq_ids = list(ExtractedQuestion.objects.filter(material__batch_id=batch_id).values_list("id", flat=True))
        if delete_published:
            from .publishing import _nullify_published_links  # type: ignore
            _nullify_published_links(eq_ids)
        for m in materials:
            m.delete()
        # Drop auto-tests for this batch.
        from tests_engine.models import Test
        test_qs = Test.objects.filter(title__icontains=f"batch {batch_id}")
        tests_deleted = test_qs.count()
        test_qs.delete()
        return {"materials": len(materials), "questions": len(eq_ids), "tests": tests_deleted}
    return _do()


def _safe_set_questions(test_obj, ids, max_per_test):
    """Attach only the *published* Question ids from the staging list.

    `tests_engine.Test.questions` is a many-to-many to `questions.Question`
    (the canonical bank), not to `ExtractedQuestion`. We map each
    `ExtractedQuestion.id` to its `published_question_id` (id may be None
    if the row hasn't been promoted yet) and attach only those that exist.
    """
    from .models import ExtractedQuestion
    pub_ids = list(
        ExtractedQuestion.objects
        .filter(id__in=ids[:max_per_test], published_question__isnull=False)
        .values_list("published_question_id", flat=True)
    )
    if pub_ids:
        test_obj.questions.set(pub_ids)
    return len(pub_ids)
