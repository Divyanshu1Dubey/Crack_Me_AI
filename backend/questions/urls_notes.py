"""Topic-notes builder and answer-insight routes under /api/questions/ (owned by the notes group, 2026-11)."""
from django.urls import path

from questions import views_notes

urlpatterns = [
    path('topic-notes/build/', views_notes.TopicNoteBuildView.as_view(), name='topic-note-build'),
    path('topic-notes/library/<int:pk>/sources/', views_notes.TopicNoteSourcesView.as_view(), name='topic-note-sources'),
    path('topic-notes/published/<int:pk>/', views_notes.PublishedTopicNoteDetailView.as_view(), name='topic-note-published-detail'),
]
