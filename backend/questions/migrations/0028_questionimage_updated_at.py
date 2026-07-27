# Hand-authored migration — adds `updated_at` to `QuestionImage` so the
# admin upload dedup path (`upload_image_to_supabase`) can bump a real
# column instead of crashing with
# "fields do not exist in this model: updated_at".
#
# Idempotent for environments where the column was added ad-hoc: the
# column-existence check makes AddField a no-op when the schema is
# already current, so re-running `migrate` after a manual fix is safe.
from django.db import migrations, models


TABLE = "questions_questionimage"
COLUMN = "updated_at"


def _has_column(schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                [TABLE, COLUMN],
            )
        else:
            cursor.execute(
                "SELECT 1 FROM pragma_table_info(%s) WHERE name = %s",
                [TABLE, COLUMN],
            )
        return cursor.fetchone() is not None


def _add_field_if_missing(apps, schema_editor):
    if _has_column(schema_editor):
        return
    field = models.DateTimeField(auto_now=True)
    field.set_attributes_from_name(COLUMN)
    schema_editor.add_field(apps.get_model("questions", "QuestionImage"), field)


def _drop_field_if_present(apps, schema_editor):
    if not _has_column(schema_editor):
        return
    model = apps.get_model("questions", "QuestionImage")
    schema_editor.remove_field(model, model._meta.get_field(COLUMN))


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0027_strip_html_and_leaks"),
    ]

    operations = [
        migrations.RunPython(_add_field_if_missing, _drop_field_if_present),
    ]