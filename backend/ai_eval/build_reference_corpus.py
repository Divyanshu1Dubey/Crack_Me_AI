"""Build the page-aware reference corpus (see ai_engine/reference_corpus.py).

Stages (each resumable; run from backend/):
    python -m ai_eval.build_reference_corpus registry --inventory INV.json --out REG.json
    python -m ai_eval.build_reference_corpus extract  --registry REG.json --db DB [--ocr] [--only TEXT] [--max-pages N]
    python -m ai_eval.build_reference_corpus embed    --db DB [--model BAAI/bge-small-en-v1.5] [--batch 64]
    python -m ai_eval.build_reference_corpus report   --db DB

``registry`` classifies local documents from their file names only: title,
edition and year are filled in only when the name states them, everything
else stays empty. Personal / administrative documents and non-medical files
are excluded. Exact duplicates are collapsed by SHA-256, near duplicates
("Copy of ...", re-saves) by normalised title and page count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine.reference_corpus import connect  # noqa: E402

# ---------------------------------------------------------------- registry --

EXCLUDE = re.compile(
    r'affidavit|certificate|proforma|performa|daf[\s_-]*\d|travel+ing allowance|competitor|prerequis|armed force'
    r'|notice|time ?table|syllabus|\bform\b|payment receipt|instructions for obc|madeeasy|dbms|java|servlet|matrices'
    r'|calculas|calculus|oss-assignment|aaaps|da\.pyq|mahima|htdocs|appointment|^~\$'
    # Non-medical or not a reference, identified from the documents' own first pages: Theory of Computation
    # papers, an e-poster draft, an agricultural plant-pathology thesis, cloud-computing MCQs, a GATE key,
    # software-engineering answers, seating plans, invoices, assignments, ML papers, personal documents.
    r'|\btoc\b|e-poster|pathology t-1038|prepare all possible mcqs|^g200p84|se question bank|seating|invoice|php'
    r'|assignment|patent|agreement|dual-degree|super-resolution|cnn|_payment',
    re.I,
)
# Answer keys whose origin was checked against the document text (not just the file name).
OFFICIAL_KEYS = [
    # OCR of the single page: "Examination CMSE-2013 / Series A / Subject Paper-I / Maximum Marks 250 /
    # No. of items dropped 1 / Items to be taken for scoring 119" followed by the 120-item grid -- the UPSC
    # final-answer-key format (re-hosted by a prep website).
    (r'upsc-cms-2013-general-medicine-and-pediatrics-paper-1-answer-key',
     'UPSC CMSE-2013 Paper I final answer key (Series A)', 2013),
]
SUBJECTS = [
    (r'anaesth|anesth', 'Anaesthesia'), (r'anatom', 'Anatomy'), (r'biochem', 'Biochemistry'), (r'derma', 'Dermatology'),
    (r'\bent\b', 'ENT'), (r'fmt|forensic', 'Forensic Medicine'), (r'medicine|nephro|neuro|cardio|respir|rheumat', 'Medicine'),
    (r'micro', 'Microbiology'), (r'obg|obgy|obstet|gyn|gyane', 'Obstetrics & Gynaecology'), (r'ophthal', 'Ophthalmology'),
    (r'ortho', 'Orthopaedics'), (r'psm|preventive|community|health care|communicable|international health', 'PSM'),
    (r'patho', 'Pathology'), (r'pediat|paediat|newborn|growth|immuni|imnci|fluids|development', 'Pediatrics'),
    (r'pharm', 'Pharmacology'), (r'physiol', 'Physiology'), (r'psychiat', 'Psychiatry'), (r'radiol', 'Radiology'),
    (r'surgery|surgical', 'Surgery'),
]
TEXTBOOKS = [
    (r"harrison.*17ed_2010", "Harrison's Principles of Internal Medicine", '17th edition', 2010, 'Medicine'),
    (r'harrison 2025.*22nd edition', "Harrison's Principles of Internal Medicine", '22nd edition', 2025, 'Medicine'),
    (r'nelson textbook of pediatrics', 'Nelson Textbook of Pediatrics', None, None, 'Pediatrics'),
    (r'ghai essential pediatrics, 9e', 'Ghai Essential Pediatrics', '9th edition', None, 'Pediatrics'),
    (r'park textbook of preventive and social medicine', "Park's Textbook of Preventive and Social Medicine", None, None, 'PSM'),
    (r'park 27 edition', "Park's Textbook of Preventive and Social Medicine (excerpt)", '27th edition', None, 'PSM'),
    (r'dc_dutta_s_textbook_of_obstetrics', "DC Dutta's Textbook of Obstetrics (excerpt)", None, None, 'Obstetrics & Gynaecology'),
]
LICENCE_BOOK = 'copyrighted textbook - internal retrieval and verification only; never shown in full to students'
LICENCE_NOTES = 'course / coaching material - internal use; attribute as notes'


def _subject(name: str):
    for rx, subj in SUBJECTS:
        if re.search(rx, name, re.I):
            return subj
    return None


def _clean_title(name: str) -> str:
    stem = re.sub(r'\.(pdf|docx|pptx)$', '', name, flags=re.I)
    stem = re.sub(r'^(copy of|done_|new )\s*', '', stem, flags=re.I)
    stem = re.sub(r'_[0-9a-f]{8}-[0-9a-f-]{20,}$', '', stem)            # uploaded-file uuid suffix
    stem = re.sub(r'\s*\(\d+\)', '', stem)                              # "(1)", "(2)" copies
    stem = re.sub(r'[_-][0-9]{6,}$|[_-][0-9a-f]{16,}$', '', stem)       # site suffixes / hashes
    return re.sub(r'\s+', ' ', stem.replace('_', ' ')).strip()


def classify(path: str) -> dict | None:
    name = os.path.basename(path)
    low = name.lower()
    base = re.sub(r'^copy of\s*', '', name, flags=re.I)
    if EXCLUDE.search(name):
        return None
    for rx, title, year in OFFICIAL_KEYS:
        if re.search(rx, low):
            return dict(title=title, edition=None, year=year, tier=1, kind='answer_key', subject=None,
                        licence='official answer key (public document)')
    for rx, title, edition, year, subj in TEXTBOOKS:
        if re.search(rx, low):
            return dict(title=title, edition=edition, year=year, tier=3, kind='textbook', subject=subj, licence=LICENCE_BOOK)
    if re.match(r'^final \(1\)\.pdf$', name, re.I):
        # Opens with "Chapter 1: Man, and Medicine ... Biomedical concept: Means '_____ of disease'": a PSM
        # fill-in-the-blank workbook. The key facts are blanked out, so it is never evidence.
        return dict(title='final (PSM fill-in-the-blank workbook)', edition=None, year=None, tier=5, kind='workbook',
                    subject='PSM', licence=LICENCE_NOTES)
    m = re.match(r'^(\w+) pyqs\.pdf$', name, re.I)
    if m:
        return dict(title=f'{m.group(1)} PYQ compilation (questions with explanations)', edition=None, year=None, tier=4,
                    kind='pyq_compilation', subject=_subject(name), licence=LICENCE_NOTES)
    m = (re.match(r'^(20\d\d) paper ([12])', base, re.I) or re.match(r'^cms(20\d\d)-paper([12])', base, re.I)
         or re.match(r'^upsc_cms_(20\d\d)_paper([12])', base, re.I))
    if m:
        return dict(title=f'UPSC CMS {m.group(1)} Paper {m.group(2)}', edition=None, year=int(m.group(1)), tier=5,
                    kind='question_paper', subject=None, licence='question paper')
    m = re.match(r'^upsc_cms_(20\d\d)_gs_paper_(ii|i)_', base, re.I)
    if m:
        return dict(title=f'UPSC CMS {m.group(1)} Paper {len(m.group(2))}', edition=None, year=int(m.group(1)), tier=5,
                    kind='question_paper', subject=None, licence='question paper')
    if 'neet' in low and 'quest' in low and not re.search(r'20\d\d', low):
        return dict(title=_clean_title(name).replace('-', ' '), edition=None, year=None, tier=4, kind='pyq_compilation',
                    subject=_subject(name), licence=LICENCE_NOTES)
    m = re.search(r'neet[-_ ]?pg[-_ ]?(?:question[-_ ]paper[-_ ]?)?(20\d\d)|neet[-_ ]pg[-_ ](?:question[-_ ]paper[-_ ])?(20\d\d)', low)
    if m and ('neet' in low):
        yr = int(m.group(1) or m.group(2))
        sol = 'with solutions' if 'solution' in low or 'answer' in low else ''
        return dict(title=f'NEET PG {yr} question paper {sol}'.strip() + (' (third-party key)' if sol else ''), edition=None,
                    year=yr, tier=5, kind='question_paper', subject=None, licence='question paper')
    if re.search(r'test|mini|question[ _]?box|boxes|in_?boxes|selected_boxes|mcqs|_questions|_\d+q\b', low):
        return dict(title=_clean_title(name), edition=None, year=None, tier=5, kind='question_set', subject=_subject(name),
                    licence=LICENCE_NOTES)
    if re.search(r'pyq', low):
        return dict(title=_clean_title(name), edition=None, year=None, tier=4, kind='pyq_compilation', subject=_subject(name),
                    licence=LICENCE_NOTES)
    if re.search(r'notes?|unannotated|annotated|merged|anno_|growth|immuni|nutrition|newborn|development|fluids', low):
        return dict(title=_clean_title(name), edition=None, year=None, tier=4, kind='notes', subject=_subject(name),
                    licence=LICENCE_NOTES)
    if low.endswith('.docx') and (_subject(name) or re.search(r'\bunit\b', low)):
        # UPSC CMS unit notes ("OBGY-UNIT-10.docx", "Psychiatry.docx", "Health care, Communication, ...docx").
        return dict(title=_clean_title(name), edition=None, year=None, tier=4, kind='notes', subject=_subject(name),
                    licence=LICENCE_NOTES)
    return None


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def build_registry(inventory: str, out: str, extra_inventory: str | None = None) -> None:
    """``extra_inventory`` (e.g. a whole-disk PDF listing) contributes only UPSC CMS papers and verified keys."""
    items = json.load(open(inventory, encoding='utf-8'))
    known = {os.path.normcase(i['path']) for i in items}
    if extra_inventory:
        for it in json.load(open(extra_inventory, encoding='utf-8')):
            meta = classify(it['path'])
            if (os.path.normcase(it['path']) not in known and meta and meta['kind'] in ('question_paper', 'answer_key')
                    and meta['title'].startswith('UPSC')):
                items.append(it)
    chosen, seen_hash, seen_title, skipped = [], {}, {}, []
    for it in sorted(items, key=lambda i: (-(i.get('pages') or 0), -i['mb'])):
        meta = classify(it['path'])
        if meta is None:
            skipped.append(it['path'])
            continue
        if not os.path.exists(it['path']):
            continue
        digest = sha256_file(it['path'])
        if digest in seen_hash:
            continue
        key = (meta['title'].lower(), it.get('pages'), meta['kind'])
        if key in seen_title and it.get('pages'):
            continue
        seen_hash[digest] = it['path']
        seen_title[key] = it['path']
        chosen.append(dict(meta, path=it['path'], file_name=os.path.basename(it['path']), sha256=digest,
                           pages=it.get('pages'), mb=it['mb'], scanned=str(it.get('text_pages_sampled', '')).startswith('0/')))
    json.dump(chosen, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by_kind = {}
    for c in chosen:
        by_kind.setdefault((c['tier'], c['kind']), []).append(c)
    print(f'registry: {len(chosen)} sources ({len(skipped)} files excluded or unclassified)')
    for (tier, kind), cs in sorted(by_kind.items()):
        print(f'  tier {tier} {kind:16s} {len(cs):4d} docs {sum(c.get("pages") or 0 for c in cs):7d} pdf pages '
              f'{sum(1 for c in cs if c["scanned"]):3d} scanned')


# ----------------------------------------------------------------- extract --

# Some coaching-compilation PDFs (the "<Subject> pyqs.pdf" files) embed a font whose glyphs sit in
# the Private Use Area at U+E000 + (ASCII code - 0x20): U+E049 U+E043 U+E054 = "ict", U+E032 = "R",
# U+E024 U+E02E U+E021 = "DNA", U+E010.. = digits. A plain text extraction then yields only PUA
# characters; mapping them back recovers the text without OCR (checked on Biochem pyqs.pdf p.12:
# "Restriction endonuclease enzymes act at specific palindromic sequences ...").
_PUA_ASCII = {cp: cp - 0xE000 + 0x20 for cp in range(0xE000, 0xE05F)}


def repair_pua(text: str) -> str:
    if not text:
        return text
    pua = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xE05E)
    if pua < 5 or pua < 0.2 * len(text.strip()):
        return text
    return text.translate(_PUA_ASCII)


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKC', repair_pua(text or ''))
    text = re.sub(r'[ \t ]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


_OCR = None


def _ocr_page(page) -> str:
    global _OCR
    import numpy as np
    if _OCR is None:
        from rapidocr import RapidOCR
        _OCR = RapidOCR()
    pix = page.get_pixmap(dpi=150)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    res = _OCR(img)
    txts = list(getattr(res, 'txts', None) or [])
    boxes = getattr(res, 'boxes', None)
    if boxes is not None and len(boxes) == len(txts):
        # Reading order: rows by top y (bucketed), then x.
        order = sorted(range(len(txts)), key=lambda i: (round(float(boxes[i][0][1]) / 12), float(boxes[i][0][0])))
        lines, last_row, row = [], None, []
        for i in order:
            r = round(float(boxes[i][0][1]) / 12)
            if last_row is not None and r != last_row:
                lines.append(' '.join(row))
                row = []
            row.append(txts[i])
            last_row = r
        if row:
            lines.append(' '.join(row))
        return '\n'.join(lines)
    return '\n'.join(txts)


def extract_pdf(path: str, *, ocr: bool, max_pages: int | None):
    import fitz
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count if not max_pages else min(doc.page_count, max_pages)):
            page = doc[i]
            text = _norm(page.get_text('text'))
            # The image count only decides whether a near-empty page needs OCR. Some PDFs list every
            # image of the book in a shared resource dictionary (Harrison 17e: ~12,700 per page,
            # 0.5 s per get_images call), so pages with a real text layer skip it.
            images = len(page.get_images()) if len(text) < OCR_MIN_CHARS else 0
            method = 'text'
            if ocr and len(text) < OCR_MIN_CHARS and images:
                text = _norm(_ocr_page(page))
                method = 'ocr'
            yield i + 1, text, method, images
    finally:
        doc.close()


def _extract_docx_lenient(path: str, section_chars: int = 3000):
    """Fallback for DOCX files python-docx rejects (merge tools leave undeclared namespaces or a
    missing footer part): read word/document.xml and take the <w:t> text of each <w:p> paragraph."""
    import html
    import zipfile
    with zipfile.ZipFile(path) as zf:
        xml = zf.read('word/document.xml').decode('utf-8', errors='replace')
    buf, n = [], 0
    for para in re.split(r'</w:p>', xml):
        text = ''.join(html.unescape(t) for t in re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', para)).strip()
        if not text:
            continue
        buf.append(text)
        if sum(len(b) for b in buf) >= section_chars:
            n += 1
            yield n, _norm('\n'.join(buf)), 'docx', 0
            buf = []
    if buf:
        n += 1
        yield n, _norm('\n'.join(buf)), 'docx', 0


def extract_docx(path: str, section_chars: int = 3000):
    """DOCX has no pages: emit ~3,000-char sections in document order (paragraphs and tables)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = docx.Document(path)
    except Exception:
        yield from _extract_docx_lenient(path, section_chars)
        return
    buf, heading, n = [], None, 0

    def blocks():
        body = d.element.body
        for child in body.iterchildren():
            tag = child.tag.rsplit('}', 1)[-1]
            if tag == 'p':
                yield Paragraph(child, d)
            elif tag == 'tbl':
                yield Table(child, d)

    for block in blocks():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style = (block.style.name or '').lower() if block.style is not None else ''
            if style.startswith('heading') or (len(text) < 80 and text.isupper()):
                heading = text
                text = f'## {text}'
        else:
            rows = []
            for row in block.rows:
                cells = []
                for cell in row.cells:
                    t = ' '.join(cell.text.split())
                    if not cells or cells[-1] != t:
                        cells.append(t)
                rows.append(' | '.join(cells))
            text = '\n'.join(r for r in rows if r.strip())
            if not text:
                continue
        buf.append(text)
        if sum(len(b) for b in buf) >= section_chars:
            n += 1
            yield n, _norm('\n'.join(buf)), 'docx', 0
            buf = []
    if buf:
        n += 1
        yield n, _norm('\n'.join(buf)), 'docx', 0


