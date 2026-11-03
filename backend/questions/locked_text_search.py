"""Text search on locked questions whose public text leaks the answer.

The serving guard (``answer_leak.redact_public_text``) cuts an answer label
or a correctness flag -- and the text after it -- out of the stem / options a
caller without the answer sees. The text filters still matched the raw
columns, so the match itself named the key on those rows:
``GET /api/questions/?question_id=<id>&search="Schwannoma ✅"`` returned the
row and ``"Ependymoma ✅"`` did not, and ``recall_search/?drug=Correct
Answer: B`` returned exactly the rows whose option label names B (four
requests read the key of every such row).

For a caller without full access (not staff / premium), a *locked* row
(outside the free showcase, ``views.free_showcase_rows``) whose public text
carries a label or a flag stays in a text-filtered result only when the terms
still occur in the text that caller sees (``redact_stem_text`` /
``cut_option_text``, after the API's ``normalize_text``). Rows a caller may
read the answer of keep the raw match.

The leaky rows are found by one scan (``answer_leak.PREFILTER_WORDS`` as an
SQL regex, then the detector) and cached with their visible text for
CACHE_TTL; a save that leaves an active row leaking drops the cache (see
``_question_saved``, connected by ``QuestionsConfig.ready``). Writes that
bypass ``save()`` (``QuerySet.update``, ``bulk_create``) are picked up when
the cache expires; the import gates hold such rows anyway
(``answer_leak.label_hold_reasons``). Running ``manage.py
fix_answer_label_leaks --apply`` empties the set.
"""
from __future__ import annotations

import re

from django.core.cache import cache
from django.db.models.signals import post_save

from .answer_leak import (
    OPTION_FIELDS, PREFILTER_WORDS, PUBLIC_TEXT_FIELDS, cut_option_text, redact_stem_text,
    row_has_answer_label,
)

CACHE_KEY = 'answer_leak:leaky_public_text:v1'
CACHE_TTL = 60 * 60
# Bumped by every invalidation: a scan that raced one is not cached.
_GENERATION_KEY = CACHE_KEY + ':generation'
# A tick that went through a cp1252 / latin-1 round trip ("âœ”"): the API
# repairs it before it shows (and checks) the text, so the scan must see it.
_MOJIBAKE_MARK = 'â'
# A save touching none of these leaves the cached set valid.
_WATCHED_FIELDS = frozenset(PUBLIC_TEXT_FIELDS) | {'is_active'}


def _visible_texts(stem, options) -> tuple:
    """(stem, option_a, ..., option_d) as a caller without the answer sees
    them, lower-cased for ``icontains``-like checks."""
    return (
        (redact_stem_text(stem) or '').lower(),
        *((cut_option_text(text) or '').lower() for text in options),
    )


def leaky_public_texts() -> dict:
    """``{question id: visible texts}`` (see ``_visible_texts``) of every
    active question whose public text carries an answer label, an
    explanation label or a correctness flag (``row_has_answer_label``)."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    from django.db.models import Q

    from .models import Question
    from .text_encoding import normalize_text

    generation = cache.get(_GENERATION_KEY)
    # One case-insensitive regex per field (the same words as the repair
    # command's icontains pre-filter, without 5 x 19 LIKEs in one query).
    pattern = '|'.join(re.escape(word) for word in (*PREFILTER_WORDS, _MOJIBAKE_MARK))
    prefilter = Q()
    for name in PUBLIC_TEXT_FIELDS:
        prefilter |= Q(**{f'{name}__iregex': pattern})
    rows = (
        Question.objects.filter(is_active=True).filter(prefilter)
        .order_by().values_list('id', *PUBLIC_TEXT_FIELDS)
    )
    out = {}
    for pk, *texts in rows.iterator(chunk_size=1000):
        # The serializers check and cut the normalised text.
        row = {name: normalize_text(text) for name, text in zip(PUBLIC_TEXT_FIELDS, texts)}
        if row_has_answer_label(row):
            out[pk] = _visible_texts(row['question_text'], [row[name] for name in OPTION_FIELDS])
    # Not cached when a leaky row was saved during the scan (it may miss it).
    if cache.get(_GENERATION_KEY) == generation:
        cache.set(CACHE_KEY, out, CACHE_TTL)
    return out


def invalidate() -> None:
    cache.delete(CACHE_KEY)
    try:
        cache.incr(_GENERATION_KEY)
    except ValueError:  # not set yet
        cache.set(_GENERATION_KEY, 1, None)


def _instance_leaks(instance) -> bool:
    """Whether a saved question's public text carries a label / flag (True
    when its text is not loaded)."""
    if set(PUBLIC_TEXT_FIELDS) & instance.get_deferred_fields():
        return True
    from .text_encoding import normalize_text

    return row_has_answer_label({name: normalize_text(getattr(instance, name, '') or '')
                                 for name in PUBLIC_TEXT_FIELDS})


def _question_saved(sender, instance=None, update_fields=None, **kwargs):
    """Drop the cached set when a save may have added a leaky active row.

    Saves of clean rows (imports, admin edits) keep it: rescanning after
    each of them would cost every search a scan of the bank. A row that
    stops leaking or is deactivated keeps a stale entry until CACHE_TTL,
    which can only hide a match on that row, never reveal one."""
    if update_fields is not None and not (_WATCHED_FIELDS & set(update_fields)):
        return
    if instance is None or not getattr(instance, 'is_active', True):
        return
    if _instance_leaks(instance):
        invalidate()


post_save.connect(_question_saved, sender='questions.Question',
                  dispatch_uid='questions.locked_text_search.question_saved')


def without_hidden_matches(queryset, still_matches):
    """``queryset`` (text-filtered, for a caller without full access) minus
    the locked leaky rows for which ``still_matches(visible_texts)`` is
    False -- rows the filter matched only inside the part the caller does
    not see."""
    leaky = leaky_public_texts()
    if not leaky:
        return queryset
    from .views import free_showcase_rows  # lazy: views imports this module

    showcase = set(free_showcase_rows().values_list('question_id', flat=True))
    locked = [pk for pk in leaky if pk not in showcase]
    if not locked:
        return queryset
    matched = queryset.filter(pk__in=locked).order_by().values_list('pk', flat=True)
    hidden = {pk for pk in matched if not still_matches(leaky[pk])}
    return queryset.exclude(pk__in=hidden) if hidden else queryset


def terms_visible_in_stem(terms):
    """``still_matches`` for the question-bank ``?search=`` of a caller
    without full access (stem only, every term -- DRF SearchFilter)."""
    folded = [term.lower() for term in terms]
    return lambda texts: all(term in texts[0] for term in folded)


def recall_terms_visible(phrase, keywords):
    """``still_matches`` for ``recall_search``: the ``q`` phrase in the stem
    (``q`` filters ``question_text__icontains`` as a whole -- its OR-ed
    tokens are substrings of it), and every clinical keyword in the stem or
    an option (each keyword is a filter of its own)."""
    folded_phrase = (phrase or '').lower()
    folded_keywords = [keyword.lower() for keyword in keywords]

    def still_matches(texts):
        if folded_phrase and folded_phrase not in texts[0]:
            return False
        return all(any(keyword in text for text in texts) for keyword in folded_keywords)

    return still_matches
