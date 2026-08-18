"""
Dashboard bundle: one API call returns everything the dashboard page needs.

Reduces 5 parallel requests → 1, cutting perceived load time significantly.

Endpoint: GET /api/analytics/dashboard/bundle/
Auth: required
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
import datetime

from tests_engine.models import TestAttempt
from questions.models import QuestionAttempt, Question
from analytics.models import (
    DailyActivity, StudyStreak, Announcement,
    UserTopicPerformance,
)
from analytics.serializers import (
    DailyActivitySerializer, StudyStreakSerializer,
    AnnouncementSerializer,
)


def _exam_source_q(exam_source: str) -> Q:
    """Build a Q-filter for a given exam_source label."""
    prefixes = {
        'NEET PG': ('NEET PG',),
        'UPSC CMS': ('UPSC CMS',),
    }
    q = Q(exam_source=exam_source)
    for pat in prefixes.get(exam_source, ()):
        q |= Q(exam_source__startswith=pat)
    return q


class DashboardBundleView(APIView):
    """Single endpoint for the entire dashboard page."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now().date()
        days_120 = now - datetime.timedelta(days=120)

        # ── 1. Overall stats + subject performance (mirrors DashboardView) ──
        attempts = TestAttempt.objects.filter(user=user, is_completed=True)
        overall = attempts.aggregate(
            total_tests=Count('id'),
            avg_score=Avg('score'),
            total_correct=Sum('correct_count'),
            total_incorrect=Sum('incorrect_count'),
            total_unanswered=Sum('unanswered_count'),
            total_time=Sum('time_taken_seconds'),
        )

        qbank_qs = QuestionAttempt.objects.filter(user=user)
        qbank_total = qbank_qs.count()
        qbank_correct = qbank_qs.filter(is_correct=True).count()
        qbank_incorrect = qbank_total - qbank_correct

        total_q = (overall['total_correct'] or 0) + (overall['total_incorrect'] or 0) + qbank_total
        total_correct = (overall['total_correct'] or 0) + qbank_correct
        total_incorrect = (overall['total_incorrect'] or 0) + qbank_incorrect
        overall_accuracy = round(total_correct / total_q * 100, 1) if total_q > 0 else 0

        # Bulk-fetch all subject performance in 1 query
        subject_stats = UserTopicPerformance.objects.filter(
            user=user, subject__isnull=False
        ).values('subject__name', 'subject__code', 'subject__color').annotate(
            total=Sum('total_attempts'),
            correct=Sum('correct_answers'),
        )
        subject_performance = [
            {
                'subject': s['subject__name'],
                'code': s['subject__code'] or '',
                'color': s['subject__color'] or '',
                'total_attempts': s['total'] or 0,
                'correct': s['correct'] or 0,
                'accuracy': round((s['correct'] or 0) / (s['total'] or 1) * 100, 1) if (s['total'] or 0) > 0 else 0,
            }
            for s in subject_stats
        ]

        dashboard = {
            'overall': {
                'total_tests': overall['total_tests'] or 0,
                'avg_score': round(overall['avg_score'] or 0, 1),
                'total_questions': total_q,
                'total_correct': total_correct,
                'total_incorrect': total_incorrect,
                'overall_accuracy': overall_accuracy,
                'total_time_hours': round((overall['total_time'] or 0) / 3600, 1),
            },
            'subject_performance': subject_performance,
        }

        # ── 2. Heatmap (120 days) ──
        activities = DailyActivity.objects.filter(
            user=user, date__gte=days_120
        ).order_by('date')
        heatmap = DailyActivitySerializer(activities, many=True).data

        # ── 3. Streak ──
        streak, _ = StudyStreak.objects.get_or_create(user=user)
        streak_data = StudyStreakSerializer(streak).data

        # ── 4. Announcements ──
        now_dt = timezone.now()
        announcements_qs = Announcement.objects.filter(
            is_active=True,
            delivery_status='sent',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now_dt)
        ).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now_dt)
        )
        user_role = getattr(user, 'role', None)
        user_target = getattr(user, 'target_year', None)
        announcements_qs = announcements_qs.filter(
            Q(audience_filter__role__isnull=True)
            | Q(audience_filter__role='')
            | Q(audience_filter__role=user_role)
        ).filter(
            Q(audience_filter__target_year__isnull=True)
            | Q(audience_filter__target_year='')
            | Q(audience_filter__target_year=user_target)
        )
        announcements_data = AnnouncementSerializer(
            announcements_qs[:10], many=True
        ).data

        # ── 5. Question stats (cms vs neet pg) ──
        cms_qs = Question.objects.filter(is_active=True).filter(_exam_source_q('UPSC CMS'))
        neetpg_qs = Question.objects.filter(is_active=True).filter(_exam_source_q('NEET PG'))
        question_stats = {
            'cms': cms_qs.aggregate(
                total=Count('id'),
                with_explanation=Count('id', filter=Q(explanation__isnull=False) & ~Q(explanation='')),
            ),
            'neet_pg': neetpg_qs.aggregate(
                total=Count('id'),
                with_explanation=Count('id', filter=Q(explanation__isnull=False) & ~Q(explanation='')),
            ),
        }

        return Response({
            'dashboard': dashboard,
            'heatmap': heatmap,
            'streak': streak_data,
            'announcements': announcements_data,
            'question_stats': question_stats,
        })
