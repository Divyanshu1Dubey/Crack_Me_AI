from django.urls import path, re_path
from rest_framework.routers import DefaultRouter

from .images import BlogImageServeView, BlogImageUploadView
from .views import BlogPostViewSet

router = DefaultRouter()
router.register(r"posts", BlogPostViewSet)

urlpatterns = [
    # Admin upload; the stored file is served publicly below (see blog_engine.images).
    path("images/", BlogImageUploadView.as_view(), name="blog-image-upload"),
    re_path(r"^images/(?P<name>\d{4}/\d{2}/[0-9a-f]{32}\.(?:png|jpg|gif|webp))$",
            BlogImageServeView.as_view(), name="blog-image"),
] + router.urls
