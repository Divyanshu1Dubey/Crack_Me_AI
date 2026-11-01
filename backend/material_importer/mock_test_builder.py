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

Test ownership: the tests a batch generated are found by the ids recorded
in ``ImportBatch.summary`` ("auto_test_ids" / "mock_test_ids") plus the
exact generated title shape ``"Auto • … • batch <id>"``. They used to be
found with ``title__icontains="batch <id>"``, which also matched batch 10,
11, 100… and any test whose title merely contained the phrase, and every
publish deleted (and so cascade-deleted the student attempts of) those
tests. A test that students have attempted is never deleted by the
importer: it is unpublished instead, so attempt history survives.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable, List

log = logging.getLogger(__name__)

# Title shape of every importer-generated test: "Auto • <label> • batch <id>".
AUTO_TEST_PREFIX = "Auto • "


def _batch_title_suffix(batch_id: int) -> str:
    return f" • batch {batch_id}"


def _batch_tests_queryset(batch_id: int, recorded_ids: Iterable[int] = ()):
    """Tests generated for exactly this batch (never batch 10 for batch 1)."""
    from django.db.models import Q
    from tests_engine.models import Test

    exact_title = Q(title__startswith=AUTO_TEST_PREFIX) & Q(
        title__endswith=_batch_title_suffix(batch_id)
    )
    ids = [int(i) for i in recorded_ids if str(i).isdigit()]
    if ids:
        return Test.objects.filter(exact_title | Q(id__in=ids))
    return Test.objects.filter(exact_title)


def _retire_test(test) -> str:
    """Remove an importer-generated test without destroying student history.

    A test with attempts is unpublished (attempts and responses survive);
    a test nobody attempted is deleted. Returns "unpublished" / "deleted".
    """
    if test.attempts.exists():
        if test.is_published:
            test.is_published = False
            test.save(update_fields=["is_published", "updated_at"])
        return "unpublished"
    test.delete()
    return "deleted"


def _record_batch_test_ids(batch_id: int, key: str, ids: Iterable[int], *, replace: bool) -> None:
    """Persist the ids of tests built for a batch in ``ImportBatch.summary[key]``.

    Uses a queryset ``update`` so it never overwrites other batch fields
    (status, counters) that a concurrent writer may have changed.
    """
    from .models import ImportBatch

    batch = ImportBatch.objects.filter(id=batch_id).only("id", "summary").first()
    if batch is None:
        return
    summary = dict(batch.summary or {})
    new_ids = {int(i) for i in ids}
    if not replace:
        new_ids |= {int(i) for i in (summary.get(key) or []) if str(i).isdigit()}
    summary[key] = sorted(new_ids)
    ImportBatch.objects.filter(id=batch_id).update(summary=summary)


