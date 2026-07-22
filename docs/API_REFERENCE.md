# API Reference

> Every API endpoint in CrackCMS — purpose, authentication, permissions, request/response, status codes, error responses, examples.

---

## Conventions

- **Base URL**: `https://crackcms-vsthc.ondigitalocean.app/api` (production), `http://localhost:8000/api` (dev). The legacy Render URL `https://crackcms-backend.onrender.com/api` is intentionally blacklisted as unhealthy in `frontend/src/lib/api.ts`.
- **Content-Type**: `application/json` for all write requests.
- **Authentication header**: `Authorization: Bearer <token>` (Supabase access token preferred; Django JWT accepted).
- **Session header**: `X-Session-ID: <crack_device_id>` (auto-injected by `frontend/src/lib/api.ts`).
- **Timestamps**: ISO 8601 UTC.
- **All write endpoints** require either JWT or Supabase session.
- **Pagination**: page-based, query params `?page=1&page_size=20` (defaults vary per endpoint).

### Standard Error Response

```json
{
  "error": "human-readable message",
  "code": "machine_readable_code",
  "detail": {}
}
```

### Common status codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 204 | No content |
| 400 | Validation error |
| 401 | Unauthenticated / invalid token |
| 402 | Insufficient tokens (AI endpoints) |
| 403 | Forbidden (permission denied) |
| 404 | Not found |
| 409 | Conflict (duplicate) |
| 429 | Rate-limited (django-axes / provider quota) |
| 500 | Internal server error |
| 502 / 503 / 504 | Backend / AI provider unavailable (frontend failover) |

---

## Auth endpoints — `/api/auth/`

### `POST /api/auth/register/`
**Auth**: none. **Permission**: public.

Request:
```json
{
  "username": "student42",
  "email": "student42@example.com",
  "password": "StrongP@ssw0rd!",
  "phone": "9876543210",
  "college": "AIIMS Delhi",
  "target_exam": "UPSC CMS",
  "target_year": 2026
}
```
Response `201`:
```json
{
  "user": {
    "id": 42,
    "username": "student42",
    "email": "student42@example.com",
    "role": "student",
    "is_subscribed": false
  },
  "access": "<jwt_access>",
  "refresh": "<jwt_refresh>"
}
```
Errors: `400` weak password, `409` duplicate username/email.

---

### `POST /api/auth/login/`
**Auth**: none.

Request:
```json
{ "username": "student42", "password": "StrongP@ssw0rd!" }
```
Response `200`:
```json
{
  "access": "<jwt_access>",
  "refresh": "<jwt_refresh>",
  "user": { "id": 42, "username": "student42", "role": "student", "is_subscribed": false }
}
```
Errors: `401` invalid credentials, `403` blocked by `django-axes` lockout.

---

### `GET /api/auth/profile/`
**Auth**: required. **Permission**: authenticated user.

Response `200`:
```json
{
  "id": 42,
  "username": "student42",
  "email": "student42@example.com",
  "role": "student",
  "phone": "9876543210",
  "college": "AIIMS Delhi",
  "target_exam": "UPSC CMS",
  "target_year": 2026,
  "active_exam_track": 1,
  "is_subscribed": false,
  "avatar_url": "https://..."
}
```

### `PUT / PATCH /api/auth/profile/`
**Auth**: required.

Partial update (PATCH) example:
```json
{ "college": "AIIMS Bhubaneswar", "target_year": 2027 }
```
Response `200`: updated user.

---

### `POST /api/auth/verify-scholarship/`
**Auth**: none.
Request: `{ "answers": { "1": "B", "2": "A", ... } }`
Response `200`: `{ "passed": true, "granted_price": 199 }`

---

### `POST /api/auth/password-reset/`
**Auth**: none.
Request: `{ "email": "student42@example.com" }`
Response `200`: `{ "message": "If an account with that email exists, a reset link has been sent." }` (always generic to prevent enumeration).

### `POST /api/auth/password-reset/confirm/`
**Auth**: none.
Request: `{ "uid": "MTI", "token": "<one-time>", "new_password": "NewP@ssw0rd!" }`
Response `200`: `{ "message": "Password has been reset successfully." }`

---

### Device Management

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/devices/` | List active devices for current user |
| POST | `/api/auth/devices/logout/` | Force-logout `{ "device_id": 7 }` |

---

### Token System

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/` | Returns balance breakdown (free remaining, purchased, feedback) |
| POST | `/api/auth/tokens/purchase/` | `{ "amount": 50, "payment_id": "rzp_..." }` |
| GET | `/api/auth/tokens/history/` | Paginated `TokenTransaction` rows |