_HEADING_RE = re.compile(r'^(?:##\s*)?([A-Z][A-Z0-9 ,&/()\-\']{3,70}|\d+(?:\.\d+)*\s+[A-Z][^\n]{3,70})$')


def chunk_pages(pages, target: int = 1000, overlap: int = 150, minimum: int = 250):
    """Paragraph-respecting chunks that may span consecutive pages; each carries the nearest heading."""
    chunks, cur, cur_len, start_page, heading = [], [], 0, None, None
    last_heading_for_chunk = None

    def flush(end_page):
        nonlocal cur, cur_len, start_page
        text = '\n'.join(cur).strip()
        if len(text) >= minimum or (text and not chunks):
            chunks.append((start_page, end_page, last_heading_for_chunk, text))
        tail = text[-overlap:] if overlap and len(text) > overlap else ''
        cur = [tail] if tail else []
        cur_len = len(tail)
        start_page = end_page if tail else None

    for page_no, text, _method, _images in pages:
        for para in re.split(r'\n\s*\n|\n(?=[A-Z0-9•\-–])', text):
            para = para.strip()
            if not para:
                continue
            first_line = para.split('\n', 1)[0].strip()
            if _HEADING_RE.match(first_line) and len(first_line) < 80:
                heading = first_line.lstrip('# ').strip()
            if start_page is None:
                start_page = page_no
            if not cur:
                last_heading_for_chunk = heading
            cur.append(para)
            cur_len += len(para)
            if cur_len >= target:
                flush(page_no)
                last_heading_for_chunk = heading
        last_page = page_no
    if cur and ''.join(cur).strip():
        flush(locals().get('last_page', start_page or 1))
    return chunks


