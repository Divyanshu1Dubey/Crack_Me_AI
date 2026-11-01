import csv
import hashlib
import logging
import math
import os
import threading
from collections import defaultdict
from datetime import datetime, time, timedelta
from io import StringIO
from rest_framework.views import APIView
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from django.http import Http404, HttpResponse
from django.db.models import (Sum, Avg, Count, F, Q, Exists, OuterRef, Value, BooleanField, ExpressionWrapper,
                              FloatField, Min)
from django.utils import timezone
from .models import (UserTopicPerformance, DailyActivity, Feedback, Announcement, StudyStreak, Badge, UserBadge,
                     ContactMessage, AnalyticsEvent, XPEvent)
from questions.models import StudyTimeBreakdown, UserQuest, QuestStreak, MistakeNotebook
from .serializers import (TopicPerformanceSerializer, DailyActivitySerializer, FeedbackSerializer,
                          AnnouncementSerializer, StudentAnnouncementSerializer, StudyStreakSerializer, BadgeSerializer,
                          StudyTimeBreakdownSerializer, UserQuestSerializer, UserQuestAdminSerializer, QuestStreakSerializer,
                          MistakeNotebookSerializer)
from tests_engine.models import TestAttempt
from questions.models import Question
from accounts.permissions import IsControlTowerAdmin

logger = logging.getLogger(__name__)


from django.core.mail import send_mail
from django.conf import settings

# Mail backends that accept a message but deliver nothing (settings.py falls
# back to the console backend when no SMTP password is configured).
_NON_DELIVERING_EMAIL_BACKENDS = (
    'django.core.mail.backends.console.EmailBackend',
    'django.core.mail.backends.dummy.EmailBackend',
)
_DEFAULT_ADMIN_NOTIFICATION_EMAIL = 'divyanshudubey2712@gmail.com'


def _admin_notification_recipient() -> str:
    return (
        getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', '')
        or os.getenv('ADMIN_NOTIFICATION_EMAIL', '')
        or _DEFAULT_ADMIN_NOTIFICATION_EMAIL
    ).strip()


def send_admin_notification_email(subject, message) -> bool:
    """Email a notification to the administrator.

    Returns True only when the message was handed to a mail backend that
    really delivers mail; never raises.
    """
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[_admin_notification_recipient()],
            fail_silently=False,
        )
    except Exception as e:
        logger.exception("Failed to send admin notification email: %s", e)
        return False
    if getattr(settings, 'EMAIL_BACKEND', '') in _NON_DELIVERING_EMAIL_BACKENDS:
        logger.warning("Admin notification not delivered (no real email backend configured): %s", subject)
        return False
    logger.info("Admin notification email sent successfully: %s", subject)
    return bool(sent)


def _run_in_background(func, *args) -> None:
    """Run a best-effort notification off the request thread (after the
    current transaction commits), so slow SMTP never delays the response.
    ``ADMIN_NOTIFICATIONS_SYNC`` runs it inline (tests)."""
    if getattr(settings, 'ADMIN_NOTIFICATIONS_SYNC', False):
        func(*args)
        return

    def _target():
        from django.db import connection
        try:
            func(*args)
        except Exception:
            logger.exception('Background admin notification failed')
        finally:
            connection.close()

    from django.db import transaction
    transaction.on_commit(
        lambda: threading.Thread(target=_target, name='admin-notify', daemon=True).start()
    )


class _DefaultRateThrottle(UserRateThrottle):
    """Per-user (per-IP when anonymous) throttle with a built-in default.

    The rate can be set in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'][scope];
    a scope missing there falls back to ``default_rate`` instead of raising
    ImproperlyConfigured (HTTP 500) on every request.
    """
    default_rate = None

    def get_rate(self):
        try:
            return super().get_rate()
        except ImproperlyConfigured:
            return self.default_rate


class FeedbackSubmitThrottle(_DefaultRateThrottle):
    scope = 'feedback_submit'
    default_rate = '10/hour'


class ContactHourlyThrottle(_DefaultRateThrottle):
    scope = 'contact_us_hourly'
    default_rate = '20/hour'


def _csv_safe(value):
    """Neutralise spreadsheet formulas in exported text cells (CSV injection):
    a cell starting with = + - @ tab or CR is prefixed with a quote."""
    if isinstance(value, str) and value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


class _FormulaSafeCSVWriter:
    """csv.writer whose text cells go through _csv_safe."""

    def __init__(self, stream):
        self._writer = csv.writer(stream)

    def writerow(self, row):
        self._writer.writerow([_csv_safe(cell) for cell in row])


def subject_totals(user) -> list:
    """Per-subject attempts / correct answers for ``user``.

    Every answer updates the subject-level row (topic=NULL) *and* the topic
    row, so summing all rows double-counted. Use the subject-level row, and
    the topic rows only for subjects that have none (older data).
    """
    fields = ('subject_id', 'subject__name', 'subject__code', 'subject__color')
    base = UserTopicPerformance.objects.filter(user=user, subject__isnull=False)

    def _grouped(qs):
        return qs.values(*fields).annotate(total=Sum('total_attempts'), correct=Sum('correct_answers')).order_by()

    rows = {r['subject_id']: r for r in _grouped(base.filter(topic__isnull=True))}
    for r in _grouped(base.filter(topic__isnull=False)):
        rows.setdefault(r['subject_id'], r)
    return sorted(rows.values(), key=lambda r: (r['subject__name'] or ''))