### Admin Token Management (superuser only)

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/admin/users/` | All users + balances |
| POST | `/api/auth/tokens/admin/grant/` | `{ "user_id": 42, "amount": 100, "note": "scholarship" }` |
| POST | `/api/auth/tokens/admin/transfer/` | `{ "from_user_id": 1, "to_user_id": 42, "amount": 10, "note": "..." }` |
| GET | `/api/auth/tokens/admin/audit-logs/` | Paginated `AdminAuditLog` |

---

### Admin User Lifecycle (superuser only)

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/admin/users/` | Paginated users (filters: `?role=&is_blocked=&search=`) |
| PATCH | `/api/auth/admin/users/<id>/block/` | `{ "blocked": true, "reason": "..." }` |
| PATCH | `/api/auth/admin/users/<id>/role/` | `{ "role": "admin" }` |
| POST | `/api/auth/admin/users/<id>/reset-progress/` | Wipes attempts/analytics |
| POST | `/api/auth/admin/system/reset-attempts/` | `{ "scope": "all" }` or `{"scope": "user","user_id":42}` |
| POST | `/api/auth/admin/system/clear-analytics/` | same shape |
| POST | `/api/auth/admin/system/rerun-evaluation/` | re-run score prediction |
| POST | `/api/auth/admin/system/backup-data/` | Returns backup file URL |
| POST | `/api/auth/admin/system/restore-data/` | `{ "backup_id": "..." }` |
| PATCH | `/api/auth/admin/users/<id>/subscription/` | `{ "plan": "admin_grant" }` |
| GET | `/api/auth/admin/users/<id>/devices/` | List target user's devices |
| GET | `/api/auth/admin/payments/` | All payment attempts |

---

