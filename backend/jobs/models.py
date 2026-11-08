from django.db import models
from django.conf import settings
from questions.models import ExamTrack

class JobCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Job(models.Model):
    """A job listing. Students see it only once an admin checked it against the official notification and
    approved it (jobs.official_sources): nothing is fetched or generated."""
    STATUS_CHOICES = [
        ('draft', 'Draft (not public)'),
        ('approved', 'Approved (public while verified)'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=200)
    hospital = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    category = models.ForeignKey(JobCategory, on_delete=models.SET_NULL, null=True, related_name='jobs')
    description = models.TextField()
    salary = models.CharField(max_length=100, blank=True, null=True)
    apply_link = models.URLField(max_length=500)
    posted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # New fields for 6-Task Architecture Upgrade
    eligibility_summary = models.TextField(blank=True, help_text="Short summary of eligibility criteria")
    exam_track_tags = models.JSONField(default=list, blank=True, help_text="List of exam tracks (e.g. ['cms', 'neet_pg'])")
    exam_tracks = models.ManyToManyField(ExamTrack, blank=True, related_name='jobs', help_text="Target exam tracks")
    admin_edited = models.BooleanField(default=False, help_text="Flag to protect from automated overwrite")

    # Verification (2026-11-09): the official notification the listing was checked against, when and by whom.
    source_url = models.URLField(max_length=500, blank=True,
                                 help_text='Official notification / recruitment page the listing was checked against')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft', db_index=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    review_note = models.CharField(max_length=300, blank=True, help_text='Why the listing was rejected (admin only)')

    def __str__(self):
        return f"{self.title} at {self.hospital}"

class JobBookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarked_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'job']
