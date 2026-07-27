"""Database records for the generic material-importer pipeline.

All models are additive (no migrations on existing tables). They record the
origin and provenance of every imported question, theory block, and image so
duplicates can be detected and imports can be re-run safely.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from questions.models import Question, QuestionImage, Subject, Topic


class ImportBatch(models.Model):
    """A single user/admin-initiated import run (folder, ZIP, or single file)."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("partial", "Completed with errors"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    source_label = models.CharField(max_length=255, blank=True)
    root_path = models.CharField(max_length=500)
    total_files = models.IntegerField(default=0)
    files_processed = models.IntegerField(default=0)
    files_failed = models.IntegerField(default=0)
    questions_extracted = models.IntegerField(default=0)
    questions_found = models.IntegerField(default=0)
    questions_rejected = models.IntegerField(default=0)
    theory_blocks_extracted = models.IntegerField(default=0)
    images_extracted = models.IntegerField(default=0)
    duplicates_skipped = models.IntegerField(default=0)
    ai_enrichment_queued = models.IntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    error_report = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="material_import_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Import Batch"
        verbose_name_plural = "Import Batches"

    def __str__(self) -> str:
        return f"Batch#{self.id} {self.status} {self.source_label}"


class ImportMaterial(models.Model):
    """One source file inside an ImportBatch."""

    FORMAT_CHOICES = [
        ("docx", "DOCX"),
        ("pdf", "PDF"),
        ("pptx", "PPTX"),
        ("txt", "Plain text"),
        ("md", "Markdown"),
        ("unknown", "Unknown"),
    ]

    DETECTED_TYPE_CHOICES = [
        ("mcq_classic", "MCQ (Q1./A./B./C./D./Answer:)"),
        ("mcq_boxed", "MCQ (Question/Option/correct/incorrect)"),
        ("mcq_statement", "MCQ (numbered statements + code)"),
        ("theory", "Theory notes"),
        ("hybrid", "Theory + MCQs mixed"),
        ("unknown", "Unknown"),
    ]

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="materials")
    original_filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500, blank=True)
    file_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="unknown")
    file_size_bytes = models.BigIntegerField(default=0)
    file_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    detected_type = models.CharField(max_length=20, choices=DETECTED_TYPE_CHOICES, default="unknown")
    parse_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("parsed", "Parsed"),
            ("failed", "Failed"),
            ("skipped", "Skipped (duplicate)"),
        ],
        default="pending",
    )
    question_count = models.IntegerField(default=0)
    questions_found = models.IntegerField(default=0)
    questions_rejected = models.IntegerField(default=0)
    theory_block_count = models.IntegerField(default=0)
    image_count = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    parse_warnings = models.JSONField(default=list, blank=True)
    parse_errors = models.JSONField(default=list, blank=True)
    parser_used = models.CharField(max_length=50, blank=True)
    duration_ms = models.IntegerField(default=0)
    parsed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["batch", "parse_status"]),
            models.Index(fields=["file_sha256"]),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} [{self.parse_status}]"