### Subscription

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/subscribe/order/` | `{ "plan": "1_month" }` → `{ "order_id": "...", "amount": 199, "currency": "INR" }` |
| POST | `/api/auth/subscribe/verify/` | `{ "razorpay_payment_id", "razorpay_order_id", "razorpay_signature" }` |
| POST | `/api/auth/subscribe/webhook/` | Razorpay webhook (server-to-server) |
| GET | `/api/auth/subscribe/status/` | `{ "active": true, "plan": "1_month", "expires_at": "..." }` |

---

## Question endpoints — `/api/questions/`

### `GET /api/questions/exam-tracks/`
Response: `[ { "id": 1, "name": "UPSC CMS", "code": "UPSC_CMS", "is_active": true }, ... ]`

### `GET /api/questions/subjects/`
Query: `?exam_track=1`
Response: list of `Subject` objects.

### `GET /api/questions/topics/`
Query: `?subject=1&parent=2`
Response: hierarchical list.

### `GET /api/questions/`
**Auth**: required for full data; public for preview.
Query params: `?subject=1&topic=5&year=2022&difficulty=medium&is_active=true&search=&page=1&page_size=20`

Response `200`:
```json
{
  "count": 1966,
  "next": "?page=2",
  "previous": null,
  "results": [
    {
      "id": 35,
      "question_text": "Characteristic feature of upper motor neuron lesion",
      "option_a": "Fasciculations",
      "option_b": "Hypotonia",
      "option_c": "Clonus",
      "option_d": "Atrophy",
      "correct_answer": "C",
      "year": 2018,
      "subject": 1,
      "topic": 5,
      "difficulty": "medium",
      "explanation": "Clonus is characteristic of UMN lesions...",
      "mnemonic": "C-Clonus, L-Loss of inhibition...",
      "high_yield_points": ["Fact 1", "Fact 2"],
      "textbook_reference": "Harrison's Ch. 15",
      "concept_tags": ["Neurology", "UMN Lesion"],
      "is_active": true
    }
  ]
}
```

### `GET /api/questions/<id>/`
Single question detail.

### `POST /api/questions/<id>/bookmark/`
**Auth**: required. Toggle bookmark.
Response `200`: `{ "bookmarked": true }` or `{ "bookmarked": false }`.

### `POST /api/questions/<id>/attempt/`
**Auth**: required. Record an attempt.
Request: `{ "selected_answer": "C" }`
Response `200`: `{ "is_correct": true, "correct_answer": "C" }`

### `GET /api/questions/bookmarks/`
List current user's bookmarked questions.

### `GET /api/questions/years/`
List years that have questions, with counts.

### `GET /api/questions/stats/`
Overall question-bank stats.

### `POST /api/questions/upload/`
**Auth**: admin. Bulk upload array of question objects.

### `POST /api/questions/import-preview/`
**Auth**: admin. Preview a CSV/JSON/Word import before applying.

### `PATCH /api/questions/bulk-metadata/`
**Auth**: admin. Update metadata for many questions at once.

### `POST /api/questions/bulk-delete/`
**Auth**: admin. Bulk delete.

### `POST /api/questions/extraction/upload/`
**Auth**: admin. Upload a PDF/Word file for question extraction.

### `GET /api/questions/extraction/jobs/`
**Auth**: admin. List extraction jobs.

### `GET /api/questions/extraction/jobs/<job_id>/items/`
**Auth**: admin. Items of a specific extraction job.

### `PATCH /api/questions/extraction/items/<item_id>/`
**Auth**: admin. Update a single extracted item.

### `POST /api/questions/extraction/items/<item_id>/autotag/`
**Auth**: admin. AI auto-tag an item.

### `POST /api/questions/extraction/items/<item_id>/approve/`
**Auth**: admin. Approve item → draft Question.

### `POST /api/questions/extraction/items/<item_id>/reject/`
**Auth**: admin. Reject item.

### `POST /api/questions/extraction/items/<item_id>/publish/`
**Auth**: admin. Publish approved item to question bank.

### `POST /api/questions/extraction/jobs/<job_id>/retry/`
**Auth**: admin. Retry a failed extraction.

### `POST /api/questions/<id>/generate-video/`
**Auth**: admin. Trigger AI video generation for a question.

### `POST /api/questions/<id>/similar/`
**Auth**: optional. Find similar questions via RAG.

### `PATCH /api/questions/<id>/verify/`
**Auth**: admin. Mark question verified.

### `PATCH /api/questions/<id>/unverify/`
**Auth**: admin. Unverify question.

### `PATCH /api/questions/<id>/ai-override/`
**Auth**: admin. Override AI-generated fields (`admin_answer_override`, `admin_explanation_override`, `admin_mnemonic_override`).

### `PATCH /api/questions/<id>/ai-lock/`
**Auth**: admin. Lock fields from AI regeneration (`lock_answer`, `lock_explanation`).

### `POST /api/questions/<id>/force-regenerate/`
**Auth**: admin. Force AI regeneration.

### `GET | POST /api/questions/ai-prompt-versions/`
**Auth**: admin. List / create prompt versions.

### `POST /api/questions/ai-prompt-versions/<version_id>/activate/`
**Auth**: admin. Activate a prompt version.

### `GET /api/questions/<id>/ai-timeline/`
**Auth**: admin. View AI operation history for a question.

### `POST /api/questions/<id>/duplicate/`
**Auth**: admin. Duplicate a question.

### `PATCH /api/questions/<id>/related-pyqs/`
**Auth**: admin. Set related PYQ links.

### `PATCH /api/questions/<id>/concept-id/`
**Auth**: admin. Set stable concept ID for linking.

### `PATCH /api/questions/<id>/reference/`
**Auth**: admin. Update textbook reference.

### `PATCH /api/questions/<id>/format-fix/`
**Auth**: admin. Fix formatting issues.

### `PATCH /api/questions/<id>/archive/`
**Auth**: admin. Archive a question.

### `PATCH /api/questions/<id>/unarchive/`
**Auth**: admin. Unarchive.

### `GET /api/questions/<id>/revisions/`
**Auth**: admin. List revision snapshots.

### `GET /api/questions/<id>/revisions-diff/`
**Auth**: admin. Diff between revisions.

### `POST /api/questions/<id>/undo-last-revision/`
**Auth**: admin. Roll back last revision.

### `POST /api/questions/<id>/resolve-dispute/`
**Auth**: admin. Mark dispute as resolved.

### `POST /api/questions/<id>/report/`
**Auth**: required.
Request: `{ "feedback_type": "wrong_answer", "description": "..." }`
Response `201`: `{ "id": 12, "status": "pending" }`.

---

### Flashcards

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/flashcards/` | List current user's flashcards; `?due=true` filters to due-only |
| POST | `/api/questions/flashcards/` | `{ "question_id": 35, "ease_factor": 2.5 }` |
| GET | `/api/questions/flashcards/<id>/` | Detail |
| PUT / DELETE | `/api/questions/flashcards/<id>/` | Update / delete |
| POST | `/api/questions/flashcards/<id>/review/` | `{ "quality": 4 }` → SM-2 update |
| GET | `/api/questions/flashcards/analytics/` | `{ "total_cards": 100, "due_today": 12, "retention_7d": 0.83 }` |

---

