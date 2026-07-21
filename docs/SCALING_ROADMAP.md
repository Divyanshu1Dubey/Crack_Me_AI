# Scaling Roadmap

> Plan for scaling CrackCMS from the current stage to **1 million users**, with per-stage infra, database, caching, search, storage, AI, payments, security, monitoring, analytics, CI/CD, SEO, hiring, and estimated monthly cost.

---

## Stage 0 — Current State (≤ 100 users)

**Today**: Single Render free-tier instance, SQLite, free-tier AI providers, no Redis, no CDN, manual deploys.

| Component | State |
|---|---|
| Backend | Render free, 1 worker / 4 threads, ~4 concurrent requests |
| Database | SQLite on ephemeral disk (data at risk on spin-down) |
| Cache | Django LocMemCache (per-process) |
| Search | TF-IDF in-process |
| Storage | Local disk + Git LFS |
| AI | 11-provider round-robin + Ollama local fallback |
| Payments | Razorpay |
| Auth | Supabase + Django JWT |
| Monitoring | Sentry + Datadog RUM (when configured) |
| CI/CD | GitHub Actions |
| SEO | Basic sitemap + robots |
| Team | Solo + small team |

**Estimated monthly cost**: $0–30 (Render free + Vercel free + free AI tier)

**Critical fixes needed before next stage**:
- Switch off Render free tier (ephemeral disk kills SQLite)
- Add `DATABASE_URL` Postgres (already supported via `dj_database_url`)
- Add Redis
- Switch email to API provider (Gmail SMTP blocked on Render free)

---

## Stage 1 — 1,000 users

**Headline**: Move to a single Render paid instance + managed Postgres + Redis.

### Infrastructure

- Backend: Render Standard plan (1 instance, 2 GB RAM)
- Database: Render Managed Postgres (Starter, 1 GB)
- Cache: Render Managed Redis (Starter, 100 MB)
- CDN: Vercel (free, already in use)
- Storage: Render persistent disk for `MEDIA_ROOT` (PDFs)

### Database

- Postgres (not SQLite)
- Connection pooling: `pgbouncer` or Render's built-in pooler
- `CONN_MAX_AGE=60`
- Run `python manage.py migrate` on every deploy
- Fixture still loaded via `loaddata questions_fixture.json`

### Caching

- Redis for: token balance cache, dashboard analytics, AI explain-answer responses (24h MD5 cache), session lookup

### Search

- Same TF-IDF (5K chunks fits in RAM)
- Add Django ORM full-text on Question text + tags as backup

### Storage

- Render persistent disk for media (PDFs)
- Cloudflare R2 for static assets (S3-compatible, zero egress)

### AI costs

- Mostly free tier (60+ RPM operational floor per `DEPLOYMENT_CAPACITY_REPORT.md`)
- Purchase DeepSeek only when all 11 + Ollama fail
- Track per-user AI spend via `TokenTransaction`

### Payments

- Razorpay live (already integrated)

### Security

- HTTPS via Vercel + Render
- CORS locked to Vercel origin
- Rate limit (Cloudflare free + `django-ratelimit`)
- Pre-commit secret scan (active)

### Monitoring

- Sentry (error tracking)
- Datadog RUM (frontend)
- Datadog APM (backend)
- UptimeRobot (free, 5-min checks)

### Analytics

- Google Analytics 4
- Mixpanel or PostHog (free tier, product analytics)
- Datadog dashboards

### CI/CD

- GitHub Actions: lint, test, build, bandit, safety
- Auto-deploy main → Render + Vercel

### SEO

- Add canonical URLs
- Add Organization + WebSite JSON-LD
- Submit sitemap to Google Search Console

### Hiring

- 1 backend dev (full-time)
- 1 frontend dev (part-time)
- 1 SRE / DevOps (fractional)

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Render Standard + Postgres + Redis | $35 |
| Vercel Pro | $20 |
| Domain | $1 |
| Datadog APM Pro | $31 |
| Sentry Team | $26 |
| Razorpay transaction fees (1% of revenue) | variable |
| Misc (email API, S3, Cloudflare Pro) | $30 |
| **Total infra** | **~$145/mo** |
| Personnel (3 people blended) | $8,000 |
| **Burn (personnel + infra)** | **~$8,150/mo** |

---

## Stage 2 — 10,000 users

**Headline**: Horizontal scaling + dedicated DB + improved AI throughput.

### Infrastructure

- Backend: 2× Render Standard (behind load balancer)
- Database: Render Managed Postgres Pro (4 GB + replicas)
- Cache: Render Managed Redis Pro (1 GB)
- Queue: Render Managed Redis (django-q2 broker)
- CDN: Cloudflare Pro in front of Vercel

