# Hand-authored migration — adds two fields on QuestionImage for the
# admin manual-fix editor (Task 1 of the admin-image-fix plan).
#
# - uploaded_by_admin: distinguishes admin uploads from recall imports.
# - url: Supabase public URL for admin-uploaded images (empty for recall).
#
# Kept separate from any unrelated drift (e.g. Subject.exam_type) so the
# migration is minimal, atomic, and easy to revert.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0024_rename_ix_dupcluster_method_questions_d_detecti_00b46e_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="questionimage",
            name="uploaded_by_admin",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="True if uploaded via the admin manual-fix editor (vs recall importer)",
            ),
        ),
        migrations.AddField(
            model_name="questionimage",
            name="url",
            field=models.URLField(
                blank=True,
                default="",
                help_text="Supabase public URL for admin-uploaded images (empty for recall imports)",
                max_length=500,
            ),
        ),
    ]