### Notes

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/notes/` | List current user's notes; `?question=35` |
| POST | `/api/questions/notes/` | `{ "question_id": 35, "body": "UMN lesions show ↑tone, ↑reflexes, +Babinski" }` |
| GET / PUT / DELETE | `/api/questions/notes/<id>/` | Detail |

---

### Discussions

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/discussions/` | List; `?question=35` |
| POST | `/api/questions/discussions/` | `{ "question_id": 35, "content": "...", "parent_id": null }` |
| GET | `/api/questions/discussions/<id>/replies/` | Thread |
| POST | `/api/questions/discussions/<id>/replies/` | Reply |
| POST | `/api/questions/discussions/<id>/vote/` | `{ "value": 1 }` (upvote) or `{ "value": -1 }` |

---

### Chat Assistant (Question Bank)

| Method | Path | Description |
|---|---|---|
| POST | `/api/questions/chat/` | `{ "message": "Explain UMN vs LMN", "question_id": 35 }` → token-metered AI response |

---

## Test endpoints — `/api/tests/`

### `GET /api/tests/`
List tests; `?exam_track=1&is_adaptive=true&is_pyq_simulator=true`.

### `POST /api/tests/`
**Auth**: required.
Request:
```json
{
  "title": "Cardiology Practice Set 1",
  "subject": 1,
  "num_questions": 20,
  "time_limit_minutes": 30,
  "difficulty": "medium",
  "year": 2023,
  "is_adaptive": false
}
```

### `GET /api/tests/<id>/`
Test detail + selected questions.

### `POST /api/tests/<id>/submit/`
**Auth**: required.
Request:
```json
{
  "responses": [
    { "question_id": 35, "selected_answer": "C", "time_taken_seconds": 42 },
    { "question_id": 36, "selected_answer": "A", "time_taken_seconds": 21 }
  ]
}
```
Response `200`:
```json
{
  "attempt_id": 99,
  "score": 17,
  "total": 20,
  "accuracy": 0.85,
  "negative_marking_applied": false,
  "results": [
    { "question_id": 35, "is_correct": true, "selected_answer": "C", "correct_answer": "C", "explanation": "..." }
  ]
}
```

### `GET /api/tests/<id>/review/`
Returns full review with explanations.

### `GET /api/tests/attempts/`
List current user's attempts.

---

## Analytics endpoints — `/api/analytics/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/dashboard/` | Aggregate stats: streak, total questions, accuracy |
| GET | `/api/analytics/topic-performance/` | Per-topic mastery; `?topic=5` |
| GET | `/api/analytics/heatmap/` | 365-day daily activity heatmap |
| GET | `/api/analytics/recent-attempts/` | Last 20 attempts |
| GET | `/api/analytics/score-prediction/` | ML/predictive score estimate |
| GET | `/api/analytics/performance-trend/` | Weekly trend line |
| GET | `/api/analytics/weak-topics/` | Topics with accuracy < threshold |
| GET | `/api/analytics/roadmap/` | AI-generated personalized roadmap |
| GET | `/api/analytics/streak/` | Current streak + longest |
| GET | `/api/analytics/badges/` | Earned badges + locked badges |
| GET | `/api/analytics/leaderboard/` | Global ranking; `?period=weekly` |

### Feedback & Contact

| Method | Path | Description |
|---|---|---|
| GET / POST | `/api/analytics/feedback/` | List / submit feedback |
| GET / PATCH / DELETE | `/api/analytics/feedback/<id>/` | Detail |
| POST | `/api/analytics/contact/` | `{ "name", "email", "message" }` |
| GET | `/api/analytics/export/` | JSON dump (Google Sheets import) |
| GET | `/api/analytics/export/csv/` | CSV download |

### Announcements

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/announcements/` | List active |
| GET | `/api/analytics/announcements/<id>/` | Detail |

### Admin (superuser)

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/admin-dashboard/` | Cross-user aggregate |
| POST | `/api/analytics/admin/weak-area-control/` | Adjust weak-topic thresholds |
| GET / POST | `/api/analytics/admin/campaigns/` | List / create campaigns |
| POST | `/api/analytics/admin/campaigns/<id>/send-now/` | Trigger send |

---

## AI endpoints — `/api/ai/`

All endpoints below are **token-metered** (1 token per call) unless noted.

