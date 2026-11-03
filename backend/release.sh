#!/usr/bin/env bash
# Release step (Railway preDeployCommand; also usable on any host before the new
# version starts). The database steps of build.sh, without pip install and
# collectstatic (those run at build time). Every step is idempotent and
# non-destructive; see docs/DEPLOY_RAILWAY.md.
#
# DATABASE ONLY. Railway runs the pre-deploy command in a separate container:
# the volume is not mounted there and filesystem changes are discarded. Steps
# that read or write MEDIA_ROOT (media restore, recall_images, fixture image
# relinking) therefore run in start_web.sh, where the volume is mounted.
set -o errexit

python manage.py migrate --no-input

# Accounts flagged is_subscribed without a Subscription row: DRY RUN report only.
python manage.py reconcile_legacy_subscriptions || true

# Seeds an EMPTY question bank only; a live bank is never touched.
python manage.py seed_question_bank
python manage.py seed_blogs || true

python manage.py load_ontology || true
python manage.py ingest_source internal-notes || true
echo "release.sh complete"
