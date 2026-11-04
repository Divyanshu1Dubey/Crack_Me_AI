from django.contrib import admin
from .models import BlogPost, BlogSeedImport


@admin.action(description="Publish selected posts")
def publish_posts(modeladmin, request, queryset):
    queryset.update(is_published=True)
    modeladmin.message_user(request, f"{queryset.count()} post(s) published.")


@admin.action(description="Unpublish selected posts")
def unpublish_posts(modeladmin, request, queryset):
    queryset.update(is_published=False)
    modeladmin.message_user(request, f"{queryset.count()} post(s) unpublished.")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """The posts are edited at /admin/blog (the site's editor); this is the raw view."""

    list_display = [
        "title",
        "category",
        "author",
        "date_published",
        "is_published",
        "pinned",
        "difficulty",
        "words",
    ]
    list_filter = ["category", "difficulty", "is_published", "pinned", "date_published"]
    search_fields = ["title", "slug", "body", "excerpt", "tags", "author"]
    # word_count / reading_time: the seed's metadata, not shown on the site.
    readonly_fields = ["created_at", "updated", "words", "reading_time", "word_count"]
    actions = [publish_posts, unpublish_posts]
    list_editable = ["is_published", "pinned"]
    fieldsets = (
        ("Content", {
            "fields": ("title", "slug", "description", "excerpt", "body", "cover_image")
        }),
        ("Classification", {
            "fields": ("category", "subcategory", "tags", "difficulty")
        }),
        ("Author", {
            "fields": ("author_id", "reviewed_by", "author", "author_role", "date_published", "date_modified", "updated_at")
        }),
        ("Visibility", {
            "fields": ("is_published", "pinned", "trending", "words")
        }),
        ("Extended Content", {
            "fields": ("primary_cta", "related_exam_paths", "faqs", "toc", "references", "revision_log", "prelude", "outro"),
            "classes": ("collapse",),
        }),
        ("Seed metadata (not shown on the site)", {
            "fields": ("reading_time", "word_count"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Words", ordering="body_word_count")
    def words(self, obj):
        thin = " (thin)" if obj.is_thin else ""
        return f"{obj.body_word_count} · {obj.reading_time_label}{thin}"


@admin.register(BlogSeedImport)
class BlogSeedImportAdmin(admin.ModelAdmin):
    """Which static posts seed_blogs imported. Deleting a row lets the next
    deploy re-create that static post if it no longer exists."""

    list_display = ["slug", "content_hash", "imported_at", "updated_at"]
    search_fields = ["slug"]
    readonly_fields = ["slug", "content_hash", "imported_at", "updated_at"]

    def has_add_permission(self, request):
        return False
