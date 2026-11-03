"""The reference store: a separate, git-ignored SQLite file with the page-aware reference corpus.

It holds copyrighted text (internal retrieval and verification only), so it lives outside the
repository at ``settings.REFERENCE_STORE_PATH`` and is never committed. It is written only by
``manage.py build_reference_store --apply`` (into ``<store>.building``, then swapped in) and
``manage.py embed_reference_store --apply``; everything else opens it read-only
(``mode=ro``, rollback journal, so readers never create -wal / -shm sidecars).

Pages are **1-based physical page numbers** of the source file (``page_no``: what a PDF viewer
calls page N). ``page_label`` is the printed page number when it could be established (PDF page
labels, or a running header/footer number consistent over consecutive pages), else NULL and
the UI shows "PDF p. N". DOCX / text sources use the section ordinal as ``page_no`` with no label.

Tables
------
store_meta   key/value: schema_version, build_id, built_at, chunker/parser versions, embedding info
sources      one row per file (sha256): registry metadata (never guessed), tier, licence, student
             display, ingest status, the page-cache state it was built from
pages        cleaned page text (running headers/footers removed) + label, section, OCR flags
chunks       retrieval units (kinds text / table / figure / caption) with page range, section,
             ``chunk_key`` (the citation handle), ``text_hash``, ``is_duplicate_of``
chunks_fts   contentless FTS5 index (rowid = chunk_id) over lexical_index tokens
chunks_vocab fts5vocab over chunks_fts (document frequencies for IDF)
embeddings   float16 little-endian, L2-normalised vectors (rebuilt into memmap sidecars)
figures      figure captions with their page and bounding box (admin figure tools)
ingest_runs  one row per build run (arguments and statistics)
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = '1'

SOURCE_KINDS = ('textbook', 'guideline', 'notes', 'pyq_compilation', 'question_paper', 'question_set',
                'answer_key', 'workbook', 'other')
CHUNK_KINDS = ('text', 'table', 'figure', 'caption', 'list')
STUDENT_DISPLAY = ('none', 'citation', 'snippet', 'figure')
INGEST_STATUSES = ('pending', 'ok', 'partial', 'failed', 'excluded')
SEARCHABLE_STATUSES = ('ok', 'partial')

_q = lambda values: ', '.join(f"'{v}'" for v in values)  # noqa: E731  (DDL literals only)

DDL = f"""
CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
    source_id INTEGER PRIMARY KEY,
    sha256 TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    short_title TEXT,
    edition TEXT,
    year INTEGER,
    authors TEXT,
    publisher TEXT,
    isbn TEXT,
    subject TEXT,
    kind TEXT NOT NULL CHECK (kind IN ({_q(SOURCE_KINDS)})),
    tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 5),
    licence TEXT NOT NULL,
    student_display TEXT NOT NULL CHECK (student_display IN ({_q(STUDENT_DISPLAY)})),
    is_excerpt INTEGER NOT NULL DEFAULT 0,
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_bytes INTEGER,
    file_mtime_ns INTEGER,
    page_count INTEGER,
    metadata_source TEXT NOT NULL DEFAULT 'registry'
        CHECK (metadata_source IN ('registry', 'pdf_metadata', 'title_page', 'admin')),
    metadata_verified INTEGER NOT NULL DEFAULT 0,
    ingest_status TEXT NOT NULL CHECK (ingest_status IN ({_q(INGEST_STATUSES)})),
    excluded_reason TEXT,
    ingest_error TEXT,
    parser TEXT,
    parser_version TEXT,
    chunker_version TEXT,
    cache_state TEXT,
    pages_ocr_pending INTEGER NOT NULL DEFAULT 0,
    ingest_seconds REAL,
    ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS pages (
    page_id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL CHECK (page_no >= 1),
    page_label TEXT,
    label_source TEXT NOT NULL DEFAULT 'none'
        CHECK (label_source IN ('pdf_labels', 'running_header', 'interpolated', 'none')),
    section_path TEXT NOT NULL DEFAULT '',
    chapter TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('text', 'ocr', 'docx', 'txt', 'none')),
    ocr INTEGER NOT NULL DEFAULT 0,
    ocr_engine TEXT,
    ocr_pending INTEGER NOT NULL DEFAULT 0,
    text_quality REAL,
    width REAL,
    height REAL,
    UNIQUE (source_id, page_no)
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    chunk_key TEXT UNIQUE NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    label_start TEXT,
    label_end TEXT,
    section_path TEXT NOT NULL DEFAULT '',
    chapter TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL CHECK (kind IN ({_q(CHUNK_KINDS)})),
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    ocr INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL,
    is_duplicate_of INTEGER REFERENCES chunks(chunk_id),
    CHECK (page_end >= page_start)
);
CREATE INDEX IF NOT EXISTS chunks_source_page ON chunks(source_id, page_start);
CREATE INDEX IF NOT EXISTS chunks_text_hash ON chunks(text_hash);
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    vec BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS figures (
    figure_id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    bbox TEXT,
    caption TEXT NOT NULL,
    chunk_id INTEGER REFERENCES chunks(chunk_id)
);
CREATE INDEX IF NOT EXISTS figures_page ON figures(source_id, page_no);
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id INTEGER PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    args_json TEXT,
    stats_json TEXT,
    code_version TEXT
);
"""

FTS_DDL = """
DROP TABLE IF EXISTS chunks_vocab;
DROP TABLE IF EXISTS chunks_fts;
CREATE VIRTUAL TABLE chunks_fts USING fts5(body, section, content='', tokenize='unicode61');
"""
VOCAB_DDL = "CREATE VIRTUAL TABLE chunks_vocab USING fts5vocab(chunks_fts, 'row');"

REQUIRED_TABLES = ('store_meta', 'sources', 'pages', 'chunks', 'chunks_fts', 'embeddings')

SOURCE_COLUMNS = ('source_id', 'sha256', 'title', 'short_title', 'edition', 'year', 'authors', 'publisher', 'isbn',
                  'subject', 'kind', 'tier', 'licence', 'student_display', 'is_excerpt', 'file_name', 'page_count',
                  'metadata_source', 'metadata_verified', 'ingest_status', 'pages_ocr_pending')
CHUNK_COLUMNS = ('chunk_id', 'chunk_key', 'source_id', 'page_start', 'page_end', 'label_start', 'label_end',
                 'section_path', 'chapter', 'kind', 'text', 'text_hash', 'char_start', 'char_end', 'ocr',
                 'token_count', 'is_duplicate_of')


class StoreError(RuntimeError):
    pass


def create_store(path: str | os.PathLike) -> sqlite3.Connection:
    """Open (creating if needed) a store for writing: rollback journal, foreign keys on."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.executescript(DDL)
    conn.execute('INSERT OR IGNORE INTO store_meta (key, value) VALUES (?, ?)', ('schema_version', SCHEMA_VERSION))
    conn.commit()
    return conn


