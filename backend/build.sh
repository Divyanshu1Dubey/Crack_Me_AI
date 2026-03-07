#!/usr/bin/env bash
# Render build script for CrackCMS backend
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Auto-create superuser if env vars are set (no shell on free tier)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  python manage.py createsuperuser --no-input || true
fi

# Re-import PYQ questions (SQLite is ephemeral on Render free tier)
echo "Importing PYQ questions..."
python _import_pyq_txt.py || true
python _import_pyq_md.py || true
