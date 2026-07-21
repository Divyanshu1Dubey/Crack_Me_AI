# Performance Audit

> Performance audit covering slow queries, missing indexes, large React components, duplicate renders, duplicate API requests, caching opportunities, memory leaks, N+1 queries, large assets, bundle size, expensive serializers, background jobs, and recommendations.

---

## Executive Summary

| Area | Risk | Headline |
|---|---|---|
| Slow queries | Medium | No DB indexes on `Question.year` / `Question.subject` / `Question.topic` for filters |
| Missing indexes | Medium-High | Most lookup columns lack indexes (Django auto-indexes FKs only) |
| Large React components | Medium | `frontend/src/app/page.tsx` is heavily dynamic-loaded — verify bundle split |
| Duplicate renders | Low | Most pages use SWR for cache; manual `useEffect`s may double-fetch |
| Duplicate API requests | Medium | `api.ts` failover can call same URL twice on timeout edge cases |
| Caching | Medium | LocMemCache only; Redis optional but not configured in prod |
| Memory leaks | Low-Medium | RAG SQLite connection + thread-local state in `ai_engine/services.py` |
| N+1 queries | High | `QuestionViewSet.list` likely N+1s without `select_related` / `prefetch_related` |
| Large assets | Medium | PDF textbooks in `Medura_Train/textbooks/` are 50+ MB each |
| Bundle size | Medium | `recharts` (~200 KB) and `react-markdown` (~100 KB) shipped to all pages |
| Expensive serializers | Medium | DRF serializer for `Question` embeds 15+ fields + JSONField |
| Background jobs | Low | `django-q2` configured but only used by `video_engine` + enrichment |

---

## 1. Slow Queries

### Identified patterns

| Query | Latency cause | Severity |
|---|---|---|
| `Question.objects.filter(subject=…, year=…, difficulty=…)` | Full table scan if no composite index | Medium |
| `QuestionAttempt.objects.filter(user=…).aggregate(avg(is_correct))` | Aggregates per request | Medium |
| `UserTopicPerformance.objects.filter(user=…).order_by('-accuracy')[:10]` | Sort + limit on small table — fine | Low |
| `Question.concept_tags` JSON lookup | SQLite cannot use index on JSONField | High |
| RAG cosine similarity | Linear scan over chunks | Medium |

### Recommendations

- Add composite index on `Question(exam_track, subject, year, difficulty)`
- Move JSON tag lookups to a join table or PostgreSQL `GIN` index
- Cache dashboard aggregates for 5 minutes in Redis

---

## 2. Missing Indexes

### Current model fields without explicit indexes (Django auto-creates indexes only for FK + `unique=True` + `Meta.indexes`)

| Model | Field | Recommended index? |
|---|---|---|
| `Question` | `year` | Yes — used in filter, sort |
| `Question` | `difficulty` | Yes |
| `Question` | `is_active` | Yes — most queries filter on this |
| `Question` | `correct_answer` | No |
| `QuestionAttempt` | `created_at` | Yes — for analytics time-range queries |
| `QuestionAttempt` | `is_correct` | Yes — for accuracy aggregations |
| `QuestionBookmark` | `user` | Already indexed (FK) |
| `TokenTransaction` | `transaction_type` | Yes |
| `TokenTransaction` | `created_at` | Yes |
| `ChatMessage` | `created_at` | Yes |
| `ChatSession` | `updated_at` | Yes |
| `DailyActivity` | `date` | Already part of `unique_together` |
| `UserTopicPerformance` | `accuracy` | Yes (for weak-topic sort) |

### Composite index candidates

```python
class Meta:
    indexes = [
        models.Index(fields=['exam_track', 'subject', 'year'], name='q_track_subj_year_idx'),
        models.Index(fields=['is_active', 'year'], name='q_active_year_idx'),
        models.Index(fields=['user', '-created_at'], name='qa_user_recent_idx'),
        models.Index(fields=['user', 'is_correct'], name='qa_user_correct_idx'),
    ]
```

