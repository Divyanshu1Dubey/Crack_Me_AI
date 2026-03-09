"""
Management command to backup and sync question data between environments.
Run: python manage.py sync_data --action=backup|restore|export
"""
import json
import os
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from questions.models import Question, Subject, Topic
from datetime import datetime


class Command(BaseCommand):
    help = 'Backup, restore, or export question data for environment sync'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['backup', 'restore', 'export'],
            required=True,
            help='Action to perform: backup, restore, or export'
        )
        parser.add_argument(
            '--file',
            type=str,
            help='File path for backup/restore operations'
        )
        parser.add_argument(
            '--years',
            type=str,
            help='Comma-separated years to include (e.g., "2018,2019,2020")'
        )

    def handle(self, *args, **options):
        action = options['action']
        years_filter = None
        
        if options['years']:
            try:
                years_filter = [int(y.strip()) for y in options['years'].split(',')]
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid years format. Use: "2018,2019,2020"'))
                return

        if action == 'backup':
            self.backup_data(options['file'], years_filter)
        elif action == 'restore':
            self.restore_data(options['file'])
        elif action == 'export':
            self.export_data(options['file'], years_filter)

    def backup_data(self, filepath, years_filter=None):
        """Backup all question data to JSON file"""
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f'questions_backup_{timestamp}.json'
        
        self.stdout.write(f'📦 Backing up data to {filepath}...')
        
        # Filter by years if specified
        questions_qs = Question.objects.all()
        if years_filter:
            questions_qs = questions_qs.filter(year__in=years_filter)
            self.stdout.write(f'  Filtering by years: {years_filter}')
        
        # Serialize data
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'total_questions': questions_qs.count(),
            'subjects': list(Subject.objects.all().values()),
            'topics': list(Topic.objects.all().values()),
            'questions': list(questions_qs.values())
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Backup complete: {backup_data["total_questions"]} questions saved'))

    def restore_data(self, filepath):
        """Restore data from JSON backup file"""
        if not filepath or not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR('Please provide a valid backup file path'))
            return
        
        self.stdout.write(f'📥 Restoring data from {filepath}...')
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Clear existing data (optional - you might want to merge instead)
            response = input('This will DELETE all existing questions. Continue? (y/N): ')
            if response.lower() != 'y':
                self.stdout.write('Restore cancelled.')
                return
            
            Question.objects.all().delete()
            Topic.objects.all().delete()
            Subject.objects.all().delete()
            
            # Restore subjects
            for subject_data in backup_data['subjects']:
                Subject.objects.create(**subject_data)
            
            # Restore topics
            for topic_data in backup_data['topics']:
                # Convert foreign key references
                topic_data['subject_id'] = topic_data.pop('subject')
                Topic.objects.create(**topic_data)
            
            # Restore questions
            for question_data in backup_data['questions']:
                # Convert foreign key references
                question_data['subject_id'] = question_data.pop('subject')
                if question_data.get('topic'):
                    question_data['topic_id'] = question_data.pop('topic')
                else:
                    question_data['topic_id'] = None
                
                Question.objects.create(**question_data)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Restore complete: {backup_data["total_questions"]} questions restored'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Restore failed: {str(e)}'))

    def export_data(self, filepath, years_filter=None):
        """Export questions in a format suitable for manual editing"""
        if not filepath:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f'questions_export_{timestamp}.json'
        
        self.stdout.write(f'📤 Exporting data to {filepath}...')
        
        # Filter by years if specified
        questions_qs = Question.objects.select_related('subject', 'topic').all()
        if years_filter:
            questions_qs = questions_qs.filter(year__in=years_filter)
            self.stdout.write(f'  Filtering by years: {years_filter}')
        
        # Export in human-readable format
        export_data = []
        for q in questions_qs:
            export_data.append({
                'id': q.id,
                'year': q.year,
                'subject': q.subject.name if q.subject else None,
                'topic': q.topic.name if q.topic else None,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct_answer': q.correct_answer,
                'difficulty': q.difficulty,
                'explanation': q.explanation,
                'concept_tags': q.concept_tags,
                'is_active': q.is_active
            })
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(self.style.SUCCESS(f'✅ Export complete: {len(export_data)} questions exported'))