def _content_hash(pages) -> str:
    joined = ' '.join(re.sub(r'[^a-z0-9]+', ' ', t.lower()) for _n, t, _m, _i in pages)
    return hashlib.sha256(' '.join(joined.split()).encode()).hexdigest()


def _chunk_hash(text: str) -> str:
    return hashlib.sha1(' '.join(re.sub(r'[^a-z0-9]+', ' ', text.lower()).split()).encode()).hexdigest()


# A PDF page with less text than this and at least one image is treated as scanned / image-only.
OCR_MIN_CHARS = 80
# The text pass leaves a whole PDF for the OCR pass when more than this share of its pages is
# image-only (a scanned book). Otherwise the text pages are stored now and the few image-only pages
# are recorded in meta('ocr_pending:<source id>') for ocr_pending_pages(), which re-chunks the source.
OCR_DEFER_FRACTION = 0.3


def _chunk_rows(source_id, pages, known_chunks):
    rows, skipped = [], 0
    for a, b, h, t in chunk_pages(pages):
        digest = _chunk_hash(t)
        if digest in known_chunks:
            skipped += 1
            continue
        known_chunks.add(digest)
        rows.append((source_id, a, b, h, 'text', t, len(t), digest))
    return rows, skipped


def extract(registry: str, db_path: str, *, ocr: bool, only: str | None, max_pages: int | None, skip_ocr_sources: bool) -> None:
    conn = connect(db_path)
    reg = json.load(open(registry, encoding='utf-8'))
    known_chunks = {r[0] for r in conn.execute('SELECT text_hash FROM chunks WHERE text_hash IS NOT NULL')}
    if ocr:
        # Cheapest OCR first (a compilation with 4 image-only pages before a 1,000-page scanned book);
        # evidence tiers (1-4) before question papers and workbooks.
        pending_ocr = {r['sha256']: r['n'] for r in conn.execute(
            'SELECT s.sha256, count(p.page_no) n FROM sources s LEFT JOIN pages p ON p.source_id = s.id '
            'AND p.method = ? AND p.chars < ? AND p.image_count > 0 GROUP BY s.id', ('text', OCR_MIN_CHARS))}

        def cost(src):
            n = pending_ocr.get(src['sha256'])
            return (0 if src['tier'] <= 4 else 1, n if n is not None else (src.get('pages') or 0))
        reg = sorted(reg, key=cost)
    for src in reg:
        if only and only.lower() not in (src['file_name'] + ' ' + src['title']).lower():
            continue
        if skip_ocr_sources and src.get('scanned'):
            continue
        row = conn.execute('SELECT id, status FROM sources WHERE sha256 = ?', (src['sha256'],)).fetchone()
        if row and row['status'] in ('done', 'duplicate'):
            continue
        if row and row['status'] == 'needs_ocr' and not ocr:
            continue
        if row is None:
            cur = conn.execute(
                'INSERT INTO sources (sha256, title, edition, year, tier, kind, subject, licence, file_name, path, pages, status, added_at) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (src['sha256'], src['title'], src.get('edition'), src.get('year'), src['tier'], src['kind'], src.get('subject'),
                 src.get('licence'), src['file_name'], src['path'], src.get('pages'), 'extracting',
                 datetime.now(timezone.utc).isoformat()))
            source_id = cur.lastrowid
        else:
            source_id = row['id']
            conn.execute('DELETE FROM chunks WHERE source_id = ?', (source_id,))
            conn.execute('DELETE FROM pages WHERE source_id = ?', (source_id,))
        conn.commit()
        t0 = time.time()
        try:
            if src['file_name'].lower().endswith('.docx'):
                pages = list(extract_docx(src['path']))
            elif src['file_name'].lower().endswith('.pdf'):
                pages = []
                for p in extract_pdf(src['path'], ocr=ocr, max_pages=max_pages):
                    pages.append(p)
                    if p[2] == 'ocr' and len(pages) % 25 == 0:
                        print(f'    ocr {src["file_name"][:50]} page {p[0]}', flush=True)
            else:
                pages = []
        except Exception as exc:  # a corrupt file must not stop the build
            conn.execute('DELETE FROM pages WHERE source_id = ?', (source_id,))
            conn.execute('UPDATE sources SET status = ? WHERE id = ?', ('failed', source_id))
            conn.commit()
            print(f'  FAILED {src["file_name"][:60]}: {type(exc).__name__}: {str(exc)[:120]}', flush=True)
            continue
        conn.executemany('INSERT OR REPLACE INTO pages (source_id, page_no, text, method, chars, image_count) VALUES (?,?,?,?,?,?)',
                         [(source_id, n, t, m, len(t), imgs) for n, t, m, imgs in pages])
        image_only_pages = [n for n, t, m, imgs in pages if m == 'text' and len(t) < OCR_MIN_CHARS and imgs]
        if not ocr and pages and len(image_only_pages) / len(pages) > OCR_DEFER_FRACTION:
            conn.execute('UPDATE sources SET status = ?, pages = ? WHERE id = ?', ('needs_ocr', len(pages), source_id))
            conn.commit()
            print(f'  ocr-later {src["kind"]:15s} {src["file_name"][:60]:60s} {len(image_only_pages)} image-only of {len(pages)} pages', flush=True)
            continue
        if not ocr and image_only_pages:
            conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)',
                         (f'ocr_pending:{source_id}', json.dumps(image_only_pages)))
        content = _content_hash(pages)
        twin = conn.execute('SELECT id, title FROM sources WHERE content_sha256 = ? AND id != ? AND status = ?',
                            (content, source_id, 'done')).fetchone()
        if twin is not None:
            conn.execute('UPDATE sources SET status = ?, pages = ?, content_sha256 = ?, duplicate_of = ? WHERE id = ?',
                         ('duplicate', len(pages), content, twin['id'], source_id))
            conn.execute('DELETE FROM pages WHERE source_id = ?', (source_id,))
            conn.commit()
            print(f'  duplicate {src["file_name"][:60]} = source {twin["id"]}', flush=True)
            continue
        chunks, skipped = _chunk_rows(source_id, pages, known_chunks)
        conn.executemany('INSERT INTO chunks (source_id, page_start, page_end, heading, kind, text, chars, text_hash) '
                         'VALUES (?,?,?,?,?,?,?,?)', chunks)
        conn.execute('UPDATE sources SET status = ?, pages = ?, content_sha256 = ? WHERE id = ?',
                     ('done', len(pages), content, source_id))
        conn.commit()
        ocr_pages = sum(1 for p in pages if p[2] == 'ocr')
        print(f'  done {src["kind"]:15s} {src["file_name"][:60]:60s} pages {len(pages):5d} (ocr {ocr_pages}) '
              f'chunks {len(chunks):5d} (+{skipped} repeated) {time.time() - t0:6.0f}s', flush=True)


