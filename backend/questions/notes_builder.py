"""PYQ-first topic notes (2026-11, docs/audit/MEDICAL_ACCURACY_DESIGN.md, pyq-notes map design A).

A note is built from the previous-year questions (PYQs) of one subject or topic, without a
language model:

1. ``candidate_questions``: active, dated PYQs of the note's exam(s) and subject / topic.
2. ``questions.key_status.key_statuses``: verified / provisional / excluded keys.
3. ``group_repeats``: questions that recur (duplicate cluster, same concept id or stem hash, or
   the same answer with similar stems) become one point; the number of sittings is its
   frequency, the high-yield signal.
4. ``make_point``: a template fact ``<stem> -> **<answer>**`` that cites its questions as [Q#]
   links with "asked in" labels (exam, year, paper); a point whose key is not verified carries
   the warning mark. Questions whose answer means nothing without the options or an image are
   listed as "Practise these PYQs" links without an answer.
5. ``attach_evidence``: at most one verbatim supporting sentence per fact, from
   ``reference_corpus.api.search`` (tiers 1-3, the quote checked against the stored passage);
   none when the reference store is unavailable. AI output is never a source.
6. ``sectionize`` / ``render_markdown``: "Most repeated" first, then sections by topic or
   recurring concept tag.
7. Optional ``compose_with_llm`` rewrite (never under AI_OFFLINE_MODE): every bullet must cite
   known facts, may not add numbers, and keeps the warning mark; otherwise the extractive
   version is used. ``structured`` always stays the extractive note.

The builder never publishes a note and never changes an answer key. Notes are marked stale when
a cited question changes (``on_question_changed``, called by questions.content_hooks), and the
read path hides points whose questions changed since the build (``source_state``).
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from questions import key_status as ks
from questions.content_hashes import stem_hash, valid_key

logger = logging.getLogger(__name__)

# pyq-notes/2: every point lists its source questions (``sources``: id, asked-in label, year, exam,
# key status), so readers can show and link each PYQ. Notes built by /1 rebuild on the next run.
BUILDER_VERSION = 'pyq-notes/2'
CATCH_ALL_TOPICS = frozenset({'general', 'imported', 'expert curated', 'misc', 'miscellaneous', 'other', 'others'})
MIN_PYQS = 3
MAX_CANDIDATES = 2000          # questions read for one note (safety cap)
MAX_POINTS = 250               # points kept in one note (most repeated / verified / latest first)
MAX_EVIDENCE_LOOKUPS = 120     # reference searches per note
MAX_LLM_FACTS = 60             # larger notes stay extractive
LLM_MIN_SURVIVAL = 0.7
STEM_CHARS = 220
ANSWER_CHARS = 160
WHY_CHARS = 240
REPEAT_DICE = 0.5
MAX_LINKS = 6
MAX_ASKED_IN = 6
EXAMS = ('cms', 'neet_pg', 'ini_cet')
MODES = ('extractive', 'llm', 'auto')
LEVELS = ('subject', 'topic')
EVIDENCE_TIERS = (1, 2, 3)
MARK = '⚠'
EXAM_LABELS = {'cms': 'UPSC CMS', 'neet_pg': 'NEET PG', 'ini_cet': 'INI-CET', 'all': 'all exams'}
SHORT_EXAM_LABELS = {'cms': 'CMS', 'neet_pg': 'NEET PG', 'ini_cet': 'INI-CET', 'usmle': 'USMLE', 'fmge': 'FMGE'}

# Words that frame a question rather than say what it is about (repeat matching, evidence anchors).
_BOILERPLATE = frozenset("""
consider given above below select code using list match pair option options answer choose best likely
least year old question questions mcq one two three four
""".split())
_GENERIC_ANSWER_RE = re.compile(
    r'^(?:all|none|both|neither)\b'
    r'|^(?:only )?(?:[1-9]|i{1,3}|iv|vi{0,3}|ix|x)(?:(?: ?, ?| and | & | or | nor )(?:[1-9]|i{1,3}|iv|vi{0,3}|ix|x))*(?: only)?$'
    r'|^[a-e](?:(?: ?, ?| and | & )[a-e])+$'
    # an order or match of numbered / lettered statements: "4 → 3 → 1 → 2", "B-D-A-C", "ii > i > iii"
    r'|^(?:[1-9]|[a-e]|i{1,3}|iv|vi{0,3}|ix|x)(?:\s*(?:→|->|>|-|–|—)\s*(?:[1-9]|[a-e]|i{1,3}|iv|vi{0,3}|ix|x))+$'
    r'|\bboth a and r\b|\b(?:a|r) (?:is|are) (?:true|false|correct|incorrect)\b'
    r'|^\(?[a-e]\)?\s*[-–:]\s*\(?\d',
    re.IGNORECASE,
)
_LEADING_NUMBER_RE = re.compile(r'^\s*(?:q(?:uestion)?\.?\s*)?\d{1,3}\s*[.):]\s+', re.IGNORECASE)
_IMG_TOKEN_RE = re.compile(r'\[\[img:\d+\]\]')
_TAG_RE = re.compile(r'<[^<>]{0,400}>')
_MD_SPECIAL_RE = re.compile(r'([\\`*_\[\]<>])')
_PYQ_TAG_RE = re.compile(r'^pyq[_ -]?\d{4}', re.IGNORECASE)
_SKIP_TAGS = frozenset({'high_yield', 'high yield', 'pyq', 'important', 'repeated', 'recall', 'imported',
                        'expert curated', 'general', 'misc', 'miscellaneous', 'cms', 'neet pg', 'neet_pg',
                        'ini-cet', 'ini_cet', 'inicet', 'upsc cms'})


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def builder_enabled() -> bool:
    """TOPIC_NOTES_BUILDER (setting, else env; default off): the topic-note generate endpoints
    delegate to this builder and the build / sources / published-detail routes answer."""
    value = getattr(settings, 'TOPIC_NOTES_BUILDER', None)
    if value is None:
        value = os.getenv('TOPIC_NOTES_BUILDER', '0')
    return _truthy(value)


def ai_offline() -> bool:
    from ai_engine.offline import ai_offline_mode
    return ai_offline_mode()


# ─── Text helpers ───────────────────────────────────────────────────────────

_CP437_TRIPLET_RE = re.compile('Γ..', re.DOTALL)


def repair_cp437_triplets(text: str) -> str:
    """'ΓåÆ' -> '→', 'Γéé' -> '₂', 'ΓÇÖ' -> '’': the UTF-8 bytes of a U+2000-U+2FFF character
    (arrows, sub/superscripts, punctuation, math signs) read as cp437 by an importer, a family
    questions.text_encoding's table does not list. A triplet is replaced only when it round-trips
    to exactly one such character, so real Greek text is left alone."""
    if 'Γ' not in text:
        return text

    def _sub(match):
        chunk = match.group(0)
        try:
            char = chunk.encode('cp437').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return chunk
        return char if len(char) == 1 and 0x2000 <= ord(char) <= 0x2FFF else chunk

    return _CP437_TRIPLET_RE.sub(_sub, text)


def _plain(text) -> str:
    """Public text without HTML tags, image tokens and extra whitespace (mojibake repaired)."""
    from questions.text_encoding import normalize_text
    text = repair_cp437_triplets(normalize_text(text or '')) if isinstance(text, str) else ''
    text = _IMG_TOKEN_RE.sub(' ', text)
    text = _TAG_RE.sub(' ', text)
    return ' '.join(text.split())


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if ' ' in cut[limit // 2:]:
        cut = cut[:cut.rfind(' ')]
    return cut.rstrip(' ,;:-') + '…'


def clean_stem(text) -> str:
    """The stem as a note shows it: up to its first answer label, without correctness flags, the
    leading question number, HTML and image tokens; a long stem keeps its start and its question."""
    from questions.answer_leak import redact_stem_text
    text = _plain(redact_stem_text(text or '') if isinstance(text, str) else '')
    text = _LEADING_NUMBER_RE.sub('', text).strip()
    if len(text) <= STEM_CHARS:
        return text
    head = _cut(text[:150], 140).rstrip('…').rstrip()
    tail = text[-70:]
    if ' ' in tail:
        tail = tail[tail.find(' ') + 1:]
    return f'{head} … {tail}'.strip()


def clean_answer(text) -> str:
    from questions.answer_leak import cut_option_text
    text = cut_option_text(text or '') if isinstance(text, str) else ''
    text = re.sub(r'^\(?[A-Da-d][.)]\s+', '', _plain(text))
    return _cut(text, ANSWER_CHARS)


def is_generic_answer(text) -> bool:
    """True when the answer text means nothing without the options / statements ("All of the
    above", "1 and 2 only", "Both A and R are true ...", match codes, a bare letter)."""
    norm = ' '.join(str(text or '').lower().split()).strip(' .;:')
    return len(norm) <= 2 or bool(_GENERIC_ANSWER_RE.search(norm))


def _md(text) -> str:
    """Escape the markdown / HTML characters of imported text."""
    return _MD_SPECIAL_RE.sub(r'\\\1', text or '')


def _ws(text) -> str:
    return ' '.join((text or '').split())


def _terms(text) -> set:
    from ai_engine.lexical_index import tokenize
    return {t for t in tokenize(text or '') if t not in _BOILERPLATE and not t.isdigit()}


def _dice(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def public_subject_label(name) -> str:
    from questions.serializers import public_subject_name
    return public_subject_name(name or '') or ''


# ─── Scope and candidates ───────────────────────────────────────────────────

def note_exam_types(note) -> tuple:
    if getattr(note, 'is_combined', False) or getattr(note, 'exam_type', '') == 'all':
        return EXAMS
    return (note.exam_type,)


def is_catch_all_topic(topic) -> bool:
    name = (getattr(topic, 'name', '') or '').strip().lower()
    return not name or name in CATCH_ALL_TOPICS


def note_scope(note) -> dict:
    """``{subject_id, topic_id, exam_types, level}`` the builder reads for ``note``. A note filed
    under a catch-all topic ("General", "Imported", ...) is built from its whole subject."""
    topic = note.topic if getattr(note, 'topic_id', None) else None
    subject_id = getattr(note, 'subject_id', None) or getattr(topic, 'subject_id', None)
    topic_id = topic.pk if topic is not None and not is_catch_all_topic(topic) else None
    return {
        'subject_id': subject_id,
        'topic_id': topic_id,
        'exam_types': note_exam_types(note),
        'level': 'topic' if topic_id else 'subject',
    }


_CANDIDATE_FIELDS = ks.QUESTION_FIELDS + (
    'year', 'paper', 'session', 'exam_type', 'subject_id', 'topic_id', 'concept_id', 'concept_tags',
    'recall_text_hash', 'updated_at', 'explanation_status', 'explanation_for_key', 'explanation_stem_hash',
    'admin_explanation_override', 'why_correct',
)


def candidate_questions(*, subject_id=None, topic_id=None, exam_types=EXAMS, limit=MAX_CANDIDATES) -> list:
    """Active, dated PYQs (year > 0, not dropped) of ``exam_types`` in the topic / subject, newest first."""
    from questions.models import Question

    qs = Question.objects.filter(is_active=True, is_dropped=False, year__gt=0, exam_type__in=tuple(exam_types))
    if topic_id:
        qs = qs.filter(topic_id=topic_id)
    elif subject_id:
        qs = qs.filter(subject_id=subject_id)
    else:
        return []
    qs = qs.select_related('subject', 'topic').only(
        *_CANDIDATE_FIELDS, 'subject__id', 'subject__name', 'subject__code', 'topic__id', 'topic__name',
    ).order_by('-year', 'id')
    return list(qs[:limit])


# ─── Points ─────────────────────────────────────────────────────────────────

def _sitting(q) -> tuple:
    paper = q.paper if q.exam_type == 'cms' and q.paper in (1, 2) else 0
    session = (q.session or '').strip().lower()
    return (q.exam_type, q.year, paper, '' if session == 'none' else session)


def asked_in_label(q) -> str:
    """'CMS 2019 P1', 'NEET PG 2021 (recall)', 'INI-CET 2023 May'."""
    exam, year, paper, session = _sitting(q)
    parts = [SHORT_EXAM_LABELS.get(exam, (exam or '').upper()), str(year)]
    if paper:
        parts.append(f'P{paper}')
    if session:
        parts.append(session.capitalize())
    label = ' '.join(parts)
    if (q.recall_status or '') == 'recall':
        label += ' (recall)'
    return label


def _option_set(q) -> frozenset:
    return frozenset(ks._norm_answer(getattr(q, f'option_{letter}', '')) for letter in 'abcd')


def group_repeats(questions) -> list:
    """Union-find over the questions: a shared duplicate cluster, the same stem with the same
    options (in any order), or the same specific answer text with stems sharing half their terms
    (Dice >= 0.5). A shared concept id only groups points into a section (related PYQs can have
    different answers), and a generic stem ("Which of the following is correct?") with other
    options is a different question."""
    from questions.models import DuplicateCluster, DuplicateMember, compute_stem_hash

    questions = list(questions)
    by_id = {q.pk: q for q in questions}
    parent = {qid: qid for qid in by_id}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    def union_all(ids):
        ids = [qid for qid in ids if qid in by_id]
        for other in ids[1:]:
            union(ids[0], other)

    ids = list(by_id)
    clusters = defaultdict(list)
    if ids:
        for cluster_id, question_id in DuplicateMember.objects.filter(question_id__in=ids).values_list(
                'cluster_id', 'question_id'):
            clusters[cluster_id].append(question_id)
        for cluster_id, question_id in DuplicateCluster.objects.filter(canonical_question_id__in=ids).values_list(
                'id', 'canonical_question_id'):
            clusters[cluster_id].append(question_id)
    for members in clusters.values():
        union_all(members)

    keyed = defaultdict(list)
    for q in questions:
        keyed[(compute_stem_hash(q.question_text or ''), _option_set(q))].append(q.pk)
    for members in keyed.values():
        union_all(members)

    by_answer = defaultdict(list)
    for q in questions:
        answer = ks._norm_answer(ks.correct_option_text(q))
        if len(answer) >= 3 and not is_generic_answer(answer):
            by_answer[answer].append(q)
    for members in by_answer.values():
        if len(members) < 2:
            continue
        terms = {q.pk: _terms(clean_stem(q.question_text)) for q in members}
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if _dice(terms[a.pk], terms[b.pk]) >= REPEAT_DICE:
                    union(a.pk, b.pk)

    groups = defaultdict(list)
    for q in questions:
        groups[find(q.pk)].append(q)
    out = [sorted(members, key=lambda q: (-q.year, q.pk)) for members in groups.values()]
    out.sort(key=lambda members: (-max(q.year for q in members), members[0].pk))
    return out


def _reviewed_why(q) -> str:
    """First sentence of the curated explanation, only when it was reviewed / source-verified for
    the key and stem the question has now (explanation provenance, questions.editorial)."""
    if (getattr(q, 'explanation_status', '') or '') not in ('source_verified', 'reviewed'):
        return ''
    key = valid_key(q.correct_answer)
    if not key or valid_key(getattr(q, 'explanation_for_key', '')) != key:
        return ''
    if (getattr(q, 'explanation_stem_hash', '') or '') != stem_hash(q):
        return ''
    from ai_engine.lexical_index import iter_sentences
    from ai_engine.offline import is_unusable_text
    for name in ('admin_explanation_override', 'explanation', 'why_correct'):
        text = getattr(q, name, '') or ''
        if isinstance(text, str) and not is_unusable_text(text):
            for sentence in iter_sentences(_plain(text)):
                return _cut(sentence, WHY_CHARS)
    return ''


def _point_tags(members, stop_tags: set) -> list:
    tags = Counter()
    for q in members:
        values = q.concept_tags if isinstance(q.concept_tags, list) else []
        for tag in values[:8]:
            if not isinstance(tag, str):
                continue
            norm = ' '.join(tag.strip().lower().replace('_', ' ').split())
            if (len(norm) < 3 or len(norm) > 60 or norm in stop_tags or norm in _SKIP_TAGS
                    or _PYQ_TAG_RE.match(norm)):
                continue
            tags[norm] += 1
    return [tag for tag, _n in tags.most_common(4)]


def make_point(members, statuses: dict, *, include_provisional=True, stop_tags=frozenset()):
    """``(point, '')`` for one group of repeated questions, or ``(None, reason)`` when the group
    cannot be stated (its members disagree on the answer)."""
    answers = {ks._norm_answer(ks.correct_option_text(q)) for q in members}
    if len(answers) > 1:
        return None, 'repeat_key_conflict'
    canonical = sorted(members, key=lambda q: (
        ks.needs_image(q), statuses[q.pk].status != ks.VERIFIED, -q.year, q.pk))[0]
    verified = all(statuses[q.pk].status == ks.VERIFIED for q in members)
    stem = clean_stem(canonical.question_text)
    answer = clean_answer(ks.correct_option_text(canonical))
    kind, practice_reason = 'fact', ''
    if ks.needs_image(canonical):
        kind, practice_reason = 'practice', 'image'
    elif not stem or not answer or is_generic_answer(answer):
        kind, practice_reason = 'practice', 'needs_options'
    elif not verified and not include_provisional:
        kind, practice_reason = 'practice', 'provisional_hidden'
    sittings = {}
    for q in members:
        sittings.setdefault(_sitting(q), asked_in_label(q))
    asked = [label for _key, label in sorted(sittings.items(), key=lambda kv: (-kv[0][1], kv[1]))]
    topic = canonical.topic if canonical.topic_id else None
    point = {
        'kind': kind,
        'practice_reason': practice_reason,
        'stem': stem,
        'answer': answer if kind == 'fact' else '',
        'key_status': ks.VERIFIED if verified else ks.PROVISIONAL,
        'reasons': sorted({statuses[q.pk].reason for q in members if statuses[q.pk].status != ks.VERIFIED}),
        'question_ids': [q.pk for q in members],
        # One entry per source question (members are newest first): what a reader shows and links.
        'sources': [{'id': q.pk, 'label': asked_in_label(q), 'year': q.year, 'exam_type': q.exam_type,
                     'key_status': statuses[q.pk].status} for q in members],
        'primary_id': canonical.pk,
        'asked_in': asked,
        'frequency': len(sittings),
        'latest_year': max(q.year for q in members),
        'why': _reviewed_why(canonical) if (verified and kind == 'fact') else '',
        'evidence': [],
        '_concept': next((q.concept_id.strip() for q in members if (q.concept_id or '').strip()), ''),
        '_topic': '' if topic is None or is_catch_all_topic(topic) else topic.name.strip(),
        '_tags': _point_tags(members, stop_tags),
    }
    return point, ''


def _rank_key(point) -> tuple:
    return (-point['frequency'], point['kind'] != 'fact', point['key_status'] != ks.VERIFIED,
            -point['latest_year'], point['primary_id'])


# ─── Evidence (reference corpus) ────────────────────────────────────────────

def reference_api():
    """``reference_corpus.api`` when it is installed and has ``search``; else None."""
    try:
        from reference_corpus import api
    except Exception:  # noqa: BLE001 - the reference corpus is optional
        return None
    return api if callable(getattr(api, 'search', None)) else None


def evidence_state(api=None, *, enabled=True) -> str:
    """'on' when the reference store can be searched; 'off' / 'unavailable' / 'no_store' / 'error'."""
    if not enabled:
        return 'off'
    api = api if api is not None else reference_api()
    if api is None:
        return 'unavailable'
    try:
        available = api.store_available() if callable(getattr(api, 'store_available', None)) else False
    except Exception:  # noqa: BLE001
        logger.warning('notes builder: reference store check failed', exc_info=True)
        return 'error'
    return 'on' if available else 'no_store'


def supporting_sentence(stem: str, answer: str, passage_text: str) -> Optional[str]:
    """The sentence of ``passage_text`` that states the answer: it contains at least half of the
    answer's distinctive terms (>= 4 letters) and shares terms with the stem. Verbatim, or None."""
    from ai_engine.lexical_index import iter_sentences
    anchors = {t for t in _terms(answer) if len(t) >= 4}
    if not anchors:
        return None
    needed = max(1, math.ceil(len(anchors) / 2))
    stem_terms = _terms(stem) - anchors
    min_overlap = 2 if len(stem_terms) >= 4 else 1
    best = None
    for sentence in iter_sentences(passage_text or ''):
        if not 40 <= len(sentence) <= 600:
            continue
        terms = _terms(sentence)
        hits = len(anchors & terms)
        overlap = len(stem_terms & terms)
        if hits < needed or overlap < min_overlap:
            continue
        score = overlap + 2.0 * hits / len(anchors)
        if best is None or score > best[0]:
            best = (score, sentence)
    return best[1] if best else None


def _quote_on_page(api, sha256: str, page_start: int, page_end: int, quote: str) -> Optional[bool]:
    """True / False when the page text can be read, None when it cannot."""
    page_text = getattr(api, 'page_text', None)
    if not callable(page_text):
        return None
    needle = _ws(quote)
    seen = False
    for page_no in range(page_start, min(page_end, page_start + 2) + 1):
        try:
            page = page_text(sha256, page_no)
        except Exception:  # noqa: BLE001
            return None
        if isinstance(page, dict) and isinstance(page.get('text'), str):
            seen = True
            if needle in _ws(page['text']):
                return True
    return False if seen else None


def evidence_label(entry: dict) -> str:
    """'Title, edition, p. <label>' / 'Title, PDF p. N' (questions show the printed page label
    when it is known, else the physical PDF page)."""
    title = (entry.get('title') or 'Reference').strip()
    edition = (entry.get('edition') or '').strip()
    label = (entry.get('page_label') or '').strip()
    head = f'{title}, {edition}' if edition else title
    if label:
        return f'{head}, p. {label}'
    if entry.get('page_start'):
        return f'{head}, PDF p. {entry["page_start"]}'
    return head


def _snippet_limit() -> int:
    return int(getattr(settings, 'EVIDENCE_SNIPPET_MAX_CHARS', 240) or 240)


def evidence_for_point(point: dict, api) -> Optional[dict]:
    """One verified supporting sentence for a fact point, or None."""
    query = f"{point['stem']} {point['answer']}"[:1000]
    try:
        hits = api.search(query, k=5, tiers=EVIDENCE_TIERS, exclude_question_id=point['primary_id']) or []
    except Exception:  # noqa: BLE001 - retrieval failing never blocks a build
        logger.warning('notes builder: reference search failed', exc_info=True)
        return None
    limit = _snippet_limit()
    for hit in hits:
        if not isinstance(hit, dict) or hit.get('retrieval_mode') == 'legacy':
            continue
        source = hit.get('source') or {}
        tier, sha256, page_start = source.get('tier'), (source.get('sha256') or '').strip(), hit.get('page_start')
        if not isinstance(tier, int) or tier not in EVIDENCE_TIERS or not sha256 or not isinstance(page_start, int):
            continue
        if source.get('student_display') is False:
            continue
        text = hit.get('text') or ''
        sentence = supporting_sentence(point['stem'], point['answer'], text)
        if not sentence or _ws(sentence) not in _ws(text):
            continue
        page_end = hit.get('page_end') if isinstance(hit.get('page_end'), int) else page_start
        if _quote_on_page(api, sha256, page_start, page_end, sentence) is False:
            continue
        quote = _ws(sentence)
        excerpt = quote if len(quote) <= limit else _cut(quote, limit).rstrip('…')
        entry = {
            'source_sha256': sha256,
            'title': (source.get('title') or '').strip(),
            'edition': (source.get('edition') or '').strip() if isinstance(source.get('edition'), str) else '',
            'year': source.get('year'),
            'tier': tier,
            'page_start': page_start,
            'page_end': page_end,
            'page_label': (hit.get('page_label') or '').strip() if isinstance(hit.get('page_label'), str) else '',
            'section': (hit.get('section') or '')[:200] if isinstance(hit.get('section'), str) else '',
            'chunk_key': str(hit.get('chunk_key') or ''),
            'excerpt': excerpt,
            'truncated': len(excerpt) < len(quote),
            'quote_sha256': hashlib.sha256(quote.encode('utf-8')).hexdigest(),
        }
        entry['label'] = evidence_label(entry)
        return entry
    return None


def attach_evidence(points, *, api=None, state=None) -> str:
    """Add one supporting sentence to fact points (ranked order, up to MAX_EVIDENCE_LOOKUPS
    searches); returns the evidence state."""
    api = api if api is not None else reference_api()
    state = state or evidence_state(api)
    if state != 'on':
        return state
    lookups = 0
    for point in points:
        if point['kind'] != 'fact':
            continue
        if lookups >= MAX_EVIDENCE_LOOKUPS:
            break
        lookups += 1
        entry = evidence_for_point(point, api)
        if entry:
            point['evidence'] = [entry]
    return state


# ─── Sections and rendering ─────────────────────────────────────────────────

_KEY_PRIORITY = {'concept': 0, 'topic': 1, 'tag': 2}


def _section_title(key) -> str:
    kind, value = key
    if kind == 'topic':
        return value
    value = ' '.join(value.replace('_', ' ').replace('-', ' ').split()) if kind == 'concept' else value
    return value[:1].upper() + value[1:]


def sectionize(points, *, topic_level: bool) -> list:
    """Sections: 'Most repeated' (asked in two or more sittings), then one per concept id, topic
    (subject notes) or recurring concept tag with at least two points, 'Other PYQs', and
    'Practise these PYQs' (questions shown without an answer). Within a section: most repeated,
    then verified, then latest."""
    facts = [p for p in points if p['kind'] == 'fact']
    practice = [p for p in points if p['kind'] != 'fact']
    repeated = [p for p in facts if p['frequency'] >= 2]
    rest = [p for p in facts if p['frequency'] < 2]

    support = Counter()
    for p in rest:
        keys = [('concept', p['_concept'])] if p['_concept'] else []
        if p['_topic'] and not topic_level:
            keys.append(('topic', p['_topic']))
        keys += [('tag', t) for t in p['_tags']]
        p['_keys'] = keys
        for key in set(keys):
            support[key] += 1
    buckets = defaultdict(list)
    other = []
    for p in rest:
        keys = [k for k in p['_keys'] if support[k] >= 2]
        if not keys:
            other.append(p)
            continue
        best = sorted(keys, key=lambda k: (-support[k], _KEY_PRIORITY[k[0]], k[1]))[0]
        buckets[best].append(p)

    def ordered(items):
        return [p['id'] for p in sorted(items, key=_rank_key)]

    sections = []
    if repeated:
        sections.append({'title': 'Most repeated', 'kind': 'repeated', 'points': ordered(repeated)})
    for key, items in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), _KEY_PRIORITY[kv[0][0]], kv[0][1])):
        sections.append({'title': _section_title(key), 'kind': key[0], 'points': ordered(items)})
    if other:
        sections.append({'title': 'Other PYQs' if sections else 'Asked in PYQs', 'kind': 'other',
                         'points': ordered(other)})
    if practice:
        sections.append({'title': 'Practise these PYQs', 'kind': 'practice', 'points': ordered(practice)})
    for index, section in enumerate(sections, start=1):
        section['id'] = f's{index}'
    for p in points:
        for name in ('_keys', '_concept', '_topic', '_tags'):
            p.pop(name, None)
    return sections


