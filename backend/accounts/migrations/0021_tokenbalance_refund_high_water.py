"""High-water marks for purchased / feedback token pools.

Fix #2 — refund_token was silently losing paid tokens. We now track the
highest purchased_tokens / feedback_credits the user has ever had, and
refund_token restores up to that high-water mark when an AI call fails
after consuming a token.

Defaults match the existing defaults on the primary columns so legacy
rows don't suddenly claim huge token grants.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0020_subscription_active_lookup_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="tokenbalance",
            name="purchased_tokens_max",
            field=models.IntegerField(
                default=50,
                help_text='High-water mark of purchased tokens — used by refund_token.',
            ),
        ),
        migrations.AddField(
            model_name="tokenbalance",
            name="feedback_credits_max",
            field=models.IntegerField(
                default=0,
                help_text='High-water mark of feedback credits — used by refund_token.',
            ),
        ),
    ]