# ------------------------------------------------------------------- embed --

def embed(db_path: str, model_name: str, batch: int) -> None:
    import numpy as np
    from fastembed import TextEmbedding
    conn = connect(db_path)
    model = TextEmbedding(model_name)
    todo = conn.execute('SELECT c.id, c.heading, c.text FROM chunks c LEFT JOIN embeddings e ON e.chunk_id = c.id AND e.model = ? '
                        'WHERE e.chunk_id IS NULL ORDER BY c.id', (model_name,)).fetchall()
    print(f'embedding {len(todo)} chunks with {model_name}', flush=True)
    t0 = time.time()
    for i in range(0, len(todo), batch * 8):
        part = todo[i:i + batch * 8]
        texts = [((r['heading'] + ': ') if r['heading'] else '') + r['text'][:2000] for r in part]
        vecs = list(model.embed(texts, batch_size=batch))
        conn.executemany('INSERT OR REPLACE INTO embeddings (chunk_id, model, dim, vec) VALUES (?,?,?,?)',
                         [(r['id'], model_name, len(v), np.asarray(v, dtype=np.float16).tobytes()) for r, v in zip(part, vecs)])
        conn.commit()
        done = i + len(part)
        print(f'  {done}/{len(todo)} chunks, {done / max(1e-6, time.time() - t0):.0f}/s', flush=True)
    conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('embedding_model', model_name))
    conn.commit()


