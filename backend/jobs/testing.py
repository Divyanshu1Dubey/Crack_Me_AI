"""Test helper: a listing students can see (official links, verified now, approved: jobs.official_sources)."""
from django.utils import timezone

from .models import Job

OFFICIAL_APPLY_LINK = 'https://www.aiimsexams.ac.in/info/recruitment.html'
OFFICIAL_SOURCE_URL = 'https://www.aiimsexams.ac.in/pdf/notice.pdf'


def published_job(**fields):
    fields.setdefault('apply_link', OFFICIAL_APPLY_LINK)
    fields.setdefault('source_url', OFFICIAL_SOURCE_URL)
    fields.setdefault('status', 'approved')
    fields.setdefault('last_verified_at', timezone.now())
    return Job.objects.create(**fields)
