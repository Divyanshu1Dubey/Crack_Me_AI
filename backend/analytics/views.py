import csv
from io import StringIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.http import HttpResponse
from django.db.models import Sum, Avg, Count, F, Q
from .models import UserTopicPerformance, DailyActivity, Feedback
from .serializers import TopicPerformanceSerializer, DailyActivitySerializer, FeedbackSerializer
from tests_engine.models import TestAttempt
from questions.models import Subject


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
    permission_classes = [permissions.IsAdminUser]

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
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'trace': traceback.format_exc()}, status=500)

        return Response(data)


class DataExportCSVView(APIView):
    """Download data as CSV file (admin only). ?type=users|tokens|transactions|feedback"""
    permission_classes = [permissions.IsAdminUser]

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

