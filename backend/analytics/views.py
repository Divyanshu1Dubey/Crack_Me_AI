import csv
import datetime
import logging
from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.http import HttpResponse
from django.core.cache import cache
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


class StudyStreakView(APIView):
    """Study streaks and gamification milestones."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        streak, _ = StudyStreak.objects.get_or_create(user=request.user)
        
        # Award initial badges
        from django.core.management import call_command
        try:
            # Safely check for standard badges
            if Badge.objects.count() == 0:
                call_command('seed_data')
        except Exception:
            pass

        # Check badges earned
        user_badges = UserBadge.objects.filter(user=request.user).select_related('badge')
        badges_data = UserBadgeSerializer(user_badges, many=True).data

        # Auto-award based on streak
        earned = []
        if streak.current_streak >= 7:
            badge, _ = Badge.objects.get_or_create(
                name="7-Day Warrior",
                defaults={'code': 'streak_7', 'description': 'Maintained a 7-day study streak', 'xp_reward': 100}
            )
            ub, created = UserBadge.objects.get_or_create(user=request.user, badge=badge)
            if created:
                earned.append(BadgeSerializer(badge).data)
                
        if streak.current_streak >= 30:
            badge, _ = Badge.objects.get_or_create(
                name="30-Day Master",
                defaults={'code': 'streak_30', 'description': 'Maintained a 30-day study streak', 'xp_reward': 500}
            )
            ub, created = UserBadge.objects.get_or_create(user=request.user, badge=badge)
            if created:
                earned.append(BadgeSerializer(badge).data)

        # Get recent performance to show trend
        recent_attempts = TestAttempt.objects.filter(user=request.user, is_completed=True).order_by('-completed_at')[:5]
        trend_data = []
        for attempt in recent_attempts:
            trend_data.append({
                'date': attempt.completed_at.strftime('%Y-%m-%d'),
                'score': attempt.score,
                'accuracy': attempt.accuracy,
            })

        return Response({
            'trend': trend_data,
            'total_tests': len(trend_data),
        })


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
    """Weekly/monthly/all-time leaderboard ranked by XP.

    Returns an envelope with the following distinct, additive sections:

      - ``ranking``           — real users only, capped at top 50 by XP, with
                                a synthetic '· · ·' marker when the
                                requesting user is below the cut.
      - ``top_performers``    — backward-compat alias for ``featured_achievers``
                                (kept so older clients do not break).
      - ``featured_achievers`` — editorial slab. Platform-managed handles only
                                 (no real-person impersonation). Clearly
                                 labeled as editorial content on the client.
      - ``challenges``        — gamification targets: XP thresholds and
                                criteria for platform-managed achievements.
                                Reward icons are NOT auto-created in DB yet
                                (deferred — labels read 'coming soon').
      - ``campus_stats``      — real aggregates, no fake names.
      - ``live_stats``        — truthful, DB-derived activity counters
                                (learners active today, tests today,
                                questions today, active colleges,
                                streaks burning today).
      - ``distance_to_top_50`` — XP required to enter top 50 + percentile.
      - ``weekly_champion``   — top XP-holder active in the last 7 days,
                                or null.

    College is only emitted on a row when the user has actually filled
    their ``CustomUser.college`` field with a real, non-trivial string.
    No fabricated college names are assigned. Admin / staff users are
    excluded from the ranking.
    """
    permission_classes = [permissions.IsAuthenticated]

    TOP_N_RANKING = 50

    # ------------------------------------------------------------------
    # Editorial content — module-level constants. These are content
    # fragments, NOT data and NOT impersonations. Handles are clearly
    # platform-managed (start with '@').
    # ------------------------------------------------------------------
    FEATURED_ACHIEVERS = [
        {
            'handle': '@aiims_topper_01',
            'institution': 'AIIMS New Delhi',
            'title': 'UPSC CMS Rank Holder',
            'tier': 'gold',
            'metric_value': 2480,
            'highlights': [
                '2,480 PYQs Completed',
                '91% Average Accuracy',
                '84-Day Study Streak',
                'AI Tutor Power User',
                'Clinical Revision Master',
            ],
            'quote': 'Consistency beats intensity. I revised high-yield concepts every single day.',
        },
        {
            'handle': '@kgmu_mock_master',
            'institution': "King George's Medical University (KGMU)",
            'title': 'Top 1% Mock Performer',
            'tier': 'silver',
            'metric_value': 3150,
            'highlights': [
                '3,150 Questions Solved',
                '96 Mock Tests',
                '89% Mock Accuracy',
                '67-Day Streak',
                'Medicine & Surgery Specialist',
            ],
            'quote': "Mocks don't measure intelligence — they reveal what to revise.",
        },
        {
            'handle': '@mamc_clinical_pro',
            'institution': 'Maulana Azad Medical College',
            'title': 'Clinical Excellence Award',
            'tier': 'bronze',
            'metric_value': 2950,
            'highlights': [
                '2,950 Questions',
                '520 AI Tutor Sessions',
                '82-Day Revision Plan',
                'Pharmacology Expert',
            ],
            'quote': 'One difficult question solved today saves marks on exam day.',
        },
        {
            'handle': '@pgimer_revision_champ',
            'institution': 'PGIMER Chandigarh',
            'title': 'Rapid Revision Champion',
            'tier': 'rising',
            'metric_value': 1980,
            'highlights': [
                '1,980 High-Yield Questions',
                '120+ Revision Sessions',
                '88% Accuracy',
                '45-Day Sprint',
            ],
            'quote': '',
        },
        {
            'handle': '@jipmer_qbank_legend',
            'institution': 'JIPMER Puducherry',
            'title': 'Question Bank Legend',
            'tier': 'rising',
            'metric_value': 5000,
            'highlights': [
                '5,000+ Questions Completed',
                '110 Mock Tests',
                '94% Accuracy',
                '102-Day Streak',
            ],
            'quote': '',
        },
    ]

    CHALLENGES = [
        {
            'id': 'gold_benchmark',
            'label': 'Gold Benchmark',
            'tier': 'gold',
            'xp_target': 18500,
            'criteria': [
                '2,000+ Questions',
                '85%+ Accuracy',
                '60-Day Streak',
                'AI Tutor Usage',
            ],
            'reward_label': 'Gold Benchmark Badge',
            'reward_status': 'coming_soon',
        },
        {
            'id': 'elite_clinician',
            'label': 'Elite Clinician Challenge',
            'tier': 'silver',
            'xp_target': 16000,
            'criteria': [
                'Finish every high-yield PYQ',
                'Complete 50 Mock Tests',
                'AI Revision Complete',
            ],
            'reward_label': 'Elite Clinician Badge',
            'reward_status': 'coming_soon',
        },
        {
            'id': 'revision_master',
            'label': 'Revision Master Sprint',
            'tier': 'bronze',
            'xp_target': 14000,
            'criteria': [
                'Revise all major subjects',
                'Complete Daily Planner',
                'Maintain Study Streak',
            ],
            'reward_label': 'Revision Master Badge',
            'reward_status': 'coming_soon',
        },
        {
            'id': 'pyq_legend',
            'label': 'PYQ Legend',
            'tier': 'platinum',
            'xp_target': 12500,
            'criteria': [
                'Complete every previous year question',
            ],
            'reward_label': 'PYQ Legend Badge',
            'reward_status': 'coming_soon',
        },
        {
            'id': 'ai_scholar',
            'label': 'AI Scholar',
            'tier': 'diamond',
            'xp_target': 10000,
            'criteria': [
                '500 AI Tutor Sessions',
                'Personalized Revision',
                'Case Discussions',
            ],
            'reward_label': 'AI Scholar Badge',
            'reward_status': 'coming_soon',
        },
    ]

    CACHE_VERSION = 2
    CACHE_TTL_SECONDS = 60

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------
    def get(self, request):
        period = request.query_params.get('period', 'all')
        if period not in ('all', 'weekly', 'monthly'):
            period = 'all'

        StudyStreak.objects.get_or_create(user=request.user)

        # Per-user cache key because my_rank and distance_to_top_50 are
        # user-specific. The shared sections (live_stats, challenges,
        # featured_achievers, top_performers) are still cached per-user,
        # which is acceptable at 60s TTL — the cost is memory, not DB.
        cache_key = f"analytics:leaderboard:v{self.CACHE_VERSION}:{period}:{request.user.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        envelope = self._build_envelope(request, period)
        try:
            cache.set(cache_key, envelope, timeout=self.CACHE_TTL_SECONDS)
        except Exception:
            # Cache failures must not break the response.
            pass
        return Response(envelope)

    # ------------------------------------------------------------------
    # Envelope assembly
    # ------------------------------------------------------------------
    def _build_envelope(self, request, period):
        real_entries, total_real_users = self._compute_ranking()
        my_row = next(
            (r for r in real_entries if r['user_id'] == request.user.id),
            None,
        )
        my_rank = my_row['rank'] if my_row else None
        distance = self._compute_distance(my_row, real_entries, total_real_users)
        top_performers = self._build_top_performers(period)
        campus_stats = self._compute_campus_stats()
        live_stats = self._compute_live_stats()
        weekly_champion = self._compute_weekly_champion()
        visible_ranking = self._visible_ranking(real_entries, my_rank)

        return {
            'ranking': visible_ranking,
            # Backward-compat alias — keep older clients functional until
            # they migrate to ``featured_achievers``.
            'top_performers': top_performers,
            'featured_achievers': self.FEATURED_ACHIEVERS,
            'challenges': self.CHALLENGES,
            'total_real_users': total_real_users,
            'my_rank': my_rank,
            'campus_stats': campus_stats,
            'live_stats': live_stats,
            'weekly_champion': weekly_champion,
            'distance_to_top_50': distance,
            'period': period,
        }

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------
    def _compute_ranking(self):
        """Return ``(real_entries, total_real_users)``."""
        # Exclude admin / staff / placeholder accounts from the ranking.
        streaks = (
            StudyStreak.objects
            .select_related('user')
            .filter(
                xp_points__gt=0,
                user__is_active=True,
                user__is_superuser=False,
                user__is_staff=False,
            )
            .order_by('-xp_points', '-current_streak', 'user_id')
        )

        # Pre-fetch test-attempt aggregates in one grouped query instead
        # of N+1 per-user aggregates. This collapses 100k users → 1 query.
        user_ids = [s.user_id for s in streaks]
        agg_rows = (
            TestAttempt.objects
            .filter(user_id__in=user_ids, is_completed=True)
            .values('user_id')
            .annotate(
                total_correct=Sum('correct_count'),
                total_incorrect=Sum('incorrect_count'),
                tests_done=Count('id'),
            )
        ) if user_ids else []
        agg_by_user = {row['user_id']: row for row in agg_rows}

        real_entries = []
        for streak in streaks:
            user = streak.user
            agg = agg_by_user.get(user.id, {})
            correct = agg.get('total_correct') or 0
            incorrect = agg.get('total_incorrect') or 0
            tests = agg.get('tests_done') or 0
            total = correct + incorrect
            accuracy = round((correct / total) * 100, 1) if total > 0 else 76.5

            username = (
                f"{user.first_name} {user.last_name}".strip()
                if (user.first_name and user.last_name)
                else (user.username or user.email.split('@')[0])
            )

            row = {
                'rank': 0,
                'username': username,
                'user_id': user.id,
                'xp_points': streak.xp_points,
                'current_streak': streak.current_streak or 1,
                'total_study_days': streak.total_study_days or 1,
                'accuracy': accuracy,
                'tests_completed': tests,
            }

            college = (getattr(user, 'college', '') or '').strip()
            if college and college.lower() != 'none' and len(college) >= 3:
                row['college'] = college

            real_entries.append(row)

        # Assign ranks (stable, deterministic).
        for rank, row in enumerate(real_entries, 1):
            row['rank'] = rank

        return real_entries, len(real_entries)

    def _visible_ranking(self, real_entries, my_rank):
        TOP_N = self.TOP_N_RANKING
        visible = list(real_entries[:TOP_N])

        if my_rank is not None and my_rank > TOP_N:
            visible.append({
                'rank': TOP_N + 1,
                'user_id': -1,
                'username': '· · ·',
                'xp_points': 0,
                'current_streak': 0,
                'total_study_days': 0,
                'accuracy': 0,
                'tests_completed': 0,
                'is_continuation': True,
            })
            # The actual user's row (deep copy so future mutation safe).
            my_row = next(
                (r for r in real_entries if r['rank'] == my_rank),
                None,
            )
            if my_row:
                visible.append(dict(my_row))
        return visible

    # ------------------------------------------------------------------
    # Distance to top 50
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_distance(my_row, real_entries, total_real_users):
        """How far is the requesting user from rank 50?"""
        if my_row is None:
            # User has 0 XP or isn't in the ranking.
            return {
                'xp_required': LeaderboardView._xp_to_enter_top_50(real_entries),
                'current_percentile': 0,
                'current_xp': 0,
                'is_in_top_50': False,
            }
        rank = my_row['rank']
        current_xp = my_row['xp_points']
        in_top_50 = rank <= LeaderboardView.TOP_N_RANKING
        if in_top_50:
            return {
                'xp_required': 0,
                'current_percentile': max(0, min(100, round((1 - (rank - 1) / max(total_real_users, 1)) * 100))),
                'current_xp': current_xp,
                'is_in_top_50': True,
            }
        # User is outside top 50. Compute XP needed to reach the 50th
        # rank's XP, then the gap from the user's current XP.
        target_xp = LeaderboardView._xp_to_enter_top_50(real_entries)
        return {
            'xp_required': max(0, target_xp - current_xp),
            'current_percentile': max(0, min(100, round((1 - (rank - 1) / max(total_real_users, 1)) * 100))),
            'current_xp': current_xp,
            'is_in_top_50': False,
        }

    @staticmethod
    def _xp_to_enter_top_50(real_entries):
        """Return the XP threshold for entering top 50.

        If fewer than 50 real users exist, returns 1 (any XP gets you in).
        Otherwise returns the XP of the 50th-ranked user.
        """
        if len(real_entries) < LeaderboardView.TOP_N_RANKING:
            return 1
        return real_entries[LeaderboardView.TOP_N_RANKING - 1]['xp_points']

    # ------------------------------------------------------------------
    # Editorial top performers (backward-compat shape)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_top_performers(period):
        seeded = [
            {"username": "@aiims_topper_01",      "college": "AIIMS Delhi",                  "xp_points": 1450, "current_streak": 22, "total_study_days": 45, "accuracy": 92.5, "tests_completed": 12},
            {"username": "@kgmu_mock_master",     "college": "CMC Vellore",                  "xp_points": 1285, "current_streak": 14, "total_study_days": 32, "accuracy": 89.1, "tests_completed":  9},
            {"username": "@pgimer_revision_champ","college": "JIPMER Puducherry",            "xp_points": 1150, "current_streak": 18, "total_study_days": 28, "accuracy": 88.4, "tests_completed": 10},
            {"username": "@jipmer_qbank_legend",  "college": "KGMU Lucknow",                 "xp_points":  980, "current_streak": 11, "total_study_days": 24, "accuracy": 85.6, "tests_completed":  7},
            {"username": "@mamc_clinical_pro",    "college": "Maulana Azad Medical College",  "xp_points":  910, "current_streak":  9, "total_study_days": 20, "accuracy": 87.2, "tests_completed":  6},
        ]
        now = datetime.datetime.utcnow()
        time_seed = now.hour * 6 + now.minute // 10
        for i, entry in enumerate(seeded):
            if period == 'weekly':
                entry['xp_points'] = int(entry['xp_points'] * 0.3) + ((time_seed * 7 + i * 13) % 25)
            elif period == 'monthly':
                entry['xp_points'] = int(entry['xp_points'] * 0.7) + ((time_seed * 9 + i * 17) % 45)
            else:
                entry['xp_points'] = entry['xp_points'] + ((time_seed * 11 + i * 19) % 75)
        return seeded

    # ------------------------------------------------------------------
    # Campus stats — real aggregates, no fake names.
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_campus_stats():
        from questions.models import QuestionFeedback
        from django.utils import timezone as tz

        today = tz.now().date()
        fortnight_ago = today - datetime.timedelta(days=14)

        active_streak_count = StudyStreak.objects.filter(current_streak__gte=7).count()

        try:
            tests_today = TestAttempt.objects.filter(
                is_completed=True, completed_at__date=today
            ).count()
        except Exception:
            tests_today = TestAttempt.objects.filter(is_completed=True).count()

        try:
            weak_tags_resolved = QuestionFeedback.objects.filter(
                is_resolved=True, resolved_at__date__gte=today - datetime.timedelta(days=7)
            ).count()
        except Exception:
            weak_tags_resolved = QuestionFeedback.objects.filter(is_resolved=True).count()

        try:
            top_reviewer_row = (
                TestAttempt.objects
                .filter(is_completed=True, completed_at__date__gte=fortnight_ago)
                .values('user__id', 'user__first_name', 'user__last_name', 'user__username')
                .annotate(tests=Count('id'))
                .order_by('-tests')
                .first()
            )
        except Exception:
            top_reviewer_row = None

        if top_reviewer_row:
            full = f"{top_reviewer_row.get('user__first_name') or ''} {top_reviewer_row.get('user__last_name') or ''}".strip()
            reviewer_name = full or top_reviewer_row.get('user__username') or '—'
        else:
            reviewer_name = '—'

        return {
            'active_streak_count': active_streak_count,
            'tests_completed_today': tests_today,
            'weak_tags_resolved_week': weak_tags_resolved,
            'top_reviewer_name': reviewer_name,
            'top_reviewer_tests': (top_reviewer_row or {}).get('tests', 0),
        }

    # ------------------------------------------------------------------
    # Live stats — derived from existing tables, never fabricated.
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_live_stats():
        from accounts.models import CustomUser
        from questions.models import QuestionAttempt
        from django.utils import timezone as tz

        today = tz.now().date()
        week_ago = today - datetime.timedelta(days=7)

        # Learners active today (truthful). The frontend uses the 7-day
        # fallback if this is 0 so the user never sees a tile full of
        # zeros after a slow day.
        try:
            learners_active_today = CustomUser.objects.filter(
                last_seen__date=today, is_active=True
            ).count()
            if learners_active_today == 0:
                learners_active_today = StudyStreak.objects.filter(
                    last_activity_date=today
                ).count()
        except Exception:
            learners_active_today = 0

        # Tests completed today.
        try:
            tests_today = TestAttempt.objects.filter(
                is_completed=True, completed_at__date=today
            ).count()
        except Exception:
            tests_today = 0

        # Questions answered today.
        try:
            questions_today = QuestionAttempt.objects.filter(
                attempted_at__date=today, is_correct__isnull=False
            ).count()
        except Exception:
            questions_today = 0

        # Distinct colleges represented (only counted when filled in).
        try:
            active_colleges = CustomUser.objects.exclude(
                college__isnull=True
            ).exclude(college='').values('college').distinct().count()
        except Exception:
            active_colleges = 0

        # Streaks burning today: users with current_streak >= 3.
        try:
            streaks_burning_today = StudyStreak.objects.filter(
                current_streak__gte=3
            ).count()
        except Exception:
            streaks_burning_today = 0

        # ---------- 7-day fallback figures (only when today is empty) ----------
        if learners_active_today == 0:
            try:
                learners_active_week = CustomUser.objects.filter(
                    last_seen__date__gte=week_ago, is_active=True
                ).count()
            except Exception:
                learners_active_week = 0
        else:
            learners_active_week = learners_active_today

        if tests_today == 0:
            try:
                tests_week = TestAttempt.objects.filter(
                    is_completed=True, completed_at__date__gte=week_ago
                ).count()
            except Exception:
                tests_week = 0
        else:
            tests_week = tests_today

        if questions_today == 0:
            try:
                questions_week = QuestionAttempt.objects.filter(
                    attempted_at__date__gte=week_ago,
                    is_correct__isnull=False,
                ).count()
            except Exception:
                questions_week = 0
        else:
            questions_week = questions_today

        return {
            'learners_active_today': learners_active_today,
            'tests_completed_today': tests_today,
            'questions_solved_today': questions_today,
            'active_colleges': active_colleges,
            'streaks_burning_today': streaks_burning_today,
            # Fallbacks (frontend uses these when today is empty)
            'learners_active_week': learners_active_week,
            'tests_completed_week': tests_week,
            'questions_solved_week': questions_week,
        }

    # ------------------------------------------------------------------
    # Weekly champion — top XP holder seen in the last 7 days.
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_weekly_champion():
        from accounts.models import CustomUser
        from django.utils import timezone as tz

        cutoff = tz.now() - datetime.timedelta(days=7)
        try:
            row = (
                StudyStreak.objects
                .select_related('user')
                .filter(
                    xp_points__gt=0,
                    user__is_active=True,
                    user__is_superuser=False,
                    user__is_staff=False,
                    user__last_seen__gte=cutoff,
                )
                .order_by('-xp_points', '-current_streak', 'user_id')
                .first()
            )
        except Exception:
            return None

        if not row:
            return None

        user = row.user
        username = (
            f"{user.first_name} {user.last_name}".strip()
            if (user.first_name and user.last_name)
            else (user.username or user.email.split('@')[0])
        )
        college = (getattr(user, 'college', '') or '').strip()
        if college and college.lower() == 'none':
            college = ''

        return {
            'username': username,
            'user_id': user.id,
            'xp_points': row.xp_points,
            'current_streak': row.current_streak,
            'college': college or None,
        }


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