Apply via a migration; safe to add without downtime on SQLite/Postgres.

---

## 3. Large React Components

### Suspected hotspots

- `frontend/src/app/page.tsx` — landing page with many `dynamic()` imports. Verify `dynamic(() => import(...), { ssr: false })` is used for heavy sections.
- `frontend/src/app/questions/page.tsx` — large filter UI + AI answer modal.
- `frontend/src/app/admin/page.tsx` — multiple tabs (users, tokens, payments, audit log) loaded eagerly.

### Recommendations

- Verify `dynamic(..., { loading: () => <Skeleton /> })` on every `dynamic()` import.
- Split `admin` page into `admin/(dashboard|users|tokens|payments|audit)` route segments.
- Profile in Chrome DevTools → Performance tab → check "Scripting" / "Rendering" time.

---

## 4. Duplicate Renders

### Patterns to verify

- `useEffect` deps arrays in pages — if missing, double-fetch on mount
- `useSWR` keys — verify they include all params (`/questions/?subject=X&year=Y`)
- React Context value objects created inline — every render creates new object → cascades to consumers

### Recommendations

- Use `useMemo` for context values (`useMemo(() => ({user, isAdmin, ...}), [user, isAdmin])`)
- Audit each `useEffect` for missing/incorrect deps
- Replace inline object props with stable references

---

## 5. Duplicate API Requests

### Patterns

- `api.ts` failover: on 502/503/504, retries against fallback URL. If the original request actually succeeded but response was lost, the same request fires twice.
- React StrictMode in dev → every effect fires twice.
- SWR with `refreshInterval` set → can fire while a tab is in background.

### Recommendations

| Fix | Effort | Impact |
|---|---|---|
| Add idempotency-key header for write endpoints | 1 day | High |
| Disable React StrictMode in production builds | 5 min | Medium |
| Set `refreshInterval: 0` for SWR on auth-gated data | 1 hour | Low |
| Add request de-duplication at api.ts layer (Map<key, Promise>) | 4 hours | Medium |

---

## 6. Caching Opportunities

### Current state
- Default Django cache = `LocMemCache` (per-process)
- `django-redis` available but not configured in production
- RAG explain-answer has 24h MD5 cache (in-process)
- AI provider status cached briefly

### Recommendations

| Cache target | TTL | Storage |
|---|---|---|
| `/api/analytics/dashboard/` | 5 min | Redis |
| `/api/questions/?...` | 1 min | Redis with cache key from filters |
| AI `explain-answer` responses | 24 h | Redis (currently in-process) |
| AI provider list | 1 h | Redis |
| TokenConfig singleton | 5 min | Redis |
| User profile | 10 min | Redis |
| Question detail | 1 h | Redis |

### High-impact first
1. Move `TokenConfig.get_config()` to a Redis-cached call (eliminates 1 DB hit per token check).
2. Move `analytics/dashboard/` to cached view (heavy aggregation).

---

## 7. Memory Leaks

### Suspected patterns

- `ai_engine/services.py` initializes provider clients in `__init__`. If `AIService()` is instantiated per request, large model objects live briefly but the GC pressure adds up.
- `RAGPipeline._conn` (sqlite3 connection) is opened once per process. Confirm `check_same_thread=False` + serialized access.
- `axios.create()` instances created per request — should be a singleton. Verify `api.ts` exports a single instance.

### Recommendations

| Fix | Effort | Impact |
|---|---|---|
| Singleton `AIService` via Django app config | 4 hours | High |
| Add `MAX_POOL_SIZE` to aiohttp/httpx clients if used | 2 hours | Medium |
| Audit `useEffect` cleanups in pages | 4 hours | Medium |
- Add Sentry performance monitoring with transaction sampling | 1 day | High |

---

## 8. N+1 Queries

### Suspected

