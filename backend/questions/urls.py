from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'topics', views.TopicViewSet)
router.register(r'feedback', views.QuestionFeedbackViewSet)
router.register(r'', views.QuestionViewSet, basename='question')

urlpatterns = [
    path('', include(router.urls)),
    # Discussions
    path('discussions/', views.DiscussionListCreateView.as_view(), name='discussion-list'),
    path('discussions/<int:pk>/replies/', views.DiscussionRepliesView.as_view(), name='discussion-replies'),
    path('discussions/<int:pk>/vote/', views.DiscussionVoteView.as_view(), name='discussion-vote'),
    # Notes
    path('notes/', views.NoteListCreateView.as_view(), name='note-list'),
    path('notes/<int:pk>/', views.NoteDetailView.as_view(), name='note-detail'),
    # Flashcards
    path('flashcards/', views.FlashcardListCreateView.as_view(), name='flashcard-list'),
    path('flashcards/<int:pk>/', views.FlashcardDetailView.as_view(), name='flashcard-detail'),
    path('flashcards/<int:pk>/review/', views.FlashcardReviewView.as_view(), name='flashcard-review'),
    path('flashcards/analytics/', views.FlashcardAnalyticsView.as_view(), name='flashcard-analytics'),
]
