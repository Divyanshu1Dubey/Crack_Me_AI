# API Keys Setup Guide

CrackCMS uses 7 cloud AI providers + Ollama for round-robin AI features. This guide explains how to get and configure each API key.

## Environment Variables

Add these to your `.env` file (backend root) or set them as environment variables on Render/Vercel:

```env
# ─── AI Provider API Keys ───
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csk-...
GEMINI_API_KEY=AIza...
GITHUB_TOKEN=ghp_...
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_API_KEY2=sk-or-...
ELEVENLABS_API_KEY=sk_...
COHERE_API_KEY=...
DEEPSEEK_API_KEY=sk-...

# ─── Email (Gmail SMTP) ───
EMAIL_HOST_USER=crackwith.ai@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx

# ─── Frontend URL (for password reset links) ───
FRONTEND_URL=http://localhost:3000
```

---

## Provider Setup Instructions

### 1. Groq (Free — 30 RPM)
- **Model**: Llama 3.3 70B Versatile
- **Sign up**: https://console.groq.com
- **Get key**: Console → API Keys → Create
- **Rate limit**: 30 req/min (free tier)

### 2. Cerebras (Free — 30 RPM)
- **Model**: Llama 3.1 8B
- **Sign up**: https://cloud.cerebras.ai
- **Get key**: Dashboard → API Keys
- **Rate limit**: 30 req/min

### 3. Google Gemini (Free — 15 RPM)
- **Model**: Gemini 2.0 Flash
- **Sign up**: https://aistudio.google.com
- **Get key**: API Keys → Create
- **Rate limit**: 15 req/min (free tier)

### 4. GitHub Models (Free — 150 RPM)
- **Model**: GPT-4o Mini
- **Sign up**: https://github.com/settings/tokens
- **Get key**: Generate a personal access token (classic) with no special scopes
- **Rate limit**: 150 req/min

### 5. OpenRouter (Free tier)
- **Model**: Meta Llama 3 8B (free)
- **Sign up**: https://openrouter.ai
- **Get key**: Dashboard → API Keys
- **Rate limit**: ~20 req/min (free models)

### 6. Cohere (Free trial)
- **Model**: Command A
- **Sign up**: https://dashboard.cohere.com
- **Get key**: API Keys → Create Trial Key
- **Rate limit**: ~20 req/min

### 7. DeepSeek (Pay-as-you-go)
- **Model**: DeepSeek Chat
- **Sign up**: https://platform.deepseek.com
- **Get key**: API Keys → Create
- **Note**: Requires account balance. Very affordable ($0.14/1M input tokens)

### 8. Ollama (Local — Unlimited)
- **Model**: llama3.2:3b (default)
- **Install**: See OLLAMA_SETUP.md
- **No API key needed** — runs locally on port 11434

---

## Testing Your Keys

Run the API key tester:

```bash
cd backend
python test_api_keys.py
```

This will test each provider and show ✅/❌ status.

---

## How Round-Robin Works

The AI service rotates through all working providers to distribute load:
1. Each request picks the next provider in rotation
2. If a provider fails or is rate-limited, it tries the next one
3. Ollama serves as the final fallback (always available locally)
4. Rate limits are tracked per-provider with cooldown periods

## Security Note

- Never paste live keys into docs, code, prompts, or test output.
- Store provider credentials only in backend `.env` or deployment environment settings.