### Database

- Read replica for analytics queries
- Move `DailyActivity` aggregation to materialized view (refresh nightly)
- Partition `QuestionAttempt` by month
- Add `pg_trgm` extension for fuzzy question search

### Caching

- 80%+ cache hit rate on dashboard + token balance
- Cache invalidation on user-action events (Redis pub/sub or signals)

### Search

- Postgres FTS (full-text search) on Question.text + tags
- Migrate from TF-IDF to `pgvector` for semantic question search (only if needed)

### Storage

- Cloudflare R2 for textbook PDFs
- Move Django `MEDIA_ROOT` to S3 / R2 via `django-storages`

### AI costs

- Migrate token-metered calls to async queue (django-q2 worker pool)
- Persistent Ollama on a dedicated VM (or paid tier) for fallback
- Negotiate bulk pricing with DeepSeek

### Payments

- Razorpay subscriptions + token packs
- Add international payment (Stripe) for non-Indian users

### Security

- WAF (Cloudflare Pro)
- 2FA for admins
- IP allowlist for Django admin

### Monitoring

- Datadog APM with full distributed tracing
- Custom SLO dashboards (API p95 < 1 s, AI p95 < 20 s)
- PagerDuty integration

### Analytics

- Mixpanel / PostHog
- Datadog product analytics
- Funnel: visit → register → first question → first AI explanation → subscription

### CI/CD

- Staging environment (Render preview apps)
- Feature flags (LaunchDarkly or Unleash)
- Canary deploys (Render supports traffic splitting)

### SEO

- Add Blog / Articles section
- Backlink strategy (partner sites)
- Localized landing pages (Hindi, Tamil)

### Hiring

- +1 backend dev
- +1 frontend dev
- +1 DevOps / SRE
- +1 content / SEO specialist

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Render 2× Standard + Postgres Pro + Redis Pro | $250 |
| Vercel Pro | $20 |
| Cloudflare Pro | $20 |
| Datadog APM + Logs Pro | $200 |
| Sentry Business | $80 |
| R2 / S3 | $20 |
| Misc | $50 |
| **Total infra** | **~$640/mo** |
| Personnel (6 people) | $18,000 |
| **Burn** | **~$18,700/mo** |

---

## Stage 3 — 50,000 users

**Headline**: Multi-region + dedicated search + dedicated AI gateway.

### Infrastructure

- Backend: 4–6× Render Standard + autoscaling
- Database: Postgres + read replica + connection pooler (PgBouncer)
- Cache: Redis cluster (3 nodes)
- Search: Meilisearch or Algolia for question search
- Queue: Celery + Redis (migrate from django-q2 for scale)
- AI: dedicated gateway service (FastAPI) with retry logic

### Database

- Shard `QuestionAttempt` by user_id range if > 50M rows
- Read replicas per region
- Backup strategy: PITR (point-in-time recovery) + daily snapshots to S3 Glacier

### Caching

- Multi-tier: edge (Cloudflare) → app Redis → DB
- Stale-while-revalidate for analytics

### Search

- Meilisearch for typo-tolerant question search
- `pgvector` for "similar questions" recommendations
- Indexing pipeline as a background job

### Storage

- S3 / R2 multi-region
- Lifecycle policy: textbooks → Glacier after 90 days

### AI costs

- AI gateway with cost tracking per request
- Self-hosted Llama 3.1 70B on GPU VM (for 50% of traffic)
- Negotiated enterprise rates with paid providers

### Payments

- Razorpay + Stripe
- Annual plans, family plans

### Security

- SOC 2 Type I audit preparation
- Penetration testing (annual)
- Bug bounty program (HackerOne or Bugcrowd)

### Monitoring

- Full observability: Datadog + Sentry + LogRocket
- Synthetic monitoring (Datadog)
- Custom business KPIs (daily active users, AI calls/day, subscription churn)

### Analytics

- Dedicated data warehouse (BigQuery / Snowflake)
- dbt for analytics engineering
- Mode / Metabase for self-serve dashboards

### CI/CD

- GitOps with ArgoCD or Flux
- Preview environments per PR
- Automated rollback on error rate spike

### SEO

- Massive content push: blog, video transcripts, glossary
- Programmatic SEO: `/questions/subject/{slug}`, `/questions/year/{year}`
- Backlink outreach + PR

### Hiring

