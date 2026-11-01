"""In-memory BM25 index over the textbook RAG chunk store.

Why: ``RAGPipeline.search`` used to score chunks with a hand-written TF-IDF
cosine, stopped after the first ``RAG_MAX_SEARCH_CHUNKS`` (2,000) rows in
rowid order — so 74% of the 7,823-chunk store (267 of 274 books) was never
searched — and fetched IDF with one SQL query per term per chunk (~3.5 s per
query). This module scores the whole store with Okapi BM25 from an inverted
index held in memory (built once per process, rebuilt when the store file
changes), and applies a corpus policy:

* one indexing pass per source file (the same file was indexed under two or
  three book names, with different chunk sizes, so top-k filled with copies);
* documents that are not study material are never returned (personal / form
  PDFs that ended up in the store, an internal business document);
* raw question-paper chunks are excluded unless a caller asks for a book
  explicitly (they are question text, not explanations).

Benchmarks: docs/audit/RAG_BENCHMARK.md (``manage.py rag_benchmark``).
"""
from __future__ import annotations

import hashlib
import heapq
import logging
import math
import os
import re
import sqlite3
import threading
import time
import unicodedata
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# ─── Text normalisation ─────────────────────────────────────────────────

_GREEK = {
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon',
    'ζ': 'zeta', 'η': 'eta', 'θ': 'theta', 'ι': 'iota', 'κ': 'kappa',
    'λ': 'lambda', 'μ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'ο': 'omicron',
    'π': 'pi', 'ρ': 'rho', 'σ': 'sigma', 'ς': 'sigma', 'τ': 'tau',
    'υ': 'upsilon', 'φ': 'phi', 'χ': 'chi', 'ψ': 'psi', 'ω': 'omega',
}
_GREEK_TABLE = str.maketrans(_GREEK)
_TOKEN_RE = re.compile(r'[a-z0-9]+')

STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had
has have having he her here hers him his how i if in into is it its itself just me more most my
no nor not now of off on once only or other our ours out over own same she should so some such
than that the their theirs them then there these they this those through to too under until up
very was we were what when where which while who whom why will with would you your yours
following true false statement statements correct incorrect regarding except
""".split())


def fold(text: str) -> str:
    """Lower-case, Greek letters to names (β → beta), strip diacritics."""
    text = unicodedata.normalize('NFKC', text or '').lower().translate(_GREEK_TABLE)
    text = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _s_stem(token: str) -> str:
    """Harman's conservative plural stemmer (keeps medical terms intact)."""
    if len(token) <= 3 or token.isdigit():
        return token
    if token.endswith('ies') and not token.endswith(('eies', 'aies')):
        return token[:-3] + 'y'
    if token.endswith('es') and not token.endswith(('aes', 'ees', 'oes')):
        return token[:-1]
    if token.endswith('s') and not token.endswith(('us', 'ss', 'is')):
        return token[:-1]
    return token


def tokenize(text: str, stem: bool = True) -> list[str]:
    """Tokens for indexing and querying: alphanumeric runs (hyphens and
    slashes split words), stopwords and 1-character tokens dropped."""
    tokens = [t for t in _TOKEN_RE.findall(fold(text)) if len(t) > 1 and t not in STOPWORDS]
    return [_s_stem(t) for t in tokens] if stem else tokens


def content_key(text: str) -> str:
    """Identity of a chunk's content (whitespace/case-insensitive)."""
    return hashlib.md5(' '.join(_TOKEN_RE.findall(fold(text))).encode('utf-8'), usedforsecurity=False).hexdigest()


# ─── Corpus policy ──────────────────────────────────────────────────────

# Not study material: personal / administrative forms and internal docs.
# Matched against the source file name and the book name (case-insensitive).
EXCLUDED_DOCUMENT_PATTERNS = (
    r'affidavit', r'disability', r'certificate', r'proforma', r'performa',
    r'cms[\s_-]*daf[\s_-]*\d',  # the filled application-form PDF, not DAF guidance notes
    r'travel+ing allowance', r'competitor', r'prerequ?isi?tie?', r'armed force',
)
_EXCLUDED_RE = re.compile('|'.join(EXCLUDED_DOCUMENT_PATTERNS), re.IGNORECASE)

# Raw previous-year question papers (questions + answer keys, not explanations).
_QUESTION_PAPER_RE = re.compile(
    r'(^|[^a-z])(19|20)\d\d[\s_-]*paper|paper[\s_-]*\d|\bpyq\b|question[\s_-]*paper',
    re.IGNORECASE,
)


def is_excluded_document(book: str, source_file: str) -> bool:
    return bool(_EXCLUDED_RE.search(f'{book} {source_file}'.replace('_', ' ')))


