"""Clean question text artifacts from fixture: trailing *, (a)(b)(c), etc."""
import json
import re

with open('questions_fixture.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

cleaned = 0
for item in data:
    if item['model'] != 'questions.question':
        continue
    fields = item['fields']
    qt = fields.get('question_text', '')
    orig = qt

    # Remove trailing asterisks (possibly with whitespace before)
    qt = re.sub(r'\s*\*+\s*$', '', qt)

    # Remove (a) (b) (c) or (a) (b) (c) (d) anywhere near the end
    qt = re.sub(r'\s*\(a\)\s*\(b\)\s*\(c\)(?:\s*\(d\))?\s*$', '', qt)

    # Remove standalone * Codes: pattern artifacts (match sets)
    # These appear as "* Codes:" at end — clean them
    qt = re.sub(r'\s*\*\s*Codes:\s*$', '', qt)

    # Clean "Select the correct answer using the code given below. (a) (b) (c) (d)" patterns
    qt = re.sub(r'\s*Select the correct answer using the code[s]? given below\.?\s*\(a\)\s*\(b\)\s*\(c\)(?:\s*\(d\))?\s*$', '', qt, flags=re.IGNORECASE)

    # Remove trailing * that might be after a colon or period
    qt = re.sub(r'\s*\*\s*$', '', qt)

    # Clean options
    for opt_key in ['option_a', 'option_b', 'option_c', 'option_d']:
        opt = fields.get(opt_key, '')
        if opt:
            fields[opt_key] = re.sub(r'\s*\*+\s*$', '', opt).strip()

    if qt != orig:
        cleaned += 1
    fields['question_text'] = qt.strip()

with open('questions_fixture.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'Cleaned {cleaned} question texts')

# Verify
with open('questions_fixture.json', 'r', encoding='utf-8') as f:
    data2 = json.load(f)
questions = [d for d in data2 if d['model'] == 'questions.question']
still_star = sum(1 for q in questions if q['fields']['question_text'].rstrip().endswith('*'))
still_abc = sum(1 for q in questions if re.search(r'\(a\)\s*\(b\)\s*\(c\)', q['fields']['question_text']))
print(f'Remaining with trailing *: {still_star}')
print(f'Remaining with (a)(b)(c): {still_abc}')

# Show a few remaining ones for inspection
if still_star > 0:
    print('\nSample remaining * questions:')
    count = 0
    for q in questions:
        qt = q['fields']['question_text']
        if qt.rstrip().endswith('*'):
            print(f"  PK {q['pk']}: ...{qt[-100:]}")
            count += 1
            if count >= 5:
                break
