import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

# 1. Fix Q#5830 Explanation
try:
    q = Question.objects.get(id=5830)
    q.explanation = "Prevalence of neonatal hypothyroidism: This is the correct choice. The newborn thyroid is exceptionally vulnerable to a lack of iodine due to its accelerated intrinsic turnover rate. Fluctuations in environmental iodine levels reflect instantly in neonatal TSH spikes. A high prevalence acts as the most sensitive early clinical warning sign that an environment lacks the iodine required to protect against endemic brain damage. So option B."
    q.save()
    print("Updated Q#5830 explanation.")
except Question.DoesNotExist:
    pass

# 2. Deactivate wrong/unmatched questions based on user feedback
deactivate_ids = [6530, 6289, 6702, 6450, 6054, 4106]
for qid in deactivate_ids:
    try:
        q = Question.objects.get(id=qid)
        q.is_active = False
        q.save()
        print(f"Deactivated Q#{qid}")
    except Question.DoesNotExist:
        print(f"Could not find Q#{qid}")

print("Database fixes complete.")
