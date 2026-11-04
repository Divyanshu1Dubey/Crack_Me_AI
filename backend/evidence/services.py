"""The only write path for question evidence, and the student view of it (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md section 4 (images / evidence group). Rules enforced here:

* Only stored passages become evidence. ``record_passage_evidence`` checks that the passage text
  is on the cited page(s) of the source file in the reference store (``reference_corpus.api
  .page_text``; for a question's own recall page, its ``QuestionSource`` text) and stores the
  verbatim page text, at most ``SNIPPET_STORE_MAX_CHARS``. Anything else raises
  ``SnippetNotOnPage`` (or ``ReferenceStoreUnavailable`` when the page cannot be read). AI output
  is never stored as evidence: an AI verdict only sets the stance of a stored passage, pending
  review.
* Nothing here changes an answer key.
* New rows are ``pending`` and hidden from students. An admin ``review`` accepts / rejects them;
  accepting confirms the row for the current key and content.
* When a question's key, stem or options change (``on_question_changed`` from
  ``questions.content_hooks``), rows recorded for the old content become ``stale`` and hidden.
* Students see ``student_citations``: accepted, student-visible, current rows of sources in
  ``REFERENCE_STUDENT_TIERS`` whose ``student_display`` allows it, at most
  ``EVIDENCE_MAX_STUDENT_ROWS``, snippets cut to ``EVIDENCE_SNIPPET_MAX_CHARS`` -- never file paths,
  sha256 hashes, page text or full pages.

Pages are 1-based physical page numbers of the file; ``page_label`` is the printed number when
known (citations say 'PDF p. N' otherwise). DOCX sources count sections (``page_labels['_unit']
== 'section'``).
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
import secrets
import unicodedata
from typing import Iterable, Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from questions.content_hashes import stem_hash, valid_key

logger = logging.getLogger(__name__)

SNIPPET_STORE_MAX_CHARS = 600
SNIPPET_MIN_MATCH_CHARS = 12
MAX_PAGE_SPAN = 4
OPTION_LETTERS = ('A', 'B', 'C', 'D')
REVIEW_STATUSES = ('pending', 'accepted', 'rejected')
LIVE_STATUSES = ('pending', 'accepted')
DEFAULT_DISPLAY_BY_TIER = {1: 'snippet', 2: 'snippet', 3: 'snippet', 4: 'citation', 5: 'none'}
SECTION_UNIT_KEY = '_unit'
FIGURE_MAX_DPI = 150
DEFAULT_FIGURE_DPI = 150
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_SHA_PREFIX_RE = re.compile(r'^[0-9a-f]{8,64}$')
_WORD_RE = re.compile(r'[a-z0-9]+')
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?;:])\s+')
_STOPWORDS = frozenset(
    'the and for with that this from which what when where into than then there their these those '
    'have has had been being were was are is not all any most more less least none only also other '
    'following true false except about after before between during under over most commonly seen'.split()
)
# Typographic variants folded before comparing a passage with page text.
_FOLD = str.maketrans({
    '‘': "'", '’': "'", '‚': "'", '‛': "'", '′': "'",
    '“': '"', '”': '"', '„': '"', '‟': '"', '″': '"',
    '–': '-', '—': '-', '‒': '-', '―': '-', '−': '-',
})
_LINEBREAK_HYPHENS = ('-', '‐', '‑')


class EvidenceError(ValueError):
    """A request the evidence rules refuse. ``code`` / ``status`` map onto the API response."""

    code = 'invalid_evidence'
    status = 400

    def __init__(self, message: str = '', **detail):
        super().__init__(message or self.code)
        self.detail = detail


class UnknownSource(EvidenceError):
    code = 'unknown_source'


class SnippetNotOnPage(EvidenceError):
    code = 'snippet_not_on_page'


class ReferenceStoreUnavailable(EvidenceError):
    code = 'reference_store_unavailable'
    status = 503


class FigureTooLarge(EvidenceError):
    code = 'figure_too_large'


class NotStudentDisplayable(EvidenceError):
    code = 'source_not_student_displayable'


# ── reference store access (reference_corpus.api, built by the RAG-core group) ───────────────

def reference_api():
    """``reference_corpus.api`` or None when it cannot be imported."""
    try:
        from reference_corpus import api
    except Exception:  # noqa: BLE001 - optional at runtime; tests patch this function
        return None
    return api


def store_available() -> bool:
    api = reference_api()
    if api is None:
        return False
    try:
        return bool(api.store_available())
    except Exception:  # noqa: BLE001
        return False


def page_text(sha256: str, page_no: int) -> Optional[dict]:
    """``{text, page_label, chapter}`` of one page from the reference store, or None."""
    api = reference_api()
    if api is None:
        return None
    try:
        data = api.page_text(sha256, int(page_no))
    except Exception as exc:  # noqa: BLE001 - a broken store reads as "no page"
        logger.warning('evidence: page_text failed for %s p.%s (%s)', (sha256 or '')[:16], page_no,
                       type(exc).__name__)
        return None
    if isinstance(data, str):
        data = {'text': data}
    if not isinstance(data, dict) or not isinstance(data.get('text'), str):
        return None
    return data


def render_page_png(sha256: str, page_no: int, dpi: int = 110) -> Optional[bytes]:
    api = reference_api()
    if api is None:
        return None
    try:
        data = api.render_page_png(sha256, int(page_no), dpi=int(dpi))
    except Exception as exc:  # noqa: BLE001
        logger.warning('evidence: render_page_png failed for %s p.%s (%s)', (sha256 or '')[:16], page_no,
                       type(exc).__name__)
        return None
    return bytes(data) if data else None


def registry_rows() -> list[dict]:
    api = reference_api()
    if api is None:
        return []
    try:
        rows = api.sources()
    except Exception as exc:  # noqa: BLE001
        logger.warning('evidence: reference sources() failed (%s)', type(exc).__name__)
        return []
    return [row for row in (rows or []) if isinstance(row, dict)]


# ── passage matching ────────────────────────────────────────────────────────────────────────

def _skeleton(text: str) -> tuple[str, list[int]]:
    """Comparison form of ``text`` plus, per character, its index in ``text``: whitespace, soft
    hyphens and line-break hyphens removed, typography folded, accents dropped, casefolded."""
    out: list[str] = []
    index: list[int] = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch == '­' or ch.isspace():
            continue
        if ch in _LINEBREAK_HYPHENS and i + 1 < n and text[i + 1].isspace():
            continue
        for c in unicodedata.normalize('NFKD', ch.translate(_FOLD)).casefold():
            if c.isspace() or unicodedata.combining(c):
                continue
            out.append(c)
            index.append(i)
    return ''.join(out), index


def snippet_sha1(snippet: str) -> str:
    skeleton, _ = _skeleton(snippet or '')
    return hashlib.sha1(skeleton.encode('utf-8'), usedforsecurity=False).hexdigest()


def locate_snippet(haystack: str, snippet: str) -> Optional[tuple[int, int]]:
    """``(start, end)`` of ``snippet`` in ``haystack`` (verbatim up to whitespace, hyphenation at
    line breaks, typographic quotes / dashes, accents and case), or None."""
    hay, index = _skeleton(haystack or '')
    needle, _ = _skeleton(snippet or '')
    if len(needle) < SNIPPET_MIN_MATCH_CHARS:
        return None
    pos = hay.find(needle)
    if pos < 0:
        return None
    return index[pos], index[pos + len(needle) - 1] + 1


def _clip(text: str, max_chars: int = SNIPPET_STORE_MAX_CHARS) -> str:
    text = ' '.join((text or '').split())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if ' ' in cut[int(max_chars * 0.6):]:
        cut = cut.rsplit(' ', 1)[0]
    return cut


def verify_on_pages(sha256: str, page_start: int, page_end: int, snippet: str) -> dict:
    """Is ``snippet`` on pages ``page_start..page_end`` of the stored file?

    ``{'available': bool, 'verified': bool, 'exact', 'char_start', 'char_end', 'page_label',
    'page_label_end', 'chapter'}`` -- offsets are into the page texts joined with newlines.
    """
    texts: list[str] = []
    labels: dict[int, str] = {}
    chapter = ''
    for page in range(page_start, page_end + 1):
        data = page_text(sha256, page)
        if data is None:
            if page == page_start:
                return {'available': False, 'verified': False}
            break
        texts.append(data['text'])
        labels[page] = (data.get('page_label') or '').strip()[:32]
        chapter = chapter or (data.get('chapter') or '').strip()
    joined = '\n'.join(texts)
    found = locate_snippet(joined, snippet)
    result = {'available': True, 'verified': found is not None, 'page_label': labels.get(page_start, ''),
              'page_label_end': labels.get(page_end, ''), 'chapter': chapter[:300]}
    if found:
        start, end = found
        result.update({'exact': ' '.join(joined[start:end].split()), 'char_start': start, 'char_end': end})
    return result


def _verify_on_recall_page(question, sha256: str, page_start: int, page_end: int, snippet: str) -> dict:
    """The question's own recall page: its stored ``QuestionSource`` text for that PDF / page."""
    from questions.models import QuestionSource

    rows = QuestionSource.objects.filter(
        question_id=question.pk, recall_source__pdf_sha256=sha256,
        page_number__gte=page_start, page_number__lte=page_end,
    ).only('original_text', 'extracted_text')
    texts = [t for row in rows for t in (row.original_text, row.extracted_text) if t]
    if not texts:
        return {'available': False, 'verified': False}
    for text in texts:
        found = locate_snippet(text, snippet)
        if found:
            start, end = found
            return {'available': True, 'verified': True, 'exact': ' '.join(text[start:end].split()),
                    'char_start': None, 'char_end': None, 'page_label': '', 'page_label_end': '', 'chapter': ''}
    return {'available': True, 'verified': False}


