from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import BlogPost
from .serializers import BlogPostSerializer, BlogPostListSerializer

# Seed rows whose body is only a placeholder are never served publicly.
_PLACEHOLDER_BODIES = ["", "Full article content here."]

# Read-only actions anyone may call (published posts only).
_PUBLIC_ACTIONS = {"list", "retrieve", "by_slug"}


def _is_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class BlogPostViewSet(viewsets.ModelViewSet):
    """Blog post CRUD for admins (front-end control tower).

    The blog management backend replaces the previous frontend-only
    static content with a proper DB-backed model. The frontend's
    `frontend/src/lib/blog.ts` continues to render the existing
    built-in posts (SSG) while the admin can add/edit/delete new
    posts through this API.

    ``list`` / ``retrieve`` / ``by-slug`` are also open read-only to
    everyone, limited to published posts with a real body, so the public
    /blog pages can render posts created or edited in Blog Management.
    Every write stays admin-only.
    """

    queryset = BlogPost.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "difficulty", "is_published", "pinned", "author_id"]
    search_fields = ["title", "body", "excerpt", "tags", "author"]
    ordering_fields = ["date_published", "created_at", "word_count"]

    def get_permissions(self):
        if self.action in _PUBLIC_ACTIONS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action in _PUBLIC_ACTIONS and not _is_staff(self.request.user):
            qs = qs.filter(is_published=True).exclude(body__in=_PLACEHOLDER_BODIES)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return BlogPostListSerializer
        return BlogPostSerializer

    @action(detail=True, methods=["post"], url_path="toggle-publish")
    def toggle_publish(self, request, pk=None):
        post = self.get_object()
        post.is_published = not post.is_published
        post.save(update_fields=["is_published", "updated"])
        return Response({
            "id": post.id,
            "is_published": post.is_published,
            "message": "Published" if post.is_published else "Unpublished",
        })

    @action(detail=False, methods=["get"], url_path="by-slug/(?P<slug>[^/.]+)")
    def by_slug(self, request, slug=None):
        post = self.get_queryset().filter(slug=slug).first()
        if not post:
            return Response({"detail": "Not found"}, status=404)
        ser = BlogPostSerializer(post)
        return Response(ser.data)
