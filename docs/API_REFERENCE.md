# API Reference

> Every API endpoint in CrackCMS — purpose, authentication, permissions, request/response, status codes, error responses, examples.

---

## Conventions

- **Base URL**: `https://crackcms-vsthc.ondigitalocean.app/api` (production), `http://localhost:8000/api` (dev). The legacy Render URL `https://crackcms-backend.onrender.com/api` is intentionally blacklisted as unhealthy in `frontend/src/lib/api.ts`.
- **Content-Type**: `application/json` for all write requests.
- **Authentication header**: `Authorization: Bearer <token>` (Supabase access token preferred; Django JWT accepted).
- **Session header**: `X-Session-ID: <crack_device_id>` (auto-injected by `frontend/src/lib/api.ts`). It identifies the device for the device limit (2 devices on a free plan, 4 with a subscription; see [`AUTHENTICATION.md`](./AUTHENTICATION.md) §6).
- **Timestamps**: ISO 8601 UTC.
- **All write endpoints** require either JWT or Supabase session.
- **Pagination**: page-based, `?page=1&page_size=20`. The project default (`crack_cms.pagination.StandardResultsSetPagination`) is 20 rows per page, `?page_size=` up to 100, response `{count, next, previous, results}`. Endpoints that return a plain array or their own page shape say so below.

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
| 401 | Unauthenticated / invalid token; also the sign-in codes `account_blocked`, `email_not_confirmed`, `email_required`, `account_link_required`, `device_inactive`, `device_limit_reached` (see [Error Code Reference](#error-code-reference)) |
| 402 | Paywall: `{ "code": "upgrade_required", "feature": "...", "message": "..." }` for content or features the caller's plan does not include. The frontend interceptor opens the upgrade modal. |
| 403 | Forbidden (permission denied) |
| 404 | Not found |
| 409 | Conflict (duplicate, or an import operation that is already running) |
| 410 | Gone: disabled legacy endpoints (local register / login, password reset) |
| 429 | Rate-limited (DRF throttles), or `insufficient_tokens` on token-metered AI endpoints |
| 500 | Internal server error |
| 503 | `{ "code": "ai_unavailable" }` when no AI provider answered (nothing is charged); also `backup_not_configured`, `payments_unavailable` |
| 502 / 503 / 504 | Backend unavailable: `api.ts` retries idempotent requests (GET / HEAD / OPTIONS) once on `NEXT_PUBLIC_API_FALLBACK_URL` |

---

## Auth endpoints — `/api/auth/`

### `POST /api/auth/register/` (disabled)
**Auth**: none. Always `410 Gone`:
```json
{ "error": "Local username/password registration is disabled. Use Supabase Auth to sign up." }
```
Sign-up goes through Supabase Auth. The local `CustomUser` row is created (or linked) on the first authenticated request with a Supabase access token; see [`AUTHENTICATION.md`](./AUTHENTICATION.md) §4.

---

### `POST /api/auth/login/` (disabled)
**Auth**: none. Always `410 Gone`:
```json
{ "detail": "Local login is disabled. Please use Supabase authentication at /auth/login.", "error": "endpoint_gone" }
```
(The dev-only `/api/auth/local/{login,register,refresh}/` routes exist only when `LOCAL_DEV_AUTH` is on, which requires `DEBUG=True`; see [`LOCAL_DEVELOPMENT.md`](./LOCAL_DEVELOPMENT.md).)

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
The full field list is `accounts.serializers.UserSerializer` (it also carries `is_admin`, `is_premium`, `token_info`, `subscription_info`, the scholarship fields and the AI-tutor quota). The frontend decides admin access from `role` / `is_admin` in this response, not from Supabase metadata.

### `PUT / PATCH /api/auth/profile/`
**Auth**: required.

Partial update (PATCH) example:
```json
{ "college": "AIIMS Bhubaneswar", "target_year": 2027 }
```
Response `200`: updated user.

---

### `POST /api/auth/scholarship/start/`
**Auth**: required. Throttle: 10 starts per hour.
The server picks the five scholarship questions (`is_scholarship_eligible=True`, active).
Response `200`:
```json
{
  "questions": [{ "id": 812, "question_text": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "..." }],
  "challenge_token": "<signed>",
  "expires_in": 3600
}
```
The set is stored on the user (`CustomUser.scholarship_challenge`) until the attempt is submitted: starting again re-issues the **same** five questions with a new token, so a student cannot re-roll the set. `400` once the price is unlocked, `403` after 2 attempts. With fewer than five eligible questions the response is `{ "questions": [], "challenge_token": null, "expires_in": 0 }`.

### `POST /api/auth/verify-scholarship/`
**Auth**: required.
Request: `{ "answers": { "812": "B", "907": "A", ... }, "challenge_token": "<from /scholarship/start/>" }` (exactly five answers; ids must be the issued set).
Response `200`: `{ "status": "passed" | "failed", "score": 5, "message": "..." }`. A 5/5 on the first attempt unlocks ₹79, on the second ₹99 (`scholarship_granted_price`).
Errors: `400 {code: "scholarship_expired"}` (token older than 1 h), `400 {code: "scholarship_not_started"}` (bad token, a token already submitted, or any set other than the one stored for the current attempt), `400` for other ids, `403` after 2 attempts.

---

### `POST /api/auth/password-reset/` and `POST /api/auth/password-reset/confirm/` (disabled)
**Auth**: none. Both always answer `410 Gone`:
```json
{ "detail": "Password reset is handled by Supabase Auth. Use \"Forgot password\" on the sign-in page.", "error": "endpoint_gone" }
```
Password reset goes through Supabase (`resetPasswordForEmail`, then `updateUser` on `/reset-password`).

---

### Device Management

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/devices/` | Active devices of the current user, newest first. Each row carries `is_current: true` for the device the request comes from (its `X-Session-ID`), else `false`. |
| POST | `/api/auth/devices/logout/` | Log a device out `{ "device_id": 7 }` (sets `is_active=False`; that device's next request gets `401 device_inactive`) |

Device limit: a new device (unknown `X-Session-ID`) beyond the cap (2 free / 4 subscribed, counting devices seen in the last 30 days) gets `401 {code: "device_limit_reached"}` on every request except `/auth/profile/`, `/auth/devices/…`, `/auth/subscribe/…` and the read-only `GET /auth/tokens/` and `GET /analytics/announcements/`, which are answered without enrolling it. Admins are exempt. Details: [`AUTHENTICATION.md`](./AUTHENTICATION.md) §6.

---

### Token System

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/` | `{ available, purchased_tokens, feedback_credits, daily_tokens_used, weekly_tokens_used, total_tokens_used, daily_limit, weekly_limit, token_price, is_admin, unlimited_ai }`. `unlimited_ai` is true while an active plan with unlimited AI (1 year / legacy / admin grant) is never charged tokens; admins are reported by `is_admin`. |
| POST | `/api/auth/tokens/purchase/` | Not wired to a payment gateway: always `503 {code: "payments_unavailable"}` |
| GET | `/api/auth/tokens/history/` | Paginated `TokenTransaction` rows |

### Admin Token Management (admin: `IsControlTowerAdmin`, i.e. `role='admin'` or superuser)

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/admin/users/` | All users + balances |
| POST | `/api/auth/tokens/admin/grant/` | `{ "user_id": 42, "amount": 100, "note": "scholarship" }` |
| POST | `/api/auth/tokens/admin/transfer/` | `{ "from_user_id": 1, "to_user_id": 42, "amount": 10, "note": "..." }` |
| GET | `/api/auth/tokens/admin/audit-logs/` | Paginated `AdminAuditLog` |

---

### Admin User Lifecycle (admin: `IsControlTowerAdmin`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/admin/users/` | Paginated users (filters: `?role=&is_blocked=&search=`) |
| PATCH | `/api/auth/admin/users/<id>/block/` | `{ "blocked": true, "reason": "..." }` |
| PATCH | `/api/auth/admin/users/<id>/role/` | `{ "role": "admin" }` |
| POST | `/api/auth/admin/users/<id>/reset-progress/` | Wipes attempts/analytics |
| POST | `/api/auth/admin/system/reset-attempts/` | `{"scope": "user", "user_id": 42}` or `{ "scope": "all", "confirm": "RESET ALL" }`. `scope` is required (400 otherwise); `scope=all` without the phrase is `400 {code: "confirmation_required"}`. |
| POST | `/api/auth/admin/system/clear-analytics/` | same shape |
| POST | `/api/auth/admin/system/rerun-evaluation/` | same shape. Rebuilds `UserTopicPerformance` (subject-level and per-topic rows) from test answers and question-bank answers. `results`: `{ scope, user_id, rows_created, subject_rows_created, processed_responses, processed_qbank_answers }`; `processed_responses` counts answered test responses only. |
| POST | `/api/auth/admin/system/backup-data/` | Writes the core configuration data to the JSON fixture at `CORE_DATA_BACKUP_PATH` → `{ "message": "...", "records": 123 }` |
| POST | `/api/auth/admin/system/restore-data/` | Loads that same file → `{ "message": "...", "records": 123 }` |

`backup-data` and `restore-data` answer `503 {code: "backup_not_configured"}` in production while `CORE_DATA_BACKUP_PATH` is unset (the default file would sit on the container disk, which a redeploy wipes; `check --deploy` reports `accounts.W003`). `manage.py backup_core_data --output PATH` / `restore_core_data --input PATH` work without it.
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

**Answer entitlement** (one rule everywhere, `questions.views.user_can_view_answer`): staff, admins and premium users may see every answer; everyone else only the admin-curated free showcase questions, and never a scholarship-challenge question. Endpoints that would reveal an answer the caller may not see answer `402 {code: "upgrade_required", feature: "PYQ answers"}` or redact the answer parts, as described per endpoint.

> `/api/questions/mistake-notebook/*` was removed. The Mistake Notebook is served only by [`/api/analytics/mistake-notebook/*`](#mistake-notebook).

### `GET /api/questions/subjects/`
**Auth**: public. Query: `?exam_type=cms`
Response: a plain (unpaginated) array of `{ id, name, code, paper, description, icon, color, question_count }`, ordered by paper, name.

### `GET /api/questions/topics/`
**Auth**: public. Query: `?subject=1&parent=2&importance=`
Response: a plain (unpaginated) array of topics; `parent` carries the hierarchy.

### `GET /api/questions/`
**Auth**: required for full data; public for preview.
Query params: `?subject=1&topic=5&year=2022&difficulty=medium&is_active=true&search=&page=1&page_size=20`

Response `200` (student row, abbreviated):
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
      "year": 2018,
      "subject": 1,
      "subject_name": "General Medicine",
      "topic": 5,
      "difficulty": "medium",
      "concept_tags": ["high_yield"],
      "book_name": "",
      "reference_text": "",
      "textbook_references": [],
      "is_showcase": false,
      "effective_answer": null,
      "effective_explanation": null,
      "user_selected_answer": null,
      "user_is_correct": null
    }
  ]
}
```
List rows never carry the answer or explanation for students (`effective_answer` / `effective_explanation` are `null`). On a row the viewer may not see the answer of, the textbook fields are blanked (`reference_text`, `book_name`, `chapter`, `page_number` → `""`, `textbook_references` → `[]`), `concept_tags` keeps only `high_yield`, explanation images and answer media (video, page screenshot) are dropped, and the viewer's own `user_is_correct` / `user_selected_answer` are `null`. Admin rows (`QuestionAdminListSerializer`) add `correct_answer`, `explanation`, the AI and lock fields, `updated_at` and `is_active`.

### `GET /api/questions/<id>/`
Single question detail. The answer and explanation fields (`correct_answer`, `explanation`, `mnemonic`, the AI and `effective_*` fields, ...) are redacted unless the caller may see the answer.

### `POST /api/questions/<id>/bookmark/`
**Auth**: required. Toggle bookmark.
Response `201`: `{ "bookmarked": true }`, or `200`: `{ "bookmarked": false }`.

### `POST /api/questions/<id>/attempt/`
**Auth**: required. Record an attempt.
Request: `{ "selected_answer": "C", "time_spent_seconds": 42 }` (`selected_answer` A–E, else `400`).
Response `200`:
```json
{
  "is_correct": true,
  "correct_answer": "C",
  "explanation": "...",
  "effective_explanation": "...",
  "mnemonic": "...",
  "is_subscribed": false
}
```
`effective_explanation` is never blank (a short "the correct answer is X" note when nothing has been written yet). A question without an answer key returns `is_correct: null, correct_answer: ""` and records only study time. `402 upgrade_required` when the caller may not see the answer. `POST /api/questions/<id>/practice/attempt/` (`{ "answer": "C", "time_spent": 42, "confidence": 3 }`) follows the same rules. Both responses, like `GET /api/questions/<id>/`, carry `explanation_overridden: true` when an admin lock or a non-blank admin override decides the explanation (`null` in a redacted detail).

### `GET /api/questions/bookmarks/`
Current user's bookmarked questions, newest first: a plain array (at most 500 rows) without `?page=`, paginated with `?page=`.

### `GET /api/questions/years/`
Years that have questions, newest first, as a plain array of integers (`[2025, 2024, ...]`). Optional `?exam_type=` (`cms`, `neet_pg`, ...) and `?exam_source=` (prefix match, so `NEET PG` also covers `NEET PG (recall)`). Year 0 is never listed; students see years of active questions only.

### `GET /api/questions/stats/`
Question-bank stats for one bank: `?exam_source=` (label), `?exam_type=` (slug) or `?exam=` (URL slug, e.g. `neet-pg`).
Response: `{ total, total_solved, by_subject: [{id, name, code, count, solved}], by_year: [{year, count, solved}], by_difficulty: [{difficulty, count, solved}] }`. `by_subject` omits subjects with no active questions in the bank; `by_year` omits year 0. The INI-CET bank is stored under two labels (`INI-CET (recall)` and `INICET`): `exam_source=INI-CET`, `exam_source=INICET` and `exam_type=ini_cet` all count both, and the list and years endpoints accept either label.

### `POST /api/questions/<id>/generate-explanation/`
**Auth**: admin (`IsControlTowerAdmin`).
Request: `{ "correct_answer": "B", "regenerate_if_exists": false, "update_correct_answer": false, "dry_run": false }`. `correct_answer` (A–D) is required: missing or invalid is a `400`.
- An existing explanation and `regenerate_if_exists=false` (and not `dry_run`) → `409` with `existing_fields` and `requires_confirmation: true`.
- `dry_run: true` → `{ generated_fields, saved: false, dry_run: true }`; nothing is written.
- Otherwise the fields are saved after a revision snapshot → `{ generated_fields, saved: true, dry_run: false, verification_cleared, question }`. Generated content is never marked "Verified by Admin"; a verified question whose content changes loses the mark (`verification_cleared: true`).
- AI failure → `503`, nothing saved.

### `GET /api/questions/images/<image_id>/serve/`
**Auth**: public. Streams a `QuestionImage` (`?w=` max width, `?q=` JPEG quality). Only PNG, JPEG, GIF and WebP, detected from the file's bytes, are served inline; anything else (e.g. an SVG) is sent as a download. Every response carries `Content-Security-Policy: default-src 'none'; sandbox` and `X-Content-Type-Options: nosniff`. `404` for a missing or inactive row, `503` when the file is missing on disk.
Stem figures are public. An explanation figure (stored with role `explanation`, or referenced by `[[img:N]]` only from the explanation, concept explanation or mnemonic) needs `?t=<token>`: a signed token for that image id, which list, detail, `/images/` and admin image payloads append for viewers entitled to the answer (`questions/image_access.py`; valid for at least `QUESTION_IMAGE_TOKEN_TTL` seconds, default 12 h). A caller whose own credentials make it entitled needs no token. Otherwise `403 {"code": "image_token_required"}` and no redirect to storage.

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
| POST | `/api/questions/flashcards/<id>/review/` | `{ "quality": 4 }` (integer 0–5, else `400`) → SM-2 update |
| GET | `/api/questions/flashcards/analytics/` | Over all of the user's cards: `{ total_cards, due_today, cards_due_today, reviewed_cards, total_reviews, lapses, retention_rate, avg_ease_factor, avg_interval, interval_distribution }`. `due_today` = due now or never scheduled (`cards_due_today` is the older name); `reviewed_cards` = cards with at least one review; `retention_rate` = 1 − lapses / total_reviews, `null` until the first review. |

---

### Notes

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/notes/` | List current user's notes; `?question=35` |
| POST | `/api/questions/notes/` | `{ "question_id": 35, "body": "UMN lesions show ↑tone, ↑reflexes, +Babinski" }` |
| GET / PUT / PATCH / DELETE | `/api/questions/notes/<id>/` | Detail (frontend uses PATCH for partial updates) |

