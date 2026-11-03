"""Read-only access to the page / OCR cache built by ``python -m ai_eval.build_reference_corpus``.

The reference store never runs OCR itself: text for image-only pages is taken from this cache
by ``(sha256, page_no)`` (``pages.method = 'ocr'``). The cache may be written by a running OCR
pass at the same time, so it is opened read-only (``mode=ro``), every query is short (no long
read transaction that would block the writer's commit), and a locked database is retried and
then treated as "no OCR available yet". A source whose OCR is unfinished is ingested with what
exists; its ``cache_state`` changes when OCR text arrives, and the next incremental build
re-ingests it.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OCR_ENGINE_LABEL = 'rapidocr (page cache)'


class PageCache:
    def __init__(self, path: str, *, timeout: float = 20.0, retries: int = 4, retry_wait: float = 2.0):
        self.path = str(path)
        self.timeout = timeout
        self.retries = retries
        self.retry_wait = retry_wait
        self._conn: Optional[sqlite3.Connection] = None
        self.available = Path(self.path).exists()
        self.errors = 0

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f'file:{Path(self.path).resolve().as_posix()}?mode=ro'
            self._conn = sqlite3.connect(uri, uri=True, timeout=self.timeout, check_same_thread=False)
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _query(self, sql: str, params=()) -> Optional[list[tuple]]:
        if not self.available:
            return None
        for attempt in range(self.retries + 1):
            try:
                return self._connect().execute(sql, params).fetchall()
            except sqlite3.OperationalError as exc:
                msg = str(exc).lower()
                if attempt < self.retries and ('locked' in msg or 'busy' in msg):
                    time.sleep(self.retry_wait)
                    continue
                if 'no such table' in msg:
                    return None
                self.errors += 1
                logger.warning('page cache read failed (%s): %s', self.path, exc)
                self.close()
                return None
            except sqlite3.DatabaseError as exc:
                self.errors += 1
                logger.warning('page cache unreadable (%s): %s', self.path, exc)
                self.close()
                return None
        return None

    def state(self, sha256: str) -> Optional[dict]:
        """{status, pages, ocr_pages, ocr_chars} for a source, or None when it is not in the cache."""
        rows = self._query('SELECT id, status FROM sources WHERE sha256 = ?', (sha256,))
        if not rows:
            return None
        source_id, status = rows[0]
        agg = self._query(
            "SELECT count(*), sum(CASE WHEN method = 'ocr' THEN 1 ELSE 0 END), "
            "sum(CASE WHEN method = 'ocr' THEN chars ELSE 0 END) FROM pages WHERE source_id = ?", (source_id,))
        pages, ocr_pages, ocr_chars = (agg[0] if agg else (0, 0, 0))
        return {'status': status, 'pages': pages or 0, 'ocr_pages': ocr_pages or 0, 'ocr_chars': ocr_chars or 0}

    def ocr_pages(self, sha256: str) -> dict[int, str]:
        """page_no (1-based) -> OCR text for the pages the cache has OCR'd."""
        rows = self._query(
            "SELECT p.page_no, p.text FROM pages p JOIN sources s ON s.id = p.source_id "
            "WHERE s.sha256 = ? AND p.method = 'ocr'", (sha256,))
        return {int(n): t or '' for n, t in (rows or [])}


def cache_state_key(state: Optional[dict]) -> str:
    """What the ingestion of a source depends on: the OCR text available for it."""
    if not state:
        return 'ocr:0:0'
    return f"ocr:{state.get('ocr_pages', 0)}:{state.get('ocr_chars', 0)}"


def in_flux(state: Optional[dict]) -> bool:
    """The cache is re-extracting this source right now (its pages are temporarily absent)."""
    return bool(state) and state.get('status') == 'extracting'
