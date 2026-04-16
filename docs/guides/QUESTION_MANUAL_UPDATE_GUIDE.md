# CrackCMS — Manual Question Update Guide

Complete guide to manually update questions, correct answers, explanations, and all metadata — via Django Admin Panel, Django Shell, API, or direct fixture editing.

---



## Table of Contents

1. [Method 1: Django Admin Panel (Easiest — GUI)](#method-1-django-admin-panel)
2. [Method 2: Django Shell (Quick Code)](#method-2-django-shell)
3. [Method 3: REST API (Programmatic)](#method-3-rest-api)
4. [Method 4: Fixture File (Bulk Edit)](#method-4-fixture-file)
5. [Method 5: Management Commands](#method-5-management-commands)
6. [Question Fields Reference](#question-fields-reference)
7. [Bulk Operations](#bulk-operations)
8. [Export & Backup](#export--backup)

---

## Method 1: Django Admin Panel

**Best for:** Editing individual questions via a web UI. No coding needed.

### Step 1: Start the Server

```bash
cd backend
python manage.py runserver
```

### Step 2: Open Admin Panel

Go to: **http://127.0.0.1:8000/admin/**

Login with your superuser credentials. If you don't have one:

```bash
python manage.py createsuperuser
```

### Step 3: Navigate to Questions

Click **Questions** → **Questions** in the sidebar.

### Step 4: Find the Question

Use these filters on the right sidebar:
- **Year** — Filter by PYQ year (2018, 2019, etc.)
- **Subject** — Filter by Medicine, Surgery, PSM, etc.
- **Difficulty** — easy / medium / hard
- **Is active** — show/hide deactivated questions

Or use the **Search bar** at the top to search by question text or explanation.

### Step 5: Edit a Question

Click on any question to open the edit form. You'll see these sections:

#### Section: Question
| Field | What to Edit |
|-------|-------------|
| **Question text** | The MCQ question itself |
| **Option A/B/C/D** | The four answer choices |
| **Correct answer** | Select A, B, C, or D |

#### Section: Classification
| Field | What to Edit |
|-------|-------------|
| **Year** | PYQ year (e.g., 2019) |
| **Subject** | Select from dropdown (Medicine, Surgery, etc.) |
| **Topic** | Select specific topic (e.g., Cardiology) |
| **Difficulty** | easy / medium / hard |
| **Concept tags** | JSON array: `["Cardiology", "Valvular Heart Disease"]` |
| **Exam source** | Usually "UPSC CMS" |

#### Section: Explanation
| Field | What to Edit |
|-------|-------------|
| **Explanation** | Why the correct answer is right (2-4 sentences) |
| **Concept explanation** | Overview of the underlying concept |
| **Mnemonic** | Memory trick (e.g., "MUDPILES for metabolic acidosis") |

#### Section: Textbook Reference
| Field | What to Edit |
|-------|-------------|
| **Book name** | e.g., "Harrison's Principles of Internal Medicine" |
| **Chapter** | e.g., "Valvular Heart Disease" |
| **Page number** | e.g., "pp. 1528-1532" |
| **Reference text** | Relevant excerpt from textbook |

### Step 6: Save

Click **Save** at the bottom.

### Admin Bulk Actions

Select multiple questions using checkboxes, then use the dropdown:
- **Activate selected questions** — Mark as active
- **Deactivate selected questions** — Mark as inactive (hides from students)
- **Check questions without explanations** — Quick audit

---

## Method 2: Django Shell

**Best for:** Quick fixes, updating multiple questions by criteria.

```bash
cd backend
python manage.py shell
```

### Update a Single Question by ID

```python
from questions.models import Question

q = Question.objects.get(id=42)
q.correct_answer = 'B'
q.explanation = 'Streptococcus pneumoniae is the most common cause of CAP. Ref: Harrison Ch.121'
q.concept_explanation = 'Community-acquired pneumonia (CAP) organisms differ from hospital-acquired.'
q.mnemonic = 'S. Pneumoniae = #1 CAP pathogen (think "Pneumonia = Pneumoniae")'
q.book_name = "Harrison's Principles of Internal Medicine"
q.chapter = 'Pneumonia'
q.page_number = 'pp. 908-920'
q.difficulty = 'medium'
q.concept_tags = ['Pulmonology', 'Infectious Disease', 'Community-Acquired Pneumonia']
q.concept_keywords = ['pneumonia', 'streptococcus', 'CAP', 'sputum culture']
q.learning_technique = 'Remember: CAP = S.pneumoniae > H.influenzae > Atypicals'
q.shortcut_tip = 'If question asks "most common" CAP cause — always S.pneumoniae unless immunocompromised'
q.save()
print(f'Updated question {q.id}: {q.question_text[:60]}')
```

### Change Correct Answer for Multiple Questions

```python
# Fix all questions with wrong answer where PK is known
fixes = {
    42: 'B',   # PK 42 should be B
    105: 'C',  # PK 105 should be C
    237: 'A',  # PK 237 should be A
}
for pk, ans in fixes.items():
    q = Question.objects.get(pk=pk)
    q.correct_answer = ans
    q.save()
    print(f'PK {pk}: answer → {ans}')
```

### Add Explanation to All Questions Missing One

```python
from questions.models import Question

no_expl = Question.objects.filter(explanation='')
print(f'{no_expl.count()} questions have no explanation')

# List them
for q in no_expl[:20]:
    print(f'  ID={q.id} Year={q.year} {q.question_text[:80]}')
```

### Bulk Update Difficulty

```python
# Set all PSM questions from 2019 to "medium"
from questions.models import Question
Question.objects.filter(year=2019, subject__code='PSM').update(difficulty='medium')
```

### Search Questions by Text

```python
from questions.models import Question

results = Question.objects.filter(question_text__icontains='carcinoid')
for q in results:
    print(f'ID={q.id} Year={q.year} Answer={q.correct_answer}')
    print(f'  {q.question_text[:100]}')
    print(f'  Explanation: {q.explanation[:80] if q.explanation else "MISSING"}')
    print()
```

### Update Topic Assignment

```python
from questions.models import Question, Topic, Subject

# Find or create topic
subj = Subject.objects.get(code='MED')
topic, _ = Topic.objects.get_or_create(subject=subj, name='Nephrology')

# Assign to questions mentioning kidney
kidney_qs = Question.objects.filter(
    question_text__icontains='kidney',
    subject=subj,
    topic__isnull=True
)
updated = kidney_qs.update(topic=topic)
print(f'Assigned {updated} questions to Nephrology')
```

---

## Method 3: REST API

**Best for:** Programmatic updates from scripts or external tools.

### Update a Question via API

```bash
# First get an admin JWT token
curl -X POST http://127.0.0.1:8000/api/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Response: {"access": "eyJ...", "refresh": "eyJ..."}

# Update question ID 42
curl -X PATCH http://127.0.0.1:8000/api/questions/42/ \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "correct_answer": "B",
    "explanation": "S. pneumoniae is the most common CAP pathogen.",
    "difficulty": "medium",
    "concept_tags": ["Pulmonology", "Infectious Disease"]
  }'
```

### Python Script for API Updates

```python
import requests

BASE = 'http://127.0.0.1:8000/api'

# Login
r = requests.post(f'{BASE}/accounts/login/', json={
    'username': 'admin', 'password': 'your_password'
})
token = r.json()['access']
headers = {'Authorization': f'Bearer {token}'}

# Update question
r = requests.patch(f'{BASE}/questions/42/', headers=headers, json={
    'correct_answer': 'B',
    'explanation': 'Updated explanation here',
    'mnemonic': 'New mnemonic',
    'book_name': "Harrison's",
    'chapter': 'Pneumonia',
})
print(r.status_code, r.json())
```

### Bulk Upload New Questions via API

```python
import requests

BASE = 'http://127.0.0.1:8000/api'
r = requests.post(f'{BASE}/accounts/login/', json={
    'username': 'admin', 'password': 'your_password'
})
token = r.json()['access']
headers = {'Authorization': f'Bearer {token}'}

questions = [
    {
        "question_text": "Which organism causes the most CAP?",
        "option_a": "Staphylococcus aureus",
        "option_b": "Streptococcus pneumoniae",
        "option_c": "Klebsiella pneumoniae",
        "option_d": "Pseudomonas aeruginosa",
        "correct_answer": "B",
        "year": 2024,
        "subject": 1,
        "difficulty": "easy",
        "explanation": "S. pneumoniae is the #1 cause of CAP.",
    }
]

r = requests.post(f'{BASE}/questions/upload/', headers=headers, json=questions)
print(r.status_code, r.json())
```

---

## Method 4: Fixture File

**Best for:** Bulk offline editing, version-controlled changes, full data backup.

The fixture file is at: `backend/questions_fixture.json`

### Structure of Each Question

```json
{
  "model": "questions.question",
  "pk": 42,
  "fields": {
    "question_text": "Which is the most common cause of CAP?",
    "option_a": "Staphylococcus aureus",
    "option_b": "Streptococcus pneumoniae",
    "option_c": "Klebsiella pneumoniae",
    "option_d": "Pseudomonas aeruginosa",
    "correct_answer": "B",
    "year": 2019,
    "subject": 1,
    "topic": 5,
    "difficulty": "medium",
    "concept_tags": ["Pulmonology", "Infectious Disease"],
    "explanation": "S. pneumoniae is the most common cause...",
    "concept_explanation": "CAP differs from HAP in organism spectrum...",
    "mnemonic": "Pneumonia = Pneumoniae (#1 cause)",
    "book_name": "Harrison's Principles of Internal Medicine",
    "chapter": "Pneumonia",
    "page_number": "pp. 908-920",
    "concept_keywords": ["pneumonia", "streptococcus", "CAP"],
    "learning_technique": "Compare CAP vs HAP organisms side-by-side",
    "shortcut_tip": "Most common CAP = S. pneumoniae (unless immunocompromised)",
    "ai_explanation": "**Answer: B**\nS. pneumoniae is #1...",
    "is_active": true
  }
}
```

### Edit the Fixture File

1. Open `backend/questions_fixture.json` in any text editor
2. Search for the question (Ctrl+F by text or PK)
3. Edit the fields you want to change
4. Save the file

### Load Updated Fixture into Database

```bash
cd backend
python manage.py loaddata questions_fixture.json
```

This will **update existing questions** (matched by PK) and add new ones.

### Export Current Database to Fixture

```bash
cd backend
python manage.py dumpdata questions.question --indent 2 -o questions_fixture.json
```

### Quick Fixture Edit Script

```python
"""Quick script to edit a question in the fixture file."""
import json

FIXTURE = 'backend/questions_fixture.json'

# Load
data = json.load(open(FIXTURE, 'r', encoding='utf-8'))

# Find and update
for item in data:
    if item.get('model') == 'questions.question' and item['pk'] == 42:
        item['fields']['correct_answer'] = 'B'
        item['fields']['explanation'] = 'Updated explanation'
        item['fields']['mnemonic'] = 'New mnemonic'
        print(f"Updated PK {item['pk']}")
        break

# Save
with open(FIXTURE, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Fixture saved. Run: python manage.py loaddata questions_fixture.json")
```

---

## Method 5: Management Commands

**Best for:** Repeatable operations via command line.

### Enrich All Questions (AI-powered)

```bash
# Using all cloud providers + Ollama
python enrich_all.py --batch 3

# Using only Ollama (local, no rate limits)
python enrich_turbo.py

# Enrich only questions missing answers
python enrich_all.py --answers-only

# Start from scratch
python enrich_all.py --reset
```

### Load fixture into database

```bash
python manage.py loaddata questions_fixture.json
```

### Validate all questions

```bash
python validate_questions.py
```

### Check database status

```bash
python check_db.py
```

---

## Question Fields Reference

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `question_text` | Text | The MCQ question | "Which organism causes..." |
| `option_a` | Text | Option A | "Staphylococcus aureus" |
| `option_b` | Text | Option B | "Streptococcus pneumoniae" |
| `option_c` | Text | Option C | "Klebsiella pneumoniae" |
| `option_d` | Text | Option D | "Pseudomonas aeruginosa" |
| `correct_answer` | A/B/C/D | The correct option letter | "B" |
| `year` | Integer | PYQ year | 2019 |
| `subject` | FK (ID) | Subject ID | 1 (Medicine) |
| `topic` | FK (ID) | Topic ID | 5 (Nephrology) |
| `difficulty` | Choice | easy / medium / hard | "medium" |
| `explanation` | Text | Why the answer is correct | "S. pneumoniae is..." |
| `concept_explanation` | Text | Underlying concept overview | "CAP differs from..." |
| `mnemonic` | Text | Memory aid | "MUDPILES" |
| `concept_tags` | JSON array | Topic tags | `["Cardiology"]` |
| `concept_keywords` | JSON array | Search keywords | `["pneumonia"]` |
| `book_name` | String | Textbook reference | "Harrison's" |
| `chapter` | String | Chapter name | "Pneumonia" |
| `page_number` | String | Page range | "pp. 908-920" |
| `reference_text` | Text | Textbook excerpt | "The pneumococcus..." |
| `learning_technique` | Text | Study tip | "Compare CAP vs HAP" |
| `shortcut_tip` | Text | Exam trick | "If 'most common'→..." |
| `ai_explanation` | Text | Combined AI explanation | Auto-generated |
| `is_active` | Boolean | Show to students | true |
| `times_asked` | Integer | Repeat count | 3 |

---

## Bulk Operations

### Fix Multiple Wrong Answers (Shell)

```python
python manage.py shell

from questions.models import Question
fixes = {
    42: {'correct_answer': 'B', 'explanation': 'Because...'},
    105: {'correct_answer': 'C', 'explanation': 'Reason...'},
    237: {'correct_answer': 'A'},
}
for pk, updates in fixes.items():
    Question.objects.filter(pk=pk).update(**updates)
    print(f'Fixed PK {pk}')
```

### Add Explanations to All Empty Questions (via Ollama)

```python
"""Use local Ollama to add explanations to questions missing them."""
import requests, json
from questions.models import Question

OLLAMA_URL = 'http://localhost:11434/api/chat'

for q in Question.objects.filter(explanation='')[:50]:
    prompt = f"""Question: {q.question_text}
A) {q.option_a}  B) {q.option_b}  C) {q.option_c}  D) {q.option_d}
Correct answer: {q.correct_answer}

Explain why {q.correct_answer} is correct in 2-3 sentences."""

    r = requests.post(OLLAMA_URL, json={
        'model': 'llama3.2:3b',
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
    }, timeout=120)
    
    if r.ok:
        q.explanation = r.json()['message']['content']
        q.save()
        print(f'✅ PK {q.id} done')
```

### Reassign All Questions by Subject Keyword

```python
from questions.models import Question, Subject

psm = Subject.objects.get(code='PSM')
# Find misclassified PSM questions
psm_keywords = ['immunization', 'vaccination', 'epidemiology', 'sanitation', 'demography']
for kw in psm_keywords:
    moved = Question.objects.filter(
        question_text__icontains=kw
    ).exclude(subject=psm).update(subject=psm)
    if moved:
        print(f'Moved {moved} questions with "{kw}" to PSM')
```

---

## Export & Backup

### Export full fixture (backup)

```bash
cd backend
python manage.py dumpdata questions --indent 2 -o questions_backup_$(date +%Y%m%d).json
```

### Export to CSV for spreadsheet editing

```python
python manage.py shell

import csv
from questions.models import Question

with open('questions_export.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Year', 'Subject', 'Question', 'A', 'B', 'C', 'D',
                     'Answer', 'Explanation', 'Difficulty', 'Book', 'Chapter'])
    for q in Question.objects.select_related('subject').all():
        writer.writerow([
            q.id, q.year, q.subject.name, q.question_text,
            q.option_a, q.option_b, q.option_c, q.option_d,
            q.correct_answer, q.explanation, q.difficulty,
            q.book_name, q.chapter
        ])
print('Exported to questions_export.csv')
```

### Import from CSV

```python
import csv
from questions.models import Question

with open('questions_fixes.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        pk = int(row['ID'])
        q = Question.objects.get(pk=pk)
        if row.get('Answer'):
            q.correct_answer = row['Answer']
        if row.get('Explanation'):
            q.explanation = row['Explanation']
        q.save()
        print(f'Updated PK {pk}')
```

---

## Quick Reference Commands

```bash
# Start admin panel
cd backend && python manage.py runserver

# Open Django shell
python manage.py shell

# Load fixture
python manage.py loaddata questions_fixture.json

# Export fixture
python manage.py dumpdata questions.question --indent 2 -o questions_fixture.json

# Run enrichment (all providers)
python enrich_all.py --batch 3

# Run enrichment (Ollama only, no rate limits)
python enrich_turbo.py

# Test all API keys
python test_api_keys.py

# Create admin user
python manage.py createsuperuser

# Check question stats
python check_db.py
```