### Topic notes (admin) — added 2026-10-31

| Method | Path | Description |
|---|---|---|
| GET / POST | `/api/questions/topic-notes/library/` | Admin CRUD (paginated). `notes/` is the personal-notes endpoint and shadowed the old registration. |
| GET / PATCH / DELETE | `/api/questions/topic-notes/library/<id>/` | Detail |
| POST | `/api/questions/topic-notes/library/<id>/generate/` | AI-compile from same-topic explanations (admin) |
| POST | `/api/questions/topic-notes/` | Create-or-update by subject/topic/exam/title (admin) |
| POST | `/api/questions/topic-notes/<id>/generate/` | AI generation (admin, `ai_heavy` throttle) |

### Practice state & quests — added 2026-10-31

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/<id>/practice/state/` | `{flag, confidence, time_spent, eliminated, bookmarked}` (auth) — stored in `QuestionPracticeState` |
| POST | `/api/questions/<id>/practice/{flag,confidence,eliminate,time,attempt}/` | Update practice state (auth) |
| GET | `/api/analytics/quests/` | Lists quests; today's daily quests are generated server-side with progress from real activity |
| PATCH | `/api/analytics/quests/<id>/` | `{"is_completed": true}` claims a finished quest once; XP is server-defined. Other fields are read-only. DELETE is admin-only. |

---

### Discussions

| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/discussions/` | Top-level threads; `?question=35` |
| POST | `/api/questions/discussions/` | `{ "question": 35, "text": "...", "parent": null }`; a reply sets `parent` (same question as the parent) |
| GET | `/api/questions/discussions/<id>/replies/` | Replies of a thread (read-only) |
| GET / PATCH / DELETE | `/api/questions/discussions/<id>/` | Authors edit (`text` only) or delete their own posts; admins / staff may delete any post |
| POST | `/api/questions/discussions/<id>/vote/` | `{ "vote_type": "up" }` or `{ "vote_type": "down" }`; the same vote again removes it |

