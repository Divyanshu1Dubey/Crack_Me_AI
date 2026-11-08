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
# migrate also (re)creates the daily renewal-reminder schedule (accounts
# post_migrate signal) and the ingestion stale-job recovery schedule
# (ingestion post_migrate signal, every 10 min on the qcluster worker).
python manage.py migrate --no-input

# Admin/staff accounts not yet linked to a Supabase identity: a DRY RUN report
# (writes nothing, never fails the build). Review it, then run once by hand
# (owner action, never from this script):
#   python manage.py link_supabase_identity --all-privileged --apply
python manage.py link_supabase_identity --all-privileged || true

# Accounts flagged is_subscribed without a Subscription row (premium now comes
# from Subscription rows only; accounts.0026 restored the plans that signed
# payments prove): a DRY RUN report of the UNPROVEN accounts left to review
# (writes nothing without --apply, never fails the build). Owner action, by
# hand only, after granting a plan to any that should keep premium:
#   python manage.py reconcile_legacy_subscriptions --apply --clear-unproven
python manage.py reconcile_legacy_subscriptions || true

# Question bank seed for a fresh database (new deploy DB, staging, fresh
# local DB): loads fixtures/cms_fixture.json -- subjects, topics, questions,
# honouring admin-removal tombstones -- only while the CMS bank is empty.
# A bank that already has questions is never touched (re-loading the fixture
# would overwrite AI explanations, answer fixes and deactivations made since
# the export); re-sync on purpose with `python manage.py load_exam_fixture cms`.
python manage.py seed_question_bank

# Import static blog posts the database lacks; never overwrites admin edits (see seed_blogs)
python manage.py seed_blogs || true

# Unpublished blog drafts from the question bank, each slug created once (blog_engine/pyq_drafts.py)
python manage.py generate_pyq_blog_drafts --apply || true

# UPSC's official CMS 2014-2025 keys as official_key reviews in the answer-key audit (records only what is missing)
python manage.py record_official_cms_keys --apply || true

# Past test attempts scored again for pending answer-key changes / UPSC-dropped questions (keeps original scores)
python manage.py rescore_key_changes --apply || true

# Bootstrap MEDIA_ROOT for recall image persistence.
# The importer writes extracted images into MEDIA_ROOT/recall_images/...
# so the browser can fetch them via MEDIA_URL. Without this mkdir,
# Django's storage backend silently fails the first write with
# SuspiciousFileOperation, leaving the QuestionImage row with no file.
python manage.py shell -c "from pathlib import Path; from django.conf import settings; p = Path(settings.MEDIA_ROOT) / 'recall_images'; p.mkdir(parents=True, exist_ok=True); print('Bootstrapped', p)"

# NEET PG 2025/2020 papers: NOT imported on deploy. `import_neet_pg` used to
# run here and deleted every exam_source="NEET PG" question (with their
# attempts, bookmarks, notes, flashcards and test responses) on every build.
# It is now a manual, non-destructive command; run it by hand when needed:
#   python manage.py import_neet_pg --dry-run   # report only
#   python manage.py import_neet_pg             # create missing keyed questions
#
# ONE-TIME CLEANUP (once per database that ever ran the old command): rows it
# wrote -- the 2020 paper answered "A" throughout, cut-off 2025 stems, all
# tagged exam_type="cms" so they are served in the UPSC CMS bank -- are left
# untouched by the default mode. Repair (2025) / hide (2020, no answer key:
# is_active=False, needs_review=True) them, skipping admin-edited rows:
#   python manage.py import_neet_pg --replace --dry-run   # review the counts
#   python manage.py import_neet_pg --replace
#
# ONE-TIME CLEANUP, owner action (this script never runs destructive data
# commands): releases before the seed_data fix stored its 15
# demo questions as UPSC CMS PYQs of 2019-2023, so the live bank shows them
# as real papers. Review the report, then apply once per database (rows an
# admin edited, verified or answer-locked are reported and left alone):
#   python manage.py cleanup_seed_samples                 # dry run: report only
#   python manage.py cleanup_seed_samples --apply         # set year=0 (Expert Curated)

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
# (No --fixture: the old path, backend/questions_fixture.json, no longer
# exists, and mirroring into a fixture inside a deploy container is pointless.)
python manage.py relink_fixture_images --apply || true

# Background jobs: ingestion / recall imports, video generation, the daily
# renewal-reminder schedule and the ingestion stale-job recovery schedule run
# only while a django-q worker is up
# (Procfile `worker: python manage.py qcluster`). DigitalOcean App Platform
# does not start a Procfile worker (or run `release`) on its own: add a Worker
# component with run command `python manage.py qcluster` and the web
# component's environment, or queued jobs stay queued and no reminder is sent.

# build.sh is complete
