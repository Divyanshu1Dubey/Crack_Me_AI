# Knowledge Base — Setup Guide

One-time setup on the DigitalOcean App Service + Supabase + Upstash +
Cloudflare stack you already run. Total time: 45-60 minutes.

---

## Part A — Supabase (you already have this)

### A1. Confirm pgvector extension (5 min)

In Supabase dashboard → SQL Editor → run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

This enables the `vector` type. We currently store vectors as JSON for
engine portability; if you want native pgvector speed later, see
"Optional: pgvector" below.

### A2. Confirm env vars on DigitalOcean App Service (5 min)

Backend service → Environment Variables → add or confirm:

```
DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres
DJANGO_SECRET_KEY=<already set>
REDIS_URL=                 # see Part B
GROQ_API_KEY=<already set>
GEMINI_API_KEY=<already set>
CEREBRAS_API_KEY=<already set>
COHERE_API_KEY=<already set>
OPENROUTER_API_KEY=<already set>
OPENAI_API_KEY=<optional, for embeddings>
NCBI_API_KEY=<optional, free from https://www.ncbi.nlm.nih.gov/account/settings/>
EMBEDDING_MODEL=bge-small-en-v1.5
KB_FALLBACK_THRESHOLD=10
KB_USE_RERANK=true
KB_USE_KG_BOOST=true
```

### A3. Run migrations + initial KB build (10 min)

SSH or one-off container on the backend app:

```bash
python manage.py migrate
python manage.py load_ontology
python manage.py build_kb --max 2000
python manage.py ingest_source upsc
python manage.py ingest_source mohfw-india
python manage.py ingest_source nhm-india
python manage.py ingest_source nmc-india
python manage.py ingest_source icmr
```

After build_kb finishes you should see ~50-200 internal chunks
indexed. The connectors that hit network sources (`ncbi-bookshelf`,
`openstax-*`) are deliberately not run automatically — schedule them
separately (Part C).

---

## Part B — Upstash Redis (free tier, 10 min)

The codebase already supports Redis via `REDIS_URL` env var.

1. Open <https://upstash.com> → Sign up → Create Database
2. Region: pick the one closest to your DigitalOcean region
3. Type: Regional (free)
4. TLS: enabled
5. Copy the `redis://default:PASSWORD@HOST:PORT` URL
6. Set `REDIS_URL` env var on the backend service
7. Redeploy

That's it. The KB retrieval cache uses a dedicated `kb_retrieval`
cache alias so it doesn't share quota with sessions / generic views.

If you prefer not to use Upstash, the code falls back to local-memory
cache automatically (`LocMemCache`). Performance is worse but
correctness is the same.

---

## Part C — Cloudflare free CDN (20 min)

Cloudflare's free plan is enough.

1. Add `cracklabs.app` to Cloudflare
2. Cloudflare scans existing DNS — accept defaults
3. Set TLS to **Full (Strict)** — your origin (DigitalOcean App
   Service) supports TLS via the App Service default cert
4. Enable:
   - Auto Minify: HTML, CSS, JS
   - Brotli
   - HTTP/3 (QUIC)
   - Early Hints
5. **Caching → Configuration → Cache Rules** — add a rule:
   - Match: `*cracklabs.app/cms/*` AND `*cracklabs.app/neet-pg/*` AND
     `*cracklabs.app/guides/*`
   - Cache eligible: ✅
   - Edge TTL: 1 hour
   - Browser TTL: 30 minutes
6. **Security → WAF → Custom rules** — add:
   - Block: `(http.request.uri.path contains "/admin/") and ip.src ne 1.2.3.4`
     (replace 1.2.3.4 with your static IP if you have one)
   - Challenge: `cf.client.bot` (challenges bots except verified search
     engines — Google/Bing pass automatically)
7. **DNS → Add records** — ensure apex + `www` proxied through
   Cloudflare (orange cloud)

Cloudflare's free tier also gives you free DDoS protection and free
SSL — no extra config.

---

## Part D — Frontend env vars (5 min)

In your Vercel project (or wherever the frontend is hosted):

```
NEXT_PUBLIC_API_URL=https://crackcms-backend.onrender.com
NEXT_PUBLIC_KB_HEALTH_URL=https://crackcms-backend.onrender.com/api/knowledge/health
```

`NEXT_PUBLIC_KB_HEALTH_URL` is optional; useful for the KB admin
dashboard.

---

## Part E — Daily operations (15 min/day)

### Refresh embeddings for new chunks

```bash
python manage.py shell -c "
from knowledge_base.services.indexer import EmbeddingIndexer
print(EmbeddingIndexer().index_pending(max_chunks=2000))
"
```

### Refresh from network sources (weekly)

```bash
python manage.py ingest_source ncbi-bookshelf --query "hypertension" --max 25
python manage.py ingest_source openstax-microbiology --max 20
python manage.py ingest_source openstax-psychology --max 20
```

(NCBI without an API key is throttled to ~3 req/sec. Get a free key
from your NCBI account to go to 10/sec.)

### Run eval

```bash
python manage.py evaluate_kb
```

Should print `R@5=...`, `MRR=...`, `CiteAcc=...`. Target:
- R@5 ≥ 0.7
- MRR ≥ 0.6
- Citation accuracy ≥ 0.7

If R@5 is <0.5, you need more chunks. Run more `ingest_source`
commands or add more curated notes to `Medura_Train/`.

---

## Part F — Optional: native pgvector for faster search

When you outgrow pure-Python cosine (around 100k+ chunks):

```sql
-- one-time
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE knowledge_base_knowledgeembedding
  ADD COLUMN embedding_vec vector(384);  -- match your model dim

-- backfill (run from a one-off Django shell)
UPDATE knowledge_base_knowledgeembedding ke
SET embedding_vec = (
  SELECT v::vector FROM jsonb_array_elements_text(ke.vector::jsonb) WITH ORDINALITY t(v, ord)
  WHERE t.ord <= 384
);
```

Then in `retrieval/pipeline.py._vector`, replace the Python cosine
loop with:

```python
qs = qs.extra(select={"distance":
    "embedding_vec <=> %s::vector"})\
       .order_by("distance")[:top_k]
```

(Will ship as a follow-up once chunk count justifies it.)

---

## Troubleshooting

**`RuntimeError: source 'X' not registered`**
→ Run `python manage.py load_ontology` first.

**Embedding step falls back to hash embeddings**
→ sentence-transformers isn't installed in this env. Add to
`requirements.txt` and rebuild. Hash embeddings are deterministic and
work for retrieval but lack semantic quality.

**NCBI returns 429**
→ Either set `NCBI_API_KEY` or slow the connector. We already
rate-limit to 3 req/s by default.

**Build.sh fails on `import_neet_pg`**
→ That's an unrelated pre-existing step. Don't worry about it for KB
setup.

**Redis connection refused**
→ Check `REDIS_URL` env var, confirm Upstash TLS is enabled, confirm
port 6379 is reachable from DigitalOcean.