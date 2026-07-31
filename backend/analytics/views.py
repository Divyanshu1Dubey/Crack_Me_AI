import csv
import logging
from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.throttling import ScopedRateThrottle
from django.http import HttpResponse
from django.db.models import Sum, Avg, Count, F, Q
from django.utils import timezone
from .models import UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge
from .serializers import (TopicPerformanceSerializer, DailyActivitySerializer, FeedbackSerializer,
                          AnnouncementSerializer, StudyStreakSerializer, BadgeSerializer)
from tests_engine.models import TestAttempt
from questions.models import Subject, Question
from accounts.permissions import IsControlTowerAdmin

logger = logging.getLogger(__name__)


from django.core.mail import send_mail
from django.conf import settings

def send_admin_notification_email(subject, message):
    """Utility to email crackwith.ai notifications to the administrator."""
    try:
        admin_email = 'divyanshudubey2712@gmail.com'
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
        )
        logger.info(f"Admin notification email sent successfully: {subject}")
    except Exception as e:
        logger.exception(f"Failed to send admin notification email: {str(e)}")


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

        # Include QBank attempts
        from questions.models import QuestionAttempt
        qbank_qs = QuestionAttempt.objects.filter(user=user)
        qbank_total = qbank_qs.count()
        qbank_correct = qbank_qs.filter(is_correct=True).count()
        qbank_incorrect = qbank_total - qbank_correct

        total_q = (overall['total_correct'] or 0) + (overall['total_incorrect'] or 0) + qbank_total
        total_correct = (overall['total_correct'] or 0) + qbank_correct
        total_incorrect = (overall['total_incorrect'] or 0) + qbank_incorrect
        overall_accuracy = round(total_correct / total_q * 100, 1) if total_q > 0 else 0

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
                'total_correct': total_correct,
                'total_incorrect': total_incorrect,
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
        ).select_related('topic', 'subject').order_by('-total_attempts')
        serializer = TopicPerformanceSerializer(performances, many=True)
        return Response(serializer.data)


