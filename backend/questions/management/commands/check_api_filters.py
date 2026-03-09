"""
Management command to test API filtering and identify frontend display issues.
Run: python manage.py check_api_filters
"""
from django.core.management.base import BaseCommand
from questions.models import Question, Subject
from django.test import RequestFactory
from questions.serializers import QuestionListSerializer
from questions.views import QuestionViewSet


class Command(BaseCommand):
    help = 'Test API filtering logic to identify frontend display issues'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Testing API Filtering Logic...\n')

        factory = RequestFactory()
        viewset = QuestionViewSet()

        # Test 1: Basic listing without filters
        self.stdout.write('📋 Test 1: Basic API Listing')
        request = factory.get('/api/questions/')
        
        # Create a mock user for the request
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Simulate unauthenticated request (no user)
        queryset = QuestionViewSet().get_queryset()
        
        self.stdout.write(f'  Total questions in queryset: {queryset.count()}')
        self.stdout.write(f'  Sample questions (first 3):')
        
        for i, q in enumerate(queryset[:3]):
            self.stdout.write(f'    {i+1}. ID: {q.id}, Year: {q.year}, Subject: {q.subject.name if q.subject else "None"}')
            self.stdout.write(f'       Text: {q.question_text[:60]}...')

        # Test 2: Year filtering for 2018-2020
        self.stdout.write('\n📅 Test 2: Year Filtering (2018-2020)')
        for year in [2018, 2019, 2020]:
            queryset = QuestionViewSet().get_queryset().filter(year=year)
            
            self.stdout.write(f'  Year {year}:')
            self.stdout.write(f'    Filtered queryset count: {queryset.count()}')
            
            if queryset.exists():
                first_q = queryset.first()
                self.stdout.write(f'    First question: ID {first_q.id}, Subject: {first_q.subject.name if first_q.subject else "None"}')
                self.stdout.write(f'    Text preview: {first_q.question_text[:60]}...')

        # Test 3: Subject filtering
        self.stdout.write('\n📚 Test 3: Subject Filtering')
        subjects = Subject.objects.all()[:3]
        for subject in subjects:
            queryset = QuestionViewSet().get_queryset().filter(subject=subject)
            count = queryset.count()
            
            self.stdout.write(f'  {subject.name} (ID: {subject.id}): {count} questions')

        # Test 4: Check specific years that user reported as missing
        self.stdout.write('\n🚨 Test 4: Problem Years Deep Dive')
        for year in [2018, 2019, 2020]:
            questions = Question.objects.filter(year=year, is_active=True)
            self.stdout.write(f'\n  Year {year} Analysis:')
            self.stdout.write(f'    Total in DB: {questions.count()}')
            
            if questions.exists():
                # Check subject distribution
                subject_breakdown = {}
                for q in questions:
                    subj_name = q.subject.name if q.subject else 'None'
                    subject_breakdown[subj_name] = subject_breakdown.get(subj_name, 0) + 1
                
                self.stdout.write('    Subject breakdown:')
                for subj, count in subject_breakdown.items():
                    self.stdout.write(f'      {subj}: {count}')
                
                # Check if questions have topics
                with_topics = questions.filter(topic__isnull=False).count()
                self.stdout.write(f'    With topics: {with_topics}')
                self.stdout.write(f'    Without topics: {questions.count() - with_topics}')
                
                # Check if questions have explanations
                with_explanations = questions.exclude(explanation='').count()
                self.stdout.write(f'    With explanations: {with_explanations}')
                self.stdout.write(f'    Without explanations: {questions.count() - with_explanations}')

        # Test 5: API endpoint response simulation
        self.stdout.write('\n🌐 Test 5: API Endpoint Simulation')
        
        for year in [2018, 2019, 2020]:
            filtered_qs = QuestionViewSet().get_queryset().filter(year=year)
            
            self.stdout.write(f'  Year {year}: API would return {filtered_qs.count()} items')
            
            # Check if any items have problematic data
            for q in filtered_qs[:5]:
                if not q.question_text:
                    self.stdout.write(f'    ⚠️  Item {q.id} has empty question_text!')
                if not q.subject:
                    self.stdout.write(f'    ⚠️  Item {q.id} has missing subject!')

        # Test 6: Years endpoint
        self.stdout.write('\n📊 Test 6: Years Endpoint')
        years = Question.objects.values_list('year', flat=True).distinct().order_by('-year')
        self.stdout.write(f'  Available years: {list(years)}')
        
        # Check if 2018-2020 are in the list
        problem_years = [2018, 2019, 2020]
        missing_from_years_endpoint = [y for y in problem_years if y not in years]
        if missing_from_years_endpoint:
            self.stdout.write(f'  ⚠️  Years missing from endpoint: {missing_from_years_endpoint}')
        else:
            self.stdout.write('  ✅ All problem years (2018-2020) are available')

        self.stdout.write(self.style.SUCCESS('\n✅ API filtering test complete!'))