# ── sources ─────────────────────────────────────────────────────────────────────────────────

_KIND_ALIASES = {
    'notes_docx': 'notes', 'docx_notes': 'notes', 'docx': 'notes', 'unit_notes': 'notes', 'coaching_notes': 'notes',
    'pyq': 'pyq_compilation', 'recall': 'pyq_compilation', 'paper': 'question_paper', 'pyq_paper': 'question_paper',
    'key': 'answer_key', 'official_key': 'answer_key', 'book': 'textbook',
}
_ADMIN_PROTECTED_FIELDS = ('title', 'edition', 'year', 'kind', 'tier', 'subject', 'licence', 'student_display',
                           'metadata_source', 'metadata_verified', 'is_active')


def _int_or_none(value, lo=None, hi=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if (lo is not None and number < lo) or (hi is not None and number > hi):
        return None
    return number


def _is_section_unit(raw: dict, kind_raw: str) -> bool:
    if str(raw.get('page_unit') or '').lower() == 'section':
        return True
    if kind_raw in ('notes_docx', 'docx_notes', 'docx'):
        return True
    for key in ('format', 'file_type', 'ext', 'file_name'):
        if str(raw.get(key) or '').lower().endswith('docx'):
            return True
    return False


def source_fields(raw: dict) -> Optional[dict]:
    """EvidenceSource fields from one registry row, or None when the row lacks a valid sha256,
    title or tier. Metadata is copied, never guessed; unknown kinds become 'other'."""
    from .models import EvidenceSource

    sha = str(raw.get('sha256') or '').strip().lower()
    title = ' '.join(str(raw.get('title') or '').split())[:300]
    tier = _int_or_none(raw.get('tier'), 1, 5)
    if not _SHA256_RE.match(sha) or not title or tier is None:
        return None
    kind_raw = str(raw.get('kind') or '').strip().lower()
    kinds = {k for k, _ in EvidenceSource.KIND_CHOICES}
    kind = kind_raw if kind_raw in kinds else _KIND_ALIASES.get(kind_raw, 'other')
    displays = {k for k, _ in EvidenceSource.STUDENT_DISPLAY_CHOICES}
    display = str(raw.get('student_display') or '').strip().lower()
    if display not in displays:
        display = DEFAULT_DISPLAY_BY_TIER[tier]
    if tier == 5:
        display = 'none'
    labels = {}
    raw_labels = raw.get('page_labels')
    if isinstance(raw_labels, dict):
        for key, value in raw_labels.items():
            page = _int_or_none(key, 1)
            label = ' '.join(str(value or '').split())[:32]
            if page is not None and label:
                labels[str(page)] = label
    if _is_section_unit(raw, kind_raw):
        labels[SECTION_UNIT_KEY] = 'section'
    metadata_sources = {k for k, _ in EvidenceSource.METADATA_SOURCE_CHOICES}
    metadata_source = str(raw.get('metadata_source') or 'registry').strip().lower()
    status = str(raw.get('status') or '').strip().lower()
    return {
        'sha256': sha,
        'title': title,
        'edition': ' '.join(str(raw.get('edition') or '').split())[:60],
        'year': _int_or_none(raw.get('year'), 1800, 2100),
        'kind': kind,
        'tier': tier,
        'subject': ' '.join(str(raw.get('subject') or '').split())[:80],
        'licence': ' '.join(str(raw.get('licence') or raw.get('license') or '').split())[:200],
        'student_display': display,
        'is_excerpt': bool(raw.get('is_excerpt', False)),
        'page_count': _int_or_none(raw.get('page_count', raw.get('pages')), 0),
        'page_labels': labels,
        'metadata_source': metadata_source if metadata_source in metadata_sources else 'registry',
        'metadata_verified': bool(raw.get('metadata_verified', False)),
        'is_active': bool(raw.get('is_active', True)) and status != 'duplicate',
    }


def sync_sources(rows: Optional[Iterable[dict]] = None, *, dry_run: bool = False) -> dict:
    """Upsert EvidenceSource from reference-store registry rows (default ``reference_corpus.api
    .sources()``). A source an admin curated (``metadata_source='admin'``) keeps its metadata;
    only page_count / page_labels are refreshed. Returns counts."""
    from .models import EvidenceSource

    rows = registry_rows() if rows is None else list(rows)
    counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0}
    for raw in rows:
        fields = source_fields(raw) if isinstance(raw, dict) else None
        if fields is None:
            counts['skipped'] += 1
            continue
        existing = EvidenceSource.objects.filter(sha256=fields['sha256']).first()
        if existing is None:
            counts['created'] += 1
            if not dry_run:
                try:
                    with transaction.atomic():
                        EvidenceSource.objects.create(**fields)
                except IntegrityError:  # created concurrently
                    counts['created'] -= 1
                    counts['unchanged'] += 1
            continue
        protected = existing.metadata_source == 'admin'
        updates = {}
        for name, value in fields.items():
            if name == 'sha256' or (protected and name in _ADMIN_PROTECTED_FIELDS):
                continue
            if getattr(existing, name) != value:
                updates[name] = value
        if not updates:
            counts['unchanged'] += 1
            continue
        counts['updated'] += 1
        if not dry_run:
            for name, value in updates.items():
                setattr(existing, name, value)
            existing.save(update_fields=[*updates, 'updated_at'])
    return counts


