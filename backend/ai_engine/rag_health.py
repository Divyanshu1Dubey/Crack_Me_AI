"""Read-only health check of the textbook search store (chroma_db/rag_store.sqlite3).

Ported (and adapted to the current BM25 store) from branch
feat/ai-production-unification: `manage.py verify_rag_index` and the admin
endpoint GET /api/ai/knowledge/health/ both use this.
"""
from __future__ import annotations

import os
import sqlite3

from django.conf import settings

LFS_POINTER_PREFIX = b'version https://git-lfs.github.com/spec/v1'

# status -> exit code for `manage.py verify_rag_index`
EXIT_CODES = {'healthy': 0, 'disabled': 0, 'missing': 2, 'empty': 2, 'lfs_pointer': 3, 'corrupt': 3}


def rag_store_path() -> str:
    db_dir = getattr(settings, 'CHROMA_DB_DIR', os.path.join(settings.BASE_DIR, 'chroma_db'))
    return os.path.join(db_dir, 'rag_store.sqlite3')


def rag_store_health(path: str | None = None) -> dict:
    """Inspect the store without writing to it. Never raises."""
    from ai_engine.services import rag_disabled

    path = path or rag_store_path()
    report = {
        'path': path,
        'rag_disabled': rag_disabled(),
        'exists': os.path.exists(path),
        'size_bytes': 0,
        'integrity': None,
        'total_chunks': 0,
        'books': 0,
        'idf_terms': 0,
        'status': 'missing',
        'detail': '',
    }
    if not report['exists']:
        report['detail'] = 'Store file not found.'
        return _finish(report)

    report['size_bytes'] = os.path.getsize(path)
    try:
        with open(path, 'rb') as handle:
            head = handle.read(64)
    except OSError as exc:
        report.update(status='corrupt', detail=f'Cannot read store: {exc}')
        return _finish(report)
    if head.startswith(LFS_POINTER_PREFIX):
        report.update(status='lfs_pointer',
                      detail='The file is a Git LFS pointer, not the database (LFS objects were not fetched).')
        return _finish(report)

    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False)
    except sqlite3.Error as exc:
        report.update(status='corrupt', detail=f'Cannot open store: {exc}')
        return _finish(report)
    try:
        report['integrity'] = conn.execute('PRAGMA quick_check').fetchone()[0]
        if report['integrity'] != 'ok':
            report.update(status='corrupt', detail=f'Integrity check failed: {report["integrity"]}')
            return _finish(report)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'chunks' not in tables:
            report.update(status='empty', detail='No chunks table.')
            return _finish(report)
        report['total_chunks'] = conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
        report['books'] = conn.execute('SELECT COUNT(DISTINCT book) FROM chunks').fetchone()[0]
        if 'idf_cache' in tables:
            report['idf_terms'] = conn.execute('SELECT COUNT(*) FROM idf_cache').fetchone()[0]
    except sqlite3.Error as exc:
        report.update(status='corrupt', detail=f'Query failed: {exc}')
        return _finish(report)
    finally:
        conn.close()

    report['status'] = 'healthy' if report['total_chunks'] > 0 else 'empty'
    if report['status'] == 'empty':
        report['detail'] = 'The store has no chunks; run _train_all.py.'
    return _finish(report)


def _finish(report: dict) -> dict:
    # When RAG is switched off on purpose, a missing/pointer store is expected.
    if report['rag_disabled'] and report['status'] != 'healthy':
        report['detail'] = (report['detail'] + ' RAG is disabled (DISABLE_RAG), so this is expected.').strip()
        report['status'] = 'disabled'
    return report