def reset_pua_sources(db_path: str) -> None:
    """Re-queue for the text pass (status 'pending', pages / chunks / vectors removed):
    sources whose stored pages still hold Private-Use-Area glyph text (extracted before
    ``repair_pua``), and every whole-document OCR deferral made under the old rule (the text pass
    re-decides them with OCR_DEFER_FRACTION)."""
    conn = connect(db_path)
    pua = set()
    for sid, text in conn.execute('SELECT source_id, text FROM pages'):
        if sid not in pua and sum(1 for ch in text[:3000] if 0xE000 <= ord(ch) <= 0xE05E) >= 20:
            pua.add(sid)
    deferred = {r[0] for r in conn.execute("SELECT id FROM sources WHERE status IN ('needs_ocr', 'failed', 'extracting')")}
    for sid in pua | deferred:
        conn.execute('DELETE FROM embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE source_id = ?)', (sid,))
        conn.execute('DELETE FROM chunks WHERE source_id = ?', (sid,))
        conn.execute('DELETE FROM pages WHERE source_id = ?', (sid,))
        conn.execute('DELETE FROM meta WHERE key = ?', (f'ocr_pending:{sid}',))
        conn.execute('UPDATE sources SET status = ?, content_sha256 = NULL WHERE id = ?', ('pending', sid))
    conn.commit()
    print(f'reset {len(pua)} sources with PUA glyph text and {len(deferred - pua)} deferred / failed sources', flush=True)