| Endpoint | Likely N+1 |
|---|---|
| `/api/questions/` (list) | `Question.subject` + `Question.topic` lookups per row |
| `/api/analytics/performance/` | `UserTopicPerformance.topic` lookup per row |
| `/api/analytics/leaderboard/` | User lookups per row |
| `/api/ai/chat/sessions/` | `ChatSession.last_message` lookup per row |
| `/api/tests/attempts/` | `TestAttempt.test` lookup per row |

### Recommendations

```python
# questions/views.py
queryset = Question.objects.select_related('subject', 'topic').prefetch_related('bookmarks')
```

Add `select_related` / `prefetch_related` to every list-view queryset.

### Audit checklist

```python
# Add to CI: fail if a view returns > 100 queries for a single request
from django.test.utils import CaptureQueriesContext
with CaptureQueriesContext(connection) as ctx:
    response = client.get('/api/questions/')
assert len(ctx.captured_queries) < 10
```

---

## 9. Large Assets

### Identified

- `backend/Medura_Train/textbooks/*.pdf` — 50+ MB each (auto-skipped for >50 MB in RAG, but still on disk and in Git LFS)
- `data_dump.json` — 7.6 MB committed at root
- `data_dump_chunk_*.json` — chunks for migration; should be removed post-migration

### Recommendations

- Confirm Git LFS is configured for `**/textbooks/*.pdf` (per `.gitattributes`)
- Verify LFS bandwidth quota on the GitHub plan
- Add `frontend/public/icons/custom/icons-index.json` to LFS if icons are large

---

## 10. Bundle Size

### Likely contributors (from `package.json`)

| Package | Size (min+gz) | Used on every page? |
|---|---|---|
| `recharts` | ~200 KB | Only `/analytics`, `/dashboard`, `/trends` |
| `react-markdown` | ~100 KB | Only question pages + AI tutor |
| `@radix-ui/react-*` (15+ packages) | ~50 KB total | Varies |
| `axios` | ~30 KB | Yes |
| `@supabase/ssr` | ~50 KB | Conditional (only if Supabase enabled) |
| `@datadog/browser-rum` + `browser-logs` | ~80 KB | Yes |
| `lucide-react` | ~50 KB (tree-shakeable) | Yes |

### Recommendations

| Fix | Effort | Impact |
|---|---|---|
| Lazy-load `recharts` only on analytics pages | 2 hours | High |
| Lazy-load `react-markdown` only on question detail / AI tutor | 2 hours | High |
| Use `next/dynamic` for Datadog init in non-prod | 1 hour | Medium |
| Audit `lucide-react` imports for tree-shaking | 1 hour | Medium |
| Consider `swr` replacement with native `fetch` + cache for small pages | 1 day | Low |

---

## 11. Expensive Serializers

### `QuestionSerializer`

Includes 20+ fields including JSONFields. For list endpoints, this is heavy.

### Recommendations

- Create `QuestionListSerializer` with only essential fields: `id`, `question_text`, `options`, `correct_answer` (hidden until answered), `year`, `subject_name`, `topic_name`, `difficulty`, `is_active`.
- Create `QuestionDetailSerializer` with everything.
- Use DRF's `SerializerMethodField` to defer expensive computed fields.

---

## 12. Background Jobs

### Current usage

- `django-q2` configured (`django_q` in INSTALLED_APPS)
- Used by `video_engine/tasks.py`, `questions/tasks.py`, `ai_engine/management/`
- Schedule: cron via `BROKER_CLASS` config

### Recommendations

| Job | Move to background? |
|---|---|
| AI enrichment of imported questions | ✓ already done |
| Score prediction recompute | ✓ should be |
| Daily free token refill | ✓ should be (currently inline) |
| Weekly free token refill | ✓ should be (currently inline) |
| Daily activity aggregation | ✓ should be |
| RAG scan + index | ✓ already done |

### Recommended cron schedule

```python
# management/commands/setup_q_schedule.py
Schedule.objects.create(
    func='accounts.tasks.refill_daily_tokens',
    schedule_type=Schedule.DAILY,
    repeats=-1,
    next_run=timezone.now().replace(hour=0, minute=5),
)
Schedule.objects.create(
    func='analytics.tasks.compute_weekly_aggregates',
    schedule_type=Schedule.WEEKLY,
    repeats=-1,
    next_run=...,
)
```

