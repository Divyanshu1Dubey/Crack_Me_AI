"""Grounded, extractive answers for when no language model may (or can) be called.

Two situations use this module:

* ``AI_OFFLINE_MODE`` is on (env ``AI_OFFLINE_MODE`` in ``1/true/yes``): no
  external LLM call is made anywhere. AI endpoints answer from retrieval and
  stored data, label the answer as offline, and charge nothing.
* Every provider failed (``ai_engine.services.AIUnavailable``): the views give
  the user's tokens and freemium slot back and use the same composer as the
  fallback, so the student never sees the outage sentence as an "answer".

The composer never writes new prose. It picks the sentences of the retrieved
textbook passages that share the most (rarity-weighted) terms with the
question, cites each one as ``[book p.page]``, and adds the closest past
question from the question bank with its stored explanation when the match is
strong. When nothing clears the threshold it says so instead of guessing.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from itertools import islice
from typing import Iterable, Optional

from ai_engine.lexical_index import iter_sentences, tokenize

logger = logging.getLogger(__name__)

REASON_OFFLINE_MODE = 'offline_mode'
REASON_PROVIDERS_DOWN = 'providers_unavailable'

OFFLINE_NOTICES = {
    REASON_OFFLINE_MODE: (
        'Offline answer: AI generation is switched off, so this was assembled '
        'from the textbook library and question bank without an AI model. '
        'No tokens were charged.'
    ),
    REASON_PROVIDERS_DOWN: (
        'Offline answer: the AI tutor is unavailable right now, so this was '
        'assembled from the textbook library and question bank without an AI '
        'model. No tokens were charged.'
    ),
}

NO_GROUNDED_ANSWER = (
    'No grounded offline answer is available for this question: nothing in the '
    'textbook library or question bank matches it closely enough.'
)

# A sentence must cover at least this share of the question's (rarity-
# weighted) terms, and share at least two terms with it, before the answer
# counts as grounded.
MIN_SENTENCE_COVERAGE = 0.34
# Weaker sentences are still listed once the best one cleared the bar.
MIN_SUPPORTING_COVERAGE = 0.2
MAX_SENTENCES = 5
# Past-question match: Dice overlap of the stems' terms.
MIN_PYQ_SIMILARITY = 0.5
MIN_PYQ_SHARED_TERMS = 3
MAX_EXPLANATION_CHARS = 1200
# The question-bank prefilter searches for the question's longest few words.
PYQ_PROBE_TERMS = 4
# Distinct words considered for that probe. A real question has far fewer
# distinct words of five letters or more; the cap only bounds pathological input.
MAX_PROBE_CANDIDATES = 500

# Longest text the composer tokenises, matches and searches with (defence in
# depth: every API caller already caps its input). A question stem is capped
# at ai_engine.views.MAX_AI_INPUT_CHARS (4000) and the explain views append
# the correct option (MAX_OPTION_CHARS, 1000) after a space, so legitimate
# queries are never cut. ai_engine.views imports this module, so the limit is
# restated here; a test keeps the two in step.
MAX_QUERY_CHARS = 4000 + 1 + 1000

# Text that providers or older code paths returned *instead of* an answer.
# Stored explanations containing these are not shown as answers.
OUTAGE_SENTINELS = (
    'all ai services are temporarily unavailable',
    'ai answer generation is unavailable',
    'ai service is temporarily unavailable',
    'ai service temporarily unavailable',
    'ai explanation unavailable',
    'rag pipeline not initialized',
    'regenerated ai explanation placeholder',
    'no auto mode endpoints provided',
    'no endpoints provided',
    'model endpoint not found',
    'upstream request failed',
)


def ai_offline_mode() -> bool:
    """True when ``AI_OFFLINE_MODE`` asks for no external LLM calls at all.

    Read on every call (not at import) so operators and tests can flip it
    without a restart of the module.
    """
    return os.getenv('AI_OFFLINE_MODE', '').strip().lower() in ('1', 'true', 'yes')


def is_unusable_text(text) -> bool:
    """True for empty text or an outage / provider-error sentence."""
    if not isinstance(text, str) or not text.strip():
        return True
    lowered = text.strip().lower()
    return any(marker in lowered for marker in OUTAGE_SENTINELS)


@dataclass
class OfflineAnswer:
    grounded: bool
    answer: str                      # markdown: notice + body
    citations: list = field(default_factory=list)
    pyq: Optional[dict] = None
    reason: str = REASON_OFFLINE_MODE
    body: str = ''                   # markdown without the notice
    sentences: list = field(default_factory=list)   # [{'text', 'label'}]

    @property
    def notice(self) -> str:
        return offline_notice(self.reason)


def offline_notice(reason: str) -> str:
    return OFFLINE_NOTICES.get(reason, OFFLINE_NOTICES[REASON_OFFLINE_MODE])


def _bounded_query(text) -> str:
    """``text`` stripped and cut to MAX_QUERY_CHARS."""
    return (text or '').strip()[:MAX_QUERY_CHARS]


# ─── Display rule ───────────────────────────────────────────────────────

def public_subject(name):
    """A subject label as students see it: the loader's "Imported" bucket
    reads "Expert Curated" (``questions.serializers.public_subject_name``);
    every other value comes back unchanged. Imported lazily: ai_engine.services
    imports this module."""
    from questions.serializers import public_subject_name
    return public_subject_name(name)


def with_public_subject(payload):
    """An explain-after-answer dict with its subject labels as students see
    them: ``category`` and the ``context.subject`` that explain-question
    stores next to it. Changed in place and returned (``context`` is
    replaced, not mutated); anything that is not a dict is returned as is.

    Stored, cached and model-written explanations can carry the raw
    "Imported" (it was the prompt's subject), so every exit applies this."""
    if not isinstance(payload, dict):
        return payload
    if 'category' in payload:
        payload['category'] = public_subject(payload['category'])
    context = payload.get('context')
    if isinstance(context, dict) and 'subject' in context:
        payload['context'] = {**context, 'subject': public_subject(context['subject'])}
    return payload


@dataclass
class _Candidate:
    score: float
    hits: int
    sentence: str
    label: str
    passage: dict


# ─── Retrieval ──────────────────────────────────────────────────────────

def retrieve_passages(query: str, k: int = 8) -> list[dict]:
    """Textbook passages for ``query`` from the RAG store (never raises).

    Returns RAGPipeline.search dicts: ``{text, book, page, score, source_file}``.
    """
    query = _bounded_query(query)
    if not query:
        return []
    try:
        from ai_engine import services
        if services.rag_disabled():
            return []
        from ai_engine.rag_pipeline import RAGPipeline
        rag = RAGPipeline()
    except Exception as exc:  # RAG disabled or store unreadable
        logger.info('Offline composer: textbook retrieval unavailable (%s)', exc)
        return []
    try:
        return list(rag.search(query, n_results=k) or [])
    except Exception as exc:
        logger.warning('Offline composer: textbook search failed: %s', exc)
        return []
    finally:
        try:
            rag.close()
        except Exception:
            pass


def _cite_label(passage: dict) -> str:
    explicit = passage.get('cite')
    if explicit:
        return str(explicit)
    book = str(passage.get('book') or 'Textbook').strip()
    page = passage.get('page')
    if page in (None, '', 0, '0'):
        return book
    return f'{book} p.{page}'


# Words students add around a question that say nothing about its topic
# (already stemmed the way ``tokenize`` stems them).
_QUERY_FILLER = frozenset("""
explain please tell describe define list give show help know want need briefly brief
detail detailed kindly thank exam tomorrow today question answer mcq upsc cms neet
note short simple word mean meaning regard way
""".split())


def _query_terms(question: str) -> set:
    return {t for t in tokenize(question) if t not in _QUERY_FILLER}


def _match_key(term: str) -> str:
    """Looser key for matching query terms against sentence terms, so that
    "scoring" meets "score" and "caused" meets "cause" (``tokenize`` only
    folds plurals)."""
    for suffix in ('ing', 'ed'):
        if term.endswith(suffix) and len(term) - len(suffix) >= 4:
            term = term[: -len(suffix)]
            break
    if term.endswith('e') and len(term) > 4:
        term = term[:-1]
    return term


# Bibliography lines and navigation lists ("See also ...") from encyclopedia
# exports: they share words with almost any query but answer none.
_JUNK_SENTENCE_RE = re.compile(
    r'^\s*(see also|references|external links|further reading|bibliography)\b'
    r'|\b(doi|pmid|pmc|isbn|issn|retrieved|archived from)\b',
    re.IGNORECASE,
)


def _sentence_units(text: str) -> Iterable[str]:
    """``iter_sentences``, with long list/table blocks split per line so a
    numbered list does not become one 1,000-character "sentence"."""
    for sentence in iter_sentences(text):
        parts = [sentence]
        if len(sentence) > 300 and '\n' in sentence:
            parts = [line.strip(' \t-*•#|') for line in sentence.split('\n')]
        for part in parts:
            if len(part) >= 40 and not _JUNK_SENTENCE_RE.search(part):
                yield part


def _display_sentence(sentence: str) -> str:
    sentence = re.sub(r'\s+', ' ', sentence or '').strip()
    if len(sentence) > 600:
        cut = sentence[:600]
        sentence = cut[: cut.rfind(' ')] + '…' if ' ' in cut else cut + '…'
    return sentence


def _global_idf() -> Optional[dict]:
    """IDF of the whole textbook store (from the shared BM25 index), or None."""
    try:
        from django.conf import settings
        from ai_engine.lexical_index import get_index

        db_dir = getattr(settings, 'CHROMA_DB_DIR', None) or os.path.join(str(settings.BASE_DIR), 'chroma_db')
        index, _stats = get_index(os.path.join(str(db_dir), 'rag_store.sqlite3'))
        return index.idf if index is not None else None
    except Exception as exc:
        logger.debug('Offline composer: corpus IDF unavailable (%s)', exc)
        return None


def _term_weights(q_keys: dict, pool: list) -> tuple[dict, set]:
    """Weight per query key, and the anchor keys.

    Weights are corpus IDF when the BM25 index is available (terms the corpus
    never uses count as 1.0 so typos cannot dominate), otherwise rarity within
    the retrieved sentences. Anchors are the query's most specific terms that
    the corpus knows (one for a short question, up to three for a long
    vignette): a sentence with none of them is usually about something else.
    """
    idf = _global_idf()
    weights: dict[str, float] = {}
    known: dict[str, float] = {}
    if idf:
        for key, term in q_keys.items():
            value = idf.get(term)
            weights[key] = value if value is not None else 1.0
            if value is not None:
                known[key] = value
    else:
        n = len(pool)
        for key in q_keys:
            df = sum(1 for _s, keys, *_rest in pool if key in keys)
            weights[key] = math.log(1.0 + (n + 1.0) / (df + 0.5))
            if df:
                known[key] = weights[key]
    n_anchors = 1 if len(q_keys) < 6 else (2 if len(q_keys) < 12 else 3)
    anchors = set(sorted(known, key=known.get, reverse=True)[:n_anchors])
    return weights, anchors


def _rank_sentences(question: str, passages: Iterable[dict]) -> list[_Candidate]:
    """Score every sentence of every passage by weighted query-term overlap."""
    q_keys = {}
    for term in _query_terms(question):
        q_keys.setdefault(_match_key(term), term)
    if not q_keys:
        return []

    pool: list[tuple[str, set, str, dict, int]] = []
    seen: set[str] = set()
    passages = list(passages or [])
    for rank, passage in enumerate(passages):
        label = _cite_label(passage)
        for raw in _sentence_units(passage.get('text') or ''):
            if len(raw.strip()) < 40:
                continue
            keys = {_match_key(t) for t in tokenize(raw)}
            fingerprint = ' '.join(sorted(keys))
            if not keys or fingerprint in seen:
                continue
            seen.add(fingerprint)
            pool.append((_display_sentence(raw), keys, label, passage, rank))
    if not pool:
        return []

    weights, anchors = _term_weights(q_keys, pool)
    total = sum(weights.values()) or 1.0

    candidates = []
    for sentence, keys, label, passage, rank in pool:
        hits = q_keys.keys() & keys
        if not hits:
            continue
        coverage = sum(weights[k] for k in hits) / total
        if anchors and not (anchors & hits):
            coverage *= 0.6
        # Tiny tie-breaker for passages the retriever ranked higher.
        coverage += 0.01 * (len(passages) - rank) / max(len(passages), 1)
        candidates.append(_Candidate(coverage, len(hits), sentence, label, passage))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _select_sentences(question: str, passages: Iterable[dict]) -> list[_Candidate]:
    ranked = _rank_sentences(question, passages)
    if not ranked:
        return []
    needed_hits = min(2, len({_match_key(t) for t in _query_terms(question)}))
    best = ranked[0]
    if best.score < MIN_SENTENCE_COVERAGE or best.hits < needed_hits:
        return []
    # Up to MAX_SENTENCES supporting sentences, but never filler: each must
    # share enough terms and score at least half as well as the best one.
    floor = max(MIN_SUPPORTING_COVERAGE, best.score * 0.5)
    chosen = [best]
    for cand in ranked[1:]:
        if len(chosen) >= MAX_SENTENCES:
            break
        if cand.score >= floor and cand.hits >= needed_hits:
            chosen.append(cand)
    return chosen


# ─── Question bank ──────────────────────────────────────────────────────

def stored_explanation_text(row) -> str:
    """Best stored explanation for a question row (model instance or dict).

    Admin override → curated explanation → curated why_correct → a valid
    AI explanation. Outage sentences and placeholders are skipped.
    """
    def get(name):
        if isinstance(row, dict):
            return row.get(name)
        return getattr(row, name, None)

    for name in ('admin_explanation_override', 'explanation', 'why_correct'):
        value = get(name)
        if isinstance(value, str) and not is_unusable_text(value):
            return value.strip()
    if get('lock_explanation'):
        return ''
    ai = get('ai_explanation')
    if isinstance(ai, str) and ai.strip():
        stripped = ai.strip()
        if stripped.startswith('{'):
            try:
                data = json.loads(stripped)
            except ValueError:
                data = None
            # Legacy unparsed fallbacks carry `raw_response` (raw prose or
            # truncated JSON in why_correct): never an answer.
            if isinstance(data, dict) and not data.get('_failed') and 'raw_response' not in data:
                for key in ('why_correct', 'analysis'):
                    value = data.get(key)
                    if (isinstance(value, str) and not is_unusable_text(value)
                            and not value.strip().startswith(('{', '```'))):
                        return value.strip()
        elif not is_unusable_text(stripped):
            return stripped
    return ''


def _dice(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def _user_sees_full_bank(user) -> bool:
    """Staff and premium users see every answer (questions.views.
    user_can_view_answer); fails closed."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)):
        return True
    try:
        from accounts.utils import is_premium
        return bool(is_premium(user))
    except Exception:
        return False


def _pyq_probe_terms(question_text: str) -> list[str]:
    """The question's longest distinct words (five letters or more, longest
    first, ties in order of appearance) for the question-bank prefilter.

    Linear in the input: de-duplicated with a dict (a list-membership test
    was quadratic) and capped at MAX_PROBE_CANDIDATES distinct words.
    """
    distinct = dict.fromkeys(tok for tok in tokenize(question_text or '', stem=False) if len(tok) >= 5)
    candidates = list(islice(distinct, MAX_PROBE_CANDIDATES))
    return sorted(candidates, key=len, reverse=True)[:PYQ_PROBE_TERMS]


def find_similar_pyq(question_text: str, *, user=None, exclude_id=None) -> Optional[dict]:
    """The closest active past question with a stored explanation, or None.

    Free users only get admin-curated showcase questions back, the same rule
    the question bank applies to its retrieve endpoint, and never a
    scholarship-test question (its answer would leak to test takers).
    """
    question_text = _bounded_query(question_text)
    probe = _pyq_probe_terms(question_text)
    if not probe:
        return None

    try:
        from django.db.models import Exists, OuterRef, Q
        from questions.models import Question

        cond = Q()
        for term in probe:
            cond |= Q(question_text__icontains=term)
        qs = Question.objects.filter(is_active=True).filter(cond)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if not _user_sees_full_bank(user):
            # The question bank's own definition of free content.
            from questions.views import free_showcase_rows
            qs = qs.filter(
                Exists(free_showcase_rows().filter(question_id=OuterRef('pk'))),
                is_scholarship_eligible=False,
            )
        rows = list(qs.values(
            'id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'explanation', 'why_correct', 'admin_explanation_override',
            'ai_explanation', 'lock_explanation', 'year', 'exam_source',
        )[:300])
    except Exception as exc:
        logger.warning('Offline composer: question-bank lookup failed: %s', exc)
        return None

    q_terms = {_match_key(t) for t in _query_terms(question_text)}
    best, best_sim, best_shared = None, 0.0, 0
    for row in rows:
        terms = {_match_key(t) for t in tokenize(row.get('question_text') or '')}
        sim = _dice(q_terms, terms)
        if sim > best_sim:
            best, best_sim, best_shared = row, sim, len(q_terms & terms)
    if best is None or best_sim < MIN_PYQ_SIMILARITY or best_shared < MIN_PYQ_SHARED_TERMS:
        return None
    explanation = stored_explanation_text(best)
    if not explanation:
        return None
    letter = (best.get('correct_answer') or '').strip().upper()[:1]
    return {
        'id': best['id'],
        'year': best.get('year'),
        'exam_source': best.get('exam_source') or '',
        'question_text': best.get('question_text') or '',
        'correct_answer': letter,
        'correct_text': best.get(f'option_{letter.lower()}', '') if letter else '',
        'explanation': _truncate(explanation, MAX_EXPLANATION_CHARS),
        'similarity': round(best_sim, 3),
    }


def _truncate(text: str, limit: int) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return (cut[: cut.rfind(' ')] if ' ' in cut else cut) + '…'


# ─── Composer ───────────────────────────────────────────────────────────

def _pyq_heading(pyq: dict) -> str:
    bits = [b for b in (pyq.get('exam_source'), str(pyq.get('year') or '')) if b]
    return f"Closest past question ({' '.join(bits)})" if bits else 'Closest past question'


def pyq_summary(pyq: dict) -> str:
    """One plain-text paragraph for a past question (for non-markdown UIs)."""
    text = f"{_pyq_heading(pyq)}: {_truncate(pyq['question_text'], 300)}"
    if pyq.get('correct_answer'):
        answer = pyq['correct_answer']
        if pyq.get('correct_text'):
            answer = f"{answer}) {pyq['correct_text']}"
        text += f" Answer: {answer}."
    return f"{text} {pyq['explanation']}".strip()


def _render(chosen: list[_Candidate], pyq: Optional[dict]) -> str:
    lines = []
    if chosen:
        lines.append('**From the textbook library**')
        for cand in chosen:
            lines.append(f'- {cand.sentence} *[{cand.label}]*')
    if pyq:
        if chosen:
            lines.append('')
        lines.append(f'**{_pyq_heading(pyq)}**')
        lines.append(f"> {_truncate(pyq['question_text'], 400)}")
        if pyq.get('correct_answer'):
            answer = pyq['correct_answer']
            if pyq.get('correct_text'):
                answer = f"{answer}) {pyq['correct_text']}"
            lines.append(f'**Answer:** {answer}')
        lines.append('')
        lines.append(pyq['explanation'])
    return '\n'.join(lines).strip()


def compose_offline_answer(
    question_text: str,
    *,
    passages: Optional[list] = None,
    user=None,
    reason: str = REASON_OFFLINE_MODE,
    k: int = 8,
    include_pyq: bool = True,
    exclude_question_id=None,
) -> OfflineAnswer:
    """Build an extractive answer for ``question_text``.

    ``passages`` (RAGPipeline.search dicts, or dicts with a ``cite`` label)
    skips the textbook search when the caller already has them. The result is
    ``grounded`` only when a sentence or past question matched strongly.
    """
    question_text = _bounded_query(question_text)
    if passages is None:
        passages = retrieve_passages(question_text, k=k)
    chosen = _select_sentences(question_text, passages)
    pyq = None
    if include_pyq:
        pyq = find_similar_pyq(question_text, user=user, exclude_id=exclude_question_id)
    if not chosen and not pyq:
        return OfflineAnswer(grounded=False, answer=NO_GROUNDED_ANSWER, reason=reason)

    citations = []
    seen_labels = set()
    for cand in chosen:
        if cand.label in seen_labels:
            continue
        seen_labels.add(cand.label)
        citations.append({
            'book': cand.passage.get('book') or cand.label,
            'page': cand.passage.get('page') or '',
            'excerpt': cand.sentence[:200],
            'relevance': round(min(cand.score, 1.0), 3),
        })
    body = _render(chosen, pyq)
    return OfflineAnswer(
        grounded=True,
        answer=f'> {offline_notice(reason)}\n\n{body}',
        citations=citations,
        pyq=pyq,
        reason=reason,
        body=body,
        sentences=[{'text': c.sentence, 'label': c.label} for c in chosen],
    )


# ─── Per-question explanation from stored fields ────────────────────────

def stored_rich_explanation(question, *, selected_answer: str = '') -> Optional[dict]:
    """An explain-after-answer shaped dict built only from a question's
    stored (curated) fields, or None when it has no usable explanation."""
    why_correct = ''
    for name in ('admin_explanation_override', 'why_correct', 'explanation'):
        value = getattr(question, name, '') or ''
        if not is_unusable_text(value):
            why_correct = value.strip()
            break
    if not why_correct:
        return None
    correct = (getattr(question, 'correct_answer', '') or '').strip().upper()[:1]
    why_wrong = {}
    for letter in 'ABCD':
        if letter == correct:
            continue
        value = getattr(question, f'why_wrong_{letter.lower()}', '') or ''
        if not is_unusable_text(value):
            why_wrong[letter] = value.strip()
    mnemonic = ''
    for name in ('admin_mnemonic_override', 'mnemonic', 'ai_mnemonic'):
        value = getattr(question, name, '') or ''
        if not is_unusable_text(value):
            mnemonic = value.strip()
            break
    subject = getattr(question, 'subject', None)
    topic = getattr(question, 'topic', None)
    return {
        'ai_verified_answer': correct,
        'answer_mismatch': False,
        'confidence_note': '',
        'why_correct': why_correct,
        'why_wrong': why_wrong,
        'textbook_reference': {
            'book': getattr(question, 'book_name', '') or '',
            'chapter': getattr(question, 'chapter', '') or '',
            'page': getattr(question, 'page_number', '') or '',
            'section': '',
        },
        'mnemonic': mnemonic,
        'core_concept': '',
        'topic_deep_dive': (getattr(question, 'concept_explanation', '') or '').strip(),
        'key_differentiators': [],
        'category': public_subject(getattr(subject, 'name', '') or ''),
        'sub_category': getattr(topic, 'name', '') or '',
        'question_type': '',
        'around_concepts': [],
        'high_yield_points': [],
        'clinical_pearl': (getattr(question, 'ai_clinical_pearl', '') or '').strip(),
        'exam_tip': ((getattr(question, 'shortcut_tip', '') or '')
                     or (getattr(question, 'learning_technique', '') or '')).strip(),
        'quick_revision': '',
        'pyq_frequency': '',
        'similar_pyq': '',
        'citations': [],
        'is_correct': bool(selected_answer) and selected_answer == correct,
    }
