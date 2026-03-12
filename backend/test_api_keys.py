"""
Test all AI API keys — reports working/rate-limited/invalid status for each provider.
Usage: python test_api_keys.py
"""
import os, sys, time
from dotenv import load_dotenv
load_dotenv(override=True)

TEST_PROMPT = "What is the most common cause of community-acquired pneumonia? Answer in one sentence."

results = []

def test_groq():
    key = os.getenv('GROQ_API_KEY', '')
    if not key:
        return 'NO_KEY', 'GROQ_API_KEY not set in .env'
    try:
        from groq import Groq
        client = Groq(api_key=key)
        r = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_tokens=100, temperature=0.1, timeout=15.0
        )
        return 'OK', r.choices[0].message.content[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit (free tier: 30 RPM, 14400 RPD)'
        if '401' in err: return 'INVALID', 'API key invalid or expired'
        return 'ERROR', err[:100]

def test_cerebras():
    key = os.getenv('CEREBRAS_API_KEY', '')
    if not key:
        return 'NO_KEY', 'CEREBRAS_API_KEY not set in .env'
    try:
        from cerebras.cloud.sdk import Cerebras
        client = Cerebras(api_key=key)
        r = client.chat.completions.create(
            model='llama3.1-8b',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_completion_tokens=100, temperature=0.1,
        )
        return 'OK', r.choices[0].message.content[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit (free tier: 30 RPM)'
        if '401' in err: return 'INVALID', 'API key invalid or expired'
        return 'ERROR', err[:100]

def test_gemini():
    key = os.getenv('GEMINI_API_KEY', '')
    if not key:
        return 'NO_KEY', 'GEMINI_API_KEY not set in .env'
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        r = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=TEST_PROMPT,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=100),
        )
        return 'OK', r.text[:80] if r and r.text else 'Empty response'
    except Exception as e:
        err = str(e)
        if '429' in err or 'RESOURCE_EXHAUSTED' in err: return 'RATE_LIMITED', 'Quota exhausted (free: 15 RPM, 1500 RPD)'
        if '401' in err or '403' in err: return 'INVALID', 'API key invalid'
        return 'ERROR', err[:100]

def test_github():
    key = os.getenv('GITHUB_TOKEN', '')
    if not key:
        return 'NO_KEY', 'GITHUB_TOKEN not set in .env'
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url='https://models.inference.ai.azure.com')
        r = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_tokens=100, temperature=0.1, timeout=15.0
        )
        return 'OK', r.choices[0].message.content[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit (free: 150 RPM, 15K RPD)'
        if '401' in err or '403' in err: return 'INVALID', 'Token invalid or expired'
        return 'ERROR', err[:100]

def test_openrouter():
    key = os.getenv('OPENROUTER_API_KEY', '')
    if not key:
        return 'NO_KEY', 'OPENROUTER_API_KEY not set in .env'
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url='https://openrouter.ai/api/v1')
        r = client.chat.completions.create(
            model='meta-llama/llama-3.3-70b-instruct:free',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_tokens=100, temperature=0.1, timeout=15.0
        )
        return 'OK', r.choices[0].message.content[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit (free: 20 RPM)'
        if '401' in err or '403' in err: return 'INVALID', 'API key invalid'
        return 'ERROR', err[:100]

def test_cohere():
    key = os.getenv('COHERE_API_KEY', '')
    if not key:
        return 'NO_KEY', 'COHERE_API_KEY not set in .env'
    try:
        import cohere
        client = cohere.ClientV2(api_key=key)
        r = client.chat(
            model='command-a-03-2025',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_tokens=100, temperature=0.1,
        )
        return 'OK', r.message.content[0].text[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit (free: 20 RPM, 1000/month)'
        if '401' in err: return 'INVALID', 'API key invalid'
        return 'ERROR', err[:100]

def test_deepseek():
    key = os.getenv('DEEPSEEK_API_KEY', '')
    if not key:
        return 'NO_KEY', 'DEEPSEEK_API_KEY not set in .env'
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url='https://api.deepseek.com')
        r = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': TEST_PROMPT}],
            max_tokens=100, temperature=0.1, timeout=15.0
        )
        return 'OK', r.choices[0].message.content[:80]
    except Exception as e:
        err = str(e)
        if '429' in err: return 'RATE_LIMITED', 'Rate limit hit'
        if '401' in err: return 'INVALID', 'API key invalid'
        if '402' in err or 'Insufficient' in err: return 'NO_BALANCE', 'Balance depleted (pay-as-you-go)'
        return 'ERROR', err[:100]

