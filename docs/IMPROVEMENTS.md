# Top 100 Improvements

> Ranked by **Impact × Effort × Time × Business Value × Revenue × UX × Priority**.

Each item scored 1–5 (5 = best). Final score = weighted sum (Priority × 2 + Impact × 2 + Business Value × 1.5 + Revenue × 1 + UX × 1 + Difficulty×−0.5).

---

## Tier 0 — Critical (P0) — Do this quarter

| # | Improvement | Impact | Difficulty | Time | Value | Revenue | UX | Score |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 1 | Move from SQLite to Postgres (set `DATABASE_URL`) | 5 | 2 | 1d | 5 | 3 | 3 | **21.5** |
| 2 | Move from Render free to Render paid (or DO) | 5 | 1 | 0.5d | 5 | 3 | 5 | **20.5** |
| 3 | Add DRF throttling (`UserRateThrottle`, `AnonRateThrottle`) | 5 | 2 | 1d | 4 | 1 | 3 | **17.0** |
| 4 | Add `select_related` / `prefetch_related` to list views | 5 | 2 | 1d | 3 | 0 | 4 | **15.0** |
| 5 | Add DB indexes (Question, QuestionAttempt, TokenTransaction) | 5 | 1 | 0.5d | 3 | 0 | 4 | **15.0** |
| 6 | Add email verification on registration | 4 | 3 | 1d | 5 | 2 | 4 | **19.0** |
| 7 | Add CAPTCHA on register/login/password-reset | 4 | 2 | 0.5d | 4 | 1 | 3 | **15.5** |
| 8 | Validate file-upload magic bytes + size limits | 5 | 2 | 0.5d | 4 | 0 | 3 | **16.0** |
| 9 | Switch JWT to short-lived access + rotated refresh | 4 | 1 | 0.5d | 4 | 0 | 2 | **13.0** |
| 10 | Wrap `TokenBalance.consume_token` in `transaction.atomic()` | 4 | 2 | 0.5d | 3 | 1 | 2 | **13.0** |
| 11 | Add `DATABASES['default']['CONN_MAX_AGE']` | 3 | 1 | 5 min | 3 | 0 | 3 | **10.5** |
| 12 | Remove dead code (`_import_pyq_*`, `_fix_and_enrich_answers`, etc.) | 2 | 1 | 0.5d | 3 | 0 | 2 | **8.5** |
| 13 | Add coverage CI gate (`coverage.py --fail-under=70`) | 4 | 2 | 0.5d | 3 | 0 | 1 | **11.5** |
| 14 | Add canonical URLs to every page | 4 | 2 | 0.5d | 4 | 1 | 3 | **14.5** |
| 15 | Add Organization + WebSite JSON-LD on landing | 3 | 1 | 0.5d | 3 | 1 | 2 | **10.5** |
| 16 | Lazy-load `recharts` and `react-markdown` | 4 | 1 | 0.5d | 3 | 0 | 5 | **13.0** |
| 17 | Add Lighthouse CI to GitHub Actions | 4 | 2 | 1d | 3 | 1 | 3 | **13.0** |
| 18 | Verify `RECOVERED_KEYS.txt` is git-ignored | 5 | 1 | 5 min | 5 | 0 | 1 | **14.5** |
| 19 | Add `pip-audit` to CI | 4 | 1 | 0.5d | 4 | 0 | 0 | **11.5** |
| 20 | Add proper 404 / 500 error pages (frontend) | 3 | 1 | 0.5d | 3 | 0 | 4 | **11.0** |

---

## Tier 1 — High (P1) — Do next quarter

