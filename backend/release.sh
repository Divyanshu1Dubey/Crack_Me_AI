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
# Unpublished blog drafts from the question bank (paper analyses, topic-wise PYQs), each slug created once; editors
# review and publish them at /admin/blog (blog_engine/pyq_drafts.py).
python manage.py generate_pyq_blog_drafts --apply || true

# UPSC's official CMS 2014-2025 keys as official_key reviews in the answer-key audit (questions.0047 / 0049 made
# the bank match them). Records only what is missing, so later deploys finish at once.
python manage.py record_official_cms_keys --apply || true

# Past test attempts scored again for pending answer-key changes and questions UPSC dropped (tests_engine.scoring):
# the original score is kept on the attempt, every change has an AttemptRescore row. Only pending work: a deploy
# with nothing pending finishes at once.
python manage.py rescore_key_changes --apply || true

python manage.py load_ontology || true
python manage.py ingest_source internal-notes || true
echo "release.sh complete"
