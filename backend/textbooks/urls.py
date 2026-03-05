from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'books', views.TextbookViewSet, basename='textbook')
router.register(r'uploads', views.PDFUploadViewSet, basename='pdf-upload')

urlpatterns = [
    path('', include(router.urls)),
]
