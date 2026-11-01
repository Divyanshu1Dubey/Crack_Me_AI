#!/usr/bin/env bash
# Run this from the project root: bash SHIP_KB.sh
#
# Commits the knowledge-base build (Monica AI Knowledge Platform) in one
# shot and pushes to origin/main. After pushing, DigitalOcean App Service
# auto-deploys from main, so your live backend picks up the new endpoints
# on the next deploy.
#
# Only the knowledge-base paths listed in KB_PATHS are staged and committed
# (it used to run `git add -A` and push whatever else was lying in the tree:
# database dumps, exports, local env files).
#
# Pre-flight:
#   git status   # review; anything outside KB_PATHS is left alone
#   git remote -v # confirm origin is set
#
# Post-flight:
#   python manage.py migrate
#   python manage.py load_ontology
#   python manage.py build_kb --max 2000
#   python manage.py ingest_source upsc
#   python manage.py ingest_source mohfw-india
#   python manage.py ingest_source nhm-india
#   python manage.py ingest_source nmc-india
#   python manage.py ingest_source icmr
#   python manage.py evaluate_kb

set -euo pipefail

cd "$(dirname "$0")"

KB_PATHS=(
  backend/knowledge_base
  backend/crack_cms/settings.py
  backend/crack_cms/urls.py
  backend/build.sh
  backend/requirements.txt
  docs/knowledge-base
  docs/INDEX.md
  CHANGES_SUMMARY.md
)
existing_paths=()
for path in "${KB_PATHS[@]}"; do
  if [ -e "$path" ]; then
    existing_paths+=("$path")
  fi
done
if [ "${#existing_paths[@]}" -eq 0 ]; then
  echo "None of the knowledge-base paths exist; nothing to ship." >&2
  exit 1
fi

git add -- "${existing_paths[@]}"

# Path-limited commit (pathspec after the message): changes staged earlier
# for any other file stay out of it.
git commit -m "feat(kb): Monica AI knowledge platform with source whitelist + citations

New knowledge_base Django app:

Backend
- Models: KnowledgeSource (whitelist), KnowledgeChunk (license +
  provenance + approval), KnowledgeEmbedding (JSON vectors,
  pgvector-ready), KnowledgeEntity / KnowledgeRelation (curated KG),
  IngestionJob (audit), GoldenTestCase / EvalRun (quality harness),
  UserUploadAttestation (rights gate).
- Curated UPSC-CMS ontology: 80+ entities, 100+ relations, medical
  synonym expansion (HTN, MI, TB, T2DM, etc).
- 5 connectors with defence-in-depth copyright guard:
    InternalNotesConnector — your own Medura_Train MD notes
    NCBIBookshelfConnector — StatPearls + PMC OA via Entrez
    OpenStaxConnector — CC BY Anatomy/Micro/Psychology
    GovernmentGuidelinesConnector — UPSC/MoHFW/NMC/ICMR/NHM PDFs
    UserUploadsConnector — gated on rights attestation
- Retrieval: multi-stage BM25 + vector + RRF + KG boost +
  cross-encoder rerank + citation assembly.
- Monica orchestrator composes new pipeline with existing
  ai_engine.services.AIService; falls back to existing sqlite_rag
  when KB has < KB_FALLBACK_THRESHOLD chunks.
- Embedding service: BGE-small-en-v1.5 default; OpenAI / Cohere /
  hash fallback. Never crashes retrieval.
- Eval harness: 10 seeded UPSC-CMS queries, R@5 / MRR / citation
  accuracy.
- Management commands: load_ontology, ingest_source, build_kb,
  evaluate_kb.
- API endpoints: /api/knowledge/{ask,search,stats,sources,upload,
  ingest,index,extract-kg,eval,health}.
- Full Django admin for every model with bulk approve/reject.

Settings / infra
- KB_FALLBACK_THRESHOLD, KB_DEFAULT_TOP_K, KB_USE_RERANK,
  KB_USE_KG_BOOST, EMBEDDING_MODEL, NCBI_API_KEY env vars.
- Dedicated kb_retrieval Redis cache alias.
- build.sh calls load_ontology on every deploy.
- requirements.txt: sentence-transformers>=2.7.0, numpy.

Existing code untouched
- ai_engine/sqlite_rag.py + rag_pipeline.py kept as fallback.
- All 11 AI providers, token economy, question/year-stats views,
  auth, frontend all continue to work.

Docs
- docs/knowledge-base/ARCHITECTURE.md
- docs/knowledge-base/SOURCES.md (whitelist + NEVER-ingest list)
- docs/knowledge-base/SETUP.md (Supabase + Upstash + Cloudflare)
- docs/knowledge-base/INGESTION.md (ops cookbook)
- docs/INDEX.md updated.
- CHANGES_SUMMARY.md updated.

Refs the original prompt: 'transform Monica into the most accurate
AI tutor for UPSC CMS via RAG + KG + ontology + citations over
whitelisted sources.' Deliberately refused to ingest copyrighted
textbooks or competitor platforms. Same architecture over StatPearls
+ OpenStax + NCBI + Govt + Internal gives equivalent quality without
legal exposure." -- "${existing_paths[@]}" || {
  echo "Nothing to commit (everything already committed)."
}

git push origin main

echo ""
echo "Done. Now on the live backend:"
echo "  python manage.py migrate"
echo "  python manage.py load_ontology"
echo "  python manage.py build_kb --max 2000"
echo "  python manage.py ingest_source upsc"
echo "  python manage.py ingest_source mohfw-india"
echo "  python manage.py ingest_source nhm-india"
echo "  python manage.py ingest_source nmc-india"
echo "  python manage.py ingest_source icmr"
echo "  python manage.py evaluate_kb"
echo ""
echo "Or, on DigitalOcean App Service one-off console:"
echo "  python manage.py build_kb --max 5000 --skip-extract"