"""Importers Django app — wraps the standalone `importers.neetpg` package.

This package is the integration point between the recall importer and
the existing Django platform. It exposes:
- `importers.neetpg.urls`  — mounted at `/api/imports/neetpg/`
- `importers.neetpg.apps.NeetPgImporterConfig` — registered in INSTALLED_APPS
- `importers.neetpg.db_writer.DjangoWriter` — writes parsed output into the database
- `importers.neetpg.runner` — extended to accept `--write-db`
"""