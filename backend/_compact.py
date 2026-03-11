import json, os

data = json.load(open('questions_fixture.json', 'r', encoding='utf-8'))
with open('questions_fixture.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize('questions_fixture.json')
print(f"Compacted to {size // 1024} KB")

qs = [x for x in data if x.get('model') == 'questions.question']
p = json.load(open('enrich_progress.json'))
total = len(qs)
done = len(p)
print(f"Progress: {done}/{total}")
print(f"Remaining: {total - done}")

has_ans = sum(1 for q in qs if q['fields'].get('correct_answer', '').strip() in ('A','B','C','D'))
has_exp = sum(1 for q in qs if len(q['fields'].get('explanation', '').strip()) > 10)
print(f"Has answer: {has_ans}/{total}")
print(f"Has explanation: {has_exp}/{total}")
