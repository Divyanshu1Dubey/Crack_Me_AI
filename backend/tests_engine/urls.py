from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'attempts', views.TestAttemptViewSet, basename='attempt')
router.register(r'', views.TestViewSet, basename='test')

urlpatterns = [
    path('', include(router.urls)),
]
