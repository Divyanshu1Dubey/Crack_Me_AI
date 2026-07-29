from django.apps import AppConfig
from django.conf import settings
import logging


class AiEngineConfig(AppConfig):
    """
    AI engine app config.

    Phase 4 (2026-07-29): on `ready()`, run a non-blocking RAG
    health probe and log the result. The probe NEVER raises —
    it logs and lets the rest of the application boot normally.
    The probe is gated by `RAG_HEALTHCHECK_ON_STARTUP` (default
    ON). A failed/missing index degrades gracefully; users still
    see a working app, just without RAG-backed answers.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_engine'

    def ready(self):
        # Skip during management commands like `migrate`, `collectstatic`,
        # `shell`, etc. — these need the DB to be in a known state.
        import os
        import sys
        argv = ' '.join(sys.argv)
        skip_in_cmds = (
            'migrate', 'makemigrations', 'collectstatic',
            'shell', 'test', 'loaddata', 'dumpdata',
            'createsuperuser', 'verify_rag_index',
        )
        if any(cmd in argv for cmd in skip_in_cmds):
            return

        if not getattr(settings, 'RAG_HEALTHCHECK_ON_STARTUP', True):
            return

        try:
            from ai_engine.retrieval.federated import FederatedRetrieval
            fr = FederatedRetrieval()
            h = fr.health_check()
            legacy = h.get('legacy', {})
            modern = h.get('modern', {})
            logger = logging.getLogger(__name__)
            logger.info(
                "[RAG HEALTH] status=%s | legacy=%s chunks/%.1fMB/integ=%s | "
                "modern=%s active=%s",
                h.get('status'),
                legacy.get('status'),
                legacy.get('db_size_bytes', 0) / 1024 / 1024,
                legacy.get('integrity'),
                modern.get('status'),
                modern.get('active_chunks', 'n/a'),
            )
        except Exception as e:
            logging.getLogger(__name__).warning(
                "[RAG HEALTH] startup probe failed: %s — continuing without RAG health info",
                e,
                exc_info=True,
            )
