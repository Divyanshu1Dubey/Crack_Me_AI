#!/usr/bin/env bash
# Backend build script for CrackCMS
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Knowledge Base: load ontology + whitelisted sources (idempotent)
python manage.py load_ontology

# Import dataset for NEET PG
python manage.py import_neet_pg

# build.sh is complete
