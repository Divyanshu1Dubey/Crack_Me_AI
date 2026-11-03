"""Project-wide DRF pagination (``REST_FRAMEWORK['DEFAULT_PAGINATION_CLASS']``)."""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Page-number pagination that honours ``?page_size=`` (capped at 100).

    DRF's stock ``PageNumberPagination`` ignores ``page_size`` unless
    ``page_size_query_param`` is set, so clients that asked for 100 rows
    (exam palette, Test Center, flashcards, practice) silently received the
    20-row default and stopped paging after the first page.

    The default page stays at ``REST_FRAMEWORK['PAGE_SIZE']`` (20). Values
    that are missing, zero, negative or not integers fall back to it, and
    anything above ``max_page_size`` is clamped to 100. The response shape
    (``count`` / ``next`` / ``previous`` / ``results``) is unchanged.
    """

    page_size_query_param = "page_size"
    max_page_size = 100
