"""Recover the answer key each source document prints for the questions imported from it (2026-11).

Deterministic, no AI, read-only against the database. Needs the source documents on disk, so it runs
where they are (the local corpus); its output is loaded anywhere with ``manage.py import_source_keys``.

    DJANGO_ENV_FILE=.env.localdev python -m ai_eval.recover_source_keys \\
        --registry REG.json [--inventory INV.json] --out source_keys.jsonl [--exam neet_pg] [--limit N]

``REG.json`` is the reference-corpus registry (``ai_eval.build_reference_corpus registry``: file name,
path, sha256, ...); ``INV.json`` an optional list of ``{path}`` for documents outside the registry
(question papers are tier 5 and not in it).

Formats handled
* "<Subject> pyqs.pdf" compilations: chapters titled "<Subject> <AIIMS|NEET|INI-CET> <year> [(session)]"
  at the top of a page; questions "Question N:"; per chapter an "Answer Key / Question No. / Correct
  Option" table.
* Paper "with solutions" PDFs: questions "N. <stem>" followed by "Correct Answer - A", "Answer < C: ...",
  "Ans. is b" or "Answer: C".
Text is extracted with the Private-Use-Area glyph repair of the corpus builder.

Matching: each numbered question of a source is indexed by its canonical stem prefix. A bank question is
matched through its ``QuestionSource`` link (page + number) or, without one, by its stem prefix within the
file named in ``Question.source``. ``located`` means the stem was found in the source text (not only a
page / number link). The printed letter is mapped onto the bank's option order through the option text
(``option_order`` 'same' / 'reordered'); when that text cannot be matched the order is 'assumed_same'.

Each output line: ``{question_id, stem_hash, exam, year, stored_key, source_file, source_sha256, located,
occurrences, status, printed_letter, letter, option_order, method, question_page, answer_page,
question_number, chapter, source_exam, source_year, recovery_version, recovered_at}`` (file names only,
never local paths). ``status``: match | mismatch | no_source_key | source_ambiguous.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

if __name__ == '__main__':  # standalone: python -m ai_eval.recover_source_keys
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
    import django
    django.setup()

RECOVERY_VERSION = 'v2-2026-11-03'

SUBJECT_WORDS = (r'Anatomy|Physiology|Biochemistry|Pathology|Pharmacology|Microbiology|Forensic Medicine|FMT|'
                 r'Community Medicine|Preventive|PSM|Medicine|Surgery|Obstetrics|Gynaecology|Gynecology|OBG|OBGY|'
                 r'Pediatrics|Paediatrics|Ophthalmology|ENT|Otorhinolaryngology|Orthopaedics|Orthopedics|'
                 r'Dermatology|Psychiatry|Radiology|Radiodiagnosis|Anaesthesia|Anesthesia|Anaesthesiology')
CHAPTER = re.compile(r'^\s*((?:%s)[^\n]{0,40}?\b(AIIMS|NEET|INI[- ]?CET)\b[^\n]{0,12}?\b(20\d\d)\b[^\n]{0,30})\s*$'
                     % SUBJECT_WORDS, re.I | re.M)
KEY_HDR = re.compile(r'Answer\s*Key\s*\n\s*Question\s*No\.?\s*\n\s*Correct\s*Option', re.I)
STOP = re.compile(r'Detailed\s+Explanations|Solution\s+to\s+Question', re.I)
PAIR = re.compile(r'(?m)^\s*(\d{1,3})\s*\n\s*([a-dA-D])\s*$')
Q_COMPILATION = re.compile(r'(?m)^\s*Question\s+(\d{1,3})\s*:\s*\n?(.{15,200})')
Q_PAPER = re.compile(r'(?m)^\s*(?:Q\.?\s*)?(\d{1,3})\s*[.):]\s+(\S.{15,200})')
Q_PREFIXED = re.compile(r'(?m)^\s*Q\.?\s*(\d{1,3})\s*[.):]\s+(\S.{15,200})')
INLINE_ANS = re.compile(r'Correct\s+Answer\s*[-:–]\s*\(?([A-Da-d])\b|Answer\s*<\s*([A-Da-d])\b'
                        r'|Ans(?:wer)?\.?\s*(?:is|:|-|–)\s*\(?([a-dA-D])\)?(?=[\s.):,])', re.I)


def canon(text) -> str:
    text = unicodedata.normalize('NFKC', text or '').casefold()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def parse_chapter(title: str) -> dict:
    m = re.search(r'\b(AIIMS|NEET|INI[- ]?CET)\b', title, re.I)
    y = re.search(r'\b(20\d\d)\b', title)
    s = re.search(r'\b(May|Nov(?:ember)?|Jan(?:uary)?|Jul(?:y)?)\b', title, re.I)
    exam = {'aiims': 'aiims_pg', 'neet': 'neet_pg'}.get(m.group(1).lower(), 'ini_cet') if m else ''
    return {'exam': exam, 'year': int(y.group(1)) if y else None, 'session': s.group(1)[:3].lower() if s else ''}


class Source:
    """One source document: its pages, chapters, answer-key tables and question index."""

    def __init__(self, path: str):
        from ai_eval.build_reference_corpus import _norm
        if path.lower().endswith('.docx'):
            from ai_eval.build_reference_corpus import extract_docx
            # One "page" holding the whole document, so a question never splits across sections.
            self.pages = ['\n'.join(t for _n, t, _m, _i in extract_docx(path))]
        else:
            import fitz
            doc = fitz.open(path)
            self.pages = [_norm(doc[i].get_text('text')) for i in range(doc.page_count)]
            doc.close()
        self.compilation = any(Q_COMPILATION.search(t) for t in self.pages[:40])
        # Documents that number questions "Q1." also number statements "1." inside questions.
        self.qrx = Q_PREFIXED if sum(len(Q_PREFIXED.findall(t)) for t in self.pages[:60]) >= 10 else Q_PAPER
        self.chapter, current = [], ''
        for text in self.pages:
            m = CHAPTER.search(text[:300])
            if m:
                current = ' '.join(m.group(1).split())
            self.chapter.append(current)
        self.tables = []
        for i, text in enumerate(self.pages):
            for m in KEY_HDR.finditer(text):
                region = text[m.end():]
                stop = STOP.search(region)
                if stop:
                    region = region[:stop.start()]
                elif i + 1 < len(self.pages):
                    nxt = self.pages[i + 1]
                    stop2 = STOP.search(nxt)
                    region += '\n' + (nxt[:stop2.start()] if stop2 else nxt)
                pairs = {int(n): letter.upper() for n, letter in PAIR.findall(region)}
                if pairs:
                    self.tables.append((i, pairs))
        self.index = defaultdict(list)   # canonical stem prefix -> [(page, qno, char offset)]
        rx = Q_COMPILATION if self.compilation else self.qrx
        for i, text in enumerate(self.pages):
            for m in rx.finditer(text):
                key = canon(m.group(2))[:45]
                if len(key) >= 20:
                    self.index[key].append((i, int(m.group(1)), m.start()))

    def key_for(self, page: int, qno: int, offset: int) -> tuple:
        """(letter, method, 1-based answer page) for question ``qno`` starting on ``page`` at ``offset``."""
        if self.compilation:
            chapter = self.chapter[page]
            for ti, pairs in self.tables:
                if ti >= page and qno in pairs:
                    if self.chapter[ti] and chapter and self.chapter[ti] != chapter:
                        break   # the next table belongs to another chapter: do not cross it
                    return pairs[qno], 'answer_key_table', ti + 1
            return '', '', None
        text = self.question_text(page, offset)
        m = INLINE_ANS.search(text)
        if m:
            return next(g for g in m.groups() if g).upper(), 'inline_answer', page + 1
        return '', '', None

    def question_text(self, page: int, offset: int) -> str:
        """The text of the question that starts at ``offset`` on ``page``, up to the next question."""
        text = self.pages[page][offset:] + '\n' + (self.pages[page + 1] if page + 1 < len(self.pages) else '')
        rx = Q_COMPILATION if self.compilation else self.qrx
        nxt = rx.search(text, 5)
        return text[: nxt.start() if nxt and nxt.start() > 40 else 2500]


def map_letter(src: Source, page: int, offset: int, letter: str, question) -> tuple:
    """(bank letter, option_order) for the printed ``letter``, through the printed option's text."""
    from questions.content_hashes import OPTION_LETTERS
    bank = {l: canon(getattr(question, f'option_{l.lower()}', ''))[:80] for l in OPTION_LETTERS}
    block = src.question_text(page, offset)
    m = re.search(r'(?:^|\s)\(?%s\)\s+(.{3,80}?)(?:\n|\s\(?[a-d]\)\s|$)' % letter.lower(), block, re.I)
    if not m:
        return letter, 'assumed_same'
    printed = canon(m.group(1))[:40]
    if not printed:
        return letter, 'assumed_same'
    hits = [l for l, t in bank.items() if t and (t.startswith(printed[:20]) or printed.startswith(t[:20]))]
    if len(hits) != 1:
        return letter, 'assumed_same'
    return hits[0], 'same' if hits[0] == letter else 'reordered'


