import os

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsControlTowerAdmin
from crack_cms.filters import BoundedSearchFilter
from crack_cms.throttling import AnonRateThrottle, UserRateThrottle

from .models import BlogPost
from .seeding import is_placeholder_body
from .serializers import PUBLISH_NEEDS_BODY, BlogPostListSerializer, BlogPostSerializer

# Read-only actions anyone may call. Everyone but a blog admin sees published
# posts with a real body only; ``catalog`` (the public site's post list) is
# limited to those for everyone.
_PUBLIC_ACTIONS = {"list", "retrieve", "by_slug", "catalog"}

# Who may see drafts and write: the control-tower admins the /admin pages
# gate on (role 'admin' or superuser) and staff accounts (the rule this API
# used before; QuestionImageViewSet combines the two the same way).
BlogAdminPermission = IsControlTowerAdmin | permissions.IsAdminUser


def is_blog_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "is_admin", False) or user.is_superuser or user.is_staff)
    )


def public_posts(queryset):
    """Published posts with a real body: what the public blog may show."""
    return (
        queryset.filter(is_published=True)
        .exclude(body__iexact="full article content here.")
        .exclude(body__regex=r"^\s*$")
    )


class BlogReadThrottle(AnonRateThrottle):
    """Anonymous reads of the public blog API.

    The Next.js build and its ISR revalidation read the catalog and every
    post from one address; the project-wide anonymous rate (120/min) would
    answer part of a build with 429 (those pages would fall back to static
    copies). Override with DRF_THROTTLE_BLOG_READ or a 'blog_read' entry in
    DEFAULT_THROTTLE_RATES.
    """

    scope = "blog_read"

    def get_rate(self):
        return self.THROTTLE_RATES.get(self.scope) or os.getenv("DRF_THROTTLE_BLOG_READ", "1200/min")


class BlogPostViewSet(viewsets.ModelViewSet):
    """Blog posts: the source of truth of the public /blog pages.

    The Next.js site renders the published posts server-side with ISR
    (frontend/src/lib/blog.ts: ``catalog`` for lists, ``by-slug`` for a post);
    /admin/blog lists, creates, edits, (un)publishes and deletes them.

    * ``list`` / ``retrieve`` / ``by-slug``: public, published posts with a
      real body only; blog admins also see drafts.
    * ``catalog``: every published post (summary fields), unpaginated.
    * ``facets``: admin totals and categories for the filters.
    * writes and ``toggle-publish``: blog admins only.
    """

    queryset = BlogPost.objects.all()
    # BoundedSearchFilter: ?search= (open to anonymous callers) keeps at most
    # 10 distinct terms of up to 100 characters; each term is an ILIKE per
    # search field.
    filter_backends = [DjangoFilterBackend, BoundedSearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "difficulty", "is_published", "pinned", "trending", "author_id"]
    search_fields = ["title", "slug", "body", "excerpt", "tags", "author", "category"]
    ordering_fields = ["date_published", "created_at", "updated", "title", "word_count"]

    def get_permissions(self):
        if self.action in _PUBLIC_ACTIONS:
            return [permissions.AllowAny()]
        return [BlogAdminPermission()]

    def get_throttles(self):
        if self.action in _PUBLIC_ACTIONS:
            return [BlogReadThrottle(), UserRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "catalog" or (
            self.action in _PUBLIC_ACTIONS and not is_blog_admin(self.request.user)
        ):
            qs = public_posts(qs)
        return qs

    def get_serializer_class(self):
        if self.action in ("list", "catalog"):
            return BlogPostListSerializer
        return BlogPostSerializer

    @action(detail=False, methods=["get"], url_path="catalog")
    def catalog(self, request):
        """Every published post, newest first, without bodies (the public site's post list)."""
        rows = BlogPostListSerializer(self.get_queryset(), many=True).data
        return Response({"count": len(rows), "results": rows})

    @action(detail=False, methods=["get"], url_path="facets")
    def facets(self, request):
        """Totals and categories over every post, drafts included (the admin filters)."""
        posts = BlogPost.objects.all()
        total = posts.count()
        published = posts.filter(is_published=True).count()
        categories = (
            posts.values("category").annotate(count=Count("id")).order_by("-count", "category")
        )
        return Response({
            "total": total,
            "published": published,
            "drafts": total - published,
            "categories": [{"name": row["category"], "count": row["count"]} for row in categories],
        })

    @action(detail=True, methods=["post"], url_path="toggle-publish")
    def toggle_publish(self, request, pk=None):
        post = self.get_object()
        if not post.is_published and is_placeholder_body(post.body):
            return Response({"detail": PUBLISH_NEEDS_BODY}, status=status.HTTP_400_BAD_REQUEST)
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
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(BlogPostSerializer(post).data)
