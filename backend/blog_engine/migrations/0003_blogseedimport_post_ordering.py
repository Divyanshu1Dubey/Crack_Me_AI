"""The database becomes the source of truth of the public blog.

* BlogSeedImport: which static posts ``seed_blogs`` has imported, and the hash
  of the content it last wrote for each, so a post deleted, renamed or edited
  in the admin is never re-created or overwritten by a deploy.
* BlogPost ordering gets an ``-id`` tiebreak: many posts share a publish date,
  and the public hub features the first one.

Schema only; seed_blogs fills the import table on its next run (release.sh).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog_engine", "0002_credit_editorial_team"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogSeedImport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Blog seed import",
                "verbose_name_plural": "Blog seed imports",
                "ordering": ["slug"],
            },
        ),
        migrations.AlterModelOptions(
            name="blogpost",
            options={
                "ordering": ["-date_published", "-created_at", "-id"],
                "verbose_name": "Blog Post",
                "verbose_name_plural": "Blog Posts",
            },
        ),
    ]