def open_readonly(path: str | os.PathLike, *, timeout: float = 30.0) -> sqlite3.Connection:
    uri = f'file:{Path(path).resolve().as_posix()}?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def tier_filter_sql(tiers: Optional[Iterable[int]], kinds: Optional[Iterable[str]], *, alias_s='s', alias_c='c'):
    """WHERE fragment + params for tier / chunk-kind / duplicate / status filters."""
    where = [f'{alias_c}.is_duplicate_of IS NULL',
             f"{alias_s}.ingest_status IN ({', '.join('?' for _ in SEARCHABLE_STATUSES)})"]
    params: list = list(SEARCHABLE_STATUSES)
    if tiers is not None:
        tiers = [int(t) for t in tiers]
        if not tiers:
            return '0', []
        where.append(f"{alias_s}.tier IN ({', '.join('?' for _ in tiers)})")
        params.extend(tiers)
    if kinds is not None:
        kinds = [str(k) for k in kinds]
        if not kinds:
            return '0', []
        where.append(f"{alias_c}.kind IN ({', '.join('?' for _ in kinds)})")
        params.extend(kinds)
    return ' AND '.join(where), params


class ReferenceStore:
    """Read-only access to a built store. One SQLite connection per thread."""

    def __init__(self, path: str | os.PathLike, readonly: bool = True):
        self.path = str(path)
        if not readonly:
            raise StoreError('ReferenceStore is read-only; builds go through reference_corpus.builder')
        if not os.path.exists(self.path):
            raise StoreError(f'reference store not found: {self.path}')
        self._local = threading.local()
        conn = self._conn()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
        missing = [t for t in REQUIRED_TABLES if t not in names]
        if missing:
            raise StoreError(f'not a reference store (missing {", ".join(missing)}): {self.path}')
        self.meta = {r['key']: r['value'] for r in conn.execute('SELECT key, value FROM store_meta')}
        if self.meta.get('schema_version') != SCHEMA_VERSION:
            raise StoreError(f'unsupported store schema {self.meta.get("schema_version")!r}')
        self.has_vocab = 'chunks_vocab' in names
        self._sources = None
        self._idf = None

    # ── connection ──
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = open_readonly(self.path)
            self._local.conn = conn
        return conn

    def close(self):
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    @property
    def build_id(self) -> str:
        return self.meta.get('build_id', '')

    def execute(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        return self._conn().execute(sql, tuple(params)).fetchall()

    # ── sources ──
    def sources(self) -> dict[int, dict]:
        """source_id -> source row (dict), cached for the life of the store object."""
        if self._sources is None:
            cols = ', '.join(SOURCE_COLUMNS)
            self._sources = {r['source_id']: dict(r) for r in self.execute(f'SELECT {cols} FROM sources')}
        return self._sources

    def source(self, ref) -> Optional[dict]:
        """By source_id (int) or sha256 (str)."""
        if isinstance(ref, int):
            return self.sources().get(ref)
        for src in self.sources().values():
            if src['sha256'] == ref:
                return src
        return None

    def source_file_path(self, source_id: int) -> Optional[str]:
        rows = self.execute('SELECT file_path FROM sources WHERE source_id = ?', (source_id,))
        return rows[0]['file_path'] if rows else None

    def page_labels(self, source_id: int) -> dict[int, str]:
        return {r['page_no']: r['page_label'] for r in self.execute(
            'SELECT page_no, page_label FROM pages WHERE source_id = ? AND page_label IS NOT NULL ORDER BY page_no',
            (source_id,))}

    # ── pages / chunks ──
    def page(self, source_id: int, page_no: int) -> Optional[dict]:
        rows = self.execute('SELECT * FROM pages WHERE source_id = ? AND page_no = ?', (source_id, int(page_no)))
        return dict(rows[0]) if rows else None

    def chunk(self, key: str) -> Optional[dict]:
        rows = self.execute(f'SELECT {", ".join(CHUNK_COLUMNS)} FROM chunks WHERE chunk_key = ?', (key,))
        return dict(rows[0]) if rows else None

    def chunks(self, keys: Iterable[str]) -> dict[str, dict]:
        keys = list(dict.fromkeys(keys))
        out = {}
        for i in range(0, len(keys), 500):
            part = keys[i:i + 500]
            q = ', '.join('?' for _ in part)
            for r in self.execute(f'SELECT {", ".join(CHUNK_COLUMNS)} FROM chunks WHERE chunk_key IN ({q})', part):
                out[r['chunk_key']] = dict(r)
        return out

    def chunks_by_id(self, ids: Iterable[int]) -> dict[int, dict]:
        ids = list(dict.fromkeys(int(i) for i in ids))
        out = {}
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            q = ', '.join('?' for _ in part)
            for r in self.execute(f'SELECT {", ".join(CHUNK_COLUMNS)} FROM chunks WHERE chunk_id IN ({q})', part):
                out[r['chunk_id']] = dict(r)
        return out

    def counts(self) -> dict:
        one = lambda sql: self.execute(sql)[0][0]  # noqa: E731
        return {
            'sources': one('SELECT count(*) FROM sources'),
            'sources_searchable': one("SELECT count(*) FROM sources WHERE ingest_status IN ('ok', 'partial')"),
            'pages': one('SELECT count(*) FROM pages'),
            'chunks': one('SELECT count(*) FROM chunks'),
            'chunks_canonical': one('SELECT count(*) FROM chunks WHERE is_duplicate_of IS NULL'),
            'embeddings': one('SELECT count(*) FROM embeddings'),
        }

    # ── lexical index ──
    def fts_search(self, match: str, n: int, *, tiers=None, kinds=None,
                   weights: tuple[float, float] = (1.0, 0.3)) -> list[tuple[int, float]]:
        """(chunk_id, score) best first; score = -bm25 (higher is better)."""
        if not match:
            return []
        where, params = tier_filter_sql(tiers, kinds)
        sql = (f'SELECT c.chunk_id, -bm25(chunks_fts, ?, ?) AS score FROM chunks_fts '
               f'JOIN chunks c ON c.chunk_id = chunks_fts.rowid JOIN sources s ON s.source_id = c.source_id '
               f'WHERE chunks_fts MATCH ? AND {where} ORDER BY bm25(chunks_fts, ?, ?) LIMIT ?')
        rows = self.execute(sql, [weights[0], weights[1], match, *params, weights[0], weights[1], int(n)])
        return [(r[0], float(r[1])) for r in rows]

    def doc_count(self) -> int:
        return self.execute('SELECT count(*) FROM chunks')[0][0]

    def term_idf(self) -> dict[str, float]:
        """BM25 IDF per indexed term (same formula as ai_engine.lexical_index)."""
        if self._idf is None:
            import math
            n = self.doc_count() or 1
            idf = {}
            if self.has_vocab:
                for r in self.execute("SELECT term, doc FROM chunks_vocab"):
                    idf[r[0]] = math.log(1 + (n - r[1] + 0.5) / (r[1] + 0.5))
            self._idf = idf
        return self._idf


# ─── process-wide default store ────────────────────────────────────────

_default_lock = threading.Lock()
_default: dict[str, tuple[tuple, Optional[ReferenceStore]]] = {}


def _signature(path: str) -> Optional[tuple]:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def default_store(path: Optional[str] = None) -> Optional[ReferenceStore]:
    """The store at ``settings.REFERENCE_STORE_PATH`` (or ``path``), or None when it is not
    configured, missing or unreadable. Re-opened when the file changes (after a swap)."""
    if path is None:
        from django.conf import settings
        path = (getattr(settings, 'REFERENCE_STORE_PATH', '') or '').strip()
    if not path:
        return None
    sig = _signature(path)
    if sig is None:
        return None
    cached = _default.get(path)
    if cached and cached[0] == sig:
        return cached[1]
    with _default_lock:
        cached = _default.get(path)
        if cached and cached[0] == sig:
            return cached[1]
        try:
            store = ReferenceStore(path)
        except (StoreError, sqlite3.Error) as exc:
            logger.warning('reference store unavailable (%s): %s', path, exc)
            store = None
        _default[path] = (sig, store)
        return store


def reset_default_store():
    with _default_lock:
        for _sig, store in _default.values():
            if store is not None:
                try:
                    store.close()
                except Exception:  # noqa: BLE001
                    pass
        _default.clear()


def meta_json(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute('SELECT value FROM store_meta WHERE key = ?', (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return row[0]


def set_meta(conn: sqlite3.Connection, **values):
    for key, value in values.items():
        if not isinstance(value, str):
            value = json.dumps(value, sort_keys=True)
        conn.execute('INSERT OR REPLACE INTO store_meta (key, value) VALUES (?, ?)', (key, value))
