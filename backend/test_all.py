#!/usr/bin/env python
"""
CrackCMS Comprehensive Test Suite
===================================
Tests everything: API keys, database, AI service, endpoints, fixture integrity.
Run: python test_all.py [--quick] [--keys-only] [--db-only] [--ai-only] [--endpoints-only]

Examples:
    python test_all.py              # Run all tests
    python test_all.py --quick      # Skip slow AI provider tests
    python test_all.py --keys-only  # Only test API keys
    python test_all.py --ai-only   # Only test AI service layer
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
from dotenv import load_dotenv
load_dotenv(override=True)

import django
django.setup()

# ─── Colors & formatting ───
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'

pass_count = 0
fail_count = 0
skip_count = 0
results = []

def ok(test_name, detail=""):
    global pass_count
    pass_count += 1
    results.append(('PASS', test_name, detail))
    print(f"  {GREEN}[OK] PASS{RESET} {test_name}" + (f" -- {detail[:80]}" if detail else ""))

def fail(test_name, detail=""):
    global fail_count
    fail_count += 1
    results.append(('FAIL', test_name, detail))
    print(f"  {RED}[XX] FAIL{RESET} {test_name}" + (f" -- {detail[:100]}" if detail else ""))

def skip(test_name, detail=""):
    global skip_count
    skip_count += 1
    results.append(('SKIP', test_name, detail))
    print(f"  {YELLOW}[--] SKIP{RESET} {test_name}" + (f" -- {detail[:80]}" if detail else ""))

def section(title):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")


# ══════════════════════════════════════════════════════════════
# SECTION 1: DATABASE HEALTH
# ══════════════════════════════════════════════════════════════
def test_database():
    section("1. DATABASE HEALTH")

    # 1.1 Django DB connection
    try:
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SELECT 1")
        ok("DB connection", "SQLite responding")
    except Exception as e:
        fail("DB connection", str(e))

    # 1.2 Question count
    try:
        from questions.models import Question
        count = Question.objects.count()
        if count >= 2000:
            ok("Question count", f"{count} questions in DB")
        elif count > 0:
            fail("Question count", f"Only {count} questions (expected 2000+)")
        else:
            fail("Question count", "0 questions — run: python manage.py loaddata questions_fixture.json")
    except Exception as e:
        fail("Question count", str(e))

    # 1.3 Enrichment quality
    try:
        from questions.models import Question
        total = Question.objects.count()
        with_answer = Question.objects.exclude(correct_answer='').exclude(correct_answer__isnull=True).count()
        with_explanation = Question.objects.exclude(explanation='').exclude(explanation__isnull=True).count()
        pct = (with_answer / total * 100) if total else 0
        if pct >= 99:
            ok("Enrichment coverage", f"{with_answer}/{total} with answers ({pct:.0f}%), {with_explanation} with explanations")
        else:
            fail("Enrichment coverage", f"Only {with_answer}/{total} ({pct:.0f}%) have answers")
    except Exception as e:
        fail("Enrichment coverage", str(e))

    # 1.4 Subject/topic data
    try:
        from questions.models import Subject, Topic
        subjects = Subject.objects.count()
        topics = Topic.objects.count()
        if subjects > 0:
            ok("Subject/Topic data", f"{subjects} subjects, {topics} topics")
        else:
            fail("Subject/Topic data", "No subjects found")
    except Exception as e:
        fail("Subject/Topic data", str(e))

    # 1.5 Migrations check
    try:
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        output = out.getvalue()
        unapplied = [l for l in output.strip().split('\n') if l.strip().startswith('[ ]')]
        if not unapplied:
            ok("Migrations", "All migrations applied")
        else:
            fail("Migrations", f"{len(unapplied)} unapplied migrations")
    except Exception as e:
        fail("Migrations", str(e))

    # 1.6 User model
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_count = User.objects.count()
        ok("User model", f"{user_count} users in DB")
    except Exception as e:
        fail("User model", str(e))


# ══════════════════════════════════════════════════════════════
# SECTION 2: FIXTURE INTEGRITY
# ══════════════════════════════════════════════════════════════
def test_fixture():
    section("2. FIXTURE INTEGRITY")

    fixture_path = Path(__file__).parent / 'questions_fixture.json'

    # 2.1 File exists
    if not fixture_path.exists():
        fail("Fixture file exists", "questions_fixture.json not found")
        return
    ok("Fixture file exists", f"{fixture_path.stat().st_size / 1e6:.1f} MB")

    # 2.2 Valid JSON
    try:
        data = json.loads(fixture_path.read_text(encoding='utf-8'))
        ok("Valid JSON", f"{len(data)} objects")
    except Exception as e:
        fail("Valid JSON", str(e))
        return

    # 2.3 Question objects
    questions = [d for d in data if d.get('model') == 'questions.question']
    if questions:
        ok("Question objects", f"{len(questions)} questions in fixture")
    else:
        fail("Question objects", "No questions.question entries found")
        return

    # 2.4 No duplicate PKs
    pks = [q['pk'] for q in questions]
    unique_pks = set(pks)
    if len(pks) == len(unique_pks):
        ok("No duplicate PKs", f"All {len(pks)} PKs unique")
    else:
        dupes = len(pks) - len(unique_pks)
        fail("No duplicate PKs", f"{dupes} duplicate PK(s) found")

    # 2.5 All have answers
    no_answer = [q['pk'] for q in questions if q['fields'].get('correct_answer', '').strip() not in ('A', 'B', 'C', 'D')]
    if not no_answer:
        ok("All have correct_answer", f"{len(questions)}/{len(questions)} enriched")
    else:
        fail("All have correct_answer", f"{len(no_answer)} missing: PKs {no_answer[:10]}...")

    # 2.6 All have explanations
    no_exp = [q['pk'] for q in questions if len(q['fields'].get('explanation', '').strip()) < 10]
    if not no_exp:
        ok("All have explanations", "All explanations > 10 chars")
    else:
        fail("All have explanations", f"{len(no_exp)} missing: PKs {no_exp[:10]}...")

    # 2.7 Required fields present
    required = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'year']
    missing = []
    for q in questions:
        for f in required:
            if not q['fields'].get(f):
                missing.append((q['pk'], f))
    if not missing:
        ok("Required fields", "All questions have text, options A-D, year")
    else:
        fail("Required fields", f"{len(missing)} missing fields: {missing[:5]}...")


# ══════════════════════════════════════════════════════════════
# SECTION 3: API KEY TESTS
# ══════════════════════════════════════════════════════════════
def test_api_keys():
    section("3. API KEY TESTS")
    prompt = "What is the most common cause of community-acquired pneumonia? Answer in one sentence."

    def _test_openai_compat(name, env_var, base_url, model, timeout=15.0):
        key = os.getenv(env_var, '')
        if not key:
            skip(f"{name}", f"{env_var} not set")
            return
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=base_url)
            r = client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=60, temperature=0.1, timeout=timeout,
            )
            ok(name, r.choices[0].message.content[:70])
        except Exception as e:
            err = str(e)
            if '429' in err:
                skip(name, "Rate limited (try later)")
            elif '401' in err or '403' in err:
                fail(name, f"API key INVALID — get new key")
            elif '402' in err or 'Insufficient' in err:
                fail(name, "No balance / credits exhausted")
            else:
                fail(name, err[:100])

    # Groq
    key = os.getenv('GROQ_API_KEY', '')
    if key:
        try:
            from groq import Groq
            r = Groq(api_key=key).chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=60, temperature=0.1, timeout=15.0)
            ok("Groq (Llama 3.3 70B)", r.choices[0].message.content[:70])
        except Exception as e:
            err = str(e)
            if '429' in err: skip("Groq", "Rate limited")
            elif '401' in err: fail("Groq", "API key invalid")
            else: fail("Groq", err[:100])
    else:
        skip("Groq", "GROQ_API_KEY not set")

    # Cerebras
    key = os.getenv('CEREBRAS_API_KEY', '')
    if key:
        try:
            from cerebras.cloud.sdk import Cerebras
            r = Cerebras(api_key=key).chat.completions.create(
                model='llama3.1-8b',
                messages=[{'role': 'user', 'content': prompt}],
                max_completion_tokens=60, temperature=0.1)
            ok("Cerebras (Llama 3.1 8B)", r.choices[0].message.content[:70])
        except Exception as e:
            err = str(e)
            if '429' in err: skip("Cerebras", "Rate limited")
            elif '401' in err: fail("Cerebras", "API key invalid")
            else: fail("Cerebras", err[:100])
    else:
        skip("Cerebras", "CEREBRAS_API_KEY not set")

    # Gemini
    key = os.getenv('GEMINI_API_KEY', '')
    if key:
        try:
            from google import genai
            from google.genai import types
            r = genai.Client(api_key=key).models.generate_content(
                model='gemini-2.0-flash', contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=60))
            ok("Gemini (Flash 2.0)", r.text[:70] if r and r.text else "Empty")
        except Exception as e:
            err = str(e)
            if '429' in err or 'RESOURCE_EXHAUSTED' in err: skip("Gemini", "Quota exhausted")
            elif '401' in err or '403' in err: fail("Gemini", "API key invalid")
            else: fail("Gemini", err[:100])
    else:
        skip("Gemini", "GEMINI_API_KEY not set")

    # Cohere
    key = os.getenv('COHERE_API_KEY', '')
    if key:
        try:
            import cohere
            r = cohere.ClientV2(api_key=key).chat(
                model='command-a-03-2025',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=60, temperature=0.1)
            ok("Cohere (Command-A)", r.message.content[0].text[:70])
        except Exception as e:
            err = str(e)
            if '429' in err: skip("Cohere", "Rate limited")
            elif '401' in err: fail("Cohere", "API key invalid")
            else: fail("Cohere", err[:100])
    else:
        skip("Cohere", "COHERE_API_KEY not set")

    # OpenAI-compatible providers
    time.sleep(0.5)
    _test_openai_compat("GitHub Models (GPT-4o-mini)", "GITHUB_TOKEN",
                        "https://models.inference.ai.azure.com", "gpt-4o-mini")
    time.sleep(0.5)
    _test_openai_compat("OpenRouter (Llama 3.3)", "OPENROUTER_API_KEY",
                        "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", 20.0)
    time.sleep(0.5)
    _test_openai_compat("OpenRouter2 (Key 2)", "OPENROUTER_API_KEY2",
                        "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", 20.0)
    time.sleep(0.5)
    _test_openai_compat("HuggingFace (Llama 3.3)", "HUGGINGFACE_API_KEY",
                        "https://router.huggingface.co/novita/v3/openai", "meta-llama/llama-3.3-70b-instruct", 20.0)
    time.sleep(0.5)
    _test_openai_compat("Mistral (small-latest)", "MISTRAL_API_KEY",
                        "https://api.mistral.ai/v1", "mistral-small-latest")
    time.sleep(0.5)
    _test_openai_compat("DeepSeek (PAID-last)", "DEEPSEEK_API_KEY",
                        "https://api.deepseek.com", "deepseek-chat")

    # Ollama (local)
    try:
        import requests
        r = requests.get('http://localhost:11434/api/tags', timeout=3)
        models = [m['name'] for m in r.json().get('models', [])]
        if models:
            ok("Ollama (local)", f"Models: {models}")
        else:
            skip("Ollama", "Running but no models pulled")
    except Exception:
        skip("Ollama", "Not running (optional)")


# ══════════════════════════════════════════════════════════════
# SECTION 4: AI SERVICE LAYER
# ══════════════════════════════════════════════════════════════
def test_ai_service():
    section("4. AI SERVICE LAYER")

    # 4.1 Service init
    try:
        from ai_engine.services import AIService
        svc = AIService()
        ok("AIService init", "Created successfully")
    except Exception as e:
        fail("AIService init", str(e))
        return

    # 4.2 Provider count
    providers = [n for n, c in [
        ('Gemini', svc.gemini_client), ('Groq', svc.groq),
        ('Cerebras', svc.cerebras), ('Cohere', svc.cohere),
        ('OpenRouter', svc.openrouter), ('OpenRouter2', svc.openrouter2),
        ('GitHub', svc.github_models), ('HuggingFace', svc.huggingface),
        ('Mistral', svc.mistral), ('DeepSeek', svc.deepseek),
    ] if c]
    if len(providers) >= 3:
        ok("Provider count", f"{len(providers)}/10 initialized: {', '.join(providers)}")
    elif len(providers) > 0:
        fail("Provider count", f"Only {len(providers)} providers — need at least 3 for reliability")
    else:
        fail("Provider count", "No providers initialized! Check .env API keys")

    # 4.3 Quick AI call test
    try:
        start_t = time.time()
        answer = svc._call_ai("What is hypertension? One sentence.", max_tokens=100)
        elapsed = time.time() - start_t
        if answer and 'unavailable' not in answer.lower():
            ok("AI call (_call_ai)", f"{elapsed:.1f}s — {answer[:60]}")
        else:
            fail("AI call (_call_ai)", f"No response after {elapsed:.1f}s")
    except Exception as e:
        fail("AI call (_call_ai)", str(e))

    # 4.4 ask_tutor
    try:
        answer = svc.ask_tutor("What are the causes of acute pancreatitis?")
        if answer and len(answer) > 50:
            ok("ask_tutor()", f"Response: {len(answer)} chars")
        else:
            fail("ask_tutor()", "Empty or too short response")
    except Exception as e:
        fail("ask_tutor()", str(e))

    # 4.5 generate_mnemonic
    try:
        answer = svc.generate_mnemonic("Causes of pancreatitis")
        if answer and len(answer) > 30:
            ok("generate_mnemonic()", f"Response: {len(answer)} chars")
        else:
            fail("generate_mnemonic()", "Empty or too short response")
    except Exception as e:
        fail("generate_mnemonic()", str(e))

    # 4.6 explain_concept
    try:
        answer = svc.explain_concept("Myocardial infarction", level="basic")
        if answer and len(answer) > 30:
            ok("explain_concept()", f"Response: {len(answer)} chars")
        else:
            fail("explain_concept()", "Empty or too short response")
    except Exception as e:
        fail("explain_concept()", str(e))


# ══════════════════════════════════════════════════════════════
# SECTION 5: DJANGO ENDPOINTS (HTTP)
# ══════════════════════════════════════════════════════════════
def test_endpoints():
    section("5. DJANGO ENDPOINTS")

    from django.test import RequestFactory
    from django.test.client import Client
    client = Client()

    # 5.1 Health check
    try:
        r = client.get('/')
        if r.status_code == 200:
            ok("GET / (health)", r.json().get('status', ''))
        else:
            fail("GET / (health)", f"Status {r.status_code}")
    except Exception as e:
        fail("GET / (health)", str(e))

    # 5.2 API root
    try:
        r = client.get('/api/')
        if r.status_code == 200:
            ok("GET /api/ (root)", str(r.json().get('endpoints', ''))[:60])
        else:
            fail("GET /api/ (root)", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/ (root)", str(e))

    # 5.3 Question list (public or auth-required)
    try:
        r = client.get('/api/questions/')
        if r.status_code in (200, 401, 403):
            ok("GET /api/questions/", f"Status {r.status_code}")
        else:
            fail("GET /api/questions/", f"Unexpected status {r.status_code}")
    except Exception as e:
        fail("GET /api/questions/", str(e))

    # 5.4 Question years
    try:
        r = client.get('/api/questions/years/')
        if r.status_code in (200, 401):
            ok("GET /api/questions/years/", f"Status {r.status_code}")
        else:
            fail("GET /api/questions/years/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/questions/years/", str(e))

    # 5.5 AI status
    try:
        r = client.get('/api/ai/status/')
        if r.status_code == 200:
            data = r.json()
            ok("GET /api/ai/status/", f"Providers: {data.get('providers_active', '?')}")
        else:
            fail("GET /api/ai/status/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/ai/status/", str(e))

    # 5.6 AI test
    try:
        r = client.get('/api/ai/test/')
        if r.status_code == 200:
            ok("GET /api/ai/test/", r.json().get('response', '')[:60])
        else:
            fail("GET /api/ai/test/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/ai/test/", str(e))

    # 5.7 Subjects
    try:
        r = client.get('/api/questions/subjects/')
        if r.status_code in (200, 401):
            ok("GET /api/questions/subjects/", f"Status {r.status_code}")
        else:
            fail("GET /api/questions/subjects/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/questions/subjects/", str(e))

    # 5.8 Auth endpoints exist
    try:
        r = client.post('/api/auth/login/', {'username': 'test', 'password': 'test'},
                        content_type='application/json')
        if r.status_code in (200, 400, 401):
            ok("POST /api/auth/login/", f"Status {r.status_code} (endpoint reachable)")
        else:
            fail("POST /api/auth/login/", f"Status {r.status_code}")
    except Exception as e:
        fail("POST /api/auth/login/", str(e))

    # 5.9 Flashcard list needs auth
    try:
        r = client.get('/api/questions/flashcards/')
        if r.status_code in (200, 401, 403):
            ok("GET /api/questions/flashcards/", f"Status {r.status_code}")
        else:
            fail("GET /api/questions/flashcards/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/questions/flashcards/", str(e))

    # 5.10 Tests list
    try:
        r = client.get('/api/tests/')
        if r.status_code in (200, 401):
            ok("GET /api/tests/", f"Status {r.status_code}")
        else:
            fail("GET /api/tests/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/tests/", str(e))

    # 5.11 Analytics
    try:
        r = client.get('/api/analytics/dashboard/')
        if r.status_code in (200, 401):
            ok("GET /api/analytics/dashboard/", f"Status {r.status_code}")
        else:
            fail("GET /api/analytics/dashboard/", f"Status {r.status_code}")
    except Exception as e:
        fail("GET /api/analytics/dashboard/", str(e))


# ══════════════════════════════════════════════════════════════
# SECTION 6: CONFIGURATION CHECKS
# ══════════════════════════════════════════════════════════════
def test_config():
    section("6. CONFIGURATION")

    from django.conf import settings as s

    # 6.1 Secret key
    if s.SECRET_KEY and 'insecure' not in s.SECRET_KEY:
        ok("SECRET_KEY", "Set and not insecure default")
    else:
        fail("SECRET_KEY", "Using insecure default — set DJANGO_SECRET_KEY env var for production")

    # 6.2 CORS
    cors = getattr(s, 'CORS_ALLOWED_ORIGINS', [])
    if cors:
        ok("CORS_ALLOWED_ORIGINS", f"{len(cors)} origins: {cors[:3]}")
    else:
        fail("CORS_ALLOWED_ORIGINS", "Empty — frontend won't be able to call API")

    # 6.3 Middleware
    middleware = getattr(s, 'MIDDLEWARE', [])
    has_cors = any('cors' in m.lower() for m in middleware)
    has_whitenoise = any('whitenoise' in m.lower() for m in middleware)
    if has_cors:
        ok("CORS middleware", "corsheaders.middleware present")
    else:
        fail("CORS middleware", "Missing — add django-cors-headers")
    if has_whitenoise:
        ok("WhiteNoise middleware", "Static file serving ready")
    else:
        fail("WhiteNoise middleware", "Missing — needed for Render deployment")

    # 6.4 Fixture file
    fixture = Path(__file__).parent / 'questions_fixture.json'
    if fixture.exists():
        ok("Fixture file", f"Present ({fixture.stat().st_size / 1e6:.1f} MB)")
    else:
        fail("Fixture file", "Missing — question bank won't load on deploy")

    # 6.5 Build script
    build = Path(__file__).parent / 'build.sh'
    if build.exists():
        ok("build.sh", "Present for Render deployment")
    else:
        fail("build.sh", "Missing — Render won't build correctly")

    # 6.6 Requirements.txt
    reqs = Path(__file__).parent / 'requirements.txt'
    if reqs.exists():
        lines = [l.strip() for l in reqs.read_text().splitlines() if l.strip() and not l.startswith('#')]
        ok("requirements.txt", f"{len(lines)} dependencies")
    else:
        fail("requirements.txt", "Missing")

    # 6.7 ENV file
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        ok(".env file", "Present")
    else:
        skip(".env file", "Not present (using system env vars)")


# ══════════════════════════════════════════════════════════════
# SECTION 7: AUTH FLOW TEST
# ══════════════════════════════════════════════════════════════
def test_auth_flow():
    section("7. AUTH FLOW")
    from django.test.client import Client
    client = Client()
    import uuid

    test_user = f"test_{uuid.uuid4().hex[:8]}"
    test_pass = "TestPass123!@#"
    test_email = f"{test_user}@test.com"

    # 7.1 Register
    try:
        r = client.post('/api/auth/register/', {
            'username': test_user, 'email': test_email,
            'password': test_pass, 'password2': test_pass
        }, content_type='application/json')
        if r.status_code in (200, 201):
            ok("Register user", f"Created {test_user}")
        else:
            detail = r.json() if r.headers.get('content-type', '').startswith('application/json') else r.content[:100]
            fail("Register user", f"Status {r.status_code}: {detail}")
            return
    except Exception as e:
        fail("Register user", str(e))
        return

    # 7.2 Login
    try:
        r = client.post('/api/auth/login/', {
            'username': test_user, 'password': test_pass
        }, content_type='application/json')
        if r.status_code == 200:
            data = r.json()
            token = data.get('access', '')
            if token:
                ok("Login", "Got JWT access token")
            else:
                fail("Login", "No access token in response")
                return
        else:
            fail("Login", f"Status {r.status_code}")
            return
    except Exception as e:
        fail("Login", str(e))
        return

    # 7.3 Auth'd request
    try:
        r = client.get('/api/auth/profile/',
                       HTTP_AUTHORIZATION=f'Bearer {token}')
        if r.status_code == 200:
            ok("Authed profile request", f"Username: {r.json().get('username', '?')}")
        else:
            fail("Authed profile request", f"Status {r.status_code}")
    except Exception as e:
        fail("Authed profile request", str(e))

    # 7.4 Flashcard create (auth'd)
    try:
        r = client.post('/api/questions/flashcards/', {
            'front': 'Test question - what is hypertension?',
            'back': 'Sustained elevated blood pressure > 140/90 mmHg',
            'difficulty': 'easy'
        }, content_type='application/json',
           HTTP_AUTHORIZATION=f'Bearer {token}')
        if r.status_code in (200, 201):
            card_id = r.json().get('id', '')
            ok("Flashcard CREATE", f"Created card ID {card_id}")
            # Cleanup
            if card_id:
                client.delete(f'/api/questions/flashcards/{card_id}/',
                              HTTP_AUTHORIZATION=f'Bearer {token}')
        elif r.status_code == 401:
            fail("Flashcard CREATE", "Auth failed — JWT not accepted")
        else:
            fail("Flashcard CREATE", f"Status {r.status_code}: {r.content[:100]}")
    except Exception as e:
        fail("Flashcard CREATE", str(e))

    # 7.5 Token balance
    try:
        r = client.get('/api/auth/tokens/',
                       HTTP_AUTHORIZATION=f'Bearer {token}')
        if r.status_code == 200:
            data = r.json()
            ok("Token balance", f"Balance: {data.get('balance', data.get('total', '?'))}")
        else:
            fail("Token balance", f"Status {r.status_code}")
    except Exception as e:
        fail("Token balance", str(e))

    # Cleanup test user
    try:
        from django.contrib.auth import get_user_model
        get_user_model().objects.filter(username=test_user).delete()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CrackCMS Comprehensive Test Suite')
    parser.add_argument('--quick', action='store_true', help='Skip slow AI provider tests')
    parser.add_argument('--keys-only', action='store_true', help='Only test API keys')
    parser.add_argument('--db-only', action='store_true', help='Only test database')
    parser.add_argument('--ai-only', action='store_true', help='Only test AI service')
    parser.add_argument('--endpoints-only', action='store_true', help='Only test HTTP endpoints')
    parser.add_argument('--auth-only', action='store_true', help='Only test auth flow')
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  CrackCMS Comprehensive Test Suite{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    specific = args.keys_only or args.db_only or args.ai_only or args.endpoints_only or args.auth_only

    if not specific or args.db_only:
        test_database()

    if not specific:
        test_fixture()

    if not specific or args.keys_only:
        if not args.quick:
            test_api_keys()
        else:
            section("3. API KEY TESTS (SKIPPED — quick mode)")

    if not specific or args.ai_only:
        if not args.quick:
            test_ai_service()
        else:
            section("4. AI SERVICE LAYER (SKIPPED — quick mode)")

    if not specific or args.endpoints_only:
        test_endpoints()

    if not specific:
        test_config()

    if not specific or args.auth_only:
        test_auth_flow()

    # Summary
    total = pass_count + fail_count + skip_count
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  {BOLD}RESULTS: {GREEN}{pass_count} passed{RESET}, {RED}{fail_count} failed{RESET}, {YELLOW}{skip_count} skipped{RESET}  (total: {total})")
    if fail_count == 0:
        print(f"  {GREEN}{BOLD}ALL TESTS PASSED!{RESET}")
    else:
        print(f"  {RED}{BOLD}{fail_count} FAILURE(S) — see details above{RESET}")
    print(f"{'='*60}\n")

    sys.exit(1 if fail_count > 0 else 0)