class DashboardView(APIView):
    """Main analytics dashboard data."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        cache_key = f'dashboard:{user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
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

        # Subject-wise performance — aggregated queries, no N+1, no double count
        subject_perf = []
        for perf in subject_totals(user):
            total = perf['total'] or 0
            correct = perf['correct'] or 0
            acc = round(correct / total * 100, 1) if total > 0 else 0
            subject_perf.append({
                'subject': perf['subject__name'],
                'code': perf['subject__code'],
                'color': perf['subject__color'],
                'total_attempts': total,
                'correct': correct,
                'accuracy': acc,
            })

        result = Response({
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
        cache.set(cache_key, result.data, 120)
        return result


WEAK_TOPIC_MIN_ATTEMPTS = 3


class WeakTopicsView(APIView):
    """Identify weak topics for improvement."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Ranked by accuracy (it used to be the absolute correct count, which
        # put barely-attempted topics first), ignoring topics with too few
        # attempts to judge.
        topic_perfs = UserTopicPerformance.objects.filter(
            user=request.user,
            total_attempts__gte=WEAK_TOPIC_MIN_ATTEMPTS,
            topic__isnull=False  # Only topics, not subject-level aggregates
        ).select_related('topic', 'subject').annotate(
            acc=ExpressionWrapper(F('correct_answers') * 100.0 / F('total_attempts'), output_field=FloatField()),
        )

        weak = [TopicPerformanceSerializer(p).data
                for p in topic_perfs.filter(acc__lt=60).order_by('acc', '-total_attempts')[:10]]
        strong = [TopicPerformanceSerializer(p).data
                  for p in topic_perfs.filter(acc__gte=80).order_by('-acc', '-total_attempts')[:10]]

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
        days_ago = timezone.localdate() - timezone.timedelta(days=120)
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
    """Predict CMS exam score based on current performance trends.

    UPSC CMS has two papers of 120 questions / 250 marks each (500 total):
    Paper I = General Medicine 96 + Paediatrics 24; Paper II = Surgery,
    Obstetrics & Gynaecology and PSM, 40 each. A wrong answer costs one
    third of the question's marks; unanswered questions cost nothing.
    """
    permission_classes = [permissions.IsAuthenticated]

    MARKS_PER_QUESTION = 250 / 120
    PENALTY_PER_WRONG = MARKS_PER_QUESTION / 3
    PAPER_PATTERN = {
        1: {'MED': 96, 'PED': 24},
        2: {'SUR': 40, 'OBG': 40, 'PSM': 40},
    }
    SUBJECT_MIN_ATTEMPTS = 10

    def get(self, request):
        user = request.user
        attempts = TestAttempt.objects.filter(user=user, is_completed=True).select_related('test').order_by('-started_at')
        attempt_count = attempts.count()

        if attempt_count < 3:
            return Response({
                'predicted_score': None,
                'message': 'Complete at least 3 tests to get score prediction',
                'confidence': 'low',
            })

        # Calculate recent accuracy trend
        recent = list(attempts[:10])
        accuracies = [a.accuracy for a in recent if a.accuracy is not None]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
        # Share of questions the student actually answers (skips are not wrong).
        answered = sum((a.correct_count or 0) + (a.incorrect_count or 0) for a in recent)
        offered = answered + sum(a.unanswered_count or 0 for a in recent)
        attempt_rate = answered / offered if offered else 1.0

        # Subject-wise prediction — aggregated queries, no N+1, no double count
        subject_predictions = []
        subject_accuracy = {}
        for perf in subject_totals(user):
            total = perf['total'] or 0
            correct = perf['correct'] or 0
            acc = round(correct / total * 100, 1) if total > 0 else 0
            code = (perf['subject__code'] or '').upper()
            if total >= self.SUBJECT_MIN_ATTEMPTS:
                subject_accuracy[code] = acc
            out_of = next((p[code] for p in self.PAPER_PATTERN.values() if code in p), None)
            subject_predictions.append({
                'subject': perf['subject__name'],
                'code': perf['subject__code'],
                'accuracy': acc,
                # Questions this subject has in the real paper (None: not a CMS paper subject).
                'out_of': out_of,
                'predicted_correct': int(round(out_of * attempt_rate * acc / 100)) if out_of else None,
                'strength': 'strong' if acc >= 70 else ('average' if acc >= 50 else 'weak'),
            })

        def _paper_score(pattern):
            correct = wrong = 0.0
            for code, questions in pattern.items():
                acc = subject_accuracy.get(code, avg_accuracy) / 100
                answered_qs = questions * attempt_rate
                correct += answered_qs * acc
                wrong += answered_qs * (1 - acc)
            return max(0.0, correct * self.MARKS_PER_QUESTION - wrong * self.PENALTY_PER_WRONG)

        paper1 = round(_paper_score(self.PAPER_PATTERN[1]), 1)
        paper2 = round(_paper_score(self.PAPER_PATTERN[2]), 1)
        predicted_score = round(paper1 + paper2, 1)

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
            'predicted_score': predicted_score,
            'predicted_score_paper1': paper1,
            'predicted_score_paper2': paper2,
            'max_score': 500,
            'max_score_per_paper': 250,
            'attempt_rate': round(attempt_rate * 100, 1),
            'avg_accuracy': round(avg_accuracy, 1),
            'trend': trend,
            'confidence': 'high' if attempt_count >= 10 else 'medium',
            'subject_predictions': subject_predictions,
            'tests_taken': attempt_count,
        })