def _links(point) -> str:
    ids = point['question_ids']
    links = ' '.join(f'[Q{qid}](/practice?id={qid})' for qid in ids[:MAX_LINKS])
    return links + (f' (+{len(ids) - MAX_LINKS} more)' if len(ids) > MAX_LINKS else '')


def _asked(point) -> str:
    labels = point['asked_in'][:MAX_ASKED_IN]
    text = ', '.join(labels) + (' …' if len(point['asked_in']) > MAX_ASKED_IN else '')
    return f"asked {point['frequency']}× ({text})" if point['frequency'] > 1 else f'asked in {text}'


def render_point(point, *, provisional=False) -> list:
    if point['kind'] != 'fact':
        note = ' (image-based)' if point.get('practice_reason') == 'image' else ''
        return [f"- Practise: {_md(_cut(point['stem'], 140))}{note} — {_asked(point)} {_links(point)}"]
    mark = f'{MARK} ' if (provisional or point['key_status'] != ks.VERIFIED) else ''
    lines = [f"- {mark}{_md(point['stem'])} → **{_md(point['answer'])}** — {_asked(point)} {_links(point)}"]
    if point.get('why'):
        lines.append(f"  - Why: {_md(point['why'])}")
    for entry in (point.get('evidence') or [])[:1]:
        ellipsis = '…' if entry.get('truncated') else ''
        lines.append(f"  - Textbook: \"{_md(entry['excerpt'])}{ellipsis}\" — *{_md(entry.get('label') or evidence_label(entry))}*")
    return lines


