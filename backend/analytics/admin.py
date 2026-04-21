from django.contrib import admin
from .models import UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge

@admin.register(UserTopicPerformance)
class UserTopicPerformanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'topic', 'subject', 'total_attempts', 'correct_answers', 'accuracy']
    list_filter = ['subject']

@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'questions_attempted', 'correct_answers']
    list_filter = ['date']

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'category', 'rating', 'is_read', 'created_at']
    list_filter = ['category', 'is_read', 'rating']
    search_fields = ['title', 'message', 'user__username']
    readonly_fields = ['user', 'category', 'rating', 'title', 'message', 'created_at']

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'delivery_status', 'delivery_count', 'is_active', 'created_by', 'scheduled_for', 'sent_at', 'expires_at', 'created_at']
    list_filter = ['priority', 'is_active', 'delivery_status']
    search_fields = ['title', 'message']

@admin.register(StudyStreak)
class StudyStreakAdmin(admin.ModelAdmin):
    list_display = ['user', 'current_streak', 'longest_streak', 'total_study_days', 'xp_points']
    search_fields = ['user__username']

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'criteria_type', 'criteria_value', 'xp_reward']
    list_filter = ['criteria_type']

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ['user', 'badge', 'earned_at']
    list_filter = ['badge']
