from django.urls import path
from . import views
from . import dashboard_v3 as views_v3

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('weak-topics/', views.WeakTopicsView.as_view(), name='weak-topics'),
    path('topic-performance/', views.TopicPerformanceView.as_view(), name='topic-performance'),
    path('heatmap/', views.DailyActivityView.as_view(), name='heatmap'),
    path('recent-attempts/', views.RecentAttemptsView.as_view(), name='recent-attempts'),
    path('score-prediction/', views.ScorePredictionView.as_view(), name='score-prediction'),
    path('performance-trend/', views.PerformanceTrendView.as_view(), name='performance-trend'),
    # Feedback & Contact Us
    path('feedback/', views.FeedbackListCreateView.as_view(), name='feedback-list'),
    path('feedback/<int:pk>/', views.FeedbackDetailView.as_view(), name='feedback-detail'),
    path('contact/', views.ContactUsView.as_view(), name='contact-us'),
    # Data export for Google Sheets
    path('export/', views.DataExportView.as_view(), name='data-export'),
    path('export/csv/', views.DataExportCSVView.as_view(), name='data-export-csv'),
    # Announcements
    path('announcements/', views.AnnouncementListView.as_view(), name='announcements'),
    path('announcements/<int:pk>/', views.AnnouncementDetailView.as_view(), name='announcement-detail'),
    # Gamification
    path('streak/', views.StudyStreakView.as_view(), name='study-streak'),
    path('badges/', views.BadgeListView.as_view(), name='badges'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    # Admin
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/weak-area-control/', views.AdminWeakAreaControlView.as_view(), name='admin-weak-area-control'),
    path('admin/campaigns/', views.AdminCampaignListCreateView.as_view(), name='admin-campaigns'),
    path('admin/campaigns/<int:pk>/send-now/', views.AdminCampaignSendNowView.as_view(), name='admin-campaign-send-now'),
    # Phase 3 — combined dashboard + new analytics endpoints (additive).
    path('dashboard_v3/', views_v3.DashboardV3View.as_view(), name='dashboard-v3'),
    path('heatmap/subject/', views_v3.HeatmapSubjectView.as_view(), name='heatmap-subject'),
    path('revision_progress/', views_v3.RevisionProgressView.as_view(), name='revision-progress'),
    path('pyq_coverage/', views_v3.PYQCoverageView.as_view(), name='pyq-coverage'),
    path('average_time/', views_v3.AverageTimeView.as_view(), name='average-time'),
    path('search_analytics/', views_v3.SearchAnalyticsView.as_view(), name='search-analytics'),
]
