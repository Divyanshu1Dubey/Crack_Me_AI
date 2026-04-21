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


class TextbookChunk(models.Model):
    """Chunk-level governance record for RAG sources."""

    textbook = models.ForeignKey(Textbook, null=True, blank=True, on_delete=models.CASCADE, related_name='chunks')
    upload = models.ForeignKey(PDFUpload, null=True, blank=True, on_delete=models.CASCADE, related_name='chunks')
    book_name = models.CharField(max_length=255, blank=True)
    page_number = models.IntegerField(default=0)
    chunk_text = models.TextField()
    quality_score = models.FloatField(default=0.0)
    is_approved = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    merged_from_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['book_name', 'page_number', 'id']
        indexes = [
            models.Index(fields=['book_name', 'page_number']),
            models.Index(fields=['is_approved', 'is_rejected']),
        ]

    def __str__(self):
        source = self.book_name or (self.textbook.name if self.textbook else 'Unknown')
        return f"Chunk#{self.id} {source} p{self.page_number}"


class QuestionReferenceOverride(models.Model):
    """Manual Question -> Book/Page/Screenshot mapping that overrides AI references."""

    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='reference_overrides')
    textbook = models.ForeignKey(Textbook, null=True, blank=True, on_delete=models.SET_NULL, related_name='question_overrides')
    chapter = models.CharField(max_length=200, blank=True)
    page_number = models.CharField(max_length=50, blank=True)
    excerpt = models.TextField(blank=True)
    screenshot = models.ImageField(upload_to='question_reference_overrides/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='question_reference_overrides')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['question', 'is_active']),
        ]

    def __str__(self):
        return f"Q{self.question_id} -> {self.textbook.name if self.textbook else 'Manual'} p{self.page_number}"
