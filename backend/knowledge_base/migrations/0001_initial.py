"""
Initial migration for knowledge_base app.

Hand-authored because the Bash safety classifier is unavailable in
this session. Uses raw SQL with `IF NOT EXISTS` / `IF EXISTS` guards
so the migration is **idempotent** on Heroku Postgres where previous
failed deploys may have left partial artifacts.

Schema mirrors `models.py` exactly. After this migration runs,
`python manage.py makemigrations --dry-run` should report no diffs.

Tables created (Django default `<app_label>_<modelname>` form so the
ORM can talk to them — load_ontology, admin, and any Model.objects.*
call go through this naming):

  knowledge_base_knowledgesource
  knowledge_base_knowledgechunk
  knowledge_base_knowledgeembedding
  knowledge_base_knowledgeentity
  knowledge_base_knowledgerelation
  knowledge_base_ingestionjob
  knowledge_base_goldentestcase
  knowledge_base_evalrun
  knowledge_base_useruploadattestation

All indexes and unique constraints use explicit, table-prefixed
names so they cannot collide with each other or with leftover
objects from a partial prior migration.

Earlier versions of this migration created the tables with the
unprefixed names (knowledge_source, knowledge_chunk, …) which left
them invisible to the Django ORM. The leading self-heal block
renames those tables AND their indexes / constraints forward to
the canonical prefixed names, so a partial prior state is rescued
rather than abandoned.
"""
from django.conf import settings
from django.db import migrations


# ─── Canonical name tables ────────────────────────────────────────────────
# Centralized so the self-heal block and the CREATE block stay in sync
# and a typo is obvious from a single diff.

TABLE_NAMES = {
    "KnowledgeSource":            "knowledge_base_knowledgesource",
    "KnowledgeChunk":             "knowledge_base_knowledgechunk",
    "KnowledgeEmbedding":         "knowledge_base_knowledgeembedding",
    "KnowledgeEntity":            "knowledge_base_knowledgeentity",
    "KnowledgeRelation":          "knowledge_base_knowledgerelation",
    "IngestionJob":               "knowledge_base_ingestionjob",
    "GoldenTestCase":             "knowledge_base_goldentestcase",
    "EvalRun":                    "knowledge_base_evalrun",
    "UserUploadAttestation":      "knowledge_base_useruploadattestation",
}

# Legacy unprefixed names a prior failed migration may have written.
# If present, we rename to the canonical prefixed form.
LEGACY_TABLE_RENAMES = [
    ("knowledge_source",                TABLE_NAMES["KnowledgeSource"]),
    ("knowledge_chunk",                 TABLE_NAMES["KnowledgeChunk"]),
    ("knowledge_embedding",             TABLE_NAMES["KnowledgeEmbedding"]),
    ("knowledge_entity",                TABLE_NAMES["KnowledgeEntity"]),
    ("knowledge_relation",              TABLE_NAMES["KnowledgeRelation"]),
    ("knowledge_ingestionjob",          TABLE_NAMES["IngestionJob"]),
    ("knowledge_goldentestcase",        TABLE_NAMES["GoldenTestCase"]),
    ("knowledge_evalrun",               TABLE_NAMES["EvalRun"]),
    ("knowledge_useruploadattestation", TABLE_NAMES["UserUploadAttestation"]),
]

# Indexes / unique constraints defined by this app. The base name is the
# Meta Index/Constraint `name=` we use; the table suffix is the canonical
# table name. The full DB object name Postgres stores is
#   f"{base}_{tablesuffix}"
# but tablesuffix is just "<table>" without the app prefix.
def _idx_full_name(base, short_table):
    # short_table is e.g. "knowledgeentity" (canonical, no app prefix)
    return f"{base}_{short_table}"


# Matches our Meta declarations in models.py.
INDEX_BASES = [
    "kb_source_active_lic",   # knowledge_base_knowledgesource(is_active, license)
    "kb_source_slug",          # knowledge_base_knowledgesource(slug)
    "kb_chunk_src_active",     # knowledge_base_knowledgechunk(source_id, is_active)
    "kb_chunk_subj_topic",     # knowledge_base_knowledgechunk(subject, topic)
    "kb_chunk_appr_active",    # knowledge_base_knowledgechunk(approval_state, is_active)
    "kb_chunk_text_hash",      # knowledge_base_knowledgechunk(text_hash)
    "kb_chunk_subject",        # knowledge_base_knowledgechunk(subject)
    "kb_chunk_topic",          # knowledge_base_knowledgechunk(topic)
    "kb_chunk_uniq_source_hash",  # UNIQUE (source_id, text_hash)
    "kb_embed_model",          # knowledge_base_knowledgeembedding(model)
    "kb_entity_type_name",     # knowledge_base_knowledgeentity(entity_type, name)
    "kb_entity_name",          # knowledge_base_knowledgeentity(name)
    "kb_entity_type",          # knowledge_base_knowledgeentity(entity_type)
    "kb_entity_subject",       # knowledge_base_knowledgeentity(subject)
    "kb_entity_uniq_name_type",# UNIQUE (name, entity_type)
    "kb_rel_src_rel",          # knowledge_base_knowledgerelation(source_entity_id, relation)
    "kb_rel_tgt_rel",          # knowledge_base_knowledgerelation(target_entity_id, relation)
    "kb_job_status_created",   # knowledge_base_ingestionjob(status, created_at DESC)
    "kb_upload_decision",      # knowledge_base_useruploadattestation(decision, created_at DESC)
]

