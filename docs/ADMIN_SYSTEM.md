# Admin System

> Admin dashboard, permissions, admin APIs, moderation flow, and management features.

---

## 1. Admin Surfaces

CrackCMS exposes **three parallel admin surfaces**:

| Surface | Audience | URL | Auth |
|---|---|---|---|
| **Django Admin** | Superusers | `/admin/` | `is_staff=True` |
| **In-app admin page** | Admins & superusers | `/admin` (Next.js) | `role='admin' or is_superuser`, read from the backend profile (`/api/auth/profile/`) |
| **REST admin APIs** | Scripts + admin SPA | `/api/auth/admin/*`, `/api/auth/tokens/admin/*`, `/api/analytics/admin/*`, `/api/imports/*`, `/api/ingestion/*`, `/api/key-audit/*` | `IsControlTowerAdmin`: `role='admin'` or `is_superuser` |

The answer-key review queue (`/admin/review-queue`, API `/api/key-audit/`) lists questions whose key may be
wrong, by priority, with the printed source keys and AI review signals behind each; decisions go through
`change_answer_key` and are recorded as `AuditResolution` + `AdminAuditLog` (`audit_resolution`). See
[`ANSWER_KEY_AUDIT.md`](./ANSWER_KEY_AUDIT.md).

The Next.js `/admin` page consumes the REST admin APIs and renders user/token/payment tables. The Next.js middleware only requires a signed-in user for `/admin`; each admin page sends non-admins to `/dashboard` based on the backend profile's `role` / `is_admin` (Supabase `user_metadata` is never trusted), and every admin API checks the role again. Django Admin is the canonical place for content moderation (questions, subjects, topics, flashcards).

---

## 2. Permission Model

```
Superuser (is_superuser=True)
  ├── Django Admin: all models, all actions
  └── Everything an Admin can do

Admin (role='admin'; is_staff is set on sign-in for admins)
  ├── In-app /admin pages
  ├── REST admin: every IsControlTowerAdmin endpoint
  │     (token grant/transfer, user lifecycle, system operations,
  │      backup/restore, campaigns, weak-area control, imports, ingestion)
  ├── Read AdminAuditLog (all actions)
  └── Run RAG knowledge scan / Import Center (IsAdminUser: is_staff)

Staff (is_staff=True)
  └── Django Admin (limited to models with `has_module_permission`)

User (role='student')
  └── No admin access
```

**Key distinction**: Django admin allows **Django-permission-based** granularity (per-model add/change/delete), while REST admin uses a coarser `IsControlTowerAdmin` check (`role='admin'` or `is_superuser`).

---

## 3. Admin REST API Map

All endpoints under `/api/auth/` and `/api/analytics/admin/`. Authentication via Bearer token + `IsControlTowerAdmin` permission (throttle scope `admin_control_tower`, 180/min).

### 3.1 User Lifecycle (`/api/auth/admin/`)

| Method | Path | Body | Effect |
|---|---|---|---|
| GET | `/users/` | `?role=&is_blocked=&search=&page=` | Paginated user list |
| PATCH | `/users/<id>/block/` | `{ "blocked": true, "reason": "..." }` | Toggle `is_active=False` + log audit |
| PATCH | `/users/<id>/role/` | `{ "role": "admin" }` | Promote/demote user role |
| POST | `/users/<id>/reset-progress/` | (none) | Wipe user's `QuestionAttempt` + analytics rows |
| GET | `/users/<id>/devices/` | — | List user's `UserDevice` rows |
| PATCH | `/users/<id>/subscription/` | `{ "plan": "admin_grant" }` | Manually grant subscription |
| GET | `/payments/` | — | All `PaymentAttempt` rows |

### 3.2 Token Management (`/api/auth/tokens/admin/`)

| Method | Path | Body | Effect |
|---|---|---|---|
| GET | `/users/` | — | All users + balances |
| POST | `/grant/` | `{ "user_id", "amount", "note" }` | Adjust any user's balance; logs `AdminAuditLog` with action=`token_grant` or `token_revoke` |
| POST | `/transfer/` | `{ "from_user_id?", "to_user_id", "amount", "note" }` | Move tokens between users; logs `token_transfer` |
| GET | `/audit-logs/` | — | Paginated `AdminAuditLog` |

### 3.3 System Operations (`/api/auth/admin/system/`)

