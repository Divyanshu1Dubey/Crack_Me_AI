from django.contrib import admin
from .models import BlogPost


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
    list_display = [
        "title",
        "category",
        "author",
        "date_published",
        "is_published",
        "pinned",
        "difficulty",
        "reading_time",
    ]
    list_filter = ["category", "difficulty", "is_published", "pinned", "date_published"]
    search_fields = ["title", "body", "excerpt", "tags", "author"]
    readonly_fields = ["created_at", "updated"]
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
            "fields": ("author_id", "reviewed_by", "author", "author_role", "date_published", "date_modified", "updated_at", "reading_time")
        }),
        ("Visibility", {
            "fields": ("is_published", "pinned", "trending", "word_count")
        }),
        ("Extended Content", {
            "fields": ("primary_cta", "related_exam_paths", "faqs", "toc", "references", "revision_log", "prelude", "outro"),
            "classes": ("collapse",),
        }),
    )
