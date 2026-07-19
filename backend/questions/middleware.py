import time
from django.core.cache import cache
from django.http import JsonResponse

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if '/api/questions/' in request.path and request.method == 'GET':
            # Use X-Forwarded-For if available, else REMOTE_ADDR
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
            if ip:
                ip = ip.split(',')[0].strip()
                cache_key = f"rate_limit_qs_{ip}"
                # Count requests in a rolling 60 second window
                requests = cache.get(cache_key, [])
                now = time.time()
                # keep only requests in last 60 seconds
                requests = [req_time for req_time in requests if now - req_time < 60]
                
                if len(requests) >= 60:
                    return JsonResponse(
                        {"error": "Too many requests. Please slow down."},
                        status=429
                    )
                
                requests.append(now)
                cache.set(cache_key, requests, timeout=60)

        return self.get_response(request)