def header_lines(structured: dict, *, locked_points=0, hidden_points=0) -> list:
    counts = structured.get('counts') or {}
    lines = [
        f"> Built from {counts.get('cited', 0)} PYQs ({structured.get('exam_label', '')}): "
        f"{counts.get('verified', 0)} verified, {counts.get('provisional', 0)} provisional. "
        f"{MARK} = answer key not yet verified.",
    ]
    if locked_points:
        lines.append(f'> {locked_points} more point{"s" if locked_points != 1 else ""} with Premium.')
    if hidden_points:
        lines.append(f'> {hidden_points} point{"s are" if hidden_points != 1 else " is"} hidden until this note '
                     f'is rebuilt (a source question changed).')
    return lines


def render_markdown(structured: dict, *, visible=None, provisional_now=(), locked_points=0, hidden_points=0) -> str:
    """Markdown of the note (``visible``: the point ids to show, None = all)."""
    points = {p['id']: p for p in structured.get('points') or []}
    lines = header_lines(structured, locked_points=locked_points, hidden_points=hidden_points)
    for section in structured.get('sections') or []:
        ids = [pid for pid in section.get('points') or [] if pid in points and (visible is None or pid in visible)]
        if not ids:
            continue
        lines += ['', f"## {_md(section['title'])}"]
        for pid in ids:
            lines += render_point(points[pid], provisional=pid in provisional_now)
    return '\n'.join(lines).strip() + '\n'


