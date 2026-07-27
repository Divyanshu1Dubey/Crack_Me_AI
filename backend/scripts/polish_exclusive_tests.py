"""Polish the auto-built CMS Exclusive Q4 2026 Tests with proper naming,
canonical Subject linkage, realistic exam settings, and student-facing
descriptions.

Replaces the placeholder names produced by the first build script with:

  • Per-subject:  "CMS Exclusive Mock — <Canonical Subject> (Q4 2026)"
                  with proper subject FK, realistic time limit, and
                  0.33 negative marking (UPSC CMS convention).

  • Per-source-file (small batches): "CMS Exclusive Mini Test — <clean
    filename>". A "mini test" label signals to students that this is a
    focused 3-30 question drill, not a full mock.

  • Grand mixed:  "CMS Exclusive Grand Test — Q4 2026" — the full 279-q
    paper, 279 min, with all standard exam settings.

  • Image-based:  "CMS Exclusive Image-Based Test — Q4 2026" — image
    diagnosis drill covering all subjects.

Settings convention (matches the existing UPSC CMS published tests):
  • 1 minute per question.
  • Negative marking = True, value = 0.33.
  • Negative marking only enabled when n >= 10 (a 3-q mini test
    doesn't need marking).
  • description: includes source files, image count, and a one-line
    student-facing tip.

Idempotent — re-running upserts the same Tests (matched by exact title).

Run:
    python manage.py shell -c "exec(open('scripts/polish_exclusive_tests.py').read()); main()"
"""
from __future__ import annotations

import re
from collections import Counter

from django.db import transaction

from material_importer.models import ExtractedQuestion
from material_importer.mock_test_builder import _ensure_test, _safe_set_questions
from questions.models import QuestionImage, Subject
from tests_engine.models import Test


QUARTER_LABEL = "Q4 2026"
SUITE_PREFIX = "CMS Exclusive"
NEGATIVE_MARK_THRESHOLD = 10  # don't add negative marking to sub-10-q mini tests

# Canonical subject names from the DB. We never display the importer's
# classifier's inferred_subject verbatim; we map to these names so student
# labels match the rest of the app (Settings, Analytics, Onboarding).
SUBJECT_CANON = {
    # imp-classifier output  → canonical DB Subject.name
    "medicine": "General Medicine",
    "general medicine": "General Medicine",
    "internal medicine": "General Medicine",
    "surgery": "General Surgery",
    "general surgery": "General Surgery",
    "obgy": "Obstetrics & Gynaecology",
    "obstetrics": "Obstetrics & Gynaecology",
    "gyne": "Obstetrics & Gynaecology",
    "gynae": "Obstetrics & Gynaecology",
    "gynaecology": "Obstetrics & Gynaecology",
    "obstetrics & gynaecology": "Obstetrics & Gynaecology",
    "pediatrics": "Paediatrics",
    "paediatrics": "Paediatrics",
    "dermatology": "Dermatology",
    "ent": "ENT",
    "ophthalmology": "Ophthalmology",
    "psychiatry": "Psychiatry",
    "orthopaedics": "Orthopaedics",
    "ortho": "Orthopaedics",
    "anaesthesia": "Anaesthesia",
    "anesthesia": "Anaesthesia",
    "psm": "Community Medicine",
    "preventive": "Community Medicine",
    "preventive & social medicine": "Community Medicine",
}


def _subject_for_eq(eq: ExtractedQuestion):
    """Return the canonical questions.Subject (or None) for a staging row."""
    # 1. Already resolved FK
    if eq.subject_id and eq.subject and eq.subject.name in {s.name for s in Subject.objects.all()}:
        return eq.subject
    raw = (eq.inferred_subject or "").strip()
    if not raw:
        return None
    canon_name = SUBJECT_CANON.get(raw.lower())
    if canon_name:
        subj = Subject.objects.filter(name__iexact=canon_name).first()
        if subj:
            return subj
    # Final fallback: case-insensitive exact match
    return Subject.objects.filter(name__iexact=raw).first()


# ---------------------------------------------------------------------------
# Per-subject tests
# ---------------------------------------------------------------------------