### Core AI

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/api/ai/tutor/` | `{ "query": "...", "session_id": null }` | RAG-enhanced chat tutoring |
| POST | `/api/ai/explain/` | `{ "topic": "...", "depth": "beginner\|intermediate\|advanced" }` | Concept explainer |
| POST | `/api/ai/mnemonic/` | `{ "topic": "cranial nerves" }` | Generate mnemonic |
| POST | `/api/ai/analyze/` | `{ "question_id": 35 }` | Analyze question structure |
| POST | `/api/ai/explain-answer/` | `{ "question_id": 35, "selected_answer": "C" }` | Rich JSON explanation |
| POST | `/api/ai/generate-questions/` | `{ "topic": "..." , "count": 5, "difficulty": "medium" }` | AI MCQ generator |
| POST | `/api/ai/study-plan/` | `{ "weak_topic_ids": [1,2,3] }` | Personalized plan |
| GET | `/api/ai/high-yield/` | `?exam_track=1` | High-yield topics list |

### RAG

| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/rag-search/` | `{ "query": "DKA management" }` → top-K chunks (not token-metered) |
| POST | `/api/ai/rag-answer/` | `{ "query": "..." }` → RAG-grounded answer (token-metered) |
| POST | `/api/ai/textbook-reference/` | `{ "question_id": 35 }` → textbook citation |
| GET | `/api/ai/screenshot/<question_id>/` | PNG of textbook page |

### Knowledge base management

| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/knowledge/upload/` | multipart file upload |
| POST | `/api/ai/knowledge/scan/` | Trigger scan + reindex of `Medura_Train/` |
| GET | `/api/ai/knowledge/stats/` | `{ "chunks": 4972, "sources": 79 }` |

### Status / Test

| Method | Path | Description |
|---|---|---|
| GET | `/api/ai/status/` | `{ "providers": [{"name":"groq","healthy":true},...], "current_index": 3 }` |
| GET | `/api/ai/test/` | Quick smoke test (1 token) |

### Chat history

| Method | Path | Description |
|---|---|---|
| GET / POST | `/api/ai/chat/sessions/` | List / create session |
| GET | `/api/ai/chat/sessions/<id>/` | Detail |
| GET | `/api/ai/chat/sessions/<id>/messages/` | List messages |
| POST | `/api/ai/chat/sessions/<id>/messages/add/` | Add message (token-metered) |

### Feedback

| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/feedback/` | `{ "message_id": 12, "feedback_type": "accurate\|inaccurate\|harmful", "comment": "..." }` — verified feedback awards +2 tokens |

---

## Textbook endpoints — `/api/textbooks/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/textbooks/books/` | List indexed textbooks |
| GET | `/api/textbooks/books/<id>/` | Detail with chapters |
| POST | `/api/textbooks/uploads/` | multipart PDF upload (admin) |

---

## Resource endpoints — `/api/resources/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/resources/catalog/` | Resource catalog |
| GET | `/api/resources/download/<resource_id>/` | Returns signed download URL |
| GET | `/api/resources/exam-guide/` | Returns exam-guide JSON |

---

## Job endpoints — `/api/jobs/`

| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs/` | List jobs; `?category=1&is_active=true` |
| GET | `/api/jobs/<id>/` | Job detail |
| POST | `/api/jobs/<id>/bookmark/` | Toggle bookmark (auth required) |
| GET | `/api/jobs/categories/` | List categories |

---

## Health endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/` | `{ "status": "ok" }` |
| GET | `/api/` | API root index |
| GET | `/sentry-debug/` | Triggers a test exception (gated to dev only) |

---

## Authentication Examples

### Django JWT (fallback)

```bash
curl -X POST https://crackcms-vsthc.ondigitalocean.app/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"student42","password":"StrongP@ssw0rd!"}'
# {"access":"eyJ...","refresh":"eyJ..."}

curl https://crackcms-vsthc.ondigitalocean.app/api/auth/profile/ \
  -H "Authorization: Bearer eyJ..."
```

### Supabase (preferred)

Frontend `api.ts` interceptor automatically attaches `Authorization: Bearer <supabase_access_token>`.

### X-Session-ID

`api.ts` generates and sends a per-browser fingerprint:

```bash
curl https://crackcms-vsthc.ondigitalocean.app/api/questions/ \
  -H "Authorization: Bearer <token>" \
  -H "X-Session-ID: dev_a1b2c3d4_1719900000"
```

---

## Error Code Reference

| Code | When |
|---|---|
| `session_invalid` | Single-device session check failed — frontend clears session and redirects |
| `insufficient_tokens` | Token balance < 1 — frontend prompts to `/tokens` |
| `ai_provider_exhausted` | All 11 providers + Ollama failed — returns 503 |
| `quiz_in_progress` | User tried to start a second test while one is `in_progress` |
| `subscription_required` | Feature gated to paid users |
| `admin_required` | Non-admin attempted admin endpoint |

See [`AUTHENTICATION.md`](./AUTHENTICATION.md) for the auth flow; [`ADMIN_SYSTEM.md`](./ADMIN_SYSTEM.md) for admin-only endpoints.