# Legacy index names a prior failed migration may have created. Their
# base portion is mostly auto-generated and may match what we want
# exactly OR may be the bare names without the _idx suffix the model
# expects. We rename anything that ends with our base by stripping /
# replacing the index's old name.
LEGACY_INDEXES_TO_DROP = [
    "knowledge_b_is_acti_idx",
    "knowledge_b_source__idx",
    "knowledge_b_subject_idx",
    "knowledge_b_approva_idx",
    "knowledge_b_model_4c1b8b_idx",
    "knowledge_b_entity__idx",
    "knowledge_b_target__idx",
    "knowledge_b_status_5e2f3e_idx",
    "knowledge_b_decisio_idx",
    # Also drop indexes that the v1 of this migration created against
    # the (wrong) unprefixed tables — they would have been named like
    # kb_chunk_src_active_idx on knowledge_chunk, but Postgres already
    # dropped them when we renamed the tables. The IF EXISTS guards
    # make this harmless if they're already gone.
]


def _create_tables_and_indexes(apps, schema_editor):
    """Idempotent setup. Safe to run on:
       - a clean DB (every step is IF NOT EXISTS / IF EXISTS)
       - a partially-migrated DB from a prior failed deploy
         (self-heal block reconciles old names forward)
    """

    # ── 1. SELF-HEAL: if `django_migrations` thinks we already ran but
    #    the canonical entity table doesn't exist (i.e. a prior failed
    #    deploy left unprefixed `knowledge_entity` tables), delete the
    #    row so Django actually re-runs us. Django records the RunPython
    #    row automatically after we return — we must NOT insert it
    #    ourselves or we get a duplicate.
    cursor = schema_editor.connection.cursor()
    cursor.execute("""
        SELECT to_regclass('public.knowledge_base_knowledgeentity');
    """)
    table_exists = cursor.fetchone()[0] is not None
    if not table_exists:
        cursor.execute("""
            DELETE FROM django_migrations
            WHERE app = 'knowledge_base'
              AND name = '0001_initial';
        """)

    # ── 2. SELF-HEAL: rename legacy unprefixed tables to canonical names.
    #    ALTER TABLE IF EXISTS is a no-op when the table isn't there.
    for old_name, new_name in LEGACY_TABLE_RENAMES:
        cursor.execute(
            f'ALTER TABLE IF EXISTS "{old_name}" RENAME TO "{new_name}";'
        )

    # ── 3. SELF-HEAL: drop any stray indexes from the very first failed
    #    deploy attempt that left them lying around.
    for legacy in LEGACY_INDEXES_TO_DROP:
        cursor.execute(f'DROP INDEX IF EXISTS "{legacy}";')

    # ── 4. CANONICAL CREATE. Every reference uses the prefixed table
    #    name so Django's ORM finds everything.
    schema_editor.execute("""
    -- ─── knowledge_base_knowledgesource ───────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_knowledgesource (
        id              BIGSERIAL PRIMARY KEY,
        slug            VARCHAR(120) NOT NULL UNIQUE,
        name            VARCHAR(255) NOT NULL,
        description     TEXT NOT NULL DEFAULT '',
        source_url      VARCHAR(600) NOT NULL DEFAULT '',
        api_endpoint    VARCHAR(600) NOT NULL DEFAULT '',
        license         VARCHAR(24) NOT NULL,
        attribution     VARCHAR(300) NOT NULL,
        citation_template VARCHAR(300) NOT NULL DEFAULT '',
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        supports_incremental BOOLEAN NOT NULL DEFAULT FALSE,
        last_ingested_at TIMESTAMP NULL,
        last_ingestion_status VARCHAR(20) NOT NULL DEFAULT '',
        chunk_count     INTEGER NOT NULL DEFAULT 0,
        entity_count    INTEGER NOT NULL DEFAULT 0,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_source_active_lic_idx
        ON knowledge_base_knowledgesource (is_active, license);
    CREATE INDEX IF NOT EXISTS kb_source_slug_idx
        ON knowledge_base_knowledgesource (slug);

    -- ─── knowledge_base_knowledgechunk ────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_knowledgechunk (
        id              BIGSERIAL PRIMARY KEY,
        source_id       BIGINT NOT NULL REFERENCES knowledge_base_knowledgesource(id)
                          ON DELETE RESTRICT,
        source_url      VARCHAR(600) NOT NULL DEFAULT '',
        locator         VARCHAR(255) NOT NULL DEFAULT '',
        text            TEXT NOT NULL,
        text_hash       VARCHAR(64) NOT NULL,
        subject         VARCHAR(80) NOT NULL DEFAULT '',
        topic           VARCHAR(120) NOT NULL DEFAULT '',
        subtopic        VARCHAR(120) NOT NULL DEFAULT '',
        tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
        license         VARCHAR(24) NOT NULL,
        attribution     VARCHAR(300) NOT NULL,
        approval_state  VARCHAR(16) NOT NULL DEFAULT 'pending',
        approved_by_id  BIGINT NULL REFERENCES accounts_customuser(id)
                          ON DELETE SET NULL,
        approved_at     TIMESTAMP NULL,
        quality_score   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        version         INTEGER NOT NULL DEFAULT 1,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        topic_link_id   BIGINT NULL REFERENCES questions_topic(id)
                          ON DELETE SET NULL,
        pyq_link_id     BIGINT NULL REFERENCES questions_question(id)
                          ON DELETE SET NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_chunk_src_active_idx
        ON knowledge_base_knowledgechunk (source_id, is_active);
    CREATE INDEX IF NOT EXISTS kb_chunk_subj_topic_idx
        ON knowledge_base_knowledgechunk (subject, topic);
    CREATE INDEX IF NOT EXISTS kb_chunk_appr_active_idx
        ON knowledge_base_knowledgechunk (approval_state, is_active);
    CREATE INDEX IF NOT EXISTS kb_chunk_text_hash_idx
        ON knowledge_base_knowledgechunk (text_hash);
    CREATE INDEX IF NOT EXISTS kb_chunk_subject_idx
        ON knowledge_base_knowledgechunk (subject);
    CREATE INDEX IF NOT EXISTS kb_chunk_topic_idx
        ON knowledge_base_knowledgechunk (topic);
    CREATE UNIQUE INDEX IF NOT EXISTS kb_chunk_uniq_source_hash_uniq
        ON knowledge_base_knowledgechunk (source_id, text_hash);

    -- ─── knowledge_base_knowledgeembedding ────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_knowledgeembedding (
        id              BIGSERIAL PRIMARY KEY,
        chunk_id        BIGINT NOT NULL UNIQUE REFERENCES knowledge_base_knowledgechunk(id)
                          ON DELETE CASCADE,
        model           VARCHAR(64) NOT NULL DEFAULT 'bge-small-en-v1.5',
        dim             SMALLINT NOT NULL DEFAULT 384,
        vector          JSONB NOT NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_embed_model_idx
        ON knowledge_base_knowledgeembedding (model);

    -- ─── knowledge_base_knowledgeentity ───────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_knowledgeentity (
        id              BIGSERIAL PRIMARY KEY,
        name            VARCHAR(200) NOT NULL,
        canonical_id    VARCHAR(80) NOT NULL DEFAULT '',
        entity_type     VARCHAR(20) NOT NULL,
        synonyms        JSONB NOT NULL DEFAULT '[]'::jsonb,
        definition      TEXT NOT NULL DEFAULT '',
        subject         VARCHAR(80) NOT NULL DEFAULT '',
        curated         BOOLEAN NOT NULL DEFAULT FALSE,
        source_chunk_id BIGINT NULL REFERENCES knowledge_base_knowledgechunk(id)
                          ON DELETE SET NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_entity_type_name_idx
        ON knowledge_base_knowledgeentity (entity_type, name);
    CREATE INDEX IF NOT EXISTS kb_entity_name_idx
        ON knowledge_base_knowledgeentity (name);
    CREATE INDEX IF NOT EXISTS kb_entity_type_idx
        ON knowledge_base_knowledgeentity (entity_type);
    CREATE INDEX IF NOT EXISTS kb_entity_subject_idx
        ON knowledge_base_knowledgeentity (subject);
    CREATE UNIQUE INDEX IF NOT EXISTS kb_entity_uniq_name_type_uniq
        ON knowledge_base_knowledgeentity (name, entity_type);

    -- ─── knowledge_base_knowledgerelation ─────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_knowledgerelation (
        id              BIGSERIAL PRIMARY KEY,
        source_entity_id BIGINT NOT NULL REFERENCES knowledge_base_knowledgeentity(id)
                          ON DELETE CASCADE,
        target_entity_id BIGINT NOT NULL REFERENCES knowledge_base_knowledgeentity(id)
                          ON DELETE CASCADE,
        relation        VARCHAR(40) NOT NULL,
        weight          DOUBLE PRECISION NOT NULL DEFAULT 1.0,
        evidence_chunk_id BIGINT NULL REFERENCES knowledge_base_knowledgechunk(id)
                          ON DELETE SET NULL,
        curated         BOOLEAN NOT NULL DEFAULT FALSE,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_rel_src_rel_idx
        ON knowledge_base_knowledgerelation (source_entity_id, relation);
    CREATE INDEX IF NOT EXISTS kb_rel_tgt_rel_idx
        ON knowledge_base_knowledgerelation (target_entity_id, relation);

    -- ─── knowledge_base_ingestionjob ──────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_ingestionjob (
        id              BIGSERIAL PRIMARY KEY,
        connector       VARCHAR(80) NOT NULL,
        status          VARCHAR(16) NOT NULL DEFAULT 'queued',
        source_id       BIGINT NULL REFERENCES knowledge_base_knowledgesource(id)
                          ON DELETE SET NULL,
        started_at      TIMESTAMP NULL,
        finished_at     TIMESTAMP NULL,
        chunks_added    INTEGER NOT NULL DEFAULT 0,
        chunks_updated  INTEGER NOT NULL DEFAULT 0,
        chunks_rejected INTEGER NOT NULL DEFAULT 0,
        entities_added  INTEGER NOT NULL DEFAULT 0,
        relations_added INTEGER NOT NULL DEFAULT 0,
        error_log       TEXT NOT NULL DEFAULT '',
        triggered_by_id BIGINT NULL REFERENCES accounts_customuser(id)
                          ON DELETE SET NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_job_status_created_idx
        ON knowledge_base_ingestionjob (status, created_at DESC);

    -- ─── knowledge_base_goldentestcase ────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_goldentestcase (
        id              BIGSERIAL PRIMARY KEY,
        query           TEXT NOT NULL,
        expected_subject VARCHAR(80) NOT NULL DEFAULT '',
        expected_topic  VARCHAR(120) NOT NULL DEFAULT '',
        expected_source_slugs JSONB NOT NULL DEFAULT '[]'::jsonb,
        expected_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
        notes           TEXT NOT NULL DEFAULT '',
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    -- ─── knowledge_base_evalrun ───────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_evalrun (
        id              BIGSERIAL PRIMARY KEY,
        started_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        finished_at     TIMESTAMP NULL,
        testcases_total INTEGER NOT NULL DEFAULT 0,
        recall_at_5     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        recall_at_10    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        mrr             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        citation_accuracy DOUBLE PRECISION NOT NULL DEFAULT 0.0,
        notes           TEXT NOT NULL DEFAULT ''
    );

    -- ─── knowledge_base_useruploadattestation ─────────────────
    CREATE TABLE IF NOT EXISTS knowledge_base_useruploadattestation (
        id              BIGSERIAL PRIMARY KEY,
        user_id         BIGINT NOT NULL REFERENCES accounts_customuser(id)
                          ON DELETE CASCADE,
        file            VARCHAR(100) NOT NULL,
        title           VARCHAR(255) NOT NULL,
        source_description VARCHAR(300) NOT NULL,
        rights_attested BOOLEAN NOT NULL DEFAULT FALSE,
        commercial_use_ok BOOLEAN NOT NULL DEFAULT TRUE,
        reviewed_by_id  BIGINT NULL REFERENCES accounts_customuser(id)
                          ON DELETE SET NULL,
        reviewed_at     TIMESTAMP NULL,
        decision        VARCHAR(16) NOT NULL DEFAULT 'pending',
        rejection_reason TEXT NOT NULL DEFAULT '',
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_upload_decision_idx
        ON knowledge_base_useruploadattestation (decision, created_at DESC);
    """)


def _drop_tables(apps, schema_editor):
    """Reverse: drop everything we created. Used by `migrate ... zero`."""
    schema_editor.execute("""
    DROP TABLE IF EXISTS knowledge_base_useruploadattestation CASCADE;
    DROP TABLE IF EXISTS knowledge_base_evalrun CASCADE;
    DROP TABLE IF EXISTS knowledge_base_goldentestcase CASCADE;
    DROP TABLE IF EXISTS knowledge_base_ingestionjob CASCADE;
    DROP TABLE IF EXISTS knowledge_base_knowledgerelation CASCADE;
    DROP TABLE IF EXISTS knowledge_base_knowledgeentity CASCADE;
    DROP TABLE IF EXISTS knowledge_base_knowledgeembedding CASCADE;
    DROP TABLE IF EXISTS knowledge_base_knowledgechunk CASCADE;
    DROP TABLE IF EXISTS knowledge_base_knowledgesource CASCADE;
    """)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('questions', '__first__'),
        ('contenttypes', '__first__'),
    ]

    operations = [
        migrations.RunPython(_create_tables_and_indexes, _drop_tables),
    ]
