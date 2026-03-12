# Ollama Setup Guide

Ollama runs AI models locally on your machine. It serves as the final fallback provider in CrackCMS when cloud APIs are rate-limited or unavailable.

## Installation

### Windows
1. Download from https://ollama.com/download/windows
2. Run the installer
3. Ollama starts automatically as a background service

### macOS
```bash
brew install ollama
ollama serve  # Start the server
```

### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve  # Start the server
```

## Pull the Required Model

CrackCMS uses `llama3.2:3b` by default (small, fast, good quality):

```bash
ollama pull llama3.2:3b
```

Other recommended models:
- `llama3.2:3b` — 2GB, fast responses (default)
- `llama3.1:8b` — 5GB, better quality
- `gemma2:9b` — 5GB, good at medical topics
- `mistral:7b` — 4GB, fast general purpose

## Verify It's Running

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Test a prompt
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:3b",
  "prompt": "What is the treatment for acute pancreatitis?",
  "stream": false
}'
```

## Configuration

No API key is needed. CrackCMS connects to `http://localhost:11434` automatically.

To change the model, set the environment variable:

```env
OLLAMA_MODEL=llama3.1:8b
```

## How It Works in CrackCMS

1. Ollama is the **last fallback** in the round-robin provider chain
2. If all 7 cloud providers fail or are rate-limited, Ollama handles the request
3. Response time: ~2-10 seconds depending on model size and hardware
4. No internet required — fully offline capable

## Troubleshooting

- **"Connection refused"**: Run `ollama serve` to start the server
- **Slow responses**: Use a smaller model (`llama3.2:3b`) or ensure GPU is available
- **Out of memory**: Use `llama3.2:3b` (2GB) instead of larger models
- **Model not found**: Run `ollama pull llama3.2:3b` to download it
