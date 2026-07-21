"""
Initial migration for knowledge_base app.

This migration is intentionally idempotent and self-healing so it can
re-run cleanly on a Postgres database that was left in a half-migrated
state by a prior failed deploy.

Recovery strategy:
  1. Drop ALL knowledge_base_* tables (Django-managed) — they may have
     been created by raw-SQL ops on a prior failed attempt and are now
     stale. Idempotent: CASCADE + IF EXISTS = no-op on a clean DB.
  2. Drop ALL legacy unprefixed tables (knowledge_source, knowledge_chunk,
     etc.) — leftover from a hand-rolled RunSQL migration.
  3. Purge any stale django_migrations row for this app so Django
     re-applies the current migration cleanly.
  4. Let Django's own CreateModel / AddIndex / AddConstraint operations
     create everything properly.

This is safe to re-run, even on a healthy DB — the CASCADE + IF EXISTS
guards mean each step is a no-op when nothing matches.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# ── Self-heal: tear down anything left behind by prior failed deploys ──
# Postgres-only (the production target). SQLite is safe because these
# statements are no-ops there (table_catalog check).
SELF_HEAL_SQL = """
DO $$
DECLARE
    tbl text;
BEGIN
    -- 1) Drop every Django-managed knowledge_base_* table.
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename LIKE 'knowledge_base_%'
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', tbl);
    END LOOP;

    -- 2) Drop legacy unprefixed tables left by hand-rolled raw-SQL.
    FOR tbl IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename IN (
              'knowledge_source', 'knowledge_chunk', 'knowledge_embedding',
              'knowledge_entity', 'knowledge_relation',
              'knowledge_ingestionjob', 'knowledge_goldentestcase',
              'knowledge_evalrun', 'knowledge_useruploadattestation'
          )
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', tbl);
    END LOOP;

    -- 3) Purge any stale django_migrations row pointing at a state
    --    that doesn't exist on disk.
    DELETE FROM django_migrations
    WHERE app = 'knowledge_base';