def get_source(sha256: str):
    """The EvidenceSource for a full sha256, synced from the registry on first use; or None."""
    from .models import EvidenceSource

    sha = (sha256 or '').strip().lower()
    if not _SHA256_RE.match(sha):
        return None
    source = EvidenceSource.objects.filter(sha256=sha).first()
    if source is None:
        matches = [row for row in registry_rows() if str(row.get('sha256') or '').strip().lower() == sha]
        if matches:
            sync_sources(matches)
            source = EvidenceSource.objects.filter(sha256=sha).first()
    return source


def resolve_source(sha_or_prefix: str):
    """EvidenceSource by full sha256 or a unique prefix (>= 8 hex chars, e.g. the 16-char short
    hash); None when unknown or ambiguous."""
    from .models import EvidenceSource

    value = (sha_or_prefix or '').strip().lower()
    if _SHA256_RE.match(value):
        return get_source(value)
    if not _SHA_PREFIX_RE.match(value):
        return None
    matches = list(EvidenceSource.objects.filter(sha256__startswith=value)[:2])
    return matches[0] if len(matches) == 1 else None


def ensure_recall_source(recall_source):
    """A tier-5 EvidenceSource for a recall PDF (``RecallSource``): question papers are never
    evidence of a fact and never shown to students; used for 'states_key' signals."""
    from .models import EvidenceSource

    sha = (recall_source.pdf_sha256 or '').strip().lower()
    if not _SHA256_RE.match(sha):
        raise UnknownSource('recall source has no sha256')
    source = EvidenceSource.objects.filter(sha256=sha).first()
    if source is not None:
        return source
    title = (recall_source.pdf_filename or '').rsplit('.', 1)[0][:300] or f'Recall PDF {sha[:16]}'
    try:
        with transaction.atomic():
            return EvidenceSource.objects.create(
                sha256=sha, title=title, kind='pyq_compilation', tier=5, student_display='none',
                page_count=recall_source.page_count or None, metadata_source='registry',
            )
    except IntegrityError:
        return EvidenceSource.objects.get(sha256=sha)


