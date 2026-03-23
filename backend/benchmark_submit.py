import os
import sys
import time
import django
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question, Subject, Topic
from tests_engine.models import Test, TestAttempt, QuestionResponse

def setup_benchmark_data(num_questions=50):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username='bench_user', email='bench@example.com')
    user.set_password('password123')
    user.save()

    subject, _ = Subject.objects.get_or_create(name='Benchmark Subject', code='BENCH', paper=1)
    topic, _ = Topic.objects.get_or_create(subject=subject, name='Benchmark Topic')

    questions = []
    for i in range(num_questions):
        q = Question.objects.create(
            question_text=f'Question {i}',
            option_a='A', option_b='B', option_c='C', option_d='D',
            correct_answer='A',
            year=2023,
            subject=subject,
            topic=topic
        )
        questions.append(q)

    test = Test.objects.create(
        title='Benchmark Test',
        test_type='mixed',
        num_questions=num_questions,
        created_by=user
    )
    test.questions.set(questions)

    return user, test, questions

def run_benchmark(user, test, questions):
    client = APIClient()
    client.force_authenticate(user=user)

    # Start attempt
    response = client.post(f'/api/tests/{test.id}/start/')
    attempt_id = response.data['attempt_id']

    # Submit answers
    answers = []
    for q in questions:
        answers.append({
            'question_id': q.id,
            'selected_answer': 'A',
            'time_taken_seconds': 10,
            'confidence_level': 5
        })

    payload = {
        'attempt_id': attempt_id,
        'answers': answers
    }

    start_time = time.perf_counter()
    response = client.post(f'/api/tests/{test.id}/submit/', payload, format='json')
    end_time = time.perf_counter()

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.data)
        return None

    return end_time - start_time

if __name__ == '__main__':
    print("Setting up benchmark data...")
    user, test, questions = setup_benchmark_data(100)

    print("Running baseline benchmark (3 runs)...")
    durations = []
    for i in range(3):
        # We need a new attempt for each run
        duration = run_benchmark(user, test, questions)
        if duration:
            durations.append(duration)
            print(f"Run {i+1}: {duration:.4f}s")

    if durations:
        avg_duration = sum(durations) / len(durations)
        print(f"Average duration: {avg_duration:.4f}s")

    # Cleanup (optional, but good for repeatability if we run multiple times)
    # TestAttempt.objects.filter(user=user).delete()
