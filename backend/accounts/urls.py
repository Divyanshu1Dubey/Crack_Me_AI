from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    # Password reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # Token system
    path('tokens/', views.TokenBalanceView.as_view(), name='token_balance'),
    path('tokens/purchase/', views.TokenPurchaseView.as_view(), name='token_purchase'),
    path('tokens/history/', views.TokenTransactionHistoryView.as_view(), name='token_history'),
    # Super admin token management
    path('tokens/admin/users/', views.AdminTokenOverviewView.as_view(), name='admin_token_users'),
    path('tokens/admin/grant/', views.AdminTokenGrantView.as_view(), name='admin_token_grant'),
    path('tokens/admin/transfer/', views.AdminTokenTransferView.as_view(), name='admin_token_transfer'),
    path('tokens/admin/audit-logs/', views.AdminAuditLogListView.as_view(), name='admin_audit_logs'),
    # Admin lifecycle controls (Phase 6)
    path('admin/users/', views.AdminUserLifecycleListView.as_view(), name='admin_users_lifecycle_list'),
    path('admin/users/<int:user_id>/block/', views.AdminUserBlockToggleView.as_view(), name='admin_user_block_toggle'),
    path('admin/users/<int:user_id>/role/', views.AdminUserRoleUpdateView.as_view(), name='admin_user_role_update'),
    path('admin/users/<int:user_id>/reset-progress/', views.AdminUserResetProgressView.as_view(), name='admin_user_reset_progress'),
    path('admin/system/reset-attempts/', views.AdminSystemResetAttemptsView.as_view(), name='admin_system_reset_attempts'),
    path('admin/system/clear-analytics/', views.AdminSystemClearAnalyticsView.as_view(), name='admin_system_clear_analytics'),
    path('admin/system/rerun-evaluation/', views.AdminSystemRerunEvaluationView.as_view(), name='admin_system_rerun_evaluation'),
]