def _published_question_ids(eq_ids: Iterable[int], limit: int | None = None) -> list[int]:
    """Map staging ids to live, active Question ids (order kept, deduped).

    Filters to published rows FIRST and only then applies ``limit`` — the
    old code sliced the staging ids first and so built empty or undersized
    tests whenever the first N rows were not published yet.
    """
    from .models import ExtractedQuestion

    eq_ids = list(eq_ids)
    pairs = dict(
        ExtractedQuestion.objects
        .filter(
            id__in=eq_ids,
            published_question__isnull=False,
            published_question__is_active=True,
        )
        .values_list("id", "published_question_id")
    )
    out: list[int] = []
    seen: set[int] = set()
    for eq_id in eq_ids:
        pid = pairs.get(eq_id)
        if pid and pid not in seen:
            seen.add(pid)
            out.append(pid)
            if limit and len(out) >= limit:
                break
    return out


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
    """Generate every auto-test the given batch supports. Returns count of tests built.

    Tests are upserted by their exact title (``_ensure_test``), so a rebuild
    keeps each test's id, its ``is_published`` flag and its attempts. Only
    tests that end up with at least one live question are built and counted.
    A test this batch built on a previous run that is no longer produced is
    retired (deleted, or unpublished if students attempted it).
    """
    from tests_engine.models import Test
    from .models import ExtractedQuestion, ImportBatch, ImportMaterial

    materials = ImportMaterial.objects.filter(batch_id=batch_id)
    if not materials.exists():
        return 0
    qs = ExtractedQuestion.objects.filter(
        material__in=materials,
        status__in=["pending", "approved", "published"],
        published_question__isnull=False,
        published_question__is_active=True,
    )

    by_subject = defaultdict(list)
    by_topic = defaultdict(list)
    by_pyq_year = defaultdict(list)
    mixed: list = []
    built_ids: list[int] = []

    def _build(name, kind, description, ids, subject=None, topic=None):
        pub_ids = _published_question_ids(ids, max_per_test)
        if not pub_ids:
            return
        t = _ensure_test(name=name, kind=kind, description=description,
                         subject=subject, topic=topic)
        t.questions.set(pub_ids)
        Test.objects.filter(pk=t.pk).update(num_questions=len(pub_ids))
        built_ids.append(t.id)

    for eq in qs.select_related("subject", "topic", "material", "published_question"):
        subj = eq.subject.name if eq.subject_id else (eq.inferred_subject or "Imported")
        topic = eq.topic.name if eq.topic_id else (eq.inferred_topic or "")
        by_subject[subj].append(eq.id)
        by_topic[(subj, topic)].append(eq.id)
        mixed.append(eq.id)
        # PYQ year bucket: the live question's year (taken from the file /
        # batch metadata at publish time), never a year quoted in the stem.
        fn = (eq.material.original_filename or "").upper()
        if "PYQ" in fn:
            pub_year = getattr(eq.published_question, "year", 0) or 0
            year = str(pub_year) if pub_year else "unknown"
            by_pyq_year[year].append(eq.id)

    for subj, ids in by_subject.items():
        from questions.models import Subject
        subject_obj = (
            Subject.objects.filter(name__iexact=subj).first()
            or _resolve_subject_canon(subj)
        )
        _build(
            name=f"Auto • {subj} • batch {batch_id}",
            kind="subject",
            description=f"Auto-generated subject test from import batch {batch_id} ({subj}).",
            ids=ids,
            subject=subject_obj,
            topic=None,
        )

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
        _build(
            name=f"Auto • {subj} → {topic} • batch {batch_id}",
            kind="topic",
            description=f"Auto-generated topic test: {subj} → {topic}.",
            ids=ids,
            subject=subject_obj,
            topic=topic_obj,
        )

    for year, ids in by_pyq_year.items():
        if not ids:
            continue
        _build(
            name=f"Auto • PYQ {year} • batch {batch_id}",
            kind="pyq_year",
            description=f"Auto-generated PYQ test for year {year}.",
            ids=ids,
            subject=None,
            topic=None,
        )

    # Mixed omnibus test.
    if mixed:
        _build(
            name=f"Auto • Mixed • batch {batch_id}",
            kind="mixed",
            description=f"Mixed-source test from import batch {batch_id}.",
            ids=mixed,
            subject=None,
            topic=None,
        )

    # Retire tests this batch built on an earlier run but no longer produces
    # (e.g. a subject bucket that lost all its live questions). Only ids this
    # builder recorded itself are considered, so one-off mock tests from
    # generate-mock and tests of other batches are never touched.
    batch = ImportBatch.objects.filter(id=batch_id).only("id", "summary").first()
    previous_ids = {
        int(i) for i in ((batch.summary or {}).get("auto_test_ids") or [])
        if str(i).isdigit()
    } if batch else set()
    for stale in Test.objects.filter(id__in=previous_ids - set(built_ids)):
        _retire_test(stale)
    _record_batch_test_ids(batch_id, "auto_test_ids", built_ids, replace=True)

    log.info("Generated %d auto-tests for batch %d", len(built_ids), batch_id)
    return len(built_ids)


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
# and the test builder upserts its own auto-tests by exact title, keeping
# their ids, publish flags and student attempts).
#
# This is the "ARCH-2" deliverable documented in
# `docs/MOCK_TEST_ARCHITECTURE.md` §3.


def publish_batch(batch_id: int, limit: int | None = None, on_progress=None) -> int:
    """Publish every approved `ExtractedQuestion` in a batch to the live
    `questions.Question` table. Returns the number of *new* Questions
    created (re-publishing an already-published row counts as 0).

    ``on_progress(done_rows)`` (optional) is called every 100 rows so a
    background caller can record a heartbeat.
    """
    from .models import ExtractedQuestion
    from .publishing import publish_extracted_question

    qs = ExtractedQuestion.objects.filter(
        material__batch_id=batch_id, status="approved", published_question__isnull=True
    ).select_related("subject")
    if limit:
        qs = qs[:limit]
    n = 0
    for i, eq in enumerate(qs, start=1):
        try:
            if publish_extracted_question(eq):
                n += 1
        except Exception as exc:  # pragma: no cover - DB edge case
            log.warning("publish_extracted_question(%s) failed: %s", eq.id, exc)
        if on_progress is not None and i % 100 == 0:
            try:
                on_progress(i)
            except Exception:  # pragma: no cover - heartbeat is best effort
                pass
    return n


