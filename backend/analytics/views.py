import csv
import logging
from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.http import HttpResponse
from django.db.models import Sum, Avg, Count, F, Q, Max
from django.utils import timezone
from .models import UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge
from .serializers import (TopicPerformanceSerializer, DailyActivitySerializer, FeedbackSerializer,
                          AnnouncementSerializer, StudyStreakSerializer, BadgeSerializer,
                          UserBadgeSerializer, LeaderboardEntrySerializer)
from tests_engine.models import TestAttempt
from questions.models import Subject, Question, QuestionFeedback, Topic
from accounts.permissions import IsControlTowerAdmin

logger = logging.getLogger(__name__)


class DashboardView(APIView):
    """Main analytics dashboard data."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        attempts = TestAttempt.objects.filter(user=user, is_completed=True)

        # Overall stats
        overall = attempts.aggregate(
            total_tests=Count('id'),
            avg_score=Avg('score'),
            total_correct=Sum('correct_count'),
            total_incorrect=Sum('incorrect_count'),
            total_unanswered=Sum('unanswered_count'),
            total_time=Sum('time_taken_seconds'),
        )

        total_q = (overall['total_correct'] or 0) + (overall['total_incorrect'] or 0)
        overall_accuracy = round((overall['total_correct'] or 0) / total_q * 100, 1) if total_q > 0 else 0

        # Subject-wise performance
        subject_perf = []
        for subject in Subject.objects.all():
            perf = UserTopicPerformance.objects.filter(
                user=user, subject=subject
            ).aggregate(
                total=Sum('total_attempts'),
                correct=Sum('correct_answers'),
            )
            total = perf['total'] or 0
            correct = perf['correct'] or 0
            acc = round(correct / total * 100, 1) if total > 0 else 0
            subject_perf.append({
                'subject': subject.name,
                'code': subject.code,
                'color': subject.color,
                'total_attempts': total,
                'correct': correct,
                'accuracy': acc,
            })

        return Response({
            'overall': {
                'total_tests': overall['total_tests'] or 0,
                'avg_score': round(overall['avg_score'] or 0, 1),
                'total_questions': total_q,
                'total_correct': overall['total_correct'] or 0,
                'total_incorrect': overall['total_incorrect'] or 0,
                'overall_accuracy': overall_accuracy,
                'total_time_hours': round((overall['total_time'] or 0) / 3600, 1),
            },
            'subject_performance': subject_perf,
        })


class WeakTopicsView(APIView):
    """Identify weak topics for improvement."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        all_topic_perfs = UserTopicPerformance.objects.filter(
            user=request.user,
            total_attempts__gte=1,
            topic__isnull=False  # Only topics, not subject-level aggregates
        ).select_related('topic', 'subject').order_by('correct_answers')

        weak = []
        strong = []

        for perf in all_topic_perfs:
            data = TopicPerformanceSerializer(perf).data
            if perf.accuracy < 60:
                weak.append(data)
            elif perf.accuracy >= 80:
                strong.append(data)

        # AI-style suggestions
        suggestions = []
        for w in weak[:5]:
            suggestions.append(
                f"You are weak in {w['topic_name']} ({w['accuracy']}% accuracy). "
                f"Revise from {w['subject_name']} and practice more questions."
            )

        return Response({
            'weak_topics': weak[:10],
            'strong_topics': strong[:10],
            'suggestions': suggestions,
        })


class TopicPerformanceView(APIView):
    """Detailed topic-wise performance."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        performances = UserTopicPerformance.objects.filter(
            user=request.user,
            topic__isnull=False  # Only topic-level, not subject-level
        ).select_related('topic', 'subject').order_by('subject__name', 'topic__name')
        serializer = TopicPerformanceSerializer(performances, many=True)
        return Response(serializer.data)


class ActivityHeatmapView(APIView):
    """Daily activity data for heatmap visualization."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        activities = DailyActivity.objects.filter(user=request.user)[:365]
        serializer = DailyActivitySerializer(activities, many=True)
        return Response(serializer.data)


