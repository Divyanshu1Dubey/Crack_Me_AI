# Features

> Implementation reference for every feature shipped in CrackCMS.
> For each: purpose, business value, frontend files, backend files, models, APIs, user flow, dependencies, future improvements.

---

## Table of Contents

1. [User Authentication & Profile](#1-user-authentication--profile)
2. [Subscription & Payments (Razorpay)](#2-subscription--payments-razorpay)
3. [Password Reset](#3-password-reset)
4. [Single-Device Session Management](#4-single-device-session-management)
5. [Token Economy](#5-token-economy)
6. [Admin Token & User Lifecycle Management](#6-admin-token--user-lifecycle-management)
7. [Question Bank](#7-question-bank)
8. [Bookmarks & Notes](#8-bookmarks--notes)
9. [Discussions](#9-discussions)
10. [Flashcards (SM-2)](#10-flashcards-sm-2-spaced-repetition)
11. [Adaptive Tests & PYQ Simulator](#11-adaptive-tests--pyq-simulator)
12. [AI Tutor (RAG Chat)](#12-ai-tutor-rag-enhanced-chat)
13. [Explain After Answer](#13-explain-after-answer)
14. [Concept Explainer & Mnemonic Generator](#14-concept-explainer--mnemonic-generator)
15. [Study Plan & High-Yield Topics](#15-study-plan--high-yield-topics)
16. [AI Question Generator](#16-ai-question-generator)
17. [Textbook Library & RAG Knowledge Base](#17-textbook-library--rag-knowledge-base)
18. [Analytics Dashboard](#18-analytics-dashboard)
19. [Streaks, Badges & Leaderboard](#19-streaks-badges--leaderboard)
20. [Feedback & Contact](#20-feedback--contact)
21. [AI Chat Sessions & History](#21-ai-chat-sessions--history)
22. [Resources Catalog](#22-resources-catalog)
23. [Jobs / Career Listings](#23-jobs--career-listings)
24. [Video Engine (TTS Slides)](#24-video-engine-tts-slides)
25. [SEO & Marketing Pages](#25-seo--marketing-pages)

---

## 1. User Authentication & Profile

### Purpose
Register, log in, manage profile.

### Business Value
Foundation for all personalized features.

### Files
- Frontend: `frontend/src/lib/auth.tsx`, `supabase.ts`, `app/auth/login`, `app/auth/register`, `app/settings/`
- Backend: `backend/accounts/views.py` (`RegisterView`, `LoginView`, `ProfileView`), `serializers.py`, `supabase_auth.py`, `supabase_rest_auth.py`, `middleware.py`, `permissions.py`, `admin.py`

### Models
- `accounts.CustomUser` (extends `AbstractUser`)
- `accounts.UserDevice`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register |
| POST | `/api/auth/login/` | Login (JWT) |
| GET | `/api/auth/profile/` | Get profile |
| PUT/PATCH | `/api/auth/profile/` | Update profile |
| POST | `/api/auth/verify-scholarship/` | Scholarship quiz |

### Flow
1. User submits register form.
2. Backend creates `CustomUser` + `TokenBalance` (10 free daily tokens seeded).
3. Optional Supabase signup mirrors identity.
4. Frontend stores Supabase session; Axios attaches `Authorization: Bearer …`.
5. Subsequent requests authenticated via middleware → DRF view.

### Dependencies
- `rest_framework`, `rest_framework_simplejwt`
- `django-axes` (5-failure lockout)
- `@supabase/ssr`, `@supabase/supabase-js`

### Future Improvements
- WebAuthn / passkey support
- OAuth (Google, Apple) via Supabase
- Email verification flow with templated links

---

## 2. Subscription & Payments (Razorpay)

### Purpose
Convert free users into paid subscribers and token-pack purchasers.

### Business Value
Primary revenue stream. Razorpay supports Indian payment methods (UPI, cards, netbanking).

### Files
- Frontend: `app/subscription`, `app/tokens`
- Backend: `backend/accounts/views.py` (`SubscribeView`, `SubscribeOrderView`, `SubscribeVerifyView`, `SubscriptionStatusView`, `RazorpayWebhookView`, `AdminPaymentHistoryView`)

### Models
- `accounts.Subscription`
- `accounts.PaymentAttempt`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/subscribe/order/` | Create Razorpay order |
| POST | `/api/auth/subscribe/verify/` | Verify payment signature |
| POST | `/api/auth/subscribe/webhook/` | Razorpay webhook |
| GET | `/api/auth/subscribe/status/` | Current subscription |
| GET | `/api/auth/admin/payments/` | Admin payment history |

### Flow
1. User selects plan on `/subscription`.
2. Frontend → `POST /api/auth/subscribe/order/` → Razorpay order ID.
3. Razorpay checkout completes.
4. Frontend → `POST /api/auth/subscribe/verify/` → backend upgrades `Subscription` + grants tokens.
5. Webhook provides authoritative confirmation.

### Dependencies
- `razorpay` SDK

### Future Improvements
- Auto-renewal reminders, coupon codes, per-feature metering.

---

## 3. Password Reset

### Files
- Frontend: `app/forgot-password`, `app/reset-password`
- Backend: `backend/accounts/views.py` (`PasswordResetRequestView`, `PasswordResetConfirmView`)

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/password-reset/` | Request reset email |
| POST | `/api/auth/password-reset/confirm/` | Confirm with token |

### Flow
1. User submits email → backend generates one-time token, sends SMTP email with `FRONTEND_URL/reset-password?uid=…&token=…`.
2. User opens link, enters new password, frontend → `POST /password-reset/confirm/`.

### Dependencies
- Gmail App Password (SMTP). See [`setup/EMAIL_SETUP.md`](./setup/EMAIL_SETUP.md).

---

## 4. Single-Device Session Management

### Purpose
Prevent account sharing on paid content.

### Files
- Backend: `backend/accounts/middleware.py`, `views.py` (`UserDeviceListView`, `UserDeviceLogoutView`)
- Frontend: `frontend/src/lib/api.ts` — On `code: 'session_invalid'` → clears session, redirects

### Models
- `accounts.UserDevice`

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/devices/` | List devices |
| POST | `/api/auth/devices/logout/` | Force-logout a device |

---

## 5. Token Economy

### Files
- Backend: `backend/accounts/models.py` (`TokenBalance`, `TokenConfig`, `TokenTransaction`), `views.py` (`TokenBalanceView`, `TokenPurchaseView`, `TokenTransactionHistoryView`)

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/` | Balance |
| POST | `/api/auth/tokens/purchase/` | Buy token pack |
| GET | `/api/auth/tokens/history/` | Transaction history |

### Consumption Priority
**Daily Free (10/day, midnight reset)** → **Weekly Free (50/week, Sunday reset)** → **Feedback credits (+2/verified report)** → **Purchased**.

### Flow
1. User triggers AI feature.
2. Middleware/service checks balance.
3. Insufficient → `402 Payment Required`.
4. Sufficient → decrement 1 token from highest-priority pool → write `TokenTransaction` → call AI.

---

## 6. Admin Token & User Lifecycle Management

### Purpose
Staff tooling for grants, transfers, blocking, bulk ops.

### Files
- Backend: `backend/accounts/views.py` (AdminToken* + AdminUser* + AdminSystem* views)

### Models
- `accounts.AdminAuditLog`

### APIs (all require superuser)
| Method | Path | Description |
|---|---|---|
| GET | `/api/auth/tokens/admin/users/` | All users + balances |
| POST | `/api/auth/tokens/admin/grant/` | Grant/revoke |
| POST | `/api/auth/tokens/admin/transfer/` | Transfer |
| GET | `/api/auth/tokens/admin/audit-logs/` | Audit log |
| GET | `/api/auth/admin/users/` | Paginated user list |
| PATCH | `/api/auth/admin/users/<id>/block/` | Block/unblock |
| PATCH | `/api/auth/admin/users/<id>/role/` | Promote to admin |
| POST | `/api/auth/admin/users/<id>/reset-progress/` | Reset progress |
| POST | `/api/auth/admin/system/reset-attempts/` | Reset attempts (scope: all/user) |
| POST | `/api/auth/admin/system/clear-analytics/` | Clear analytics |
| POST | `/api/auth/admin/system/rerun-evaluation/` | Re-run scoring |
| POST | `/api/auth/admin/system/backup-data/` | Backup |
| POST | `/api/auth/admin/system/restore-data/` | Restore |

See [`ADMIN_SYSTEM.md`](./ADMIN_SYSTEM.md) for full admin permission matrix.

---

## 7. Question Bank

### Purpose
Platform's content core — 2,000+ UPSC CMS MCQs with explanations.

### Files
- Frontend: `app/questions`, `app/admin`
- Backend: `backend/questions/models.py` (`Question`, `Subject`, `Topic`, `ExamTrack`), `views.py` (`QuestionViewSet`, `SubjectViewSet`, `TopicViewSet`), `admin.py`, `serializers.py`

### Models
- `questions.ExamTrack` — UPSC CMS / NEET PG / etc.
- `questions.Subject`
- `questions.Topic`
- `questions.Question` — `correct_answer`, `explanation`, `mnemonic`, `high_yield_points`, `textbook_reference`, `concept_tags`, `difficulty`, …

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/questions/subjects/` | List subjects |
| GET | `/api/questions/topics/` | List topics |
| GET | `/api/questions/` | List questions (filter subject/year/difficulty/topic) |
| GET | `/api/questions/<id>/` | Detail |
| POST | `/api/questions/<id>/bookmark/` | Toggle bookmark |
| GET | `/api/questions/exam-tracks/` | List exam tracks |

### Flow
1. Open `/questions` → loads filtered list.
2. Filter by exam track → subject → topic → year.
3. Read question, reveal answer, optionally trigger "Explain After Answer".
4. Bookmark or save as flashcard.

See [`guides/QUESTION_MANAGEMENT.md`](./guides/QUESTION_MANAGEMENT.md) for editing workflows.

---

## 8. Bookmarks & Notes

### Files
- Backend: `backend/questions/models.py` (`QuestionBookmark`, `Note`), `views.py` (`NoteListCreateView`, `NoteDetailView`, `QuestionViewSet.bookmark`)
- Frontend: `app/bookmarks`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/questions/<id>/bookmark/` | Toggle bookmark |
| GET/POST | `/api/questions/notes/` | List/create note |
| GET/PUT/DELETE | `/api/questions/notes/<id>/` | Manage a note |

---

## 9. Discussions

### Files
- Backend: `backend/questions/models.py` (`Discussion`, `DiscussionVote`), `views.py` (`DiscussionListCreateView`, `DiscussionRepliesView`, `DiscussionVoteView`)

### APIs
| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/questions/discussions/` | List/create |
| GET/POST | `/api/questions/discussions/<id>/replies/` | Replies |
| POST | `/api/questions/discussions/<id>/vote/` | Upvote/downvote |

---

## 10. Flashcards (SM-2 Spaced Repetition)

### Files
- Backend: `backend/questions/models.py` (`Flashcard`), `views.py` (`FlashcardListCreateView`, `FlashcardDetailView`, `FlashcardReviewView`, `FlashcardAnalyticsView`)
- Frontend: `app/flashcards`

### APIs
| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/questions/flashcards/` | List/create |
| GET/PUT/DELETE | `/api/questions/flashcards/<id>/` | Detail |
| POST | `/api/questions/flashcards/<id>/review/` | Submit SM-2 review (quality 0–5) |
| GET | `/api/questions/flashcards/analytics/` | Retention stats |

### Algorithm
SM-2 updates `ease_factor`, `interval`, `next_review` based on user-graded recall quality.

---

## 11. Adaptive Tests & PYQ Simulator

### Files
- Backend: `backend/tests_engine/models.py` (`Test`, `TestAttempt`, `QuestionResponse`), `views.py` (`TestViewSet`, `TestAttemptViewSet`)
- Frontend: `app/tests`, `app/tests/[id]`, `app/simulator`

### Models
- `tests_engine.Test` — config: questions, time, filters
- `tests_engine.TestAttempt` — user's run
- `tests_engine.QuestionResponse` — per-question answer + correctness

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/tests/` | List tests |
| POST | `/api/tests/` | Create test |
| POST | `/api/tests/<id>/submit/` | Submit answers |
| GET | `/api/tests/<id>/review/` | Review results |
| GET | `/api/tests/attempts/` | List attempts |

---

## 12. AI Tutor (RAG-Enhanced Chat)

### Files
- Frontend: `app/ai-tutor`
- Backend: `backend/ai_engine/views.py` (`AskTutorView`), `services.py` (`EnhancedAIService.chat`), `rag_pipeline.py`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/tutor/` | RAG-enhanced chat tutoring |

### Flow
1. User submits question with optional subject/topic.
2. Backend queries RAG store for top-K chunks.
3. Top-K injected into system prompt.
4. AI provider pool called round-robin.
5. Response returned + cached 24 h.
6. Chat message persisted in `ChatMessage` (linked to `ChatSession`).

### Dependencies
- 11-provider AI pool + Ollama fallback
- TF-IDF RAG store
- CMS-specific system prompt (`CMS_SYSTEM_PROMPT`)

---

## 13. Explain After Answer

### Purpose
Rich post-answer explanations with structured JSON. The AI **independently verifies** the official answer key and flags mismatches.

### Response shape (verified from `services.py::explain_after_answer`)
```json
{
  "ai_verified_answer": "B",
  "answer_mismatch": false,
  "confidence_note": "",
  "is_correct": true,
  "why_correct": "4-5 line detailed explanation with mechanism/pathophysiology...",
  "why_wrong": {
    "A": "2-3 lines: Why this is wrong, key differentiator, quick trick",
    "C": "...",
    "D": "..."
  },
  "textbook_reference": {
    "book": "Harrison's Principles of Internal Medicine",
    "chapter": "Valvular Heart Disease",
    "page": "1528-1532",
    "section": "Mitral Stenosis"
  },
  "mnemonic": "I GET SMASHED — each letter explained",
  "core_concept": "Pathophysiology of acute pancreatitis",
  "topic_deep_dive": "6-8 line mini-lecture covering what, classifications, important numbers, clinical correlations, exam traps...",
  "key_differentiators": [
    "Type 1 vs Type 2 DM — autoimmune vs insulin resistance",
    "..."
  ],
  "category": "Medicine",
  "sub_category": "Endocrinology",
  "question_type": "Clinical Scenario",
  "around_concepts": ["DKA", "HHS", "diabetic ketoacidosis management", ...],
  "high_yield_points": ["Most common cause of...", "..."],
  "clinical_pearl": "In real practice, doctors typically...",
  "exam_tip": "Eliminate options by checking...",
  "quick_revision": "3-4 line ultra-concise summary",
  "pyq_frequency": "Asked every year since 2018",
  "similar_pyq": "CMS 2022 Paper 1: Asked about...",
  "citations": [{"book": "Harrison's", "page": "1528", "text": "..."}]
}
```

### Files
- Backend: `backend/ai_engine/views.py::ExplainAfterAnswerView`, `services.py::explain_after_answer`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/explain-answer/` | Structured explanation |

### Caching
24-hour cache keyed by MD5(`question_text[:200] + correct_answer`) using Django `cache.set(cache_key, result, timeout=86400)`. Not user-specific.

### AI Independence Feature
The prompt explicitly tells the AI: **"You MUST independently determine the correct answer based on medical knowledge and textbooks. Do NOT blindly accept any answer key."** This means:
- If AI agrees with official key → `answer_mismatch=false`
- If AI disagrees → `answer_mismatch=true`, `ai_verified_answer` = AI's pick, `confidence_note` = explanation

This protects students from being misled by wrong answer keys in old PYQs.

---

## 14. Concept Explainer & Mnemonic Generator

### Files
- Backend: `backend/ai_engine/views.py` (`ExplainConceptView`, `GenerateMnemonicView`)

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/explain/` | Topic explanation at chosen depth |
| POST | `/api/ai/mnemonic/` | Memory aid for topic |

---

## 15. Study Plan & High-Yield Topics

### Files
- Backend: `backend/ai_engine/views.py` (`StudyPlanView`, `HighYieldTopicsView`), `backend/analytics/views.py` (roadmap + weak-topics endpoints)
- Frontend: `app/roadmap`, `app/analytics`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/study-plan/` | AI-generated plan |
| GET | `/api/ai/high-yield/` | High-yield topics |
| GET | `/api/analytics/weak-topics/` | User's weak areas |
| GET | `/api/analytics/roadmap/` | Roadmap based on weak topics |

---

## 16. AI Question Generator

### Files
- Backend: `backend/ai_engine/views.py` (`GenerateQuestionsView`)
- Frontend: `app/generate`

### APIs
| Method | Path | Description |
|---|---|---|
| POST | `/api/ai/generate-questions/` | Returns N MCQs |

---

## 17. Textbook Library & RAG Knowledge Base

### Files
- Frontend: `app/textbooks`, `app/upload`
- Backend: `backend/textbooks/views.py` (`TextbookViewSet`, `PDFUploadViewSet`), `backend/ai_engine/views.py` (`KnowledgeUploadView`, `KnowledgeScanView`, `KnowledgeStatsView`), `backend/ai_engine/rag_pipeline.py`, `sqlite_rag.py`, `document_processor.py`, `pyq_extractor.py`, `auto_ingest.py`, `upsc_cms_knowledge.py`, `similar_questions.py`, `backend/_train_all.py`

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/textbooks/books/` | List textbooks |
| POST | `/api/textbooks/uploads/` | Upload PDF |
| POST | `/api/ai/knowledge/upload/` | Upload to RAG |
| POST | `/api/ai/knowledge/scan/` | Scan + reindex |
| GET | `/api/ai/knowledge/stats/` | KB stats |
| POST | `/api/ai/rag-search/` | Top-K chunks |
| POST | `/api/ai/rag-answer/` | RAG-grounded answer |
| POST | `/api/ai/textbook-reference/` | Reference for a question |
| GET | `/api/ai/screenshot/<qid>/` | Page screenshot |

### Ingestion Flow
```
Medura_Train/{textbooks,PYQ,web_knowledge}/ → _train_all.py → chunk → rag_store.sqlite3
```

---

## 18. Analytics Dashboard

### Files
- Frontend: `app/dashboard`, `app/analytics`, `app/trends`
- Backend: `backend/analytics/views.py` (`DashboardView`, `TopicPerformanceView`, `DailyActivityView`, `RecentAttemptsView`, `ScorePredictionView`, `PerformanceTrendView`, `WeakTopicsView`), `models.py` (`UserTopicPerformance`, `DailyActivity`)

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/dashboard/` | Aggregate |
| GET | `/api/analytics/topic-performance/` | Per-topic stats |
| GET | `/api/analytics/heatmap/` | Daily activity heatmap |
| GET | `/api/analytics/recent-attempts/` | Recent attempts |
| GET | `/api/analytics/score-prediction/` | Predicted score |
| GET | `/api/analytics/performance-trend/` | Trend line |
| GET | `/api/analytics/weak-topics/` | Accuracy < threshold |

---

## 19. Streaks, Badges & Leaderboard

### Files
- Backend: `backend/analytics/views.py` (`StudyStreakView`, `BadgeListView`, `LeaderboardView`, `AdminCampaignListCreateView`, `AdminCampaignSendNowView`), `models.py` (`StudyStreak`, `Badge`, `UserBadge`)
- Frontend: `app/leaderboard` + widgets in `app/dashboard`

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/analytics/streak/` | Current streak |
| GET | `/api/analytics/badges/` | Earned badges |
| GET | `/api/analytics/leaderboard/` | Global leaderboard |

---

## 20. Feedback & Contact

### Files
- Backend: `backend/analytics/views.py` (`FeedbackListCreateView`, `FeedbackDetailView`, `ContactUsView`, `DataExportView`, `DataExportCSVView`, `AdminWeakAreaControlView`), `backend/ai_engine/views.py` (`AIFeedbackView`)
- Frontend: `app/feedback`, `app/contact`

### APIs
| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/analytics/feedback/` | List/create |
| GET/PATCH/DELETE | `/api/analytics/feedback/<id>/` | Detail |
| POST | `/api/analytics/contact/` | Contact form |
| GET | `/api/analytics/export/` | JSON export (Google Sheets) |
| GET | `/api/analytics/export/csv/` | CSV export |

---

## 21. AI Chat Sessions & History

### Files
- Backend: `backend/ai_engine/models.py` (`ChatSession`, `ChatMessage`, `AIFeedback`), `views.py`

### APIs
| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/ai/chat/sessions/` | List/create session |
| GET | `/api/ai/chat/sessions/<id>/` | Session detail |
| GET | `/api/ai/chat/sessions/<id>/messages/` | List messages |
| POST | `/api/ai/chat/sessions/<id>/messages/add/` | Add message |

---

## 22. Resources Catalog

### Files
- Backend: `backend/resources/views.py` (`ResourceCatalogView`, `ResourceDownloadView`, `ExamGuideView`)
- Frontend: `app/resources`

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/resources/catalog/` | Catalog |
| GET | `/api/resources/download/<id>/` | Download URL |
| GET | `/api/resources/exam-guide/` | Exam guide |

---

## 23. Jobs / Career Listings

### Files
- Backend: `backend/jobs/models.py` (`JobCategory`, `Job`, `JobBookmark`), `views.py`, `urls.py`
- Frontend: `app/jobs`

### APIs
| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs/` | List jobs |
| GET | `/api/jobs/categories/` | Categories |
| POST | `/api/jobs/<id>/bookmark/` | Bookmark |

---

## 24. Video Engine (TTS Slides)

### Files
- Backend: `backend/video_engine/services.py`, `slide_renderer.py`, `tasks.py`, `views.py`, `urls.py`, `management/`

### Dependencies
- `edge-tts`, `moviepy`, `Pillow`, `django-q2`

### Future Improvements
- Frontend video player + library UI, AI-generated slide content.

---

## 25. SEO & Marketing Pages

### Files
- Frontend: `app/page.tsx`, `app/robots.ts`, `app/sitemap.ts`, `lib/seo.ts`, `components/StickyExamCta.tsx`, `components/TrafficAnalytics.tsx`

### Dependencies
- Next.js metadata API, Google Analytics (`G-MM88RT1QQK`), Datadog RUM

See [`SEO.md`](./SEO.md) for the full SEO audit.

---

## Cross-Cutting Capabilities

| Capability | Implementation |
|---|---|
| **AI round-robin** | `backend/ai_engine/services.py` |
| **RAG over SQLite + TF-IDF** | `backend/ai_engine/rag_pipeline.py`, `sqlite_rag.py` |
| **Token metering** | `backend/accounts/models.py::TokenBalance` + service-layer checks |
| **Auth (Supabase + JWT)** | `accounts/*` + `frontend/src/lib/{auth,supabase}.{tsx,ts}` |
| **Brute-force protection** | `django-axes` |
| **Single-device sessions** | `accounts/middleware.py` + `UserDevice` |
| **Structured logging** | `python-json-logger` |
| **Error tracking** | Sentry (`sentry_sdk.init` gated on `SENTRY_DSN`) |
| **Browser observability** | Datadog RUM + browser logs |
| **CI/CD** | `.github/workflows/ci.yml` |
| **Pre-commit secret scan** | `.pre-commit-config.yaml` |
| **Git LFS for binaries** | `.gitattributes` |