def source_student_displayable(source) -> bool:
    tiers = tuple(getattr(settings, 'REFERENCE_STUDENT_TIERS', (1, 2, 3, 4)) or ())
    return bool(source.is_active and source.tier in tiers and source.tier != 5 and source.student_display != 'none')


def is_section_unit(source) -> bool:
    labels = source.page_labels if isinstance(source.page_labels, dict) else {}
    return labels.get(SECTION_UNIT_KEY) == 'section'


# ── citations ───────────────────────────────────────────────────────────────────────────────

def page_locator(row) -> str:
    """'p. 312' (printed label known), 'PDF p. 340' (physical page only) or 'section 4' (DOCX)."""
    source = row.source
    start, end = row.page_start, row.page_end
    if is_section_unit(source):
        return f'section {start}' if end == start else f'sections {start}-{end}'
    label = (row.page_label or '').strip()
    if label:
        labels = source.page_labels if isinstance(source.page_labels, dict) else {}
        end_label = (labels.get(str(end)) or '').strip() if end != start else ''
        return f'pp. {label}-{end_label}' if end_label and end_label != label else f'p. {label}'
    return f'PDF p. {start}' if end == start else f'PDF pp. {start}-{end}'


def citation_label(row) -> str:
    """'Title, edition, p. <label>' / '..., PDF p. N' / '..., section N' -- only stored metadata."""
    source = row.source
    parts = [source.title]
    if source.edition:
        parts.append(source.edition)
    if source.year and str(source.year) not in ' '.join(parts):
        parts.append(str(source.year))
    return ', '.join(p for p in parts if p) + ', ' + page_locator(row)


def is_current(row, question) -> bool:
    """Accepted / pending row recorded for the question's current key and content."""
    if row.review_status not in LIVE_STATUSES:
        return False
    return (row.key_at_creation == valid_key(question.correct_answer)
            and row.content_sha256 == stem_hash(question))


def _terms(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or '').casefold()) if len(w) >= 4 and w not in _STOPWORDS}


