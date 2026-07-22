# Phase 4 — AI System Audit

**Date:** 2026-07-22

## Round-robin pipeline

* `backend/ai_engine/services.py` (1,253 lines) — 11-provider
  rotation (Groq → Cerebras → Gemini → Cohere → OpenRouter ×2 →
  GitHub Models → HuggingFace → Mistral → NVIDIA Mistral → DeepSeek →
  Ollama).
* Thread-safe counter (`threading.Lock`).
* 120 s deadline, 15-20 s per provider.
* Provider-error phrases filtered (`_PROVIDER_ERROR_PHRASES`).

## Phase-3 per-question AI

* `backend/questions/ai_per_question.py` — exposes
  `concept, why_correct, why_incorrect, clinical_significance,
  memory_trick, related_pyqs, related_topics, exam_importance`.
* 24h cache per `(question_id, feature)`.
* Falls back to deterministic templates when no AI key is configured
  so demos work locally.
* Persists output to `Question.ai_explanation / ai_clinical_pearl /
  ai_mnemonic` + `QuestionAIOperationLog` audit row.

## Hallucination protection

* Prompts are short, single-shot, no chain-of-thought — limits
  hallucination surface.
* Templates are deterministic — when AI is unavailable the user
  sees a known string, never an LLM-generated fabrication.
* AI outputs are persisted but only used for display, not for
  grading or scoring.

## Evidence references

* Phase-3 `related_pyqs` only returns Question rows that already
  exist in the DB (concept_id join + token overlap fallback).
* `related_topics` aggregates `Question.topic` rows directly.

## Graceful failure

* Verified by `AIPerQuestionTestCase::test_fallback_when_no_ai_call`
  in `backend/questions/tests_phase4.py` — `concept / clinical /
  mnemonic / why_correct / why_incorrect` all return non-empty
  strings even when `_ai_call` returns `""`.

## Performance

* Each AI call costs 1 token (per-question cache means 1 token per
  question per feature, ever).
* Per-call timeout: 15-20 s (provider-specific).

## Phase-4 actions

* None — Phase-3 already added caching, fallback, persistence.

## Recommendations

* Add `LLM_ROUTING_STRATEGY=quality|cost` env to prefer the cheapest
  provider per call.
* Phase-5: route `concept` to fast/cheap provider, `why_correct` to
  quality provider.
