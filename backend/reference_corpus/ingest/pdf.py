"""PDF ingestion with PyMuPDF (text layer only; OCR text comes from the page cache).

Two passes over the document:

1. Layout survey: header/footer zone lines of every page (running headers are lines that
   repeat, digits masked, on >= 3 pages), printed page-number candidates, the body font size,
   which pages carry table / figure captions, which pages are image-only.
2. Extraction: ``page.get_text('dict')`` blocks in content order with running headers, footers
   and page-number lines removed; tables found by ``page.find_tables()`` (only on pages with a
   "Table N" caption: the finder costs 0.1-0.3 s per page) become table segments and their area
   is removed from the prose; "Fig./Figure N" blocks become figure-caption segments (with the
   nearest image's bounding box); section paths come from the PDF outline (TOC) or, without
   one, from font-size headings.

Image-only pages (< OCR_MIN_CHARS characters of text layer and at least one image) take their
text from the page cache's OCR; without cached OCR they are kept empty with ``ocr_pending``.
"""
from __future__ import annotations

import contextlib
import io
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from ..textutil import join_lines, normalize_text, text_quality, word_count
from .base import (
    FIGURE_CAPTION_RE, MARGIN_FRACTION, TABLE_CAPTION_RE, FigureRecord, IngestResult, PageBuilder, PageRecord,
    SectionStack, assign_labels, body_font_size, heading_levels, heading_matches, is_page_number_line,
    label_candidates, masked, plan_toc, running_lines, toc_by_page,
)

logger = logging.getLogger(__name__)

PARSER = 'pymupdf'
PARSER_VERSION = 'pdf-v1'
OCR_MIN_CHARS = 80          # same rule as ai_eval.build_reference_corpus (image-only page)
MAX_HEADING_WORDS = 15
MARGIN_LINES = 3            # at most this many lines per zone are header / footer candidates


@dataclass
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool


def _text_flags():
    import fitz
    # Ligatures expanded (no TEXT_PRESERVE_LIGATURES), no image payloads in the dict.
    return fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP


def _blocks(page, flags) -> list[list[Line]]:
    """Text blocks -> lines (content order)."""
    out = []
    for block in page.get_text('dict', flags=flags).get('blocks', []):
        if block.get('type') != 0:
            continue
        lines = []
        for ln in block.get('lines', []):
            spans = [s for s in ln.get('spans', []) if s.get('text')]
            if not spans:
                continue
            text = normalize_text(''.join(s['text'] for s in spans))
            if not text:
                continue
            main = max(spans, key=lambda s: len(s['text'].strip()))
            bold = bool(main.get('flags', 0) & 16) or 'bold' in (main.get('font') or '').lower()
            x0, y0, x1, y1 = ln['bbox']
            lines.append(Line(text, x0, y0, x1, y1, round(float(main.get('size', 0.0)) * 2) / 2, bold))
        if lines:
            out.append(lines)
    return out


def _margin_lines(blocks: list[list[Line]], height: float) -> list[Line]:
    lines = [ln for blk in blocks for ln in blk]
    top = sorted((ln for ln in lines if ln.y0 < height * MARGIN_FRACTION), key=lambda ln: ln.y0)[:MARGIN_LINES]
    bottom = sorted((ln for ln in lines if ln.y1 > height * (1 - MARGIN_FRACTION)), key=lambda ln: -ln.y1)[:MARGIN_LINES]
    return top + [ln for ln in bottom if ln not in top]


def _ocr_margin(text: str) -> list[str]:
    lines = [ln for ln in text.split('\n') if ln.strip()]
    return lines[:2] + lines[-2:] if len(lines) > 4 else lines


def _has_images(page) -> bool:
    try:
        return bool(page.get_images(full=False))
    except Exception:  # noqa: BLE001
        return False


def _image_boxes(page) -> list[tuple]:
    try:
        return [tuple(info['bbox']) for info in page.get_image_info() if info.get('bbox')]
    except Exception:  # noqa: BLE001
        return []


def _md_cell(value) -> str:
    return ' '.join(str(value or '').split()).replace('|', '/')


