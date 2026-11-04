"""DOCX ingestion: ``word/document.xml`` read directly (zip + lxml), blocks in document order.

DOCX files have no pages. A "page" here is a **section**: it starts at a level-1/2 heading
(Heading 1/2, Title or outline level 0-1) and is split again at a paragraph boundary when it
grows past SECTION_MAX_CHARS. ``page_no`` is the section ordinal (1-based), ``page_label`` is
empty, and the locator shown to people is the section heading path. Headings of every level
set the section path; tables stay in place as table segments (markdown rows); "Figure N"
paragraphs (or the Caption style) become figure captions.

Only the XML parts are read (not the embedded images), so a 35 MB notes file costs a few MB.
"""
from __future__ import annotations

import re
import time
import zipfile
from collections import Counter
from typing import Iterator, Optional

from ..textutil import normalize_text, text_quality
from .base import (
    FIGURE_CAPTION_RE, TABLE_CAPTION_RE, FigureRecord, IngestResult, PageBuilder, PageRecord, SectionStack,
)

PARSER = 'docx-xml'
PARSER_VERSION = 'docx-v1'
SECTION_MAX_CHARS = 4000
SECTION_LEVELS = 2              # headings at or above this level start a new section ("page")

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC_FALLBACK = '{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback'
_HEADING_STYLE_RE = re.compile(r'^(?:heading|überschrift|titre)\s*(\d)$', re.IGNORECASE)


def _styles(zf: zipfile.ZipFile) -> dict[str, tuple[str, Optional[int]]]:
    """styleId -> (style name, heading level or None)."""
    from lxml import etree
    try:
        root = etree.fromstring(zf.read('word/styles.xml'))
    except (KeyError, etree.XMLSyntaxError):
        return {}
    out = {}
    for st in root.iter(W + 'style'):
        sid = st.get(W + 'styleId') or ''
        name_el = st.find(W + 'name')
        name = (name_el.get(W + 'val') if name_el is not None else sid) or sid
        level = None
        m = _HEADING_STYLE_RE.match(name.strip())
        if m:
            level = int(m.group(1))
        elif name.strip().lower() == 'title':
            level = 1
        elif name.strip().lower() == 'subtitle':
            level = 2
        else:
            ol = st.find(f'{W}pPr/{W}outlineLvl')
            if ol is not None and (ol.get(W + 'val') or '').isdigit() and int(ol.get(W + 'val')) < 9:
                level = int(ol.get(W + 'val')) + 1
        out[sid] = (name, level)
    return out


def _skip(el) -> bool:
    """Inside an mc:Fallback (duplicate of mc:Choice text boxes)."""
    parent = el.getparent()
    while parent is not None:
        if parent.tag == MC_FALLBACK:
            return True
        parent = parent.getparent()
    return False


def _para_text(p) -> str:
    parts = []
    for el in p.iter(W + 't', W + 'tab', W + 'br', W + 'cr'):
        if el.tag == W + 't':
            if not _skip(el):
                parts.append(el.text or '')
        elif el.tag == W + 'tab':
            parts.append('\t')
        else:
            parts.append('\n')
    return normalize_text(''.join(parts))


def _para_style(p, styles) -> tuple[str, Optional[int]]:
    ppr = p.find(W + 'pPr')
    name, level = '', None
    if ppr is not None:
        ps = ppr.find(W + 'pStyle')
        if ps is not None:
            name, level = styles.get(ps.get(W + 'val') or '', (ps.get(W + 'val') or '', None))
            if level is None:
                m = _HEADING_STYLE_RE.match((ps.get(W + 'val') or '').replace('Heading', 'Heading '))
                if m:
                    level = int(m.group(1))
        ol = ppr.find(W + 'outlineLvl')
        if level is None and ol is not None and (ol.get(W + 'val') or '').isdigit() and int(ol.get(W + 'val')) < 9:
            level = int(ol.get(W + 'val')) + 1
    return name, level


def _pseudo_heading(text: str) -> bool:
    """A short all-capitals line ("TUBERCULOSIS", "CLINICAL FEATURES") used as a heading."""
    letters = [c for c in text if c.isalpha()]
    return (3 <= len(text) <= 80 and len(letters) >= 3 and text.upper() == text and not text.rstrip().endswith('.')
            and len(text.split()) <= 10)


def _cell_text(tc) -> str:
    texts = [_para_text(p) for p in tc.iter(W + 'p')]
    return ' '.join(' '.join(t.split()) for t in texts if t).replace('|', '/')