@transaction.atomic
def polish_per_subject_tests() -> dict[str, int]:
    """Build per-canonical-subject test with proper FK and naming."""
    qs = (ExtractedQuestion.objects
          .filter(material__batch__source_label__icontains="CMS Exclusive Q4 2026",
                  published_question__isnull=False)
          .select_related("subject", "material"))

    # Group by *canonical* subject
    by_subject: dict[str, list[int]] = {}
    for eq in qs:
        subj_obj = _subject_for_eq(eq)
        if subj_obj is None:
            continue
        by_subject.setdefault(subj_obj.name, []).append(eq.id)

    print("[1] Per-subject (canonical):")
    built = {}
    for subj_name, eq_ids in sorted(by_subject.items()):
        subj_obj = Subject.objects.filter(name__iexact=subj_name).first()
        q_count = len(eq_ids)
        title = f"{SUITE_PREFIX} Mock — {subj_name} ({QUARTER_LABEL})"

        # Image count
        pub_ids = list(ExtractedQuestion.objects
                       .filter(id__in=eq_ids, published_question__isnull=False)
                       .values_list("published_question_id", flat=True))
        n_img = QuestionImage.objects.filter(question_id__in=pub_ids).values("question_id").distinct().count()

        desc = (
            f"Subject mock test covering {subj_name} from the "
            f"{SUITE_PREFIX} {QUARTER_LABEL} question bank. "
            f"{q_count} questions, {n_img} image-based. "
            f"{'Includes negative marking (–⅓ per wrong answer). ' if q_count >= NEGATIVE_MARK_THRESHOLD else ''}"
            f"Time: {q_count} minutes. Best taken as a timed practice after completing the chapter."
        )

        t = _ensure_test(
            name=title,
            kind="subject",
            description=desc,
            subject=subj_obj,
        )
        t.exam_type = "cms"
        t.num_questions = q_count
        t.time_limit_minutes = max(q_count, 10)  # minimum 10 min
        t.negative_marking = q_count >= NEGATIVE_MARK_THRESHOLD
        t.negative_mark_value = 0.33
        t.is_published = True
        t.save()

        _safe_set_questions(t, eq_ids, max_per_test=500)
        built[subj_name] = t.id
        print(f"  ✓ {t.id:>4}  q={q_count:>3}  img={n_img:>2}  {title!r}")
    return built


# ---------------------------------------------------------------------------
# Per-source-file tests (small mini-tests)
# ---------------------------------------------------------------------------

# Files we want to surface as "Mini Test" entries instead of standalone
# "Mock Test" entries. Trigger: file has <= 40 published Qs.
MINI_TEST_Q_LIMIT = 40

# Manual cleanup of file names for student-facing display.
# Final labels MUST NOT start with "Mini Test — Mini Test …" (avoid double
# prefix). Always produce a clean, Title-Cased label that reads naturally
# after "CMS Exclusive Mini Test — " or "CMS Exclusive Mock — ".
_FILE_NAME_CLEAN = {
    "Mini test-2 .docx": "Mini Test 2",
    "Mini test-4.docx": "Mini Test 4",
    "Mini test unit 9 gynae.docx": "Gynaecology — Unit 9",
    "Mini test-1 newborn care.docx": "Newborn Care",
    "Mini Test-3 Dermatology.docx": "Dermatology — Box Set",
    "Mini Test-3 Systemic pediatrics.docx": "Systemic Paediatrics — Box Set",
    "minitest_unit_9.docx": "Paediatrics — Unit 9",
    "Neuro_PYQ_boxes_IN.docx": "Neuro PYQ — Image Diagnosis",
    "obgy_Question_boxes.docx": "OBG — Question Boxes",
    "Pediatrics_test4_boxes.docx": "Paediatrics — Test 4 Boxes",
    "Question boxes_SURGERY.docx": "Surgery — Question Boxes",
    "Respiratory mini test-2.docx": "Respiratory — Mini Test 2",
    "surgery unit 6 mini test (1).docx": "Surgery Unit 6 — Mini Test 1",
    "surgery_unit6_question_Inboxes.docx": "Surgery Unit 6 — Question Boxes",
    "meduraa_test5_in_boxes.docx": "Meduraa Test 5 — Image Boxes",
}


def _pretty_filename(stem: str) -> str:
    """Convert a filename stem into a Title-Case label."""
    # Drop trailing "(1)", "(2)" suffixes typical of duplicate filenames
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem).strip()
    # Convert snake / underscores to spaces, then title-case
    stem = stem.replace("_", " ").replace("-", " ").strip()
    return stem.title()