def choose_snippet(text: str, terms: Iterable[str] = (), max_chars: int = 240) -> str:
    """The run of whole sentences of ``text`` (at most ``max_chars``) with the most ``terms``;
    a single over-long sentence is cut at a word boundary and ends with an ellipsis."""
    text = ' '.join((text or '').split())
    if len(text) <= max_chars:
        return text
    wanted = {t.casefold() for t in terms if t}
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s]

    def hits(chunk: str) -> int:
        return sum(1 for w in _WORD_RE.findall(chunk.casefold()) if w in wanted)

    best, best_score = '', -1
    for i in range(len(sentences)):
        window = ''
        for j in range(i, len(sentences)):
            candidate = f'{window} {sentences[j]}'.strip()
            if len(candidate) > max_chars:
                break
            window = candidate
            score = hits(window)
            if score > best_score or (score == best_score and len(window) > len(best)):
                best, best_score = window, score
    if best:
        return best
    sentence = max(sentences or [text], key=hits)
    cut = sentence[:max_chars - 1]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' ,;:') + '…'


def _option_text(question, letter: str) -> str:
    return getattr(question, f'option_{letter.lower()}', '') if letter in OPTION_LETTERS else ''


def student_rows(question) -> list:
    """Accepted, student-visible, current rows of displayable sources whose quote was verified
    against the page, best first, capped."""
    from .models import QuestionEvidence

    tiers = tuple(getattr(settings, 'REFERENCE_STUDENT_TIERS', (1, 2, 3, 4)) or ())
    max_rows = max(0, int(getattr(settings, 'EVIDENCE_MAX_STUDENT_ROWS', 3)))
    rows = (
        QuestionEvidence.objects.filter(
            question_id=question.pk, review_status='accepted', student_visible=True, quote_verified=True,
            source__is_active=True, source__tier__in=[t for t in tiers if t != 5],
        )
        .exclude(source__student_display='none')
        .select_related('source', 'figure')
    )
    current = [row for row in rows if is_current(row, question)]
    current.sort(key=lambda r: (r.source.tier, 0 if r.stance == 'supports' else 1, -(r.score or 0), r.pk))
    return current[:max_rows]


def student_citation(row, question, *, request=None) -> dict:
    """One citation as students see it (no sha256, paths, page text or full pages)."""
    from .access import figure_url

    source = row.source
    max_chars = max(0, int(getattr(settings, 'EVIDENCE_SNIPPET_MAX_CHARS', 240)))
    snippets_on = bool(getattr(settings, 'EVIDENCE_STUDENT_SNIPPETS', True))
    snippet = ''
    if snippets_on and source.student_display in ('snippet', 'figure') and max_chars:
        letter = row.option_letter or valid_key(question.correct_answer)
        snippet = choose_snippet(row.snippet, _terms(_option_text(question, letter)) | _terms(question.question_text),
                                 max_chars)
    figure = None
    if source.student_display == 'figure' and row.figure_id and row.figure and row.figure.image:
        figure = figure_url(row.figure_id, request)
    label = (row.page_label or '').strip()
    return {
        'id': row.pk,
        'citation': citation_label(row),
        'source': {'title': source.title, 'edition': source.edition, 'year': source.year, 'kind': source.kind},
        'chapter': row.chapter,
        'page_label': label,
        'page_note': '' if label or is_section_unit(source) else page_locator(row),
        'snippet': snippet,
        'stance': row.stance,
        'option_letter': row.option_letter,
        'figure_url': figure,
        'verified': True,
    }


def student_citations(question, *, revealed: bool, request=None) -> list[dict]:
    """Citations a student may see for ``question``; [] unless ``revealed`` (the viewer may see
    the answer -- evidence for an option names it)."""
    if not revealed:
        return []
    return [student_citation(row, question, request=request) for row in student_rows(question)]


def figure_publicly_viewable(figure) -> bool:
    """A figure crop students may load: used by an accepted, student-visible, current row of a
    source whose display level is 'figure'."""
    from .models import QuestionEvidence

    rows = QuestionEvidence.objects.filter(
        figure_id=figure.pk, review_status='accepted', student_visible=True, quote_verified=True,
        source__student_display='figure', source__is_active=True,
    ).select_related('question', 'source')
    return any(is_current(row, row.question) and source_student_displayable(row.source) for row in rows)


# ── writes ──────────────────────────────────────────────────────────────────────────────────

def _choice_values(choices) -> set:
    return {value for value, _ in choices}


def _clean_letter(value) -> str:
    letter = (value or '').strip().upper()
    if letter and letter not in OPTION_LETTERS:
        raise EvidenceError('option_letter must be A-D or blank', field='option_letter')
    return letter


def _clean_bbox(bbox):
    if bbox in (None, '', []):
        return None
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise EvidenceError('bbox must be [x0, y0, x1, y1] in PDF points', field='bbox')
    try:
        x0, y0, x1, y1 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise EvidenceError('bbox must be four numbers', field='bbox')
    if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0 or max(x1, y1) > 20000:
        raise EvidenceError('bbox must have x1 > x0 >= 0 and y1 > y0 >= 0', field='bbox')
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def _review_state(row) -> dict:
    return {'review_status': row.review_status, 'student_visible': row.student_visible, 'stance': row.stance,
            'option_letter': row.option_letter, 'key_at_creation': row.key_at_creation,
            'stale_reason': row.stale_reason}


