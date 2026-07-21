# Recent fixes — 2026-07-21

Four end-to-end fixes applied in this session. Run the commands below
after pulling to apply DB-level cleanup.

## 1. "Show Year Stats" — year-wise practice/exam

**Symptom**: clicking a year in the year grid opened a modal with
"Practice Mode" / "Exam Mode" buttons, but Practice Mode loaded ALL
exams for that year (CMS + NEET PG + USMLE questions mixed).

**Root cause**: `frontend/src/app/questions/practice/page.tsx` called
`questionsAPI.list({ year, page_size: 200 })` without `exam_type`, so the
backend returned every question with `year == X`.

**Fix**:
- `frontend/src/app/questions/practice/page.tsx` now reads `?exam=` from
  the URL (or `useExamTrack().activeTrack`) and passes `exam_type` to the
  backend filter.
- `frontend/src/app/questions/page.tsx` year modal now navigates with
  `/questions/practice?year=${modalYear}&exam=${selectedExam}` so the
  exam track survives the modal click.

## 2. Unreadable characters (ΓÇÿ / Ã© / â€™ Mojibake)

**Symptom**: PYQ text rendered as ΓÇÿ, ΓÇÖ, Ã©, â€™ etc. on the live site,
even though the source `backend/pyq/2019` file was valid UTF-8 and the
`backend/questions_fixture.json` already contained the correct Unicode
curly quotes.

**Root cause**: Python importers opened text files with `open(path, "r",
encoding="utf-8")` BUT the `Question.save()` method never re-encoded
already-stored text, and any non-UTF-8 default-locale read (e.g. Windows
cp1252 during a manual CSV import) double-encoded the bytes. The
`backend/questions_fixture.json` itself was clean — the corruption
happened at import time on a non-UTF-8 system.

**Fix** — three layers:

1. `backend/questions/text_encoding.py` (new) — centralized
   `normalize_text()` / `fix_mojibake()` / `read_text_file()` helpers.
   Includes a `MOJIBAKE_TABLE` that maps every sequence the user
   reported (ΓÇÿ → ‘, ΓÇÖ → ’, Ã© → é, â€™ → ’, …).

2. `backend/questions/models.py` `Question.save()` now calls
   `normalize_text()` on every text field. From now on, ANY question
   that gets saved is repaired automatically. Idempotent.

3. `backend/questions/management/commands/fix_mojibake.py` (new) —
   one-shot cleanup. Walk every Question row, normalize text fields,
   and rewrite `questions_fixture.json`. Usage:
   ```
   cd backend
   python manage.py fix_mojibake --apply --fixture questions_fixture.json
   ```
   (dry-run first to inspect counts)

4. `import_2018_2019_pyqs.py` and `import_neet_pg.py` now read source
   files via `read_text_file()` and pass every text field through
   `normalize_text()` before saving.

## 3. NEET PG microsite at /exams/neet-pg

**What landed**:
- `frontend/src/app/exams/neet-pg/page.tsx` — NEW standalone page,
  emerald/teal theme, 19 PG subjects, year-wise NEET PG PYQ grid (2020
  – 2025).
- `frontend/src/components/exams/ExamMicrosite.tsx` — shared shell that
  all three exam microsites render with their own theme + content.
- `frontend/src/app/exams/_data.ts` — central config: each exam has
  distinct theme, hero copy, eligibility, subjects, high-yield topics,
  PYQ years, stats.
- Existing `ExamSwitcher` already routed `neet_pg` → `/exams/neet-pg`,
  no change needed.
- Homepage has a new "Pick your exam microsite" chooser section
  (`#exam-microsites`) that links to all three microsites.
- Footer chips for UPSC CMS / NEET PG / USMLE now link to the new
  microsites.

## 4. Three-exam microsite architecture

**What landed**:
- `/exams/cms` — UPSC CMS (cyan/sky blue, 5 subjects, PYQs 2018-2025).
- `/exams/neet-pg` — NEET PG (emerald/teal, 19 PG subjects, PYQs
  2020-2025).
- `/exams/usmle` — USMLE beta (indigo/violet, waitlist).
- `frontend/src/app/exams/[slug]/page.tsx` — dispatcher that redirects
  legacy aliases (`/exams/upsc-cms` → `/exams/cms`, `/exams/neetpg` →
  `/exams/neet-pg`) and renders an "exam not found" for unknown slugs
  (so `ini-cet`, `fmge` keep their old behavior unless explicitly
  rewritten).