| # | Improvement | Impact | Difficulty | Time | Value | Revenue | UX | Score |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 21 | Move AI calls to async queue (django-q2) | 5 | 4 | 3d | 5 | 3 | 3 | **19.0** |
| 22 | Cache dashboard analytics in Redis (5-min TTL) | 5 | 3 | 1d | 3 | 1 | 4 | **16.0** |
| 23 | Migrate from `google-generativeai` to `google-genai` | 3 | 2 | 1d | 3 | 0 | 0 | **9.0** |
| 24 | Split `accounts/views.py` into auth/profile/tokens/admin/subs/devices | 5 | 4 | 3d | 3 | 0 | 2 | **15.0** |
| 25 | Split `questions/views.py` into questions/flashcards/discussions/notes | 5 | 4 | 3d | 3 | 0 | 2 | **15.0** |
| 26 | Refactor `AIService` god class into smaller services | 4 | 5 | 5d | 4 | 0 | 1 | **13.5** |
| 27 | Cache AI responses in Redis (currently LocMem only) | 5 | 2 | 1d | 3 | 2 | 4 | **16.5** |
| 28 | Add `IsSuperUser` instead of `IsAdminUser` to admin-only endpoints | 4 | 1 | 1d | 4 | 0 | 0 | **11.5** |
| 29 | Add structured log shipping to Datadog | 4 | 2 | 1d | 3 | 0 | 1 | **11.5** |
| 30 | Add FAQPage schema on landing page | 3 | 1 | 0.5d | 3 | 1 | 2 | **10.5** |
| 31 | Add `Breadcrumbs` component + `BreadcrumbList` schema | 3 | 2 | 1d | 3 | 0 | 4 | **11.0** |
| 32 | Add Blog / Articles section for SEO | 4 | 4 | 5d | 5 | 3 | 3 | **17.0** |
| 33 | Add Stripe for international payments | 4 | 3 | 2d | 4 | 5 | 2 | **17.0** |
| 34 | Add Cloudflare in front of Render | 5 | 2 | 1d | 4 | 0 | 3 | **16.5** |
| 35 | Add WAF rules + DDoS protection | 4 | 2 | 1d | 4 | 0 | 1 | **12.5** |
| 36 | Add 2FA for admin accounts | 4 | 3 | 2d | 5 | 1 | 2 | **14.5** |
| 37 | Add WebAuthn / passkey support | 4 | 5 | 5d | 4 | 1 | 5 | **16.0** |
| 38 | Add OAuth (Google, Apple) via Supabase | 3 | 2 | 2d | 4 | 2 | 5 | **14.0** |
| 39 | Add idempotency keys for write endpoints | 4 | 3 | 1d | 4 | 0 | 2 | **13.0** |
| 40 | Add hCaptcha to auth flows | 4 | 2 | 0.5d | 4 | 0 | 1 | **12.5** |

---

## Tier 2 — Medium (P2) — Do in 2 quarters

