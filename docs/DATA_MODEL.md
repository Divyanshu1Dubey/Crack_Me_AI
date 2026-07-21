# Data Model Reference

> Every Django model, foreign key, index, constraint, business rule, data lifecycle, and possible bottleneck.

---

## Table of Contents

1. [`accounts` app](#accounts-app)
2. [`questions` app](#questions-app)
3. [`tests_engine` app](#tests_engine-app)
4. [`analytics` app](#analytics-app)
5. [`ai_engine` app](#ai_engine-app)
6. [`jobs` app](#jobs-app)
7. [`django-q2` (background tasks)](#django-q2)
8. [`django-axes` (auth attempts)](#django-axes)
9. [RAG store (SQLite TF-IDF)](#rag-store)
10. [Cross-cutting business rules](#cross-cutting-business-rules)
11. [Data lifecycle](#data-lifecycle)
12. [Possible bottlenecks](#possible-bottlenecks)

---

## `accounts` app

### `CustomUser` (extends `AbstractUser`)

| Field | Type | Notes |
|---|---|---|
| `username` | `CharField` (inherited) | Unique |
| `email` | `EmailField` (inherited) | |
| `password` | (inherited) | Hashed |
| `role` | `CharField` | `student` / `admin` |
| `phone` | `CharField(15)` | optional |
| `college` | `CharField(200)` | optional |
| `session_key` | `CharField(255)` | Single active session enforcement |
| `current_session_id` | `CharField(255)` | mirrors active device session |
| `profile_bonus_rewarded` | `BooleanField` | First-time profile completion flag |
| `is_subscribed` | `BooleanField` | Mirror of latest active subscription |
| `target_exam` | `CharField(50)` | Default `UPSC CMS` |
| `active_exam_track` | `FK(ExamTrack, SET_NULL)` | User's selected track |
| `target_year` | `IntegerField` | User's target exam year |
| `avatar_url` | `URLField` | |
| `scholarship_test_passed` | `BooleanField` | |
| `scholarship_test_attempts` | `IntegerField` | |
| `last_seen` | `DateTimeField` | |
| `scholarship_granted_price` | `IntegerField` | |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Properties**: `is_admin` → `role=='admin' or is_superuser` (used to bypass token checks).

**Business rules**:
- Single-active-session enforcement via `session_key` + `UserDevice`.
- Admin/staff bypass token metering (`TokenBalance.consume_token` checks `user.is_admin`).
- `active_exam_track` SET_NULL on ExamTrack delete (preserves user).

---

### `TokenBalance` (OneToOne → `CustomUser`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `user` | `OneToOneField(CustomUser, CASCADE)` | | related_name=`token_balance` |
| `purchased_tokens` | `IntegerField` | 50 | Never expire |
| `daily_tokens_used` | `IntegerField` | 0 | Counter, resets at midnight |
| `weekly_tokens_used` | `IntegerField` | 0 | Counter, resets Monday |
| `total_tokens_used` | `IntegerField` | 0 | Lifetime counter |
| `last_daily_reset` | `DateField` | today | |
| `last_weekly_reset` | `DateField` | today | |
| `feedback_credits` | `IntegerField` | 0 | Earned via verified feedback (+2) |
| `created_at` | `DateTimeField(auto_now_add)` | | |
| `updated_at` | `DateTimeField(auto_now)` | | |

**Indexes**: implicit unique on `user`.

**Properties / methods**:
- `available_tokens` → `min(daily_remaining, weekly_remaining) + purchased + feedback_credits`. **Both daily and weekly limits apply independently — daily is a subset of weekly.**
- `consume_token(amount=1)` — Priority: free → feedback → purchased. Returns `False` if insufficient.
- `add_purchased_tokens(amount)` / `refund_token(amount=1)` / `add_feedback_credit(amount=2)`.

**Business rules**:
- `_reset_if_needed()` — auto-resets `daily_tokens_used` to 0 at next-day, `weekly_tokens_used` to 0 on Monday.
- `TokenConfig.get_config()` singleton (pk=1) provides limits.
- Consumption is **atomic** only at the row level; concurrent requests could in theory over-consume. See [Possible Bottlenecks](#possible-bottlenecks).

---

### `TokenConfig` (singleton, pk=1)

| Field | Type | Default | Notes |
|---|---|---|---|
| `free_daily_tokens` | `IntegerField` | 10 | |
| `free_weekly_tokens` | `IntegerField` | 50 | |
| `token_price` | `DecimalField(6,2)` | 1.00 INR | |
| `feedback_reward` | `IntegerField` | 2 | |
| `min_purchase` | `IntegerField` | 10 | |
| `max_purchase` | `IntegerField` | 500 | |

**Class method**: `get_config()` returns the singleton (auto-creates if missing).

---

### `TokenTransaction` (audit log)

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`token_transactions` |
| `transaction_type` | `CharField` | `purchase` / `feedback_reward` / `admin_grant` / `admin_revoke` / `admin_transfer` / `refund` |
| `amount` | `IntegerField` | positive = credit, negative = debit (not enforced at DB level) |
| `price_paid` | `DecimalField(8,2)` | INR |
| `payment_id` | `CharField(200)` | Razorpay reference |
| `note` | `TextField` | |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Meta**: `ordering = ['-created_at']`.

---

### `AdminAuditLog` (immutable audit trail)

| Field | Type | Notes |
|---|---|---|
| `actor` | `FK(CustomUser, SET_NULL)` | related_name=`admin_actions` |
| `action` | `CharField(40)` | `token_grant` / `token_revoke` / `token_transfer` / `user_block` / `user_role_update` / `user_progress_reset` / `system_attempt_reset` / `system_analytics_clear` / `system_rerun_evaluation` / etc. |
| `resource_type` | `CharField(60)` | e.g. `token_balance` |
| `resource_id` | `CharField(120)` | |
| `detail` | `TextField` | Human description |
| `metadata` | `JSONField` | Structured extras |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Meta**: `ordering = ['-created_at']`. Append-only — never updated or deleted in code.

---

### `PaymentAttempt` (Razorpay session)

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`payments` |
| `razorpay_order_id` | `CharField(100)` | **unique** |
| `razorpay_payment_id` | `CharField(100)` | nullable |
| `amount` | `DecimalField(10,2)` | INR |
| `plan` | `CharField(30)` | `1_month` / `3_months` / `1_year` / `scholarship_1_month` / `legacy` |
| `status` | `CharField(20)` | `initiated` / `successful` / `failed` |
| `error_message` | `TextField` | nullable |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `updated_at` | `DateTimeField(auto_now)` | |

**Indexes**: unique on `razorpay_order_id`.

---

### `Subscription`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`subscriptions` |
| `plan` | `CharField(30)` | same choices as PaymentAttempt |
| `plan_display_name` | `CharField(100)` | |
| `amount_paid` | `DecimalField(10,2)` | |
| `razorpay_order_id` | `CharField(100)` | |
| `razorpay_payment_id` | `CharField(100)` | |
| `status` | `CharField(20)` | `active` / `expired` / `cancelled` |
| `starts_at` | `DateTimeField` | |
| `expires_at` | `DateTimeField` | **NULL = lifetime** |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Properties**:
- `is_active` → status=='active' AND (expires_at is NULL OR expires_at > now)
- `days_remaining` → -1 if lifetime, 0 if expired, otherwise delta days

**Class methods**:
- `get_active_subscription(user)` — returns the latest active sub, auto-expires stale ones
- `activate_from_payment(...)` — extends existing active sub or creates new one; updates `user.is_subscribed` mirror

**Plan durations**:
| Plan | Duration |
|---|---|
| 1_month | 30 days |
| 3_months | 90 days |
| 1_year | 365 days |
| scholarship_1_month | 30 days |
| legacy / admin_grant | lifetime (NULL) |

---

### `UserDevice`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`devices` |
| `device_fingerprint` | `CharField(255)` | |
| `device_name` | `CharField(255)` | |
| `browser` | `CharField(255)` | |
| `ip_address` | `GenericIPAddressField` | nullable |
| `last_login` | `DateTimeField(auto_now)` | |
| `is_active` | `BooleanField` | |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Constraints**: `unique_together = ('user', 'device_fingerprint')`.

**Meta**: `ordering = ['-last_login']`.

---

## `questions` app

### `ExamTrack`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField` | "UPSC CMS", "NEET PG" |
| `code` | `CharField` | unique-ish |
| `description` | `TextField` | |
| `is_active` | `BooleanField` | |

**Reverse**: `users` (CustomUser FK), `subjects`, `questions`, etc.

---

### `Subject`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField` | |
| `code` | `CharField` | e.g. MED, SURG, PSM |
| `exam_track` | `FK(ExamTrack, SET_NULL)` | related_name=`subjects` |
| `description` | `TextField` | |

**Reverse**: `topics`, `questions`, `flashcards`.

---

### `Topic`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField` | |
| `subject` | `FK(Subject, CASCADE)` | related_name=`topics` |
| `parent` | `Self-FK` | hierarchical (e.g. Respiratory → Pneumonia → CAP) |
| `description` | `TextField` | |
| `importance` | `IntegerField` | 1–10 |

---

### `Question` (the core MCQ) — verified from `backend/questions/models.py`

| Field | Type | Notes |
|---|---|---|
| `exam_type` | `CharField` | `cms` / `neet_pg` / `usmle` / `fmge` |
| `exam_track` | `FK(ExamTrack, SET_NULL)` | |
| `question_text` | `TextField` | normalized on save |
| `option_a/b/c/d` | `TextField` | normalized on save |
| `correct_answer` | `CharField(1)` | `A` / `B` / `C` / `D` |
| `year` | `IntegerField` | PYQ year, **db_index=True** |
| `subject` | `FK(Subject, CASCADE)` | |
| `topic` | `FK(Topic, SET_NULL)` | |
| `difficulty` | `CharField(10)` | `easy` / `medium` / `hard` |
| `concept_tags` | `JSONField` | `["Cardiology", "Valvular"]` |
| `concept_id` | `CharField(120)` | Stable concept identifier for linking related PYQs, db_index |
| `explanation` | `TextField` | detailed answer explanation |
| `concept_explanation` | `TextField` | from-basics concept explanation |
| `mnemonic` | `TextField` | memory trick |
| `book_name` | `CharField(200)` | "Harrison's" |
| `chapter` | `CharField(200)` | |
| `page_number` | `CharField(50)` | "pp. 908-920" |
| `reference_text` | `TextField` | textbook excerpt |
| `paper` | `IntegerField` | Paper 1 or Paper 2 |
| `source` | `CharField(200)` | Source file (e.g. `PYQ_2019_Paper1.pdf`) |
| `exam_source` | `CharField(50)` | default `UPSC CMS` |
| `times_asked` | `IntegerField` | how many times this concept appeared |
| `is_active` | `BooleanField` | hide from students |
| `uuid` | `UUIDField` | unique, immutable |
| `display_number` | `IntegerField` | number shown to students (scoped by year/paper) |
| `is_dropped` | `BooleanField` | dropped/disputed question excluded from scoring |
| `admin_edited` | `BooleanField` | protect from seed-script overwrites |
| `needs_review` | `BooleanField` | partially digitized or disputed PYQs |
| `is_scholarship_eligible` | `BooleanField` | eligible for scholarship test |
| `is_controversial` | `BooleanField` | ambiguous/controversial answers |
| `is_disputed` | `BooleanField` | answer key disputed by students |
| `created_at` / `updated_at` | `DateTimeField` | |
| `textbook_references` | `JSONField` | list of `{book, chapter, page, excerpt}` dicts |
| `learning_technique` | `TextField` | how to study/approach this concept |
| `shortcut_tip` | `TextField` | quick solving trick |
| `page_screenshot` | `ImageField` | upload_to `question_screenshots/`, optional |
| `concept_keywords` | `JSONField` | keywords for vector similarity |
| `ai_explanation` | `TextField` | AI-generated detailed explanation |
| `ai_answer` | `TextField` | AI-generated answer rationale |
| `ai_mnemonic` | `TextField` | AI-generated mnemonic |
| `ai_references` | `JSONField` | AI-generated references |
| `ai_clinical_pearl` | `TextField` | AI-generated clinical pearl |
| `ai_generated_at` | `DateTimeField` | |
| `ai_model` | `CharField(100)` | model used |
| `ai_version` | `CharField(50)` | prompt/system version |
| `video_url` | `URLField(500)` | Supabase storage URL for MP4 |
| `video_thumbnail` | `URLField(500)` | thumbnail URL |
| `video_status` | `CharField(20)` | `pending` / `processing` / `completed` / `failed`, db_index |
| `video_duration` | `IntegerField` | duration in seconds |
| `video_generated_at` | `DateTimeField` | |
| `video_version` | `CharField(50)` | |
| `video_error` | `TextField` | |
| `admin_answer_override` | `TextField` | admin manual override of AI answer |
| `admin_explanation_override` | `TextField` | |
| `admin_mnemonic_override` | `TextField` | |
| `admin_references_override` | `JSONField` | |
| `lock_answer` | `BooleanField` | protect from AI regeneration |
| `lock_explanation` | `BooleanField` | |
| `is_verified_by_admin` | `BooleanField` | db_index |
| `verified_by` | `FK(CustomUser, SET_NULL)` | related_name=`verified_questions` |
| `verified_at` | `DateTimeField` | |
| `verified_note` | `TextField` | |
| `similar_questions` | `M2M(self, symmetrical)` | questions testing the same concept |

**Indexes (declared)**:
- `(year, subject)`
- `(difficulty)`
- `(exam_source)`
- `(paper)`
- `(is_active, is_verified_by_admin)`
- `(subject, topic, year, difficulty)` — composite

**Reverse relations**: `bookmarks`, `feedbacks`, `discussions`, `notes`, `flashcards`, `qbank_attempts`, `ai_operation_logs`, `revision_snapshots`, `source_extraction_items`, `verified_questions` (via `verified_by`).

**`save()` method** (verified at line 247): auto-normalizes `question_text`, options, explanation, etc. — strips triple newlines, fixes spacing before punctuation, inserts newline before roman-numeral/decimal sub-statements (`I.`, `1.`, etc.).

**Business rules**:
- `correct_answer` must be one of `A/B/C/D` (validated via `choices=` constraint).
- `is_active=False` hides from student endpoints.
- `is_dropped=True` excludes from scoring.
- `admin_edited=True` protects from seed-script overwrites.
- Questions filtered by `exam_track` via Subject → ExamTrack chain.
- `lock_answer` / `lock_explanation` prevent AI regeneration of those fields.

---

### `QuestionImportJob` / `QuestionExtractionItem`

Track AI-driven import jobs (PDF → questions). `QuestionExtractionItem` holds per-question confidence scores and review state (`pending`, `accepted`, `rejected`).

---

### `QuestionBookmark`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser)` | |
| `question` | `FK(Question)` | |
| `created_at` | `DateTimeField` | |

**Constraints**: `unique_together = ('user', 'question')`.

---

### `QuestionFeedback`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser)` | nullable (anonymous feedback) |
| `question` | `FK(Question)` | |
| `feedback_type` | `CharField` | `wrong_answer`, `unclear`, `outdated` |
| `description` | `TextField` | |
| `status` | `CharField` | `pending` / `accepted` / `rejected` |
| `admin_response` | `TextField` | |
| `verified` | `BooleanField` | triggers +2 token reward |
| `created_at` | `DateTimeField` | |

---

### `Discussion` / `DiscussionVote`

Threaded discussions under questions.

`Discussion`: `user`, `question`, `content`, `parent` (self-FK for replies), `created_at`.
`DiscussionVote`: `user`, `discussion`, `value` (+1/-1), unique together.

---

### `Note`

Per-user, per-question private notes.

---

### `Flashcard` (SM-2)

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser)` | |
| `question` | `FK(Question)` | |
| `ease_factor` | `FloatField` | default 2.5 |
| `interval` | `IntegerField` | days until next review |
| `repetitions` | `IntegerField` | SM-2 repetition counter |
| `next_review` | `DateField` | |
| `last_reviewed` | `DateTimeField` | |
| `created_at` | `DateTimeField` | |

**Constraints**: `unique_together = ('user', 'question')`.

**Lifecycle**: SM-2 algorithm updates ease/interval/repetitions on each review (quality 0–5).

---

### `QuestionAttempt`

Per-question attempt log: `user`, `question`, `test_attempt` (nullable), `selected_answer`, `is_correct`, `time_taken_seconds`, `created_at`.

---

### `Announcement`

`title`, `body`, `starts_at`, `ends_at`, `is_active`, `audience` (`all` / `subscribers`).

---

## `tests_engine` app

### `Test`

| Field | Type | Notes |
|---|---|---|
| `title` | `CharField(300)` | |
| `exam_type` | `CharField(20)` | `cms` / `neet_pg` / `usmle` / `fmge` |
| `test_type` | `CharField(20)` | 9 types: `subject` / `topic` / `mixed` / `paper1` / `paper2` / `daily` / `pyq_year` / `weak` / `adaptive` |
| `description` | `TextField` | |
| `subject` | `FK(Subject, SET_NULL)` | nullable for mixed tests |
| `topic` | `FK(Topic, SET_NULL)` | nullable |
| `questions` | `M2M(Question)` | blank |
| `num_questions` | `IntegerField` | default 20 |
| `time_limit_minutes` | `IntegerField` | default 30 |
| `negative_marking` | `BooleanField` | default True |
| `negative_mark_value` | `FloatField` | default 0.33 |
| `is_published` | `BooleanField` | default True |
| `version` | `PositiveIntegerField` | default 1 (incremented on every edit) |
| `created_by` | `FK(CustomUser, SET_NULL)` | related_name=`created_tests` |
| `created_at` / `updated_at` | `DateTimeField` | |

### `TestAttempt`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`test_attempts` |
| `test` | `FK(Test, CASCADE)` | related_name=`attempts` |
| `started_at` | `DateTimeField(auto_now_add)` | |
| `completed_at` | `DateTimeField` | nullable |
| `score` | `FloatField` | nullable |
| `total_marks` | `FloatField` | nullable |
| `correct_count` | `IntegerField` | default 0 |
| `incorrect_count` | `IntegerField` | default 0 |
| `unanswered_count` | `IntegerField` | default 0 |
| `time_taken_seconds` | `IntegerField` | nullable |
| `is_completed` | `BooleanField` | default False |

Property: `accuracy = round(correct / (correct + incorrect) * 100, 1)`

### `QuestionResponse`

| Field | Type | Notes |
|---|---|---|
| `attempt` | `FK(TestAttempt, CASCADE)` | related_name=`responses` |
| `question` | `FK(Question, CASCADE)` | |
| `selected_answer` | `CharField(1)` | nullable |
| `is_correct` | `BooleanField` | nullable (None = unanswered) |
| `time_taken_seconds` | `IntegerField` | nullable |
| `is_marked_for_review` | `BooleanField` | default False |
| `confidence_level` | `IntegerField` | 1–5, nullable |

**Constraints**: `unique_together = ['attempt', 'question']`

---

## `analytics` app

### `UserTopicPerformance`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser)` | |
| `topic` | `FK(Topic)` | |
| `attempts` | `IntegerField` | |
| `correct` | `IntegerField` | |
| `accuracy` | `FloatField` | cached |
| `last_attempt_at` | `DateTimeField` | |
| `mastery_level` | `IntegerField` | 0–100 |

**Constraints**: `unique_together = ('user', 'topic')`.

### `DailyActivity`

`user`, `date`, `questions_attempted`, `correct_count`, `minutes_studied`, `tokens_spent`. Unique together `(user, date)`.

### `Feedback`

Student-facing general feedback (separate from `QuestionFeedback`): `user`, `category`, `subject`, `body`, `status`, `admin_response`.

### `Announcement` (analytics-side)

Cross-app announcements also exist here (in addition to `questions.Announcement`).

### `StudyStreak`

`user`, `current_streak`, `longest_streak`, `last_active_date`. OneToOne with CustomUser.

### `Badge` / `UserBadge`

`Badge`: `code`, `name`, `description`, `icon_url`, `criteria`.
`UserBadge`: `user`, `badge`, `earned_at`.

### `Gamification meta-models`

`Campaign` (admin messaging), `ContactUs` message store.

---

## `ai_engine` app

### `ChatSession`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`chat_sessions` |
| `title` | `CharField(200)` | auto-generated from first user message (saved in `save()` override) |
| `mode` | `CharField(20)` | `tutor` / `mnemonic` / `explain` / `textbook` / `analyze` |
| `created_at` | `DateTimeField(auto_now_add)` | |
| `updated_at` | `DateTimeField(auto_now)` | |
| `is_archived` | `BooleanField` | default False |

**Indexes**: `(user, -updated_at)`, `(user, is_archived)`

### `ChatMessage`

| Field | Type | Notes |
|---|---|---|
| `session` | `FK(ChatSession, CASCADE)` | related_name=`messages` |
| `role` | `CharField(4)` | `user` / `ai` |
| `content` | `TextField` | |
| `mode` | `CharField(20)` | blank |
| `citations` | `JSONField` | list of citation dicts |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Indexes**: `(session, created_at)`

### `AIFeedback`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, SET_NULL)` | nullable (anonymous feedback) |
| `message` | `FK(ChatMessage, CASCADE)` | related_name=`feedback` |
| `query` | `TextField` | the prompt/query sent to AI |
| `response_text` | `TextField` | the AI response being rated |
| `is_helpful` | `BooleanField` | default True |
| `report_reason` | `CharField(255)` | reason if reported |
| `comments` | `TextField` | |
| `created_at` | `DateTimeField(auto_now_add)` | |

---

## `jobs` app

### `JobCategory`
| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(100)` | |
| `slug` | `SlugField(unique=True)` | |

### `Job`
| Field | Type | Notes |
|---|---|---|
| `title` | `CharField(200)` | |
| `hospital` | `CharField(200)` | |
| `location` | `CharField(200)` | |
| `category` | `FK(JobCategory, SET_NULL)` | related_name=`jobs` |
| `description` | `TextField` | |
| `salary` | `CharField(100)` | nullable |
| `apply_link` | `URLField(500)` | |
| `posted_at` | `DateTimeField(auto_now_add)` | |
| `expires_at` | `DateTimeField` | nullable |
| `is_active` | `BooleanField` | default True |
| `eligibility_summary` | `TextField` | 6-Task Architecture |
| `exam_track_tags` | `JSONField` | list of exam codes |
| `exam_tracks` | `M2M(ExamTrack)` | related_name=`jobs` |
| `admin_edited` | `BooleanField` | protect from overwrite |

### `JobBookmark`
| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`bookmarked_jobs` |
| `job` | `FK(Job, CASCADE)` | related_name=`bookmarks` |
| `created_at` | `DateTimeField(auto_now_add)` | |

**Constraints**: `unique_together = ['user', 'job']`

---

## `django-q2`

Tables managed by `django_q` migration: `django_q_ormq`, `django_q_task`, `django_q_schedule`, `django_q_failure`, etc. Used by `video_engine/tasks.py`, `questions/tasks.py`, `ai_engine/management/`.

---

## `django-axes`

Tables: `axes_accessattempt`, `axes_accesslog`, `axes_accessfailurelog`. Tracks login attempts + lockouts.

---

## RAG store

File: `backend/chroma_db/rag_store.sqlite3` (SQLite, separate from app DB).

```sql
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document TEXT NOT NULL,
    book TEXT NOT NULL,
    page INTEGER DEFAULT 0,
    chunk_index INTEGER DEFAULT 0,
    source_file TEXT DEFAULT '',
    tokens TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS idf_cache (
    term TEXT PRIMARY KEY,
    idf REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_book ON chunks(book);
```

Approx. 5,000 chunks (4972+ per existing reports).

---

## Cross-cutting business rules

1. **Token metering**:
   - Each AI feature costs **1 token** (default).
   - Consumption priority: Free (daily→weekly minimum) → Feedback credits → Purchased.
   - Admins/staff bypass (`CustomUser.is_admin`).
   - Refund on AI failure (`TokenBalance.refund_token`).

2. **Single-device session**:
   - `CustomUser.session_key` + `UserDevice` enforce one active session.
   - Backend can return `code: 'session_invalid'` to force logout on the older device.

3. **Subscription mirror**:
   - `CustomUser.is_subscribed` is a denormalized mirror of `Subscription.status=='active'`.
   - `Subscription.activate_from_payment` keeps them in sync.

4. **AI provider rotation**:
   - `_call_counter` + `_counter_lock` (thread-safe).
   - 120 s deadline per request; per-provider timeout 15–20 s.
   - Provider errors filtered (`_PROVIDER_ERROR_PHRASES`).

5. **Brute-force protection**:
   - `django-axes` locks accounts after 5 failed attempts (30 min).

6. **Admin audit trail**:
   - Every grant/transfer/block/reset writes `AdminAuditLog`.
   - Append-only — never updated/deleted.

---

## Data lifecycle

```
Source PDFs / MD / TXT
    │
    ▼ (_train_all.py, KnowledgeUploadView)
RAG store (SQLite TF-IDF)
    │
    ▼
User query → cosine top-K → AI prompt → answer
    │
    ▼
ChatSession → ChatMessage (immutable per turn)

Question lifecycle:
  Source → Import scripts → Django DB
    → AI Enrichment (correct_answer via 3-vote, explanation, mnemonic)
    → validate_questions.py
    → _export_fixture.py → questions_fixture.json
    → build.sh → loaddata → production DB
    → DRF API → student UI
    → QuestionAttempt per attempt
    → UserTopicPerformance aggregated
```

**Retention**:
- `QuestionAttempt`, `DailyActivity`, `TokenTransaction`, `ChatMessage` grow unbounded.
- `AdminAuditLog`, `AdminAuditLog`, `PaymentAttempt` should be retained for ≥7 years (financial compliance).
- `chroma_db/rag_store.sqlite3` is the RAG cache — re-ingest rebuilds.

---

## Possible bottlenecks

### 1. SQLite write contention
- `TokenBalance.consume_token` is read-modify-write without `select_for_update` — concurrent requests can race.
- **Fix**: add `transaction.atomic()` + `select_for_update()` for token consumption (requires Postgres or SQLite ≥ 3.24).

### 2. N+1 query risk
- `Question` list endpoints with `select_related('subject', 'topic')` are present in serializers — verify all list endpoints apply it.
- `UserTopicPerformance` aggregations recompute on every read — pre-compute via background task.

### 3. JSONField scans
- `Question.concept_tags`, `Question.concept_keywords`, `Question.similar_question_ids` are `JSONField`. SQLite cannot index JSON arrays natively.
- **Fix**: PostgreSQL `GIN` index on JSONField expressions, or denormalize tags into a join table.

### 4. RAG TF-IDF scale
- `MAX_SEARCH_CHUNKS = 2000` caps memory usage.
- At 5,000+ chunks per query the linear scan is fine. Past 100k chunks, switch to vector embeddings (ChromaDB option already on disk).

### 5. Unbounded chat history
- `ChatMessage` grows per user forever.
- **Fix**: cap conversation length per session (e.g. last 50 messages) or summarize old ones.

### 6. AI quota starvation
- Single backend instance (`gunicorn --workers 1 --threads 4`) means **4 concurrent AI requests max**. Long AI calls block threads.
- **Fix**: scale to 2–4 instances behind a load balancer; or move AI calls to a queue (django-q2 already present).

### 7. Fixture churn
- `questions_fixture.json` is 5+ MB and grows. Every `loaddata` is a full table overwrite.
- **Fix**: for >10k questions, switch to `manage.py loaddata --format=jsonl` or move to a proper migration seed.

### 8. Password reset token table growth
- Django's default `password_reset_tokens` (in core) expires automatically — but if `EmailLog`-style audit is added later, watch for unbounded growth.

### 9. Subscription timezone drift
- `Subscription.expires_at` uses `timezone.now()`. If server timezone changes, expiry calculations drift. Always store UTC.

### 10. Frontend session tracking
- `X-Session-ID` is generated client-side per `localStorage` — clearing storage loses the ID. Add server-side fallback cookie.

---

## Model → API mapping

| Model | Read endpoints | Write endpoints |
|---|---|---|
| `CustomUser` | `/auth/profile/` | `/auth/register/`, `/auth/profile/` (PATCH), `/auth/admin/users/<id>/...` |
| `TokenBalance` | `/auth/tokens/` | `/auth/tokens/purchase/`, `/auth/tokens/admin/grant/` |
| `TokenConfig` | (admin only) | Django admin only |
| `TokenTransaction` | `/auth/tokens/history/`, `/auth/admin/audit-logs/` | (auto) |
| `AdminAuditLog` | `/auth/admin/audit-logs/` | (auto) |
| `PaymentAttempt` | `/auth/admin/payments/` | (auto via webhook) |
| `Subscription` | `/auth/subscribe/status/`, `/auth/admin/users/<id>/subscription/` | `/auth/subscribe/verify/`, `/auth/admin/users/<id>/subscription/` |
| `UserDevice` | `/auth/devices/` | `/auth/devices/logout/`, `/auth/admin/users/<id>/devices/` |
| `ExamTrack`, `Subject`, `Topic` | `/questions/exam-tracks/`, `/questions/subjects/`, `/questions/topics/` | (admin) |
| `Question` | `/questions/`, `/questions/<id>/` | admin / `_export_fixture.py` |
| `QuestionBookmark` | `/questions/bookmarks/` | `/questions/<id>/bookmark/` |
| `QuestionFeedback` | `/questions/feedback/` | `/questions/feedback/` |
| `Discussion` | `/questions/discussions/` | `/questions/discussions/`, `/discussions/<id>/replies/`, `/discussions/<id>/vote/` |
| `Note` | `/questions/notes/` | `/questions/notes/`, `/questions/notes/<id>/` |
| `Flashcard` | `/questions/flashcards/` | `/questions/flashcards/`, `/questions/flashcards/<id>/review/` |
| `QuestionAttempt` | `/analytics/recent-attempts/` | (auto) |
| `Test`, `TestAttempt` | `/tests/`, `/tests/attempts/` | `/tests/`, `/tests/<id>/submit/` |
| `UserTopicPerformance` | `/analytics/topic-performance/`, `/analytics/weak-topics/` | (auto) |
| `DailyActivity` | `/analytics/heatmap/` | (auto) |
| `Feedback` (analytics) | `/analytics/feedback/` | `/analytics/feedback/`, `/analytics/contact/` |
| `StudyStreak`, `Badge`, `UserBadge` | `/analytics/streak/`, `/analytics/badges/` | (auto) |
| `ChatSession`, `ChatMessage` | `/ai/chat/sessions/`, `/ai/chat/sessions/<id>/messages/` | same |
| `AIFeedback` | (admin) | `/ai/feedback/` |
| `Job`, `JobCategory` | `/jobs/`, `/jobs/categories/` | `/jobs/<id>/bookmark/` |

See [`API_REFERENCE.md`](./API_REFERENCE.md) for the full per-endpoint spec.

## `textbooks` app (verified from `backend/textbooks/models.py`)

### `Textbook`

| Field | Type | Notes |
|---|---|---|
| `name` | `CharField(200)` | |
| `author` | `CharField(200)` | |
| `edition` | `CharField(50)` | blank |
| `subject` | `FK(Subject, CASCADE)` | related_name=`textbooks` |
| `cover_image` | `ImageField` | upload_to `textbook_covers/` |
| `description` | `TextField` | blank |

### `Chapter`

| Field | Type | Notes |
|---|---|---|
| `textbook` | `FK(Textbook, CASCADE)` | related_name=`chapters` |
| `number` | `IntegerField` | |
| `title` | `CharField(300)` | |
| `topics_covered` | `M2M(Topic)` | blank |

**Constraints**: `unique_together = ['textbook', 'number']`

### `PDFUpload`

| Field | Type | Notes |
|---|---|---|
| `user` | `FK(CustomUser, CASCADE)` | related_name=`uploads` |
| `title` | `CharField(300)` | |
| `file` | `FileField` | upload_to `pdfs/` |
| `textbook` | `FK(Textbook, SET_NULL)` | nullable |
| `subject` | `FK(Subject, SET_NULL)` | nullable |
| `is_processed` | `BooleanField` | default False |
| `uploaded_at` | `DateTimeField(auto_now_add)` | |

### `TextbookChunk` — RAG chunk-level governance

| Field | Type | Notes |
|---|---|---|
| `textbook` | `FK(Textbook, CASCADE)` | nullable, related_name=`chunks` |
| `upload` | `FK(PDFUpload, CASCADE)` | nullable, related_name=`chunks` |
| `book_name` | `CharField(255)` | blank |
| `page_number` | `IntegerField` | default 0 |
| `chunk_text` | `TextField` | |
| `quality_score` | `FloatField` | default 0.0 |
| `is_approved` | `BooleanField` | default False |
| `is_rejected` | `BooleanField` | default False |
| `merged_from_ids` | `JSONField` | list of source chunk ids |
| `created_at` / `updated_at` | `DateTimeField` | |

**Indexes**: `(book_name, page_number)`, `(is_approved, is_rejected)`

### `QuestionReferenceOverride` — manual Q → Book/Page mapping

| Field | Type | Notes |
|---|---|---|
| `question` | `FK(Question, CASCADE)` | related_name=`reference_overrides` |
| `textbook` | `FK(Textbook, SET_NULL)` | related_name=`question_overrides` |
| `chapter` | `CharField(200)` | blank |
| `page_number` | `CharField(50)` | blank |
| `excerpt` | `TextField` | blank |
| `screenshot` | `ImageField` | upload_to `question_reference_overrides/`, nullable |
| `is_active` | `BooleanField` | default True |
| `created_by` | `FK(CustomUser, SET_NULL)` | |
| `created_at` / `updated_at` | `DateTimeField` | |

**Indexes**: `(question, is_active)`

