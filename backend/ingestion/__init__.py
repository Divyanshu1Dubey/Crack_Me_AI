"""ingestion — Production Content Ingestion Platform (Phase 1).

This Django app is isolated from the live UPSC CMS admin / APIs. It owns
ONLY the new production ingestion framework that wraps the validated
Medical Content Engine (MCE) — Stages 1-10 + db_writer + QA V2 — with
job management, checkpoints, retries, audit, conservative import gate,
and admin review queue scaffolding.

NEET PG / INI-CET / FMGE / USMLE / PLAB share this app; the existing
UPSC CMS apps (`questions`, `importers`, `accounts`, `mce`, …) are
NEVER modified by this app except via additive reuse through their
public APIs.
"""

default_app_config = "ingestion.apps.IngestionConfig"
