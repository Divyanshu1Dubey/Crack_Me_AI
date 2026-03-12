"""
MASTER Question Enrichment — uses ALL cloud AI providers + Ollama fallback.
Round-robin load balancing across: Groq, Cerebras, Gemini, GitHub Models, OpenRouter(x2), Cohere, HuggingFace, AIML, Mistral, DeepSeek(last/paid), Ollama.
Resume-safe, rate-limit aware, auto-saves progress.

Usage:
    python enrich_all.py                    # Enrich all missing
    python enrich_all.py --limit 50         # Only process 50
    python enrich_all.py --reset            # Reset progress, start fresh
    python enrich_all.py --answers-only     # Only fix missing correct_answer
"""
import json, os, sys, time, re, argparse, logging, threading, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

FIXTURE = Path(__file__).parent / 'questions_fixture.json'
PROGRESS = Path(__file__).parent / 'enrich_progress.json'
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434/api/chat')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:3b')

# ─── Provider configurations ───
PROVIDERS = []
_counter = 0
_lock = threading.Lock()

SYSTEM = """You are a UPSC CMS (Combined Medical Services) exam expert with deep knowledge of medical sciences.
You will be given medical MCQs from UPSC CMS Previous Year Papers.

For EACH question, provide a JSON object with these fields:
- "correct_answer": The correct option letter (A, B, C, or D). Use your medical expertise.
- "explanation": Clear 2-4 sentence explanation of WHY the correct answer is right. Include the key medical fact.
- "concept_explanation": Brief concept overview (1-2 sentences) about the underlying medical topic.
- "mnemonic": A well-known medical mnemonic or memory aid. Prefer established mnemonics over invented ones. Use "" if not applicable.
- "concept_tags": Array of 2-4 relevant medical topic tags (e.g., ["Cardiology", "Valvular Heart Disease"]).
- "concept_keywords": Array of 3-6 important keywords from the question/answer.
- "book_name": Most relevant standard textbook (Harrison's, Park's, Bailey & Love, Ghai, etc.)
- "chapter": Relevant chapter/section name.
- "page_number": Approximate page number range in latest edition (e.g., "pp. 234-236"). Use "" if unknown.
- "difficulty": "easy", "medium", or "hard" based on UPSC CMS standards.
- "learning_technique": One practical study tip for this topic (1 sentence).
- "shortcut_tip": A quick exam trick or elimination strategy. Use "" if not applicable.

CRITICAL RULES:
1. Answer MUST be A, B, C, or D only.
2. Use standard medical textbook knowledge.
3. If unsure, pick the most commonly accepted answer in Indian medical PG exams.
4. Keep explanations concise but accurate.
5. Textbook preference: PSM=Park's, Pharma=KDT, Path=Robbins, Med=Harrison's, Surg=Bailey&Love, Peds=Ghai/Nelson, OBG=Dutta.
6. Return ONLY a JSON array [{...},{...}]. No markdown, no extra text."""