def _actor_or_none(actor):
    return actor if getattr(actor, 'is_authenticated', False) else None


def _admin_audit(actor, row, action: str, detail: str = '') -> None:
    """Central admin trail (accounts.AdminAuditLog 'evidence_review'); best effort, ids only."""
    actor = _actor_or_none(actor)
    if actor is None:
        return
    try:
        from accounts.models import AdminAuditLog
        with transaction.atomic():
            AdminAuditLog.objects.create(
                actor=actor, action='evidence_review', resource_type='question_evidence',
                resource_id=str(row.pk), detail=detail[:300],
                metadata={'question_id': row.question_id, 'action': action, 'review_status': row.review_status,
                          'stance': row.stance, 'option_letter': row.option_letter, 'origin': row.origin},
            )
    except Exception:  # noqa: BLE001 - EvidenceReviewLog is the primary record
        logger.debug('evidence: AdminAuditLog write skipped', exc_info=True)


def record_passage_evidence(question, *, sha256, page_start, page_end, text, option_letter, stance, origin,
                            score=None, method='', run_ref='', created_by=None, question_image=None, bbox=None,
                            chapter=None, page_label=None):
    """Record (idempotently) that a stored passage relates to ``question`` / an option.

    The passage must be on pages ``page_start..page_end`` (1-based) of the source file; the row
    stores the page's own text (<= 600 chars), the printed page label when known, and the
    question's current key and content hash. New rows are ``pending``. Re-recording the same
    passage (same question, source, first page, text, option and origin) updates score / method /
    run and, for a stale row, makes it a pending candidate for the current content; a rejected
    row stays rejected.

    Raises ``EvidenceError`` (bad arguments), ``UnknownSource``, ``ReferenceStoreUnavailable``
    or ``SnippetNotOnPage``.
    """
    from .models import EvidenceReviewLog, QuestionEvidence

    if origin not in _choice_values(QuestionEvidence.ORIGIN_CHOICES):
        raise EvidenceError(f'unknown origin {origin!r}', field='origin')
    if stance not in _choice_values(QuestionEvidence.STANCE_CHOICES):
        raise EvidenceError(f'unknown stance {stance!r}', field='stance')
    letter = _clean_letter(option_letter)
    try:
        page_start = int(page_start)
        page_end = int(page_end) if page_end not in (None, '', 0) else page_start
    except (TypeError, ValueError):
        raise EvidenceError('page_start / page_end must be integers', field='page_start')
    if page_start < 1 or page_end < page_start or page_end - page_start > MAX_PAGE_SPAN:
        raise EvidenceError(f'pages must satisfy 1 <= page_start <= page_end <= page_start + {MAX_PAGE_SPAN}',
                            field='page_start')
    bbox = _clean_bbox(bbox)
    snippet = _clip(text)
    if not snippet:
        raise EvidenceError('text is required', field='text')
    source = get_source(sha256)
    if source is None:
        raise UnknownSource('no evidence source with this sha256')
    if source.page_count and page_end > source.page_count:
        raise EvidenceError('page beyond the end of the source', field='page_end')
    if question_image is not None and question_image.question_id != question.pk:
        raise EvidenceError('question_image belongs to another question', field='question_image')

    check = verify_on_pages(source.sha256, page_start, page_end, snippet)
    if not check.get('available') and origin == 'recall_source':
        check = _verify_on_recall_page(question, source.sha256, page_start, page_end, snippet)
    if not check.get('available'):
        raise ReferenceStoreUnavailable('the cited page cannot be read from the reference store')
    if not check.get('verified'):
        raise SnippetNotOnPage('the text is not on the cited page(s)')
    snippet = _clip(check.get('exact') or snippet)
    labels = source.page_labels if isinstance(source.page_labels, dict) else {}
    label = (page_label if page_label is not None else '') or check.get('page_label') or labels.get(str(page_start), '')
    heading = (chapter if chapter is not None else '') or check.get('chapter') or ''
    lookup = {'question_id': question.pk, 'source': source, 'page_start': page_start,
              'snippet_sha1': snippet_sha1(snippet), 'option_letter': letter, 'origin': origin}
    current_key, current_hash = valid_key(question.correct_answer), stem_hash(question)
    actor = _actor_or_none(created_by)

    with transaction.atomic():
        row = QuestionEvidence.objects.select_for_update().filter(**lookup).first()
        created = False
        if row is None:
            try:
                with transaction.atomic():
                    row = QuestionEvidence.objects.create(
                        **lookup, question_image=question_image, page_end=page_end, page_label=str(label)[:32],
                        chapter=str(heading)[:300], snippet=snippet, char_start=check.get('char_start'),
                        char_end=check.get('char_end'), quote_verified=True, bbox=bbox, stance=stance,
                        score=score, retrieval_method=(method or '')[:24], run_ref=(run_ref or '')[:64],
                        review_status='pending', student_visible=False, key_at_creation=current_key,
                        content_sha256=current_hash, created_by=actor,
                    )
                created = True
            except IntegrityError:
                row = QuestionEvidence.objects.select_for_update().get(**lookup)
        if created:
            EvidenceReviewLog.objects.create(evidence=row, actor=actor, action='create', after=_review_state(row),
                                             note=f'origin={origin}')
            return row
        before = _review_state(row)
        changed = []
        if score is not None and row.score != score:
            row.score = score
            changed.append('score')
        for name, value in (('retrieval_method', (method or '')[:24]), ('run_ref', (run_ref or '')[:64])):
            if value and getattr(row, name) != value:
                setattr(row, name, value)
                changed.append(name)
        if row.review_status == 'stale' or (row.review_status in LIVE_STATUSES and not is_current(row, question)):
            row.review_status = 'pending'
            row.student_visible = False
            row.stale_reason = ''
            row.key_at_creation, row.content_sha256 = current_key, current_hash
            row.stance = stance
            changed += ['review_status', 'student_visible', 'stale_reason', 'key_at_creation', 'content_sha256',
                        'stance']
        elif row.review_status == 'pending' and stance != 'candidate' and row.stance != stance:
            row.stance = stance
            changed.append('stance')
        if changed:
            row.save(update_fields=[*dict.fromkeys(changed), 'updated_at'])
            if before != _review_state(row):
                EvidenceReviewLog.objects.create(evidence=row, actor=actor, action='edit', before=before,
                                                 after=_review_state(row), note=f're-recorded ({origin})')
    return row


