import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crack_cms.settings")
django.setup()

from ai_engine.services import AIService
import json

question_text = "A 45-year-old lady presents with complaints of fatigue, muscle weakness along with bilateral multiple renal calculi... serum calcium levels of 11.4 mg%. What is the next best investigation required to arrive at a diagnosis?"
options = {
    "A": "MRI neck",
    "B": "Sestamibi scan",
    "C": "CECT head and neck",
    "D": "NCCT head and neck"
}
correct_answer = "B"
selected_answer = "C"

service = AIService()
try:
    print("Asking AI Service...")
    res = service.explain_after_answer(question_text, options, correct_answer, selected_answer, subject="General Medicine")
    print(json.dumps(res, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
