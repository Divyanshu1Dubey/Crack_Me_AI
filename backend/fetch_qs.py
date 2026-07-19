import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

q_ids = [5830, 6751, 5552, 1161, 6273, 4106, 6530, 6289, 6702, 6450, 6054]

out = []
for qid in q_ids:
    try:
        q = Question.objects.get(id=qid)
        out.append({
            "id": q.id,
            "text": q.question_text,
            "A": q.option_a,
            "B": q.option_b,
            "C": q.option_c,
            "D": q.option_d,
            "correct": q.correct_answer,
            "explanation": q.explanation
        })
    except Question.DoesNotExist:
        out.append({"id": qid, "error": "Not found"})

with open("q_debug.json", "w") as f:
    json.dump(out, f, indent=4)