def load_paths(registry_path: str, inventory_path: str = '') -> tuple:
    """({file name: path}, {file name: sha256})."""
    paths, shas = {}, {}
    for row in json.load(open(registry_path, encoding='utf-8')):
        paths.setdefault(row['file_name'], row['path'])
        if row.get('sha256'):
            shas.setdefault(row['file_name'], row['sha256'])
    if inventory_path:
        for row in json.load(open(inventory_path, encoding='utf-8')):
            paths.setdefault(Path(row['path']).name, row['path'])
    return paths, shas


def recover(paths: dict, shas: dict, *, exam: str = '', limit: int = 0) -> tuple:
    """(records, stats) for the active questions whose source document is available."""
    from questions.content_hashes import stem_hash, valid_key
    from questions.models import Question, QuestionSource

    links = defaultdict(list)
    for qs in QuestionSource.objects.select_related('recall_source').all():
        links[qs.question_id].append(qs)
    known = set(paths)
    active = Question.objects.filter(is_active=True)
    if exam:
        active = active.filter(exam_type=exam)
    candidates = list(active.filter(source__in=known)) + list(
        active.filter(id__in=list(links)).exclude(source__in=known))
    candidates.sort(key=lambda q: q.pk)
    if limit:
        candidates = candidates[:limit]
    sources, records, stats = {}, [], Counter()
    now = datetime.now(timezone.utc).isoformat()
    for q in candidates:
        fname = q.source if q.source in known else (
            links[q.id][0].recall_source.pdf_filename if links.get(q.id) and links[q.id][0].recall_source else '')
        if fname not in sources:
            path = paths.get(fname)
            sources[fname] = Source(path) if path and os.path.exists(path) else None
        src = sources[fname]
        if src is None:
            stats['source_missing'] += 1
            continue
        stem_key = canon(q.question_text)[:45]
        hits = src.index.get(stem_key, [])
        if not hits and len(stem_key) >= 30:   # prefix differs slightly (OCR / import trimming)
            hits = [h for k, hs in src.index.items() if k[:30] == stem_key[:30] for h in hs]
        link = links.get(q.id, [None])[0]
        if link and hits:
            near = [h for h in hits if abs(h[0] - (link.page_number - 1)) <= 1 and h[1] == link.question_number_in_pdf]
            hits = near or hits
        if not hits and link and link.page_number and link.question_number_in_pdf:
            hits, located = [(link.page_number - 1, link.question_number_in_pdf, 0)], False
        else:
            located = bool(hits)
        answers = {}
        for page, qno, off in hits:
            if page >= len(src.pages):
                continue
            letter, method, ev_page = src.key_for(page, qno, off)
            if letter:
                answers[(page, qno)] = (letter, method, ev_page, src.chapter[page], off)
        stored = valid_key(q.correct_answer)
        rec = {'question_id': q.id, 'stem_hash': stem_hash(q), 'exam': q.exam_type, 'year': q.year,
               'stored_key': stored, 'source_file': Path(fname).name, 'source_sha256': shas.get(fname, ''),
               'located': located, 'occurrences': len(hits), 'recovery_version': RECOVERY_VERSION,
               'recovered_at': now}
        letters = {a[0] for a in answers.values()}
        if not answers:
            rec['status'] = 'no_source_key'
        elif len(letters) > 1:
            rec.update(status='source_ambiguous', source_letters=sorted(letters))
        else:
            (page, qno), (letter, method, ev_page, chapter, off) = next(iter(answers.items()))
            bank_letter, order = map_letter(src, page, off, letter, q) if located else (letter, 'assumed_same')
            parsed = parse_chapter(chapter) if chapter else {}
            rec.update(status='match' if bank_letter == stored else 'mismatch', printed_letter=letter,
                       letter=bank_letter, option_order=order, method=method, question_page=page + 1,
                       answer_page=ev_page, question_number=qno, chapter=chapter,
                       source_exam=parsed.get('exam', ''), source_year=parsed.get('year'))
        stats[rec['status']] += 1
        if rec['status'] in ('match', 'mismatch'):
            stats['confident' if located and rec['option_order'] in ('same', 'reordered') else 'not_confident'] += 1
        records.append(rec)
    return records, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--registry', required=True)
    ap.add_argument('--inventory', default='')
    ap.add_argument('--out', required=True)
    ap.add_argument('--exam', default='')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args(argv)
    paths, shas = load_paths(args.registry, args.inventory)
    records, stats = recover(paths, shas, exam=args.exam, limit=args.limit)
    with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(f'records {len(records)}', dict(stats))
    print('method:', dict(Counter(r.get('method', '') for r in records)))
    print('option order:', dict(Counter(r.get('option_order', '') for r in records if r.get('letter'))))
    mism = Counter((r['stored_key'], r['letter']) for r in records if r['status'] == 'mismatch' and r['located'])
    print('mismatch stored->source (located):', mism.most_common(8))
    return 0


if __name__ == '__main__':
    sys.exit(main())
