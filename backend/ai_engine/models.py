"""
AI Engine Models - Chat History for AI Tutor.

Stores conversation sessions and messages for the AI tutor feature,
allowing students to review their past conversations.
"""

from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    """
    A chat session represents a conversation between a user and the AI tutor.
    Sessions are organized by mode (tutor, mnemonic, explain, textbook, analyze).
    """
    MODE_CHOICES = [
        ('tutor', 'AI Tutor'),
        ('mnemonic', 'Mnemonic Generator'),
        ('explain', 'Concept Explainer'),
        ('textbook', 'Textbook Search'),
        ('analyze', 'Question Analyzer'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions'
    )
    title = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='tutor')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['user', 'is_archived']),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.title or 'Untitled'} ({self.mode})"

    def save(self, *args, **kwargs):
        # Auto-generate title from first message if not set
        if not self.title and self.pk:
            first_msg = self.messages.filter(role='user').first()
            if first_msg:
                self.title = first_msg.content[:100]
        super().save(*args, **kwargs)


class ChatMessage(models.Model):
    """
    Individual messages within a chat session.
    Stores both user questions and AI responses.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=4, choices=ROLE_CHOICES)
    content = models.TextField()
    mode = models.CharField(max_length=20, blank=True)
    citations = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}..."
