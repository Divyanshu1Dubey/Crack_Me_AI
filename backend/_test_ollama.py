"""Quick test of Ollama with 2-question batch."""
import requests, json, time, re

SYSTEM = """You are a UPSC CMS medical exam expert. You MUST return ONLY a valid JSON array wrapped in [ ]. No other text.
For each question return one object in this exact format:
{"correct_answer":"A/B/C/D","explanation":"2-3 sentences","concept_explanation":"1 sentence","mnemonic":"memory aid or empty","concept_tags":["tag1","tag2"],"concept_keywords":["kw1","kw2"],"book_name":"textbook","chapter":"section","difficulty":"easy/medium/hard","learning_technique":"study tip","shortcut_tip":"exam trick or empty"}
IMPORTANT: Wrap ALL objects in a JSON array like [{...},{...}]. Books: PSM=Park's, Pharma=KDT, Path=Robbins, Med=Harrison's, Surg=Bailey&Love, Anat=BDChaurasia."""

prompt = """Answer ALL:

Q1[100,2020]: Which drug is used for treatment of organophosphorus poisoning?
A) Atropine | B) Pralidoxime | C) Both A and B | D) None

Q2[200,2019]: The most common cause of iron deficiency anemia in India is?
A) Hookworm | B) Malaria | C) Nutritional | D) Bleeding"""

t0 = time.time()
r = requests.post('http://localhost:11434/api/chat', json={
    'model': 'llama3.2:3b',
    'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
    'stream': False,
    'options': {'temperature': 0.1, 'num_predict': 3072}
}, timeout=180)
elapsed = time.time() - t0
raw = r.json()['message']['content']
print(f"Time: {elapsed:.1f}s")
print(f"Raw ({len(raw)} chars):")
print(raw[:2000])
print("---")

# Parse
text = re.sub(r'^```(?:json)?\s*', '', raw.strip())
text = re.sub(r'\s*```$', '', text).strip()
try:
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        parsed = [parsed]
    print(f"PARSE OK: {len(parsed)} items")
    for p in parsed:
        print(f"  answer={p.get('correct_answer')}, keys={list(p.keys())}")
except Exception as e:
    print(f"PARSE FAIL: {e}")
    # Try JSONL (newline-separated objects)
    objs = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('{'):
            try:
                o = json.loads(line)
                if 'correct_answer' in o:
                    objs.append(o)
            except:
                pass
    if objs:
        print(f"JSONL PARSE OK: {len(objs)} items")
        for p in objs:
            print(f"  answer={p.get('correct_answer')}, keys={list(p.keys())}")
    else:
        m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try:
            parsed = json.loads(m.group())
            print(f"REGEX PARSE OK: {len(parsed)} items")
            for p in parsed:
                print(f"  answer={p.get('correct_answer')}, keys={list(p.keys())}")
        except:
            print("REGEX PARSE ALSO FAILED")
    else:
        # Try individual objects
        objs = []
        for m2 in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                o = json.loads(m2.group())
                if 'correct_answer' in o:
                    objs.append(o)
            except:
                continue
        if objs:
            print(f"OBJECT PARSE: {len(objs)} items")
            for p in objs:
                print(f"  answer={p.get('correct_answer')}, keys={list(p.keys())}")
        else:
            print("ALL PARSING FAILED")
            print("First 500 chars of cleaned text:")
            print(text[:500])
