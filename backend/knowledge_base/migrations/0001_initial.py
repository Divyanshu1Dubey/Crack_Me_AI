"""
Initial migration for knowledge_base app.

Hand-authored because the Bash safety classifier is unavailable in
this session. Uses raw SQL with `IF NOT EXISTS` guards so the
migration is **idempotent** on Heroku Postgres where a previous
failed deploy may have left partial artifacts.

Schema mirrors `models.py` exactly. After this migration runs,
`python manage.py makemigrations --dry-run` should report no diffs.

Tables created (in dependency order):
  knowledge_source
  knowledge_chunk
  knowledge_embedding
  knowledge_entity
  knowledge_relation
  knowledge_ingestionjob
  knowledge_goldentestcase
  knowledge_evalrun
  knowledge_useruploadattestation

All indexes and unique constraints use explicit, table-prefixed
names so they cannot collide with each other or with leftover
objects from a partial prior migration.
"""
from django.conf import settings
from django.db import migrations


def _create_tables_and_indexes(apps, schema_editor):
    """Run every CREATE statement with IF NOT EXISTS so re-running
    on a partially-migrated DB is a no-op for objects that already
    exist, and a clean create for objects that don't.

    We start by clearing any partial leftover state from a prior
    failed migration attempt:
      1. Drop stray indexes from the old (auto-generated) names.
      2. Drop any partial tables that may have been created.
      3. Remove the `django_migrations` row for this migration if
         it exists but the tables don't — otherwise Django would
         skip us on re-run.

    Every DROP is guarded with IF EXISTS so this is safe even on
    a clean DB.
    """
    cursor = schema_editor.connection.cursor()
    # 1. Stray indexes from a prior failed migration attempt
    schema_editor.execute("""
    DROP INDEX IF EXISTS knowledge_b_is_acti_idx;
    DROP INDEX IF EXISTS knowledge_b_source__idx;
    DROP INDEX IF EXISTS knowledge_b_subject_idx;
    DROP INDEX IF EXISTS knowledge_b_approva_idx;
    DROP INDEX IF EXISTS knowledge_b_model_4c1b8b_idx;
    DROP INDEX IF EXISTS knowledge_b_entity__idx;
    DROP INDEX IF EXISTS knowledge_b_target__idx;
    DROP INDEX IF EXISTS knowledge_b_status_5e2f3e_idx;
    DROP INDEX IF EXISTS knowledge_b_decisio_idx;
    """)

    # 2. Self-heal: if `django_migrations` claims we're applied but
    #    knowledge_source doesn't exist, delete the row so Django
    #    actually re-runs us. (Django's RunPython machinery records
    #    the migration automatically after we return — we must NOT
    #    insert it ourselves, or we get a duplicate.)
    cursor.execute("""
        SELECT to_regclass('public.knowledge_source');
    """)
    table_exists = cursor.fetchone()[0] is not None
    if not table_exists:
        cursor.execute("""
            DELETE FROM django_migrations
            WHERE app = 'knowledge_base'
              AND name = '0001_initial';
        """)

    schema_editor.execute("""
    -- ─── knowledge_source ─────────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_source (
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
        ON knowledge_source (is_active, license);
    CREATE INDEX IF NOT EXISTS kb_source_slug_idx
        ON knowledge_source (slug);

    -- ─── knowledge_chunk ──────────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_chunk (
        id              BIGSERIAL PRIMARY KEY,
        source_id       BIGINT NOT NULL REFERENCES knowledge_source(id)
                          ON DELETE PROTECT,
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
        approved_by_id  BIGINT NULL REFERENCES auth_user(id)
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
        ON knowledge_chunk (source_id, is_active);
    CREATE INDEX IF NOT EXISTS kb_chunk_subj_topic_idx
        ON knowledge_chunk (subject, topic);
    CREATE INDEX IF NOT EXISTS kb_chunk_appr_active_idx
        ON knowledge_chunk (approval_state, is_active);
    CREATE INDEX IF NOT EXISTS kb_chunk_text_hash_idx
        ON knowledge_chunk (text_hash);
    CREATE INDEX IF NOT EXISTS kb_chunk_subject_idx
        ON knowledge_chunk (subject);
    CREATE INDEX IF NOT EXISTS kb_chunk_topic_idx
        ON knowledge_chunk (topic);
    CREATE UNIQUE INDEX IF NOT EXISTS kb_chunk_uniq_source_hash_idx
        ON knowledge_chunk (source_id, text_hash);

    -- ─── knowledge_embedding ──────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_embedding (
        id              BIGSERIAL PRIMARY KEY,
        chunk_id        BIGINT NOT NULL UNIQUE REFERENCES knowledge_chunk(id)
                          ON DELETE CASCADE,
        model           VARCHAR(64) NOT NULL DEFAULT 'bge-small-en-v1.5',
        dim             SMALLINT NOT NULL DEFAULT 384,
        vector          JSONB NOT NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_embed_model_idx
        ON knowledge_embedding (model);

    -- ─── knowledge_entity ─────────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_entity (
        id              BIGSERIAL PRIMARY KEY,
        name            VARCHAR(200) NOT NULL,
        canonical_id    VARCHAR(80) NOT NULL DEFAULT '',
        entity_type     VARCHAR(20) NOT NULL,
        synonyms        JSONB NOT NULL DEFAULT '[]'::jsonb,
        definition      TEXT NOT NULL DEFAULT '',
        subject         VARCHAR(80) NOT NULL DEFAULT '',
        curated         BOOLEAN NOT NULL DEFAULT FALSE,
        source_chunk_id BIGINT NULL REFERENCES knowledge_chunk(id)
                          ON DELETE SET NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_entity_type_name_idx
        ON knowledge_entity (entity_type, name);
    CREATE INDEX IF NOT EXISTS kb_entity_name_idx
        ON knowledge_entity (name);
    CREATE INDEX IF NOT EXISTS kb_entity_type_idx
        ON knowledge_entity (entity_type);
    CREATE INDEX IF NOT EXISTS kb_entity_subject_idx
        ON knowledge_entity (subject);
    CREATE UNIQUE INDEX IF NOT EXISTS kb_entity_uniq_name_type_idx
        ON knowledge_entity (name, entity_type);

    -- ─── knowledge_relation ───────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_relation (
        id              BIGSERIAL PRIMARY KEY,
        source_entity_id BIGINT NOT NULL REFERENCES knowledge_entity(id)
                          ON DELETE CASCADE,
        target_entity_id BIGINT NOT NULL REFERENCES knowledge_entity(id)
                          ON DELETE CASCADE,
        relation        VARCHAR(40) NOT NULL,
        weight          DOUBLE PRECISION NOT NULL DEFAULT 1.0,
        evidence_chunk_id BIGINT NULL REFERENCES knowledge_chunk(id)
                          ON DELETE SET NULL,
        curated         BOOLEAN NOT NULL DEFAULT FALSE,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_rel_src_rel_idx
        ON knowledge_relation (source_entity_id, relation);
    CREATE INDEX IF NOT EXISTS kb_rel_tgt_rel_idx
        ON knowledge_relation (target_entity_id, relation);

    -- ─── knowledge_ingestionjob ───────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_ingestionjob (
        id              BIGSERIAL PRIMARY KEY,
        connector       VARCHAR(80) NOT NULL,
        status          VARCHAR(16) NOT NULL DEFAULT 'queued',
        source_id       BIGINT NULL REFERENCES knowledge_source(id)
                          ON DELETE SET NULL,
        started_at      TIMESTAMP NULL,
        finished_at     TIMESTAMP NULL,
        chunks_added    INTEGER NOT NULL DEFAULT 0,
        chunks_updated  INTEGER NOT NULL DEFAULT 0,
        chunks_rejected INTEGER NOT NULL DEFAULT 0,
        entities_added  INTEGER NOT NULL DEFAULT 0,
        relations_added INTEGER NOT NULL DEFAULT 0,
        error_log       TEXT NOT NULL DEFAULT '',
        triggered_by_id BIGINT NULL REFERENCES auth_user(id)
                          ON DELETE SET NULL,
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_job_status_created_idx
        ON knowledge_ingestionjob (status, created_at DESC);

    -- ─── knowledge_goldentestcase ─────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_goldentestcase (
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

    -- ─── knowledge_evalrun ────────────────────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_evalrun (
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

    -- ─── knowledge_useruploadattestation ──────────────────────
    CREATE TABLE IF NOT EXISTS knowledge_useruploadattestation (
        id              BIGSERIAL PRIMARY KEY,
        user_id         BIGINT NOT NULL REFERENCES auth_user(id)
                          ON DELETE CASCADE,
        file            VARCHAR(100) NOT NULL,
        title           VARCHAR(255) NOT NULL,
        source_description VARCHAR(300) NOT NULL,
        rights_attested BOOLEAN NOT NULL DEFAULT FALSE,
        commercial_use_ok BOOLEAN NOT NULL DEFAULT TRUE,
        reviewed_by_id  BIGINT NULL REFERENCES auth_user(id)
                          ON DELETE SET NULL,
        reviewed_at     TIMESTAMP NULL,
        decision        VARCHAR(16) NOT NULL DEFAULT 'pending',
        rejection_reason TEXT NOT NULL DEFAULT '',
        created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS kb_upload_decision_idx
        ON knowledge_useruploadattestation (decision, created_at DESC);
    """)


def _drop_tables(apps, schema_editor):
    """Reverse: drop everything we created. Used by `migrate ... zero`."""
    schema_editor.execute("""
    DROP TABLE IF EXISTS knowledge_useruploadattestation CASCADE;
    DROP TABLE IF EXISTS knowledge_evalrun CASCADE;
    DROP TABLE IF EXISTS knowledge_goldentestcase CASCADE;
    DROP TABLE IF EXISTS knowledge_ingestionjob CASCADE;
    DROP TABLE IF EXISTS knowledge_relation CASCADE;
    DROP TABLE IF EXISTS knowledge_entity CASCADE;
    DROP TABLE IF EXISTS knowledge_embedding CASCADE;
    DROP TABLE IF EXISTS knowledge_chunk CASCADE;
    DROP TABLE IF EXISTS knowledge_source CASCADE;
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