def test_ollama():
    import requests
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        models = [m['name'] for m in r.json().get('models', [])]
        if not models:
            return 'NO_MODELS', 'Ollama running but no models pulled. Run: ollama pull llama3.2:3b'
        # Test a call
        r2 = requests.post('http://localhost:11434/api/chat', json={
            'model': models[0],
            'messages': [{'role': 'user', 'content': TEST_PROMPT}],
            'stream': False, 'options': {'num_predict': 50}
        }, timeout=60)
        r2.raise_for_status()
        return 'OK', f"Models: {models} | {r2.json()['message']['content'][:50]}"
    except Exception as e:
        if 'Connection' in str(e):
            return 'NOT_RUNNING', 'Ollama not running. Start with: ollama serve'
        return 'ERROR', str(e)[:100]


STATUS_ICONS = {'OK': '✅', 'RATE_LIMITED': '⚠️', 'INVALID': '❌', 'NO_KEY': '⬜', 'ERROR': '❌', 'NO_BALANCE': '💸', 'NOT_RUNNING': '🔴', 'NO_MODELS': '🟡'}

tests = [
    ('Groq (Llama 3.3 70B)', '30 RPM, 14,400 RPD', 'Free', test_groq),
    ('Cerebras (Llama 3.1 8B)', '30 RPM, ~1M tok/day', 'Free', test_cerebras),
    ('Gemini (Flash 2.0)', '15 RPM, 1,500 RPD', 'Free', test_gemini),
    ('GitHub Models (GPT-4o-mini)', '150 RPM, 15K RPD', 'Free with PAT', test_github),
    ('OpenRouter (Llama 3.3 70B)', '20 RPM (free tier)', 'Free', test_openrouter),
    ('Cohere (Command-A)', '20 RPM, 1,000/month', 'Free', test_cohere),
    ('DeepSeek (deepseek-chat)', 'No strict limit', 'Pay-as-you-go', test_deepseek),
    ('Ollama (Local)', 'Unlimited', 'Free (local)', test_ollama),
]

print("=" * 70)
print("  CrackCMS AI API Key Status Report")
print("=" * 70)
print()

working = 0
for name, limits, tier, test_fn in tests:
    print(f"Testing {name}...", end=' ', flush=True)
    status, detail = test_fn()
    icon = STATUS_ICONS.get(status, '❓')
    print(f"{icon} {status}")
    print(f"  Rate Limits: {limits} | Tier: {tier}")
    print(f"  Detail: {detail}")
    print()
    if status == 'OK':
        working += 1
    time.sleep(1)

print("=" * 70)
print(f"  Summary: {working}/{len(tests)} providers working")
print()

# Recommendations
if working < 3:
    print("⚠️ Low provider count! Enrichment will be slow.")
    print("   Consider refreshing expired API keys.")
print()
print("To fix non-working keys:")
print("  Groq:       https://console.groq.com/keys")
print("  Cerebras:   https://cloud.cerebras.ai/")
print("  Gemini:     https://aistudio.google.com/apikey")
print("  GitHub:     https://github.com/settings/tokens (needs 'models' scope)")
print("  OpenRouter: https://openrouter.ai/keys")
print("  Cohere:     https://dashboard.cohere.com/api-keys")
print("  DeepSeek:   https://platform.deepseek.com/api_keys")
print("  Ollama:     https://ollama.ai/download → ollama pull llama3.2:3b → ollama serve")
