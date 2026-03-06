import requests
import json

url = "http://localhost:8000/api/ai/explain-answer/"
payload = {
    "question_text": "A 45-year-old lady presents...",
    "correct_answer": "B",
    "selected_answer": "C"
}
try:
    response = requests.post(url, json=payload)
    print("Status Code:", response.status_code)
    print("Response JSON:", response.text)
except Exception as e:
    print("Error:", e)
