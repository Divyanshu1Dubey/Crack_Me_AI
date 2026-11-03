"""Ingestion data model and the layout rules shared by the PDF / DOCX / text parsers.

A parser turns one source file into ``PageRecord``s: the cleaned text of each page (1-based
``page_no``; DOCX / text: section ordinal) plus ordered ``Segment``s that say which spans of that
text are prose, a table, a figure caption or a table caption, and which section they belong
to. The chunker works only on these records, so every chunk is traceable to page text.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..textutil import norm_phrase

SEGMENT_KINDS = ('text', 'table', 'figure', 'caption', 'heading')


@dataclass
class Segment:
    kind: str                  # text | table | figure | caption | heading
    start: int                 # offsets into PageRecord.text
    end: int
    section_path: str = ''
    chapter: str = ''
    figure_index: Optional[int] = None   # index into IngestResult.figures (figure captions)
    table_rows: Optional[list[str]] = None   # markdown rows of a table (header first)
    table_caption: str = ''


@dataclass
class PageRecord:
    page_no: int
    text: str = ''
    segments: list[Segment] = field(default_factory=list)
    page_label: Optional[str] = None
    label_source: str = 'none'           # pdf_labels | running_header | interpolated | none
    section_path: str = ''
    chapter: str = ''
    method: str = 'text'                 # text | ocr | docx | txt | none
    ocr: bool = False
    ocr_engine: Optional[str] = None
    ocr_pending: bool = False            # image-only page whose OCR text is not available yet
    text_quality: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class FigureRecord:
    page_no: int
    caption: str
    bbox: Optional[tuple] = None         # PDF points (x0, y0, x1, y1)


@dataclass
class IngestResult:
    parser: str
    parser_version: str
    page_count: int = 0
    pages: list[PageRecord] = field(default_factory=list)
    figures: list[FigureRecord] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    error: str = ''


class PageBuilder:
    """Accumulates the text of one page segment by segment, recording offsets."""

    def __init__(self, page_no: int):
        self.page_no = page_no
        self.parts: list[str] = []
        self.length = 0
        self.segments: list[Segment] = []

    def add(self, kind: str, text: str, *, section_path='', chapter='', sep='\n', **extra) -> Optional[Segment]:
        text = (text or '').strip()
        if not text:
            return None
        if self.parts:
            self.parts.append(sep)
            self.length += len(sep)
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        seg = Segment(kind=kind, start=start, end=self.length, section_path=section_path, chapter=chapter, **extra)
        self.segments.append(seg)
        return seg

    @property
    def text(self) -> str:
        return ''.join(self.parts)


# ─── running headers / footers and printed page labels ─────────────────

MARGIN_FRACTION = 0.08          # top / bottom share of the page height treated as header / footer zone
RUNNING_MIN_PAGES = 3           # a margin line repeated (digits masked) on this many pages is a running header
LABEL_MIN_RUN = 5               # plain numbers: label - page_no constant over >= 5 supporting pages
LABEL_MIN_RUN_PREFIXED = 3      # prefixed labels such as Nelson's online pages "e330-9"
LABEL_MAX_GAP = 2               # pages without a readable number inside a run (chapter openers)

_DIGITS_RE = re.compile(r'\d+')
_E_LABEL_RE = re.compile(r'\b(e\d{1,4}-)(\d{1,3})\b', re.IGNORECASE)
_NOISE_TOKEN_RE = re.compile(r"^(?:[^0-9A-Za-z]+|[IlL|]{1,3}|page|pg|p)$", re.IGNORECASE)
_PAGE_NUMBER_LINE_RE = re.compile(
    r"^[^0-9A-Za-z]*(?:page|pg|p)?[^0-9A-Za-z]*(?:e\d{1,4}-)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?[^0-9A-Za-z]*$",
    re.IGNORECASE)


def masked(text: str) -> str:
    """Digit-masked, folded form of a margin line ("Chapter 8 ... I 27" -> "chapter # ... i #")."""
    return _DIGITS_RE.sub('#', norm_phrase(text))


def is_page_number_line(text: str) -> bool:
    t = (text or '').strip()
    if not t:
        return False
    if _PAGE_NUMBER_LINE_RE.match(t):
        return True
    tokens = [tok for tok in t.split() if not _NOISE_TOKEN_RE.match(tok)]
    return len(tokens) == 1 and bool(re.fullmatch(r'(?:e\d{1,4}-)?\d{1,4}', tokens[0], re.IGNORECASE))


def label_candidates(text: str) -> set[tuple[str, int]]:
    """Printed page numbers a margin line could carry: a number at its start or end, any lone
    number in a short (noisy) line, or a prefixed label like "e330-9"."""
    out: set[tuple[str, int]] = set()
    t = (text or '').strip()
    if not t:
        return out
    for m in _E_LABEL_RE.finditer(t):
        out.add((m.group(1).lower(), int(m.group(2))))
    t_wo = _E_LABEL_RE.sub(' ', t)
    tokens = [tok.strip('.,:;()[]') for tok in t_wo.split()]
    tokens = [tok for tok in tokens if tok and not _NOISE_TOKEN_RE.match(tok)]
    if not tokens:
        return out
    nums = [tok for tok in tokens if re.fullmatch(r'\d{1,4}', tok)]
    if len(tokens) <= 3:
        out.update(('', int(n)) for n in nums)
    else:
        if re.fullmatch(r'\d{1,4}', tokens[0]):
            out.add(('', int(tokens[0])))
        if re.fullmatch(r'\d{1,4}', tokens[-1]):
            out.add(('', int(tokens[-1])))
    return {(p, n) for p, n in out if 0 < n < 10000}


def running_lines(margin_lines: dict[int, list[str]]) -> set[str]:
    """Masked margin lines repeated on at least RUNNING_MIN_PAGES pages."""
    pages_per_form: dict[str, set[int]] = defaultdict(set)
    for page_no, lines in margin_lines.items():
        for line in lines:
            form = masked(line)
            if form:
                pages_per_form[form].add(page_no)
    return {form for form, pages in pages_per_form.items() if len(pages) >= RUNNING_MIN_PAGES}


def assign_labels(candidates: dict[int, set[tuple[str, int]]]) -> dict[int, tuple[str, str]]:
    """page_no -> (label, label_source) from running-header numbers.

    A label is accepted only inside a run where printed number minus page_no stays constant
    over at least LABEL_MIN_RUN supporting pages (gaps of up to LABEL_MAX_GAP pages allowed);
    pages inside a run without a readable number get the run's number ('interpolated'), which
    is safe because a constant offset on both sides means no page was inserted in between.
    Conflicting runs leave a page unlabelled.
    """
    by_key: dict[tuple[str, int], list[int]] = defaultdict(list)
    for page_no, cands in candidates.items():
        for prefix, num in cands:
            by_key[(prefix, num - page_no)].append(page_no)
    runs = []
    for key, pages in by_key.items():
        pages = sorted(set(pages))
        need = LABEL_MIN_RUN_PREFIXED if key[0] else LABEL_MIN_RUN
        cur = [pages[0]]
        for p in pages[1:]:
            if p - cur[-1] <= LABEL_MAX_GAP + 1:
                cur.append(p)
            else:
                if len(cur) >= need:
                    runs.append((key, cur))
                cur = [p]
        if len(cur) >= need:
            runs.append((key, cur))
    assigned: dict[int, tuple[int, tuple[str, str]]] = {}
    conflicted: set[int] = set()
    for (prefix, offset), support in runs:
        support_set = set(support)
        strength = len(support)
        for p in range(support[0], support[-1] + 1):
            num = p + offset
            if num < 1:
                continue
            label = f'{prefix}{num}'
            source = 'running_header' if p in support_set else 'interpolated'
            prev = assigned.get(p)
            if prev is None:
                assigned[p] = (strength, (label, source))
            elif prev[1][0] != label:
                if strength > prev[0]:
                    assigned[p] = (strength, (label, source))
                elif strength == prev[0]:
                    conflicted.add(p)
    return {p: v[1] for p, v in assigned.items() if p not in conflicted}


# ─── sections ──────────────────────────────────────────────────────────

MAX_SECTION_DEPTH = 4
_CHAPTER_RE = re.compile(r'^(?:chapter|chap\.?|ch\.?|unit|lesson)\s*[\dIVXLC]+\b', re.IGNORECASE)


def chapter_of(path: list[str]) -> str:
    for title in path:
        if _CHAPTER_RE.match(title):
            return title
    return path[0] if path else ''


class SectionStack:
    """A heading hierarchy: set(level, title) pops deeper levels and pushes the title."""

    def __init__(self):
        self.stack: list[tuple[int, str]] = []

    def set(self, level: int, title: str):
        title = ' '.join((title or '').split())[:160]
        if not title:
            return
        level = max(1, min(int(level), MAX_SECTION_DEPTH))
        while self.stack and self.stack[-1][0] >= level:
            self.stack.pop()
        self.stack.append((level, title))

    @property
    def titles(self) -> list[str]:
        return [t for _l, t in self.stack]

    @property
    def path(self) -> str:
        return ' > '.join(self.titles)

    @property
    def chapter(self) -> str:
        return chapter_of(self.titles)


def toc_by_page(toc: list) -> dict[int, list[tuple[int, str]]]:
    """PyMuPDF ``get_toc(simple=True)`` rows [level, title, page(1-based)] grouped by page."""
    out: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in toc or []:
        try:
            level, title, page = int(row[0]), str(row[1]), int(row[2])
        except (TypeError, ValueError, IndexError):
            continue
        if page >= 1 and title.strip():
            out[page].append((level, title.strip()))
    return out


def heading_matches(title: str, line: str) -> bool:
    """Does a page line print this TOC title (or its first part, for a wrapped heading)?"""
    t, ln = norm_phrase(title), norm_phrase(line)
    if not t or not ln:
        return False
    if ln == t or ln.startswith(t):
        return True
    if len(ln) >= 12 and t.startswith(ln):
        return True
    head = t[:40]
    return len(head) >= 12 and ln.startswith(head)


def plan_toc(n_pending: int, matched: set[int]) -> tuple[list[int], dict[int, list[int]]]:
    """For the TOC entries starting on a page (in outline order): the unmatched ones before the
    first heading found in the text apply at the top of the page; later unmatched ones follow
    the matched heading before them (they are its sub-sections)."""
    top, followers, current = [], {}, None
    for idx in range(n_pending):
        if idx in matched:
            current = idx
            followers[idx] = []
        elif current is None:
            top.append(idx)
        else:
            followers[current].append(idx)
    return top, followers


def body_font_size(size_chars: Counter) -> float:
    return size_chars.most_common(1)[0][0] if size_chars else 0.0


def heading_levels(heading_sizes: Counter, body: float, *, max_levels: int = 3) -> dict[float, int]:
    """Font size -> heading level (largest = 1) for sizes clearly above the body size."""
    sizes = sorted((s for s in heading_sizes if body and s >= body * 1.18), reverse=True)
    return {s: min(i + 1, max_levels) for i, s in enumerate(sizes)}


FIGURE_CAPTION_RE = re.compile(r'^\s*(?:fig(?:ure)?s?\.?|plate)\s*[\dIVX]+[\w.\-–]*', re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r'^\s*table\s*[\dIVX]+[\w.\-–]*', re.IGNORECASE)
