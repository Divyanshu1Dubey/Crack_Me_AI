import os
import django
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

q_ids = [5830, 6751, 5552, 6750, 5208, 6723, 4484, 5549, 2026, 2017, 2011, 2009, 6677, 6678, 5250]

for qid in q_ids:
    try:
        q = Question.objects.get(id=qid)
        print(f"\n--- Q#{qid} ---")
        print(f"TEXT: {q.question_text}")
        print(f"OPTS: {q.option_a} | {q.option_b} | {q.option_c} | {q.option_d}")
        print(f"ANS: {q.correct_answer}")
    except Question.DoesNotExist:
        print(f"Q#{qid} NOT FOUND")