# ─── Optional LLM rewrite ───────────────────────────────────────────────────

_CITE_RE = re.compile(r'\[\s*F\d+(?:\s*[,;]\s*F?\d+)*\s*\]', re.IGNORECASE)
_NUMBER_RE = re.compile(r'\d+(?:\.\d+)?')
_BULLET_RE = re.compile(r'^(?:[-*•]|\d{1,2}[.)])\s+(.*)$')


def llm_prompt(facts: list, *, topic_name: str, subject_label: str, exam_label: str) -> str:
    lines = []
    for fact in facts:
        status = 'VERIFIED' if fact['key_status'] == ks.VERIFIED else f'PROVISIONAL {MARK}'
        line = f"{fact['fid']} [{status}] {fact['stem']} -> {fact['answer']} (asked in {', '.join(fact['asked_in'])})"
        for entry in fact.get('evidence') or []:
            line += f'; textbook: "{entry["excerpt"]}" ({entry.get("label", "")})'
        lines.append(line)
    return (
        'You are writing revision notes for a medical entrance exam from previous-year questions (PYQs).\n'
        f'Topic: "{topic_name}" (Subject: {subject_label}), {exam_label}.\n\n'
        'Use ONLY the facts below. Rules:\n'
        '- Every bullet cites the facts it uses as [F1], [F2]; never write a bullet without a citation.\n'
        f'- Start every bullet that cites a PROVISIONAL fact with {MARK}.\n'
        '- Do not add numbers, doses, drugs, names or claims that the cited facts do not state.\n'
        '- Leave out anything uncertain; no introduction and no conclusion.\n'
        '- Group related bullets under short "## " headings. Output markdown only.\n\n'
        'Facts:\n' + '\n'.join(lines)
    )


