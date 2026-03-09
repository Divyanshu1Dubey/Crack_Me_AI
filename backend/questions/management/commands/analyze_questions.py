"""
Management command to analyze question bank data quality and completeness.
Run: python manage.py analyze_questions
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from questions.models import Question, Subject, Topic


class Command(BaseCommand):
    help = 'Analyze question bank data quality and identify issues'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Analyzing Question Bank Data...\n')

        # Overall statistics
        total_questions = Question.objects.count()
        active_questions = Question.objects.filter(is_active=True).count()
        inactive_questions = total_questions - active_questions
        
        self.stdout.write(f'📊 Overall Statistics:')
        self.stdout.write(f'  Total questions: {total_questions}')
        self.stdout.write(f'  Active questions: {active_questions}')
        self.stdout.write(f'  Inactive questions: {inactive_questions}')
        
        # Year-wise analysis for 2018-2020
        problem_years = [2018, 2019, 2020]
        self.stdout.write(f'\n📅 Year-wise Analysis (2018-2020):')
        
        for year in problem_years:
            year_qs = Question.objects.filter(year=year)
            active_year_qs = year_qs.filter(is_active=True)
            
            self.stdout.write(f'\n  Year {year}:')
            self.stdout.write(f'    Total questions: {year_qs.count()}')
            self.stdout.write(f'    Active questions: {active_year_qs.count()}')
            self.stdout.write(f'    Inactive questions: {year_qs.count() - active_year_qs.count()}')
            
            if year_qs.exists():
                # Check data completeness
                complete_questions = year_qs.filter(
                    Q(explanation__gt='') &
                    Q(subject__isnull=False) &
                    Q(topic__isnull=False)
                ).count()
                
                questions_with_references = year_qs.filter(
                    Q(book_name__gt='') |
                    Q(chapter__gt='')
                ).count()
                
                self.stdout.write(f'    Complete with explanation: {complete_questions}')
                self.stdout.write(f'    With textbook references: {questions_with_references}')
                
                # Sample questions
                sample = active_year_qs.first()
                if sample:
                    self.stdout.write(f'    Sample question: "{sample.question_text[:80]}..."')
                    self.stdout.write(f'    Subject: {sample.subject.name if sample.subject else "None"}')
                    self.stdout.write(f'    Topic: {sample.topic.name if sample.topic else "None"}')
                    self.stdout.write(f'    Has explanation: {"Yes" if sample.explanation else "No"}')
            else:
                self.stdout.write(f'    ❌ NO QUESTIONS FOUND FOR YEAR {year}')
        
        # Subject-wise breakdown for problem years
        self.stdout.write(f'\n📚 Subject-wise Breakdown (2018-2020):')
        for year in problem_years:
            self.stdout.write(f'\n  Year {year}:')
            subject_stats = Question.objects.filter(year=year, is_active=True)\
                .values('subject__name')\
                .annotate(count=Count('id'))\
                .order_by('-count')
            
            for stat in subject_stats:
                self.stdout.write(f'    {stat["subject__name"]}: {stat["count"]} questions')
        
        # Check for data quality issues
        self.stdout.write(f'\n🔧 Data Quality Issues:')
        
        # Questions without explanations
        no_explanation = Question.objects.filter(
            year__in=problem_years,
            is_active=True,
            explanation=''
        ).count()
        
        # Questions without topics
        no_topic = Question.objects.filter(
            year__in=problem_years,
            is_active=True,
            topic__isnull=True
        ).count()
        
        # Questions with very short text
        short_text = Question.objects.filter(
            year__in=problem_years,
            is_active=True
        ).extra(where=["LENGTH(question_text) < 50"]).count()
        
        self.stdout.write(f'  Questions without explanations: {no_explanation}')
        self.stdout.write(f'  Questions without topics: {no_topic}')
        self.stdout.write(f'  Questions with very short text: {short_text}')
        
        # API filtering simulation (simplified)
        self.stdout.write(f'\n🌐 API Filter Simulation:')
        
        for year in problem_years:
            filtered_qs = Question.objects.filter(year=year, is_active=True)
            self.stdout.write(f'  Year {year} - API would return {filtered_qs.count()} questions')
            if filtered_qs.exists():
                first_question = filtered_qs.first()
                if first_question:
                    self.stdout.write(f'    First result ID: {first_question.id}')
                    self.stdout.write(f'    First result text: {first_question.question_text[:50]}...')
        
        # Recommendations
        self.stdout.write(f'\n💡 Recommendations:')
        
        if inactive_questions > 0:
            self.stdout.write(f'  ⚠️  {inactive_questions} questions are inactive - check if they should be activated')
        
        if no_explanation > 0:
            self.stdout.write(f'  ⚠️  {no_explanation} questions lack explanations - consider adding them')
        
        if no_topic > 0:
            self.stdout.write(f'  ⚠️  {no_topic} questions lack topics - assign appropriate topics')
        
        # Check if any year has suspiciously low question count
        for year in problem_years:
            count = Question.objects.filter(year=year, is_active=True).count()
            if count < 50:
                self.stdout.write(f'  ⚠️  Year {year} has only {count} questions - may need more questions')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Analysis complete!'))
