from django.db import models

from .text_stats import count_words, is_thin, reading_time_label


class BlogPost(models.Model):
    """A blog post: the source of truth of the public /blog pages.

    The Next.js site renders the published rows (``is_published`` and a real
    body) server-side with ISR, through ``GET /api/blog/posts/catalog/`` and
    ``/by-slug/<slug>/``; admins edit them at /admin/blog. Every field the
    static post type of frontend/src/lib/blog.ts has is stored here
    (structured parts as JSON); ``manage.py seed_blogs`` imports the static
    posts (frontend/src/content/blog).
    """

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    title = models.CharField(max_length=300)
    description = models.TextField()
    excerpt = models.TextField()
    cover_image = models.CharField(max_length=500, blank=True, default="")
    category = models.CharField(max_length=100, db_index=True)
    subcategory = models.CharField(max_length=100, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    difficulty = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default="intermediate"
    )
    author_id = models.CharField(max_length=200, default="crackcms-editorial")
    reviewed_by = models.CharField(max_length=200, blank=True, default="")
    author = models.CharField(max_length=200)
    author_role = models.CharField(max_length=200)
    date_published = models.CharField(max_length=50)
    date_modified = models.CharField(max_length=50, blank=True, default="")
    updated_at = models.CharField(max_length=50, blank=True, default="")
    # The static seed's metadata, kept so seed_blogs' content hashes stay
    # stable; never shown (most seeded posts claimed ~2,000 words for a
    # ~100-word body). The site shows body_word_count and the reading time
    # derived from it (blog_engine.text_stats).
    reading_time = models.CharField(
        max_length=20, default="10 min",
        help_text="Seed metadata only; the site shows the reading time computed from the body.")
    word_count = models.IntegerField(
        null=True, blank=True, default=None,
        help_text="Seed metadata only; the site shows body_word_count.")
    body_word_count = models.PositiveIntegerField(
        default=0, editable=False,
        help_text="Words in the body (blog_engine.text_stats.count_words), set on every save. "
                  "The API reports it as word_count, with reading_time derived from it.")
    primary_cta = models.JSONField(default=dict, blank=True)
    related_exam_paths = models.JSONField(default=list, blank=True)
    faqs = models.JSONField(default=list, blank=True)
    toc = models.JSONField(default=list, blank=True)
    references = models.JSONField(default=list, blank=True)
    revision_log = models.JSONField(default=list, blank=True)
    body = models.TextField()
    prelude = models.TextField(blank=True, default="")
    outro = models.TextField(blank=True, default="")
    pinned = models.BooleanField(default=False)
    trending = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest first; posts of the same day: the most recently created first
        # (``-id`` settles rows created in the same instant).
        ordering = ["-date_published", "-created_at", "-id"]
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Every save path that writes the body (the API, Django admin, seed_blogs'
        # creates) recounts it; a save of other fields only leaves it alone.
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "body" in update_fields:
            self.body_word_count = count_words(self.body)
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "body_word_count"}
        super().save(*args, **kwargs)

    @property
    def reading_time_label(self) -> str:
        return reading_time_label(self.body_word_count)

    @property
    def is_thin(self) -> bool:
        return is_thin(self.body_word_count)


class BlogSeedImport(models.Model):
    """One row per slug ``seed_blogs`` has handled: a static post it imported,
    or a row of the previous seed it unpublished.

    A static post is imported once: a post deleted or renamed in the admin
    is not re-created on the next deploy (``seed_blogs --restore`` does that
    on purpose), and an unpublished old-seed row is left to the admin.
    ``content_hash`` is the hash of the content seed_blogs last wrote for the
    slug (blog_engine.seeding.content_hash); while the row still hashes to it
    nobody has edited the post, so a changed static file may update it. Empty
    when the content was not written by seed_blogs (an admin's edit, a row an
    older seed wrote and an admin changed, an unpublished old-seed row).
    """

    slug = models.SlugField(max_length=200, unique=True)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Blog seed import"
        verbose_name_plural = "Blog seed imports"

    def __str__(self):
        return self.slug