def is_question_paper(book: str, source_file: str) -> bool:
    name = f'{book} {source_file}'
    if 'database' in name.lower():  # curated PYQ topic database, not a paper
        return False
    return bool(_QUESTION_PAPER_RE.search(name.replace('_', ' ')))


# ─── Index ──────────────────────────────────────────────────────────────

@dataclass
class Doc:
    chunk_id: str
    text: str
    book: str
    page: int
    source_file: str
    key: str
    question_paper: bool
    length: int = 0


@dataclass
class IndexStats:
    rows_in_store: int = 0
    docs_indexed: int = 0
    dropped_alias_copies: int = 0
    dropped_duplicate_content: int = 0
    dropped_excluded_documents: int = 0
    question_paper_docs: int = 0
    terms: int = 0
    build_seconds: float = 0.0
    excluded_books: list = field(default_factory=list)


class BM25Index:
    """Okapi BM25 over documents; postings stored as compact int arrays."""

    def __init__(self, docs: list[Doc], k1: float = 1.2, b: float = 0.75, stem: bool = True):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.stem = stem
        postings_docs: dict[str, array] = defaultdict(lambda: array('i'))
        postings_tf: dict[str, array] = defaultdict(lambda: array('i'))
        total_len = 0
        for idx, doc in enumerate(docs):
            counts = Counter(tokenize(doc.text, stem=stem))
            doc.length = sum(counts.values())
            total_len += doc.length
            for term, tf in counts.items():
                postings_docs[term].append(idx)
                postings_tf[term].append(tf)
        self.postings_docs = dict(postings_docs)
        self.postings_tf = dict(postings_tf)
        n = len(docs) or 1
        self.avgdl = (total_len / n) if docs else 1.0
        self.idf = {
            term: math.log(1 + (n - len(ids) + 0.5) / (len(ids) + 0.5))
            for term, ids in self.postings_docs.items()
        }

    def max_score(self, query: str) -> float:
        """Upper bound of a document's score for this query (each term's
        idf × (k1+1)); used to normalise scores to 0..1 across queries."""
        terms = set(tokenize(query, stem=self.stem))
        return sum(self.idf.get(t, 0.0) * (self.k1 + 1) for t in terms)

    def scores(self, query: str) -> dict[int, float]:
        terms = set(tokenize(query, stem=self.stem))
        acc: dict[int, float] = defaultdict(float)
        k1, b, avgdl = self.k1, self.b, self.avgdl
        for term in terms:
            ids = self.postings_docs.get(term)
            if not ids:
                continue
            idf = self.idf[term]
            tfs = self.postings_tf[term]
            for i in range(len(ids)):
                d = ids[i]
                tf = tfs[i]
                dl = self.docs[d].length
                acc[d] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
        return acc

    def search(self, query: str, n: int = 5, *, book: Optional[str] = None,
               include_question_papers: bool = False, min_score: float = 0.0) -> list[tuple[float, Doc]]:
        acc = self.scores(query)
        if not acc:
            return []

        def allowed(d: int) -> bool:
            doc = self.docs[d]
            if book is not None:
                return doc.book == book
            return include_question_papers or not doc.question_paper

        best = heapq.nlargest(n, ((s, d) for d, s in acc.items() if s > min_score and allowed(d)),
                              key=lambda x: x[0])
        return [(s, self.docs[d]) for s, d in best]


def load_documents(db_path: str, *, keep_question_papers: bool = True) -> tuple[list[Doc], IndexStats]:
    """Read the chunk store (read-only) and apply the corpus policy."""
    stats = IndexStats()
    uri = f'file:{db_path}?mode=ro'
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        rows = conn.execute(
            'SELECT id, document, book, page, source_file FROM chunks ORDER BY rowid'
        ).fetchall()
    finally:
        conn.close()
    stats.rows_in_store = len(rows)

    # One indexing pass per source file: keep the book alias with the most
    # chunks (finest chunking); other aliases are re-indexed copies.
    per_file_alias: dict[str, Counter] = defaultdict(Counter)
    for _id, _text, book, _page, source_file in rows:
        per_file_alias[source_file or book][book] += 1
    chosen_alias = {f: c.most_common(1)[0][0] for f, c in per_file_alias.items()}

    docs: list[Doc] = []
    seen_keys: set[str] = set()
    excluded_books: set[str] = set()
    for chunk_id, text, book, page, source_file in rows:
        if is_excluded_document(book or '', source_file or ''):
            stats.dropped_excluded_documents += 1
            excluded_books.add(book)
            continue
        if chosen_alias.get(source_file or book) != book:
            stats.dropped_alias_copies += 1
            continue
        key = content_key(text or '')
        if not text or key in seen_keys:
            stats.dropped_duplicate_content += 1
            continue
        seen_keys.add(key)
        qp = is_question_paper(book or '', source_file or '')
        if qp and not keep_question_papers:
            continue
        stats.question_paper_docs += int(qp)
        docs.append(Doc(chunk_id=chunk_id, text=text, book=book, page=int(page or 0),
                        source_file=source_file or '', key=key, question_paper=qp))
    stats.docs_indexed = len(docs)
    stats.excluded_books = sorted(excluded_books)
    return docs, stats