Threads discuss the answer, so they follow the answer entitlement: on a question whose answer the viewer may not see (a free account outside the free showcase, or any scholarship question) the viewer sees only their own posts. Admins, staff and premium users see everything.

---

### Chat Assistant (Question Bank)

| Method | Path | Description |
|---|---|---|
| POST | `/api/questions/chat/` | `{ "message": "Explain UMN vs LMN", "question_id": 35 }` → token-metered AI response |

---

## Test endpoints — `/api/tests/`

All endpoints need an authenticated user. Creating, editing and publishing library tests (`POST /api/tests/`, `PUT/PATCH/DELETE /api/tests/<id>/`, `create-manual/`, `set-questions/`, `publish/`, `unpublish/`, `duplicate/`, `safe-update/`) is admin-only (`IsControlTowerAdmin`). Students see the published official library plus the tests they generated themselves.

**Free-plan rules** (`tests_engine/entitlement.py`). A student without full access (not premium, staff or admin) may start or submit only a test of at most 20 questions (`FREE_TEST_MAX_QUESTIONS`), all of them free-showcase, non-scholarship questions. Anything else is:
```json
{ "code": "upgrade_required", "feature": "Mock Tests", "message": "..." }
```
with status `402`. Scoring a question is a right / wrong signal (and a test can be retaken), so a student is never scored on a question whose answer they may not see. `TestSerializer.is_free_for_current_user` applies the same rule for the UI badge.

