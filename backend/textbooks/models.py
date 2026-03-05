from django.db import models
from django.conf import settings


class Textbook(models.Model):
    """Standard medical textbook."""
    name = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    edition = models.CharField(max_length=50, blank=True)
    subject = models.ForeignKey('questions.Subject', on_delete=models.CASCADE, related_name='textbooks')
    cover_image = models.ImageField(upload_to='textbook_covers/', blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['subject', 'name']

    def __str__(self):
        return f"{self.name} by {self.author}"


class Chapter(models.Model):
    """Chapter within a textbook."""
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name='chapters')
    number = models.IntegerField()
    title = models.CharField(max_length=300)
    topics_covered = models.ManyToManyField('questions.Topic', blank=True, related_name='chapters')

    class Meta:
        ordering = ['textbook', 'number']
        unique_together = ['textbook', 'number']

    def __str__(self):
        return f"{self.textbook.name} Ch.{self.number}: {self.title}"


class PDFUpload(models.Model):
    """User-uploaded PDF documents (notes, handwritten PDFs, etc.)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploads')
    title = models.CharField(max_length=300)
    file = models.FileField(upload_to='pdfs/')
    textbook = models.ForeignKey(Textbook, null=True, blank=True, on_delete=models.SET_NULL)
    subject = models.ForeignKey('questions.Subject', null=True, blank=True, on_delete=models.SET_NULL)
    is_processed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (by {self.user.username})"
