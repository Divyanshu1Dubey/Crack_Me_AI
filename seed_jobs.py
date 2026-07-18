import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from jobs.models import Job, JobCategory
from django.utils import timezone
from datetime import timedelta

def seed_jobs():
    print("Seeding Jobs Knowledge Base...")
    
    jobs_data = [
        {
            "title": "Medical Officer (Coming Soon)",
            "hospital": "UPSC Combined Medical Services",
            "location": "All India",
            "category_name": "Government",
            "description": "Details regarding the 2024/2025 UPSC CMS vacancies will be updated here once officially released. We are actively scraping the official portals.",
            "salary": "Level 10 Matrix",
            "apply_link": "https://upsc.gov.in",
            "expires_at": timezone.now() + timedelta(days=365)
        },
        {
            "title": "Junior Resident (Non-Academic) - Coming Soon",
            "hospital": "AIIMS New Delhi",
            "location": "New Delhi",
            "category_name": "Residency",
            "description": "Information regarding JR ship vacancies at AIIMS will be automatically fetched and updated here soon.",
            "salary": "As per 7th CPC",
            "apply_link": "https://aiimsexams.ac.in",
            "expires_at": timezone.now() + timedelta(days=365)
        },
        {
            "title": "Senior Medical Officer (NBE) - Coming Soon",
            "hospital": "National Board of Examinations",
            "location": "Various Locations",
            "category_name": "Government",
            "description": "NBE medical officer postings are currently being indexed by our web crawler.",
            "salary": "TBD",
            "apply_link": "https://natboard.edu.in",
            "expires_at": timezone.now() + timedelta(days=365)
        }
    ]

    for data in jobs_data:
        # Get or create category
        cat, _ = JobCategory.objects.get_or_create(
            name=data['category_name'],
            defaults={'slug': data['category_name'].lower().replace(' ', '-')}
        )
        
        job_data = data.copy()
        job_data.pop('category_name')
        job_data['category'] = cat
        
        job, created = Job.objects.get_or_create(
            title=data['title'],
            defaults=job_data
        )
        if created:
            print(f"Created job: {job.title}")
        else:
            print(f"Job already exists: {job.title}")

if __name__ == '__main__':
    seed_jobs()
