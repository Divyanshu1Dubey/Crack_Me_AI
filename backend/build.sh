#!/usr/bin/env bash
# Backend build script for CrackCMS
#
# KB ingest policy: we run the local "internal-notes" connector AND the
# embedding indexer on EVERY deploy because both are idempotent
# (`update_or_create` on text_hash + the indexer only fills missing rows).
# Network connectors (NCBI / OpenStax / PMC) are skipped by default to
# avoid cold-start rate-limit failures on transient deploys; set
# `KB_INGEST_NETWORK=1` to enable them.
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input

# Self-healing migration handles stale KB tables — no manual ALTER needed.
python manage.py migrate --no-input

# Bootstrap MEDIA_ROOT for recall image persistence.
# The importer writes extracted images into MEDIA_ROOT/recall_images/...
# so the browser can fetch them via MEDIA_URL. Without this mkdir,
# Django's storage backend silently fails the first write with
# SuspiciousFileOperation, leaving the QuestionImage row with no file.
python manage.py shell -c "from pathlib import Path; from django.conf import settings; p = Path(settings.MEDIA_ROOT) / 'recall_images'; p.mkdir(parents=True, exist_ok=True); print('Bootstrapped', p)"

# Import dataset for NEET PG
python manage.py import_neet_pg

# Knowledge Base: load ontology + whitelisted sources (idempotent)
python manage.py load_ontology

# One-shot ingest: internal .md notes (idempotent via text_hash).
# Always safe to re-run; only new content lands in the KB.
python manage.py ingest_source internal-notes || true

# Backfill embeddings for any chunks that lack them (idempotent).
python manage.py shell -c "
from knowledge_base.services.indexer import EmbeddingIndexer
print('Indexed', EmbeddingIndexer().index_pending(max_chunks=2000), 'chunks')
" || true

# Optional: pull fresh content from network sources on deploys that opt in.
# Disabled by default — set KB_INGEST_NETWORK=1 to enable.
if [ "${KB_INGEST_NETWORK:-0}" = "1" ]; then
    python manage.py ingest_source ncbi-bookshelf --query "hypertension" --max 25 || true
    python manage.py ingest_source openstax-microbiology --max 20 || true
    python manage.py ingest_source openstax-psychology --max 20 || true
fi

# build.sh is complete
