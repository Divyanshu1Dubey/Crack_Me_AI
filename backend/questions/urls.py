from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'topics', views.TopicViewSet)
router.register(r'feedback', views.QuestionFeedbackViewSet)
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'exam-tracks', views.ExamTrackViewSet, basename='examtrack')
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
    # Chat AI Assistant
    path('chat/', views.ChatAssistantView.as_view(), name='chat-assistant'),
    # Bug #P0-2 (2026-07-25): prod /media/recall_images/ 404s because
    # static(MEDIA_URL, ...) is DEBUG-only in crack_cms/urls.py AND the
    # render container doesn't ship the local PNGs in git. This view
    # streams the QuestionImage.file binary through Django instead.
    path('images/<int:image_id>/serve/', views.QuestionImageServeView.as_view(), name='question-image-serve'),
    # Router URLs (QuestionViewSet, SubjectViewSet, etc.) - must be last
    path('', include(router.urls)),
]
