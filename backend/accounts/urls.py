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
]
