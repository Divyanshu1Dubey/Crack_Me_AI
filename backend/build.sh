#!/usr/bin/env bash
# Render build script for CrackCMS backend
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py bootstrap_admin

# Auto-create superuser if env vars are set (no shell on free tier)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || true
fi

# Load all questions from fixture (SQLite is ephemeral on Render free tier)
echo "Loading question bank fixture..."
python manage.py loaddata questions_fixture.json

# Hard check: fail deploy if fixture is empty or broken
QUESTION_COUNT=$(python -c "import os,sys,django;os.environ['DJANGO_SETTINGS_MODULE']='crack_cms.settings';sys.path.insert(0,'.');django.setup();from questions.models import Question;print(Question.objects.count())")
echo "Total questions in DB: ${QUESTION_COUNT}"

if [ "${QUESTION_COUNT}" = "0" ]; then
  echo "ERROR: Question bank is empty after fixture load. Failing build."
  exit 1
fi
