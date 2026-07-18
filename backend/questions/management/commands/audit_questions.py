import csv
import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from questions.models import Question

class Command(BaseCommand):
    help = 'Audits and cleans up existing questions, assigning UUIDs and sequential display_numbers based on year/paper.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply the changes to the database')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        
        self.stdout.write(self.style.NOTICE(f"Starting Question Audit... {'(DRY RUN)' if not apply_changes else '(LIVE RUN)'}"))
        
        questions = Question.objects.all().order_by('year', 'paper', 'id')
        
        # Group by year and paper
        groups = {}
        for q in questions:
            key = (q.year, q.paper)
            if key not in groups:
                groups[key] = []
            groups[key].append(q)
            
        report_data = []
        updates = []
        
        for (year, paper), q_list in groups.items():
            for i, q in enumerate(q_list):
                new_display_number = i + 1
                new_uuid = uuid.uuid4() # Force new UUID for all existing to fix duplication
                
                # Check for inconsistent tagging (e.g., missing subject or topic)
                issues = []
                if not q.subject_id:
                    issues.append("Missing subject")
                if not q.topic_id:
                    issues.append("Missing topic")
                
                report_data.append({
                    'id': q.id,
                    'year': year,
                    'paper': paper,
                    'old_display_number': q.display_number,
                    'new_display_number': new_display_number,
                    'uuid': str(new_uuid),
                    'issues': ", ".join(issues)
                })
                
                if apply_changes:
                    q.display_number = new_display_number
                    q.uuid = new_uuid
                    updates.append(q)
                    
        # Write report
        report_file = 'audit_report.csv'
        with open(report_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['id', 'year', 'paper', 'old_display_number', 'new_display_number', 'uuid', 'issues']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in report_data:
                writer.writerow(row)
                
        self.stdout.write(self.style.SUCCESS(f"Audit complete. Report written to {report_file}"))
        
        if apply_changes and updates:
            with transaction.atomic():
                Question.objects.bulk_update(updates, ['display_number', 'uuid'])
            self.stdout.write(self.style.SUCCESS(f"Successfully updated {len(updates)} questions."))
            
