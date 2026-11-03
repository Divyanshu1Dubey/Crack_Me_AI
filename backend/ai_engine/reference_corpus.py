"""Page-aware reference corpus: the evidence base for answer verification and RAG.

A separate SQLite store (``settings.REFERENCE_CORPUS_PATH``, default
``chroma_db/reference_corpus.sqlite3``; gitignored because the sources are
copyrighted books and notes). Built by ``python -m ai_eval.build_reference_corpus``.

Tables
------
sources     one row per distinct document (sha256): title, edition and year only
            when the file states them (never guessed), evidence ``tier``
            (lower = more authoritative), ``kind`` (textbook, notes,
            pyq_compilation, question_paper), licence note, page count.
pages       extracted text per page with the method used (text layer, OCR,
            DOCX section) and the number of embedded images, so evidence can
            point at a page and the page can be rendered for admins.
chunks      retrieval units (~1,000 chars) that may span consecutive pages
            (``page_start``..``page_end``) so a qualification is not cut off,
            with the nearest heading.
embeddings  dense vectors (fp16) per chunk and model.

Evidence tiers (configurable per source in the registry):
  1 official answer key / correction, 2 guideline / professional body,
  3 standard textbook, 4 notes and coaching compilations (secondary),
  5 raw question papers (never evidence for a fact; used to detect
  duplicates and published keys).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    sha256 TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    edition TEXT,
    year INTEGER,
    tier INTEGER NOT NULL,
    kind TEXT NOT NULL,
    subject TEXT,
    licence TEXT,
    file_name TEXT NOT NULL,
    path TEXT NOT NULL,
    pages INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',   -- extracting | needs_ocr | done | duplicate
    content_sha256 TEXT,                      -- hash of the normalised text (same content, different file)
    duplicate_of INTEGER REFERENCES sources(id),
    added_at TEXT
);
CREATE INDEX IF NOT EXISTS sources_content ON sources(content_sha256);
CREATE TABLE IF NOT EXISTS pages (
    source_id INTEGER NOT NULL REFERENCES sources(id),
    page_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    method TEXT NOT NULL,
    chars INTEGER NOT NULL,
    image_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (source_id, page_no)
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    heading TEXT,
    kind TEXT NOT NULL DEFAULT 'text',
    text TEXT NOT NULL,
    chars INTEGER NOT NULL,
    text_hash TEXT                            -- normalised-text hash; a repeated passage is stored once
);
CREATE INDEX IF NOT EXISTS chunks_source ON chunks(source_id, page_start);
CREATE INDEX IF NOT EXISTS chunks_hash ON chunks(text_hash);
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL,
    PRIMARY KEY (chunk_id, model)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

TIER_LABELS = {
    1: 'official answer key',
    2: 'guideline',
    3: 'standard textbook',
    4: 'notes / compilation (secondary)',
    5: 'question paper (not evidence)',
}


@dataclass(frozen=True)
class SourceRef:
    id: int
    title: str
    edition: Optional[str]
    year: Optional[int]
    tier: int
    kind: str

    def citation(self, page_start: int, page_end: int) -> str:
        """'Ghai Essential Pediatrics, 9e, p. 312' -- only stored metadata, never guessed."""
        parts = [self.title]
        if self.edition:
            parts.append(self.edition)
        if self.year and str(self.year) not in ' '.join(parts):
            parts.append(str(self.year))
        pages = f'p. {page_start}' if page_start == page_end else f'pp. {page_start}-{page_end}'
        return ', '.join(parts) + (f', {pages}' if self.kind != 'notes_docx' else f', section {page_start}')


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if readonly:
        conn = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def sources(conn: sqlite3.Connection) -> dict[int, SourceRef]:
    return {
        r['id']: SourceRef(r['id'], r['title'], r['edition'], r['year'], r['tier'], r['kind'])
        for r in conn.execute('SELECT id, title, edition, year, tier, kind FROM sources')
    }


def iter_chunks(conn: sqlite3.Connection, *, max_tier: int = 4) -> Iterable[sqlite3.Row]:
    """Chunks usable as evidence (tier <= max_tier; question papers excluded by default)."""
    return conn.execute(
        'SELECT c.id, c.source_id, c.page_start, c.page_end, c.heading, c.kind, c.text '
        'FROM chunks c JOIN sources s ON s.id = c.source_id WHERE s.tier <= ? AND s.status = ? ORDER BY c.id',
        (max_tier, 'done'),
    )
