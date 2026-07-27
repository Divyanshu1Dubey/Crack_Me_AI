"""Django admin for the material importer.

The admin gives the team a single place to:
  * see every import batch
  * drill into the files inside a batch
  * review staged questions and reject/approve them
  * read theory + image records
  * inspect audit logs

Admins can also trigger a re-import: see the `rerun` action.
"""
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ExtractedQuestion,
    ExtractedTheory,
    ImportedImage,
    ImportAuditLog,
    ImportBatch,
    ImportMaterial,
)


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "source_label", "status", "total_files", "files_processed",
                    "questions_extracted", "theory_blocks_extracted", "images_extracted",
                    "duplicates_skipped", "started_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("source_label", "root_path")
    readonly_fields = ("summary", "error_report", "created_at", "updated_at",
                       "started_at", "finished_at")
    actions = ["rerun_import", "publish_batch_and_build_tests"]

    @admin.action(description="Re-ingest this batch (re-parses all files)")
    def rerun_import(self, request, queryset):
        from .ingest_service import ingest_path
        for batch in queryset:
            try:
                new_batch = ingest_path(batch.root_path, source_label=f"rerun:{batch.source_label}")
                self.message_user(request, f"Created Batch#{new_batch.id}")
            except Exception as exc:
                self.message_user(request, f"Failed: {exc}", level="error")

    @admin.action(description="Publish approved rows and build auto-tests")
    def publish_batch_and_build_tests(self, request, queryset):
        """One-shot action — ARCH-2. Replaces the 3-step admin workflow
        (Approve → Publish → Build Tests) with a single click."""
        from .mock_test_builder import publish_batch_and_build_tests
        total_published = 0
        total_tests = 0
        for batch in queryset:
            try:
                res = publish_batch_and_build_tests(batch.id)
                total_published += res["published"]
                total_tests += res["tests_built"]
                self.message_user(
                    request,
                    f"Batch#{batch.id}: published={res['published']} tests={res['tests_built']}",
                )
            except Exception as exc:
                self.message_user(request, f"Batch#{batch.id} failed: {exc}", level="error")
        if total_published or total_tests:
            self.message_user(
                request,
                f"Total: published={total_published} new Questions, built={total_tests} tests.",
            )


@admin.register(ImportMaterial)
class ImportMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "original_filename", "file_format", "detected_type",
                    "parse_status", "question_count", "theory_block_count",
                    "image_count", "duplicate_count", "duration_ms", "parsed_at")
    list_filter = ("file_format", "detected_type", "parse_status", "batch")
    search_fields = ("original_filename",)
    readonly_fields = ("file_sha256", "file_size_bytes", "parse_warnings",
                       "parse_errors", "created_at", "parsed_at", "duration_ms")


@admin.register(ExtractedQuestion)
class ExtractedQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "material", "position_index", "correct_answer",
                    "inferred_subject", "inferred_difficulty", "classification_confidence",
                    "status", "content_hash_short", "provenance_checksum_short", "paragraph_index")
    list_filter = ("status", "inferred_subject", "inferred_difficulty",
                   "inferred_bloom_level", "material__detected_type")
    search_fields = ("question_text", "explanation", "option_a", "option_b", "option_c", "option_d",
                     "provenance_checksum", "content_hash")
    readonly_fields = ("content_hash", "provenance_checksum", "raw_text",
                       "classification_meta", "image_refs", "paragraph_index", "created_at")
    fieldsets = (
        (None, {
            "fields": ("material", "position_index", "paragraph_index",
                       "question_text", "option_a", "option_b", "option_c", "option_d",
                       "correct_answer", "explanation", "status")
        }),
        ("Provenance (P5)", {
            "fields": ("content_hash", "provenance_checksum", "image_refs", "raw_text"),
            "description": "Traceability chain: content_hash covers question_text; provenance_checksum adds correct_answer + explanation. paragraph_index is the source paragraph in the DOCX.",
        }),
        ("Classification", {
            "fields": ("inferred_subject", "inferred_topic", "inferred_difficulty",
                       "inferred_bloom_level", "classification_confidence", "classification_meta"),
        }),
        ("Taxonomy", {
            "fields": ("subject", "topic", "published_question", "duplicate_of"),
        }),
        ("Meta", {
            "fields": ("marks", "negative_marks", "review_note", "created_at"),
        }),
    )
    actions = ["mark_approved", "mark_rejected", "mark_needs_review", "publish_to_questions"]

    @admin.display(description="hash")
    def content_hash_short(self, obj):
        return (obj.content_hash or "")[:12]

    @admin.display(description="prov-sum")
    def provenance_checksum_short(self, obj):
        return (obj.provenance_checksum or "")[:12]

    @admin.action(description="Mark selected as approved")
    def mark_approved(self, request, queryset):
        n = queryset.update(status="approved")
        self.message_user(request, f"Approved {n} items")

    @admin.action(description="Mark selected as rejected")
    def mark_rejected(self, request, queryset):
        n = queryset.update(status="rejected")
        self.message_user(request, f"Rejected {n} items")

    @admin.action(description="Mark selected as needs review")
    def mark_needs_review(self, request, queryset):
        n = queryset.update(status="needs_review")
        self.message_user(request, f"Flagged {n} items for review")

    @admin.action(description="Publish selected to Question bank")
    def publish_to_questions(self, request, queryset):
        from .publishing import publish_extracted_question
        created = 0
        for eq in queryset.filter(status="approved"):
            try:
                if publish_extracted_question(eq):
                    created += 1
            except Exception as exc:
                self.message_user(request, f"Item#{eq.id} failed: {exc}", level="error")
        self.message_user(request, f"Published {created} questions")


@admin.register(ExtractedTheory)
class ExtractedTheoryAdmin(admin.ModelAdmin):
    list_display = ("id", "material", "position_index", "block_type", "heading", "subheading")
    list_filter = ("block_type", "material__detected_type")
    search_fields = ("heading", "subheading", "body_text")


@admin.register(ImportedImage)
class ImportedImageAdmin(admin.ModelAdmin):
    list_display = ("id", "material", "original_filename", "mime_type", "width",
                    "height", "size_bytes", "ocr_status", "is_duplicate")
    list_filter = ("mime_type", "ocr_status", "is_duplicate")
    search_fields = ("original_filename", "stored_path", "ocr_text")
    readonly_fields = ("sha256", "size_bytes", "ocr_text", "created_at")


@admin.register(ImportAuditLog)
class ImportAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "material", "level", "code", "message_short", "created_at")
    list_filter = ("level", "code")
    search_fields = ("message", "code")

    @admin.display(description="message")
    def message_short(self, obj):
        return (obj.message or "")[:80]
