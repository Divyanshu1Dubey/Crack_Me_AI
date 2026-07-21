# Knowledge Base — Ingestion Cookbook

How to safely add new content to the knowledge base.

## Standard pipeline

```bash
# 1. Drop a new internal note into Medura_Train/textbooks/ or web_knowledge/
#    (filename must NOT contain copyrighted-textbook markers — the
#    connector will refuse it otherwise)
cp my_notes.md backend/Medura_Train/textbooks/my_subject_cms_notes.md

# 2. Run ingestion (idempotent — re-runs are no-ops on unchanged chunks)
python manage.py ingest_source internal-notes

# 3. Backfill embeddings
python manage.py shell -c "
from knowledge_base.services.indexer import EmbeddingIndexer
print(EmbeddingIndexer().index_pending())
"

# 4. Re-extract KG relations
python manage.py shell -c "
from knowledge_base.retrieval.kg_extractor import KGExtractor
print(KGExtractor().extract_all())
"

# 5. Run eval
python manage.py evaluate_kb
```

## Pull from NCBI Bookshelf (StatPearls)

```bash
python manage.py ingest_source ncbi-bookshelf \
    --query "acute myocardial infarction" \
    --max 25 --db books
```

`--db books` for NCBI Bookshelf (StatPearls); `--db pmc` for PubMed
Central OA subset.

## Pull from OpenStax

```bash
python manage.py ingest_source openstax-microbiology --max 30
python manage.py ingest_source openstax-psychology --max 30
python manage.py ingest_source openstax-anatomy --max 50
```

## User uploads (gated on rights attestation)

```bash
# User uploads via the API; admin approves via Django admin or:
python manage.py shell -c "
from knowledge_base.models import UserUploadAttestation
UserUploadAttestation.objects.filter(decision='pending').update(
    decision='approved',
    reviewed_at=__import__('django.utils.timezone', fromlist=['timezone']).timezone.now(),
)
"
python manage.py ingest_source user-uploads
```

## Reset & rebuild from scratch

```bash
# Wipe chunks + embeddings (entities + relations + sources stay)
python manage.py shell -c "
from knowledge_base.models import KnowledgeChunk, KnowledgeEmbedding
KnowledgeEmbedding.objects.all().delete()
KnowledgeChunk.objects.all().delete()
"
python manage.py build_kb
```

## Schedule

For production we recommend:

| Frequency | Command | Why |
|---|---|---|
| On deploy | `python manage.py migrate && python manage.py build_kb --max 2000` | Initial populate |
| Daily | `python manage.py ingest_source internal-notes` | Pick up new internal notes |
| Weekly | `python manage.py ingest_source ncbi-bookshelf --query "<topic>" --max 25` | Refresh network sources |
| Weekly | `python manage.py evaluate_kb` | Catch retrieval regressions |
| On demand | `python manage.py shell -c "from knowledge_base.services.indexer import EmbeddingIndexer; EmbeddingIndexer().index_pending()"` | After large ingestion |

Wire these into cron or django-q2 — there's a `django_q` worker already
running in `Q_CLUSTER`.