"""
Phase 2 additive migration — NEET PG / INI-CET / AIIMS PG recall bank.

Adds fields on `Question` and introduces 5 new models:
- RecallSource (one row per source PDF)
- QuestionSource (provenance bridge)
- QuestionImage (multi-image)
- DuplicateCluster (canonical-question pointer)
- DuplicateMember (cluster membership)

Hand-authored. `python manage.py makemigrations --check --dry-run` MUST
report "No changes detected" once this migration is applied.

Existing rows remain valid — every AddField has a default.
"""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0022_question_is_disputed"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. New fields on Question ────────────────────────────────────
        migrations.AddField(
            model_name="question",
            name="recall_status",
            field=models.CharField(
                choices=[
                    ("recall", "Recall"),
                    ("coaching_compiled", "Coaching Compiled"),
                    ("official_compiled", "Official / Compiled"),
                ],
                default="official_compiled",
                max_length=32,
                help_text="Recall / coaching-compiled / official-compiled provenance.",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("single_best", "Single Best Answer"),
                    ("multiple_correct", "Multiple Correct"),
                    ("assertion_reason", "Assertion-Reason"),
                    ("match", "Match the Following"),
                    ("image_based", "Image-Based"),
                    ("numerical", "Numerical"),
                ],
                default="single_best",
                max_length=32,
                help_text="Question format (single best, multiple correct, A/R, image-based, etc.)",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="clinical_category",
            field=models.CharField(
                choices=[
                    ("clinical", "Clinical"),
                    ("preclinical", "Preclinical"),
                    ("paraclinical", "Paraclinical"),
                ],
                default="clinical",
                max_length=32,
                help_text="Preclinical / Paraclinical / Clinical classification.",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="session",
            field=models.CharField(
                choices=[
                    ("jan", "January"),
                    ("jul", "July"),
                    ("may", "May"),
                    ("nov", "November"),
                    ("none", "None"),
                ],
                default="",
                blank=True,
                max_length=16,
                help_text="Exam session for the year (jan/jul/may/nov/none).",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="confidence_score",
            field=models.DecimalField(
                decimal_places=3,
                default=1.000,
                help_text="Weighted OCR + parse + completeness score (0..1).",
                max_digits=4,
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="ocr_confidence",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Tesseract avg confidence (0..100).",
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="extraction_confidence",
            field=models.DecimalField(
                decimal_places=3,
                default=1.000,
                help_text="Parser confidence (0..1).",
                max_digits=4,
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="is_image_based",
            field=models.BooleanField(
                default=False,
                help_text="Image is required to answer this question.",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="recall_text_hash",
            field=models.CharField(
                blank=True,
                default="",
                help_text="sha256 of normalised question text — used for cross-PDF dedup.",
                max_length=64,
            ),
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["question_type"], name="ix_question_type"),
        ),
        migrations.AddIndex(
            model_name="question",
            index=models.Index(fields=["clinical_category"], name="ix_question_clinical"),
        ),

        # ── 2. New model: RecallSource ───────────────────────────────────
        migrations.CreateModel(
            name="RecallSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pdf_filename", models.CharField(max_length=255)),
                ("pdf_path", models.CharField(max_length=512)),
                ("pdf_sha256", models.CharField(max_length=64)),
                ("pdf_sha256_short", models.CharField(db_index=True, max_length=16)),
                ("pdf_size_bytes", models.BigIntegerField(default=0)),
                ("page_count", models.IntegerField(default=0)),
                ("page_start", models.IntegerField(blank=True, null=True)),
                ("page_end", models.IntegerField(blank=True, null=True)),
                ("question_count", models.IntegerField(default=0)),
                (
                    "scan_type",
                    models.CharField(
                        choices=[("digital", "Digital"), ("scanned", "Scanned"), ("hybrid", "Hybrid")],
                        default="hybrid",
                        max_length=16,
                    ),
                ),
                ("recall_status", models.CharField(default="recall", max_length=32)),
                ("publisher", models.CharField(blank=True, max_length=160)),
                ("pdf_metadata", models.JSONField(blank=True, default=dict)),
                (
                    "import_job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recall_sources",
                        to="questions.questionimportjob",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="recallsource",
            constraint=models.UniqueConstraint(
                fields=("pdf_sha256", "page_start", "page_end"),
                name="uniq_recall_source_sha_pagerange",
            ),
        ),
        migrations.AddIndex(
            model_name="recallsource",
            index=models.Index(fields=["scan_type"], name="ix_recall_source_scan"),
        ),
        migrations.AddIndex(
            model_name="recallsource",
            index=models.Index(fields=["recall_status"], name="ix_recall_source_recall"),
        ),
        migrations.AddIndex(
            model_name="recallsource",
            index=models.Index(fields=["is_active"], name="ix_recall_source_active"),
        ),

        # ── 3. New model: QuestionSource ─────────────────────────────────
        migrations.CreateModel(
            name="QuestionSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recall_sources",
                        to="questions.question",
                    ),
                ),
                (
                    "recall_source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="question_sources",
                        to="questions.recallsource",
                    ),
                ),
                ("page_number", models.IntegerField()),
                ("question_number_in_pdf", models.IntegerField(blank=True, null=True)),
                ("original_text", models.TextField(blank=True)),
                ("extracted_text", models.TextField(blank=True)),
                ("ocr_confidence", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("extraction_confidence", models.DecimalField(decimal_places=3, default=1.000, max_digits=4)),
                ("import_job_id", models.CharField(blank=True, max_length=64)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["recall_source", "page_number"],
            },
        ),
        migrations.AddConstraint(
            model_name="questionsource",
            constraint=models.UniqueConstraint(
                fields=("recall_source", "page_number", "question_number_in_pdf"),
                name="uniq_question_source_page_qno",
            ),
        ),
        migrations.AddIndex(
            model_name="questionsource",
            index=models.Index(fields=["question"], name="ix_qsource_question"),
        ),
        migrations.AddIndex(
            model_name="questionsource",
            index=models.Index(fields=["recall_source", "page_number"], name="ix_qsource_page"),
        ),
        migrations.AddIndex(
            model_name="questionsource",
            index=models.Index(fields=["import_job_id"], name="ix_qsource_jobid"),
        ),

        # ── 4. New model: QuestionImage ──────────────────────────────────
        migrations.CreateModel(
            name="QuestionImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="images",
                        to="questions.question",
                    ),
                ),
                (
                    "recall_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="images",
                        to="questions.recallsource",
                    ),
                ),
                ("page_number", models.IntegerField()),
                ("image_index_in_page", models.IntegerField(default=0)),
                ("file", models.ImageField(blank=True, null=True, upload_to="recall_images/%Y/%m/")),
                ("mime", models.CharField(default="image/png", max_length=32)),
                ("width", models.IntegerField(default=0)),
                ("height", models.IntegerField(default=0)),
                ("bytes", models.BigIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, max_length=64)),
                ("sha256_short", models.CharField(blank=True, db_index=True, max_length=16)),
                ("phash", models.CharField(blank=True, max_length=16)),
                ("dhash", models.CharField(blank=True, max_length=16)),
                (
                    "modality",
                    models.CharField(
                        choices=[
                            ("radiology", "Radiology"),
                            ("histopathology", "Histopathology"),
                            ("gross_pathology", "Gross Pathology"),
                            ("ecg", "ECG"),
                            ("ct", "CT"),
                            ("mri", "MRI"),
                            ("x_ray", "X-Ray"),
                            ("ultrasound", "Ultrasound"),
                            ("clinical_photo", "Clinical Photograph"),
                            ("instrument", "Instrument"),
                            ("chart", "Chart"),
                            ("flowchart", "Flowchart"),
                            ("microbiology", "Microbiology Slide"),
                            ("slide", "Slide"),
                            ("embryology", "Embryology"),
                            ("anatomy", "Anatomy Diagram"),
                            ("biochem_pathway", "Biochemistry Pathway"),
                            ("dermatology", "Dermatology"),
                            ("ophthalmology_fundus", "Ophthalmology Fundus"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=32,
                    ),
                ),
                ("modality_subtype", models.CharField(blank=True, max_length=64)),
                ("body_region", models.CharField(blank=True, max_length=64)),
                ("ocr_text", models.TextField(blank=True)),
                ("caption", models.TextField(blank=True)),
                ("caption_source", models.CharField(default="none", max_length=32)),
                ("ocr_confidence", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("extraction_confidence", models.DecimalField(decimal_places=3, default=1.000, max_digits=4)),
                ("has_diagram", models.BooleanField(default=False)),
                ("has_table", models.BooleanField(default=False)),
                ("is_watermarked", models.BooleanField(default=False)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("primary", "Primary"),
                            ("option", "Option"),
                            ("illustration", "Illustration"),
                            ("explanation", "Explanation"),
                        ],
                        default="illustration",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["question", "page_number", "image_index_in_page"],
            },
        ),
        migrations.AddIndex(
            model_name="questionimage",
            index=models.Index(fields=["question"], name="ix_qimage_question"),
        ),
        migrations.AddIndex(
            model_name="questionimage",
            index=models.Index(fields=["modality"], name="ix_qimage_modality"),
        ),
        migrations.AddIndex(
            model_name="questionimage",
            index=models.Index(fields=["phash"], name="ix_qimage_phash"),
        ),
        migrations.AddIndex(
            model_name="questionimage",
            index=models.Index(fields=["is_active"], name="ix_qimage_active"),
        ),

        # ── 5. New model: DuplicateCluster ───────────────────────────────
        migrations.CreateModel(
            name="DuplicateCluster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "canonical_question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="canonical_for",
                        to="questions.question",
                    ),
                ),
                ("similarity_threshold", models.DecimalField(decimal_places=3, default=0.920, max_digits=4)),
                ("detection_method", models.CharField(default="rapidfuzz", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="duplicatecluster",
            index=models.Index(fields=["detection_method"], name="ix_dupcluster_method"),
        ),

        # ── 6. New model: DuplicateMember ───────────────────────────────
        migrations.CreateModel(
            name="DuplicateMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "cluster",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="questions.duplicatecluster",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cluster_memberships",
                        to="questions.question",
                    ),
                ),
                ("similarity_score", models.DecimalField(decimal_places=3, default=1.000, max_digits=4)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["cluster", "-similarity_score"],
            },
        ),
        migrations.AddConstraint(
            model_name="duplicatemember",
            constraint=models.UniqueConstraint(
                fields=("cluster", "question"),
                name="uniq_duplicate_member",
            ),
        ),
        migrations.AddIndex(
            model_name="duplicatemember",
            index=models.Index(fields=["question"], name="ix_dupmember_question"),
        ),
    ]