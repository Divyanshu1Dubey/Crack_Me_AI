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

# Seed blog posts from frontend static content (idempotent update_or_create)
python manage.py seed_blogs || true

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

# AI backfill — re-run the explanation pipeline for every Question whose
# ai_explanation is empty. There are ~8k of these (production-incident
# 2026-07-26). The command has its own retry + per-row backoff.
#
# Off by default because every deploy would burn ~8k tokens against the
# 11-provider round-robin. Set BACKFILL_AI_ON_DEPLOY=1 on the deploy
# environment (Render → Environment → Secret Files) to enable.
# Also gated by SKIP_BACKFILL=1 to manually disable without removing
# the env flag. Wrapped in `|| true` so a transient provider outage
# cannot fail the deploy — failed rows stay empty and the next run
# retries them.
if [ "${SKIP_BACKFILL:-0}" = "1" ]; then
    echo "==> Skipping AI backfill (SKIP_BACKFILL=1)"
elif [ "${BACKFILL_AI_ON_DEPLOY:-0}" = "1" ]; then
    echo "==> Running AI backfill (BACKFILL_AI_ON_DEPLOY=1)..."
    python manage.py backfill_empty_ai --batch-size 25 --batch-pause 2 --max-retries 2 || true
    echo "==> AI backfill complete."
else
    echo "==> AI backfill skipped (BACKFILL_AI_ON_DEPLOY!=1; set it to enable)"
fi

# Self-heal: rewrite any legacy bare /media/fixtures/images/ URLs left in
# Question text back to canonical [[img:N]] tokens. Idempotent — only
# rewrites rows that still contain a bare URL. Wrapped in `|| true` so
# a transient DB blip on deploy can't fail the build. The 2026-07-28
# live audit surfaced the original bare-URL bug (Production incident);
# this command keeps fresh deploys from inheriting the same data.
python manage.py relink_fixture_images --apply --fixture backend/questions_fixture.json || true

# build.sh is complete
