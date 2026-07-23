"""
NEET PG / INI-CET / AIIMS PG recall-based question bank importer.

This package is a STANDALONE importer — it does NOT modify the production
database, models, migrations, settings, or frontend. It writes JSONL output
under `backend/importers/neetpg/_output/` and (optionally) bulk-loads into
a future `backend/importer/` Django app once the user opts in.

Run from the project root:

    python -m backend.importers.neetpg.runner --source-dir <path>
    python -m backend.importers.neetpg.runner --pdf <file>

See README.md for full usage.
"""
__version__ = "0.1.0"
