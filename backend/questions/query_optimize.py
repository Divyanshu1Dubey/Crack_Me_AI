"""Phase-3 query optimization helpers.

* `with_related(qs)` — applies the standard `select_related` /
  `prefetch_related` chain every Question list / detail query should
  use, so callers never re-invent the joins.
* `apply_pagination(qs, request, default=25, max=100)` — consistent
  page + page_size handling used by the practice queue + recall
  search + analytics endpoints.

These are intentionally small, import-free helpers — every new code
path that reads `Question` should funnel through them.
"""
from __future__ import annotations

from typing import Tuple


def with_related(qs):
    """Apply standard prefetches for Question list / detail."""
    return (qs
            .select_related("subject", "topic")
            .prefetch_related("images", "recall_sources"))


def apply_pagination(qs, request, *, default: int = 25, max_size: int = 100) -> Tuple:
    """Return (sliced_qs, page, page_size, total)."""
    try:
        page_size = min(int(request.query_params.get("page_size", default)), max_size)
    except (TypeError, ValueError):
        page_size = default
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    return qs[start:end], page, page_size, total
