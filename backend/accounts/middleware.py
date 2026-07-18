from django.utils import timezone
from datetime import timedelta

class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            # Update last_seen if it's empty or older than 5 minutes to avoid hitting DB every single request
            now = timezone.now()
            if not request.user.last_seen or request.user.last_seen < now - timedelta(minutes=5):
                # We use update() to prevent triggering signals or saving the whole model, keeping it extremely lightweight
                request.user.__class__.objects.filter(pk=request.user.pk).update(last_seen=now)
                # Note: this won't update the object in memory during this request, but that's fine for our use case.
        return response
