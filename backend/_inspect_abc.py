import json, re
with open('questions_fixture.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
questions = [d for d in data if d['model'] == 'questions.question']
count = 0
for q in questions:
    qt = q['fields']['question_text']
    if re.search(r'\(a\)\s*\(b\)\s*\(c\)', qt):
        count += 1
        if count <= 5:
            print(f"PK {q['pk']}: ...{qt[-120:]}")
            print()
print(f"Total remaining: {count}")