def review(evidence, *, actor, status, stance=None, option_letter=None, student_visible=None, note=''):
    """An admin decision on one row: ``status`` 'accepted' | 'rejected' | 'pending'.

    Accepting confirms the row for the question's current key and content (its staleness
    inputs are refreshed) and makes it student-visible when its source may be shown
    (``student_visible`` overrides; True for a source that may not be shown raises
    ``NotStudentDisplayable``). Rejecting / re-opening hides it. Logged in EvidenceReviewLog.
    """
    from .models import EvidenceReviewLog, QuestionEvidence

    if status not in REVIEW_STATUSES:
        raise EvidenceError("status must be 'accepted', 'rejected' or 'pending'", field='status')
    if stance is not None and stance not in _choice_values(QuestionEvidence.STANCE_CHOICES):
        raise EvidenceError(f'unknown stance {stance!r}', field='stance')
    letter = _clean_letter(option_letter) if option_letter is not None else None
    actor = _actor_or_none(actor)
    with transaction.atomic():
        row = QuestionEvidence.objects.select_for_update().select_related('source', 'question').get(pk=evidence.pk)
        before = _review_state(row)
        question = row.question
        if stance is not None:
            row.stance = stance
        if letter is not None:
            row.option_letter = letter
        if status == 'accepted':
            displayable = source_student_displayable(row.source)
            if student_visible is True and not displayable:
                raise NotStudentDisplayable('this source is not shown to students (tier / display setting)')
            row.key_at_creation = valid_key(question.correct_answer)
            row.content_sha256 = stem_hash(question)
            row.stale_reason = ''
            row.student_visible = bool(displayable and row.quote_verified) if student_visible is None else bool(
                student_visible)
        else:
            row.student_visible = False
        row.review_status = status
        row.reviewed_by = actor
        row.reviewed_at = timezone.now()
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError:
            raise EvidenceError('another row already records this passage for that option', field='option_letter')
        action = {'accepted': 'accept', 'rejected': 'reject'}.get(status, 'edit')
        if before['review_status'] == status:
            action = 'edit'
        EvidenceReviewLog.objects.create(evidence=row, actor=actor, action=action, before=before,
                                         after=_review_state(row), note=(note or '')[:2000])
        _admin_audit(actor, row, action, note or '')
    return row


def link_manual(question, *, actor, sha256, page_start, snippet, page_end=None, option_letter='', stance='supports',
                bbox=None, question_image=None, accept=True, student_visible=None, note=''):
    """An admin links a passage they found on a page (origin 'admin_manual'); accepted at once
    unless ``accept`` is False. Same checks as ``record_passage_evidence``."""
    row = record_passage_evidence(
        question, sha256=sha256, page_start=page_start, page_end=page_end, text=snippet,
        option_letter=option_letter, stance=stance, origin='admin_manual', method='manual',
        created_by=actor, question_image=question_image, bbox=bbox,
    )
    if accept:
        row = review(row, actor=actor, status='accepted', student_visible=student_visible,
                     note=note or 'linked manually')
    return row