def _table_rows(tbl) -> list[str]:
    rows = []
    for tr in tbl.iterchildren(W + 'tr'):
        cells = []
        for tc in tr.iterchildren(W + 'tc'):
            vm = tc.find(f'{W}tcPr/{W}vMerge')
            if vm is not None and (vm.get(W + 'val') or 'continue') == 'continue':
                cells.append('')
                continue
            cells.append(_cell_text(tc))
        if any(cells):
            rows.append(' | '.join(cells))
    return rows


def _blocks(body) -> Iterator:
    for child in body.iterchildren():
        tag = child.tag
        if tag in (W + 'p', W + 'tbl'):
            yield child
        elif tag in (W + 'sdt', W + 'customXml'):
            content = child.find(W + 'sdtContent') if tag == W + 'sdt' else child
            if content is not None:
                yield from _blocks(content)


def ingest_docx(path: str, *, max_pages: Optional[int] = None) -> IngestResult:
    from lxml import etree

    started = time.perf_counter()
    result = IngestResult(parser=PARSER, parser_version=PARSER_VERSION)
    try:
        with zipfile.ZipFile(path) as zf:
            styles = _styles(zf)
            root = etree.fromstring(zf.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, OSError, etree.XMLSyntaxError) as exc:
        result.error = f'cannot read DOCX: {type(exc).__name__}'
        return result
    body = root.find(W + 'body')
    if body is None:
        result.error = 'DOCX without a body'
        return result

    stats = Counter()
    sections = SectionStack()
    pages: list[PageRecord] = []
    state = {'pb': None, 'rec': None}

    def open_section():
        page_no = len(pages) + 1
        rec = PageRecord(page_no=page_no, method='docx', section_path=sections.path, chapter=sections.chapter)
        state['pb'], state['rec'] = PageBuilder(page_no), rec
        pages.append(rec)

    def close_section():
        pb, rec = state['pb'], state['rec']
        if pb is not None:
            rec.text, rec.segments = pb.text, pb.segments
            rec.text_quality = text_quality(rec.text)
        state['pb'] = state['rec'] = None

    def add(kind, text, **extra):
        if state['pb'] is None or (state['pb'].length >= SECTION_MAX_CHARS and kind != 'heading'):
            close_section()
            open_section()
        state['pb'].add(kind, text, section_path=sections.path, chapter=sections.chapter, sep='\n', **extra)

    for block in _blocks(body):
        if max_pages and len(pages) > max_pages:
            break
        if block.tag == W + 'tbl':
            rows = _table_rows(block)
            if not rows:
                continue
            if len(rows) == 1 or max(r.count(' | ') for r in rows) == 0:
                add('text', '\n'.join(r.replace(' | ', ' ') for r in rows))
            else:
                add('table', '\n'.join(rows), table_rows=rows, table_caption='')
                stats['tables'] += 1
            continue
        text = _para_text(block)
        if not text:
            continue
        style, level = _para_style(block, styles)
        if level is None and _pseudo_heading(text):
            level = 3
            stats['pseudo_headings'] += 1
        if level is not None and len(text) <= 200:
            if level <= SECTION_LEVELS:
                close_section()
                sections.set(level, text)
                open_section()
            else:
                sections.set(level, text)
            add('heading', text)
            stats['headings'] += 1
        elif FIGURE_CAPTION_RE.match(text) or style.lower() == 'caption':
            if TABLE_CAPTION_RE.match(text):
                add('caption', text)
            else:
                result.figures.append(FigureRecord(page_no=(len(pages) or 1), caption=text[:2000]))
                add('figure', text, figure_index=len(result.figures) - 1)
                stats['figure_captions'] += 1
        elif TABLE_CAPTION_RE.match(text) and len(text) <= 200:
            add('caption', text)
        else:
            add('text', text)
    close_section()
    if max_pages:
        pages = pages[:max_pages]
    result.pages = [p for p in pages if p.text]
    # Renumber after dropping empty sections so page_no stays a dense ordinal.
    for i, rec in enumerate(result.pages, start=1):
        if rec.page_no != i:
            for fig in result.figures:
                if fig.page_no == rec.page_no:
                    fig.page_no = i
            rec.page_no = i
    result.page_count = len(result.pages)
    stats['sections'] = len(result.pages)
    stats['seconds'] = round(time.perf_counter() - started, 2)
    result.stats = dict(stats)
    return result