def _tables(page) -> list[dict]:
    """Detected tables: {bbox, caption, rows (markdown, header first)}; degenerate ones dropped."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            found = page.find_tables()
    except Exception as exc:  # noqa: BLE001
        logger.debug('find_tables failed: %s', exc)
        return []
    out = []
    for tab in found.tables:
        try:
            raw = tab.extract()
        except Exception:  # noqa: BLE001
            continue
        rows = [[_md_cell(c) for c in row] for row in raw if row and any((c or '').strip() for c in row)]
        caption = ''
        if rows and sum(1 for c in rows[0] if c) == 1 and TABLE_CAPTION_RE.match(next(c for c in rows[0] if c)):
            caption = next(c for c in rows[0] if c)
            rows = rows[1:]
        ncols = max((len(r) for r in rows), default=0)
        cells = sum(len(r) for r in rows) or 1
        filled = sum(1 for r in rows for c in r if c)
        if len(rows) < 2 or ncols < 2 or filled / cells < 0.3:
            continue
        out.append({'bbox': tuple(tab.bbox), 'caption': caption,
                    'rows': [' | '.join(r) for r in rows]})
    return out


def _inside(line: Line, bbox: tuple, tol: float = 2.0) -> bool:
    cx, cy = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
    return bbox[0] - tol <= cx <= bbox[2] + tol and bbox[1] - tol <= cy <= bbox[3] + tol


def _union(a: Optional[tuple], b: Optional[tuple]) -> Optional[tuple]:
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _figure_bbox(caption_bbox: tuple, images: list[tuple]) -> tuple:
    """Caption box joined with the closest image above it (else below it) that overlaps horizontally."""
    x0, y0, x1, y1 = caption_bbox
    best, best_gap = None, None
    for box in images:
        if box[2] < x0 - 5 or box[0] > x1 + 5:
            continue
        gap = y0 - box[3] if box[3] <= y0 + 10 else (box[1] - y1) * 2 if box[1] >= y1 - 10 else None
        if gap is None or gap > 250:
            continue
        if best_gap is None or gap < best_gap:
            best, best_gap = box, gap
    return tuple(round(v, 1) for v in _union(caption_bbox, best))


def ingest_pdf(path: str, *, ocr_text: Optional[dict[int, str]] = None, max_pages: Optional[int] = None,
               ocr_engine: str = '') -> IngestResult:
    import fitz

    started = time.perf_counter()
    result = IngestResult(parser=PARSER, parser_version=PARSER_VERSION)
    ocr_text = ocr_text or {}
    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        result.error = f'cannot open PDF: {type(exc).__name__}'
        return result
    try:
        if doc.needs_pass:
            result.error = 'encrypted PDF'
            return result
        n = doc.page_count if not max_pages else min(doc.page_count, int(max_pages))
        result.page_count = doc.page_count
        flags = _text_flags()
        stats = Counter()

        # ── pass 1: layout survey ──
        margin: dict[int, list[str]] = {}
        candidates: dict[int, set] = {}
        size_chars: Counter = Counter()
        short_sizes: Counter = Counter()
        needs_ocr, table_pages, figure_pages, dims = set(), set(), set(), {}
        for i in range(n):
            page_no = i + 1
            try:
                page = doc[i]
                dims[page_no] = (round(page.rect.width, 1), round(page.rect.height, 1))
                blocks = _blocks(page, flags)
            except Exception:  # noqa: BLE001
                stats['page_errors'] += 1
                continue
            chars = sum(len(ln.text) for blk in blocks for ln in blk)
            if chars < OCR_MIN_CHARS and _has_images(page):
                needs_ocr.add(page_no)
                if page_no in ocr_text:
                    lines = _ocr_margin(normalize_text(ocr_text[page_no]))
                    margin[page_no] = lines
                    candidates[page_no] = set().union(*(label_candidates(t) for t in lines)) if lines else set()
                continue
            mlines = _margin_lines(blocks, page.rect.height)
            margin[page_no] = [ln.text for ln in mlines]
            candidates[page_no] = set().union(*(label_candidates(ln.text) for ln in mlines)) if mlines else set()
            mids = {id(ln) for ln in mlines}
            for blk in blocks:
                for ln in blk:
                    if id(ln) in mids:
                        continue
                    size_chars[ln.size] += len(ln.text)
                    if word_count(ln.text) <= MAX_HEADING_WORDS and not ln.text.rstrip().endswith(('.', ',', ';')):
                        short_sizes[ln.size] += 1
                    if TABLE_CAPTION_RE.match(ln.text):
                        table_pages.add(page_no)
                    elif FIGURE_CAPTION_RE.match(ln.text):
                        figure_pages.add(page_no)

        running = running_lines(margin)
        labels: dict[int, tuple[str, str]] = {}
        try:
            has_pdf_labels = bool(doc.get_page_labels())
        except Exception:  # noqa: BLE001
            has_pdf_labels = False
        if has_pdf_labels:
            for i in range(n):
                label = (doc[i].get_label() or '').strip()
                if label:
                    labels[i + 1] = (label[:32], 'pdf_labels')
        else:
            labels = {p: (lab[:32], src) for p, (lab, src) in assign_labels(candidates).items()}
        try:
            toc = toc_by_page(doc.get_toc(simple=True))
        except Exception:  # noqa: BLE001
            toc = {}
        body = body_font_size(size_chars)
        levels = {} if toc else heading_levels(
            Counter({s: c for s, c in short_sizes.items() if size_chars.get(s, 0) <= 0.15 * sum(size_chars.values())}),
            body)
        stats.update(toc_entries=sum(len(v) for v in toc.values()), body_font_size=body,
                     heading_sizes=len(levels), running_header_forms=len(running))

        # ── pass 2: extraction ──
        sections = SectionStack()
        for i in range(n):
            page_no = i + 1
            width, height = dims.get(page_no, (None, None))
            label, label_src = labels.get(page_no, (None, 'none'))
            pending = list(toc.get(page_no, []))
            rec = PageRecord(page_no=page_no, width=width, height=height, page_label=label, label_source=label_src)
            pb = PageBuilder(page_no)

            if page_no in needs_ocr:
                if page_no in ocr_text:
                    _ocr_page(pb, rec, normalize_text(ocr_text[page_no]), pending, sections, running, result, stats)
                    rec.method, rec.ocr, rec.ocr_engine = 'ocr', True, ocr_engine or 'ocr'
                    stats['ocr_pages'] += 1
                else:
                    for level, title in pending:
                        sections.set(level, title)
                    rec.method, rec.ocr_pending = 'none', True
                    stats['ocr_pending_pages'] += 1
                rec.section_path, rec.chapter = rec.section_path or sections.path, rec.chapter or sections.chapter
                rec.text, rec.segments = pb.text, pb.segments
                rec.text_quality = text_quality(rec.text)
                result.pages.append(rec)
                continue

            try:
                page = doc[i]
                blocks = _blocks(page, flags)
            except Exception:  # noqa: BLE001
                rec.method = 'none'
                result.pages.append(rec)
                continue
            mlines = _margin_lines(blocks, page.rect.height)
            strip = {id(ln) for ln in mlines if masked(ln.text) in running or is_page_number_line(ln.text)}
            stats['margin_lines_removed'] += len(strip)
            tables = _tables(page) if page_no in table_pages else []
            images = _image_boxes(page) if page_no in figure_pages else []
            matched = set()
            for idx, (_lvl, title) in enumerate(pending):
                for blk in blocks:
                    if any(id(ln) not in strip and heading_matches(title, ln.text) for ln in blk):
                        matched.add(idx)
                        break
            top, followers = plan_toc(len(pending), matched)
            for idx in top:
                sections.set(*pending[idx])          # heading not printed as text: section starts at the top
            rec.section_path, rec.chapter = sections.path, sections.chapter
            _pdf_page(pb, blocks, strip, tables, images, pending, matched, followers, levels, body, sections,
                      result, stats, page_no)
            rec.text, rec.segments = pb.text, pb.segments
            rec.method = 'text' if rec.text else 'none'
            rec.text_quality = text_quality(rec.text)
            stats['text_pages' if rec.text else 'empty_pages'] += 1
            result.pages.append(rec)
        stats['labelled_pages'] = sum(1 for p in result.pages if p.page_label)
        stats['seconds'] = round(time.perf_counter() - started, 2)
        result.stats = dict(stats)
        return result
    finally:
        doc.close()


def _pdf_page(pb, blocks, strip, tables, images, pending, matched, followers, levels, body, sections, result,
              stats, page_no):
    emitted_tables = set()
    matched = set(matched)

    def flush_text(lines):
        if lines:
            pb.add('text', join_lines(lines), section_path=sections.path, chapter=sections.chapter, sep='\n\n')
        return []

    for blk in blocks:
        lines = [ln for ln in blk if id(ln) not in strip]
        if not lines:
            continue
        # Lines inside a detected table belong to the table segment (emitted once, in place).
        rest = []
        for ln in lines:
            hit = next((ti for ti, t in enumerate(tables) if _inside(ln, t['bbox'])), None)
            if hit is None:
                rest.append(ln)
            elif hit not in emitted_tables:
                emitted_tables.add(hit)
                _emit_table(pb, tables[hit], sections, stats)
        lines = rest
        if not lines:
            continue
        first = lines[0]
        if FIGURE_CAPTION_RE.match(first.text):
            caption = join_lines([ln.text for ln in lines])
            bbox = (min(ln.x0 for ln in lines), min(ln.y0 for ln in lines),
                    max(ln.x1 for ln in lines), max(ln.y1 for ln in lines))
            result.figures.append(FigureRecord(page_no=page_no, caption=caption[:2000], bbox=_figure_bbox(bbox, images)))
            pb.add('figure', caption, section_path=sections.path, chapter=sections.chapter, sep='\n\n',
                   figure_index=len(result.figures) - 1)
            stats['figure_captions'] += 1
            continue
        if TABLE_CAPTION_RE.match(first.text):
            near = next((ti for ti, t in enumerate(tables) if ti not in emitted_tables and not t['caption']
                         and 0 <= t['bbox'][1] - first.y1 <= 40), None)
            cap_lines = [first.text]
            for ln in lines[1:3]:
                if cap_lines[-1].rstrip().endswith('.'):
                    break
                cap_lines.append(ln.text)
            caption = join_lines(cap_lines)
            if near is not None:
                tables[near]['caption'] = caption
                emitted_tables.add(near)
                _emit_table(pb, tables[near], sections, stats)
            else:
                pb.add('caption', caption, section_path=sections.path, chapter=sections.chapter, sep='\n\n')
                stats['table_captions_without_table'] += 1
            lines = lines[len(cap_lines):]
            if not lines:
                continue
        buf: list[str] = []
        j = 0
        while j < len(lines):
            ln = lines[j]
            toc_hit = next((idx for idx, (_l, title) in enumerate(pending)
                            if idx in matched and heading_matches(title, ln.text)), None)
            level = None
            if toc_hit is not None:
                level = pending[toc_hit][0]
                title = pending[toc_hit][1]
                matched.discard(toc_hit)
            elif levels and word_count(ln.text) <= MAX_HEADING_WORDS and not ln.text.rstrip().endswith(('.', ',', ';')):
                level = levels.get(ln.size)
                if level is None and ln.bold and body and ln.size >= body and len(lines) <= 2 and len(ln.text) >= 3:
                    level = 3
                title = ln.text
            if level is not None and re.search('[A-Za-z]{2}', ln.text):
                buf = flush_text(buf)
                head = [ln.text]
                while j + 1 < len(lines) and lines[j + 1].size == ln.size and toc_hit is None and \
                        word_count(' '.join(head) + ' ' + lines[j + 1].text) <= MAX_HEADING_WORDS:
                    j += 1
                    head.append(lines[j].text)
                heading_text = join_lines(head)
                sections.set(level, title if toc_hit is not None else heading_text)
                pb.add('heading', heading_text, section_path=sections.path, chapter=sections.chapter, sep='\n\n')
                for f in followers.get(toc_hit, []) if toc_hit is not None else []:
                    sections.set(*pending[f])
                stats['headings'] += 1
            else:
                buf.append(ln.text)
            j += 1
        flush_text(buf)
    for ti, t in enumerate(tables):
        if ti not in emitted_tables:
            _emit_table(pb, t, sections, stats)
    # TOC entries matched to a line that never came up (e.g. inside a table) still apply.
    for idx in sorted(matched):
        sections.set(*pending[idx])
        for f in followers.get(idx, []):
            sections.set(*pending[f])


def _emit_table(pb, table, sections, stats):
    text = '\n'.join(([table['caption']] if table['caption'] else []) + table['rows'])
    pb.add('table', text, section_path=sections.path, chapter=sections.chapter, sep='\n\n',
           table_rows=list(table['rows']), table_caption=table['caption'])
    stats['tables'] += 1


def _ocr_page(pb, rec, text, pending, sections, running, result, stats):
    lines = [ln for ln in text.split('\n')]
    nonempty = [i for i, ln in enumerate(lines) if ln.strip()]
    edge = set(nonempty[:2] + nonempty[-2:]) if len(nonempty) > 4 else set(nonempty)
    drop = {i for i in edge if masked(lines[i]) in running or is_page_number_line(lines[i])}
    stats['margin_lines_removed'] += len(drop)
    matched = {}
    for idx, (_lvl, title) in enumerate(pending):
        for i, ln in enumerate(lines):
            if i not in drop and i not in matched and ln.strip() and heading_matches(title, ln):
                matched[i] = idx
                break
    top, followers = plan_toc(len(pending), set(matched.values()))
    for idx in top:
        sections.set(*pending[idx])
    rec.section_path, rec.chapter = sections.path, sections.chapter
    buf: list[str] = []

    def flush():
        if buf:
            pb.add('text', join_lines(buf), section_path=sections.path, chapter=sections.chapter, sep='\n\n')
            buf.clear()

    for i, ln in enumerate(lines):
        if i in drop:
            continue
        if not ln.strip():
            flush()
            continue
        if i in matched:
            flush()
            sections.set(*pending[matched[i]])
            pb.add('heading', ln, section_path=sections.path, chapter=sections.chapter, sep='\n\n')
            for f in followers.get(matched[i], []):
                sections.set(*pending[f])
            continue
        if FIGURE_CAPTION_RE.match(ln):
            flush()
            result.figures.append(FigureRecord(page_no=rec.page_no, caption=ln[:2000], bbox=None))
            pb.add('figure', ln, section_path=sections.path, chapter=sections.chapter, sep='\n\n',
                   figure_index=len(result.figures) - 1)
            stats['figure_captions'] += 1
            continue
        if TABLE_CAPTION_RE.match(ln):
            flush()
            pb.add('caption', ln, section_path=sections.path, chapter=sections.chapter, sep='\n\n')
            continue
        buf.append(ln)
    flush()
