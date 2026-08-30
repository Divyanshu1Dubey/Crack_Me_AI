from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import BlogPost
from .serializers import BlogPostSerializer, BlogPostListSerializer


class BlogPostViewSet(viewsets.ModelViewSet):
    """Blog post CRUD for admins (front-end control tower).

    The blog management backend replaces the previous frontend-only
    static content with a proper DB-backed model. The frontend's
    `frontend/src/lib/blog.ts` continues to render the existing
    built-in posts (SSG) while the admin can add/edit/delete new
    posts through this API.
    """

    queryset = BlogPost.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "difficulty", "is_published", "pinned", "author_id"]
    search_fields = ["title", "body", "excerpt", "tags", "author"]
    ordering_fields = ["date_published", "created_at", "word_count"]
    permission_classes = [permissions.IsAdminUser]

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
        post = BlogPost.objects.filter(slug=slug).first()
        if not post:
            return Response({"detail": "Not found"}, status=404)
        ser = BlogPostSerializer(post)
        return Response(ser.data)
