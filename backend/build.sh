#!/usr/bin/env bash
# Backend build script for CrackCMS
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# build.sh is complete