### `GET /api/tests/`
Paginated tests (`TestSerializer`): filters `?test_type=&subject=&topic=&exam_type=&is_published=`; `?scope=library` (official library only) or `?scope=mine` (the viewer's generated tests).

### `GET /api/tests/<id>/`
Test detail with its questions. For non-admins the questions omit `textbook_references`, `reference_text`, `concept_tags` and `concept_id`, and (without full access) the explanation figures of questions outside the free set.

### `POST /api/tests/generate/`
Request: `{ "test_type": "mixed", "num_questions": 20, "exam_type": "cms", "subject_id": null, "topic_id": null, "year": null }`.
`test_type` ∈ `subject`, `topic`, `mixed`, `paper1`, `paper2`, `daily`, `pyq_year`, `weak`, `adaptive` (default `mixed`); `num_questions` 1–500; `daily` is always 20 questions, `paper1` / `paper2` are always a full 120-question paper with the 120-minute CMS limit. Questions come from one exam (`exam_type`, default `cms`). Response `201`: the new test (`TestSerializer`), private to its creator (`is_published=false`).
For a free plan the questions are drawn from the free showcase; a selection with questions but no free ones is `402 upgrade_required`. Paper mocks keep the real paper (minus scholarship questions) and stay premium: `/start/` answers `402`.

### `POST /api/tests/generate-adaptive/`
Request: `{ "num_questions": 30, "exam_type": "cms" }` (1–200). Targets the ten lowest-accuracy topic / subject rows with at least three answers, then fills up from the exam. Free plans get free questions only (`402` when the exam has questions but no free ones, `400` when it has none). Response `201`: the new test.

### `POST /api/tests/pyq-simulation/`
Request: `{ "exam_type": "cms", "year": 2024, "paper": 1 }` (`paper` optional, 1 or 2). Builds the real paper of that exam and year with its time limit (CMS: 120 minutes per paper) and negative marking; `404` when the year has no questions. A simulation is the real paper, so it is premium: a free plan gets `402` at `/start/`. Response `201`: the new test.

### `POST /api/tests/<id>/start/`
Starts the test, or resumes the user's in-progress attempt of it (same `attempt_id`, start time and question order; two racing starts resume the attempt that won the insert).
Response `200`:
```json
{
  "attempt_id": 99,
  "test": { "...": "TestSerializer" },
  "questions": [ { "...": "QuestionListSerializer row" } ],
  "started_at": "2026-11-01T06:30:00Z",
  "resumed": false,
  "server_time": "2026-11-01T06:30:00Z",
  "time_limit_seconds": 1800,
  "remaining_seconds": 1800,
  "last_completed_attempt_id": 98
}
```
`questions` omit `textbook_references`, `reference_text`, `concept_tags` and `concept_id`. `last_completed_attempt_id` is the user's latest completed attempt of this test (or `null`), so a player whose submit response was lost can still show the stored result. `402 upgrade_required` per the free-plan rules.

### `POST /api/tests/<id>/submit/`
Request:
```json
{
  "attempt_id": 99,
  "answers": [
    { "question_id": 35, "selected_answer": "C", "time_taken_seconds": 42, "confidence_level": 4 },
    { "question_id": 36, "selected_answer": "", "time_taken_seconds": 21 }
  ]
}
```
Only questions of this test are scored, each once; the score counts the whole paper (`correct − incorrect × negative_mark_value` when negative marking is on).
Response `200`: the attempt (`TestAttemptSerializer`: `id, test, test_title, started_at, completed_at, score, total_marks, correct_count, incorrect_count, unanswered_count, time_taken_seconds, is_completed, is_late, accuracy`) plus `xp_earned`. `is_late` is true when the submit came later than the time limit + 120 s: the attempt is scored but earns no XP and stays off the leaderboard.
Errors: `400 {error: "Invalid attempt"}`; `400 {code: "already_submitted", attempt_id, result}` for a repeated submit (with the stored result); `402 upgrade_required` per the free-plan rules (the attempt stays open).

### `GET /api/tests/<id>/review/?attempt_id=99`
Per-question review of a completed attempt: `{ attempt_id, score, total_marks, accuracy, total_time, correct, incorrect, unanswered, is_late, subject_breakdown, questions }`. Each row carries `correct_answer`, `selected_answer`, `is_correct`, `explanation`, `mnemonic`, `concept_explanation`, `textbook_references`, `book_reference`, `chapter`, `page_number`, `concept_tags`, ... and `answer_locked`. For a question the user may not see the answer of, `answer_locked` is `true`, `correct_answer` is `null` and `explanation`, `mnemonic`, `concept_explanation` are `""` and `textbook_references` `[]`. Such rows only appear in attempts scored before the free-plan rule, or while the user was premium.

### `GET /api/tests/attempts/` and `GET /api/tests/attempts/<id>/`
The user's attempts (`TestAttemptSerializer`, including `is_late`). The detail adds `responses`, each with a slim, entitlement-aware `question_detail` snapshot (`id`, text and options, subject / topic, `year`, `paper`, `difficulty`, `exam_source`, `correct_answer`, `explanation`, `mnemonic`, `concept_explanation`, `textbook_references`, `answer_locked`), locked the same way as `/review/`.

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
| GET | `/api/analytics/study-time/` | Per-subject study-time breakdown |
| GET | `/api/analytics/streak/` | Current streak + longest |
| GET | `/api/analytics/badges/` | Earned badges + locked badges |
| GET | `/api/analytics/leaderboard/` | Global ranking; `?period=weekly` |

### Mistake Notebook

Filled automatically from wrong answers in the question bank and in completed tests (`questions/mistakes.py`). These are the only Mistake Notebook routes (the `/api/questions/mistake-notebook/*` duplicates were removed).

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/mistake-notebook/` | `{ results, count, page, page_size }` (`page_size` up to 100); filters `?review_status=&is_flagged=true&subject=&topic=` |
| POST | `/api/analytics/mistake-notebook/` | `{ "question": 35, "user_note": "...", "is_flagged": true }`: (re-)adds a question the user really answered wrong (bank or completed test), else `400`; `201` when created |
| PATCH / DELETE | `/api/analytics/mistake-notebook/<id>/` | Update `user_note` / `is_flagged`, or delete the entry |
| POST | `/api/analytics/mistake-notebook/<id>/review/` | Mark reviewed; schedules the next review (1 → 3 → 7 days; `mastered` after 5 reviews) |
| GET | `/api/analytics/mistake-notebook/due/` | Entries due for review now: `{ results, count }` |
| GET | `/api/analytics/mistake-notebook/stats/` | `{ total, by_status, flagged, due_today }` |

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

### Admin (`IsControlTowerAdmin`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/admin-dashboard/` | Cross-user aggregate |
| POST | `/api/analytics/admin/weak-area-control/` | Adjust weak-topic thresholds |
| GET / POST | `/api/analytics/admin/campaigns/` | List (`{count, results}`, newest 200; `?status=`) / create campaigns (announcements). A campaign with a future `scheduled_for` is created `scheduled`, otherwise `draft`. |
| POST | `/api/analytics/admin/campaigns/<id>/send-now/` | Publish in-app now: the dashboard feed and the notification bell. Nothing is emailed or pushed. Sets `delivery_status='sent'`, `sent_at`, `delivery_count` = audience size; a future `scheduled_for` is moved to now. `400 {code: "expired"}` when `expires_at` has passed (set a later expiry first). |

---

## AI endpoints — `/api/ai/`

Token costs (`consume_ai_token`): **1 token** for tutor chat, `rag-answer` and a fresh `high-yield` prediction; **10 tokens** for `mnemonic`, `explain`, `analyze`, `explain-answer`, `explain-question/<id>/`, `study-plan` and `generate-questions`. Admins, staff and plans with unlimited AI are never charged. A short balance is `429 { "error": "insufficient_tokens", "message", "available", "required" }`. Free plans also have a daily AI Tutor cap: `402 { "code": "upgrade_required", "feature": "AI Tutor", "remaining": 0, "cap": N }`.

Failure contract: when no provider answers, the view gives back what it charged (tokens and the free slot), stores nothing, and answers with an extractive offline answer or `503 { "code": "ai_unavailable", "error", "message", "offline", "charged": false }`. With `AI_OFFLINE_MODE=1` no provider is called. An AI explanation of a question-bank question reveals its answer, so those endpoints answer `402 upgrade_required` (`charged: false`) when the caller may not see the answer.

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
| POST | `/api/ai/rag-search/` | `{ "query": "DKA management" }` → raw textbook passages. **Admin only.** |
| POST | `/api/ai/rag-answer/` | `{ "query": "..." }` → RAG-grounded answer (1 token) |
| POST | `/api/ai/textbook-reference/` | `{ "question_text": "..." }` → `{ "references": [...] }` (at most 3, each with a short locating excerpt). Free, auth required, throttle `ai_tutor`. The exact stem of a question the caller may not see answers `402 upgrade_required`. |
| GET | `/api/ai/screenshot/<question_id>/` | The cited textbook page: `200 { "screenshot_url": "..." }`; `202 { "status": "rendering" }` while another request renders the page; `402 { "code": "upgrade_required" }` when the caller may not see the answer (`questions.views.user_can_view_answer`; scholarship questions are always locked); `404` when no textbook page is available (a miss is cached for 1 h). Free, auth required, throttle `ai_tutor`. The render is stored in `Question.page_screenshot`, a MEDIA file: production must serve `/media/` (Django routes it only with `DEBUG=True`; see [`ARCHITECTURE.md`](./ARCHITECTURE.md) §7). |

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

## Import endpoints (admin only)

### Recall importers — `/api/imports/neetpg/` and `/api/imports/inicet/`

Both mounts expose the same admin-only (`IsControlTowerAdmin`) views; each lists, shows and retries only its own importer's jobs (`QuestionImportJob.summary["importer"]`; jobs without one are NEET PG's).