class RecentAttemptsView(APIView):
    """Recent test attempts for the dashboard."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from tests_engine.serializers import TestAttemptSerializer
        attempts = TestAttempt.objects.filter(
            user=request.user, is_completed=True
        ).select_related('test')[:10]
        serializer = TestAttemptSerializer(attempts, many=True, context={'request': request})
        return Response(serializer.data)


class ScorePredictionView(APIView):
    """Predict CMS exam score based on current performance trends."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        attempts = TestAttempt.objects.filter(user=user, is_completed=True).order_by('-started_at')

        if attempts.count() < 3:
            return Response({
                'predicted_score': None,
                'message': 'Complete at least 3 tests to get score prediction',
                'confidence': 'low',
            })

        # Calculate recent accuracy trend
        recent = attempts[:10]
        accuracies = [a.accuracy for a in recent if a.accuracy is not None]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0

        # CMS scoring: 120 questions × ~2.08 marks each = 250 marks
        # Negative marking: -0.33 for wrong
        total_qs = 120
        predicted_correct = int(total_qs * avg_accuracy / 100)
        predicted_wrong = total_qs - predicted_correct
        predicted_score = round(
            predicted_correct * 2.08 - predicted_wrong * 0.33, 1
        )

        # Subject-wise prediction
        subject_predictions = []
        for subject in Subject.objects.all():
            perf = UserTopicPerformance.objects.filter(
                user=user, subject=subject
            ).aggregate(
                total=Sum('total_attempts'),
                correct=Sum('correct_answers'),
            )
            total = perf['total'] or 0
            correct = perf['correct'] or 0
            acc = round(correct / total * 100, 1) if total > 0 else 0
            subject_predictions.append({
                'subject': subject.name,
                'code': subject.code,
                'accuracy': acc,
                'predicted_correct': int(24 * acc / 100),  # ~24 questions per subject
                'strength': 'strong' if acc >= 70 else ('average' if acc >= 50 else 'weak'),
            })

        # Trend direction
        if len(accuracies) >= 5:
            first_half = sum(accuracies[len(accuracies)//2:]) / len(accuracies[len(accuracies)//2:])
            second_half = sum(accuracies[:len(accuracies)//2]) / len(accuracies[:len(accuracies)//2])
            trend = 'improving' if second_half > first_half + 2 else (
                'declining' if second_half < first_half - 2 else 'stable'
            )
        else:
            trend = 'insufficient_data'

        return Response({
            'predicted_score': max(0, predicted_score),
            'predicted_score_paper1': max(0, round(predicted_score / 2, 1)),
            'predicted_score_paper2': max(0, round(predicted_score / 2, 1)),
            'max_score': 250,
            'avg_accuracy': round(avg_accuracy, 1),
            'trend': trend,
            'confidence': 'high' if attempts.count() >= 10 else 'medium',
            'subject_predictions': subject_predictions,
            'tests_taken': attempts.count(),
        })


class PerformanceTrendView(APIView):
    """Accuracy and score trends over time for charting."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        attempts = TestAttempt.objects.filter(
            user=request.user, is_completed=True
        ).order_by('started_at')[:20]

        trend_data = []
        for a in attempts:
            trend_data.append({
                'date': a.started_at.strftime('%Y-%m-%d'),
                'test_title': a.test.title if a.test else 'Test',
                'accuracy': a.accuracy,
                'score': a.score,
                'correct': a.correct_count,
                'incorrect': a.incorrect_count,
                'time_minutes': round((a.time_taken_seconds or 0) / 60, 1),
            })

        return Response({
            'trend': trend_data,
            'total_tests': len(trend_data),
        })


class FeedbackListCreateView(APIView):
    """Students submit feedback; admins see all feedback."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_admin:
            feedbacks = Feedback.objects.all()
        else:
            feedbacks = Feedback.objects.filter(user=request.user)
        serializer = FeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FeedbackDetailView(APIView):
    """Admin can reply to and mark feedback as read."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=403)
        try:
            fb = Feedback.objects.get(pk=pk)
        except Feedback.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        fb.is_read = True
        if 'admin_reply' in request.data:
            fb.admin_reply = request.data['admin_reply']
        fb.save(update_fields=['is_read', 'admin_reply'])
        return Response(FeedbackSerializer(fb).data)

    def delete(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=403)
        try:
            fb = Feedback.objects.get(pk=pk)
        except Feedback.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        fb.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataExportView(APIView):
    """Export all data as JSON for Google Sheets integration (admin only)."""
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        from accounts.models import CustomUser, TokenBalance, TokenTransaction
        export_type = request.query_params.get('type', 'all')
        data = {}

        try:
            if export_type in ('all', 'users'):
                data['users'] = [
                    {
                        'id': u.id,
                        'username': u.username,
                        'email': u.email,
                        'first_name': u.first_name,
                        'last_name': u.last_name,
                        'is_admin': u.is_admin,
                        'date_joined': str(u.date_joined),
                        'last_login': str(u.last_login),
                    } for u in CustomUser.objects.all()
                ]

            if export_type in ('all', 'tokens'):
                balances = TokenBalance.objects.select_related('user').all()
                token_balances = []
                for b in balances:
                    try:
                        avail = b.available_tokens
                    except Exception:
                        avail = b.purchased_tokens + b.feedback_credits
                    token_balances.append({
                        'username': b.user.username,
                        'purchased_tokens': b.purchased_tokens,
                        'feedback_credits': b.feedback_credits,
                        'available': avail,
                    })
                data['token_balances'] = token_balances
                txns = TokenTransaction.objects.select_related('user').order_by('-created_at')[:500]
                data['token_transactions'] = [
                    {
                        'username': t.user.username,
                        'type': t.transaction_type,
                        'amount': t.amount,
                        'note': t.note,
                        'created_at': str(t.created_at),
                    } for t in txns
                ]

            if export_type in ('all', 'feedback'):
                fbs = Feedback.objects.select_related('user').all()
                data['feedback'] = [
                    {
                        'username': f.user.username,
                        'category': f.category,
                        'rating': f.rating,
                        'title': f.title,
                        'message': f.message,
                        'is_read': f.is_read,
                        'admin_reply': f.admin_reply or '',
                        'created_at': str(f.created_at),
                    } for f in fbs
                ]
        except Exception:
            logger.exception('Data export failed for type=%s', export_type)
            return Response({'error': 'Failed to export data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(data)


class DataExportCSVView(APIView):
    """Download data as CSV file (admin only). ?type=users|tokens|transactions|feedback"""
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        from accounts.models import CustomUser, TokenBalance, TokenTransaction
        export_type = request.query_params.get('type', 'users')

        output = StringIO()
        writer = csv.writer(output)

        if export_type == 'users':
            writer.writerow(['ID', 'Username', 'Email', 'First Name', 'Last Name', 'Admin', 'Date Joined', 'Last Login'])
            for u in CustomUser.objects.all():
                writer.writerow([u.id, u.username, u.email, u.first_name, u.last_name, u.is_admin, u.date_joined, u.last_login])
            filename = 'crackcms_users.csv'

        elif export_type == 'tokens':
            writer.writerow(['Username', 'Purchased Tokens', 'Feedback Credits', 'Available'])
            for b in TokenBalance.objects.select_related('user').all():
                writer.writerow([b.user.username, b.purchased_tokens, b.feedback_credits, b.available_tokens])
            filename = 'crackcms_token_balances.csv'

        elif export_type == 'transactions':
            writer.writerow(['Username', 'Type', 'Amount', 'Note', 'Date'])
            for t in TokenTransaction.objects.select_related('user').order_by('-created_at')[:500]:
                writer.writerow([t.user.username, t.transaction_type, t.amount, t.note, t.created_at])
            filename = 'crackcms_transactions.csv'

        elif export_type == 'feedback':
            writer.writerow(['Username', 'Category', 'Rating', 'Title', 'Message', 'Read', 'Admin Reply', 'Date'])
            for f in Feedback.objects.select_related('user').all():
                writer.writerow([f.user.username, f.category, f.rating, f.title, f.message, f.is_read, f.admin_reply, f.created_at])
            filename = 'crackcms_feedback.csv'

        else:
            return Response({'error': 'Invalid type. Use: users, tokens, transactions, feedback'}, status=400)

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class AnnouncementListView(APIView):
    """List active announcements for students, or CRUD for admins."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        announcements = Announcement.objects.filter(
            is_active=True,
            delivery_status='sent',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now)
        )

        user = request.user
        user_role = getattr(user, 'role', None)
        user_target = getattr(user, 'target_year', None)

        announcements = announcements.filter(
            Q(audience_filter__role__isnull=True)
            | Q(audience_filter__role='')
            | Q(audience_filter__role=user_role)
        )

        target_year_filter = Q(audience_filter__target_year__isnull=True) | Q(audience_filter__target_year='')
        if user_target is not None:
            target_year_filter |= Q(audience_filter__target_year=user_target)
            target_year_filter |= Q(audience_filter__target_year=str(user_target).strip())
        announcements = announcements.filter(target_year_filter)

        if not user.is_active:
            announcements = announcements.filter(
                Q(audience_filter__active_only__isnull=True)
                | Q(audience_filter__active_only=False)
            )

        announcements = announcements.select_related('created_by').order_by('-created_at')[:200]
        return Response(AnnouncementSerializer(announcements, many=True).data)

    def post(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheduled_for = serializer.validated_data.get('scheduled_for')
        now = timezone.now()
        if scheduled_for and scheduled_for > now:
            delivery_status = 'scheduled'
            sent_at = None
        else:
            delivery_status = 'sent'
            sent_at = now

        serializer.save(
            created_by=request.user,
            delivery_status=delivery_status,
            sent_at=sent_at,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AnnouncementDetailView(APIView):
    """Update/delete announcements (admin only)."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        try:
            ann = Announcement.objects.get(pk=pk)
        except Announcement.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AnnouncementSerializer(ann, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        try:
            Announcement.objects.get(pk=pk).delete()
        except Announcement.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudyStreakView(APIView):
    """Get current user's study streak and XP."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak, _ = StudyStreak.objects.get_or_create(user=request.user)
        return Response(StudyStreakSerializer(streak).data)


class BadgeListView(APIView):
    """List all badges and which ones the user has earned."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        all_badges = Badge.objects.all()
        earned = set(UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True))
        data = []
        for badge in all_badges:
            bd = BadgeSerializer(badge).data
            bd['earned'] = badge.id in earned
            data.append(bd)
        return Response(data)


class LeaderboardView(APIView):
    """Weekly/monthly/all-time leaderboard ranked by XP."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        period = request.query_params.get('period', 'all')

        # Auto-create StudyStreak for current user if missing
        StudyStreak.objects.get_or_create(user=request.user)

        # Find users with test activity but no streak, create for them
        users_with_tests = TestAttempt.objects.filter(is_completed=True).values_list('user_id', flat=True).distinct()
        existing_streaks = StudyStreak.objects.values_list('user_id', flat=True)
        missing_users = set(users_with_tests) - set(existing_streaks)
        for user_id in missing_users:
            try:
                user = User.objects.get(id=user_id)
                StudyStreak.objects.get_or_create(user=user)
            except User.DoesNotExist:
                pass

        # Get streaks ordered by XP
        streaks = StudyStreak.objects.select_related('user').order_by('-xp_points', '-current_streak')[:50]

        entries = []
        for rank, streak in enumerate(streaks, 1):
            # Calculate accuracy from test attempts
            attempts = TestAttempt.objects.filter(user=streak.user, is_completed=True)
            agg = attempts.aggregate(
                total_correct=Sum('correct_count'),
                total_incorrect=Sum('incorrect_count'),
                tests_done=Count('id'),
            )
            total = (agg['total_correct'] or 0) + (agg['total_incorrect'] or 0)
            accuracy = round((agg['total_correct'] or 0) / total * 100, 1) if total > 0 else 0

            entries.append({
                'rank': rank,
                'username': streak.user.username,
                'user_id': streak.user.id,
                'xp_points': streak.xp_points,
                'current_streak': streak.current_streak,
                'total_study_days': streak.total_study_days,
                'accuracy': accuracy,
                'tests_completed': agg['tests_done'] or 0,
            })
        return Response(entries)


class AdminDashboardView(APIView):
    """Admin overview: user stats, question quality, AI usage."""
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        from accounts.models import CustomUser, TokenBalance
        from questions.models import Question

        total_users = CustomUser.objects.count()
        active_today = DailyActivity.objects.filter(date=timezone.now().date()).count()
        total_questions = Question.objects.count()
        questions_with_answer = Question.objects.exclude(correct_answer='').count()
        questions_with_explanation = Question.objects.filter(explanation__isnull=False).exclude(explanation='').count()
        total_tests_taken = TestAttempt.objects.filter(is_completed=True).count()
        unresolved_feedback = Feedback.objects.filter(is_read=False).count()
        recent_signups = list(
            CustomUser.objects.order_by('-date_joined')[:10].values('id', 'username', 'email', 'date_joined')
        )

        return Response({
            'total_users': total_users,
            'active_today': active_today,
            'total_questions': total_questions,
            'questions_with_answer': questions_with_answer,
            'questions_with_explanation': questions_with_explanation,
            'answer_percentage': round(questions_with_answer / total_questions * 100, 1) if total_questions else 0,
            'total_tests_taken': total_tests_taken,
            'unresolved_feedback': unresolved_feedback,
            'recent_signups': recent_signups,
        })


class AdminWeakAreaControlView(APIView):
    """Phase 7: weak-area control tower data for interventions."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        user_id = request.query_params.get('user_id')

        most_wrong_questions = list(
            Question.objects.filter(feedbacks__is_resolved=False)
            .annotate(wrong_reports=Count('feedbacks', filter=Q(feedbacks__is_resolved=False)))
            .order_by('-wrong_reports', '-year')
            .values('id', 'question_text', 'year', 'subject__name', 'wrong_reports')[:10]
        )

        difficult_topics = list(
            UserTopicPerformance.objects
            .values('topic_id', 'topic__name', 'subject__name')
            .annotate(avg_accuracy=Avg((F('correct_answers') * 100.0) / (F('total_attempts') + 0.0001)), attempts=Sum('total_attempts'))
            .order_by('avg_accuracy', '-attempts')[:10]
        )

        cohort_weak_areas = list(
            UserTopicPerformance.objects
            .values('topic_id', 'topic__name', 'subject__name')
            .annotate(total_attempts=Sum('total_attempts'), total_correct=Sum('correct_answers'))
            .annotate(accuracy=(F('total_correct') * 100.0) / (F('total_attempts') + 0.0001))
            .order_by('accuracy', '-total_attempts')[:15]
        )

        student_weak_areas = []
        if user_id:
            student_weak_areas = list(
                UserTopicPerformance.objects.filter(user_id=user_id)
                .values('topic_id', 'topic__name', 'subject__name', 'total_attempts', 'correct_answers')
                .annotate(accuracy=(F('correct_answers') * 100.0) / (F('total_attempts') + 0.0001))
                .order_by('accuracy', '-total_attempts')[:15]
            )

        impact_priorities = list(
            Question.objects
            .annotate(
                reports=Count('feedbacks', filter=Q(feedbacks__is_resolved=False)),
                attempts=Count('questionresponse', distinct=True),
                correct=Count('questionresponse', filter=Q(questionresponse__is_correct=True), distinct=True),
            )
            .annotate(accuracy=(F('correct') * 100.0) / (F('attempts') + 0.0001))
            .annotate(impact_score=F('reports') * 3 + F('attempts') * 0.2 + (100.0 - F('accuracy')))
            .order_by('-impact_score')
            .values('id', 'question_text', 'reports', 'attempts', 'accuracy', 'impact_score')[:20]
        )

        recommendations = []
        for item in cohort_weak_areas[:5]:
            recommendations.append(
                f"Push revision set for {item.get('topic__name') or 'topic'} in {item.get('subject__name') or 'subject'}; cohort accuracy is {round(item.get('accuracy', 0), 1)}%."
            )

        return Response({
            'most_wrong_questions': most_wrong_questions,
            'most_difficult_topics': difficult_topics,
            'student_weak_areas': student_weak_areas,
            'cohort_weak_areas': cohort_weak_areas,
            'impact_priorities': impact_priorities,
            'revision_recommendations': recommendations,
        })


class AdminCampaignListCreateView(APIView):
    """Phase 8: segmented campaign create/list with scheduling metadata."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        status_filter = (request.query_params.get('status') or '').strip().lower()
        rows = Announcement.objects.all().order_by('-created_at')
        if status_filter:
            rows = rows.filter(delivery_status=status_filter)
        serializer = AnnouncementSerializer(rows[:200], many=True)
        return Response({'count': len(serializer.data), 'results': serializer.data})

    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheduled_for = serializer.validated_data.get('scheduled_for')
        delivery_status = 'scheduled' if scheduled_for and scheduled_for > timezone.now() else 'draft'
        campaign = serializer.save(created_by=request.user, delivery_status=delivery_status)
        return Response(AnnouncementSerializer(campaign).data, status=status.HTTP_201_CREATED)


class AdminCampaignSendNowView(APIView):
    """Mark campaign as sent and compute target audience counts."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request, pk):
        from accounts.models import CustomUser

        try:
            campaign = Announcement.objects.get(pk=pk)
        except Announcement.DoesNotExist:
            return Response({'error': 'Campaign not found'}, status=status.HTTP_404_NOT_FOUND)

        audience = campaign.audience_filter or {}
        users = CustomUser.objects.all()
        role = audience.get('role')
        if role in ['admin', 'student']:
            users = users.filter(role=role)
        target_year = audience.get('target_year')
        if target_year:
            users = users.filter(target_year=target_year)
        active_only = audience.get('active_only')
        if active_only is True:
            users = users.filter(is_active=True)

        campaign.sent_at = timezone.now()
        campaign.delivery_status = 'sent'
        campaign.is_active = True
        campaign.delivery_count = users.count()
        campaign.failure_report = ''
        campaign.save(update_fields=['sent_at', 'delivery_status', 'is_active', 'delivery_count', 'failure_report'])

        return Response(AnnouncementSerializer(campaign).data)

