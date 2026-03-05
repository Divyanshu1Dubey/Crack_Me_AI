from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('weak-topics/', views.WeakTopicsView.as_view(), name='weak-topics'),
    path('topic-performance/', views.TopicPerformanceView.as_view(), name='topic-performance'),
    path('heatmap/', views.ActivityHeatmapView.as_view(), name='heatmap'),
    path('recent-attempts/', views.RecentAttemptsView.as_view(), name='recent-attempts'),
    path('score-prediction/', views.ScorePredictionView.as_view(), name='score-prediction'),
    path('performance-trend/', views.PerformanceTrendView.as_view(), name='performance-trend'),
]