def mark_stale(question, reason: str = '', actor=None) -> int:
    """Hide (``stale``) the pending / accepted rows recorded for another key or content than the
    question has now. Returns how many rows changed."""
    from .models import EvidenceReviewLog, QuestionEvidence

    current_key, current_hash = valid_key(question.correct_answer), stem_hash(question)
    rows = list(QuestionEvidence.objects.filter(question_id=question.pk, review_status__in=LIVE_STATUSES).only(
        'id', 'review_status', 'student_visible', 'stance', 'option_letter', 'key_at_creation', 'content_sha256',
        'stale_reason'))
    changed = []
    for row in rows:
        key_changed = row.key_at_creation != current_key
        content_changed = row.content_sha256 != current_hash
        if not (key_changed or content_changed):
            continue
        code = 'key_and_content_changed' if key_changed and content_changed else (
            'key_changed' if key_changed else 'content_changed')
        changed.append((row, code))
    if not changed:
        return 0
    actor = _actor_or_none(actor)
    logs = []
    with transaction.atomic():
        for row, code in changed:
            before = _review_state(row)
            QuestionEvidence.objects.filter(pk=row.pk).update(review_status='stale', student_visible=False,
                                                              stale_reason=code, updated_at=timezone.now())
            row.review_status, row.student_visible, row.stale_reason = 'stale', False, code
            logs.append(EvidenceReviewLog(evidence_id=row.pk, actor=actor, action='restale', before=before,
                                          after=_review_state(row), note=(reason or '')[:2000]))
        EvidenceReviewLog.objects.bulk_create(logs)
    return len(changed)


def on_question_changed(question, *, old_key: str = '', old_stem_hash: str = '', reason: str = '', actor=None,
                        **kwargs) -> int:
    """``questions.content_hooks`` reaction: evidence for the old key / content goes stale."""
    return mark_stale(question, reason=reason, actor=actor)


# ── figures ─────────────────────────────────────────────────────────────────────────────────

def create_figure(evidence, *, actor, bbox, dpi: int = DEFAULT_FIGURE_DPI):
    """Crop ``bbox`` (PDF points, top-left origin) from the evidence row's first page and attach
    it as an EvidenceFigure. Refuses crops larger than EVIDENCE_FIGURE_MAX_AREA_RATIO of the
    page; the crop's long side is scaled to at most EVIDENCE_FIGURE_MAX_PX."""
    from django.core.files.base import ContentFile
    from PIL import Image

    from questions.image_context import flatten_to_rgb

    from .models import EvidenceFigure, EvidenceReviewLog, QuestionEvidence

    box = _clean_bbox(bbox)
    if box is None:
        raise EvidenceError('bbox is required', field='bbox')
    try:
        dpi = max(50, min(int(dpi or DEFAULT_FIGURE_DPI), FIGURE_MAX_DPI))
    except (TypeError, ValueError):
        dpi = DEFAULT_FIGURE_DPI
    row = QuestionEvidence.objects.select_related('source').get(pk=evidence.pk)
    png = render_page_png(row.source.sha256, row.page_start, dpi=dpi)
    if not png:
        raise ReferenceStoreUnavailable('the page image cannot be rendered here')
    try:
        page = Image.open(io.BytesIO(png))
        page.load()
    except Exception:  # noqa: BLE001
        raise ReferenceStoreUnavailable('the page image could not be read')
    scale = dpi / 72.0
    width_pt, height_pt = page.width / scale, page.height / scale
    x0, y0 = min(box[0], width_pt), min(box[1], height_pt)
    x1, y1 = min(box[2], width_pt), min(box[3], height_pt)
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise EvidenceError('bbox lies outside the page', field='bbox')
    max_ratio = float(getattr(settings, 'EVIDENCE_FIGURE_MAX_AREA_RATIO', 0.35))
    ratio = ((x1 - x0) * (y1 - y0)) / max(1.0, width_pt * height_pt)
    if ratio > max_ratio:
        raise FigureTooLarge(f'a figure may cover at most {int(max_ratio * 100)}% of the page', area_ratio=round(ratio, 3))
    crop = flatten_to_rgb(page.crop((int(x0 * scale), int(y0 * scale), int(round(x1 * scale)), int(round(y1 * scale)))))
    max_px = int(getattr(settings, 'EVIDENCE_FIGURE_MAX_PX', 1400))
    if max(crop.size) > max_px:
        crop.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    crop.save(buf, format='PNG', optimize=True)
    clean_box = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
    actor = _actor_or_none(actor)
    with transaction.atomic():
        figure = EvidenceFigure(source=row.source, page_no=row.page_start, bbox=clean_box, width=crop.width,
                                height=crop.height, created_by=actor)
        name = f'{row.source.sha256[:16]}-p{row.page_start}-{secrets.token_hex(8)}.png'
        figure.image.save(name, ContentFile(buf.getvalue()), save=False)
        figure.save()
        locked = QuestionEvidence.objects.select_for_update().get(pk=row.pk)
        before = {'figure_id': locked.figure_id, 'bbox': locked.bbox}
        locked.figure = figure
        locked.bbox = clean_box
        locked.save(update_fields=['figure', 'bbox', 'updated_at'])
        EvidenceReviewLog.objects.create(evidence=locked, actor=actor, action='crop', before=before,
                                         after={'figure_id': figure.pk, 'bbox': clean_box})
    return figure