---

## 13. AI Call Performance

### Bottlenecks

- 11-provider round-robin: serial calls. If provider #3 fails after 20s timeout, provider #4 gets tried → 80s worst case for 4 failures.
- Long AI calls (RAG-grounded tutor) block gunicorn threads (only 4 threads).
- AI responses cached only in-process (LocMem) — multi-instance deployments hit origin every time.

### Recommendations

| Fix | Effort | Impact |
|---|---|---|
| Run AI calls via `django-q2` async — view returns 202 + polls | 2 days | High |
| Cache AI responses in Redis with key = MD5(prompt + provider) | 1 day | High |
| Reduce per-provider timeout to 12 s | 5 min | Medium |
| Parallel provider probing (race 3 in parallel, pick first) | 1 week | High but complex |

---

## 14. Frontend Performance Checklist

- [ ] Run `npm run build` and check bundle output sizes
- [ ] Lighthouse CI in GitHub Actions (Performance, Accessibility, Best Practices, SEO)
- [ ] Verify `<Image>` is used for all images (not `<img>`)
- [ ] Verify route prefetching (`<Link prefetch>`) on key navigation
- [ ] Verify font loading uses `next/font` (it does — layout.tsx uses Manrope + Space_Grotesk)
- [ ] Confirm Sentry + Datadog are not loaded in dev mode (otherwise dev is slow)

---

## 15. Backend Performance Checklist

- [ ] Run `python manage.py shell` and time critical queries
- [ ] Add `EXPLAIN ANALYZE` reports for top 10 queries to `docs/PERFORMANCE.md` appendix
- [ ] Verify `QuestionViewSet` uses `select_related`
- [ ] Confirm `TokenBalance.consume_token` is wrapped in `transaction.atomic()`
- [ ] Add `DATABASES['default']['CONN_MAX_AGE'] = 60` for connection reuse
- [ ] Enable `DEBUG=False` in production to disable Django debug toolbar overhead

---

## 16. Prioritized Action Plan

| Priority | Item | Effort | Impact |
|---|---|---|---|
| P0 | Add DB indexes (Question, QuestionAttempt, TokenTransaction) | 4 hours | High |
| P0 | Add `select_related` / `prefetch_related` to list views | 1 day | High |
| P1 | Move AI calls to async queue | 2 days | High |
| P1 | Cache dashboard analytics in Redis | 1 day | High |
| P1 | Lazy-load `recharts` + `react-markdown` | 2 hours | High |
| P2 | Connection pooling (`CONN_MAX_AGE`) | 5 min | Medium |
| P2 | Wrap `TokenBalance.consume_token` in atomic block | 4 hours | Medium |
| P2 | Idempotency keys for write endpoints | 1 day | Medium |
| P3 | Lighthouse CI in GitHub Actions | 1 day | Medium |
| P3 | Singleton `AIService` instance | 4 hours | Medium |

---

## 17. Monitoring

| Metric | Tool | Target |
|---|---|---|
| p50 / p95 API latency | Datadog APM | < 200 ms / < 1 s |
| AI call duration per provider | Datadog APM | < 20 s |
| DB query time | `django.db.backends` logging | < 100 ms |
| Frontend LCP | Lighthouse / Datadog RUM | < 2.5 s |
| Frontend TTI | Lighthouse | < 3.5 s |
| Error rate | Sentry | < 0.5 % |
| Gunicorn worker saturation | Render metrics | < 80 % |
| Cache hit ratio | Redis `INFO stats` | > 80 % |

---

## 18. See Also

- [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md) — security bottlenecks overlap with performance
- [`SCALING_ROADMAP.md`](./SCALING_ROADMAP.md) — performance at scale
- [`CODE_QUALITY.md`](./CODE_QUALITY.md) — code-smell fixes often improve performance
