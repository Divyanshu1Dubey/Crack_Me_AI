"""One-shot data fixup: restore the `explanation` field for Qs whose
explanation is empty but who have one or more active `QuestionImage`
rows with `role='explanation'` (these were originally solution-cell
images that the material_importer publish path lost during ingestion).

The fix: write `[[img:<id>]]` tokens into `explanation` so the frontend
`FormattedText` resolver (and the auth-gated proxy view) can render
them inside the explanation card on the post-submit review screen.

Run:  python manage.py shell < scripts/backfill_explanation_for_expl_role_images.py
       OR  python scripts/backfill_explanation_for_expl_role_images.py
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from questions.models import Question, QuestionImage

# Restrict to Qs whose explanation is empty AND who have at least one
# active explanation-role image. Use a single SQL aggregate via
# `images.filter(role='explanation', is_active=True).exists()` rather
# than iterating to keep the scan fast (~50k rows).
candidates = (
    Question.objects.filter(explanation="")
    .filter(images__role="explanation", images__is_active=True)
    .distinct()
    .only("id")
)

fixed = 0
batch = []
for q in candidates.iterator(chunk_size=500):
    img_ids = list(
        q.images.filter(role="explanation", is_active=True)
        .order_by("id")
        .values_list("id", flat=True)
    )
    if not img_ids:
        continue
    new_exp = "\n\n".join(f"[[img:{iid}]]" for iid in img_ids).strip()
    if not new_exp:
        continue
    batch.append((q.id, new_exp))
    if len(batch) >= 200:
        with django.db.transaction.atomic():
            for qid, txt in batch:
                Question.objects.filter(id=qid).update(explanation=txt)
        fixed += len(batch)
        batch = []

if batch:
    with django.db.transaction.atomic():
        for qid, txt in batch:
            Question.objects.filter(id=qid).update(explanation=txt)
    fixed += len(batch)

print(f"Updated {fixed} questions.")