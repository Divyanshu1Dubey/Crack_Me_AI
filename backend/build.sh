#!/usr/bin/env bash
# Backend build script for CrackCMS
set -o errexit

pip install --no-cache-dir -r requirements.txt
python manage.py collectstatic --no-input

# Pre-migration hook: rename legacy tables so --fake-initial can detect them and skip CreateModel
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('''
        ALTER TABLE IF EXISTS knowledge_source RENAME TO knowledge_base_knowledgesource;
        ALTER TABLE IF EXISTS knowledge_chunk RENAME TO knowledge_base_knowledgechunk;
        ALTER TABLE IF EXISTS knowledge_embedding RENAME TO knowledge_base_knowledgeembedding;
        ALTER TABLE IF EXISTS knowledge_entity RENAME TO knowledge_base_knowledgeentity;
        ALTER TABLE IF EXISTS knowledge_relation RENAME TO knowledge_base_knowledgerelation;
        ALTER TABLE IF EXISTS knowledge_ingestionjob RENAME TO knowledge_base_ingestionjob;
        ALTER TABLE IF EXISTS knowledge_goldentestcase RENAME TO knowledge_base_goldentestcase;
        ALTER TABLE IF EXISTS knowledge_evalrun RENAME TO knowledge_base_evalrun;
        ALTER TABLE IF EXISTS knowledge_useruploadattestation RENAME TO knowledge_base_useruploadattestation;
    ''')
"

python manage.py migrate --no-input --fake-initial

# Knowledge Base: load ontology + whitelisted sources (idempotent)
python manage.py load_ontology

# Import dataset for NEET PG
python manage.py import_neet_pg

# build.sh is complete