| Method | Path | Body | Effect |
|---|---|---|---|
| POST | `/reset-attempts/` | `{ "scope": "user", "user_id": 42 }` or `{ "scope": "all", "confirm": "RESET ALL" }` | Bulk-reset test attempts |
| POST | `/clear-analytics/` | same shape | Wipes `UserTopicPerformance`, `DailyActivity` |
| POST | `/rerun-evaluation/` | same shape | Rebuilds `UserTopicPerformance` (subject-level and per-topic rows) from test answers and question-bank answers; `results` adds `subject_rows_created` and `processed_qbank_answers` (`processed_responses` counts answered responses only) |
| POST | `/backup-data/` | (none) | Writes the core configuration data to the JSON fixture at `CORE_DATA_BACKUP_PATH` |
| POST | `/restore-data/` | (none) | Loads that same file |

`scope` is required (`400` when missing or misspelled); `scope=all` without `confirm: "RESET ALL"` is `400 {code: "confirmation_required"}`. Backup / restore answer `503 {code: "backup_not_configured"}` in production until `CORE_DATA_BACKUP_PATH` points at a persistent volume (`manage.py backup_core_data --output PATH` / `restore_core_data --input PATH` work regardless).

### 3.4 Analytics Admin (`/api/analytics/admin/`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin-dashboard/` | Cross-user aggregate: total users, active today, total attempts, total tokens sold |
| POST | `/weak-area-control/` | `{ "topic_id": 5, "threshold": 0.6 }` — adjust weak-topic detection threshold |
| GET / POST | `/campaigns/` | List / create in-app campaigns (announcements); a future `scheduled_for` makes it `scheduled`, else `draft` |
| POST | `/campaigns/<id>/send-now/` | Publish in-app now: dashboard feed and notification bell (no email or push). `delivery_count` = audience size; a future `scheduled_for` is moved to now. `400 {code: "expired"}` when `expires_at` has passed (set a later expiry first). |

### 3.5 AI Knowledge Admin (`/api/ai/`)

| Method | Path | Description |
|---|---|---|
| POST | `/knowledge/upload/` | Upload a single PDF/MD/TXT to RAG |
| POST | `/knowledge/scan/` | Trigger scan of `backend/Medura_Train/` |
| GET | `/knowledge/stats/` | `{ "chunks": 4972, "sources": 79 }` |

---

## 4. Audit Trail

Every sensitive admin operation writes an immutable `AdminAuditLog` row:

| Field | Purpose |
|---|---|
| `actor` | Admin who performed the action (`SET_NULL` on delete to preserve history) |
| `action` | machine-readable code (e.g. `token_grant`, `user_block`) |
| `resource_type` | what kind of object (e.g. `token_balance`, `user`) |
| `resource_id` | stringified PK |
| `detail` | human-readable description |
| `metadata` | structured JSON of extra context |
| `created_at` | timestamp |

**Actions logged**:
- `token_grant` / `token_revoke` / `token_transfer` / `token_view`
- `user_view` / `user_block` / `user_role_update` / `user_progress_reset`
- `system_attempt_reset` / `system_analytics_clear` / `system_rerun_evaluation`

---

## 5. Moderation Flow (Question Content)

```mermaid
flowchart TD
    A[New question submitted via API / admin] --> B{Content review?}
    B -- Auto via AI enrichment --> C[3-vote AI multi-model consensus]
    C --> D{Majority?}
    D -- Yes (≥2/3) --> E[Set correct_answer automatically]
    D -- No --> F[Flag for manual review]
    B -- Manual via CSV review --> G[_review_and_fix_answers.py]
    F --> G
    G --> H[Reviewer edits CSV in Excel]
    H --> I[Import CSV with --fix flag]
    I --> J[Validate via validate_questions.py]
    J --> K{Issues?}
    K -- Yes --> L[Fix + re-export fixture]
    K -- No --> M[Export fixture - historical, see note below]
    L --> M
    M --> N[Commit + push → Render deploys]
```

See [`guides/QUESTION_MANAGEMENT.md`](./guides/QUESTION_MANAGEMENT.md) for the canonical workflow.

Current state: `_review_and_fix_answers.py`, `validate_questions.py` and `questions_fixture.json` no longer exist, and a deploy does not load a fixture over a live bank (`build.sh` runs `seed_question_bank`, which loads `backend/fixtures/cms_fixture.json` only into an empty bank). Question edits in the admin editor / REST API are the live data. AI-generated explanations (`POST /api/questions/<id>/generate-explanation/`) are never marked "Verified by Admin"; verification is the separate `verify` action.

---

## 6. Token Grant / Revoke Lifecycle