def validate_llm_markdown(text: str, facts: dict):
    """``(markdown | None, stats)``: bullets that cite unknown facts or add numbers are dropped,
    the warning mark is forced on bullets citing provisional facts, [F#] become [Q#] links, prose
    and numbered headings are dropped. None when fewer than 70 % of the bullets survive."""
    kept, total, survived = [], 0, 0
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            heading = _plain(line.lstrip('#').strip())
            if heading and len(heading) <= 80 and not re.search(r'\d', heading):
                kept += ['', f'## {_md(heading)}']
            continue
        match = _BULLET_RE.match(line)
        if not match:
            continue
        total += 1
        body = _plain(match.group(1))
        cited = []
        for group in _CITE_RE.findall(body):
            cited += [f'F{n}' for n in re.findall(r'\d+', group)]
        if not cited or any(fid not in facts for fid in cited):
            continue
        claim = _CITE_RE.sub(' ', body).replace(MARK, ' ')
        allowed = set()
        for fid in cited:
            fact = facts[fid]
            source_text = ' '.join([fact['stem'], fact['answer'], ' '.join(fact['asked_in'])]
                                   + [entry.get('excerpt', '') for entry in fact.get('evidence') or []])
            allowed |= set(_NUMBER_RE.findall(source_text))
        if set(_NUMBER_RE.findall(claim)) - allowed:
            continue
        provisional = any(facts[fid]['key_status'] != ks.VERIFIED for fid in cited)
        links = []
        for fid in dict.fromkeys(cited):
            links += [qid for qid in facts[fid]['question_ids'] if qid not in links]
        link_text = ' '.join(f'[Q{qid}](/practice?id={qid})' for qid in links[:MAX_LINKS])
        claim = _md(' '.join(claim.split()).strip(' -–—'))
        if not claim:
            continue
        kept.append(f"- {MARK + ' ' if provisional else ''}{claim} {link_text}".rstrip())
        survived += 1
    stats = {'bullets': total, 'kept': survived}
    if not survived or survived < LLM_MIN_SURVIVAL * total:
        return None, stats
    return '\n'.join(kept).strip(), stats


def compose_with_llm(structured: dict, *, topic_name: str, subject_label: str, exam_label: str):
    """``(markdown | None, warnings)``. Never under AI_OFFLINE_MODE; any failure -> None."""
    if ai_offline():
        return None, ['llm_skipped_offline_mode']
    points = [p for p in structured.get('points') or [] if p['kind'] == 'fact']
    if not points:
        return None, ['llm_skipped_no_facts']
    if len(points) > MAX_LLM_FACTS:
        return None, ['llm_skipped_too_many_facts']
    facts = {}
    for index, point in enumerate(points, start=1):
        facts[f'F{index}'] = {**point, 'fid': f'F{index}'}
    prompt = llm_prompt(list(facts.values()), topic_name=topic_name, subject_label=subject_label, exam_label=exam_label)
    try:
        from ai_engine.services import AIService
        from questions.ai_per_question import usable_ai_text
        text = usable_ai_text(AIService()._call_ai(prompt, max_tokens=3000, temperature=0.2))
    except Exception:  # noqa: BLE001 - AIUnavailable or a provider error: extractive fallback
        logger.info('notes builder: LLM rewrite unavailable, using the extractive note', exc_info=True)
        return None, ['llm_unavailable']
    if not text:
        return None, ['llm_unavailable']
    markdown, stats = validate_llm_markdown(text, facts)
    if markdown is None:
        return None, [f"llm_validation_failed ({stats['kept']}/{stats['bullets']} bullets usable)"]
    lines = header_lines(structured) + ['', markdown]
    practice = [p for p in structured.get('points') or [] if p['kind'] != 'fact']
    if practice:
        lines += ['', '## Practise these PYQs']
        for point in practice:
            lines += render_point(point)
    return '\n'.join(lines).strip() + '\n', []


# ─── Build ──────────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    note_id: Optional[int] = None
    built: bool = False
    changed: bool = False
    method: str = 'extractive'
    fingerprint: str = ''
    counts: dict = field(default_factory=dict)
    counts_by_reason: dict = field(default_factory=dict)
    excluded: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    markdown: str = ''
    structured: dict = field(default_factory=dict)
    error: str = ''

    def summary(self) -> dict:
        return {
            'note_id': self.note_id, 'built': self.built, 'changed': self.changed, 'method': self.method,
            'fingerprint': self.fingerprint, 'counts': self.counts, 'counts_by_reason': self.counts_by_reason,
            'excluded': self.excluded[:200], 'warnings': self.warnings, 'error': self.error,
        }


def _fingerprint(candidates, statuses, *, mode, include_provisional, verified_only, ev_state) -> str:
    digest = hashlib.sha256(json.dumps(
        [BUILDER_VERSION, mode, bool(include_provisional), bool(verified_only), ev_state]).encode('utf-8'))
    for q in sorted(candidates, key=lambda q: q.pk):
        status = statuses[q.pk]
        updated = q.updated_at.isoformat() if q.updated_at else ''
        digest.update(f'{q.pk}|{q.correct_answer}|{status.status}|{status.reason}|{updated}\n'.encode('utf-8'))
    return digest.hexdigest()


def _stop_tags(note, scope) -> set:
    from questions.models import Subject
    stop = set()
    for name, code in Subject.objects.values_list('name', 'code'):
        stop.add((name or '').strip().lower())
        stop.add((code or '').strip().lower())
        stop.add(public_subject_label(name).strip().lower())
    if getattr(note, 'topic_id', None) and note.topic is not None:
        stop.add(note.topic.name.strip().lower())
    return {tag for tag in stop if tag}


def _label_for(note) -> str:
    return EXAM_LABELS.get('all' if (note.is_combined or note.exam_type == 'all') else note.exam_type, note.exam_type)


