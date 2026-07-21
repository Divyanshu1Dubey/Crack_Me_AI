from django.apps import AppConfig


class KnowledgeBaseConfig(AppConfig):
    """
    Permanent, versioned, citation-aware knowledge base for the
    Monica AI tutor. Adds:

    - KnowledgeSource (whitelist registry of legal sources)
    - KnowledgeChunk (text + metadata + license + provenance)
    - KnowledgeEmbedding (pgvector rows; SQLite-friendly JSON fallback)
    - KnowledgeEntity / KnowledgeRelation (auto-built medical KG)
    - IngestionJob (audit trail for every run)
    - GoldenTestCase / EvalRun (retrieval quality harness)
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_base'
    verbose_name = 'Knowledge Base'