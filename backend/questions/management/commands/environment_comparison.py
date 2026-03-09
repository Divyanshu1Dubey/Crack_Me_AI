"""
Management command to compare localhost vs production settings and database.
Run: python manage.py environment_comparison
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from questions.models import Question, Subject, Topic
import os


class Command(BaseCommand):
    help = 'Compare environment settings and database state'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Environment Comparison Analysis...\n')

        # Environment Settings Analysis
        self.stdout.write('⚙️  Environment Settings:')
        self.stdout.write(f'  DEBUG mode: {settings.DEBUG}')
        self.stdout.write(f'  Database engine: {settings.DATABASES["default"]["ENGINE"]}')
        self.stdout.write(f'  Database name: {settings.DATABASES["default"]["NAME"]}')
        
        # Check if we're on localhost
        db_path = settings.DATABASES["default"]["NAME"]
        is_localhost = 'localhost' in str(db_path) or '127.0.0.1' in str(db_path) or 'sqlite' in str(db_path)
        self.stdout.write(f'  Environment: {"Localhost" if is_localhost else "Production/Remote"}')
        
        # API Configuration
        self.stdout.write(f'\n🌐 API Configuration:')
        self.stdout.write(f'  ALLOWED_HOSTS: {getattr(settings, "ALLOWED_HOSTS", "Not set")}')
        self.stdout.write(f'  CORS_ALLOWED_ORIGINS: {getattr(settings, "CORS_ALLOWED_ORIGINS", "Not set")}')
        
        # Database Statistics
        self.stdout.write(f'\n📊 Database Statistics:')
        total_questions = Question.objects.count()
        active_questions = Question.objects.filter(is_active=True).count()
        total_subjects = Subject.objects.count()
        total_topics = Topic.objects.count()
        
        self.stdout.write(f'  Total questions: {total_questions}')
        self.stdout.write(f'  Active questions: {active_questions}')
        self.stdout.write(f'  Total subjects: {total_subjects}')
        self.stdout.write(f'  Total topics: {total_topics}')
        
        # Year Distribution Analysis
        self.stdout.write(f'\n📅 Year Distribution Analysis:')
        year_stats = {}
        for year in range(2018, 2026):  # 2018-2025
            count = Question.objects.filter(year=year).count()
            year_stats[year] = count
            if count > 0:
                self.stdout.write(f'  {year}: {count} questions')
        
        # Identify potential issues
        self.stdout.write(f'\n🚨 Issue Identification:')
        
        # Check for suspicious year patterns
        recent_years_high = [year for year in [2023, 2024, 2025] if year_stats.get(year, 0) > 200]
        if recent_years_high:
            self.stdout.write(f'  ⚠️  Recent years with very high question counts: {recent_years_high}')
        
        # Check for very low counts in problem years
        problem_years_low = [year for year in [2018, 2019, 2020] if year_stats.get(year, 0) < 50]
        if problem_years_low:
            self.stdout.write(f'  ⚠️  Problem years with low question counts: {problem_years_low}')
        else:
            self.stdout.write(f'  ✅ All problem years (2018-2020) have adequate question counts')
        
        # Data Quality Issues
        self.stdout.write(f'\n🔧 Data Quality Check:')
        
        # Questions without topics
        no_topic_count = Question.objects.filter(topic__isnull=True).count()
        self.stdout.write(f'  Questions without topics: {no_topic_count} ({no_topic_count/total_questions*100:.1f}%)')
        
        # Questions without explanations
        no_explanation_count = Question.objects.filter(explanation='').count()
        self.stdout.write(f'  Questions without explanations: {no_explanation_count} ({no_explanation_count/total_questions*100:.1f}%)')
        
        # Questions with very short text
        short_text_count = Question.objects.extra(where=["LENGTH(question_text) < 50"]).count()
        self.stdout.write(f'  Questions with very short text: {short_text_count}')
        
        # Environment-specific recommendations
        self.stdout.write(f'\n💡 Environment-Specific Recommendations:')
        
        if is_localhost:
            self.stdout.write('  🏠 Localhost Environment:')
            self.stdout.write('    - Ensure DEBUG=False in production')
            self.stdout.write('    - Check CORS settings for frontend access')
            self.stdout.write('    - Verify database backup procedures')
            self.stdout.write('    - Test with production-like data volumes')
            
            # Check for common localhost issues
            if total_questions == 2004:
                self.stdout.write('    ✅ Database appears to have expected question count')
            else:
                self.stdout.write(f'    ⚠️  Unexpected question count: {total_questions} (expected ~2004)')
        else:
            self.stdout.write('  🚀 Production Environment:')
            self.stdout.write('    - Ensure proper database indexing')
            self.stdout.write('    - Monitor performance with large datasets')
            self.stdout.write('    - Set up proper logging and monitoring')
            self.stdout.write('    - Configure caching for API responses')
        
        # Frontend Integration Check
        self.stdout.write(f'\n🖥️  Frontend Integration Check:')
        
        # Check if years endpoint would work correctly
        available_years = list(Question.objects.values_list('year', flat=True).distinct().order_by('-year'))
        self.stdout.write(f'  Years API would return: {available_years}')
        
        # Check if subjects endpoint would work
        subject_data = []
        for subject in Subject.objects.all():
            count = Question.objects.filter(subject=subject).count()
            subject_data.append(f'{subject.name}: {count}')
        
        self.stdout.write(f'  Subjects API would return: {len(subject_data)} subjects')
        self.stdout.write(f'    Sample: {", ".join(subject_data[:3])}...')
        
        # Potential Frontend Issues
        self.stdout.write(f'\n🐛 Potential Frontend Issues:')
        
        # Check for questions that might cause frontend display problems
        questions_with_newlines = Question.objects.filter(question_text__contains='\n').count()
        if questions_with_newlines > 0:
            self.stdout.write(f'  ⚠️  {questions_with_newlines} questions have newlines in text (may affect display)')
        
        # Check for questions with special characters
        questions_with_special_chars = Question.objects.filter(
            question_text__regex=r'[^\w\s\.\,\?\!\(\)\[\]\{\}\:\;\-\+\*\/\=\'\"]'
        ).count()
        if questions_with_special_chars > 0:
            self.stdout.write(f'  ⚠️  {questions_with_special_chars} questions have special characters')
        
        # Summary and Next Steps
        self.stdout.write(f'\n📋 Summary and Next Steps:')
        
        if no_topic_count > total_questions * 0.8:
            self.stdout.write('  🔴 HIGH PRIORITY: Most questions lack topics - affects categorization')
        
        if no_explanation_count > total_questions * 0.7:
            self.stdout.write('  🔴 HIGH PRIORITY: Most questions lack explanations - affects learning value')
        
        if total_questions > 0 and all(year_stats.get(year, 0) > 0 for year in [2018, 2019, 2020]):
            self.stdout.write('  ✅ All problem years have questions - backend data is intact')
            self.stdout.write('  🔍 Issue likely in frontend filtering or display logic')
        
        self.stdout.write('\n📝 Recommended Actions:')
        self.stdout.write('  1. Check frontend API calls and filtering logic')
        self.stdout.write('  2. Verify frontend year filter implementation')
        self.stdout.write('  3. Test frontend with browser developer tools')
        self.stdout.write('  4. Add missing topics and explanations for better UX')
        self.stdout.write('  5. Set up database backup and sync procedures')

        self.stdout.write(self.style.SUCCESS('\n✅ Environment comparison complete!'))
