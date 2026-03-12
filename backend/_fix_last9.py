"""Fix the last 9 unenriched questions using Ollama only."""
import json, requests, re, time

FIXTURE = 'questions_fixture.json'
OLLAMA_URL = 'http://localhost:11434/api/chat'
MODEL = 'llama3.2:3b'

SYSTEM = """You are a UPSC CMS medical exam expert. Return ONLY a valid JSON object (not array).
Format: {"correct_answer":"A/B/C/D","explanation":"2-3 sentences why correct","concept_explanation":"1-2 sentence concept overview","mnemonic":"memory aid or empty string","concept_tags":["tag1","tag2"],"concept_keywords":["kw1","kw2"],"book_name":"textbook name","chapter":"chapter name","difficulty":"easy/medium/hard","learning_technique":"study tip","shortcut_tip":"exam trick or empty string"}
Books: PSM=Park's, Pharma=KDT, Path=Robbins, Med=Harrison's, Surg=Bailey&Love, Peds=Ghai/Nelson, OBG=Dutta, Anat=BDChaurasia.
If the question text seems incomplete, use your medical knowledge to determine the most likely correct answer based on the options given."""

def call_ollama(prompt):
    for attempt in range(3):
        try:
            r = requests.post(OLLAMA_URL, json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': prompt}
                ],
                'stream': False,
                'options': {'temperature': 0.1, 'num_predict': 1024}
            }, timeout=180)
            r.raise_for_status()
            return r.json()['message']['content'].strip()
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return None

def parse_json(text):
    if not text:
        return None
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text).strip()
    try:
        return json.loads(text)
    except:
        pass
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return None

# Load fixture
data = json.load(open(FIXTURE, 'r', encoding='utf-8'))
qs = [x for x in data if x.get('model') == 'questions.question']

missing = [q for q in qs if not (
    q['fields'].get('correct_answer', '').strip() in ('A', 'B', 'C', 'D')
    and len(q['fields'].get('explanation', '').strip()) > 10
    and len(q['fields'].get('concept_explanation', '').strip()) > 5
)]

print(f"Fixing {len(missing)} remaining questions with Ollama ({MODEL})\n")

fixed = 0
for q in missing:
    f = q['fields']
    opts = " | ".join(f"{L}) {f.get(f'option_{L.lower()}', '')}" for L in 'ABCD' if f.get(f'option_{L.lower()}', '').strip())
    
    prompt = f"""Answer this UPSC CMS MCQ. Return ONLY a JSON object.

Question (Year {f.get('year', '?')}): {f.get('question_text', '')}
Options: {opts}

If the question seems incomplete, use your best medical judgment based on the options to determine the correct answer."""

    print(f"PK={q['pk']}:", f.get('question_text', '')[:80])
    raw = call_ollama(prompt)
    result = parse_json(raw)
    
    if result:
        ans = result.get('correct_answer', '').strip().upper()
        if ans in ('A', 'B', 'C', 'D'):
            f['correct_answer'] = ans
        elif f.get('correct_answer', '').strip() not in ('A', 'B', 'C', 'D'):
            # If still no answer, try to extract from raw text
            for letter in ['A', 'B', 'C', 'D']:
                if f'correct answer is {letter}' in (raw or '').upper() or f'answer: {letter}' in (raw or '').upper():
                    f['correct_answer'] = letter
                    break
        
        for k in ['explanation', 'concept_explanation', 'mnemonic', 'book_name', 'chapter',
                   'learning_technique', 'shortcut_tip']:
            v = result.get(k, '')
            if isinstance(v, str) and v.strip() and len(v.strip()) > 2:
                if not f.get(k, '').strip() or len(f.get(k, '').strip()) < 5:
                    f[k] = v.strip()

        if result.get('difficulty', '').lower() in ('easy', 'medium', 'hard'):
            if not f.get('difficulty') or f.get('difficulty') == 'medium':
                f['difficulty'] = result['difficulty'].lower()

        for k in ['concept_tags', 'concept_keywords']:
            v = result.get(k, [])
            if isinstance(v, list) and v and not f.get(k):
                f[k] = [str(x).strip() for x in v if str(x).strip()]

        # Build ai_explanation
        parts = []
        if f.get('explanation'):
            parts.append(f"**Answer: {f.get('correct_answer', '?')}**\n{f['explanation']}")
        if f.get('concept_explanation'):
            parts.append(f"**Concept:** {f['concept_explanation']}")
        if f.get('mnemonic'):
            parts.append(f"**Mnemonic:** {f['mnemonic']}")
        if parts:
            f['ai_explanation'] = "\n\n".join(parts)

        fixed += 1
        print(f"  ✅ ans={f.get('correct_answer','')} expl_len={len(f.get('explanation',''))}")
    else:
        print(f"  ❌ Failed to parse response")
    
    print()

# Save
with open(FIXTURE, 'w', encoding='utf-8') as fp:
    json.dump(data, fp, indent=2, ensure_ascii=False)

print(f"\nDone! Fixed {fixed}/{len(missing)} questions. Saved to {FIXTURE}")
print("Run: python manage.py loaddata questions_fixture.json")
