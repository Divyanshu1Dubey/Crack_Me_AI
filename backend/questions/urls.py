from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'topics', views.TopicViewSet)
router.register(r'feedback', views.QuestionFeedbackViewSet)
router.register(r'', views.QuestionViewSet, basename='question')

# NOTE: Explicit paths must come BEFORE router.urls because the router's
# catch-all <pk>/ pattern would otherwise match paths like 'flashcards/'
urlpatterns = [
    # Flashcards (must be before router to avoid <pk> matching 'flashcards')
    path('flashcards/analytics/', views.FlashcardAnalyticsView.as_view(), name='flashcard-analytics'),
    path('flashcards/<int:pk>/review/', views.FlashcardReviewView.as_view(), name='flashcard-review'),
    path('flashcards/<int:pk>/', views.FlashcardDetailView.as_view(), name='flashcard-detail'),
    path('flashcards/', views.FlashcardListCreateView.as_view(), name='flashcard-list'),
    # Notes
    path('notes/<int:pk>/', views.NoteDetailView.as_view(), name='note-detail'),
    path('notes/', views.NoteListCreateView.as_view(), name='note-list'),
    # Discussions
    path('discussions/<int:pk>/vote/', views.DiscussionVoteView.as_view(), name='discussion-vote'),
    path('discussions/<int:pk>/replies/', views.DiscussionRepliesView.as_view(), name='discussion-replies'),
    path('discussions/', views.DiscussionListCreateView.as_view(), name='discussion-list'),
    # Router URLs (QuestionViewSet, SubjectViewSet, etc.) - must be last
    path('', include(router.urls)),
]