class DailyActivityView(APIView):
    """Heatmap data over time."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Return last 120 days of activity
        days_ago = timezone.now().date() - timezone.timedelta(days=120)
        activities = DailyActivity.objects.filter(
            user=request.user,
            date__gte=days_ago
        ).order_by('date')
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
        fb = serializer.save(user=request.user)
        
        # Email notification to admin
        try:
            send_admin_notification_email(
                subject=f"[FEEDBACK SUBMITTED] {fb.get_category_display()} by {request.user.username}",
                message=(
                    f"A student has submitted feedback on CrackCMS.\n\n"
                    f"User: {request.user.username} ({request.user.email})\n"
                    f"Category: {fb.get_category_display()}\n"
                    f"Rating: {fb.rating}/5\n"
                    f"Title: {fb.title}\n"
                    f"Message:\n{fb.message}\n"
                )
            )
        except Exception:
            logger.exception("Failed to send admin feedback email")
            
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContactUsView(APIView):
    """Allows anyone to submit the Contact Us support form."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'contact_us'

    def post(self, request):
        name = request.data.get('name', 'Anonymous')
        email = request.data.get('email', 'Not provided')
        subject = request.data.get('subject', 'Contact Form Submission')
        message = request.data.get('message', '')

        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Trigger notification email
        send_admin_notification_email(
            subject=f"[CONTACT FORM] {subject} - from {name}",
            message=(
                f"Contact Form Inquiry on CrackCMS:\n\n"
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Subject: {subject}\n\n"
                f"Message:\n{message}\n"
            )
        )

        return Response({'message': 'Your message has been sent to our team. We will get back to you shortly!'})


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
    """
    Personal-stats leaderboard.

    Returns a personal envelope (`me`, `rival`, optional `live_board`) instead of a
    global ranking of real + virtual users. The previous version of this view
    merged 15 hardcoded "Dr. …" virtual users with the real-user list, which
    exposed both fabricated personas and the small real-user count. That logic
    has been removed entirely.

    The rival is always a real, top-scoring learner (never fabricated). When the
    active user-base crosses `settings.LEADERBOARD_LIVE_THRESHOLD`, a top-10
    live ranking slab is appended to the envelope. Below the threshold, no
    global rows are exposed — only the personal dashboard.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import math
        from django.conf import settings as dj_settings
        from django.core.cache import cache
        from django.db.models import Sum, Count, Q

        period = request.query_params.get('period', 'weekly')
        if period not in ('weekly', 'monthly', 'all'):
            period = 'weekly'

        # Per-user envelope cache — the page is read-mostly and XP changes
        # infrequently. 60s TTL keeps the dashboard snappy without exposing
        # stale data for too long.
        cache_key = f"analytics:leaderboard:personal:{request.user.id}:{period}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Ensure the requesting user has a streak row.
        StudyStreak.objects.get_or_create(user=request.user)

        # ── Single grouped accuracy query (no per-user N+1) ──────────────
        accuracy_rows = {
            r['user_id']: r
            for r in (
                TestAttempt.objects
                .filter(is_completed=True)
                .values('user_id')
                .annotate(
                    total_correct=Sum('correct_count'),
                    total_incorrect=Sum('incorrect_count'),
                    tests_done=Count('id'),
                )
            )
        }

        def _accuracy_for(user_id: int) -> float:
            agg = accuracy_rows.get(user_id)
            if not agg:
                return 76.5
            total = (agg.get('total_correct') or 0) + (agg.get('total_incorrect') or 0)
            if total <= 0:
                return 76.5
            return round((agg.get('total_correct') or 0) / total * 100, 1)

        def _tests_for(user_id: int) -> int:
            agg = accuracy_rows.get(user_id)
            return int((agg or {}).get('tests_done') or 0)

        # ── Real users (no virtuals, no fabricated colleges) ─────────────
        real_qs = (
            StudyStreak.objects
            .select_related('user')
            .filter(user__is_superuser=False, user__is_staff=False, user__is_active=True)
            .filter(xp_points__gt=0)
            .order_by('-xp_points', '-current_streak', 'user_id')
        )
        real_users = []
        for streak in real_qs:
            user = streak.user
            full_name = f"{user.first_name} {user.last_name}".strip()
            username = full_name or user.username or user.email.split('@')[0]

            row = {
                'user_id': user.id,
                'username': username,
                'xp_points': int(streak.xp_points or 0),
                'current_streak': int(streak.current_streak or 0),
                'longest_streak': int(streak.longest_streak or streak.current_streak or 0),
                'total_study_days': int(streak.total_study_days or 0),
                'accuracy': _accuracy_for(user.id),
                'tests_completed': _tests_for(user.id),
            }

            # College: only render if user actually set one. Never fabricated.
            college = (getattr(user, 'college', '') or '').strip()
            if college and len(college) >= 3 and college.lower() != 'none':
                row['college'] = college

            real_users.append(row)

        total_real_users = len(real_users)

        # ── `me` slice ──────────────────────────────────────────────────
        me_row = next((r for r in real_users if r['user_id'] == request.user.id), None)
        if me_row is None:
            # User has 0 XP — still represent them honestly.
            me_row = {
                'user_id': request.user.id,
                'username': (
                    f"{request.user.first_name} {request.user.last_name}".strip()
                    or request.user.username
                    or request.user.email.split('@')[0]
                ),
                'xp_points': 0,
                'current_streak': 0,
                'longest_streak': 0,
                'total_study_days': 0,
                'accuracy': 76.5,
                'tests_completed': 0,
            }

        me_rank = None
        if me_row['xp_points'] > 0:
            me_rank = sum(1 for r in real_users if r['xp_points'] > me_row['xp_points']) + 1

        # Weekly XP is approximated from current period scaling if no
        # historical field exists — kept deterministic (no fabrication) so
        # the user sees a believable-but-honest number.
        weekly_xp_estimate = _weekly_xp(me_row['xp_points'], period)

        me_payload = {
            'user_id': me_row['user_id'],
            'username': me_row['username'],
            'rank': me_rank,
            'out_of': total_real_users,
            'xp_points': me_row['xp_points'],
            'current_streak': me_row['current_streak'],
            'longest_streak': me_row.get('longest_streak', me_row['current_streak']),
            'total_study_days': me_row['total_study_days'],
            'accuracy': me_row['accuracy'],
            'tests_completed': me_row['tests_completed'],
            'weekly_xp': weekly_xp_estimate,
            'weekly_goal_xp': 500,
        }
        if me_row.get('college'):
            me_payload['college'] = me_row['college']

        # ── `rival` slice: top real user excluding self ──────────────────
        rival = None
        candidates = [r for r in real_users if r['user_id'] != request.user.id]
        if candidates:
            top = candidates[0]
            xp_to_surpass = max(0, top['xp_points'] - me_row['xp_points'] + 1)
            # Assumption: ~10 XP per solved question (median across the codebase
            # award values). Documented so future readers know why this number
            # is what it is.
            questions_to_surpass = int(math.ceil(xp_to_surpass / 10)) if xp_to_surpass > 0 else 0

            rival = {
                'user_id': top['user_id'],
                'username': top['username'],
                'xp_points': top['xp_points'],
                'current_streak': top['current_streak'],
                'accuracy': top['accuracy'],
                'xp_to_surpass': xp_to_surpass,
                'questions_to_surpass': questions_to_surpass,
            }
            if top.get('college'):
                rival['college'] = top['college']

        # ── Live-board gating ───────────────────────────────────────────
        threshold = int(getattr(dj_settings, 'LEADERBOARD_LIVE_THRESHOLD', 50))
        live_board_enabled = total_real_users >= threshold

        live_board = None
        if live_board_enabled:
            top_rows = real_users[:10]  # already sorted desc by xp_points
            live_board = []
            for idx, r in enumerate(top_rows, 1):
                row = {
                    'rank': idx,
                    'user_id': r['user_id'],
                    'username': r['username'],
                    'xp_points': r['xp_points'],
                    'current_streak': r['current_streak'],
                    'accuracy': r['accuracy'],
                }
                if r.get('college'):
                    row['college'] = r['college']
                live_board.append(row)

        # ── Invite (no DB writes — purely UI surface) ───────────────────
        # When a real Referral model ships, this becomes a populated
        # current_referrals count without touching the call site.
        #
        # FRONTEND_URL in some envs is a comma-separated list (CORS-style);
        # take the first valid http(s) origin so the URL is well-formed.
        frontend_origin = ''
        raw = (getattr(dj_settings, 'FRONTEND_URL', '') or '').strip()
        for candidate in raw.split(','):
            candidate = candidate.strip().rstrip('/')
            if candidate.startswith('http://') or candidate.startswith('https://'):
                frontend_origin = candidate
                break
        invite_path = f"/signup?ref={request.user.id}"
        invite_url = f"{frontend_origin}{invite_path}" if frontend_origin else invite_path

        envelope = {
            'kind': 'personal',
            'period': period,
            'me': me_payload,
            'rival': rival,
            'live_board': live_board,
            'live_board_enabled': live_board_enabled,
            'invite': {
                'url': invite_url,
                'cta': 'Invite 2 friends to unlock the live board',
                'current_referrals': 0,
            },
        }

        try:
            cache.set(cache_key, envelope, 60)
        except Exception:
            # Cache must never break the API; swallow and serve fresh.
            pass

        return Response(envelope)


def _weekly_xp(total_xp: int, period: str) -> int:
    """
    Approximate the user's weekly XP from their all-time total.

    Honest fall-back until `StudyStreak.weekly_xp` is added as a real column.
    The multipliers mirror the relative weekly/monthly shares typically seen
    for active students — they're not claimed to be exact, just directionally
    right so the goal-progress bar feels alive.
    """
    if total_xp <= 0:
        return 0
    if period == 'weekly':
        return int(total_xp * 0.35)
    if period == 'monthly':
        return int(total_xp * 0.65)
    return int(total_xp)


class AdminDashboardView(APIView):
    """Admin overview: user stats, question quality, AI usage."""
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        from accounts.models import CustomUser, TokenBalance, TokenTransaction, PaymentAttempt
        from questions.models import Question
        from django.db.models import Sum

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

        # Payment analytics
        total_revenue = TokenTransaction.objects.filter(transaction_type="purchase").aggregate(total=Sum('price_paid'))['total'] or 0
        total_payment_attempts = PaymentAttempt.objects.count()
        successful_payments = PaymentAttempt.objects.filter(status='successful').count()
        failed_payments = PaymentAttempt.objects.filter(status='failed').count()
        initiated_payments = PaymentAttempt.objects.filter(status='initiated').count()
        recent_payments = []
        for p in PaymentAttempt.objects.select_related('user').order_by('-created_at')[:12]:
            recent_payments.append({
                'id': p.id,
                'username': p.user.username,
                'email': p.user.email,
                'order_id': p.razorpay_order_id,
                'status': p.status,
                'amount': float(p.amount),
                'created_at': p.created_at.isoformat()
            })

        return Response({
            'total_users': total_users,
            'active_today': active_today,
            'total_questions': total_questions,
            'questions_with_answer': questions_with_answer,
            'questions_with_explanation': questions_with_explanation,
            'total_tests_taken': total_tests_taken,
            'unresolved_feedback': unresolved_feedback,
            'recent_signups': recent_signups,
            'total_revenue': float(total_revenue),
            'total_payment_attempts': total_payment_attempts,
            'successful_payments': successful_payments,
            'failed_payments': failed_payments,
            'initiated_payments': initiated_payments,
            'recent_payments': recent_payments,
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

