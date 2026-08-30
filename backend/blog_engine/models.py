from django.db import models


class BlogPost(models.Model):
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
    reading_time = models.CharField(max_length=20, default="10 min")
    word_count = models.IntegerField(null=True, blank=True, default=None)
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
        ordering = ["-date_published", "-created_at"]
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self):
        return self.title
