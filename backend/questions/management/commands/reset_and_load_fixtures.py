from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models import Count
from questions.models import Question

class Command(BaseCommand):
    help = "Check question counts per year and reload fixture if incorrect"

    def handle(self, *args, **options):
        # Check years 2018 to 2025
        target_years = list(range(2018, 2026))
        
        # Get count of questions in DB grouped by year
        counts = {
            item['year']: item['total'] 
            for item in Question.objects.values('year').annotate(total=Count('id'))
        }
        
        needs_reset = False
        for yr in target_years:
            if counts.get(yr, 0) != 240:
                self.stdout.write(f"Year {yr} has incorrect count: {counts.get(yr, 0)} (expected 240)")
                needs_reset = True
                break
                
        if needs_reset:
            self.stdout.write("Deleting all existing questions to clean up database...")
            deleted_count, _ = Question.objects.all().delete()
            self.stdout.write(f"Deleted {deleted_count} questions.")
            
            self.stdout.write("Loading questions_fixture.json...")
            call_command("loaddata", "questions_fixture.json")
            self.stdout.write("Database questions successfully reset and loaded!")
        else:
            self.stdout.write("Database is already clean (240 questions per year for 2018-2025). Skipping reload.")
