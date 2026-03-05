from django.urls import path
from . import views

urlpatterns = [
    path('catalog/', views.ResourceCatalogView.as_view(), name='resource-catalog'),
    path('download/<str:resource_id>/', views.ResourceDownloadView.as_view(), name='resource-download'),
    path('exam-guide/', views.ExamGuideView.as_view(), name='exam-guide'),
]