@transaction.atomic
def polish_per_file_tests() -> dict[str, int]:
    """Build a clean mini-test or full-mock per source file."""
    qs = (ExtractedQuestion.objects
          .filter(material__batch__source_label__icontains="CMS Exclusive Q4 2026",
                  published_question__isnull=False)
          .select_related("material"))

    by_file: dict[str, list[int]] = {}
    for eq in qs:
        by_file.setdefault(eq.material.original_filename, []).append(eq.id)

    print("\n[2] Per-source-file (Mini Test / Mock — by size):")
    built = {}
    for fname, eq_ids in sorted(by_file.items()):
        q_count = len(eq_ids)
        pretty = _FILE_NAME_CLEAN.get(fname) or _pretty_filename(fname.replace(".docx", "").replace(".pdf", ""))
        if q_count <= MINI_TEST_Q_LIMIT:
            title = f"{SUITE_PREFIX} Mini Test — {pretty}"
            test_kind = "topic"  # small focused drill
        else:
            title = f"{SUITE_PREFIX} Mock — {pretty}"
            test_kind = "subject"  # full subject mock from one source file

        pub_ids = list(ExtractedQuestion.objects
                       .filter(id__in=eq_ids, published_question__isnull=False)
                       .values_list("published_question_id", flat=True))
        n_img = QuestionImage.objects.filter(question_id__in=pub_ids).values("question_id").distinct().count()

        desc = (
            f"{'Image-rich mini drill' if n_img >= q_count * 0.5 else 'Focused practice drill'} "
            f"drawn from {fname}. {q_count} questions, "
            f"{n_img} with images. "
            f"{'Negative marking (–⅓ per wrong answer). ' if q_count >= NEGATIVE_MARK_THRESHOLD else 'No negative marking. '}"
            f"Best taken in one sitting."
        )

        t = _ensure_test(
            name=title,
            kind=test_kind,
            description=desc,
        )
        t.exam_type = "cms"
        t.num_questions = q_count
        t.time_limit_minutes = max(q_count, 5)
        t.negative_marking = q_count >= NEGATIVE_MARK_THRESHOLD
        t.negative_mark_value = 0.33
        t.is_published = True
        t.save()

        _safe_set_questions(t, eq_ids, max_per_test=500)
        built[fname] = t.id
        icon = "📝" if test_kind == "topic" else "📘"
        print(f"  {icon} {t.id:>4}  q={q_count:>3}  img={n_img:>2}  {title!r}")
    return built


# ---------------------------------------------------------------------------
# Grand Test (mixed)
# ---------------------------------------------------------------------------

@transaction.atomic
def polish_grand_test() -> int:
    """Single 279-q mixed paper across the entire suite."""
    eq_ids = list(
        ExtractedQuestion.objects
        .filter(material__batch__source_label__icontains="CMS Exclusive Q4 2026",
                published_question__isnull=False)
        .values_list("id", flat=True)
    )
    q_count = len(eq_ids)
    pub_ids = list(ExtractedQuestion.objects
                   .filter(id__in=eq_ids, published_question__isnull=False)
                   .values_list("published_question_id", flat=True))
    n_img = QuestionImage.objects.filter(question_id__in=pub_ids).values("question_id").distinct().count()

    # Subject mix
    subj_counter = Counter()
    for eq in ExtractedQuestion.objects.filter(id__in=eq_ids).select_related("subject"):
        subj = _subject_for_eq(eq)
        if subj:
            subj_counter[subj.name] += 1
        elif (eq.inferred_subject or "").strip():
            raw = eq.inferred_subject.strip()
            canon = SUBJECT_CANON.get(raw.lower(), raw)
            subj_counter[canon] += 1

    subj_lines = ", ".join(f"{n} {s}" for s, n in subj_counter.most_common())

    title = f"{SUITE_PREFIX} Grand Test — {QUARTER_LABEL}"
    desc = (
        f"Full-length Grand Test covering all 15 source files of the "
        f"{SUITE_PREFIX} {QUARTER_LABEL} bank. {q_count} questions across "
        f"{len(subj_counter)} subjects ({subj_lines}), with {n_img} "
        f"image-based questions. Standard UPSC CMS negative marking (–⅓ per "
        f"wrong answer). Best taken as a single timed paper to simulate "
        f"exam conditions — allow {q_count} minutes uninterrupted."
    )

    t = _ensure_test(name=title, kind="mixed", description=desc)
    t.exam_type = "cms"
    t.num_questions = q_count
    t.time_limit_minutes = q_count
    t.negative_marking = True
    t.negative_mark_value = 0.33
    t.is_published = True
    t.save()
    _safe_set_questions(t, eq_ids, max_per_test=500)
    print(f"\n[3] Grand Test: {title!r}  q={q_count}  img={n_img}  id={t.id}")
    return t.id