def init_providers():
    """Initialize all available AI providers."""
    global PROVIDERS
    providers = []

    # 1. Groq (Llama 3.3 70B) — 30 RPM, 14400 RPD
    groq_key = os.getenv('GROQ_API_KEY', '')
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            providers.append({
                'name': 'Groq', 'client': client, 'type': 'groq',
                'rpm': 25, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ Groq ready")
        except Exception as e:
            log.warning(f"Groq init failed: {e}")

    # 2. Cerebras (Llama 3.1 8B) — 30 RPM
    cerebras_key = os.getenv('CEREBRAS_API_KEY', '')
    if cerebras_key:
        try:
            from cerebras.cloud.sdk import Cerebras
            client = Cerebras(api_key=cerebras_key)
            providers.append({
                'name': 'Cerebras', 'client': client, 'type': 'cerebras',
                'rpm': 25, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ Cerebras ready")
        except Exception as e:
            log.warning(f"Cerebras init failed: {e}")

    # 3. Gemini (Flash 2.0) — 15 RPM, 1500 RPD
    gemini_key = os.getenv('GEMINI_API_KEY', '')
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            providers.append({
                'name': 'Gemini', 'client': client, 'type': 'gemini',
                'rpm': 12, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ Gemini ready")
        except Exception as e:
            log.warning(f"Gemini init failed: {e}")

    # 4. GitHub Models (GPT-4o-mini) — 150 RPM, 15K RPD
    github_token = os.getenv('GITHUB_TOKEN', '')
    if github_token:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=github_token, base_url='https://models.inference.ai.azure.com')
            providers.append({
                'name': 'GitHub', 'client': client, 'type': 'openai',
                'model': 'gpt-4o-mini', 'rpm': 100, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ GitHub Models ready")
        except Exception as e:
            log.warning(f"GitHub Models init failed: {e}")

    # 5. OpenRouter (free models) — 20 RPM
    openrouter_key = os.getenv('OPENROUTER_API_KEY', '')
    if openrouter_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openrouter_key, base_url='https://openrouter.ai/api/v1')
            providers.append({
                'name': 'OpenRouter', 'client': client, 'type': 'openai',
                'model': 'meta-llama/llama-3.3-70b-instruct:free', 'rpm': 15, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ OpenRouter ready")
        except Exception as e:
            log.warning(f"OpenRouter init failed: {e}")

    # 5b. OpenRouter Key 2 (second free-tier key for more RPM)
    openrouter_key2 = os.getenv('OPENROUTER_API_KEY2', '')
    if openrouter_key2:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openrouter_key2, base_url='https://openrouter.ai/api/v1')
            providers.append({
                'name': 'OpenRouter2', 'client': client, 'type': 'openai',
                'model': 'meta-llama/llama-3.3-70b-instruct:free', 'rpm': 15, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ OpenRouter2 ready")
        except Exception as e:
            log.warning(f"OpenRouter2 init failed: {e}")

    # 6. Cohere (Command-A) — 20 RPM, 1000/month
    cohere_key = os.getenv('COHERE_API_KEY', '')
    if cohere_key:
        try:
            import cohere
            client = cohere.ClientV2(api_key=cohere_key)
            providers.append({
                'name': 'Cohere', 'client': client, 'type': 'cohere',
                'rpm': 15, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ Cohere ready")
        except Exception as e:
            log.warning(f"Cohere init failed: {e}")

    # 7. HuggingFace Inference API (free tier)
    hf_key = os.getenv('HUGGINGFACE_API_KEY', '')
    if hf_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=hf_key, base_url='https://router.huggingface.co/novita/v3/openai')
            providers.append({
                'name': 'HuggingFace', 'client': client, 'type': 'openai',
                'model': 'meta-llama/llama-3.3-70b-instruct', 'rpm': 10, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ HuggingFace ready")
        except Exception as e:
            log.warning(f"HuggingFace init failed: {e}")

    # 8. AIML API (free tier)
    aiml_key = os.getenv('AIML_API_KEY', '')
    if aiml_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=aiml_key, base_url='https://api.aimlapi.com/v1')
            providers.append({
                'name': 'AIML', 'client': client, 'type': 'openai',
                'model': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'rpm': 10, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ AIML ready")
        except Exception as e:
            log.warning(f"AIML init failed: {e}")

    # 10. Mistral (free tier)
    mistral_key = os.getenv('MISTRAL_API_KEY', '')
    if mistral_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=mistral_key, base_url='https://api.mistral.ai/v1')
            providers.append({
                'name': 'Mistral', 'client': client, 'type': 'openai',
                'model': 'mistral-small-latest', 'rpm': 25, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("✅ Mistral ready")
        except Exception as e:
            log.warning(f"Mistral init failed: {e}")

    # 11. DeepSeek (PAID — last priority, needs balance top-up)
    deepseek_key = os.getenv('DEEPSEEK_API_KEY', '')
    if deepseek_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=deepseek_key, base_url='https://api.deepseek.com')
            providers.append({
                'name': 'DeepSeek', 'client': client, 'type': 'openai',
                'model': 'deepseek-chat', 'rpm': 25, 'last_call': 0, 'calls': 0, 'errors': 0
            })
            log.info("⚠️ DeepSeek ready (PAID — last priority)")
        except Exception as e:
            log.warning(f"DeepSeek init failed: {e}")

    PROVIDERS = providers
    log.info(f"🚀 {len(PROVIDERS)} cloud providers ready")
    return len(PROVIDERS)


def call_provider(provider, prompt):
    """Call a specific provider and return the response text."""
    ptype = provider['type']
    try:
        # Rate limiting: wait if needed
        elapsed = time.time() - provider['last_call']
        min_interval = 60.0 / provider['rpm']
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        provider['last_call'] = time.time()

        if ptype == 'groq':
            r = provider['client'].chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
                max_tokens=4096, temperature=0.1, timeout=30.0
            )
            return r.choices[0].message.content.strip()

        elif ptype == 'cerebras':
            r = provider['client'].chat.completions.create(
                model='llama3.1-8b',
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
                max_completion_tokens=4096, temperature=0.1,
            )
            return r.choices[0].message.content.strip()

        elif ptype == 'gemini':
            from google.genai import types
            full_prompt = f"{SYSTEM}\n\n{prompt}"
            r = provider['client'].models.generate_content(
                model='gemini-2.0-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=4096),
            )
            return r.text.strip() if r and r.text else None

        elif ptype == 'cohere':
            r = provider['client'].chat(
                model='command-a-03-2025',
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
                max_tokens=4096, temperature=0.1,
            )
            return r.message.content[0].text.strip()

        elif ptype == 'openai':
            model = provider.get('model', 'gpt-4o-mini')
            r = provider['client'].chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
                max_tokens=4096, temperature=0.1, timeout=30.0
            )
            return r.choices[0].message.content.strip()

    except Exception as e:
        err = str(e)
        provider['errors'] += 1
        if '429' in err or 'RESOURCE_EXHAUSTED' in err or 'rate' in err.lower():
            log.warning(f"  {provider['name']} rate limited")
        elif '401' in err or 'invalid' in err.lower() or '403' in err:
            log.warning(f"  {provider['name']} auth failed — disabling")
            provider['disabled'] = True
        elif '402' in err or 'insufficient' in err.lower():
            log.warning(f"  {provider['name']} balance depleted — disabling")
            provider['disabled'] = True
        else:
            log.warning(f"  {provider['name']} error: {str(e)[:100]}")
    return None


def call_ollama(prompt, attempt=0):
    """Call local Ollama as final fallback."""
    try:
        r = requests.post(OLLAMA_URL, json={
            'model': OLLAMA_MODEL,
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}],
            'stream': False, 'options': {'temperature': 0.1, 'num_predict': 4096}
        }, timeout=180)
        r.raise_for_status()
        return r.json()['message']['content'].strip()
    except Exception as e:
        if attempt < 2:
            time.sleep(3)
            return call_ollama(prompt, attempt + 1)
        log.warning(f"  Ollama failed: {str(e)[:80]}")
        return None


def call_ai(prompt):
    """Round-robin across all providers with fallback to Ollama."""
    global _counter
    active = [p for p in PROVIDERS if not p.get('disabled')]
    if not active:
        # Try Ollama as last resort
        result = call_ollama(prompt)
        return result, 'ollama' if result else None

    # Round-robin: pick next provider
    with _lock:
        start_idx = _counter % len(active)
        _counter += 1

    # Try each provider starting from the round-robin position
    for i in range(len(active)):
        idx = (start_idx + i) % len(active)
        provider = active[idx]
        result = call_provider(provider, prompt)
        if result:
            provider['calls'] += 1
            return result, provider['name']

    # All cloud providers failed — try Ollama
    result = call_ollama(prompt)
    return result, 'ollama' if result else None


def build_prompt(batch):
    """Build prompt for a batch of questions."""
    parts = []
    for i, q in enumerate(batch):
        f = q['fields']
        opts = " | ".join(f"{L}) {f.get(f'option_{L.lower()}', '')}" for L in 'ABCD' if f.get(f'option_{L.lower()}', '').strip())
        year = f.get('year', '')
        parts.append(f"Q{i+1}[PK={q['pk']}, Year={year}]: {f.get('question_text', '')}\n{opts}")
    return "Answer ALL the following UPSC CMS MCQs:\n\n" + "\n\n".join(parts)


def parse_response(text, n):
    """Parse AI response into list of dicts. Robust against various formats."""
    if not text:
        return None
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text).strip()

    # 1. Direct JSON array
    try:
        r = json.loads(text)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass

    # 2. Find JSON array in text
    m = re.search(r'\[[\s\S]*\]', text)
    if m:
        try:
            r = json.loads(m.group())
            return r if isinstance(r, list) else None
        except json.JSONDecodeError:
            pass

    # 3. JSONL (newline-separated objects)
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

    # 4. Regex extraction of individual objects
    for m2 in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
        try:
            o = json.loads(m2.group())
            if 'correct_answer' in o:
                objs.append(o)
        except json.JSONDecodeError:
            continue
    return objs if objs else None


def apply_enrichment(q, e):
    """Apply enrichment data to a question."""
    f = q['fields']
    ans = e.get('correct_answer', '').strip().upper()
    if ans in ('A', 'B', 'C', 'D'):
        f['correct_answer'] = ans

    for k in ['explanation', 'concept_explanation', 'mnemonic', 'book_name', 'chapter',
              'page_number', 'learning_technique', 'shortcut_tip']:
        v = e.get(k, '')
        if isinstance(v, str) and v.strip():
            f[k] = v.strip()

    if e.get('difficulty', '').lower() in ('easy', 'medium', 'hard'):
        f['difficulty'] = e['difficulty'].lower()

    for k in ['concept_tags', 'concept_keywords']:
        v = e.get(k, [])
        if isinstance(v, list) and v:
            f[k] = [str(x).strip() for x in v if str(x).strip()]

    # Build combined ai_explanation
    parts = []
    if f.get('explanation'):
        parts.append(f"**Answer: {f.get('correct_answer', '?')}**\n{f['explanation']}")
    if f.get('concept_explanation'):
        parts.append(f"**Concept:** {f['concept_explanation']}")
    if f.get('mnemonic'):
        parts.append(f"**Mnemonic:** {f['mnemonic']}")
    if f.get('shortcut_tip'):
        parts.append(f"**Exam Tip:** {f['shortcut_tip']}")
    if parts:
        f['ai_explanation'] = "\n\n".join(parts)


def is_done(q, answers_only=False):
    """Check if question is already enriched."""
    f = q['fields']
    has_answer = f.get('correct_answer', '').strip() in ('A', 'B', 'C', 'D')
    if answers_only:
        return has_answer
    return (has_answer
            and len(f.get('explanation', '').strip()) > 10
            and len(f.get('concept_explanation', '').strip()) > 5)


def main():
    parser = argparse.ArgumentParser(description='Enrich questions using all AI providers')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of questions to process')
    parser.add_argument('--batch', type=int, default=3, help='Questions per batch (default 3)')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    parser.add_argument('--answers-only', action='store_true', help='Only fill missing correct_answer')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("MASTER ENRICHMENT — All AI Providers + Ollama")
    log.info("=" * 60)

    # Init providers
    n_providers = init_providers()

    # Check Ollama
    ollama_ok = False
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        models = [m['name'] for m in r.json().get('models', [])]
        log.info(f"✅ Ollama available — models: {models}")
        ollama_ok = True
    except Exception:
        log.warning("⚠️ Ollama not available (will use cloud providers only)")

    if n_providers == 0 and not ollama_ok:
        log.error("❌ No AI providers available! Check .env API keys and/or start Ollama")
        return

    # Load fixture
    log.info("Loading fixture...")
    data = json.load(open(FIXTURE, 'r', encoding='utf-8'))
    questions = [x for x in data if x.get('model') == 'questions.question']
    log.info(f"Total questions: {len(questions)}")

    # Load progress
    processed_pks = set()
    if not args.reset and PROGRESS.exists():
        try:
            processed_pks = set(json.loads(PROGRESS.read_text(encoding='utf-8')))
        except Exception:
            pass
    log.info(f"Already processed: {len(processed_pks)}")

    # Filter questions needing enrichment
    todo = [q for q in questions if q['pk'] not in processed_pks and not is_done(q, args.answers_only)]
    if args.limit > 0:
        todo = todo[:args.limit]
    log.info(f"To enrich: {len(todo)}")
    if not todo:
        log.info("All questions enriched! ✅")
        return

    BATCH_SIZE = args.batch
    batches = [todo[i:i+BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    log.info(f"Batches: {len(batches)} ({BATCH_SIZE} questions each)")
    log.info("")

    enriched = 0
    failed = 0
    provider_stats = {}
    t0 = time.time()

    for idx, batch in enumerate(batches):
        bn = idx + 1
        pks = [q['pk'] for q in batch]
        prompt = build_prompt(batch)

        raw, provider_name = call_ai(prompt)
        results = parse_response(raw, len(batch))

        if results:
            for i, q in enumerate(batch):
                if i < len(results):
                    apply_enrichment(q, results[i])
                    processed_pks.add(q['pk'])
                    enriched += 1
                else:
                    failed += 1
            provider_stats[provider_name] = provider_stats.get(provider_name, 0) + len(batch)
        else:
            failed += len(batch)
            log.error(f"  Batch {bn} FAILED pks={pks}")

        # Save every 5 batches or at the end
        if bn % 5 == 0 or bn == len(batches):
            PROGRESS.write_text(json.dumps(sorted(processed_pks)), encoding='utf-8')
            with open(FIXTURE, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)

        # Progress log every 10 batches
        if bn % 10 == 0 or bn == len(batches):
            elapsed = time.time() - t0
            rate = enriched / max(elapsed, 1) * 60
            remaining = (len(todo) - enriched - failed) / max(rate, 0.1) if rate > 0 else 0
            log.info(f"[{bn}/{len(batches)}] ✅{enriched} ❌{failed} | "
                     f"{rate:.0f} q/min | ~{remaining:.0f}min left | "
                     f"providers: {provider_stats}")

    # Final save with pretty formatting
    log.info("\nFinal save...")
    PROGRESS.write_text(json.dumps(sorted(processed_pks)), encoding='utf-8')
    with open(FIXTURE, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)

    elapsed = time.time() - t0
    log.info(f"\n{'=' * 60}")
    log.info(f"DONE! Enriched: {enriched} | Failed: {failed} | Time: {elapsed / 60:.1f}min")
    log.info(f"Provider usage: {provider_stats}")
    log.info(f"Total processed: {len(processed_pks)}")

    # Final stats
    all_q = [x for x in data if x.get('model') == 'questions.question']
    no_answer = sum(1 for q in all_q if q['fields'].get('correct_answer', '').strip() not in ('A', 'B', 'C', 'D'))
    no_expl = sum(1 for q in all_q if not q['fields'].get('explanation', '').strip())
    log.info(f"\nRemaining: {no_answer} without answer, {no_expl} without explanation")
    log.info(f"Run: python manage.py loaddata questions_fixture.json")


if __name__ == '__main__':
    main()