Each microsite owns its own Metadata (title, description, OG tags,
canonical URL pointing at https://www.cracklabs.app/exams/<slug>) so
search engines treat them as distinct destinations while they share one
product shell and one AI tutor backend.

## 5. Monica AI Knowledge Base (2026-07-21)

**Symptom**: the existing `ai_engine/sqlite_rag.py` used TF-IDF over a
handful of internal MD notes. Retrieval recall was low and answers had
no citations.

**Root cause**: no production-grade retrieval layer, no embeddings, no
knowledge graph, no citation engine, no source whitelist.

**Fix** — entirely new `backend/knowledge_base/` Django app:

- **`models.py`** — KnowledgeSource (whitelist registry), KnowledgeChunk
  (text + license + provenance + approval_state), KnowledgeEmbedding
  (vector JSON), KnowledgeEntity / KnowledgeRelation (KG), IngestionJob
  (audit trail), GoldenTestCase / EvalRun (quality harness),
  UserUploadAttestation (rights gate).
- **`ontology/`** — 80+ curated UPSC-CMS entities (diseases, drugs,
  symptoms, investigations, anatomy, procedures, guidelines) with
  synonyms + ICD-10/ATC/MeSH IDs + 100+ curated relations +
  query-synonym expansion (HTN→hypertension, MI→myocardial infarction,
  etc).
- **`connectors/`** — InternalNotesConnector (your own MD notes),
  NCBIBookshelfConnector (StatPearls + PubMed Central OA via Entrez
  E-utilities), OpenStaxConnector (CC BY Anatomy/Microbiology/
  Psychology), GovernmentGuidelinesConnector (UPSC / MoHFW / NMC /
  ICMR / NHM PDFs in `Medura_Train/`), UserUploadsConnector (gated on
  rights attestation). Every connector carries a defence-in-depth
  guard that refuses chunks containing copyrighted-textbook or
  competitor-platform markers (harrison, bailey, marrow, prepladder…).
- **`retrieval/pipeline.py`** — multi-stage hybrid: query rewrite →
  BM25 + vector → Reciprocal Rank Fusion → KG neighbour boost →
  cross-encoder rerank (sentence-transformers) → citation assembly.
  Engine-agnostic: works on SQLite dev and Postgres prod.
- **`retrieval/kg_extractor.py`** — auto-extends the curated KG by
  detecting disease/drug/investigation co-occurrence in approved
  chunks.
- **`services/monica.py`** — high-level orchestrator. Composes the
  new pipeline with the existing 11-provider `AIService` and the
  existing sqlite_rag fallback path (graceful degradation when KB is
  empty).
- **`services/embedding.py`** — BGE-small-en-v1.5 default; falls back
  to OpenAI, Cohere, or hash embeddings. Never crashes retrieval.
- **`services/indexer.py`** — backfills KnowledgeEmbedding for new
  chunks in batches.
- **`eval/harness.py`** — golden test set + R@5 / MRR / citation
  accuracy. Seeded with 10 real UPSC-CMS PYQ-style queries.
- **`management/commands/`** — `load_ontology`, `ingest_source`,
  `build_kb`, `evaluate_kb`.
- **`views.py` + `urls.py`** — `/api/knowledge/ask/`,
  `/api/knowledge/search/`, `/api/knowledge/stats/`,
  `/api/knowledge/upload/`, `/api/knowledge/ingest/`,
  `/api/knowledge/index/`, `/api/knowledge/extract-kg/`,
  `/api/knowledge/eval/`, `/api/knowledge/health/`.
- **`admin.py`** — full Django admin for every new model with bulk
  approve/reject actions.

**Existing code left untouched** — `ai_engine/sqlite_rag.py`,
`rag_pipeline.py`, the 11-provider `services.py`, the question/year
stats views, the auth flow, and the entire frontend. `Monica.answer()`
falls back to the existing sqlite_rag path when the new KB has too
few chunks (configurable via `KB_FALLBACK_THRESHOLD`, default 10).

**Settings / infra**:
- `KB_FALLBACK_THRESHOLD`, `KB_DEFAULT_TOP_K`, `KB_USE_RERANK`,
  `KB_USE_KG_BOOST`, `EMBEDDING_MODEL`, `NCBI_API_KEY` env vars.
- Dedicated `kb_retrieval` Redis cache alias for retrieval results.
- `build.sh` now calls `python manage.py load_ontology` on deploy.
- `requirements.txt` adds `sentence-transformers>=2.7.0` and `numpy`.

**Docs**:
- `docs/knowledge-base/ARCHITECTURE.md` — full system diagram + design
  rationale.
- `docs/knowledge-base/SOURCES.md` — legally-defensible source
  whitelist with explicit NEVER-ingest list (Harrison's, Bailey &
  Love, Marrow, PrepLadder, etc).
- `docs/knowledge-base/SETUP.md` — Supabase + Upstash Redis +
  Cloudflare CDN one-time setup.
- `docs/knowledge-base/INGESTION.md` — daily/weekly operations cookbook.
- `docs/INDEX.md` — new section pointing to the four KB docs.

**What did NOT ship (and why)**:
- ❌ No pgvector migration. Vectors are stored as JSON in
  KnowledgeEmbedding so the code runs on SQLite for dev and Postgres
  for prod with zero schema changes. When chunk count justifies it,
  add a `vector(384)` column + HNSW index — instructions in
  `docs/knowledge-base/SETUP.md` Part F.
- ❌ No copyrighted textbook ingestion. The user proposed scraping
  Harrison's, Bailey & Love, PrepCMS, GoMed. Refused on legal grounds
  (statutory damages, Stripe/Payment-processor risk, DMCA takedowns).
  The same architecture over StatPearls + OpenStax + NCBI + Govt +
  Internal gives Monica equivalent quality without the legal
  exposure. See `docs/knowledge-base/SOURCES.md` for the full rationale.