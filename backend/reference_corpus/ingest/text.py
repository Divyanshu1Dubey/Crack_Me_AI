"""Plain text / Markdown ingestion. Like DOCX, a "page" is a section: Markdown headings
(``#`` / ``##``) start one, long sections are split at a paragraph boundary, ``page_no`` is the
section ordinal and there is no printed label."""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Optional

from ..textutil import join_lines, normalize_text, text_quality
from .base import FIGURE_CAPTION_RE, FigureRecord, IngestResult, PageBuilder, PageRecord, SectionStack

PARSER = 'text'
PARSER_VERSION = 'text-v1'
SECTION_MAX_CHARS = 4000
_MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$')


def ingest_text(path: str, *, max_pages: Optional[int] = None) -> IngestResult:
    started = time.perf_counter()
    result = IngestResult(parser=PARSER, parser_version=PARSER_VERSION)
    try:
        with open(path, 'rb') as fh:
            raw = fh.read()
    except OSError as exc:
        result.error = f'cannot read file: {type(exc).__name__}'
        return result
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    text = normalize_text(text)
    is_md = path.lower().endswith('.md')
    stats = Counter()
    sections = SectionStack()
    pages: list[PageRecord] = []
    state = {'pb': None, 'rec': None}

    def open_section():
        rec = PageRecord(page_no=len(pages) + 1, method='txt', section_path=sections.path, chapter=sections.chapter)
        state['pb'], state['rec'] = PageBuilder(rec.page_no), rec
        pages.append(rec)

    def close_section():
        if state['pb'] is not None:
            state['rec'].text, state['rec'].segments = state['pb'].text, state['pb'].segments
            state['rec'].text_quality = text_quality(state['rec'].text)
        state['pb'] = state['rec'] = None

    def add(kind, body, **extra):
        if state['pb'] is None or (state['pb'].length >= SECTION_MAX_CHARS and kind != 'heading'):
            close_section()
            open_section()
        state['pb'].add(kind, body, section_path=sections.path, chapter=sections.chapter, sep='\n\n', **extra)

    for para in re.split(r'\n\s*\n', text):
        lines = [ln for ln in para.split('\n') if ln.strip()]
        buf = []
        for ln in lines:
            m = _MD_HEADING_RE.match(ln) if is_md else None
            if m:
                if buf:
                    add('text', join_lines(buf))
                    buf = []
                level, title = len(m.group(1)), m.group(2)
                if level <= 2:
                    close_section()
                    sections.set(level, title)
                    open_section()
                else:
                    sections.set(level, title)
                add('heading', ln)
                stats['headings'] += 1
            elif FIGURE_CAPTION_RE.match(ln):
                if buf:
                    add('text', join_lines(buf))
                    buf = []
                result.figures.append(FigureRecord(page_no=len(pages) or 1, caption=ln[:2000]))
                add('figure', ln, figure_index=len(result.figures) - 1)
            else:
                buf.append(ln)
        if buf:
            add('text', join_lines(buf))
        if max_pages and len(pages) > max_pages:
            break
    close_section()
    result.pages = [p for p in pages if p.text][: max_pages or None]
    result.page_count = len(result.pages)
    stats['sections'] = len(result.pages)
    stats['seconds'] = round(time.perf_counter() - started, 2)
    result.stats = dict(stats)
    return result