class ExtractedQuestion(models.Model):
    """Staging row for a parsed MCQ before it is published or deduped."""

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("published", "Published"),
        ("duplicate", "Duplicate — skipped"),
    ]

    material = models.ForeignKey(ImportMaterial, on_delete=models.CASCADE, related_name="extracted_questions")
    position_index = models.IntegerField(default=0, help_text="Position within source file")
    paragraph_index = models.IntegerField(default=-1, help_text="Index of the source paragraph in the DOCX")
    raw_text = models.TextField(blank=True)
    provenance_checksum = models.CharField(max_length=64, blank=True, db_index=True, help_text="sha256(question_text + correct_answer + explanation)")
    question_text = models.TextField()
    option_a = models.TextField(blank=True)
    option_b = models.TextField(blank=True)
    option_c = models.TextField(blank=True)
    option_d = models.TextField(blank=True)
    correct_answer = models.CharField(
        max_length=2,
        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("", "—")],
        blank=True,
    )
    explanation = models.TextField(blank=True)
    marks = models.IntegerField(default=1)
    negative_marks = models.FloatField(default=0.0)

    # Auto-classification (filled by AI classifier)
    inferred_subject = models.CharField(max_length=64, blank=True)
    inferred_topic = models.CharField(max_length=128, blank=True)
    inferred_difficulty = models.CharField(max_length=12, blank=True)
    inferred_bloom_level = models.CharField(max_length=32, blank=True)
    classification_confidence = models.FloatField(default=0.0)
    classification_meta = models.JSONField(default=dict, blank=True)

    # Provenance
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates"
    )

    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    topic = models.ForeignKey(Topic, null=True, blank=True, on_delete=models.SET_NULL)
    published_question = models.ForeignKey(
        Question,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_extracts",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    review_note = models.TextField(blank=True)

    # Image references extracted from the source (filled by image extractor)
    image_refs = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["material", "position_index"]
        indexes = [
            models.Index(fields=["content_hash"]),
            models.Index(fields=["status"]),
            models.Index(fields=["inferred_subject"]),
        ]
        constraints = [
            # P13 — prevent duplicate staging rows per source material.
            models.UniqueConstraint(
                fields=["material", "content_hash"],
                name="unique_extracted_per_material",
            ),
        ]

    def __str__(self) -> str:
        return f"Extracted#{self.id} status={self.status}"


class ExtractedTheory(models.Model):
    """A theory / notes / table block parsed from a source file."""

    material = models.ForeignKey(ImportMaterial, on_delete=models.CASCADE, related_name="extracted_theory")
    position_index = models.IntegerField(default=0)
    heading = models.CharField(max_length=255, blank=True)
    subheading = models.CharField(max_length=255, blank=True)
    body_text = models.TextField(blank=True)
    block_type = models.CharField(
        max_length=32,
        choices=[
            ("heading", "Heading"),
            ("paragraph", "Paragraph"),
            ("list", "List"),
            ("table", "Table"),
            ("callout", "Clinical Pearl / Box"),
            ("index", "Index / TOC"),
            ("image_caption", "Image caption"),
            ("mixed", "Mixed"),
        ],
        default="paragraph",
    )
    keywords = models.JSONField(default=list, blank=True)
    classification_meta = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["material", "position_index"]

    def __str__(self) -> str:
        return f"Theory#{self.id} [{self.block_type}] {self.heading[:40]}"


class ImportedImage(models.Model):
    """An image extracted from a source file and stored under MEDIA_ROOT."""

    material = models.ForeignKey(ImportMaterial, on_delete=models.CASCADE, related_name="imported_images")
    original_filename = models.CharField(max_length=255)
    stored_path = models.CharField(max_length=500)
    public_url = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=64, blank=True)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    size_bytes = models.IntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    ocr_text = models.TextField(blank=True)
    ocr_status = models.CharField(
        max_length=16,
        choices=[("skipped", "Skipped"), ("pending", "Pending"), ("done", "Done"), ("failed", "Failed")],
        default="skipped",
    )
    linked_question = models.ForeignKey(
        ExtractedQuestion, null=True, blank=True, on_delete=models.SET_NULL, related_name="images"
    )
    linked_questions = models.ManyToManyField(
        ExtractedQuestion, blank=True, related_name="imported_images_m2m",
        help_text="Per-question image association (P1, Phase 4)."
    )
    is_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Image#{self.id} {self.original_filename[:30]}"


class ImportAuditLog(models.Model):
    """Row-level audit trail for import events (used by admin + QA report)."""

    LEVEL_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]

    batch = models.ForeignKey(ImportBatch, null=True, on_delete=models.CASCADE, related_name="audit_logs")
    material = models.ForeignKey(ImportMaterial, null=True, on_delete=models.CASCADE, related_name="audit_logs")
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")
    code = models.CharField(max_length=64, blank=True)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["level", "code"])]

    def __str__(self) -> str:
        return f"[{self.level}] {self.message[:80]}"
