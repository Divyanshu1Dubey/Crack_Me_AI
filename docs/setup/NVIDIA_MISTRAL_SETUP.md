# NVIDIA Mistral Integration

This document describes how to integrate NVIDIA's Mistral 7B model via the NVIDIA API platform.

## Overview

Your CrackCMS backend now supports **NVIDIA's Mistral 7B Instruct** model via the NVIDIA API integration platform. This adds another robust AI provider to your 11-provider load-balanced system.

### Key Details

- **Provider**: NVIDIA API Platform (Mistral integration)
- **Model**: `mistralai/mistral-7b-instruct-v0.2`
- **API Base URL**: `https://integrate.api.nvidia.com/v1`
- **Latency**: Fast inference (NVIDIA GPU-optimized)
- **Cost**: Free tier available (check NVIDIA docs for rate limits)

## Setup Steps

### 1. Get Your NVIDIA API Key

1. Visit: https://build.nvidia.com/
2. Sign in or create an account
3. Navigate to the API keys section
4. Generate a new API key for the **NIM (NVIDIA Inference Microservices)** platform
5. Copy the key (format: `nvapi-...`)

### 2. **IMPORTANT: Store the Key Securely**

⚠️ **NEVER commit API keys to source code or git.**

Instead, add it to your `.env` file (backend directory):

```bash
# backend/.env (git-ignored)
NVIDIA_MISTRAL_API_KEY=nvapi-YOUR-NEW-KEY-HERE
```

Or set as an environment variable in your production deployment environment:

```bash
# Render.com, Docker, or other platforms
export NVIDIA_MISTRAL_API_KEY="nvapi-YOUR-KEY"
```

### 3. Verify Configuration

The backend will auto-detect the key and initialize the NVIDIA Mistral provider on startup. Check logs:

```bash
cd backend
python manage.py shell

from ai_engine.services import AIService
ai = AIService()
print("NVIDIA Mistral initialized:", ai.nvidia_mistral is not None)
```

Expected output:
```
✅ NVIDIA Mistral AI initialized
NVIDIA Mistral initialized: True
```

## Usage

The NVIDIA Mistral provider integrates automatically into your AI service's round-robin load balancing. When you call any AI endpoint, the system may route to NVIDIA Mistral based on availability and provider health.

### Direct Usage (Advanced)

```python
from ai_engine.services import AIService

ai = AIService()

# Direct call to NVIDIA Mistral
response = ai._call_nvidia_mistral(
    prompt="Explain diabetic ketoacidosis pathophysiology",
    system="You are an expert UPSC CMS tutor.",
    temperature=0.5,
    max_tokens=1024
)
print(response)
```

### Via Standard AI Endpoint

```python
# Via your existing AI endpoint (uses round-robin load balancing)
response = ai.call_ai(
    prompt="What is the management of myocardial infarction?",
    system="You are an UPSC CMS expert.",
)
# System may use NVIDIA Mistral, Groq, Cerebras, or another provider
```

## Provider Registry

Your backend now orchestrates **11 AI providers**:

1. ✅ Groq (Llama 3.3 70B)
2. ✅ Cerebras (Llama 3.1 8B)
3. ✅ Google Gemini (Flash 2.0)
4. ✅ Cohere (Command-A)
5. ✅ OpenRouter (free models)
6. ✅ OpenRouter2 (second key)
7. ✅ GitHub Models (Llama, Phi)
8. ✅ HuggingFace (Llama 3.3)
9. ✅ Mistral Native (mistral-small)
10. ✅ **NVIDIA Mistral** (Mistral 7B) ← NEW
11. ✅ DeepSeek (paid, pay-as-you-go)

## Testing

Run the backend test suite to verify all providers (including NVIDIA) initialize successfully:


```bash
cd backend
python manage.py test ai_engine
# or
pytest tests_engine/ -v
```

Check the test output for:
```
✅ NVIDIA Mistral AI initialized
```

## Troubleshooting

### "NVIDIA Mistral init failed: ModuleNotFoundError: No module named 'openai'"

**Fix**: Install the OpenAI SDK (should already be in requirements.txt):
```bash
pip install openai
```

### "NVIDIA Mistral API key invalid — skipping"

**Fix**: Verify your API key:
1. Check it starts with `nvapi-`
2. Confirm it's set in your `.env` file: `NVIDIA_MISTRAL_API_KEY=nvapi-...`
3. Regenerate the key at https://build.nvidia.com/ if needed

### Rate limit errors ("429")

**Fix**: NVIDIA API has rate limits. The backend automatically falls back to other providers. Monitor logs:
```bash
tail -f backend.log | grep -i nvidia
```

## Performance Notes

- **First call latency**: ~500ms-2s (NVIDIA GPU cold start)
- **Subsequent calls**: ~100-500ms
- **Token throughput**: 50-200 tokens/second on free tier
- **Load balancing**: Automatically distributes load across 11 providers

## Code References

- **Settings**: [backend/crack_cms/settings.py](backend/crack_cms/settings.py) (line `NVIDIA_MISTRAL_API_KEY`)
- **Service**: [backend/ai_engine/services.py](backend/ai_engine/services.py) (methods: `_init_clients()`, `_call_nvidia_mistral()`)
- **Config**: [backend/.env.example](backend/.env.example)

## Further Reading

- NVIDIA Build Platform: https://build.nvidia.com/
- NVIDIA API Docs: https://docs.nvidia.com/nim/
- Mistral Model Details: https://docs.mistral.ai/capabilities/function_calling/