- +1 platform engineer
- +1 ML engineer (RAG tuning, embeddings)
- +1 data engineer
- +1 security engineer
- +1 product manager
- +2 content moderators

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Backend (6× Standard + autoscaling) | $1,200 |
| Postgres Pro + read replica + PgBouncer | $400 |
| Redis cluster (3 nodes) | $200 |
| Meilisearch cluster | $200 |
| AI gateway + GPU VM | $1,500 |
| Datadog Enterprise | $1,500 |
| Sentry Business | $200 |
| BigQuery + dbt | $500 |
| Cloudflare Enterprise | $1,000 |
| Misc (Stripe, S3, email) | $500 |
| **Total infra** | **~$7,200/mo** |
| Personnel (15 people) | $60,000 |
| **Burn** | **~$67,200/mo** |

---

## Stage 4 — 100,000 users

**Headline**: Move off Render → Kubernetes on AWS / DigitalOcean / GCP. Multi-region.

### Infrastructure

- Backend: Kubernetes cluster (3 regions, 12–24 pods total)
- Database: Postgres (AWS RDS Multi-AZ + cross-region replicas)
- Cache: Redis (ElastiCache / Memorystore)
- Search: ElasticSearch or Meilisearch cluster
- Queue: Celery + Redis (or SQS)

### Database

- Sharding by user_id hash
- Backup: continuous WAL shipping + PITR
- Read replicas per region

### Caching

- Multi-region Redis (CRDT or per-region with TTL)
- Browser cache via service worker

### Search

- ElasticSearch for typo-tolerant + faceted search
- Custom ranking model (ML-trained)

### AI

- Self-hosted LLM cluster (Llama 3.1 70B / Mixtral)
- NVIDIA H100 GPUs
- Mix with paid providers for redundancy

### Payments

- Razorpay + Stripe + regional gateways
- Subscription engine (Recurly or Chargebee)

### Security

- SOC 2 Type II
- ISO 27001 preparation
- Continuous security scanning (Snyk, CrowdStrike)

### Monitoring

- Datadog Enterprise + on-call rotation
- PagerDuty
- Status page (statuspage.io or self-hosted)

### Analytics

- BigQuery / Snowflake
- Real-time dashboards (Looker / Tableau)

### CI/CD

- ArgoCD + Helm
- Canary deploys (Argo Rollouts)
- Progressive delivery (feature flags)

### SEO

- Aggressive content strategy (200+ blog posts/quarter)
- Localization (5+ languages)
- Programmatic landing pages per subject × exam

### Hiring

- +1 staff backend engineer
- +1 staff SRE
- +1 ML engineer (NLP, RAG optimization)
- +1 data engineer
- +1 security engineer
- +1 product manager
- +3 content moderators
- +1 customer success

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Kubernetes (3 regions) | $5,000 |
| RDS Multi-AZ + replicas | $2,500 |
| Redis cluster | $1,000 |
| ElasticSearch | $1,500 |
| Self-hosted LLM (4× H100) | $8,000 |
| Datadog Enterprise | $4,000 |
| SOC 2 audit | $2,000/quarter |
| Misc | $2,000 |
| **Total infra** | **~$26,000/mo** |
| Personnel (25 people) | $120,000 |
| **Burn** | **~$146,000/mo** |

---

## Stage 5 — 500,000 users

**Headline**: Multi-region active-active. Self-hosted LLM as primary. Cloud-only redundancy.

### Infrastructure

- Backend: Kubernetes (5 regions, 50–100 pods total, active-active)
- Database: CockroachDB or Vitess for global distribution
- Cache: Redis Enterprise (multi-region)
- Search: ElasticSearch cluster (3 regions)
- Queue: Kafka (replace Celery broker)

### Database

- Distributed SQL with global consistency
- Per-region write capability
- Geo-partitioned tables

### AI

- Self-hosted LLM as primary (90% of traffic)
- Cloud providers as overflow
- Custom-trained model for medical domain

### Payments

- Multi-currency, multi-gateway
- Smart routing (lowest fee + best success rate per region)

### Security

- Full SOC 2 Type II
- ISO 27001 certified
- Bug bounty program ($50K pool)
- 24/7 SOC (in-house or MSSP)

### Monitoring

- Datadog Enterprise + custom MLOps tooling
- Real-user monitoring (RUM) at scale
- Anomaly detection (ML-based)

### Analytics

- Real-time analytics on Kafka
- ML feature store (Feast or Tecton)
- AB testing platform (Statsig or in-house)

### CI/CD

- Multi-cluster GitOps
- Auto-scaling CI runners
- Performance regression tests in CI

### SEO

- Marketplace of user-generated content (with moderation)
- Backlink network (sponsored content, partnerships)
- Wikipedia citations for medical claims

### Hiring

