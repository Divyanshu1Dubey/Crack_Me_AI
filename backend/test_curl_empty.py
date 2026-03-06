import requests
import json

url = "http://localhost:8000/api/ai/explain-answer/"
payload = {
    "question_text": "A 45-year-old lady presents with complaints of fatigue, muscle weakness along with bilateral multiple renal calculi... serum calcium levels of 11.4 mg%. What is the next best investigation required to arrive at a diagnosis?",
    "options": {
        "A": "MRI neck",
        "B": "Sestamibi scan",
        "C": "CECT head and neck",
        "D": "NCCT head and neck"
    },
    "correct_answer": "",
    "selected_answer": "C",
    "subject": "General Medicine",
    "topic": ""
}
try:
    response = requests.post(url, json=payload)
    print("Status Code:", response.status_code)
    print("Response JSON:", response.text)
except Exception as e:
    print("Error:", e)
