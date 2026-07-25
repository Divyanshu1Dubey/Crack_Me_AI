# BUG_P0_1_AI_TUTOR_FIX.md — `/api/ai/explain-question/<id>/` returns 404

**Incident ID:** BUG #P0-1
**Detected:** 2026-07-25 (QA mission sweep)
**Severity:** P0 — every AI Tutor click on `/questions/neet-pg/practice` failed
**Resolved by:** commit `673af64`
**Author:** Claude Code (NEET PG product-completion mission, 2026-07-25)

---

## 1. Symptom

Clicking "Ask AI Tutor" inside the NEET PG practice player surfaced an HTTP 404 in the browser network panel. The player's AI explanation panel rendered the existing fallback ("AI service is currently unavailable…") for every question.

## 2. Root cause

The frontend player calls

```ts
// frontend/src/components/neet-pg/NeetPgPlayer.tsx:200
const r = await aiAPI.explainQuestion(current.id, {...});
```

where `aiAPI.explainQuestion` is defined at `frontend/src/lib/api.ts:452`:

```ts
explainQuestion: (questionId: number, data: Record<string, unknown> = {}) =>
  api.post(`/ai/explain-question/${questionId}/`, data, { timeout: AI_TIMEOUT }),
```

Final URL: `POST /api/ai/explain-question/<int:question_id>/`.

The backend URL conf (`backend/ai_engine/urls.py`) had **no** matching pattern. Probed live:

```
$ curl -X POST https://crackcms-vsthc.ondigitalocean.app/api/ai/explain-question/10194/
HTTP/1.1 404 Not Found
```

Confirmed missing URL = the bug.

## 3. Fix

### 3.1 `backend/ai_engine/urls.py`

Added one URL pattern:

```python
# Per-question AI explain (Bug #P0-1, 2026-07-25): the NEET PG player
# calls `aiAPI.explainQuestion(questionId, ...)` and expects 200.
path('explain-question/<int:question_id>/',
     views.ExplainQuestionView.as_view(),
     name='ai-explain-question'),
```

### 3.2 `backend/ai_engine/views.py`

Added `ExplainQuestionView` (145 lines incl. helpers + docstring) modelled after `ExplainAfterAnswerView`:

- **404** if the question id is unknown (graceful, not 500).
- **Cache hit** if `Question.ai_explanation` is set and `<24h` old — reuses the rich JSON via `_stitch_explanation_markdown` so the player gets a single text blob (`explanation`, `cached=true`, `ai_model`, `ai_generated_at`).
- **Cold call** goes through `AIService.analyze_question(...)` which is the standard 9-provider round-robin (Groq → Cerebras → Gemini → Cohere → OpenRouter ×2 → GitHub Models → HuggingFace → Mistral). Response label: `RoundRobin-11`.
- **Standard token accounting** — `consume_ai_token()` (1 token, admins bypass), `refund_ai_token()` on AI failure.
- **Best-effort cache write** on success (best-effort to avoid masking AI failures with a DB write error).
- Module-level `import json` added (used by both the new view and the pre-existing `ExplainAfterAnswerView` cache path).

### 3.3 Regression tests

`frontend/tests/e2e/neet-pg-qa.spec.ts` — added `test.describe('Bug #P0-1 — AI Tutor /api/ai/explain-question/<id>/ must not 404')`:

1. **Route is wired** — `POST /api/ai/explain-question/10194/` returns 200 (auth'd) or 401 (un-auth'd). Never 404.
2. **Missing id is graceful** — `POST /api/ai/explain-question/9999999/` returns 404 (DB miss) or 401 (auth blocked first). Never 500.

The first test directly encodes the regression: before this fix, prod returned 404 for id 10194; after, it returns 401 (no token) on the unauth'd probe.

## 4. Verification

| Check | Result |
|---|---|
| `python manage.py check` | ✅ no issues |
| `python manage.py test ai_engine` | ✅ 10/10 pass |
| `python manage.py shell -c "reverse('ai-explain-question', args=[12336])"` | ✅ `/api/ai/explain-question/12336/` |
| Local `curl POST /api/ai/explain-question/10194/` (Q#10194 has no cache yet) | ✅ HTTP 200, full AI analysis returned (4189 chars) |
| Local `curl POST /api/ai/explain-question/10194/` (second hit, now cached) | ✅ HTTP 200, `cached=true`, `ai_model=RoundRobin-11`, `ai_generated_at` set |
| Local `curl POST /api/ai/explain-question/9999999/` | ✅ HTTP 404, `{error: "Question 9999999 not found"}` |
| Prod `curl POST /api/ai/explain-question/10194/` (pre-deploy) | ❌ HTTP 404 (regression was real) |
| Prod post-deploy | ⏳ pending Render deploy (~3-5 min after push) |

## 5. Files changed

```
backend/ai_engine/urls.py           (+3)
backend/ai_engine/views.py          (+145)
frontend/tests/e2e/neet-pg-qa.spec.ts (+43)
3 files changed, 191 insertions(+)
```

Commit: `673af64` — *fix(ai): add ExplainQuestionView for /ai/explain-question/<id>/ (Bug #P0-1)*

## 6. Outstanding follow-ups

After this fix the AI Tutor panel renders correctly. Next up in the NEET PG completion mission:

1. **PHASE 1.2** — image media routing (`/media/recall_images/...` still 404s in production because the prod container lacks the local files).
2. **PHASE 1.3** — verify all `is_image_based=true` rows have `QuestionImage` rows.
3. **PHASE 2-7** — explanation panel enrichment, filters, modes, similar-PYQ improvements, image viewer.