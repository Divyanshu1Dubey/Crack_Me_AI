"""Routes under /api/key-audit/ (admin review queue)."""
from django.urls import path

from key_audit.views import (
    ReviewBatchSourceKeyView,
    ReviewClaimView,
    ReviewQueueDetailView,
    ReviewQueueListView,
    ReviewQueueSummaryView,
    ReviewResolveView,
)

app_name = "key_audit"

urlpatterns = [
    path("queue/", ReviewQueueListView.as_view(), name="queue-list"),
    path("queue/summary/", ReviewQueueSummaryView.as_view(), name="queue-summary"),
    path("queue/accept-source-keys/", ReviewBatchSourceKeyView.as_view(), name="queue-accept-source-keys"),
    path("queue/<int:question_id>/", ReviewQueueDetailView.as_view(), name="queue-detail"),
    path("queue/<int:question_id>/claim/", ReviewClaimView.as_view(), name="queue-claim"),
    path("queue/<int:question_id>/resolve/", ReviewResolveView.as_view(), name="queue-resolve"),
]