```mermaid
sequenceDiagram
    participant A as Admin
    participant API as Django
    participant DB as SQLite
    participant T as Target User

    A->>API: POST /api/auth/tokens/admin/grant/ {user_id, amount, note}
    API->>API: Permission check: IsControlTowerAdmin
    API->>DB: BEGIN TRANSACTION
    API->>DB: TokenBalance.add_purchased_tokens(amount)
    API->>DB: INSERT TokenTransaction(type='admin_grant')
    API->>DB: INSERT AdminAuditLog(actor=A, action='token_grant', resource_id=user_id, detail=note)
    API->>DB: COMMIT
    API-->>A: 200 OK {new_balance}
    Note over T: User sees new balance on next /api/auth/tokens/ call
```

---

## 7. Subscription Management (Admin)

Admins can:
- Manually grant a subscription without payment: `PATCH /api/auth/admin/users/<id>/subscription/` with `{ "plan": "admin_grant" }`
- View all payment history: `GET /api/auth/admin/payments/`
- Receive webhook events from Razorpay: `POST /api/auth/subscribe/webhook/` (auto-creates `Subscription`)

---

## 8. Bulk Operations

| Operation | API | Use case |
|---|---|---|
| Reset attempts globally | `POST /api/auth/admin/system/reset-attempts/ {"scope":"all","confirm":"RESET ALL"}` | New test cycle |
| Clear analytics globally | `POST /api/auth/admin/system/clear-analytics/ {"scope":"all","confirm":"RESET ALL"}` | New academic year |
| Rebuild topic performance | `POST /api/auth/admin/system/rerun-evaluation/ {"scope":"all","confirm":"RESET ALL"}` | After a scoring fix |
| Backup data | `POST /api/auth/admin/system/backup-data/` | Pre-deploy safety (needs `CORE_DATA_BACKUP_PATH`) |
| Restore from backup | `POST /api/auth/admin/system/restore-data/` | Disaster recovery (reads `CORE_DATA_BACKUP_PATH`) |

All bulk operations write `AdminAuditLog` with `action`=`system_*`.

---

## 9. Django Admin Highlights

Django Admin (`/admin/`) is the canonical content-moderation surface. Most useful models:

| Model | Use |
|---|---|
| `questions.Question` | Add/edit MCQs; bulk activate/deactivate |
| `questions.Subject`, `questions.Topic` | Taxonomy curation |
| `questions.Flashcard` | Audit flashcards |
| `accounts.CustomUser` | Inspect users, role changes |
| `accounts.TokenBalance`, `accounts.TokenTransaction` | Audit token usage |
| `ai_engine.ChatSession`, `ai_engine.ChatMessage` | Inspect AI history (privacy-sensitive) |
| `textbooks.Textbook`, `textbooks.PDFUpload` | Upload new textbooks |
| `analytics.Feedback` | Triage user feedback |
| `accounts.AdminAuditLog` | Read-only audit trail |

---

## 10. Frontend Admin Page (`/admin`)

`frontend/src/app/admin/page.tsx` is a client-rendered admin SPA. It calls:

- `/api/auth/admin/users/` — user list with search/filter
- `/api/auth/tokens/admin/users/` — token balances
- `/api/auth/admin/payments/` — payment history
- `/api/auth/tokens/admin/audit-logs/` — audit timeline
- `/api/analytics/admin-dashboard/` — aggregate stats

**Tabs**: Dashboard · Users · Tokens · Payments · Audit Log · Campaigns · Knowledge Base.

---

## 11. Security Considerations

- **All REST admin endpoints require `IsControlTowerAdmin`** (`role='admin'` or `is_superuser`); the knowledge-base and Import Center endpoints use `IsAdminUser` (`is_staff`).
- **Admin accounts and Supabase**: an admin / staff row links to a Supabase identity automatically only for a trusted admin identity or the identity it was created from; others get `401 account_link_required` until an operator runs `manage.py link_supabase_identity` (see [`AUTHENTICATION.md`](./AUTHENTICATION.md) §4.1). Admins are exempt from the device limit.
- **Every mutation writes `AdminAuditLog`** — there is no silent admin path.
- **Superuser creation**: `python manage.py createsuperuser` (CLI only; not exposed via API).
- **No API for promoting a user to superuser** — must go through Django shell or admin.
- **Admin logout** should also clear Supabase session (`clearSupabaseLocalSession()`).
- **Backup files** should be stored encrypted at rest and rotated regularly.

---

## 12. Future Admin Improvements

- Two-person approval for high-impact ops (`token_transfer`, `system_reset_*`).
- Time-bound admin actions (e.g. block user for 24 hours).
- Bulk CSV import for questions with admin approval workflow.
- Role-based access beyond student/admin (e.g. content moderator, support).
- Admin-only analytics: cohort retention, funnel analysis.
- Audit log retention policy + S3 archival.
