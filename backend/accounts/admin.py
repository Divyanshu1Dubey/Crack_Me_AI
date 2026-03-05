from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'target_exam', 'is_active']
    list_filter = ['role', 'target_exam', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('CMS Profile', {'fields': ('role', 'phone', 'target_exam', 'target_year', 'avatar_url')}),
    )