| Method | Path | Description |
|---|---|---|
| GET | `jobs/` | Recall PDF import jobs, newest first, paginated (`count` / `next` / `results`, 20 per page, `?page_size=` up to 100) |
| POST | `jobs/` | `{ "source_dir": "<folder inside RECALL_IMPORT_ALLOWED_ROOTS>", "force": false }` → `202 { job_id, status, task_id }` (runs on the django-q worker) |
| GET | `jobs/<pk>/` | One job |
| POST | `jobs/<pk>/retry/` | Re-queue a `failed` / `completed` job (`400` otherwise) |
| GET | `reports/<run_id>/` | `{ run_id, reports: { "IMPORT_REPORT.md": "...", ... } }` |

### Ingestion platform — `/api/ingestion/`

Admin-only. Jobs: `jobs/` (newest 200, filters `?status=&batch_run=&parent_exam=&material_sha16=`), `jobs/<id>/`, `jobs/<id>/{retry,cancel,checkpoints,logs,stages,staged-questions}/`; materials: `materials/`, `materials/upload/` (PDF only, checked by its bytes), `materials/<sha16>/`; batches: `batches/`, `batches/<id>/`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/ingestion/jobs/counts/` | Jobs per status over every job: `{ "counts": { "queued", "processing", "completed", "failed", "cancelled", "crashed" }, "total" }` |

Job rows carry `exam` (the job's exam, or its material's exam hint), `exam_label` (display name) and `material_filename`. Batch `status`, `total_jobs`, `completed_jobs` and `failed_jobs` are computed from the batch's jobs, not read from stored counters. Stale-job recovery: [`BATCH_SYSTEM.md`](./BATCH_SYSTEM.md#ingestion-platform-jobs).

### Admin Import Center — `/api/admin/import/`

Staff-only material importer (upload, batches, review queue, publish). See [`IMPORT_API.md`](./IMPORT_API.md).

(`/api/video/` no longer exists: video generation is `POST /api/questions/<id>/generate-video/` plus `video_engine.tasks`.)

---

## Health endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/` | `{ "status": "ok" }` |
| GET | `/api/live/` | Liveness, no DB call: `{ "status": "live" }` |
| GET | `/api/ready/` | Readiness: `SELECT 1`, `503 {"status": "not-ready"}` when the database is unreachable |
| GET | `/api/health/client-ip/` | **Admin only** (`IsControlTowerAdmin`). Echoes the caller's own `REMOTE_ADDR`, the client-IP headers that reached Django (`X-Forwarded-For`, `X-Real-IP`, `DO-Connecting-IP`, `CF-Connecting-IP`, `True-Client-IP`, `Forwarded`), the configured `num_proxies` / `trusted_client_ip_header`, and the address the question-bank limiter (`rate_limit_client_ip`) and DRF's throttles (`drf_throttle_ident`) derive. Use it to set `NUM_PROXIES` / `TRUSTED_CLIENT_IP_HEADER`; nothing is stored. |
| GET | `/api/` | API root index |
| GET | `/sentry-debug/` | Triggers a test exception (gated to dev only) |

