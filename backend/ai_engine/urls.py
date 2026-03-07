from django.urls import path
from . import views

urlpatterns = [
    # Core AI endpoints
    path('tutor/', views.AskTutorView.as_view(), name='ai-tutor'),
    path('mnemonic/', views.GenerateMnemonicView.as_view(), name='ai-mnemonic'),
    path('explain/', views.ExplainConceptView.as_view(), name='ai-explain'),
    path('analyze/', views.AnalyzeQuestionView.as_view(), name='ai-analyze'),
    path('explain-answer/', views.ExplainAfterAnswerView.as_view(), name='ai-explain-answer'),

    # RAG-powered endpoints
    path('rag-search/', views.RAGSearchView.as_view(), name='ai-rag-search'),
    path('rag-answer/', views.RAGAnswerView.as_view(), name='ai-rag-answer'),
    path('textbook-reference/', views.TextbookReferenceView.as_view(), name='ai-textbook-ref'),
    path('screenshot/<int:question_id>/', views.PageScreenshotView.as_view(), name='ai-screenshot'),

    # Study planning
    path('study-plan/', views.StudyPlanView.as_view(), name='ai-study-plan'),
    path('high-yield/', views.HighYieldTopicsView.as_view(), name='ai-high-yield'),
    path('generate-questions/', views.GenerateQuestionsView.as_view(), name='ai-generate-questions'),

    # Knowledge base management (auto-ingest)
    path('knowledge/upload/', views.KnowledgeUploadView.as_view(), name='ai-knowledge-upload'),
    path('knowledge/scan/', views.KnowledgeScanView.as_view(), name='ai-knowledge-scan'),
    path('knowledge/stats/', views.KnowledgeStatsView.as_view(), name='ai-knowledge-stats'),

    # Debug / status
    path('status/', views.AIStatusView.as_view(), name='ai-status'),
]
