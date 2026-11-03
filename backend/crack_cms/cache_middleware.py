from django.utils.cache import add_never_cache_headers

class DisableApiCacheMiddleware:
    """
    Middleware that disables caching for API responses (paths starting with /api/)
    by setting appropriate Cache-Control and Expires headers.

    A view that sets its own Cache-Control keeps it. The question-image serve
    view marks its bytes ``private, max-age=3600``; overwriting that with
    no-cache/no-store made every question view download (and, for ``?w=``,
    re-resize) each image again. Responses without an explicit Cache-Control
    are still marked never-cache.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/') and not response.has_header('Cache-Control'):
            add_never_cache_headers(response)
        return response
