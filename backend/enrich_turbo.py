"""
LOCAL Batch Question Enrichment — Uses Ollama (llama3.2:3b) locally.
Zero API cost, no rate limits, unlimited processing.
Groq used as fallback only. Resume-safe. Auto-saves every 5 batches.

Usage: python enrich_turbo.py
"""
import json, os, time, re, logging, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

FIXTURE = Path(__file__).parent / 'questions_fixture.json'
PROGRESS = Path(__file__).parent / 'enrich_progress.json'
GROQ_KEY = os.getenv('GROQ_API_KEY', '')
OLLAMA_URL = 'http://localhost:11434/api/chat'
OLLAMA_MODEL = 'llama3.2:3b'

SYSTEM = """You are a UPSC CMS medical exam expert. Return ONLY a single JSON object (no markdown, no extra text).
Format:
{"correct_answer":"A/B/C/D","explanation":"2-3 sentences","concept_explanation":"1 sentence","mnemonic":"memory aid or empty string","concept_tags":["tag1","tag2"],"concept_keywords":["kw1","kw2"],"book_name":"textbook","chapter":"section","difficulty":"easy/medium/hard","learning_technique":"study tip","shortcut_tip":"exam trick or empty string"}
Books: PSM=Park's, Pharma=KDT, Path=Robbins, Med=Harrison's, Surg=Bailey&Love, Peds=Ghai, OBG=Dutta, Anat=BDChaurasia."""


def build_prompt(batch):
    parts = []
    for i, q in enumerate(batch):
        f = q['fields']
        opts = " | ".join(f"{L}) {f.get(f'option_{L.lower()}','')}" for L in 'ABCD' if f.get(f'option_{L.lower()}','').strip())
        parts.append(f"Q{i+1}[{q['pk']},{f.get('year','')}]: {f.get('question_text','')}\n{opts}")
    return "Answer ALL:\n\n" + "\n\n".join(parts)


def call_ollama(prompt, attempt=0):
    """Call local Ollama — no rate limits, no cost."""
    try:
        r = requests.post(OLLAMA_URL, json={
            'model': OLLAMA_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': prompt}
            ],
            'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 3072}
        }, timeout=180)
        r.raise_for_status()
        return r.json()['message']['content'].strip()
    except Exception as e:
        if attempt < 2:
            log.warning(f"  Ollama retry {attempt+1}: {str(e)[:80]}")
            time.sleep(3)
            return call_ollama(prompt, attempt + 1)
        log.error(f"Ollama fail: {str(e)[:120]}")
        return None


def call_groq(prompt, attempt=0):
    """Fallback to Groq cloud API."""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_KEY)
        r = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role':'system','content':SYSTEM}, {'role':'user','content':prompt}],
            max_tokens=4096, temperature=0.1,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        if '429' in str(e) and attempt < 6:
            wait = min(60, 10 * (attempt + 1))
            log.warning(f"  Groq 429 — waiting {wait}s (attempt {attempt+1}/6)")
            time.sleep(wait)
            return call_groq(prompt, attempt + 1)
        log.error(f"Groq fail: {str(e)[:100]}")
        return None


def call_llm(prompt):
    """Use Ollama only — no cloud APIs, no token cost."""
    result = call_ollama(prompt)
    if result:
        return result, 'ollama'
    return None, None


def parse_response(text, n):
    if not text:
        return None
    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text).strip()
    # 1. Try direct JSON parse
    try:
        r = json.loads(text)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass
    # 2. Try finding a JSON array in text
    m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try:
            r = json.loads(m.group())
            return r if isinstance(r, list) else None
        except json.JSONDecodeError:
            pass
    # 3. Try JSONL format (newline-separated objects) — common from Ollama
    objs = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('{'):
            try:
                o = json.loads(line)
                if 'correct_answer' in o:
                    objs.append(o)
            except json.JSONDecodeError:
                pass
    if objs:
        return objs
    # 4. Try extracting individual JSON objects via regex
    for m2 in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
        try:
            o = json.loads(m2.group())
            if 'correct_answer' in o:
                objs.append(o)
        except json.JSONDecodeError:
            continue
    return objs if objs else None


