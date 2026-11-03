"""Question-editor routes under /api/questions/ (explain-option, change-key, key-history, provenance ...).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (editor group).
Explicit paths here, because the router's empty-prefix detail routes would otherwise shadow nested actions.
"""
from django.urls import path

from questions import views_editorial

urlpatterns = [
    path('<int:pk>/change-key/', views_editorial.ChangeAnswerKeyView.as_view(), name='question-change-key'),
    path('<int:pk>/explain-option/', views_editorial.ExplainOptionView.as_view(), name='question-explain-option'),
    path('<int:pk>/key-history/', views_editorial.KeyHistoryListView.as_view(), name='question-key-history'),
    path('<int:pk>/save-explanation/', views_editorial.SaveExplanationView.as_view(), name='question-save-explanation'),
    path('<int:pk>/verify-key/', views_editorial.VerifyQuestionView.as_view(), name='question-verify-key'),
    path('<int:pk>/review-explanation/', views_editorial.ReviewExplanationView.as_view(), name='question-review-explanation'),
]
