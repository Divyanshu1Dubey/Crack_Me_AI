#!/usr/bin/env bash
# Render build script for CrackCMS backend
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Auto-create superuser if env vars are set (no shell on free tier)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || true
fi
