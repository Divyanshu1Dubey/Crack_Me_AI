"""BlogPost.body_word_count: the words of the body, set on every save.

The site used to show the static seed's ``word_count`` / ``reading_time``
(most seeded posts claimed ~2,000 words and 7-10 minutes for a ~100-word
body). The API now reports ``body_word_count`` and a reading time derived
from it (blog_engine.text_stats). This migration counts the existing rows.
The old columns stay (seed_blogs hashes them) and are no longer shown.
"""
import re

from django.db import migrations, models

# A frozen copy of blog_engine.text_stats.count_words as of this migration.
_STEPS = (
    (re.compile(r"\r\n?"), "\n"),
    (re.compile(r"<!--[\s\S]*?-->"), " "),
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), " "),
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"<[^>\n]*>"), " "),
    (re.compile(r"https?://\S+", re.IGNORECASE), " "),
    (re.compile(r"\[!(?:note|tip|important|warning|caution)\]", re.IGNORECASE), " "),
    (re.compile(r"^[ \t]*\d{1,9}[.)](?=[ \t])", re.MULTILINE), " "),
    (re.compile(r"[#>*_`~|\[\]\\]"), " "),
)


def _count_words(markdown):
    text = markdown or ""
    for pattern, replacement in _STEPS:
        text = pattern.sub(replacement, text)
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def count_existing_posts(apps, schema_editor):
    BlogPost = apps.get_model("blog_engine", "BlogPost")
    posts = list(BlogPost.objects.only("id", "body"))
    for post in posts:
        post.body_word_count = _count_words(post.body)
    BlogPost.objects.bulk_update(posts, ["body_word_count"], batch_size=200)


class Migration(migrations.Migration):

    dependencies = [
        ("blog_engine", "0003_blogseedimport_post_ordering"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="body_word_count",
            field=models.PositiveIntegerField(
                default=0, editable=False,
                help_text="Words in the body (blog_engine.text_stats.count_words), set on every save. "
                          "The API reports it as word_count, with reading_time derived from it."),
        ),
        migrations.AlterField(
            model_name="blogpost",
            name="reading_time",
            field=models.CharField(
                default="10 min", max_length=20,
                help_text="Seed metadata only; the site shows the reading time computed from the body."),
        ),
        migrations.AlterField(
            model_name="blogpost",
            name="word_count",
            field=models.IntegerField(
                blank=True, default=None, null=True,
                help_text="Seed metadata only; the site shows body_word_count."),
        ),
        migrations.RunPython(count_existing_posts, migrations.RunPython.noop),
    ]
