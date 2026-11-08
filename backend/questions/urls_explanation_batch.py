"""Routes of the AI explanation batch and its review queue (questions/views_explanation_batch.py), admin only.
Included before the router, whose empty-prefix detail routes would otherwise shadow them."""
from django.urls import path

from questions import views_explanation_batch as views

urlpatterns = [
    path('explanation-batches/', views.ExplanationBatchListView.as_view(), name='explanation-batches'),
    path('explanation-batches/<int:pk>/process/', views.ExplanationBatchProcessView.as_view(),
         name='explanation-batch-process'),
    path('explanation-batches/<int:pk>/items/', views.ExplanationBatchItemsView.as_view(),
         name='explanation-batch-items'),
    path('explanation-review/', views.ExplanationReviewQueueView.as_view(), name='explanation-review'),
]
