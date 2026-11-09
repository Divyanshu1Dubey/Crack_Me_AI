from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("key_audit", "0002_source_keys_and_decision_context"),
    ]

    operations = [
        migrations.CreateModel(
            name="BundledSignalImport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("sha256", models.CharField(max_length=64)),
                ("kind", models.CharField(choices=[("source_keys", "Printed source keys"),
                                                   ("reviews", "Review signals")], max_length=20)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-imported_at"],
                "constraints": [models.UniqueConstraint(fields=("name", "sha256"), name="kaudit_bundle_once")],
            },
        ),
    ]
