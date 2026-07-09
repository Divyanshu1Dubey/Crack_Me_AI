import uuid


class ApiRequestIdMiddleware:
    """
    Ensure every API request/response has an X-Request-ID for tracing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (request.META.get("HTTP_X_REQUEST_ID") or "").strip()
        if not request_id:
            request_id = str(uuid.uuid4())

        request.request_id = request_id
        response = self.get_response(request)

        if request.path.startswith("/api/"):
            response["X-Request-ID"] = request_id

        return response