| # | Improvement | Impact | Difficulty | Time | Value | Revenue | UX | Score |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 41 | Add Question content moderation UI for admins | 4 | 3 | 3d | 4 | 1 | 3 | **14.0** |
| 42 | Add bulk CSV import with admin approval workflow | 4 | 3 | 3d | 5 | 1 | 3 | **15.0** |
| 43 | Add "Study streak freeze" feature (engagement) | 3 | 2 | 1d | 3 | 1 | 5 | **12.0** |
| 44 | Add "Daily challenge" with bonus tokens | 4 | 3 | 2d | 4 | 2 | 5 | **15.5** |
| 45 | Add "Achievements / Badges" unlock UI polish | 3 | 2 | 1d | 3 | 1 | 5 | **12.0** |
| 46 | Add Push notifications (web push API) | 4 | 4 | 3d | 4 | 1 | 5 | **15.5** |
| 47 | Add Email digest (weekly progress email) | 4 | 3 | 2d | 5 | 2 | 4 | **16.5** |
| 48 | Add SMS notifications (Twilio) for important events | 3 | 4 | 3d | 4 | 1 | 4 | **13.5** |
| 49 | Add Telegram bot for daily question | 4 | 3 | 2d | 4 | 1 | 5 | **15.5** |
| 50 | Add referral program (invite friends → bonus tokens) | 5 | 3 | 2d | 5 | 4 | 4 | **19.0** |
| 51 | Add quiz customization (negative marking, time per question) | 3 | 2 | 1d | 3 | 1 | 4 | **11.0** |
| 52 | Add "compare with friends" feature | 3 | 3 | 2d | 3 | 1 | 5 | **12.5** |
| 53 | Add offline mode (PWA with cached questions) | 4 | 5 | 5d | 4 | 0 | 5 | **15.5** |
| 54 | Add mobile app (React Native / Expo) | 5 | 5 | 30d | 5 | 4 | 5 | **20.5** |
| 55 | Add Hindi / regional language support | 4 | 5 | 10d | 5 | 3 | 4 | **18.5** |
| 56 | Add Spaced repetition auto-suggestion for incorrect attempts | 4 | 3 | 2d | 4 | 1 | 4 | **14.5** |
| 57 | Add AI-generated flashcards from topic | 4 | 3 | 2d | 3 | 1 | 5 | **14.5** |
| 58 | Add video explanations (TTS slides — video_engine) | 3 | 4 | 5d | 4 | 1 | 5 | **14.5** |
| 59 | Add live exam (timed multi-user) | 3 | 5 | 10d | 4 | 1 | 5 | **14.0** |
| 60 | Add AI tutor personality / depth selection | 3 | 3 | 2d | 3 | 1 | 4 | **11.5** |

---

## Tier 3 — Lower (P3) — Roadmap items

| # | Improvement | Impact | Difficulty | Time | Value | Revenue | UX | Score |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 61 | Add international expansion (Bangladesh, Nepal, Pakistan) | 5 | 5 | 30d | 5 | 5 | 3 | **21.0** |
| 62 | Add B2B / college licensing tier | 5 | 5 | 20d | 5 | 5 | 2 | **21.0** |
| 63 | Add API monetization (institutions pay for AI tutor) | 5 | 5 | 15d | 5 | 5 | 1 | **20.5** |
| 64 | Add self-hosted LLM as primary (Llama 3.1 70B) | 4 | 5 | 15d | 4 | 4 | 1 | **16.5** |
| 65 | Add custom fine-tuned medical LLM | 5 | 5 | 30d | 5 | 4 | 2 | **20.5** |
| 66 | Add on-device inference for offline mode | 4 | 5 | 10d | 3 | 1 | 5 | **15.0** |
| 67 | Add voice-based tutor (Web Speech API) | 4 | 4 | 5d | 3 | 1 | 5 | **15.0** |
| 68 | Add image-based question input (OCR) | 3 | 4 | 5d | 3 | 0 | 4 | **11.0** |
| 69 | Add collaborative study rooms (real-time) | 3 | 5 | 15d | 3 | 1 | 5 | **12.5** |
| 70 | Add peer-to-peer doubt marketplace | 3 | 5 | 20d | 3 | 2 | 4 | **12.5** |
| 71 | Add marketplace for user-generated content | 4 | 5 | 20d | 4 | 3 | 3 | **15.5** |
| 72 | Add SEO content farm (200+ articles/quarter) | 5 | 4 | 15d | 5 | 3 | 2 | **19.5** |
| 73 | Add YouTube channel + auto-transcribe for SEO | 4 | 4 | 10d | 5 | 3 | 3 | **17.0** |
| 74 | Add Wikipedia citations for medical claims | 3 | 3 | 5d | 4 | 0 | 2 | **11.5** |
| 75 | Add SOC 2 Type II audit | 4 | 5 | 60d | 5 | 2 | 0 | **16.5** |
| 76 | Add GDPR data deletion flow | 4 | 3 | 5d | 5 | 0 | 1 | **13.5** |
| 77 | Add cookie consent banner | 3 | 1 | 0.5d | 4 | 0 | 1 | **9.5** |
| 78 | Add Penetration testing (annual) | 4 | 4 | 10d | 5 | 0 | 0 | **14.0** |
| 79 | Add Bug bounty program | 4 | 3 | 5d | 5 | 0 | 0 | **14.0** |
| 80 | Add Multi-region deployment | 5 | 5 | 30d | 5 | 2 | 3 | **20.0** |

