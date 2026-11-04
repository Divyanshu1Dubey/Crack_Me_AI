from django.urls import path
from . import native_auth, preferences, views

urlpatterns = [
    # Which sign-in the backend runs (both modes) and the Django-native
    # sign-in (AUTH_PROVIDER=django; every view below answers 404 in
    # supabase mode). See accounts/native_auth.py.
    path('config/', native_auth.AuthConfigView.as_view(), name='auth_config'),
    path('native/login/', native_auth.NativeLoginView.as_view(), name='native_login'),
    path('native/refresh/', native_auth.NativeRefreshView.as_view(), name='native_refresh'),
    path('native/logout/', native_auth.NativeLogoutView.as_view(), name='native_logout'),
    path('native/register/', native_auth.NativeRegisterView.as_view(), name='native_register'),
    path('native/verify-email/', native_auth.NativeVerifyEmailView.as_view(), name='native_verify_email'),
    path(
        'native/resend-verification/', native_auth.NativeResendVerificationView.as_view(),
        name='native_resend_verification',
    ),
    path('native/password/', native_auth.NativePasswordChangeView.as_view(), name='native_password_change'),
    path('google/', native_auth.GoogleSignInView.as_view(), name='google_signin'),
    path('google/confirm-link/', native_auth.GoogleConfirmLinkView.as_view(), name='google_confirm_link'),
    path('google/link/', native_auth.GoogleLinkView.as_view(), name='google_link'),
    # Auth
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('preferences/', preferences.UIPreferencesView.as_view(), name='ui_preferences'),
    path('subscribe/', views.SubscribeView.as_view(), name='subscribe'),
    path('subscribe/order/', views.SubscribeOrderView.as_view(), name='subscribe_order'),
    path('subscribe/verify/', views.SubscribeVerifyView.as_view(), name='subscribe_verify'),
    path('subscribe/status/', views.SubscriptionStatusView.as_view(), name='subscribe_status'),
    path('subscribe/history/', views.SubscriptionHistoryView.as_view(), name='subscribe_history'),
    path('subscribe/invoice/<int:subscription_id>/', views.SubscriptionInvoiceView.as_view(), name='subscribe_invoice'),
    path('subscribe/webhook/', views.RazorpayWebhookView.as_view(), name='razorpay_webhook'),
    path('scholarship/start/', views.ScholarshipStartView.as_view(), name='scholarship_start'),
    path('verify-scholarship/', views.VerifyScholarshipView.as_view(), name='verify_scholarship'),
    # Password reset
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # Device Management
    path('devices/', views.UserDeviceListView.as_view(), name='device_list'),
    path('devices/logout/', views.UserDeviceLogoutView.as_view(), name='device_logout'),
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
    path('admin/system/backup-data/', views.AdminSystemBackupDataView.as_view(), name='admin_system_backup_data'),
    path('admin/system/restore-data/', views.AdminSystemRestoreDataView.as_view(), name='admin_system_restore_data'),
    # Admin Phase 3 Routes
    path('admin/users/<int:user_id>/subscription/', views.AdminSubscriptionManageView.as_view(), name='admin_subscription_manage'),
    path('admin/users/<int:user_id>/devices/', views.AdminDeviceManageView.as_view(), name='admin_device_manage'),
    path('admin/payments/', views.AdminPaymentHistoryView.as_view(), name='admin_payment_history'),
]

# Dev-only local auth (see accounts/local_auth.py). Only mounted when
# settings.LOCAL_DEV_AUTH is on, which requires DEBUG=True.
from django.conf import settings as _settings  # noqa: E402

if getattr(_settings, 'LOCAL_DEV_AUTH', False):
    from . import local_auth  # noqa: E402

    urlpatterns += [
        path('local/login/', local_auth.LocalLoginView.as_view(), name='local_login'),
        path('local/register/', local_auth.LocalRegisterView.as_view(), name='local_register'),
        path('local/refresh/', local_auth.LocalRefreshView.as_view(), name='local_refresh'),
    ]

if getattr(_settings, 'PAYMENTS_MOCK', False):
    from . import payments_mock  # noqa: E402

    urlpatterns += [
        path('subscribe/mock-checkout/', payments_mock.MockCheckoutView.as_view(), name='subscribe_mock_checkout'),
    ]
