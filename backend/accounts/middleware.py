import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class UpdateLastSeenMiddleware:
    """Refresh the authenticated user's `last_seen` timestamp on every
    request, throttled to once per 5 minutes. Runs *after* the response
    is produced so it never blocks the user-facing page, but a DB error
    on the update would otherwise surface to the client (and Sentry).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            # Update last_seen if it's empty or older than 5 minutes to avoid hitting DB every single request
            now = timezone.now()
            if not request.user.last_seen or request.user.last_seen < now - timedelta(minutes=5):
                # We use update() to prevent triggering signals or saving the whole model, keeping it extremely lightweight.
                # Wrapped in try/except so a transient DB blip doesn't
                # turn a "best-effort timestamp refresh" into a 500.
                try:
                    request.user.__class__.objects.filter(pk=request.user.pk).update(last_seen=now)
                except Exception as e:
                    logger.warning(f"UpdateLastSeenMiddleware: skipping last_seen update for user {request.user.pk}: {e}")
                # Note: this won't update the object in memory during this request, but that's fine for our use case.
        return response