class PerformanceTrendView(APIView):
    """Accuracy and score trends over time for charting."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # The latest 20 tests (it used to be the oldest 20, so the charts
        # froze after the 20th test), charted oldest -> newest.
        attempts = list(TestAttempt.objects.filter(
            user=request.user, is_completed=True
        ).select_related('test').order_by('-started_at')[:20])
        attempts.reverse()

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


class PYQTrendsView(APIView):
    """Year x subject question counts of the active PYQ bank (Exam Trends page).

    ``GET /api/analytics/pyq-trends/?exam_source=UPSC CMS`` -- real counts only;
    questions without a year (year 0) count towards ``total`` but not the matrix.
    """
    permission_classes = [permissions.IsAuthenticated]

    EXAM_SOURCES = ('UPSC CMS', 'NEET PG', 'INI-CET', 'FMGE', 'USMLE')

    def get(self, request):
        exam_source = (request.query_params.get('exam_source') or 'UPSC CMS').strip()
        if exam_source not in self.EXAM_SOURCES:
            return Response({'error': f"exam_source must be one of: {', '.join(self.EXAM_SOURCES)}"}, status=400)
        cache_key = 'analytics:pyq_trends:' + hashlib.sha256(exam_source.encode()).hexdigest()[:16]
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        # Prefix match folds "NEET PG (recall)"-style labels into their exam.
        bank = Question.objects.filter(is_active=True, exam_source__startswith=exam_source)
        rows = list(
            bank.filter(year__gt=0)
            .values('year', 'subject_id', 'subject__name', 'subject__code', 'subject__color')
            .annotate(count=Count('id'))
            .order_by()
        )
        subjects = {}
        for row in rows:
            if row['subject__name'] == 'Imported':
                row['subject__name'] = 'Expert Curated'  # same rename as the question serializers
            entry = subjects.setdefault(row['subject_id'], {
                'id': row['subject_id'], 'name': row['subject__name'], 'code': row['subject__code'],
                'color': row['subject__color'] or '', 'count': 0,
            })
            entry['count'] += row['count']
        payload = {
            'exam_source': exam_source,
            'total': bank.count(),
            'years': sorted({row['year'] for row in rows}, reverse=True),
            'subjects': sorted(subjects.values(), key=lambda s: (-s['count'], s['name'] or '')),
            'trends': [
                {'year': row['year'], 'subject__name': row['subject__name'],
                 'subject__code': row['subject__code'], 'count': row['count']}
                for row in rows
            ],
        }
        try:
            cache.set(cache_key, payload, 600)
        except Exception:
            pass
        return Response(payload)


class FeedbackListCreateView(APIView):
    """Students submit feedback; admins see all feedback (paginated)."""
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.request.method == 'POST':
            throttles.append(FeedbackSubmitThrottle())
        return throttles

    def get(self, request):
        feedbacks = Feedback.objects.select_related('user')
        if not request.user.is_admin:
            feedbacks = feedbacks.filter(user=request.user)
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(int(request.query_params.get('page_size', 50)), 200))
        except (TypeError, ValueError):
            return Response({'error': 'page and page_size must be integers'}, status=400)
        total = feedbacks.count()
        start = (page - 1) * page_size
        serializer = FeedbackSerializer(feedbacks[start:start + page_size], many=True)
        return Response({'results': serializer.data, 'count': total, 'page': page, 'page_size': page_size})

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fb = serializer.save(user=request.user)

        # Email notification to admin -- best effort, off the request thread
        # (the feedback itself is already stored).
        _run_in_background(
            send_admin_notification_email,
            f"[FEEDBACK SUBMITTED] {fb.get_category_display()} by {request.user.username}",
            (
                f"A student has submitted feedback on CrackCMS.\n\n"
                f"User: {request.user.username} ({request.user.email})\n"
                f"Category: {fb.get_category_display()}\n"
                f"Rating: {fb.rating}/5\n"
                f"Title: {fb.title}\n"
                f"Message:\n{fb.message}\n"
            ),
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


def _deliver_contact_email(message_id, subject, body) -> bool:
    delivered = send_admin_notification_email(subject, body)
    if delivered and message_id:
        ContactMessage.objects.filter(pk=message_id).update(email_delivered=True)
    return delivered


class ContactUsView(APIView):
    """Contact Us support form (anyone).

    Each message is stored (ContactMessage, visible in Django admin) before
    the admin is emailed, so nothing is lost when email is slow, failing or
    not configured. The request fails only when the message could neither be
    stored nor emailed.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle, ContactHourlyThrottle]
    throttle_scope = 'contact_us'

    MAX_MESSAGE = 5000

    def post(self, request):
        data = request.data if hasattr(request.data, 'get') else {}

        def _text(key, limit):
            value = data.get(key, '')
            return value.strip()[:limit] if isinstance(value, str) else ''

        user = request.user if request.user.is_authenticated else None
        raw_message = data.get('message', '')
        message = raw_message.strip() if isinstance(raw_message, str) else ''
        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)
        if len(message) > self.MAX_MESSAGE:
            return Response({'error': f'Message is too long (max {self.MAX_MESSAGE} characters).'},
                            status=status.HTTP_400_BAD_REQUEST)
        email = _text('email', 254) or ((user.email or '').strip() if user else '')
        if not email:
            return Response({'error': 'Please enter your email address so we can reply.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except ValidationError:
            return Response({'error': 'Please enter a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)
        name = _text('name', 120) or ((user.get_full_name() or user.username) if user else '') or 'Anonymous'
        subject = _text('subject', 200) or 'Contact Form Submission'

        mail_subject = f"[CONTACT FORM] {subject} - from {name}"
        mail_body = (
            f"Contact Form Inquiry on CrackCMS:\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Subject: {subject}\n\n"
            f"Message:\n{message}\n"
        )

        try:
            stored = ContactMessage.objects.create(user=user, name=name, email=email, subject=subject, message=message)
        except Exception:
            logger.exception('Failed to store contact message')
            stored = None

        if stored is not None:
            _run_in_background(_deliver_contact_email, stored.pk, mail_subject, mail_body)
            return Response({
                'message': f"Thanks! We've received your message and will reply to {email}.",
                'stored': True,
            })

        if send_admin_notification_email(mail_subject, mail_body):
            return Response({
                'message': f"Thanks! Your message has been sent to our team. We will reply to {email}.",
                'stored': False,
            })
        return Response(
            {'error': 'We could not send your message right now. Please try again later or email crackwith.ai@gmail.com.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


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
        writer = _FormulaSafeCSVWriter(output)

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


def _campaign_audience(audience_filter):
    """Users an announcement's audience_filter targets."""
    from accounts.models import CustomUser

    audience = audience_filter if isinstance(audience_filter, dict) else {}
    users = CustomUser.objects.all()
    role = audience.get('role')
    if role in ['admin', 'student']:
        users = users.filter(role=role)
    target_year = audience.get('target_year')
    if target_year:
        users = users.filter(target_year=target_year)
    if audience.get('active_only') is True:
        users = users.filter(is_active=True)
    return users


def promote_due_scheduled_announcements(now=None) -> int:
    """Publish scheduled announcements whose time has come.

    Nothing else ever moved a row from 'scheduled' to 'sent', so scheduled
    campaigns never reached students. There is no background scheduler, so
    the feeds call this on read; it is idempotent and cheap when nothing is
    due. Delivery is in-app only (feed + notification bell).
    """
    now = now or timezone.now()
    due = list(
        Announcement.objects.filter(delivery_status='scheduled', scheduled_for__lte=now)
        .values('pk', 'scheduled_for', 'audience_filter')[:50]
    )
    promoted = 0
    for row in due:
        promoted += Announcement.objects.filter(pk=row['pk'], delivery_status='scheduled').update(
            delivery_status='sent',
            sent_at=row['scheduled_for'] or now,
            delivery_count=_campaign_audience(row['audience_filter']).count(),
        )
    return promoted


def _live_announcements(now):
    return Announcement.objects.filter(
        is_active=True,
        delivery_status='sent',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).filter(
        Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now)
    )


def student_announcements(user, now=None):
    """Live announcements whose audience_filter matches ``user``."""
    now = now or timezone.now()
    announcements = _live_announcements(now)
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
    return announcements


class AnnouncementListView(APIView):
    """List active announcements for students, or CRUD for admins."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        promote_due_scheduled_announcements(now)
        user = request.user
        if getattr(user, 'is_admin', False):
            # Admins manage every announcement, including ones targeted at
            # students (the role filter used to hide those from the admin
            # list, so they could not be deleted). ?scope=all adds drafts,
            # scheduled, inactive and expired rows.
            if request.query_params.get('scope') == 'all':
                rows = Announcement.objects.all()
            else:
                rows = _live_announcements(now)
            rows = rows.select_related('created_by').order_by('-created_at')[:200]
            return Response(AnnouncementSerializer(rows, many=True).data)

        announcements = student_announcements(user, now).order_by('-created_at')[:200]
        return Response(StudentAnnouncementSerializer(announcements, many=True).data)

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


# XP values used only to re-derive XP for days before the XPEvent ledger
# existed (see _rebuilt_period_xp): question-bank first answer 15 correct /
# 5 wrong, tests 10 per correct + 5 per completed test, quests xp_reward.
XP_QBANK_CORRECT = 15
XP_QBANK_WRONG = 5
XP_TEST_CORRECT = 10
XP_TEST_COMPLETED = 5

LEADERBOARD_PERIODS = ('weekly', 'monthly', 'all')
LEADERBOARD_TOP_N = 10
_LEADERBOARD_SHARED_TTL = 60


def _leaderboard_period_start(period, now=None):
    """Local midnight starting the current calendar week (Monday) or month;
    None for all time."""
    today = timezone.localdate(now)
    if period == 'weekly':
        day = today - timedelta(days=today.weekday())
    elif period == 'monthly':
        day = today.replace(day=1)
    else:
        return None
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())


def _eligible_learner_q(prefix='user__'):
    """Real learners only: no staff, superusers or deactivated accounts."""
    return Q(**{f'{prefix}is_superuser': False, f'{prefix}is_staff': False, f'{prefix}is_active': True})


def _scoped_by_user(qs, user_ids, eligible_only):
    if user_ids is not None:
        qs = qs.filter(user_id__in=list(user_ids))
    if eligible_only:
        qs = qs.filter(_eligible_learner_q())
    return qs.values('user_id').order_by()


def _xp_ledger_first_day():
    """Local midnight of the first day the XP ledger covers; None when empty."""
    first = cache.get('analytics:xp_ledger_first')
    if first is None:
        first = XPEvent.objects.aggregate(first=Min('created_at'))['first']
        if first is None:
            return None
        try:
            cache.set('analytics:xp_ledger_first', first, 600)
        except Exception:
            pass
    return timezone.make_aware(
        datetime.combine(timezone.localtime(first).date(), time.min), timezone.get_current_timezone())


def _rebuilt_period_xp(start, end, user_ids, eligible_only) -> dict:
    """XP for [start, end) re-derived from dated activity rows -- only for days
    before the XP ledger existed (``end`` = the ledger's first day; None =
    up to now). Uses the award values above, so it is an approximation:
      * question bank -- DailyActivity counts first answers of both the bank
        and tests, so the test answers of the same days are subtracted;
      * tests -- completed TestAttempt rows; quests -- claimed UserQuest rows.
    """
    def _window(qs, field):
        qs = qs.filter(**{f'{field}__gte': start})
        return qs.filter(**{f'{field}__lt': end}) if end is not None else qs

    daily = DailyActivity.objects.filter(date__gte=timezone.localtime(start).date())
    if end is not None:
        daily = daily.filter(date__lt=timezone.localtime(end).date())
    daily = _scoped_by_user(daily, user_ids, eligible_only).annotate(
        answered=Sum('questions_attempted'), correct=Sum('correct_answers'))
    tests = _scoped_by_user(_window(TestAttempt.objects.filter(is_completed=True), 'completed_at'),
                            user_ids, eligible_only).annotate(
        t_correct=Sum('correct_count'), t_incorrect=Sum('incorrect_count'), t_count=Count('id'))
    quests = _scoped_by_user(_window(UserQuest.objects.filter(is_claimed=True), 'completed_at'),
                             user_ids, eligible_only).annotate(quest_xp=Sum('xp_reward'))

    test_rows = {r['user_id']: r for r in tests}
    xp = defaultdict(int)
    for r in daily:
        t = test_rows.get(r['user_id'], {})
        t_correct = t.get('t_correct') or 0
        bank_answered = max(0, (r['answered'] or 0) - t_correct - (t.get('t_incorrect') or 0))
        bank_correct = min(bank_answered, max(0, (r['correct'] or 0) - t_correct))
        xp[r['user_id']] += bank_correct * XP_QBANK_CORRECT + (bank_answered - bank_correct) * XP_QBANK_WRONG
    for user_id, t in test_rows.items():
        xp[user_id] += (t.get('t_correct') or 0) * XP_TEST_CORRECT + (t.get('t_count') or 0) * XP_TEST_COMPLETED
    for r in quests:
        xp[r['user_id']] += int(r['quest_xp'] or 0)
    return xp


def period_xp_by_user(start, user_ids=None, eligible_only=True) -> dict:
    """XP earned since ``start``, per user id.

    From the dated XP ledger (XPEvent, written by StudyStreak.add_xp). Days
    before the ledger existed are re-derived from activity rows, so weekly
    and monthly boards are not blank right after the ledger ships. Capped at
    the all-time total (admin progress resets zero xp_points).
    """
    xp = defaultdict(int)
    ledger = _scoped_by_user(XPEvent.objects.filter(created_at__gte=start), user_ids, eligible_only)
    for row in ledger.annotate(points=Sum('points')):
        xp[row['user_id']] += int(row['points'] or 0)

    ledger_day = _xp_ledger_first_day()
    if ledger_day is None or start < ledger_day:
        for user_id, value in _rebuilt_period_xp(start, ledger_day, user_ids, eligible_only).items():
            xp[user_id] += value

    totals = dict(StudyStreak.objects.filter(user_id__in=list(xp)).values_list('user_id', 'xp_points'))
    capped = {user_id: min(value, int(totals.get(user_id, value) or 0)) for user_id, value in xp.items()}
    return {user_id: value for user_id, value in capped.items() if value > 0}


def _period_standings(period, start) -> list:
    """[(user_id, xp)] best first for the period; shared by every viewer."""
    key = f'analytics:leaderboard:standings:{period}:{start.date().isoformat()}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    standings = sorted(period_xp_by_user(start).items(), key=lambda item: (-item[1], item[0]))
    try:
        cache.set(key, standings, _LEADERBOARD_SHARED_TTL)
    except Exception:
        pass
    return standings


def _ranked_learner_count() -> int:
    """Learners with any XP (all time); shared by every viewer."""
    key = 'analytics:leaderboard:ranked_count'
    cached = cache.get(key)
    if cached is not None:
        return cached
    count = StudyStreak.objects.filter(_eligible_learner_q(), xp_points__gt=0).count()
    try:
        cache.set(key, count, _LEADERBOARD_SHARED_TTL)
    except Exception:
        pass
    return count


def _public_name(user) -> str:
    """The name other learners see: the username the product already shows
    in discussions -- never first/last name or email."""
    name = (getattr(user, 'username', '') or '').strip()
    if '@' in name:
        name = name.split('@')[0]
    return name or 'Learner'


class LeaderboardView(APIView):
    """
    Personal-stats leaderboard.

    Returns a personal envelope (`me`, `rival`, optional `live_board`), never
    fabricated users or numbers:

    * ``period`` (weekly = this calendar week, monthly = this calendar month,
      all) ranks learners by the XP they earned in that period, from the
      dated XP ledger (see ``period_xp_by_user``); ``all`` uses the all-time
      StudyStreak total.
    * Accuracy is null when a learner has not completed a test.
    * Other learners appear only by username (no real names, no college).
    * The rival is the top real learner of the period other than the viewer.
      When the active user-base crosses ``settings.LEADERBOARD_LIVE_THRESHOLD``
      a top-10 slab is appended; below it no global rows are exposed.
    * The shared work (standings, counts) is cached once for all viewers;
      per viewer only a handful of indexed queries run.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.conf import settings as dj_settings
        from django.contrib.auth import get_user_model

        user = request.user
        period = request.query_params.get('period', 'weekly')
        if period not in LEADERBOARD_PERIODS:
            period = 'weekly'

        # Per-user envelope cache — the page is read-mostly; 60s keeps it
        # snappy without serving stale data for long.
        cache_key = f"analytics:leaderboard:personal:{user.id}:{period}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        me_streak, _ = StudyStreak.objects.get_or_create(user=user)
        me_total_xp = int(me_streak.xp_points or 0)
        me_eligible = not (user.is_superuser or user.is_staff) and user.is_active
        week_start = _leaderboard_period_start('weekly')
        me_weekly_xp = period_xp_by_user(week_start, user_ids=[user.id], eligible_only=False).get(user.id, 0)

        if period == 'all':
            ranked = StudyStreak.objects.filter(_eligible_learner_q(), xp_points__gt=0)
            out_of = _ranked_learner_count()
            me_period_xp = me_total_xp
            me_rank = (ranked.filter(xp_points__gt=me_total_xp).count() + 1) if (me_eligible and me_total_xp > 0) else None
            top = list(
                ranked.order_by('-xp_points', '-current_streak', 'user_id')
                .values_list('user_id', 'xp_points')[:LEADERBOARD_TOP_N + 1]
            )
        else:
            start = _leaderboard_period_start(period)
            standings = _period_standings(period, start)
            out_of = len(standings)
            me_period_xp = me_weekly_xp if period == 'weekly' else (
                period_xp_by_user(start, user_ids=[user.id], eligible_only=False).get(user.id, 0))
            me_rank = (sum(1 for _, xp in standings if xp > me_period_xp) + 1) if (me_eligible and me_period_xp > 0) else None
            top = standings[:LEADERBOARD_TOP_N + 1]
        # The shared standings/counts may be up to a minute old; never show
        # "#3 of 2" to someone who just earned their first XP.
        out_of = max(out_of, me_rank or 0)

        # Details only for the handful of learners shown (+ me).
        shown_ids = {user_id for user_id, _ in top} | {user.id}
        users = {u.pk: u for u in get_user_model().objects.filter(pk__in=shown_ids).only('id', 'username')}
        streaks = {s.user_id: s for s in StudyStreak.objects.filter(user_id__in=shown_ids)}
        accuracy_rows = {
            r['user_id']: r for r in (
                TestAttempt.objects.filter(user_id__in=shown_ids, is_completed=True)
                .values('user_id').order_by()
                .annotate(total_correct=Sum('correct_count'), total_incorrect=Sum('incorrect_count'), tests_done=Count('id'))
            )
        }

        def _accuracy_for(user_id):
            agg = accuracy_rows.get(user_id) or {}
            correct = agg.get('total_correct') or 0
            answered = correct + (agg.get('total_incorrect') or 0)
            return round(correct / answered * 100, 1) if answered > 0 else None

        def _streak_for(user_id):
            s = streaks.get(user_id)
            return int(s.current_streak or 0) if s else 0

        me_payload = {
            'user_id': user.id,
            'username': (
                f"{user.first_name} {user.last_name}".strip()
                or user.username
                or (user.email or '').split('@')[0]
            ),
            'rank': me_rank,
            'out_of': out_of,
            'xp_points': me_total_xp,
            'period_xp': me_period_xp,
            'current_streak': int(me_streak.current_streak or 0),
            'longest_streak': int(me_streak.longest_streak or me_streak.current_streak or 0),
            'total_study_days': int(me_streak.total_study_days or 0),
            'accuracy': _accuracy_for(user.id),
            'tests_completed': int((accuracy_rows.get(user.id) or {}).get('tests_done') or 0),
            'weekly_xp': me_weekly_xp,
            'weekly_goal_xp': 500,
        }
        # College: only the viewer's own, only if they actually set one.
        college = (getattr(user, 'college', '') or '').strip()
        if college and len(college) >= 3 and college.lower() != 'none':
            me_payload['college'] = college

        def _row(user_id, xp):
            return {
                'user_id': user_id,
                'username': _public_name(users.get(user_id)),
                'xp_points': int(xp),
                'current_streak': _streak_for(user_id),
                'accuracy': _accuracy_for(user_id),
            }

        # ── `rival`: top real learner of the period, excluding me ─────────
        rival = None
        candidate = next(((uid, xp) for uid, xp in top if uid != user.id), None)
        if candidate is not None:
            rival = _row(*candidate)
            xp_to_surpass = max(0, rival['xp_points'] - me_period_xp + 1)
            # Assumption: ~10 XP per solved question (median of the award values above).
            rival['xp_to_surpass'] = xp_to_surpass
            rival['questions_to_surpass'] = int(math.ceil(xp_to_surpass / 10)) if xp_to_surpass > 0 else 0

        # ── Live-board gating ───────────────────────────────────────────
        threshold = int(getattr(dj_settings, 'LEADERBOARD_LIVE_THRESHOLD', 50))
        live_board_enabled = _ranked_learner_count() >= threshold
        live_board = None
        if live_board_enabled:
            live_board = [
                {'rank': idx, **_row(uid, xp)}
                for idx, (uid, xp) in enumerate(top[:LEADERBOARD_TOP_N], 1)
            ]

        # ── Invite (no DB writes — purely UI surface) ───────────────────
        # FRONTEND_URL in some envs is a comma-separated list (CORS-style);
        # take the first valid http(s) origin so the URL is well-formed.
        frontend_origin = ''
        raw = (getattr(dj_settings, 'FRONTEND_URL', '') or '').strip()
        for origin in raw.split(','):
            origin = origin.strip().rstrip('/')
            if origin.startswith('http://') or origin.startswith('https://'):
                frontend_origin = origin
                break
        # /register is the real signup route (/signup 404s). There is no
        # referral tracking yet, so nothing is promised for inviting.
        invite_path = f"/register?ref={user.id}"
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
                'cta': 'Invite friends to study with you',
            },
        }

        try:
            cache.set(cache_key, envelope, 60)
        except Exception:
            # Cache must never break the API; swallow and serve fresh.
            pass

        return Response(envelope)


class AdminDashboardView(APIView):
    """Admin overview: user stats, question quality, AI usage."""
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        from accounts.models import CustomUser, TokenBalance, TokenTransaction, PaymentAttempt
        from questions.models import Question
        from django.db.models import Sum

        total_users = CustomUser.objects.count()
        active_today = DailyActivity.objects.filter(date=timezone.localdate()).count()
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

        # Topic rankings use topic rows only; the subject-level rows
        # (topic=NULL) showed up as a "None" topic bucket.
        topic_rows = UserTopicPerformance.objects.filter(topic__isnull=False)

        difficult_topics = list(
            topic_rows
            .values('topic_id', 'topic__name', 'subject__name')
            .annotate(avg_accuracy=Avg((F('correct_answers') * 100.0) / (F('total_attempts') + 0.0001)), attempts=Sum('total_attempts'))
            .order_by('avg_accuracy', '-attempts')[:10]
        )

        cohort_weak_areas = list(
            topic_rows
            .values('topic_id', 'topic__name', 'subject__name')
            .annotate(total_attempts=Sum('total_attempts'), total_correct=Sum('correct_answers'))
            .annotate(accuracy=(F('total_correct') * 100.0) / (F('total_attempts') + 0.0001))
            .order_by('accuracy', '-total_attempts')[:15]
        )

        student_weak_areas = []
        if user_id:
            student_weak_areas = list(
                topic_rows.filter(user_id=user_id)
                .values('topic_id', 'topic__name', 'subject__name', 'total_attempts', 'correct_answers')
                .annotate(accuracy=(F('correct_answers') * 100.0) / (F('total_attempts') + 0.0001))
                .order_by('accuracy', '-total_attempts')[:15]
            )

        impact_priorities = list(
            Question.objects
            .annotate(
                # distinct: the feedback and response joins multiply rows, so
                # without it reports came out as reports x responses.
                reports=Count('feedbacks', filter=Q(feedbacks__is_resolved=False), distinct=True),
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


# ════════════════════════════════════════════════════════════════════════════
# Student Experience — Study Analytics & Gamification Views
# ════════════════════════════════════════════════════════════════════════════

# DashboardV3View / DashboardBundleView used to be duplicated here; the
# routes point at dashboard_v3.py and views_bundle.py, so these copies were
# unreachable (and the bundle copy crashed on TestAttempt.total_questions).


def _notebook_queryset(user):
    """The user's Mistake Notebook rows, annotated with whether the answer key
    may be shown (see MistakeNotebookSerializer.to_representation): premium /
    admin users, free showcase questions, or questions the user actually
    answered (question bank, or a completed test)."""
    from accounts.models_freemium import FreeShowcaseQuestion
    from accounts.utils import is_premium
    from questions.models import QuestionAttempt
    from tests_engine.models import QuestionResponse

    qs = MistakeNotebook.objects.filter(user=user).select_related('question__subject', 'question__topic')
    if is_premium(user):
        return qs.annotate(answer_visible=Value(True, output_field=BooleanField()))
    return qs.annotate(
        answered_in_bank=Exists(QuestionAttempt.objects.filter(user=user, question_id=OuterRef('question_id'))),
        answered_in_test=Exists(QuestionResponse.objects.filter(
            attempt__user=user, attempt__is_completed=True, question_id=OuterRef('question_id'))),
        is_showcase=Exists(FreeShowcaseQuestion.objects.filter(question_id=OuterRef('question_id'))),
    )


class MistakeNotebookView(APIView):
    """Get user's mistake notebook entries with optional filters."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = _notebook_queryset(request.user)
        # Filters
        review_status = request.query_params.get('review_status')
        is_flagged = request.query_params.get('is_flagged')
        subject_id = request.query_params.get('subject')
        topic_id = request.query_params.get('topic')

        if review_status:
            qs = qs.filter(review_status=review_status)
        if is_flagged is not None:
            qs = qs.filter(is_flagged=is_flagged == 'true')
        if subject_id:
            qs = qs.filter(question__subject_id=subject_id)
        if topic_id:
            qs = qs.filter(question__topic_id=topic_id)

        qs = qs.order_by('-created_at')
        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(int(request.query_params.get('page_size', 20)), 100))
        except (TypeError, ValueError):
            return Response({'error': 'page and page_size must be integers'}, status=400)
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start:start + page_size]

        serializer = MistakeNotebookSerializer(items, many=True)
        return Response({
            'results': serializer.data,
            'count': total,
            'page': page,
            'page_size': page_size,
        })

    def post(self, request):
        """Add a question you answered incorrectly.

        The notebook fills itself from wrong answers (questions/mistakes.py);
        this endpoint only (re-)adds a question the user really got wrong --
        in the question bank or in a completed test -- and sets the note /
        flag. It used to accept any question id and return its answer and
        explanation, bypassing the premium question gate.
        """
        from questions.mistakes import record_mistake
        from questions.models import QuestionAttempt
        from tests_engine.models import QuestionResponse

        user = request.user
        try:
            question_id = int(request.data.get('question'))
        except (TypeError, ValueError):
            return Response({'error': 'question is required'}, status=status.HTTP_400_BAD_REQUEST)
        questions = Question.objects.all() if getattr(user, 'is_admin', False) else Question.objects.filter(is_active=True)
        question = questions.filter(pk=question_id).first()
        if question is None:
            return Response({'error': 'Question not found'}, status=404)

        entry = MistakeNotebook.objects.filter(user=user, question=question).first()
        created = False
        if entry is None:
            bank_attempt = QuestionAttempt.objects.filter(user=user, question=question, is_correct=False).first()
            if bank_attempt is not None:
                entry = record_mistake(user, question, bank_attempt.selected_answer, attempt=bank_attempt)
            else:
                wrong_in_test = (
                    QuestionResponse.objects.filter(
                        attempt__user=user, attempt__is_completed=True, question=question, is_correct=False,
                    ).order_by('-attempt__completed_at').values_list('selected_answer', flat=True).first()
                )
                if wrong_in_test is None:
                    return Response(
                        {'error': 'Only questions you have answered incorrectly can be added to your Mistake Notebook.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                entry = record_mistake(user, question, wrong_in_test)
            # record_mistake returns None if a concurrent request created it.
            entry = entry or MistakeNotebook.objects.filter(user=user, question=question).first()
            if entry is None:
                return Response({'error': 'Could not add this question. Please try again.'}, status=500)
            created = True

        # The note and the flag are the only fields a student controls.
        changes = {key: request.data[key] for key in ('user_note', 'is_flagged') if key in request.data}
        if changes:
            serializer = MistakeNotebookSerializer(entry, data=changes, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        entry = _notebook_queryset(user).get(pk=entry.pk)
        return Response(MistakeNotebookSerializer(entry).data, status=status.HTTP_201_CREATED if created else 200)


class MistakeNotebookDetailView(APIView):
    """Update/delete a mistake notebook entry (PATCH: user_note / is_flagged only)."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_object(self, request, pk):
        try:
            return _notebook_queryset(request.user).get(pk=pk)
        except MistakeNotebook.DoesNotExist:
            raise Http404

    def patch(self, request, pk):
        obj = self._get_object(request, pk)
        serializer = MistakeNotebookSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = self._get_object(request, pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MistakeNotebookReviewView(APIView):
    """Mark a mistake as reviewed (spaced-repetition scheduler)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            obj = _notebook_queryset(request.user).get(pk=pk)
        except MistakeNotebook.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        from django.utils import timezone as tz
        now = tz.now()
        obj.review_count += 1
        obj.last_reviewed_at = now
        # Spaced repetition: increase interval based on review count
        if obj.review_count == 1:
            obj.next_review_at = now + timezone.timedelta(days=1)
            obj.review_status = 'learning'
        elif obj.review_count == 2:
            obj.next_review_at = now + timezone.timedelta(days=3)
            obj.review_status = 'reviewing'
        elif obj.review_count >= 3:
            obj.next_review_at = now + timezone.timedelta(days=7)
            if obj.review_count >= 5:
                obj.review_status = 'mastered'
        obj.save(update_fields=['review_count', 'last_reviewed_at', 'next_review_at', 'review_status'])
        serializer = MistakeNotebookSerializer(obj)
        return Response(serializer.data)


class MistakeNotebookDueView(APIView):
    """Get all mistakes due for review today."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        due = _notebook_queryset(request.user).filter(
            next_review_at__lte=now,
        ).exclude(review_status='mastered').order_by('next_review_at')
        serializer = MistakeNotebookSerializer(due, many=True)
        return Response({
            'results': serializer.data,
            'count': due.count(),
        })


class UserQuestListView(APIView):
    """List the user's quests. Today's daily quests are generated on demand
    and their progress is computed from real activity (server-side)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from questions.quest_service import ensure_daily_quests, refresh_progress

        ensure_daily_quests(request.user)
        quests = UserQuest.objects.filter(user=request.user)
        status_filter = request.query_params.get('status')
        if status_filter == 'active':
            quests = quests.filter(is_completed=False, expires_at__gt=timezone.now())
        elif status_filter == 'completed':
            quests = quests.filter(is_completed=True)
        elif status_filter == 'expired':
            quests = quests.filter(expires_at__lt=timezone.now(), is_completed=False)
        quests = list(quests.order_by('-quest_date', 'quest_type')[:20])
        refresh_progress(request.user, quests)
        serializer = UserQuestSerializer(quests, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a custom quest for a user (admin only)."""
        if not getattr(request.user, 'is_admin', False):
            return Response({'error': 'Admin only'}, status=403)
        serializer = UserQuestAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=serializer.validated_data.get('user') or request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserQuestDetailView(APIView):
    """Read or claim a quest. PATCH ``{"is_completed": true}`` claims it --
    the server checks progress and awards the server-defined XP once."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_object(self, request, pk):
        try:
            return UserQuest.objects.get(pk=pk, user=request.user)
        except UserQuest.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        from questions.quest_service import refresh_progress
        obj = self._get_object(request, pk)
        refresh_progress(request.user, [obj])
        return Response(UserQuestSerializer(obj).data)

    def patch(self, request, pk):
        from questions.quest_service import QuestClaimError, claim_quest

        raw = request.data.get('is_completed')
        wants_claim = raw is True or str(raw).strip().lower() in ('1', 'true', 'yes')
        if not wants_claim:
            return Response({'error': 'Only claiming a finished quest is supported.'}, status=400)
        # A freeze bridges one missed day only; drop a stale one before the
        # claim so it cannot carry the streak over a longer gap.
        expire_stale_quest_freeze(request.user)
        try:
            quest = claim_quest(request.user, pk)
        except QuestClaimError as exc:
            return Response({'error': exc.message}, status=exc.status)
        return Response(UserQuestSerializer(quest).data)

    def post(self, request, pk):
        """Alias: ``POST .../<pk>/`` with no body also claims."""
        return self.patch(request, pk)

    def delete(self, request, pk):
        # Deleting a claimed daily quest would let it be regenerated and
        # claimed again for more XP, so only admins may delete.
        if not getattr(request.user, 'is_admin', False):
            return Response({'error': 'Admin only'}, status=403)
        try:
            obj = UserQuest.objects.get(pk=pk)
        except UserQuest.DoesNotExist:
            raise Http404
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


QUEST_FREEZE_EVENT = 'quest_streak_freeze_used'  # server-written AnalyticsEvent ledger
QUEST_FREEZE_COOLDOWN_DAYS = 7


def _parse_bool(value) -> bool:
    """Strict boolean parsing (bool('false') is True)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ('true', '1', 'yes', 'on'):
            return True
        if text in ('false', '0', 'no', 'off'):
            return False
    raise ValueError(value)


def expire_stale_quest_freeze(user) -> None:
    """A freeze protects a single missed day. Once the last claim is older
    than the day before yesterday the streak is broken, so the freeze lapses
    instead of bridging a gap of any length."""
    today = timezone.localdate()
    QuestStreak.objects.filter(
        user=user, streak_frozen=True, last_quest_date__lt=today - timedelta(days=2),
    ).update(streak_frozen=False)


class QuestStreakView(APIView):
    """Get/update quest streak info."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        expire_stale_quest_freeze(request.user)
        streak, _ = QuestStreak.objects.get_or_create(user=request.user)
        serializer = QuestStreakSerializer(streak)
        return Response(serializer.data)


class QuestStreakFreezeView(APIView):
    """Turn the streak freeze on or off.

    Body ``{"streak_frozen": true|false}``; no body toggles. A freeze can be
    switched on only while the streak is alive (a quest claimed today or
    yesterday) and at most once every QUEST_FREEZE_COOLDOWN_DAYS days; it
    then covers one missed day.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        expire_stale_quest_freeze(user)
        streak, _ = QuestStreak.objects.get_or_create(user=user)
        raw = request.data.get('streak_frozen') if hasattr(request.data, 'get') else None
        if raw is None:
            freeze = not streak.streak_frozen
        else:
            try:
                freeze = _parse_bool(raw)
            except ValueError:
                return Response({'error': 'streak_frozen must be true or false.'}, status=400)

        if freeze and not streak.streak_frozen:
            today = timezone.localdate()
            if (not streak.last_quest_date or streak.current_streak <= 0
                    or streak.last_quest_date < today - timedelta(days=1)):
                return Response({'error': 'You need an active quest streak to freeze. Claim a quest first.'},
                                status=400)
            since = timezone.now() - timedelta(days=QUEST_FREEZE_COOLDOWN_DAYS)
            if AnalyticsEvent.objects.filter(
                event_name=QUEST_FREEZE_EVENT, user_id=user.id, created_at__gte=since,
            ).exists():
                return Response({'error': f'You can use one streak freeze every {QUEST_FREEZE_COOLDOWN_DAYS} days.'},
                                status=400)
            AnalyticsEvent.objects.create(
                event_name=QUEST_FREEZE_EVENT, user_id=user.id,
                properties={'current_streak': streak.current_streak},
            )

        if freeze != streak.streak_frozen:
            streak.streak_frozen = freeze
            streak.save(update_fields=['streak_frozen', 'updated_at'])
        serializer = QuestStreakSerializer(streak)
        return Response(serializer.data)


class StudyTimeView(APIView):
    """Record and retrieve study time per subject."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = StudyTimeBreakdown.objects.filter(user=request.user)
        # Date range filter
        start = request.query_params.get('start')
        end = request.query_params.get('end')
        if start:
            qs = qs.filter(date__gte=start)
        if end:
            qs = qs.filter(date__lte=end)

        serializer = StudyTimeBreakdownSerializer(qs, many=True)
        # Aggregate totals
        totals = qs.values('subject').annotate(
            total_seconds=Sum('seconds'),
            total_questions=Sum('question_count'),
        )
        return Response({
            'breakdown': serializer.data,
            'totals': list(totals),
        })

    def post(self, request):
        subject_id = request.data.get('subject')
        try:
            seconds = max(0, min(int(request.data.get('seconds', 0)), 24 * 3600))
            question_count = max(0, min(int(request.data.get('question_count', 0)), 1000))
        except (TypeError, ValueError):
            return Response({'error': 'seconds and question_count must be integers'}, status=400)
        import datetime as _dt
        raw_date = request.data.get('date')
        try:
            date_str = _dt.date.fromisoformat(str(raw_date)) if raw_date else timezone.localdate()
        except ValueError:
            return Response({'error': 'date must be in YYYY-MM-DD format'}, status=400)
        if date_str > timezone.localdate():
            return Response({'error': 'date cannot be in the future'}, status=400)

        from questions.models import Subject
        try:
            subject = Subject.objects.get(pk=int(subject_id))
        except (Subject.DoesNotExist, TypeError, ValueError):
            return Response({'error': 'Subject not found'}, status=404)

        obj, _ = StudyTimeBreakdown.objects.get_or_create(
            user=request.user, subject=subject, date=date_str,
            defaults={'seconds': 0, 'question_count': 0},
        )
        # Atomic increments (two tabs posting at once used to lose time).
        StudyTimeBreakdown.objects.filter(pk=obj.pk).update(
            seconds=F('seconds') + seconds,
            question_count=F('question_count') + question_count,
        )
        obj.refresh_from_db(fields=['seconds', 'question_count'])
        serializer = StudyTimeBreakdownSerializer(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MistakeStatsView(APIView):
    """Aggregate stats for the mistake notebook dashboard widget."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        total = MistakeNotebook.objects.filter(user=user).count()
        by_status = {}
        for key, _ in MistakeNotebook.REVIEW_STATUS_CHOICES:
            by_status[key] = MistakeNotebook.objects.filter(user=user, review_status=key).count()
        flagged = MistakeNotebook.objects.filter(user=user, is_flagged=True).count()
        due_today = MistakeNotebook.objects.filter(
            user=user, next_review_at__lte=timezone.now()
        ).exclude(review_status='mastered').count()
        return Response({
            'total': total,
            'by_status': by_status,
            'flagged': flagged,
            'due_today': due_today,
        })


class AdminCampaignListCreateView(APIView):
    """Phase 8: segmented campaign create/list with scheduling metadata."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def get(self, request):
        promote_due_scheduled_announcements()
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
    """Publish a campaign now (in-app: dashboard feed + notification bell;
    nothing is emailed or pushed) and record its target audience size."""

    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'admin_control_tower'

    def post(self, request, pk):
        try:
            campaign = Announcement.objects.get(pk=pk)
        except Announcement.DoesNotExist:
            return Response({'error': 'Campaign not found'}, status=status.HTTP_404_NOT_FOUND)

        users = _campaign_audience(campaign.audience_filter)

        campaign.sent_at = timezone.now()
        campaign.delivery_status = 'sent'
        campaign.is_active = True
        campaign.delivery_count = users.count()
        campaign.failure_report = ''
        campaign.save(update_fields=['sent_at', 'delivery_status', 'is_active', 'delivery_count', 'failure_report'])

        return Response(AnnouncementSerializer(campaign).data)