def ocr_pending_pages(db_path: str) -> None:
    """OCR the recorded image-only pages of sources stored by the text pass (fewest pages first),
    then rebuild that source's chunks (its old chunks and vectors are removed; 'embed' re-embeds)."""
    import fitz
    conn = connect(db_path)
    todo = []
    for key, value in conn.execute("SELECT key, value FROM meta WHERE key LIKE 'ocr_pending:%'").fetchall():
        todo.append((len(json.loads(value)), int(key.split(':', 1)[1]), json.loads(value)))
    todo.sort()
    known_chunks = {r[0] for r in conn.execute('SELECT text_hash FROM chunks WHERE text_hash IS NOT NULL')}
    for n, sid, page_nos in todo:
        src = conn.execute('SELECT path, file_name, tier FROM sources WHERE id = ?', (sid,)).fetchone()
        t0 = time.time()
        try:
            doc = fitz.open(src['path'])
            for page_no in page_nos:
                text = _norm(_ocr_page(doc[page_no - 1]))
                conn.execute('UPDATE pages SET text = ?, method = ?, chars = ? WHERE source_id = ? AND page_no = ?',
                             (text, 'ocr', len(text), sid, page_no))
            doc.close()
        except Exception as exc:
            print(f'  OCR FAILED {src["file_name"][:60]}: {type(exc).__name__}: {str(exc)[:120]}', flush=True)
            continue
        old = [r[0] for r in conn.execute('SELECT text_hash FROM chunks WHERE source_id = ?', (sid,))]
        known_chunks.difference_update(h for h in old if h)
        conn.execute('DELETE FROM embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE source_id = ?)', (sid,))
        conn.execute('DELETE FROM chunks WHERE source_id = ?', (sid,))
        pages = [(r['page_no'], r['text'], r['method'], r['image_count']) for r in conn.execute(
            'SELECT page_no, text, method, image_count FROM pages WHERE source_id = ? ORDER BY page_no', (sid,))]
        rows, _skipped = _chunk_rows(sid, pages, known_chunks)
        conn.executemany('INSERT INTO chunks (source_id, page_start, page_end, heading, kind, text, chars, text_hash) '
                         'VALUES (?,?,?,?,?,?,?,?)', rows)
        conn.execute('DELETE FROM meta WHERE key = ?', (f'ocr_pending:{sid}',))
        conn.commit()
        print(f'  ocr-pages {src["file_name"][:60]:60s} {n:4d} pages OCRed, {len(rows)} chunks {time.time() - t0:6.0f}s', flush=True)


