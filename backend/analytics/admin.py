from django.contrib import admin
from .models import UserTopicPerformance, DailyActivity, Feedback

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