# ─── Process-wide cache ────────────────────────────────────────────────

_lock = threading.Lock()
_cache: dict[str, tuple[tuple, BM25Index, IndexStats]] = {}


def _store_signature(db_path: str) -> tuple:
    sig = []
    for suffix in ('', '-wal'):
        try:
            st = os.stat(db_path + suffix)
            sig.append((st.st_size, st.st_mtime_ns))
        except OSError:
            sig.append(None)
    return tuple(sig)


def get_index(db_path: str) -> tuple[Optional[BM25Index], Optional[IndexStats]]:
    """The BM25 index for this store, built on first use and rebuilt when the
    store (or its WAL) changes. Returns (None, None) if the store is missing."""
    if not os.path.exists(db_path):
        return None, None
    sig = _store_signature(db_path)
    cached = _cache.get(db_path)
    if cached and cached[0] == sig:
        return cached[1], cached[2]
    with _lock:
        cached = _cache.get(db_path)
        if cached and cached[0] == sig:
            return cached[1], cached[2]
        started = time.perf_counter()
        try:
            docs, stats = load_documents(db_path)
        except sqlite3.Error as exc:
            logger.warning('RAG lexical index: cannot read %s: %s', db_path, exc)
            return None, None
        index = BM25Index(docs)
        stats.terms = len(index.idf)
        stats.build_seconds = round(time.perf_counter() - started, 3)
        _cache[db_path] = (sig, index, stats)
        logger.info(
            'RAG lexical index built: %d docs (%d rows; %d alias copies, %d duplicate, %d excluded), %d terms, %.2fs',
            stats.docs_indexed, stats.rows_in_store, stats.dropped_alias_copies,
            stats.dropped_duplicate_content, stats.dropped_excluded_documents, stats.terms, stats.build_seconds,
        )
        return index, stats


def invalidate(db_path: Optional[str] = None) -> None:
    with _lock:
        if db_path is None:
            _cache.clear()
        else:
            _cache.pop(db_path, None)


def iter_sentences(text: str) -> Iterable[str]:
    """Rough sentence split used by the offline extractive composer."""
    for part in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(])|\n{2,}|\n(?=[-*•]\s)', text or ''):
        part = part.strip(' \n\t-*•#')
        if len(part) >= 25:
            yield part


def extractive_answer(question: str, passages: list[dict], *, max_sentences: int = 5,
                      min_overlap: int = 2) -> Optional[dict]:
    """Answer without an LLM: the passage sentences that share the most
    distinctive terms with the question, each with its citation.

    ``passages``: dicts with ``text``, ``book``, ``page`` (RAGPipeline.search
    results). Returns None when nothing overlaps enough to be a grounded
    answer. Sentences are copied verbatim, so every claim is traceable to the
    cited source by construction.
    """
    q_terms = set(tokenize(question))
    if not q_terms or not passages:
        return None
    scored = []
    for rank, p in enumerate(passages):
        for pos, sentence in enumerate(iter_sentences(p.get('text', ''))):
            s_terms = set(tokenize(sentence))
            overlap = q_terms & s_terms
            if len(overlap) < min(min_overlap, len(q_terms)):
                continue
            # Favour coverage of the question, then earlier passages/sentences.
            score = len(overlap) / len(q_terms) + 0.15 * len(overlap) - 0.02 * rank - 0.001 * pos
            scored.append((score, rank, pos, sentence, p))
    if not scored:
        return None
    best = sorted(scored, key=lambda x: -x[0])[:max_sentences]
    best.sort(key=lambda x: (x[1], x[2]))  # keep source order for readability
    lines, citations, seen = [], [], set()
    for _score, _rank, _pos, sentence, p in best:
        cite = f"{p.get('book', 'Source')} p.{p.get('page', 0)}"
        lines.append(f'- {sentence} [{cite}]')
        if cite not in seen:
            seen.add(cite)
            citations.append({'book': p.get('book'), 'page': p.get('page'), 'excerpt': (p.get('text') or '')[:200]})
    coverage = len(q_terms & set().union(*(set(tokenize(b[3])) for b in best))) / len(q_terms)
    return {'answer': '\n'.join(lines), 'citations': citations, 'coverage': round(coverage, 3)}