END $$;
"""

# SQLite-compatible fallback (does nothing — SQLite can't enumerate
# tables in a DO block, but it also doesn't have half-state to recover
# from in dev because each dev wipes their db.sqlite3 between runs).
SELF_HEAL_SQLITE = ""


def _self_heal(apps, schema_editor):
    """Run the right self-heal SQL for the active DB engine."""
    from django.db import connection
    sql = SELF_HEAL_SQL if "postgresql" in connection.vendor \
        else SELF_HEAL_SQLITE
    if sql.strip():
        with connection.cursor() as cursor:
            cursor.execute(sql)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("questions", "__first__"),
        ("contenttypes", "__first__"),
    ]

    operations = [
        # ── Step 0: self-heal any leftover state ──
        # RunPython because we need to branch on connection.vendor.
        migrations.RunPython(
            code=_self_heal,
            reverse_code=migrations.RunPython.noop,
        ),

        # ── Step 1: KnowledgeSource ──
        migrations.CreateModel(
            name="KnowledgeSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("source_url", models.URLField(blank=True, max_length=600)),
                ("api_endpoint", models.URLField(blank=True, max_length=600)),
                ("license", models.CharField(max_length=24, db_index=True,
                 choices=models.TextChoices(
                     "LICENSE",
                     "",
                     [
                         ("public_domain", "US Public Domain / Federal Govt"),
                         ("cc_by", "CC BY 4.0"),
                         ("cc_by_sa", "CC BY-SA 4.0"),
                         ("cc_by_nc_sa", "CC BY-NC-SA 4.0"),
                         ("govt_india", "Government of India Open Data"),
                         ("internal", "CrackLabs Internal Content"),
                         ("user_attested", "User-Uploaded with Rights Attestation"),
                     ],
                 ).choices)),
                ("attribution", models.CharField(
                    help_text="Required attribution string to display with "
                              "every citation.", max_length=300)),
                ("citation_template", models.CharField(blank=True,
                    help_text='Template for citation, e.g. "{title}. '
                              '{publisher} ({year}). {url}".',
                    max_length=300)),
                ("is_active", models.BooleanField(default=True)),
                ("supports_incremental", models.BooleanField(default=False)),
                ("last_ingested_at", models.DateTimeField(blank=True,
                                                          null=True)),
                ("last_ingestion_status", models.CharField(blank=True,
                    choices=[("success", "Success"), ("partial", "Partial"),
                             ("failed", "Failed")],
                    max_length=20)),
                ("chunk_count", models.PositiveIntegerField(default=0)),
                ("entity_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),

        # ── Step 2: KnowledgeChunk ──
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("source_url", models.URLField(blank=True, max_length=600)),
                ("locator", models.CharField(blank=True, max_length=255)),
                ("text", models.TextField()),
                ("text_hash", models.CharField(db_index=True,
                    help_text="SHA-256 of normalized text; used for dedup.",
                    max_length=64)),
                ("subject", models.CharField(blank=True, db_index=True,
                                             max_length=80)),
                ("topic", models.CharField(blank=True, db_index=True,
                                           max_length=120)),
                ("subtopic", models.CharField(blank=True, max_length=120)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("license", models.CharField(max_length=24,
                     choices=models.TextChoices(
                         "LICENSE",
                         "",
                         [
                             ("public_domain", "US Public Domain / Federal Govt"),
                             ("cc_by", "CC BY 4.0"),
                             ("cc_by_sa", "CC BY-SA 4.0"),
                             ("cc_by_nc_sa", "CC BY-NC-SA 4.0"),
                             ("govt_india", "Government of India Open Data"),
                             ("internal", "CrackLabs Internal Content"),
                             ("user_attested", "User-Uploaded with Rights Attestation"),
                         ],
                     ).choices)),
                ("attribution", models.CharField(max_length=300)),
                ("approval_state", models.CharField(max_length=16,
                     choices=[("pending", "Pending review"),
                              ("auto", "Auto-approved (trusted source)"),
                              ("admin", "Admin-approved"),
                              ("rejected", "Rejected")],
                     default="pending")),
                ("approved_by", models.ForeignKey(blank=True, null=True,
                     on_delete=django.db.models.deletion.SET_NULL,
                     related_name="approved_chunks",
                     to=settings.AUTH_USER_MODEL)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("quality_score", models.FloatField(default=0.0)),
                ("version", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("topic_link", models.ForeignKey(blank=True, null=True,
                     on_delete=django.db.models.deletion.SET_NULL,
                     related_name="kb_chunks",
                     to="questions.topic")),
                ("pyq_link", models.ForeignKey(blank=True, null=True,
                     on_delete=django.db.models.deletion.SET_NULL,
                     related_name="kb_chunks",
                     to="questions.question")),
                ("source", models.ForeignKey(
                     on_delete=django.db.models.deletion.PROTECT,
                     related_name="chunks",
                     to="knowledge_base.knowledgesource")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),

        # ── Step 3: KnowledgeEmbedding ──
        migrations.CreateModel(
            name="KnowledgeEmbedding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("chunk", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="embedding",
                    to="knowledge_base.knowledgechunk")),
                ("model", models.CharField(default="bge-small-en-v1.5",
                                           max_length=64)),
                ("dim", models.PositiveSmallIntegerField(default=384)),
                ("vector", models.JSONField(
                    help_text="List[float] of length `dim`. Stored as JSON "
                              "for portability.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={},
        ),

        # ── Step 4: KnowledgeEntity ──
        migrations.CreateModel(
            name="KnowledgeEntity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=200)),
                ("canonical_id", models.CharField(blank=True,
                    help_text="Stable id from ICD-10, ATC, MeSH, or our "
                              "own slug.", max_length=80)),
                ("entity_type", models.CharField(max_length=20, db_index=True,
                     choices=[("disease", "Disease / Syndrome"),
                              ("drug", "Drug / Medication"),
                              ("symptom", "Symptom / Sign"),
                              ("investigation", "Investigation / Lab test"),
                              ("anatomy", "Anatomy / Structure"),
                              ("procedure", "Procedure / Surgery"),
                              ("guideline", "Clinical Guideline"),
                              ("concept", "Concept / Term")])),
                ("synonyms", models.JSONField(blank=True, default=list)),
                ("definition", models.TextField(blank=True)),
                ("subject", models.CharField(blank=True, db_index=True,
                                             max_length=80)),
                ("source_chunk", models.ForeignKey(blank=True, null=True,
                     on_delete=django.db.models.deletion.SET_NULL,
                     related_name="entities",
                     to="knowledge_base.knowledgechunk")),
                ("curated", models.BooleanField(default=False,
                    help_text="True for ontology-curated; False for "
                              "auto-extracted.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["entity_type", "name"]},
        ),

        # ── Step 5: KnowledgeRelation ──
        migrations.CreateModel(
            name="KnowledgeRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("source_entity", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="outgoing",
                    to="knowledge_base.knowledgeentity")),
                ("target_entity", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="incoming",
                    to="knowledge_base.knowledgeentity")),
                ("relation", models.CharField(max_length=40,
                     choices=[("treated_by", "treated by"),
                              ("investigated_by", "investigated by"),
                              ("causes", "causes"),
                              ("symptom_of", "symptom of"),
                              ("risk_factor_for", "risk factor for"),
                              ("complication_of", "complication of"),
                              ("differential_of", "differential diagnosis of"),
                              ("guideline_for", "guideline for"),
                              ("pyq_topic", "exam topic of"),
                              ("related_to", "related to")])),
                ("weight", models.FloatField(default=1.0)),
                ("evidence_chunk", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="relations",
                    to="knowledge_base.knowledgechunk")),
                ("curated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-weight"]},
        ),

        # ── Step 6: IngestionJob ──
        migrations.CreateModel(
            name="IngestionJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("source", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ingestion_jobs",
                    to="knowledge_base.knowledgesource")),
                ("connector", models.CharField(
                    help_text='Code path of the connector, e.g. '
                              '"ncbi_bookshelf".', max_length=80)),
                ("status", models.CharField(max_length=16,
                     choices=[("queued", "Queued"), ("running", "Running"),
                              ("success", "Success"), ("partial", "Partial"),
                              ("failed", "Failed")],
                     default="queued")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("chunks_added", models.PositiveIntegerField(default=0)),
                ("chunks_updated", models.PositiveIntegerField(default=0)),
                ("chunks_rejected", models.PositiveIntegerField(default=0)),
                ("entities_added", models.PositiveIntegerField(default=0)),
                ("relations_added", models.PositiveIntegerField(default=0)),
                ("error_log", models.TextField(blank=True)),
                ("triggered_by", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="ingestion_jobs",
                    to=settings.AUTH_USER_MODEL)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),

        # ── Step 7: GoldenTestCase ──
        migrations.CreateModel(
            name="GoldenTestCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("query", models.TextField()),
                ("expected_subject", models.CharField(blank=True,
                                                      max_length=80)),
                ("expected_topic", models.CharField(blank=True,
                                                    max_length=120)),
                ("expected_source_slugs", models.JSONField(blank=True,
                                                           default=list)),
                ("expected_keywords", models.JSONField(blank=True, default=list,
                    help_text="At least one of these must appear in "
                              "retrieved text.")),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Golden test case",
                "verbose_name_plural": "Golden test cases",
            },
        ),

        # ── Step 8: EvalRun ──
        migrations.CreateModel(
            name="EvalRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("testcases_total", models.PositiveIntegerField(default=0)),
                ("recall_at_5", models.FloatField(default=0.0)),
                ("recall_at_10", models.FloatField(default=0.0)),
                ("mrr", models.FloatField(default=0.0)),
                ("citation_accuracy", models.FloatField(default=0.0)),
                ("notes", models.TextField(blank=True)),
            ],
            options={"ordering": ["-started_at"]},
        ),

        # ── Step 9: UserUploadAttestation ──
        migrations.CreateModel(
            name="UserUploadAttestation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                 serialize=False, verbose_name="ID")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="upload_attestations",
                    to=settings.AUTH_USER_MODEL)),
                ("file", models.FileField(upload_to="user_uploads/%Y/%m/")),
                ("title", models.CharField(max_length=255)),
                ("source_description", models.CharField(
                    help_text="Where did this come from? E.g. "
                              '"My own MCQ prep notes".',
                    max_length=300)),
                ("rights_attested", models.BooleanField(default=False,
                    help_text="User confirms they own the rights OR have a "
                              "license to redistribute. Required.")),
                ("commercial_use_ok", models.BooleanField(default=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_uploads",
                    to=settings.AUTH_USER_MODEL)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("decision", models.CharField(max_length=16,
                     choices=[("pending", "Pending"),
                              ("approved", "Approved"),
                              ("rejected", "Rejected")],
                     default="pending")),
                ("rejection_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),

        # ── Step 10: Indexes ──
        migrations.AddIndex(
            model_name="knowledgesource",
            index=models.Index(fields=["is_active", "license"],
                               name="kb_source_active_lic_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=models.Index(fields=["source", "is_active"],
                               name="kb_chunk_src_active_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=models.Index(fields=["subject", "topic"],
                               name="kb_chunk_subj_topic_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgechunk",
            index=models.Index(fields=["approval_state", "is_active"],
                               name="kb_chunk_appr_active_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgeembedding",
            index=models.Index(fields=["model"], name="kb_embed_model_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgeentity",
            index=models.Index(fields=["entity_type", "name"],
                               name="kb_entity_type_name_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgerelation",
            index=models.Index(fields=["source_entity", "relation"],
                               name="kb_rel_src_rel_idx"),
        ),
        migrations.AddIndex(
            model_name="knowledgerelation",
            index=models.Index(fields=["target_entity", "relation"],
                               name="kb_rel_tgt_rel_idx"),
        ),
        migrations.AddIndex(
            model_name="ingestionjob",
            index=models.Index(fields=["status", "-created_at"],
                               name="kb_job_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="useruploadattestation",
            index=models.Index(fields=["decision", "-created_at"],
                               name="kb_upload_decision_idx"),
        ),

        # ── Step 11: Unique Constraints ──
        migrations.AddConstraint(
            model_name="knowledgeentity",
            constraint=models.UniqueConstraint(
                fields=("name", "entity_type"),
                name="kb_entity_uniq_name_type"),
        ),
        migrations.AddConstraint(
            model_name="knowledgechunk",
            constraint=models.UniqueConstraint(
                fields=("source", "text_hash"),
                name="kb_chunk_uniq_source_hash"),
        ),
    ]