def build_fts(db_path: str) -> None:
    """(Re)build the BM25 index: a contentless FTS5 table keyed by chunk id over the same tokens as
    ``ai_engine.lexical_index.tokenize`` (Greek letters folded, conservative plural stemming, stopwords)."""
    from ai_engine.lexical_index import tokenize
    conn = connect(db_path)
    conn.execute('DROP TABLE IF EXISTS chunks_fts')
    conn.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(body, content='', tokenize='unicode61')")
    rows = conn.execute('SELECT id, heading, text FROM chunks ORDER BY id').fetchall()
    conn.executemany('INSERT INTO chunks_fts (rowid, body) VALUES (?, ?)',
                     [(r['id'], ' '.join(tokenize(((r['heading'] or '') + '\n') + r['text']))) for r in rows])
    conn.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', ('fts_chunks', str(len(rows))))
    conn.commit()
    print(f'fts: indexed {len(rows)} chunks', flush=True)


def report(db_path: str) -> None:
    conn = connect(db_path, readonly=True)
    rows = conn.execute(
        'SELECT s.tier, s.kind, count(DISTINCT s.id) docs, sum(s.pages) pages, '
        '(SELECT count(*) FROM chunks c JOIN sources s2 ON s2.id = c.source_id WHERE s2.tier = s.tier AND s2.kind = s.kind) chunks '
        'FROM sources s WHERE s.status = "done" GROUP BY s.tier, s.kind ORDER BY s.tier, s.kind').fetchall()
    for r in rows:
        print(f"tier {r['tier']} {r['kind']:16s} docs {r['docs']:4d} pages {r['pages'] or 0:7d} chunks {r['chunks']:7d}")
    methods = conn.execute('SELECT method, count(*) n, sum(chars) c FROM pages GROUP BY method').fetchall()
    print('pages by method:', {m['method']: (m['n'], m['c']) for m in methods})
    emb = conn.execute('SELECT model, count(*) n FROM embeddings GROUP BY model').fetchall()
    print('embeddings:', {e['model']: e['n'] for e in emb})


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('registry'); r.add_argument('--inventory', required=True); r.add_argument('--out', required=True)
    r.add_argument('--extra-inventory', help='whole-disk listing; only UPSC CMS papers / verified keys are taken from it')
    e = sub.add_parser('extract'); e.add_argument('--registry', required=True); e.add_argument('--db', required=True)
    e.add_argument('--ocr', action='store_true'); e.add_argument('--only'); e.add_argument('--max-pages', type=int)
    e.add_argument('--skip-ocr-sources', action='store_true')
    m = sub.add_parser('embed'); m.add_argument('--db', required=True)
    m.add_argument('--model', default='BAAI/bge-small-en-v1.5'); m.add_argument('--batch', type=int, default=64)
    p = sub.add_parser('report'); p.add_argument('--db', required=True)
    f = sub.add_parser('fts'); f.add_argument('--db', required=True)
    a = ap.parse_args(argv)
    if a.cmd == 'registry':
        build_registry(a.inventory, a.out, a.extra_inventory)
    elif a.cmd == 'extract':
        extract(a.registry, a.db, ocr=a.ocr, only=a.only, max_pages=a.max_pages, skip_ocr_sources=a.skip_ocr_sources)
    elif a.cmd == 'embed':
        embed(a.db, a.model, a.batch)
    elif a.cmd == 'fts':
        build_fts(a.db)
    else:
        report(a.db)


if __name__ == '__main__':
    main()
