import os
import django
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

fixes = {
    5830: {'correct_answer': 'B'},
    6751: {'question_text': 'An 18 year old unmarried girl comes with complaints of heavy, prolonged bleeding during menses. Which among the following investigations is NOT usually advised?'}, # Removed the newline artifact
    5552: {'question_text': 'Which of the following are characteristics of Trichomonas vaginitis?\n1. Presence of greenish frothy discharge\n2. Vaginal pH > 4.5\n3. Presence of clue cells in microscopic examination\n4. Strawberry spots on the vaginal mucosa\nSelect the correct answer using the code given below:'},
    6750: {'question_text': 'Which one of the following statements regarding Bartholin’s glands is NOT true?', 'correct_answer': 'B'}, # Removed option words "hymen and labium minus"
    5208: {'question_text': 'Long term treatment of bipolar disorder with lithium carbonate can cause which of the following adverse effects?\n1. Weight loss\n2. Hypothyroidism\n3. Increased levels of parathyroid hormone\n4. Nephrogenic diabetes insipidus\nSelect the correct answer using the code given below:'},
    6723: {'question_text': 'Ventral hernia includes all EXCEPT:', 'correct_answer': 'D'}, # Removed stray '6'
    4484: {'question_text': 'Which of the following statements are correct regarding female sterilization?\n1. It can be done 24-48 hours following delivery.\n2. Ideal time for interval ligation is luteal phase preceding menstruation.\n3. It can be combined with medical termination of pregnancy.\n4. It is a preventive measure against serous ovarian cancer.\nSelect the correct answer using the code given below:'},
    5549: {'question_text': 'Which of the following information are provided by partograph?\n1. Colour of liquor\n2. Uterine contractions with duration and frequency\n3. Dilatation of cervix\nSelect the correct answer using the code given below:'},
    2026: {'correct_answer': 'C'},
    2017: {'correct_answer': 'B'},
    2011: {'correct_answer': 'C'},
    2009: {'correct_answer': 'C'},
    6677: {'correct_answer': 'B'},
    6678: {'correct_answer': 'C'}, # Retrograde amnesia is C (Ataxia, Ophthalamoplegia, Retrograde amnesia, Encephalopathy) Wait, let me check the script output. Option A: Ataxia, B: Ophthalamoplegia, C: Retrograde amnesia, D: Encephalopathy. So answer is C.
    5250: {'correct_answer': 'D'}
}

for qid, updates in fixes.items():
    try:
        q = Question.objects.get(id=qid)
        for key, value in updates.items():
            setattr(q, key, value)
        q.save()
        print(f"Updated Q#{qid}")
    except Question.DoesNotExist:
        print(f"Q#{qid} not found!")

print("Database update complete.")
