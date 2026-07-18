from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import JobViewSet, JobCategoryViewSet

router = DefaultRouter()
router.register(r'categories', JobCategoryViewSet, basename='jobcategory')
router.register(r'', JobViewSet, basename='job')

urlpatterns = [
    path('', include(router.urls)),
]
