from django.contrib import admin
from .models import UserTopicPerformance, DailyActivity

@admin.register(UserTopicPerformance)
class UserTopicPerformanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'topic', 'subject', 'total_attempts', 'correct_answers', 'accuracy']
    list_filter = ['subject']

@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'questions_attempted', 'correct_answers']
    list_filter = ['date']
