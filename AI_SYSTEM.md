# CrackCMS — AI System Documentation

## AI Providers

CrackCMS uses 7 AI providers in a round-robin rotation, each with a 60-second timeout:

| # | Provider | Model | Endpoint |
|---|----------|-------|----------|
| 1 | Groq | llama-3.3-70b-versatile | api.groq.com |
| 2 | Cerebras | llama-3.3-70b | api.cerebras.ai |
| 3 | Gemini | gemini-2.0-flash | generativelanguage.googleapis.com |
| 4 | GitHub Models | gpt-4o-mini | models.inference.ai.azure.com |
| 5 | OpenRouter | various | openrouter.ai |
| 6 | Cohere | command-a-03-2025 | api.cohere.com |
| 7 | DeepSeek | deepseek-chat | api.deepseek.com |
| fallback | Ollama | llama3.2 | localhost:11434 |

### Provider Selection

```python
provider_index = hash(question_text) % len(providers)  # deterministic
# On failure: tries next provider in sequence
# All 7 fail: falls back to Ollama (local)
```

## Explain After Answer

Primary AI feature — generates rich explanations after a user answers a question.

### Prompt Structure

```
You are a UPSC CMS medical exam expert tutor.
A student just answered a question. Provide a detailed explanation.

Question: {question_text}
Options: A) ... B) ... C) ... D) ...
Student's Answer: {user_answer}
Correct Answer: {correct_answer}

Respond in JSON:
{
  "is_correct": bool,
  "correct_answer": str,
  "why_correct": str (3-4 sentences, textbook-referenced),
  "why_others_wrong": {"A": str, "B": str, "C": str, "D": str},
  "mnemonic": str (optional memory aid),
  "high_yield_points": [str] (2-3 exam-relevant facts),
  "similar_topics": [str] (related topics to review),
  "textbook_reference": str (standard textbook + chapter)
}
```

### Caching

- Cache key: MD5 of `question_text[:200] + correct_answer`
- TTL: 24 hours (86400 seconds)
- Backend: Redis if `REDIS_URL` set, else Django LocMemCache
- Same question + answer combination returns cached result instantly

### Quality Scoring

Each AI explanation is scored 0.0–1.0 based on:

| Criterion | Weight | Check |
|-----------|--------|-------|
| Why Correct depth | 0.25 | `len(why_correct) > 50` |
| Textbook reference | 0.25 | Non-empty textbook_reference |
| Mnemonic | 0.15 | Non-empty mnemonic |
| High-yield points | 0.20 | Has at least 1 point |
| Answer consistency | 0.15 | `correct_answer == expected_answer` |

## Multi-Model Voting (Enrichment)

Used during batch question enrichment to determine correct answers with consensus.

### Process

1. Same question sent to 3 providers: Groq, Cerebras, GitHub Models
2. Each provider returns a single-letter answer (A/B/C/D)
3. `Counter` majority vote — answer needs ≥2/3 agreement
4. If no majority, returns `None` (question flagged for manual review)

### Prompt

```
Answer this medical MCQ with ONLY the letter (A, B, C, or D):
{question_text}
A) {option_a}  B) {option_b}  C) {option_c}  D) {option_d}
```

## RAG Pipeline

### Architecture

```
User Query → TF-IDF Vectorizer → SQLite RAG Store →
  Top-K Chunks (similarity ≥ threshold) →
    Context Injection into AI Prompt →
      Grounded Response
```

### Data Sources

- **Textbooks**: Harrison's, Robbins, Guyton, etc. (~79 sources)
- **PYQ Papers**: Previous year question papers
- **Web Knowledge**: Scraped medical content

### Storage

- **Primary**: SQLite-based TF-IDF (`chroma_db/rag_store.sqlite3`)
  - 4972+ text chunks
  - Custom TF-IDF vectorizer with cosine similarity
- **Secondary**: ChromaDB (`chroma_db/chroma.sqlite3`)
  - Available for embedding-based search
  - Not used in default pipeline

### Chunk Strategy

- Documents split into overlapping chunks (~500 tokens, 100-token overlap)
- Each chunk tagged with source, page, subject

## Token Economy

| Token Type | Allocation | Expiry |
|-----------|-----------|--------|
| Daily Free | 10/day | Midnight reset |
| Weekly Free | 50/week | Sunday reset |
| Purchased | Configurable | Never |
| Feedback Reward | 2 per feedback | Never |

- Each AI explanation costs 1 token
- Admin users bypass token checks
- `TokenConfig` singleton controls all limits

## AI Tutor

Interactive chat-like interface for:
- Topic explanations
- Study plan generation
- Concept clarification
- Differential diagnosis practice

Uses the same provider rotation but with a tutor-specific system prompt.
