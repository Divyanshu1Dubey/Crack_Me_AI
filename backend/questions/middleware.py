import time
from django.core.cache import cache
from django.http import JsonResponse


class RateLimitMiddleware:
    """Per-IP rate limit for the question bank.

    SECURITY (Fix #5): The previous version trusted ``X-Forwarded-For``
    unconditionally. That header is attacker-controlled when the backend is
    reachable directly (no proxy) — anyone can spoof a fresh IP per request
    and bypass the 60 GET/min limit. We now read only ``REMOTE_ADDR`` (the
    raw socket address), which the attacker cannot forge without a proxy.

    Note: if Render / Vercel is later configured to inject a real proxy,
    switch the read to ``HTTP_X_FORWARDED_FOR`` only AFTER validating that
    the request actually arrived via the proxy's IP range. Until then we
    accept the small risk of a noisy-IP world and stay safe from spoofing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if '/api/questions/' in request.path and request.method == 'GET':
            # SECURITY: REMOTE_ADDR only — never trust X-Forwarded-For.
            ip = request.META.get('REMOTE_ADDR', '').strip()
            if ip:
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