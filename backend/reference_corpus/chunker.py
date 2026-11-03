"""Sentence-aware chunking of ingested pages (CHUNKER_VERSION).

* Prose chunks of about 180-250 words (hard cap 320) made of whole sentences. A chunk never
  crosses a section boundary (a heading or a change of section path) and never mixes kinds; it
  may cross a page boundary instead of cutting a sentence (``page_start`` .. ``page_end``).
* Each table becomes one chunk, or several of at most TABLE_ROWS_PER_CHUNK rows with the header
  row repeated. Figure captions and table captions are chunks of their own.
* A prose chunk's text is an exact substring of its page text (pieces from consecutive pages are
  joined with a newline), with ``char_start`` / ``char_end`` offsets into the first / last page,
  so a quote can be located and highlighted on the page.
* ``chunk_key`` = sha1(source sha256 | page_start | ordinal on that page | CHUNKER_VERSION), first
  16 hex characters: a stable citation handle as long as the source file and chunker version do
  not change.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from .ingest.base import PageRecord
from .textutil import sentence_spans, word_count

CHUNKER_VERSION = 'chunk-v1'
TARGET_MIN_WORDS = 180
TARGET_MAX_WORDS = 250
HARD_CAP_WORDS = 320
TABLE_ROWS_PER_CHUNK = 15


@dataclass
class ChunkRecord:
    page_start: int
    page_end: int
    kind: str
    text: str
    section_path: str = ''
    chapter: str = ''
    label_start: Optional[str] = None
    label_end: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    ocr: bool = False
    token_count: int = 0
    ordinal: int = 0
    figure_index: Optional[int] = None


@dataclass
class _Piece:
    page: int          # index into pages
    start: int
    end: int
    words: int
    ends: bool
    heading: bool


def chunk_key(sha256: str, page_start: int, ordinal: int) -> str:
    raw = f'{sha256}|{page_start}|{ordinal}|{CHUNKER_VERSION}'.encode('utf-8')
    return hashlib.sha1(raw, usedforsecurity=False).hexdigest()[:16]


def _word_windows(text: str, start: int, end: int, size: int) -> list[tuple[int, int]]:
    """Split text[start:end] into consecutive spans of at most ``size`` words."""
    import re
    bounds = [(m.start() + start, m.end() + start) for m in re.finditer(r'\S+', text[start:end])]
    out = []
    for i in range(0, len(bounds), size):
        part = bounds[i:i + size]
        out.append((part[0][0], part[-1][1]))
    return out


def chunk_pages(pages: list[PageRecord]) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    cur: list[_Piece] = []
    state = {'section': None, 'chapter': '', 'words': 0}

    def emit(rec: ChunkRecord):
        rec.token_count = word_count(rec.text)
        if rec.text.strip():
            chunks.append(rec)

    def flush():
        if cur and not all(p.heading for p in cur):
            first, last = cur[0], cur[-1]
            parts, i = [], 0
            while i < len(cur):
                j = i
                while j + 1 < len(cur) and cur[j + 1].page == cur[i].page:
                    j += 1
                page = pages[cur[i].page]
                parts.append(page.text[cur[i].start:cur[j].end])
                i = j + 1
            p0, p1 = pages[first.page], pages[last.page]
            emit(ChunkRecord(
                page_start=p0.page_no, page_end=p1.page_no, kind='text', text='\n'.join(parts),
                section_path=state['section'] or '', chapter=state['chapter'],
                label_start=p0.page_label, label_end=p1.page_label, char_start=first.start, char_end=last.end,
                ocr=any(pages[p.page].ocr for p in cur)))
        cur.clear()
        state['words'] = 0

    for pi, page in enumerate(pages):
        for seg in page.segments:
            if seg.kind == 'table':
                flush()
                _table_chunks(page, seg, emit)
                continue
            if seg.kind in ('figure', 'caption'):
                flush()
                spans = _word_windows(page.text, seg.start, seg.end, HARD_CAP_WORDS)
                for s, e in spans:
                    emit(ChunkRecord(page_start=page.page_no, page_end=page.page_no, kind=seg.kind,
                                     text=page.text[s:e], section_path=seg.section_path, chapter=seg.chapter,
                                     label_start=page.page_label, label_end=page.page_label, char_start=s, char_end=e,
                                     ocr=page.ocr, figure_index=seg.figure_index))
                continue
            # prose and headings
            if seg.kind == 'heading' or seg.section_path != state['section']:
                flush()
                state['section'], state['chapter'] = seg.section_path, seg.chapter
            if seg.kind == 'heading':
                spans = [(seg.start, seg.end, True)]
            else:
                spans = sentence_spans(page.text, seg.start, seg.end)
            for s, e, ends in spans:
                words = word_count(page.text[s:e])
                windows = [(s, e)] if words <= HARD_CAP_WORDS else _word_windows(page.text, s, e, TARGET_MAX_WORDS)
                for wi, (ws, we) in enumerate(windows):
                    w = words if len(windows) == 1 else word_count(page.text[ws:we])
                    piece_ends = ends if wi == len(windows) - 1 else False
                    if cur:
                        total = state['words'] + w
                        if cur[-1].ends and ((total > TARGET_MAX_WORDS and state['words'] >= TARGET_MIN_WORDS)
                                             or total > HARD_CAP_WORDS):
                            flush()
                        elif not cur[-1].ends and total > HARD_CAP_WORDS + 80:
                            flush()                      # a "sentence" without an end (OCR noise, lists)
                    cur.append(_Piece(pi, ws, we, w, piece_ends, seg.kind == 'heading'))
                    state['words'] += w
    flush()
    # Ordinals per starting page (stable chunk keys).
    per_page: dict[int, int] = {}
    for rec in chunks:
        rec.ordinal = per_page.get(rec.page_start, 0)
        per_page[rec.page_start] = rec.ordinal + 1
    return chunks


def _table_chunks(page: PageRecord, seg, emit):
    rows = seg.table_rows or page.text[seg.start:seg.end].split('\n')
    caption = seg.table_caption or ''
    header, body = rows[0], rows[1:]
    whole = page.text[seg.start:seg.end]
    if len(body) <= TABLE_ROWS_PER_CHUNK and word_count(whole) <= HARD_CAP_WORDS:
        groups = [body]
    else:
        groups, cur, cur_words = [], [], word_count(header) + word_count(caption)
        for row in body:
            w = word_count(row)
            if cur and (len(cur) >= TABLE_ROWS_PER_CHUNK or cur_words + w > HARD_CAP_WORDS):
                groups.append(cur)
                cur, cur_words = [], word_count(header) + word_count(caption)
            cur.append(row)
            cur_words += w
        if cur:
            groups.append(cur)
    for group in groups:
        lines = ([caption] if caption else []) + [header] + group
        emit(ChunkRecord(page_start=page.page_no, page_end=page.page_no, kind='table', text='\n'.join(lines),
                         section_path=seg.section_path, chapter=seg.chapter, label_start=page.page_label,
                         label_end=page.page_label, char_start=seg.start, char_end=seg.end, ocr=page.ocr))