def apply(q, e):
    f = q['fields']
    ans = e.get('correct_answer','').strip().upper()
    if ans in ('A','B','C','D'):
        f['correct_answer'] = ans
    for k in ['explanation','concept_explanation','mnemonic','book_name','chapter','learning_technique','shortcut_tip']:
        v = e.get(k,'')
        if isinstance(v, str) and v.strip():
            f[k] = v.strip()
    if e.get('difficulty','').lower() in ('easy','medium','hard'):
        f['difficulty'] = e['difficulty'].lower()
    for k in ['concept_tags','concept_keywords']:
        v = e.get(k,[])
        if isinstance(v, list) and v:
            f[k] = [str(x).strip() for x in v if str(x).strip()]
    # Build combined ai_explanation
    parts = []
    if f.get('explanation'):
        parts.append(f"**Answer: {f.get('correct_answer','?')}**\n{f['explanation']}")
    if f.get('concept_explanation'):
        parts.append(f"**Concept:** {f['concept_explanation']}")
    if f.get('mnemonic'):
        parts.append(f"**Mnemonic:** {f['mnemonic']}")
    if f.get('shortcut_tip'):
        parts.append(f"**Exam Tip:** {f['shortcut_tip']}")
    if parts:
        f['ai_explanation'] = "\n\n".join(parts)


def is_done(q):
    f = q['fields']
    return (f.get('correct_answer','').strip() in ('A','B','C','D')
            and len(f.get('explanation','').strip()) > 10
            and len(f.get('concept_explanation','').strip()) > 5)


def main():
    log.info("=" * 60)
    log.info("LOCAL ENRICHMENT — Ollama + Groq fallback")
    log.info("=" * 60)

    # Verify Ollama is running
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        models = [m['name'] for m in r.json().get('models', [])]
        log.info(f"Ollama OK — models: {models}")
    except Exception:
        log.error("Ollama not running! Start with: ollama serve")
        return

    log.info("Loading fixture...")
    data = json.load(open(FIXTURE, 'r', encoding='utf-8'))
    questions = [x for x in data if x.get('model') == 'questions.question']
    log.info(f"Total questions: {len(questions)}")

    # Load progress
    processed_pks = set()
    if PROGRESS.exists():
        try:
            processed_pks = set(json.loads(PROGRESS.read_text(encoding='utf-8')))
        except Exception:
            pass
    log.info(f"Already done: {len(processed_pks)}")

    # Filter
    todo = [q for q in questions if q['pk'] not in processed_pks and not is_done(q)]
    log.info(f"To enrich: {len(todo)}")
    if not todo:
        log.info("All done!")
        return

    BATCH_SIZE = 1  # 1 per batch — most reliable for 3B model
    batches = [todo[i:i+BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    total = len(batches)
    log.info(f"Batches: {total} ({BATCH_SIZE} questions each)")
    log.info(f"No rate limits — running full speed!\n")

    enriched = 0
    failed = 0
    ollama_count = 0
    groq_count = 0
    t0 = time.time()

    for idx, batch in enumerate(batches):
        bn = idx + 1
        pks = [q['pk'] for q in batch]
        prompt = build_prompt(batch)
        raw, provider = call_llm(prompt)
        results = parse_response(raw, len(batch))

        if results:
            for i, q in enumerate(batch):
                if i < len(results):
                    apply(q, results[i])
                    processed_pks.add(q['pk'])
                    enriched += 1
                else:
                    failed += 1
            if provider == 'ollama':
                ollama_count += len(batch)
            else:
                groq_count += len(batch)
        else:
            failed += len(batch)
            log.error(f"  Batch {bn} FAILED pks={pks}")

        # Save every 5 batches or at the end
        if bn % 5 == 0 or bn == total:
            PROGRESS.write_text(json.dumps(sorted(processed_pks)), encoding='utf-8')
            with open(FIXTURE, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, separators=(',',':'))

        # Log progress every 5 batches
        if bn % 5 == 0 or bn == total:
            elapsed = time.time() - t0
            rate = enriched / max(elapsed, 1) * 60
            remaining = (len(todo) - enriched) / max(rate, 0.1)
            log.info(f"[{bn}/{total}] {enriched}/{len(todo)} ({enriched*100//max(len(todo),1)}%) | "
                     f"fail={failed} | {rate:.0f} q/min | ~{remaining:.0f}min left | "
                     f"ollama={ollama_count} groq={groq_count}")

        # No rate limit needed for local Ollama
        time.sleep(0.5)

    # Final save
    log.info("\nFinal save...")
    PROGRESS.write_text(json.dumps(sorted(processed_pks)), encoding='utf-8')
    with open(FIXTURE, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(',',':'))

    elapsed = time.time() - t0
    log.info(f"{'='*60}")
    log.info(f"DONE! Enriched: {enriched} | Failed: {failed} | Time: {elapsed/60:.1f}min")
    log.info(f"Ollama: {ollama_count} | Groq: {groq_count}")
    log.info(f"Total processed: {len(processed_pks)}")
    log.info(f"Run: python manage.py loaddata questions_fixture.json")


if __name__ == '__main__':
    main()
