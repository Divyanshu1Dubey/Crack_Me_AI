"""Routes under /api/evidence/ (see evidence/views.py for the contract)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.EvidenceListView.as_view(), name='evidence-list'),
    path('sources/', views.EvidenceSourceListView.as_view(), name='evidence-sources'),
    path('search/', views.EvidenceSearchView.as_view(), name='evidence-search'),
    path('questions/<int:qid>/citations/', views.StudentCitationsView.as_view(), name='evidence-student-citations'),
    path('questions/<int:qid>/', views.QuestionEvidenceView.as_view(), name='evidence-question'),
    path('pages/<str:sha>/<int:page_no>/image.png', views.EvidencePageImageView.as_view(), name='evidence-page-image'),
    path('pages/<str:sha>/<int:page_no>/', views.EvidencePageView.as_view(), name='evidence-page'),
    path('recall-pages/<int:qs_id>/image.png', views.RecallPageImageView.as_view(), name='evidence-recall-page-image'),
    path('figures/<int:pk>/', views.EvidenceFigureServeView.as_view(), name='evidence-figure'),
    path('<int:pk>/figure/', views.EvidenceFigureCreateView.as_view(), name='evidence-figure-create'),
    path('<int:pk>/', views.EvidenceDetailView.as_view(), name='evidence-detail'),
]