- +3 backend engineers
- +2 SREs
- +2 ML engineers
- +2 data engineers
- +1 security engineer
- +1 head of product
- +5 content moderators
- +3 customer success
- +1 sales (B2B partnerships)

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Kubernetes (5 regions) | $25,000 |
| CockroachDB / Vitess | $8,000 |
| Redis Enterprise | $3,000 |
| ElasticSearch | $5,000 |
| Self-hosted LLM cluster (16× H100) | $32,000 |
| Datadog Enterprise | $10,000 |
| Compliance + bug bounty | $10,000 |
| Misc | $10,000 |
| **Total infra** | **~$103,000/mo** |
| Personnel (45 people) | $250,000 |
| **Burn** | **~$353,000/mo** |

---

## Stage 6 — 1,000,000 users

**Headline**: Global platform. Strong unit economics.

### Infrastructure

- Multi-cloud (AWS + GCP) for redundancy
- Edge functions (Cloudflare Workers) for AI response shaping
- Custom CDN with question/textbook caching at edge

### AI

- Self-hosted fine-tuned medical LLM (own weights)
- Distillation to smaller models for mobile
- On-device inference for offline mode

### Payments

- Subscription engine with smart billing
- Enterprise / college licensing tier
- API monetization (institutions pay for AI tutor API)

### SEO

- #1 SERP for "UPSC CMS preparation"
- International expansion (Bangladesh, Nepal, Pakistan medical licensing)

### Hiring

- +5 backend engineers
- +3 SREs
- +3 ML engineers
- +3 data engineers
- +2 security engineers
- +3 product managers
- +10 content moderators
- +10 customer success / sales

### Estimated monthly cost

| Item | Cost (USD) |
|---|---|
| Multi-cloud K8s | $60,000 |
| Distributed DB | $25,000 |
| Edge cache + Redis | $10,000 |
| ElasticSearch cluster | $12,000 |
| LLM cluster (32× H100) | $64,000 |
| Datadog + observability | $25,000 |
| Compliance + security | $20,000 |
| Sales + marketing | $50,000 |
| Misc | $20,000 |
| **Total infra + GTM** | **~$286,000/mo** |
| Personnel (90 people) | $500,000 |
| **Burn** | **~$786,000/mo** |

**Revenue target**: $1.5M+ MRR (5% conversion × $30 ARPU × 1M users = $1.5M)

---

## Hiring Timeline

| Stage | Roles to add |
|---|---|
| Stage 0 → 1 | Backend dev, frontend dev (part-time), DevOps (fractional) |
| Stage 1 → 2 | + Backend dev, + Frontend dev, + DevOps, + Content/SEO |
| Stage 2 → 3 | + Platform eng, + ML eng, + Data eng, + Security eng, + PM, + 2 content mods |
| Stage 3 → 4 | + Staff backend, + Staff SRE, + ML eng, + Data eng, + Security eng, + PM, + 3 content mods, + CS |
| Stage 4 → 5 | + 3 backend, + 2 SRE, + 2 ML, + 2 data, + 1 security, + 1 head of product, + 5 mods, + 3 CS, + 1 sales |
| Stage 5 → 6 | + 5 backend, + 3 SRE, + 3 ML, + 3 data, + 2 security, + 3 PMs, + 10 mods, + 10 CS/sales |

---

## Key Milestones

| Milestone | Description | Trigger |
|---|---|---|
| First paying customer | Subscription flow validated | Stage 0 |
| First 100 daily active users | Retention validated | Stage 1 |
| First 1,000 daily active users | SEO traction | Stage 2 |
| First 10,000 daily active users | Need Postgres + Redis | Stage 3 |
| First 100,000 daily active users | Need Kubernetes | Stage 4 |
| First 500,000 daily active users | Need multi-region | Stage 5 |
| First 1M MAU | Full platform company | Stage 6 |

---

## Risk Register

| Risk | Mitigation |
|---|---|
| AI provider outage | Ollama fallback + 11-provider rotation |
| Render free-tier spin-down | Move to paid by Stage 1 |
| Postgres underprovisioned | Auto-scaling + read replicas |
| Cost overrun on AI | Token metering + per-user quotas |
| DDoS | Cloudflare Pro + rate limiting |
| Data breach | SOC 2 + encryption + access audits |
| Founder / key person risk | Hire ahead of curve + documentation |

---

## See Also

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — current architecture
- [`PERFORMANCE.md`](./PERFORMANCE.md) — bottlenecks to fix before scaling
- [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md) — security gates before scaling
- [`CODE_QUALITY.md`](./CODE_QUALITY.md) — debt to pay down before scaling
- [`IMPROVEMENTS.md`](./IMPROVEMENTS.md) — Top 100 improvements