---

## Tier 4 — Code health (P4) — Continuous

| # | Improvement | Impact | Difficulty | Time | Value | Revenue | UX | Score |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 81 | Replace LocMemCache with Redis in production | 4 | 2 | 1d | 3 | 0 | 2 | **12.0** |
| 82 | Pin upper bounds on requirements.txt | 3 | 1 | 2h | 3 | 0 | 0 | **8.0** |
| 83 | Remove unused packages (`together`, `aiml`) | 2 | 1 | 1h | 2 | 0 | 0 | **5.5** |
| 84 | Add `Singleton AIService` instance | 3 | 2 | 0.5d | 3 | 0 | 1 | **9.5** |
| 85 | Add TypeScript types for all API responses | 4 | 3 | 3d | 4 | 0 | 4 | **14.5** |
| 86 | Add Storybook for component library | 3 | 3 | 3d | 3 | 0 | 3 | **10.5** |
| 87 | Add frontend component tests (Vitest) | 4 | 3 | 5d | 4 | 0 | 2 | **13.5** |
| 88 | Add backend integration tests for AI flows | 4 | 3 | 5d | 4 | 0 | 1 | **13.0** |
| 89 | Add OpenAPI / Swagger docs (drf-spectacular) | 3 | 2 | 1d | 3 | 0 | 4 | **11.0** |
| 90 | Add GraphQL as alternative to REST | 3 | 5 | 10d | 2 | 0 | 4 | **9.5** |
| 91 | Migrate from `pyq_extractor.py` heuristics to ML model | 3 | 4 | 10d | 3 | 0 | 0 | **9.5** |
| 92 | Add A/B testing framework (Statsig) | 4 | 3 | 2d | 4 | 2 | 3 | **15.0** |
| 93 | Add Feature flags service (Unleash) | 4 | 3 | 2d | 4 | 1 | 3 | **14.5** |
| 94 | Add Real-user monitoring (Datadog RUM verify) | 4 | 1 | 0.5d | 4 | 0 | 3 | **12.5** |
| 95 | Add custom MLOps pipeline for AI quality scoring | 3 | 4 | 10d | 4 | 0 | 0 | **11.0** |
| 96 | Add CI/CD canary deploys | 4 | 4 | 5d | 4 | 0 | 1 | **13.5** |
| 97 | Add DR drill documentation | 3 | 2 | 2d | 4 | 0 | 0 | **9.5** |
| 98 | Add runbook for common incidents | 3 | 2 | 2d | 4 | 0 | 0 | **9.5** |
| 99 | Add on-call rotation + PagerDuty | 4 | 2 | 1d | 5 | 0 | 0 | **12.0** |
| 100 | Add status page (statuspage.io) | 4 | 1 | 0.5d | 5 | 0 | 3 | **12.5** |

---

## Roadmap View (by quarter)

### Q1 — Critical fixes
1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20

### Q2 — Performance + UX
21, 22, 24, 25, 27, 32, 33, 34, 36, 37, 38, 39, 40

### Q3 — Engagement + Growth
44, 46, 47, 49, 50, 54, 55, 57

### Q4 — International + B2B
61, 62, 63, 72, 73, 75

### Continuous
All Tier 4 items (81–100)

---

## See Also

- [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md) — feeds P0/P1 security fixes
- [`PERFORMANCE.md`](./PERFORMANCE.md) — feeds P1 performance fixes
- [`CODE_QUALITY.md`](./CODE_QUALITY.md) — feeds P4 code health
- [`SCALING_ROADMAP.md`](./SCALING_ROADMAP.md) — long-term scale plan
