"""
Knowledge Base models for the Monica AI tutor.

This app extends (does NOT replace) the existing ai_engine pipeline:
- ai_engine/sqlite_rag.py and rag_pipeline.py remain as the SQLite
  fallback when Supabase/Postgres is unavailable.
- knowledge_base adds Postgres-pgvector + BM25 + KG + citation engine
  on top of a *whitelisted* source list.

Design contract:
- Every chunk records its license + source_url + attribution
- Every chunk is approved before it is searched
- Embeddings are stored separately so we can re-embed without
  re-ingesting text, and so we can switch embedding models cleanly
- The Knowledge Graph (entities + relations) is auto-built from
  curated ontology + entity extraction from chunks
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


# ─── License catalog ──────────────────────────────────────────────────────
# Strict, legally-defensible whitelist. Anything not on this list must
# not enter the knowledge base. Add new sources by registering them
# here AND in KnowledgeSource.license.

LICENSE_PUBLIC_DOMAIN = 'public_domain'   # US govt work, no copyright
LICENSE_CC_BY = 'cc_by'                   # CC BY 4.0 (commercial OK w/ attribution)
LICENSE_CC_BY_SA = 'cc_by_sa'             # CC BY-SA (commercial OK, share-alike)
LICENSE_CC_BY_NC_SA = 'cc_by_nc_sa'      # CC BY-NC-SA (non-commercial only)
LICENSE_GOVT_INDIA = 'govt_india'         # Government of India work (GoI)
LICENSE_OWN_INTERNAL = 'internal'         # CrackLabs-authored notes/MCQs
LICENSE_USER_ATTESTED = 'user_attested'   # Uploaded by user with rights attestation

LICENSE_CHOICES = [
    (LICENSE_PUBLIC_DOMAIN, 'US Public Domain / Federal Govt'),
    (LICENSE_CC_BY, 'CC BY 4.0'),
    (LICENSE_CC_BY_SA, 'CC BY-SA 4.0'),
    (LICENSE_CC_BY_NC_SA, 'CC BY-NC-SA 4.0'),
    (LICENSE_GOVT_INDIA, 'Government of India Open Data'),
    (LICENSE_OWN_INTERNAL, 'CrackLabs Internal Content'),
    (LICENSE_USER_ATTESTED, 'User-Uploaded with Rights Attestation'),
]

# Sources we will never ingest — enforcement happens at the connector
# layer AND in admin/UI. See docs/knowledge-base/SOURCES.md.
PROHIBITED_LICENSE_MARKERS = (
    'harrison', 'bailey', 'love', 'robbins', 'park', 'ghai',
    'nelson', 'ganong', 'guyton', 'kd tripathi', 'kdt', 'k.d.',
    'marrow', 'prepladder', 'dams', 'prepcms', 'gomed',
    'elsevier', 'mcgraw', 'wolters', 'oxford medical', 'cbs publishers',
)


class KnowledgeSource(models.Model):
    """
    Whitelisted source registry. One row per upstream.

    Adding a row here is the legal gate to ingest that source. Every
    connector must look up its source by `slug` and verify license +
    source_url. Anything not in this table must be rejected.
    """

    LICENSE = LICENSE_CHOICES

    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Provenance
    source_url = models.URLField(max_length=600, blank=True)
    api_endpoint = models.URLField(max_length=600, blank=True)
    license = models.CharField(max_length=24, choices=LICENSE, db_index=True)
    attribution = models.CharField(
        max_length=300,
        help_text='Required attribution string to display with every citation.',
    )
    citation_template = models.CharField(
        max_length=300,
        blank=True,
        help_text='Template for citation, e.g. "{title}. {publisher} ({year}). {url}".',
    )

    # Operational
    is_active = models.BooleanField(default=True)
    supports_incremental = models.BooleanField(default=False)
    last_ingested_at = models.DateTimeField(null=True, blank=True)
    last_ingestion_status = models.CharField(
        max_length=20,
        blank=True,
        choices=[('success', 'Success'), ('partial', 'Partial'), ('failed', 'Failed')],
    )

    # Stats (cached, updated by ingestion jobs)
    chunk_count = models.PositiveIntegerField(default=0)
    entity_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'license']),
        ]

    def __str__(self):
        return f'{self.name} ({self.license})'


class KnowledgeChunk(models.Model):
    """
    A retrievable text segment with full provenance.

    A chunk is the atomic unit of search. Every chunk knows:
    - Where the text came from (source, url, locator like chapter+page)
    - What license it carries
    - Who reviewed it (default: trusted sources are auto-approved; user
      uploads are admin-approved)
    - Whether it has an embedding yet
    """

    APPROVAL_PENDING = 'pending'
    APPROVAL_AUTO = 'auto'
    APPROVAL_ADMIN = 'admin'
    APPROVAL_REJECTED = 'rejected'
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, 'Pending review'),
        (APPROVAL_AUTO, 'Auto-approved (trusted source)'),
        (APPROVAL_ADMIN, 'Admin-approved'),
        (APPROVAL_REJECTED, 'Rejected'),
    ]

    source = models.ForeignKey(
        KnowledgeSource, on_delete=models.PROTECT, related_name='chunks',
    )
    # Optional URL of the canonical page/document for traceability
    source_url = models.URLField(max_length=600, blank=True)
    # Free-text locator within the source (chapter / page / section id)
    locator = models.CharField(max_length=255, blank=True)

    text = models.TextField()
    text_hash = models.CharField(
        max_length=64, db_index=True,
        help_text='SHA-256 of normalized text; used for dedup.',
    )

    # Taxonomy (all optional but strongly recommended for filtering)
    subject = models.CharField(max_length=80, blank=True, db_index=True)
    topic = models.CharField(max_length=120, blank=True, db_index=True)
    subtopic = models.CharField(max_length=120, blank=True)
    tags = models.JSONField(default=list, blank=True)

    # Provenance / governance
    license = models.CharField(max_length=24, choices=LICENSE_CHOICES)
    attribution = models.CharField(max_length=300)
    approval_state = models.CharField(
        max_length=16, choices=APPROVAL_CHOICES, default=APPROVAL_PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='approved_chunks',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Quality / freshness
    quality_score = models.FloatField(default=0.0)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # Optional links into the existing question/topics universe
    topic_link = models.ForeignKey(
        'questions.Topic', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='kb_chunks',
    )
    pyq_link = models.ForeignKey(
        'questions.Question', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='kb_chunks',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'is_active']),
            models.Index(fields=['subject', 'topic']),
            models.Index(fields=['approval_state', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'text_hash'],
                name='unique_chunk_per_source',
            ),
        ]

    def __str__(self):
        return f'Chunk#{self.id} [{self.source.slug}] {self.subject or "-"}'


class KnowledgeEmbedding(models.Model):
    """
    Vector for a chunk. Stored separately so we can:
    - Swap embedding models without re-ingesting text
    - Use a different vector store per environment
    - Run A/B between two embedding models

    We store vectors as JSON (list[float]) to remain engine-agnostic.
    On Postgres+pgvector we ALSO write to a `vector(384)` column
    managed by a follow-up migration; for SQLite / dev, the JSON field
    is the canonical store and retrieval falls back to NumPy cosine.
    """

    EMBED_MODELS = [
        ('bge-small-en-v1.5', 384),
        ('bge-base-en-v1.5', 768),
        ('bge-large-en-v1.5', 1024),
        ('all-MiniLM-L6-v2', 384),
        ('pubmedbert-base-embed', 768),
        ('text-embedding-3-small', 1536),
        ('cohere-embed-english-v3.0', 1024),
    ]

    chunk = models.OneToOneField(
        KnowledgeChunk, on_delete=models.CASCADE, related_name='embedding',
    )
    model = models.CharField(max_length=64, default='bge-small-en-v1.5')
    dim = models.PositiveSmallIntegerField(default=384)
    vector = models.JSONField(
        help_text='List[float] of length `dim`. Stored as JSON for portability.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['model']),
        ]

    def __str__(self):
        return f'Emb#{self.id} [{self.model} d={self.dim}] for chunk {self.chunk_id}'


class KnowledgeEntity(models.Model):
    """
    A medical concept extracted from chunks or asserted from the
    curated ontology. Forms the nodes of the medical knowledge graph.

    We do NOT pull in ICD-10/ATC wholesale — those catalogs are tens of
    thousands of entries. Instead we curate a smaller UPSC-CMS-relevant
    ontology and let extraction add more as it goes (admin-revisable).
    """

    ENTITY_TYPES = [
        ('disease', 'Disease / Syndrome'),
        ('drug', 'Drug / Medication'),
        ('symptom', 'Symptom / Sign'),
        ('investigation', 'Investigation / Lab test'),
        ('anatomy', 'Anatomy / Structure'),
        ('procedure', 'Procedure / Surgery'),
        ('guideline', 'Clinical Guideline'),
        ('concept', 'Concept / Term'),
    ]

    name = models.CharField(max_length=200, db_index=True)
    canonical_id = models.CharField(
        max_length=80, blank=True,
        help_text='Stable id from ICD-10, ATC, MeSH, or our own slug.',
    )
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES, db_index=True)
    synonyms = models.JSONField(default=list, blank=True)
    definition = models.TextField(blank=True)

    subject = models.CharField(max_length=80, blank=True, db_index=True)
    source_chunk = models.ForeignKey(
        KnowledgeChunk, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='entities',
    )
    curated = models.BooleanField(
        default=False,
        help_text='True for ontology-curated; False for auto-extracted.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['entity_type', 'name']
        indexes = [
            models.Index(fields=['entity_type', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'entity_type'],
                name='unique_entity_name_type',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.entity_type})'


class KnowledgeRelation(models.Model):
    """
    A directed edge in the medical knowledge graph.

    Examples:
      Hypertension (disease) --treated_by--> ACE_inhibitor (drug)
      Tuberculosis (disease) --investigated_by--> Mantoux (investigation)
      Pneumonia (disease) --symptom--> Fever (symptom)
    """

    RELATION_TYPES = [
        ('treated_by', 'treated by'),
        ('investigated_by', 'investigated by'),
        ('causes', 'causes'),
        ('symptom_of', 'symptom of'),
        ('risk_factor_for', 'risk factor for'),
        ('complication_of', 'complication of'),
        ('differential_of', 'differential diagnosis of'),
        ('guideline_for', 'guideline for'),
        ('pyq_topic', 'exam topic of'),
        ('related_to', 'related to'),
    ]

    source_entity = models.ForeignKey(
        KnowledgeEntity, on_delete=models.CASCADE, related_name='outgoing',
    )
    target_entity = models.ForeignKey(
        KnowledgeEntity, on_delete=models.CASCADE, related_name='incoming',
    )
    relation = models.CharField(max_length=40, choices=RELATION_TYPES)
    weight = models.FloatField(default=1.0)
    evidence_chunk = models.ForeignKey(
        KnowledgeChunk, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='relations',
    )
    curated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-weight']
        indexes = [
            models.Index(fields=['source_entity', 'relation']),
            models.Index(fields=['target_entity', 'relation']),
        ]

    def __str__(self):
        return f'{self.source_entity} -{self.relation}-> {self.target_entity}'


class IngestionJob(models.Model):
    """
    Audit trail for every ingestion run.
    """

    STATUS = [
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
    ]

    source = models.ForeignKey(
        KnowledgeSource, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ingestion_jobs',
    )
    connector = models.CharField(
        max_length=80,
        help_text='Code path of the connector, e.g. "ncbi_bookshelf".',
    )
    status = models.CharField(max_length=16, choices=STATUS, default='queued')

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    chunks_added = models.PositiveIntegerField(default=0)
    chunks_updated = models.PositiveIntegerField(default=0)
    chunks_rejected = models.PositiveIntegerField(default=0)
    entities_added = models.PositiveIntegerField(default=0)
    relations_added = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)

    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ingestion_jobs',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'Ingest#{self.id} {self.connector} -> {self.status}'


class GoldenTestCase(models.Model):
    """
    A regression-test query for retrieval quality. Each test case has
    a query, an expected subject/topic, and a set of acceptable
    source-slugs / chunk ids that should appear in the top-K.

    Run via: python manage.py evaluate_kb
    """

    query = models.TextField()
    expected_subject = models.CharField(max_length=80, blank=True)
    expected_topic = models.CharField(max_length=120, blank=True)
    expected_source_slugs = models.JSONField(default=list, blank=True)
    expected_keywords = models.JSONField(
        default=list, blank=True,
        help_text='At least one of these must appear in retrieved text.',
    )
    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Golden test case'
        verbose_name_plural = 'Golden test cases'

    def __str__(self):
        return self.query[:80]


class EvalRun(models.Model):
    """A single evaluation run; holds aggregate metrics."""

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    testcases_total = models.PositiveIntegerField(default=0)
    recall_at_5 = models.FloatField(default=0.0)
    recall_at_10 = models.FloatField(default=0.0)
    mrr = models.FloatField(default=0.0)
    citation_accuracy = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'EvalRun@{self.started_at:%Y-%m-%d %H:%M} R@5={self.recall_at_5:.2f}'


class UserUploadAttestation(models.Model):
    """
    A user-uploaded document with explicit rights attestation.
    Required for the user-uploads path to enter the knowledge base.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='upload_attestations',
    )
    file = models.FileField(upload_to='user_uploads/%Y/%m/')
    title = models.CharField(max_length=255)
    source_description = models.CharField(
        max_length=300,
        help_text='Where did this come from? E.g. "My own MCQ prep notes".',
    )
    rights_attested = models.BooleanField(
        default=False,
        help_text='User confirms they own the rights OR have a license '
                  'to redistribute. Required.',
    )
    commercial_use_ok = models.BooleanField(default=True)

    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_uploads',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(
        max_length=16,
        choices=[('pending', 'Pending'), ('approved', 'Approved'),
                 ('rejected', 'Rejected')],
        default='pending',
    )
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['decision', '-created_at']),
        ]

    def __str__(self):
        return f'{self.title} ({self.user.username})'