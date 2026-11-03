"""Routes under /api/key-audit/ (admin review queue)."""
from django.urls import path

from key_audit.views import (
    ReviewClaimView,
    ReviewQueueDetailView,
    ReviewQueueListView,
    ReviewResolveView,
)

app_name = "key_audit"

urlpatterns = [
    path("queue/", ReviewQueueListView.as_view(), name="queue-list"),
    path("queue/<int:question_id>/", ReviewQueueDetailView.as_view(), name="queue-detail"),
    path("queue/<int:question_id>/claim/", ReviewClaimView.as_view(), name="queue-claim"),
    path("queue/<int:question_id>/resolve/", ReviewResolveView.as_view(), name="queue-resolve"),
]