# ---------------------------------------------------------------------------
# Image-Based Test
# ---------------------------------------------------------------------------

@transaction.atomic
def polish_image_test() -> int:
    """Test consisting only of image-bearing questions."""
    eq_ids = list(
        ExtractedQuestion.objects
        .filter(material__batch__source_label__icontains="CMS Exclusive Q4 2026",
                published_question__isnull=False)
        .exclude(image_refs=[])
        .values_list("id", flat=True)
    )
    q_count = len(eq_ids)

    title = f"{SUITE_PREFIX} Image-Based Test — {QUARTER_LABEL}"
    desc = (
        f"Image-based diagnostic test from the {SUITE_PREFIX} {QUARTER_LABEL} "
        f"bank. {q_count} questions — every question contains at least one "
        f"clinical image, X-ray, photograph, or histology slide. Mixed "
        f"subjects. Standard UPSC CMS negative marking (–⅓ per wrong "
        f"answer). Best taken with full-attention image viewing time."
    )

    t = _ensure_test(name=title, kind="mixed", description=desc)
    t.exam_type = "cms"
    t.num_questions = q_count
    t.time_limit_minutes = q_count
    t.negative_marking = True
    t.negative_mark_value = 0.33
    t.is_published = True
    t.save()
    _safe_set_questions(t, eq_ids, max_per_test=500)
    print(f"\n[4] Image-Based: {title!r}  q={q_count}  id={t.id}")
    return t.id


# ---------------------------------------------------------------------------
# Cleanup: kill the old placeholder tests so the suite has no doubles
# ---------------------------------------------------------------------------

def cleanup_placeholder_tests() -> int:
    """Remove the prior-build tests with the old naming so we end with a clean palette."""
    old_titles = list(
        Test.objects
        .filter(title__icontains="CMS Exclusive")
        .exclude(title__startswith=SUITE_PREFIX)
        .values_list("id", flat=True)
    )
    if old_titles:
        Test.objects.filter(id__in=old_titles).delete()
    # Also drop any zero-question auto-tests (leftover from build_for_batch)
    zero_q_ids = [t.id for t in Test.objects.filter(title__startswith=SUITE_PREFIX) if t.questions.count() == 0]
    if zero_q_ids:
        Test.objects.filter(id__in=zero_q_ids).delete()
    return len(old_titles) + len(zero_q_ids)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"=== {SUITE_PREFIX} {QUARTER_LABEL} — Test Polish ===\n")
    n_removed = cleanup_placeholder_tests()
    if n_removed:
        print(f"Removed {n_removed} placeholder/empty test(s).\n")

    by_subj = polish_per_subject_tests()
    by_file = polish_per_file_tests()
    grand_id = polish_grand_test()
    image_id = polish_image_test()

    print(f"\n=== Done. ===")
    print(f"  subject tests: {len(by_subj)}")
    print(f"  per-file tests: {len(by_file)}")
    print(f"  Grand Test id: {grand_id}")
    print(f"  Image Test id: {image_id}")

    # Final summary
    print("\n=== Final CMS Exclusive palette ===")
    for t in Test.objects.filter(title__startswith=SUITE_PREFIX, is_published=True).order_by("id"):
        marker = ""
        if "Mock" in t.title and "Mini" not in t.title: marker = "📘"
        elif "Mini" in t.title: marker = "📝"
        elif "Grand" in t.title: marker = "🏆"
        elif "Image" in t.title: marker = "🖼️ "
        print(f"  {marker} #{t.id:>4}  q={t.questions.count():>3}  {t.title}")


if __name__ == "__main__":
    main()
