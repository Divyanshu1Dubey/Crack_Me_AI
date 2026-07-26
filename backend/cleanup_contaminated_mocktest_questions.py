"""Clean up contaminated Questions from the prior mocktest import + bogus years.

Run as a one-shot:
    python manage.py shell < cleanup_contaminated_mocktest_questions.py
or
    python cleanup_contaminated_mocktest_questions.py  (uses DJANGO_SETTINGS_MODULE)

What it does:
  1. Deletes all Question rows whose source ends with .docx (from the
     import_mocktests run that had a faulty parser).  After this, the
     `manage.py import_mocktests --dir ../cms_exclusive_material` re-run with
     the now-fixed parser will re-create them cleanly.
  2. Renames Subject(code='IMPORTED') → Subject(name='Expert Curated') so the
     UI can group these into a single "Expert Curated" section.
  3. Sets year=0 + exam_source='Expert Curated' on the IMPORTED rows so they
     no longer leak the 2026/2030/2035 placeholder years into the year filter.
  4. Also normalizes any Question with year > 2026 (bogus future years) to
     year=0.
"""
import os
import sys

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from django.db import transaction
from questions.models import Question, Subject, QuestionImage


def main() -> None:
    # ---- 1. delete docx-sourced rows + their images ----
    with transaction.atomic():
        docx_qs = Question.objects.filter(source__endswith=".docx")
        docx_ids = list(docx_qs.values_list("id", flat=True))
        n_imgs = QuestionImage.objects.filter(question_id__in=docx_ids).count()
        QuestionImage.objects.filter(question_id__in=docx_ids).delete()
        n_q = docx_qs.count()
        docx_qs.delete()
        print(f"[1] Deleted {n_q} docx-sourced Question rows + {n_imgs} images")

    # ---- 2. rename IMPORTED subject to Expert Curated ----
    with transaction.atomic():
        subj = Subject.objects.filter(code="IMPORTED").first()
        if subj:
            old_name = subj.name
            subj.name = "Expert Curated"
            subj.code = "EXPERT"
            subj.save(update_fields=["name", "code"])
            print(f"[2] Renamed Subject #{subj.id}: {old_name!r} -> 'Expert Curated' (code=EXPERT)")

    # ---- 3. set IMPORTED/EXPERT rows: year=0 + exam_source ----
    with transaction.atomic():
        expert_rows = Question.objects.filter(subject__code="EXPERT")
        n = expert_rows.update(year=0, exam_source="Expert Curated")
        print(f"[3] Set year=0, exam_source='Expert Curated' on {n} Expert rows")

    # ---- 4. any leftover future-year rows ----
    with transaction.atomic():
        future = Question.objects.filter(year__gt=2026)
        n = future.count()
        future.update(year=0)
        print(f"[4] Reset year>2026 on {n} rows to year=0")

    # ---- summary ----
    from django.db.models import Count
    print()
    print("--- POST-CLEANUP TOTALS ---")
    print(f"Total Questions: {Question.objects.count()}")
    print(f"Total QuestionImages: {QuestionImage.objects.count()}")
    print("By subject:")
    for s in Question.objects.values("subject__code", "exam_type").annotate(c=Count("id")).order_by("-c")[:12]:
        print(f"  {s['exam_type']}/{s['subject__code']}: {s['c']}")
    print("By year (top 15):")
    for y in Question.objects.values("year").annotate(c=Count("id")).order_by("year"):
        print(f"  year={y['year']}: {y['c']}")


if __name__ == "__main__":
    main()