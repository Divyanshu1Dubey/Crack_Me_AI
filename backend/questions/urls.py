from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'topics', views.TopicViewSet)
router.register(r'', views.QuestionViewSet, basename='question')

urlpatterns = [
    path('', include(router.urls)),
]