def build_topic_note(note, *, mode='extractive', include_provisional=True, verified_only=False, dry_run=False,
                     force=False, min_questions=MIN_PYQS, evidence=True, api=None, statuses=None) -> BuildResult:
    """Build (or, with ``dry_run``, only plan) ``note`` from its PYQs. Writes the note's content,
    structure, counts and TopicNoteSource rows in one transaction; never touches ``is_published``.
    ``statuses``: precomputed key statuses to reuse (management command)."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES}')
    result = BuildResult(note_id=getattr(note, 'pk', None))
    scope = note_scope(note)
    if not scope['subject_id'] and not scope['topic_id']:
        result.error = 'no_subject_or_topic'
        return result
    candidates = candidate_questions(subject_id=scope['subject_id'], topic_id=scope['topic_id'],
                                     exam_types=scope['exam_types'])
    known = statuses if statuses is not None else {}
    missing = [q for q in candidates if q.pk not in known]
    computed = ks.key_statuses(missing) if missing else {}
    known.update(computed)   # a shared cache (one command run) keeps them for the next note
    statuses = {q.pk: known[q.pk] for q in candidates}
    summary = ks.summarize(statuses)
    result.counts_by_reason = summary['reasons']
    usable = [q for q in candidates if statuses[q.pk].usable]
    skipped = []
    if verified_only:
        skipped = [q for q in usable if statuses[q.pk].status != ks.VERIFIED]
        usable = [q for q in usable if statuses[q.pk].status == ks.VERIFIED]
    result.counts = {'candidates': len(candidates), 'usable': len(usable), **{
        name: summary[name] for name in ks.STATUSES}}
    if len(usable) < max(1, int(min_questions or 1)):
        result.error = 'not_enough_pyqs'
        return result

    api = api if api is not None else (reference_api() if evidence else None)
    ev_state = evidence_state(api, enabled=evidence)
    fingerprint = _fingerprint(candidates, statuses, mode=mode, include_provisional=include_provisional,
                               verified_only=verified_only, ev_state=ev_state)
    result.fingerprint = fingerprint
    if (not force and getattr(note, 'pk', None) and note.source_fingerprint == fingerprint
            and note.builder_version == BUILDER_VERSION and not note.is_stale):
        result.built, result.changed = True, False
        result.method = note.generation_method
        result.markdown, result.structured = note.content, note.structured
        result.counts = (note.structured or {}).get('counts') or result.counts
        return result

    stop_tags = _stop_tags(note, scope)
    points, excluded = [], []
    for q in candidates:
        if not statuses[q.pk].usable:
            excluded.append({'question_id': q.pk, 'reason': statuses[q.pk].reason})
    for q in skipped:
        excluded.append({'question_id': q.pk, 'reason': 'provisional_skipped'})
    for members in group_repeats(usable):
        point, reason = make_point(members, statuses, include_provisional=include_provisional, stop_tags=stop_tags)
        if point is None:
            excluded += [{'question_id': q.pk, 'reason': reason} for q in members]
            continue
        points.append(point)
    points.sort(key=_rank_key)
    over_cap = points[MAX_POINTS:]
    points = points[:MAX_POINTS]
    for point in over_cap:
        excluded += [{'question_id': qid, 'reason': 'over_cap', 'cited': False} for qid in point['question_ids']]
    for index, point in enumerate(points, start=1):
        point['id'] = f'p{index}'
    ev_state = attach_evidence(points, api=api, state=ev_state) if ev_state == 'on' else ev_state
    sections = sectionize(points, topic_level=scope['level'] == 'topic')

    cited = [qid for point in points for qid in point['question_ids']]
    cited_status = Counter(statuses[qid].status for qid in cited)
    counts = {
        'candidates': len(candidates),
        'cited': len(cited),
        'verified': cited_status.get(ks.VERIFIED, 0),
        'provisional': cited_status.get(ks.PROVISIONAL, 0),
        'excluded': sum(1 for row in excluded if row['reason'] not in ('over_cap', 'provisional_skipped')),
        'over_cap': sum(1 for row in excluded if row['reason'] == 'over_cap'),
        'points': len(points),
        'facts': sum(1 for p in points if p['kind'] == 'fact'),
        'practice': sum(1 for p in points if p['kind'] != 'fact'),
        'repeated_points': sum(1 for p in points if p['frequency'] >= 2),
        'evidence_points': sum(1 for p in points if p['evidence']),
        'sections': len(sections),
    }
    subject = None
    if scope['subject_id']:
        from questions.models import Subject
        subject = Subject.objects.filter(pk=scope['subject_id']).only('id', 'name').first()
    topic = note.topic if scope['topic_id'] else None
    structured = {
        'builder_version': BUILDER_VERSION,
        'mode': mode,
        'include_provisional': bool(include_provisional),
        'verified_only': bool(verified_only),
        'exam_type': 'all' if (note.is_combined or note.exam_type == 'all') else note.exam_type,
        'exam_types': list(scope['exam_types']),
        'exam_label': _label_for(note),
        'level': scope['level'],
        'subject': {'id': scope['subject_id'], 'name': public_subject_label(getattr(subject, 'name', ''))},
        'topic': {'id': topic.pk, 'name': topic.name} if topic is not None else None,
        'counts': counts,
        'excluded_reasons': dict(sorted(Counter(row['reason'] for row in excluded).items())),
        'evidence_state': ev_state,
        'sections': sections,
        'points': points,
        'excluded': [{'question_id': row['question_id'], 'reason': row['reason']} for row in excluded],
    }
    markdown = render_markdown(structured)
    method = 'extractive'
    warnings = []
    if mode in ('llm', 'auto'):
        llm_markdown, llm_warnings = compose_with_llm(
            structured, topic_name=topic.name if topic is not None else 'All topics',
            subject_label=public_subject_label(getattr(subject, 'name', '')), exam_label=_label_for(note))
        warnings += llm_warnings
        if llm_markdown:
            markdown, method = llm_markdown, 'llm'
        elif mode == 'llm':
            warnings.append('llm_fallback_extractive')
    structured['method'] = method
    result.built, result.changed, result.method = True, True, method
    result.counts, result.excluded, result.warnings = counts, structured['excluded'], warnings
    result.markdown, result.structured = markdown, structured
    if not dry_run:
        _save_build(note, structured, markdown, method, fingerprint, statuses, points, excluded)
        result.note_id = note.pk
    return result


def _save_build(note, structured, markdown, method, fingerprint, statuses, points, excluded) -> None:
    from questions.models import Question, TopicNote, TopicNoteSource

    cited_ids = sorted({qid for point in points for qid in point['question_ids']})
    keys = dict(Question.objects.filter(pk__in=cited_ids).values_list('id', 'correct_answer'))
    preview = markdown if len(markdown) <= 300 else markdown[:300] + '...'
    counts = structured['counts']
    with transaction.atomic():
        note.content = markdown
        note.content_preview = preview
        note.structured = structured
        note.generation_method = method
        note.ai_generated = method == 'llm'
        note.builder_version = BUILDER_VERSION
        note.built_at = timezone.now()
        note.source_fingerprint = fingerprint
        note.verified_source_count = counts['verified']
        note.provisional_source_count = counts['provisional']
        note.excluded_source_count = counts['excluded']
        note.is_stale = False
        note.source_question_ids = cited_ids
        note.source_question_count = len(cited_ids)
        note.save()
        TopicNoteSource.objects.filter(note=note).delete()
        rows, seen = [], set()
        for qid in cited_ids:
            seen.add(qid)
            rows.append(TopicNoteSource(note=note, question_id=qid, key_status=statuses[qid].status,
                                        reason=statuses[qid].reason[:48], answer_at_build=valid_key(keys.get(qid)),
                                        cited=True))
        for row in excluded:
            qid = row['question_id']
            if qid in seen:
                continue
            seen.add(qid)
            status = statuses.get(qid)
            rows.append(TopicNoteSource(
                note=note, question_id=qid,
                key_status=(status.status if status and row['reason'] in ('over_cap', 'provisional_skipped')
                            else ks.EXCLUDED),
                reason=row['reason'][:48], answer_at_build='', cited=False,
            ))
        TopicNoteSource.objects.bulk_create(rows, batch_size=500)


# ─── Planning (management command, build endpoint, background task) ──────────

@dataclass
class NoteSpec:
    exam_type: str
    is_combined: bool
    subject_id: int
    subject_name: str
    topic_id: Optional[int]
    topic_name: str
    eligible: int
    note: object = None

    @property
    def level(self) -> str:
        return 'topic' if self.topic_id else 'subject'

    @property
    def title(self) -> str:
        name = self.topic_name if self.topic_id else public_subject_label(self.subject_name)
        return f"{name}: PYQ notes ({EXAM_LABELS['all' if self.is_combined else self.exam_type]})"

    def instance(self):
        """The existing note, or an unsaved draft for this spec."""
        if self.note is not None:
            return self.note
        from questions.models import TopicNote
        return TopicNote(title=self.title[:300], content='', subject_id=self.subject_id, topic_id=self.topic_id,
                         exam_type='all' if self.is_combined else self.exam_type, is_combined=self.is_combined,
                         is_published=False)

    def as_dict(self) -> dict:
        return {'exam_type': 'all' if self.is_combined else self.exam_type, 'is_combined': self.is_combined,
                'level': self.level, 'subject_id': self.subject_id,
                'subject': public_subject_label(self.subject_name), 'topic_id': self.topic_id,
                'topic': self.topic_name, 'eligible_pyqs': self.eligible,
                'note_id': getattr(self.note, 'pk', None)}


def _existing_note(exam_type, is_combined, subject_id, topic_id):
    from questions.models import TopicNote
    qs = TopicNote.objects.select_related('subject', 'topic')
    if topic_id:
        return qs.filter(topic_id=topic_id, exam_type=exam_type, is_combined=is_combined).first()
    return qs.filter(subject_id=subject_id, topic__isnull=True, exam_type=exam_type,
                     is_combined=is_combined).order_by('id').first()


def plan_notes(*, exams=EXAMS, combined=False, levels=('subject',), subject_id=None, topic_id=None,
               min_questions=MIN_PYQS) -> list:
    """The notes to build: one per subject (and/or topic) with at least ``min_questions`` active
    dated PYQs, per exam in ``exams``; with ``combined`` also one cross-exam note per subject /
    topic that has PYQs in two or more exams. Catch-all topics are left to the subject notes."""
    from django.db.models import Count
    from questions.models import Question

    min_questions = max(1, int(min_questions or 1))
    base = Question.objects.filter(is_active=True, is_dropped=False, year__gt=0, exam_type__in=EXAMS)
    if topic_id:
        base = base.filter(topic_id=topic_id)
        levels = ('topic',)
    elif subject_id:
        base = base.filter(subject_id=subject_id)
    specs = []
    variants = [(exam, False) for exam in exams]
    if combined:
        variants.append(('all', True))
    for exam, is_combined in variants:
        qs = base if is_combined else base.filter(exam_type=exam)
        if 'subject' in levels:
            # Questions without a subject cannot make a subject note (the build would only fail).
            rows = qs.filter(subject__isnull=False).values('subject_id', 'subject__name').annotate(
                n=Count('id'), exams=Count('exam_type', distinct=True)).order_by('subject__name')
            for row in rows:
                if row['n'] < min_questions or (is_combined and row['exams'] < 2):
                    continue
                specs.append(NoteSpec(exam, is_combined, row['subject_id'], row['subject__name'] or '', None, '',
                                      row['n']))
        if 'topic' in levels:
            rows = qs.filter(topic__isnull=False).values('topic_id', 'topic__name', 'topic__subject_id',
                                                         'topic__subject__name').annotate(
                n=Count('id'), exams=Count('exam_type', distinct=True)).order_by('topic__name')
            for row in rows:
                if row['n'] < min_questions or (is_combined and row['exams'] < 2):
                    continue
                if (row['topic__name'] or '').strip().lower() in CATCH_ALL_TOPICS:
                    continue
                specs.append(NoteSpec(exam, is_combined, row['topic__subject_id'], row['topic__subject__name'] or '',
                                      row['topic_id'], row['topic__name'] or '', row['n']))
    for spec in specs:
        spec.note = _existing_note('all' if spec.is_combined else spec.exam_type, spec.is_combined,
                                   spec.subject_id, spec.topic_id)
    return specs


def run_build(params: dict, *, apply=False, statuses=None, log=None, actor=None, preview=False) -> dict:
    """Plan and build notes (shared by the management command, the build endpoint and the
    background task). ``apply=False`` writes nothing. Returns a JSON-able report.

    ``params['exams']`` may be empty only with ``combined`` (the cross-exam notes alone).
    ``actor``: recorded as ``created_by`` of the notes this run creates. ``preview``: each built
    row also carries its markdown (``row['preview']``, admin dry runs of one note)."""
    combined = bool(params.get('combined'))
    exams = tuple(params.get('exams') or (() if combined else EXAMS))
    levels = tuple(params.get('levels') or ('subject',))
    mode = params.get('mode') or 'extractive'
    specs = plan_notes(exams=exams, combined=combined, levels=levels,
                       subject_id=params.get('subject_id'), topic_id=params.get('topic_id'),
                       min_questions=params.get('min_questions', MIN_PYQS))
    max_notes = params.get('max_notes')
    if max_notes:
        specs = specs[:int(max_notes)]
    report = {'builder_version': BUILDER_VERSION, 'apply': bool(apply), 'mode': mode, 'levels': list(levels),
              'notes': [], 'totals': Counter()}
    statuses = statuses if statuses is not None else {}
    actor = actor if getattr(actor, 'pk', None) else None
    for spec in specs:
        # A new note is an unsaved draft: the build saves it (never published), and a spec whose
        # questions turn out unusable leaves nothing behind.
        note = spec.instance()
        if note.pk is None and actor is not None:
            note.created_by = actor
        result = build_topic_note(
            note, mode=mode, include_provisional=params.get('include_provisional', True),
            verified_only=bool(params.get('verified_only')), dry_run=not apply, force=bool(params.get('force')),
            min_questions=params.get('min_questions', MIN_PYQS), evidence=params.get('evidence', True),
            statuses=statuses,
        )
        if not result.built:
            action = 'skipped'
        elif spec.note is None:
            action = 'create'
        elif result.changed:
            action = 'update'
        else:
            action = 'unchanged'
        report['totals'][action] += 1
        row = {**spec.as_dict(), 'action': action, 'note_id': result.note_id or getattr(spec.note, 'pk', None),
               'method': result.method, 'error': result.error, 'counts': result.counts,
               'warnings': result.warnings, 'fingerprint': result.fingerprint}
        if result.built:
            row['excluded_reasons'] = (result.structured or {}).get('excluded_reasons', {})
            row['evidence_state'] = (result.structured or {}).get('evidence_state', '')
            if preview:
                row['preview'] = {'markdown': result.markdown}
        else:
            row['counts_by_reason'] = result.counts_by_reason
        report['notes'].append(row)
        if log:
            log(row)
    report['totals'] = dict(report['totals'])
    return report


# ─── Staleness ──────────────────────────────────────────────────────────────

def mark_notes_stale(question_ids) -> int:
    """Mark every note citing (or excluding) one of ``question_ids`` stale; returns the count."""
    from questions.models import TopicNote, TopicNoteSource
    ids = [getattr(qid, 'pk', qid) for qid in (question_ids or [])]
    ids = [qid for qid in ids if qid]
    if not ids:
        return 0
    return TopicNote.objects.filter(
        pk__in=TopicNoteSource.objects.filter(question_id__in=ids).values('note_id'), is_stale=False,
    ).update(is_stale=True)


def on_question_changed(question, *, old_key='', old_stem_hash='', reason='', actor=None, **_kw) -> None:
    """questions.content_hooks reaction: the notes built from this question are stale."""
    mark_notes_stale([getattr(question, 'pk', question)])


_HIDING_FLAGS = ('is_disputed', 'is_controversial', 'is_scholarship_eligible', 'is_dropped')


def source_state(note_ids) -> dict:
    """Read-time check of built notes: ``{note_id: {'hidden': {qid}, 'provisional': {qid}}}``.

    A cited question is *hidden* when its key differs from the key at build time, it was
    deactivated / dropped / disputed / marked controversial or scholarship-only, an audit now
    excludes it, or a student reported a wrong answer. A question cited as verified that is no
    longer verified is shown as *provisional*. Three queries for any number of notes; commands
    that change keys outside the API (and so call no hook) are caught here."""
    from questions.models import QuestionFeedback, TopicNoteSource

    note_ids = [nid for nid in note_ids if nid]
    out = {nid: {'hidden': set(), 'provisional': set()} for nid in note_ids}
    if not note_ids:
        return out
    rows = list(TopicNoteSource.objects.filter(note_id__in=note_ids, cited=True).values(
        'note_id', 'question_id', 'answer_at_build', 'key_status', 'question__correct_answer',
        'question__is_active', 'question__answer_key_status', 'question__is_verified_by_admin',
        *[f'question__{flag}' for flag in _HIDING_FLAGS]))
    qids = {row['question_id'] for row in rows}
    audits = ks._audits(qids) if qids else {}
    reports = set(QuestionFeedback.objects.filter(
        question_id__in=qids, category='wrong_answer', status__in=('new', 'in_progress'),
    ).values_list('question_id', flat=True)) if qids else set()
    for row in rows:
        qid, state = row['question_id'], out[row['note_id']]
        key = valid_key(row['question__correct_answer'])
        audit = audits.get(qid)
        audit_status = audit['status'] if audit else (row['question__answer_key_status'] or '')
        if (key != valid_key(row['answer_at_build']) or not row['question__is_active']
                or any(row[f'question__{flag}'] for flag in _HIDING_FLAGS)
                or audit_status in ks.AUDIT_EXCLUDING or qid in reports):
            state['hidden'].add(qid)
            continue
        if row['key_status'] == ks.VERIFIED:
            if audit:
                audit_ok = bool(audit['status'] == 'verified' and not audit['is_stale']
                                and valid_key(audit['stored_key']) == key)
            else:
                # No audit row: the stored status, as key_statuses reads it (the key is the one
                # it had at build time, checked above).
                audit_ok = audit_status == 'verified'
            if not (row['question__is_verified_by_admin'] or audit_ok):
                state['provisional'].add(qid)
    return out


def stale_question_ids(note) -> set:
    return source_state([note.pk]).get(note.pk, {}).get('hidden', set())


def check_stale(*, apply=False) -> dict:
    """Built notes with hidden (changed) sources: ``{'checked', 'stale', 'note_ids'}``; with
    ``apply`` they are marked stale."""
    from questions.models import TopicNote
    notes = list(TopicNote.objects.exclude(builder_version='').values_list('id', flat=True))
    state = source_state(notes)
    stale = sorted(nid for nid, value in state.items() if value['hidden'])
    marked = 0
    if apply and stale:
        marked = TopicNote.objects.filter(pk__in=stale, is_stale=False).update(is_stale=True)
    return {'checked': len(notes), 'stale': len(stale), 'note_ids': stale, 'marked': marked}


# ─── Viewer filtering (student read paths) ──────────────────────────────────

def is_built(note) -> bool:
    return bool(isinstance(note.structured, dict) and note.structured.get('builder_version') and note.builder_version)


def viewer_view(note, *, full_access: bool, free_ids: set, state: Optional[dict] = None) -> dict:
    """What one viewer may read of ``note``.

    Built notes: points citing a changed question are hidden (stale); free viewers see only the
    points whose questions are all free showcase questions (the rest is counted in
    ``locked_points``); sections left empty are dropped (a section title can name an answer);
    the content is re-rendered from the filtered structure (the stored LLM text is served only
    to a full-access viewer when nothing is hidden).
    Manual / legacy notes: shown in full to full-access viewers, and to free viewers only when
    every source question is free (or the note cites none); otherwise the content is withheld."""
    if not is_built(note):
        ids = set(note.source_question_ids or [])
        allowed = full_access or not ids or ids <= free_ids
        return {
            'content': note.content if allowed else '',
            'answers_locked': not allowed,
            'locked_points': 0 if allowed else None,
            'hidden_points': 0,
            'points': None,
            'sections': None,
            'source_question_ids': sorted(ids) if allowed else [],
        }
    structured = note.structured
    state = state or {'hidden': set(), 'provisional': set()}
    hidden_q, provisional_q = state['hidden'], state['provisional']
    visible, locked, hidden, provisional_now = set(), 0, 0, set()
    for point in structured.get('points') or []:
        qids = set(point['question_ids'])
        if qids & hidden_q:
            hidden += 1
            continue
        if not full_access and not qids <= free_ids:
            locked += 1
            continue
        visible.add(point['id'])
        if qids & provisional_q:
            provisional_now.add(point['id'])
    if full_access and not hidden and not provisional_now and note.generation_method == 'llm':
        content = note.content
    else:
        content = render_markdown(structured, visible=visible, provisional_now=provisional_now,
                                  locked_points=locked, hidden_points=hidden)
    points = []
    for point in structured.get('points') or []:
        if point['id'] not in visible:
            continue
        key_status = ks.PROVISIONAL if point['id'] in provisional_now else point['key_status']
        # pyq-notes/1 points carry no per-question sources: their ids, without labels.
        sources = point.get('sources') or [
            {'id': qid, 'label': '', 'year': None, 'exam_type': '', 'key_status': point['key_status']}
            for qid in point['question_ids']]
        points.append({
            'id': point['id'], 'kind': point['kind'], 'stem': point['stem'], 'answer': point['answer'],
            'key_status': key_status,
            'question_ids': point['question_ids'], 'asked_in': point['asked_in'], 'frequency': point['frequency'],
            'sources': [{
                'id': source['id'], 'label': source.get('label') or '', 'year': source.get('year'),
                'exam_type': source.get('exam_type') or '',
                'key_status': ks.PROVISIONAL if source['id'] in provisional_q else (
                    source.get('key_status') or point['key_status']),
            } for source in sources],
            'latest_year': point['latest_year'], 'why': point.get('why', ''),
            'practice_reason': point.get('practice_reason', ''),
            'evidence': [{name: entry.get(name) for name in (
                'title', 'edition', 'year', 'page_label', 'page_start', 'page_end', 'excerpt', 'truncated', 'label')}
                for entry in point.get('evidence') or []],
        })
    sections = []
    for section in structured.get('sections') or []:
        ids = [pid for pid in section.get('points') or [] if pid in visible]
        if ids:
            sections.append({'id': section.get('id'), 'title': section['title'], 'kind': section.get('kind'),
                             'points': ids})
    visible_ids = sorted({qid for point in points for qid in point['question_ids']})
    return {
        'content': content,
        'answers_locked': bool(locked),
        'locked_points': locked,
        'hidden_points': hidden,
        'points': points,
        'sections': sections,
        'source_question_ids': visible_ids,
    }
