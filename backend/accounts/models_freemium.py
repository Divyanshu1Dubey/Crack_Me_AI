"""Freemium-related models: curated showcase questions for free users."""
from django.db import models


class FreeShowcaseQuestion(models.Model):
    """Admin-curated set of 10 questions per year shown to free users.

    The same 10 questions are visible to every free user per year — keeps
    content deterministic, shareable, and SEO-friendly. Admin sets these
    in Django admin via an inline ordered by `(year, position)`.

    Premium users are NOT affected; they see the full question bank.
    """
    question = models.OneToOneField(
        'questions.Question',
        on_delete=models.CASCADE,
        related_name='free_showcase',
    )
    year = models.PositiveSmallIntegerField(db_index=True)
    position = models.PositiveSmallIntegerField(
        help_text='Display order 0-9 within the year (admin curates 10 per year).'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('year', 'position')
        ordering = ('year', 'position')
        indexes = [models.Index(fields=['year'])]

    def __str__(self):
        return f'Showcase {self.year} #{self.position}: Q{self.question_id}'