def publish_batch_and_build_tests(batch_id: int, max_per_test: int = 100, on_progress=None) -> dict:
    """One-shot "publish this batch and build its mock tests" command.

    Returns a dict with `{"published": int, "tests_built": int}` for callers
    (admin action, management command, REST endpoint).
    """
    published = publish_batch(batch_id, on_progress=on_progress)
    tests_built = build_for_batch(batch_id, max_per_test=max_per_test)
    return {"published": published, "tests_built": tests_built}


def delete_batch(batch_id: int, *, delete_published: bool = False) -> dict:
    """Rollback / cleanup helper for an import batch.

    Default behaviour (safe): cascade-delete ImportMaterial (which
    cascade-deletes ExtractedQuestion, ExtractedTheory, ImportedImage via
    Django's on_delete=CASCADE) and retire this batch's auto-generated
    tests (exact ownership, see module docstring): tests nobody attempted
    are deleted, tests with student attempts are unpublished and kept.
    *Leaves published Question rows live* by default.

    ``delete_published=True`` also removes the batch's published Question
    rows from the live bank the same way the admin "Remove from bank"
    action does: ``is_active=False, is_dropped=True, admin_edited=True``
    plus a ``RemovedQuestion`` tombstone (a hard delete is blocked by the
    PROTECT FKs and would destroy user history).

    Either way the published Question ids are returned (and the view stores
    them in ``batch.summary["rollback"]``), so they stay traceable after the
    staging rows that linked them to the batch are gone.

    Returns: ``{"materials", "questions", "tests", "tests_unpublished",
    "published_question_ids", "published_questions_removed"}``.
    """
    from django.db import transaction
    from .models import ExtractedQuestion, ImportMaterial, ImportBatch

    @transaction.atomic
    def _do():
        batch = ImportBatch.objects.filter(id=batch_id).first()
        if batch is None:
            return {"materials": 0, "questions": 0, "tests": 0, "tests_unpublished": 0,
                    "published_question_ids": [], "published_questions_removed": 0}
        materials = list(ImportMaterial.objects.filter(batch_id=batch_id))
        eq_qs = ExtractedQuestion.objects.filter(material__batch_id=batch_id)
        eq_ids = list(eq_qs.values_list("id", flat=True))
        published_ids = sorted(set(
            eq_qs.filter(published_question__isnull=False)
            .values_list("published_question_id", flat=True)
        ))
        removed = 0
        if delete_published and published_ids:
            removed = _remove_published_questions(published_ids, batch_id)

        summary = batch.summary or {}
        recorded = list(summary.get("auto_test_ids") or []) + list(summary.get("mock_test_ids") or [])
        tests_deleted = tests_unpublished = 0
        for t in _batch_tests_queryset(batch_id, recorded):
            if _retire_test(t) == "deleted":
                tests_deleted += 1
            else:
                tests_unpublished += 1

        for m in materials:
            m.delete()
        return {
            "materials": len(materials),
            "questions": len(eq_ids),
            "tests": tests_deleted,
            "tests_unpublished": tests_unpublished,
            "published_question_ids": published_ids,
            "published_questions_removed": removed,
        }
    return _do()


def _remove_published_questions(question_ids, batch_id: int) -> int:
    """Soft-delete live questions + tombstone them (mirrors "Remove from bank")."""
    from questions.models import Question, RemovedQuestion, compute_stem_hash

    n = 0
    for q in Question.objects.filter(id__in=list(question_ids)):
        RemovedQuestion.objects.get_or_create(
            exam_source=q.exam_source or "",
            year=q.year,
            source_number=getattr(q, "display_number", None),
            question_text_hash=compute_stem_hash(q.question_text or ""),
            defaults={
                "original_question_id": q.id,
                "reason": f"Import Center rollback of batch {batch_id}",
            },
        )
        if q.is_active or not q.is_dropped:
            q.is_active = False
            q.is_dropped = True
            q.admin_edited = True
            q.save(update_fields=["is_active", "is_dropped", "admin_edited"])
            n += 1
    return n


def _safe_set_questions(test_obj, ids, max_per_test):
    """Attach only the *published* Question ids from the staging list.

    `tests_engine.Test.questions` is a many-to-many to `questions.Question`
    (the canonical bank), not to `ExtractedQuestion`. We map each
    `ExtractedQuestion.id` to its `published_question_id` (id may be None
    if the row hasn't been promoted yet) and attach only those that exist.
    Published rows are selected before ``max_per_test`` is applied, and
    ``num_questions`` always matches what was attached.
    """
    pub_ids = _published_question_ids(ids, max_per_test)
    test_obj.questions.set(pub_ids)
    type(test_obj).objects.filter(pk=test_obj.pk).update(num_questions=len(pub_ids))
    return len(pub_ids)