---

## Authentication Examples

### Supabase (the only production sign-in)

Frontend `api.ts` interceptor automatically attaches `Authorization: Bearer <supabase_access_token>`. The backend verifies it with Supabase (`GET /auth/v1/user`) and resolves the local user by `CustomUser.supabase_uid`.

```bash
curl https://crackcms-vsthc.ondigitalocean.app/api/auth/profile/ \
  -H "Authorization: Bearer <supabase_access_token>" \
  -H "X-Session-ID: dev_a1b2c3d4_1719900000"
```

### Django JWT (local development only)

`POST /api/auth/login/` is disabled (`410`). Django-issued JWTs exist only for the dev-only local auth (`LOCAL_DEV_AUTH`, `DEBUG=True`): `/api/auth/local/login/`, `/local/register/`, `/local/refresh/`.

### X-Session-ID

`api.ts` generates and sends a per-browser fingerprint:

```bash
curl https://crackcms-vsthc.ondigitalocean.app/api/questions/ \
  -H "Authorization: Bearer <token>" \
  -H "X-Session-ID: dev_a1b2c3d4_1719900000"
```

---

## Error Code Reference

| Code | Status | When |
|---|---|---|
| `account_blocked` | 401 | The account is blocked (`is_active=False`). `api.ts` signs out and shows the reason on `/login`. |
| `email_not_confirmed` | 401 | The Supabase identity has not confirmed its email. Signs out. |
| `email_required` | 401 | A Supabase identity without an email (phone-only / anonymous). Signs out. |
| `account_link_required` | 401 | The email belongs to an admin/staff row (or a row linked to another identity) that this Supabase identity may not link to automatically; an operator links it with `manage.py link_supabase_identity`. The frontend signs out with "This account must be verified by an administrator". |
| `device_inactive` | 401 | This device was logged out (Settings or admin). `api.ts` drops its device id and signs out. |
| `device_limit_reached` | 401 | A new device beyond the plan's cap (2 free / 4 subscribed). `api.ts` keeps the session and opens `/settings?deviceLimit=1` (not while on `/settings` or `/subscription`). |
| `upgrade_required` | 402 | Paywall; carries `feature` (`PYQ answers`, `Mock Tests`, `AI Tutor`, ...) and `message`. Opens the upgrade modal. |
| `insufficient_tokens` | 429 | AI token balance below the action's cost (in `error`, with `available` / `required`). |
| `ai_unavailable` | 503 | No AI provider answered and no offline answer exists; nothing was charged. |
| `already_submitted` | 400 | A test attempt was submitted again; the body carries the stored `result`. |
| `scholarship_not_started` / `scholarship_expired` | 400 | Scholarship verify without a valid, current challenge token. |
| `confirmation_required` | 400 | A platform-wide admin system action (`scope=all`) without `confirm: "RESET ALL"`. |
| `expired` | 400 | Campaign send-now after its `expires_at`. |
| `backup_not_configured` | 503 | Admin backup / restore without `CORE_DATA_BACKUP_PATH` in production. |
| `payments_unavailable` | 503 | `POST /api/auth/tokens/purchase/` (not wired to a gateway). |
| `endpoint_gone` | 410 | Disabled legacy endpoints (local login, password reset). |

`session_invalid` (the old single-session code) is no longer emitted; `api.ts` still treats it as session-ending for older backends.

See [`AUTHENTICATION.md`](./AUTHENTICATION.md) for the auth flow; [`ADMIN_SYSTEM.md`](./ADMIN_SYSTEM.md) for admin-only endpoints.
