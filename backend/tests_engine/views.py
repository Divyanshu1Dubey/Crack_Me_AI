from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
import random

from .models import Test, TestAttempt, QuestionResponse
from .serializers import (
    TestSerializer, TestDetailSerializer,
    TestAttemptSerializer, TestAttemptDetailSerializer,
    SubmitAnswerSerializer
)
from questions.models import Question, Subject, Topic


class TestViewSet(viewsets.ModelViewSet):
    """Test CRUD with start, submit, and result actions."""
    queryset = Test.objects.filter(is_published=True)
    filterset_fields = ['test_type', 'subject', 'topic']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestDetailSerializer
        return TestSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='generate')
    def generate_test(self, request):
        """Generate a test dynamically based on parameters."""
        test_type = request.data.get('test_type', 'mixed')
        subject_id = request.data.get('subject_id')
        topic_id = request.data.get('topic_id')
        num_questions = int(request.data.get('num_questions', 20))
        year = request.data.get('year')

        # Build query
        q_filter = Q(is_active=True)
        title_parts = []

        if test_type == 'subject' and subject_id:
            q_filter &= Q(subject_id=subject_id)
            subject = Subject.objects.get(id=subject_id)
            title_parts.append(subject.name)
        elif test_type == 'topic' and topic_id:
            q_filter &= Q(topic_id=topic_id)
            topic = Topic.objects.get(id=topic_id)
            title_parts.append(topic.name)
        elif test_type == 'pyq_year' and year:
            q_filter &= Q(year=year)
            title_parts.append(f"PYQ {year}")
        elif test_type == 'paper1':
            q_filter &= Q(subject__paper=1)
            title_parts.append("Paper 1 Mock")
            num_questions = 120
        elif test_type == 'paper2':
            q_filter &= Q(subject__paper=2)
            title_parts.append("Paper 2 Mock")
            num_questions = 120

        questions = list(Question.objects.filter(q_filter).values_list('id', flat=True))
        if len(questions) > num_questions:
            questions = random.sample(questions, num_questions)

        title = ' | '.join(title_parts) if title_parts else 'Practice Test'
        title = f"{title} — {len(questions)} Questions"

        time_limit = max(len(questions) * 1.5, 10)  # 1.5 min per question

        test = Test.objects.create(
            title=title,
            test_type=test_type,
            subject_id=subject_id,
            topic_id=topic_id,
            num_questions=len(questions),
            time_limit_minutes=int(time_limit),
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='start')
    def start_attempt(self, request, pk=None):
        """Start a test attempt."""
        test = self.get_object()
        attempt = TestAttempt.objects.create(user=request.user, test=test)
        questions = test.questions.all().order_by('?')  # Randomize order
        from questions.serializers import QuestionListSerializer
        return Response({
            'attempt_id': attempt.id,
            'test': TestSerializer(test, context={'request': request}).data,
            'questions': QuestionListSerializer(questions, many=True, context={'request': request}).data,
            'started_at': attempt.started_at,
        })

    @action(detail=True, methods=['post'], url_path='submit')
    def submit_attempt(self, request, pk=None):
        """Submit answers for a test attempt."""
        test = self.get_object()
        attempt_id = request.data.get('attempt_id')

        try:
            attempt = TestAttempt.objects.get(id=attempt_id, user=request.user, test=test)
        except TestAttempt.DoesNotExist:
            return Response({'error': 'Invalid attempt'}, status=status.HTTP_400_BAD_REQUEST)

        if attempt.is_completed:
            return Response({'error': 'Test already submitted'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        correct = 0
        incorrect = 0
        unanswered = 0

        for ans_data in serializer.validated_data['answers']:
            question_id = ans_data.get('question_id')
            selected = ans_data.get('selected_answer', '')
            time_taken = ans_data.get('time_taken_seconds')
            confidence = ans_data.get('confidence_level')

            try:
                question = Question.objects.get(id=question_id)
            except Question.DoesNotExist:
                continue

            is_correct = None
            if selected:
                is_correct = (selected.upper() == question.correct_answer)
                if is_correct:
                    correct += 1
                else:
                    incorrect += 1
            else:
                unanswered += 1

            QuestionResponse.objects.create(
                attempt=attempt,
                question=question,
                selected_answer=selected.upper() if selected else None,
                is_correct=is_correct,
                time_taken_seconds=time_taken,
                confidence_level=confidence,
            )

        # Calculate score
        score = correct - (incorrect * test.negative_mark_value if test.negative_marking else 0)
        total_marks = correct + incorrect + unanswered

        attempt.score = score
        attempt.total_marks = total_marks
        attempt.correct_count = correct
        attempt.incorrect_count = incorrect
        attempt.unanswered_count = unanswered
        attempt.is_completed = True
        attempt.completed_at = timezone.now()
        attempt.time_taken_seconds = (attempt.completed_at - attempt.started_at).total_seconds()
        attempt.save()

        # Update Analytics Dashboard
        from analytics.models import UserTopicPerformance, DailyActivity, StudyStreak
        from django.db.models import F

        # 1. Update Daily Activity
        today = timezone.now().date()
        daily, _ = DailyActivity.objects.get_or_create(user=request.user, date=today)
        daily.questions_attempted += (correct + incorrect)
        daily.correct_answers += correct
        daily.tests_completed += 1
        daily.time_spent_minutes += max(1, int(attempt.time_taken_seconds / 60))
        daily.save()

        # 2. Update Study Streak and XP
        streak, _ = StudyStreak.objects.get_or_create(user=request.user)
        streak.record_activity()  # Updates streak count
        # Award XP: 10 per correct answer, 5 bonus for completing test
        xp_earned = (correct * 10) + 5
        streak.add_xp(xp_earned)

        # 3. Update Subject-wise Performance
        subject_counts = {}
        topic_counts = {}
        for ans_data in serializer.validated_data['answers']:
            question_id = ans_data.get('question_id')
            selected = ans_data.get('selected_answer', '')
            if not selected:
                continue
                
            try:
                question = Question.objects.get(id=question_id)
            except Question.DoesNotExist:
                continue
                
            is_correct = (selected.upper() == question.correct_answer)
            subj = question.subject
            topic = question.topic
            
            if subj:
                if subj.id not in subject_counts:
                    subject_counts[subj.id] = {'total': 0, 'correct': 0, 'incorrect': 0, 'subject': subj}
                subject_counts[subj.id]['total'] += 1
                if is_correct:
                    subject_counts[subj.id]['correct'] += 1
                else:
                    subject_counts[subj.id]['incorrect'] += 1
                    
            if topic:
                if topic.id not in topic_counts:
                    topic_counts[topic.id] = {'total': 0, 'correct': 0, 'incorrect': 0, 'topic': topic, 'subject': subj}
                topic_counts[topic.id]['total'] += 1
                if is_correct:
                    topic_counts[topic.id]['correct'] += 1
                else:
                    topic_counts[topic.id]['incorrect'] += 1

        now = timezone.now()
        for subj_id, data in subject_counts.items():
            # Update general subject performance (where topic is null)
            perf, _ = UserTopicPerformance.objects.get_or_create(
                user=request.user, subject=data['subject'], topic=None
            )
            perf.total_attempts += data['total']
            perf.correct_answers += data['correct']
            perf.incorrect_answers += data['incorrect']
            perf.last_attempted = now
            perf.save()

        # 4. Update Topic-level performance
        for topic_id, data in topic_counts.items():
            perf, _ = UserTopicPerformance.objects.get_or_create(
                user=request.user, subject=data['subject'], topic=data['topic']
            )
            perf.total_attempts += data['total']
            perf.correct_answers += data['correct']
            perf.incorrect_answers += data['incorrect']
            perf.last_attempted = now
            perf.save()
            
        return Response(TestAttemptDetailSerializer(attempt, context={'request': request}).data)


    @action(detail=True, methods=['get'], url_path='review')
    def review(self, request, pk=None):
        """Detailed post-test review with per-question analysis."""
        test = self.get_object()
        attempt_id = request.query_params.get('attempt_id')

        try:
            attempt = TestAttempt.objects.get(
                id=attempt_id, user=request.user, test=test, is_completed=True
            )
        except TestAttempt.DoesNotExist:
            return Response({'error': 'No completed attempt found'}, status=400)

        responses = QuestionResponse.objects.filter(attempt=attempt).select_related('question', 'question__subject', 'question__topic')

        questions_review = []
        subject_breakdown = {}

        for resp in responses:
            q = resp.question
            subj = q.subject.name if q.subject else 'Unknown'

            if subj not in subject_breakdown:
                subject_breakdown[subj] = {'correct': 0, 'incorrect': 0, 'unanswered': 0}

            if resp.is_correct:
                subject_breakdown[subj]['correct'] += 1
            elif resp.is_correct is False:
                subject_breakdown[subj]['incorrect'] += 1
            else:
                subject_breakdown[subj]['unanswered'] += 1

            questions_review.append({
                'question_id': q.id,
                'question_text': q.question_text,
                'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
                'correct_answer': q.correct_answer,
                'selected_answer': resp.selected_answer,
                'is_correct': resp.is_correct,
                'explanation': q.explanation or q.ai_explanation or '',
                'mnemonic': q.mnemonic or '',
                'subject': subj,
                'topic': q.topic.name if q.topic else '',
                'difficulty': q.difficulty,
                'book_reference': q.book_name,
                'chapter': q.chapter or '',
                'page_number': q.page_number or '',
                'year': q.year,
                'paper': q.paper,
                'times_asked': q.times_asked,
                'concept_explanation': q.concept_explanation or '',
                'textbook_references': q.textbook_references or [],
                'time_taken': resp.time_taken_seconds,
                'confidence': resp.confidence_level,
                'concept_tags': q.concept_tags or [],
            })

        return Response({
            'attempt_id': attempt.id,
            'score': attempt.score,
            'accuracy': attempt.accuracy,
            'total_time': attempt.time_taken_seconds,
            'correct': attempt.correct_count,
            'incorrect': attempt.incorrect_count,
            'unanswered': attempt.unanswered_count,
            'subject_breakdown': subject_breakdown,
            'questions': questions_review,
        })

    @action(detail=False, methods=['post'], url_path='generate-adaptive')
    def generate_adaptive(self, request):
        """Generate an AI adaptive test that focuses on weak areas."""
        num_questions = int(request.data.get('num_questions', 30))

        # Find weak topics from user's attempt history
        from analytics.models import UserTopicPerformance
        weak_perfs = UserTopicPerformance.objects.filter(
            user=request.user,
            total_attempts__gte=2
        ).order_by('correct_answers')[:10]

        q_filter = Q(is_active=True)
        if weak_perfs.exists():
            weak_topic_ids = [p.topic_id for p in weak_perfs if p.topic_id]
            weak_subject_ids = [p.subject_id for p in weak_perfs if p.subject_id]
            q_filter &= (Q(topic_id__in=weak_topic_ids) | Q(subject_id__in=weak_subject_ids))

        questions = list(Question.objects.filter(q_filter).values_list('id', flat=True))
        if len(questions) < num_questions:
            extra = list(
                Question.objects.filter(is_active=True)
                .exclude(id__in=questions)
                .values_list('id', flat=True)
            )
            questions.extend(extra[:num_questions - len(questions)])

        if len(questions) > num_questions:
            questions = random.sample(questions, num_questions)

        test = Test.objects.create(
            title=f"AI Adaptive Test — {len(questions)} Questions",
            test_type='adaptive',
            num_questions=len(questions),
            time_limit_minutes=int(len(questions) * 1.5),
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='pyq-simulation')
    def pyq_simulation(self, request):
        """Generate a full CMS PYQ simulation test for a specific year."""
        year = request.data.get('year')
        paper = request.data.get('paper')

        if not year:
            return Response({'error': 'Year is required'}, status=400)

        q_filter = Q(is_active=True, year=year)
        if paper:
            q_filter &= Q(paper=int(paper))

        questions = list(Question.objects.filter(q_filter).values_list('id', flat=True))

        if not questions:
            return Response({'error': f'No questions found for {year}'}, status=404)

        paper_label = f"Paper {paper}" if paper else "Combined"
        test = Test.objects.create(
            title=f"UPSC CMS {year} — {paper_label} Simulation",
            test_type='pyq_year',
            description=f"Full CMS {year} {paper_label} examination simulation with actual PYQ questions.",
            num_questions=len(questions),
            time_limit_minutes=120,
            negative_marking=True,
            negative_mark_value=0.33,
            created_by=request.user,
        )
        test.questions.set(questions)

        return Response(TestSerializer(test, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


class TestAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve user's test attempts."""
    serializer_class = TestAttemptSerializer

    def get_queryset(self):
        return TestAttempt.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TestAttemptDetailSerializer
        return TestAttemptSerializer
