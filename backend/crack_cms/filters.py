"""Project-wide DRF filter backends (``REST_FRAMEWORK['DEFAULT_FILTER_BACKENDS']``)."""
from rest_framework.filters import SearchFilter

# Every ``?search=`` term is one more ``ILIKE '%term%'`` per search field on
# every row, evaluated again by the COUNT and the page query; DRF's own
# SearchFilter accepts as many terms as fit in the URL (about 2,000
# one-letter terms in a 4 KB request line).
MAX_SEARCH_TERMS = 10
MAX_SEARCH_TERM_CHARS = 100


class BoundedSearchFilter(SearchFilter):
    """DRF ``SearchFilter`` limited to the first ``MAX_SEARCH_TERMS``
    distinct terms (case-insensitive), each cut to
    ``MAX_SEARCH_TERM_CHARS`` characters. Terms are AND-ed, so ignoring the
    extra ones can only widen the result."""

    max_terms = MAX_SEARCH_TERMS
    max_term_chars = MAX_SEARCH_TERM_CHARS

    def get_search_terms(self, request):
        terms, seen = [], set()
        for term in super().get_search_terms(request):
            term = term[:self.max_term_chars]
            key = term.lower()
            if not term or key in seen:
                continue
            seen.add(key)
            terms.append(term)
            if len(terms) >= self.max_terms:
                break
        return terms
