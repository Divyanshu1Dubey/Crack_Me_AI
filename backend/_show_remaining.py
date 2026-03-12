import json
data = json.load(open('questions_fixture.json', 'r', encoding='utf-8'))
qs = [x for x in data if x.get('model') == 'questions.question']
missing = [q for q in qs if not (
    q['fields'].get('correct_answer', '').strip() in ('A', 'B', 'C', 'D')
    and len(q['fields'].get('explanation', '').strip()) > 10
    and len(q['fields'].get('concept_explanation', '').strip()) > 5
)]
print(f"Remaining: {len(missing)} questions\n")
for q in missing:
    f = q['fields']
    print(f"PK={q['pk']} | year={f.get('year','?')} | ans='{f.get('correct_answer','')}' | expl_len={len(f.get('explanation',''))} | concept_len={len(f.get('concept_explanation',''))}")
    print(f"  Q: {f.get('question_text','')[:140]}")
    opts = []
    for L in 'ABCD':
        v = f.get(f'option_{L.lower()}', '')
        if v.strip():
            opts.append(f"{L}) {v[:40]}")
    print(f"  {' | '.join(opts)}")
    print()
