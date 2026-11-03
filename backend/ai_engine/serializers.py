"""
AI Engine Serializers - Chat History.
"""

from rest_framework import serializers
from .models import ChatSession, ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages."""

    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'mode', 'citations', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat sessions."""
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            'id', 'title', 'mode', 'created_at', 'updated_at',
            'is_archived', 'message_count', 'last_message_preview'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # The list view annotates both values in its one query; the fallbacks
    # keep the serializer usable on a plain instance (e.g. after create).
    def get_message_count(self, obj):
        annotated = getattr(obj, 'message_count_value', None)
        if annotated is not None:
            return annotated
        return obj.messages.count()

    def get_last_message_preview(self, obj):
        if hasattr(obj, 'last_message_content'):
            content = obj.last_message_content
            return content[:100] if content else None
        last_msg = obj.messages.order_by('created_at', 'id').last()
        if last_msg:
            return last_msg.content[:100]
        return None


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with all messages included."""
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            'id', 'title', 'mode', 'created_at', 'updated_at',
            'is_archived', 'messages'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
