from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0005_discussion_flashcard_note_discussionvote"),
    ]

    operations = [
        migrations.AddField(
            model_name="flashcard",
            name="personal_note",
            field=models.TextField(blank=True, help_text="User's personal study notes for this card"),
        ),
    ]
