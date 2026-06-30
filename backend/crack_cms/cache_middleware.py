from django.utils.cache import add_never_cache_headers

class DisableApiCacheMiddleware:
    """
    Middleware that disables caching for all API responses (paths starting with /api/)
    by setting appropriate Cache-Control and Expires headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/api/'):
            add_never_cache_headers(response)
        return response
