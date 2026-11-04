"""Build the reference store from the source registry and the page / OCR cache.

``manage.py build_reference_store`` (dry run by default) plans the build; with ``--apply`` it
writes ``<store>.building`` and swaps it in atomically at the end.

Idempotent per source: a source is reused from the current store (or from an interrupted
``.building`` file, so a long build resumes) when its sha256, file size / mtime, parser version,
chunker version and page-cache state (the OCR text available for it) are unchanged; otherwise
it is re-ingested. Registry metadata (title, edition, tier, ...) is always taken fresh from the
registry. After ingestion: exact-duplicate marking across sources (the most authoritative tier
keeps the canonical copy), the FTS5 index, document frequencies, store metadata, quick_check.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import chunker
from .ingest import ingest_file, parser_version_for
from .page_cache import OCR_ENGINE_LABEL, PageCache, cache_state_key, in_flux
from .registry import SourceSpec, load_registry, select
from .store import FTS_DDL, SCHEMA_VERSION, VOCAB_DDL, create_store, set_meta
from .textutil import index_tokens
from ai_engine.lexical_index import content_key

CODE_VERSION = f'store-{SCHEMA_VERSION}/{chunker.CHUNKER_VERSION}'
SWAP_RETRIES = 10


@dataclass
class PlanItem:
    spec: SourceSpec
    action: str              # ingest | reuse | resume | exclude | failed
    reason: str
    cache_state: str
    parser_version: str
    origin_source_id: Optional[int] = None    # in the old store (reuse) or in .building (resume)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _connect_rw(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f'file:{Path(path).resolve().as_posix()}', uri=True, timeout=60, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _source_rows(path: str) -> dict[str, dict]:
    """sha256 -> source row of an existing store (read-only), {} when absent or unreadable."""
    if not path or not os.path.exists(path):
        return {}
    try:
        conn = sqlite3.connect(f'file:{Path(path).resolve().as_posix()}?mode=ro', uri=True, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            meta = dict(conn.execute('SELECT key, value FROM store_meta').fetchall())
            if meta.get('schema_version') != SCHEMA_VERSION:
                return {}
            return {r['sha256']: dict(r) for r in conn.execute('SELECT * FROM sources')}
        finally:
            conn.close()
    except sqlite3.Error:
        return {}


def _file_unchanged(row: dict, spec: SourceSpec) -> bool:
    try:
        st = os.stat(spec.path)
    except OSError:
        return False
    return row.get('file_bytes') == st.st_size and row.get('file_mtime_ns') == st.st_mtime_ns


def _reusable(row: Optional[dict], spec: SourceSpec, cache_state: str, parser_version: str, flux: bool) -> str:
    """'' when the stored content of ``row`` can be reused for ``spec``, else the reason it cannot."""
    if not row:
        return 'new source'
    if row.get('ingest_status') not in ('ok', 'partial'):
        return f"previous status {row.get('ingest_status')}"
    if row.get('parser_version') != parser_version:
        return 'parser version changed'
    if row.get('chunker_version') != chunker.CHUNKER_VERSION:
        return 'chunker version changed'
    if not _file_unchanged(row, spec):
        return 'file changed'
    if row.get('cache_state') != cache_state:
        if flux:
            return ''           # the cache is re-extracting this source: keep what we have
        return 'page cache changed (new OCR text)'
    return ''


def plan_build(specs: list[SourceSpec], *, old_rows: dict, building_rows: dict, cache: Optional[PageCache],
               max_pages: Optional[int] = None, force: bool = False) -> list[PlanItem]:
    items = []
    for spec in specs:
        pv = parser_version_for(spec.extension)
        if max_pages:
            pv = f'{pv}+max{int(max_pages)}'
        state = cache.state(spec.sha256) if cache is not None else None
        cstate, flux = cache_state_key(state), in_flux(state)
        if spec.excluded_reason:
            items.append(PlanItem(spec, 'exclude', spec.excluded_reason, cstate, pv))
            continue
        if not spec.path or not os.path.exists(spec.path):
            items.append(PlanItem(spec, 'failed', 'file missing', cstate, pv))
            continue
        if not force:
            b = building_rows.get(spec.sha256)
            if b and not _reusable(b, spec, cstate, pv, flux):
                items.append(PlanItem(spec, 'resume', 'already in the interrupted build', b['cache_state'], pv,
                                      b['source_id']))
                continue
            o = old_rows.get(spec.sha256)
            why = _reusable(o, spec, cstate, pv, flux)
            if not why:
                items.append(PlanItem(spec, 'reuse', 'unchanged', o['cache_state'], pv, o['source_id']))
                continue
        else:
            why = 'forced'
        items.append(PlanItem(spec, 'ingest', why, cstate, pv))
    return items


def _source_values(spec: SourceSpec, item: PlanItem, *, status: str, page_count=None, error='',
                   pages_ocr_pending=0, seconds=None, parser='') -> dict:
    try:
        st = os.stat(spec.path)
        size, mtime = st.st_size, st.st_mtime_ns
    except OSError:
        size = mtime = None
    return {
        'sha256': spec.sha256, 'title': spec.title, 'short_title': None, 'edition': spec.edition, 'year': spec.year,
        'authors': None, 'publisher': None, 'isbn': None, 'subject': spec.subject, 'kind': spec.kind,
        'tier': spec.tier, 'licence': spec.licence, 'student_display': spec.student_display,
        'is_excerpt': int(spec.is_excerpt), 'file_name': spec.file_name, 'file_path': spec.path or None,
        'file_bytes': size, 'file_mtime_ns': mtime, 'page_count': page_count, 'metadata_source': 'registry',
        'metadata_verified': 0, 'ingest_status': status,
        'excluded_reason': spec.excluded_reason or None, 'ingest_error': error or None, 'parser': parser or None,
        'parser_version': item.parser_version, 'chunker_version': chunker.CHUNKER_VERSION,
        'cache_state': item.cache_state, 'pages_ocr_pending': pages_ocr_pending, 'ingest_seconds': seconds,
        'ingested_at': _now(),
    }


def _insert_source(conn, values: dict) -> int:
    conn.execute('DELETE FROM sources WHERE sha256 = ?', (values['sha256'],))
    cols = ', '.join(values)
    cur = conn.execute(f'INSERT INTO sources ({cols}) VALUES ({", ".join("?" for _ in values)})', list(values.values()))
    return cur.lastrowid


def _delete_source_content(conn, source_id: int):
    conn.execute('DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE source_id = ?)',
                 (source_id,))
    conn.execute('DELETE FROM figures WHERE source_id = ?', (source_id,))
    conn.execute('UPDATE chunks SET is_duplicate_of = NULL WHERE is_duplicate_of IN '
                 '(SELECT chunk_id FROM chunks WHERE source_id = ?)', (source_id,))
    conn.execute('DELETE FROM chunks WHERE source_id = ?', (source_id,))
    conn.execute('DELETE FROM pages WHERE source_id = ?', (source_id,))
    conn.execute('DELETE FROM sources WHERE source_id = ?', (source_id,))


def ingest_source(spec: SourceSpec, item: PlanItem, cache: Optional[PageCache], *, max_pages=None,
                  use_ocr_cache: bool = True):
    """Parse one source: (IngestResult, list[ChunkRecord], error)."""
    if spec.extension == '.pdf' and use_ocr_cache and cache is not None:
        ocr_text = cache.ocr_pages(spec.sha256)
    else:
        ocr_text = {}
    result = ingest_file(spec.path, spec.extension, ocr_text=ocr_text, max_pages=max_pages,
                         ocr_engine=OCR_ENGINE_LABEL)
    if result.error:
        return result, [], result.error
    chunks = chunker.chunk_pages(result.pages)
    return result, chunks, ''


def write_source(conn, spec: SourceSpec, item: PlanItem, result, chunks, seconds: float) -> dict:
    pending = sum(1 for p in result.pages if p.ocr_pending)
    status = 'partial' if pending else 'ok'
    if not chunks:
        status = 'partial' if pending else 'failed'
    error = '' if chunks else ('no text yet: image-only pages wait for OCR in the page cache' if pending
                               else 'no extractable text')
    sid = _insert_source(conn, _source_values(spec, item, status=status, page_count=result.page_count, error=error,
                                              pages_ocr_pending=pending, seconds=round(seconds, 2),
                                              parser=result.parser))
    conn.executemany(
        'INSERT INTO pages (source_id, page_no, page_label, label_source, section_path, chapter, text, char_count, '
        'method, ocr, ocr_engine, ocr_pending, text_quality, width, height) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        [(sid, p.page_no, p.page_label, p.label_source, p.section_path or '', p.chapter or '', p.text, len(p.text),
          p.method, int(p.ocr), p.ocr_engine, int(p.ocr_pending), p.text_quality, p.width, p.height)
         for p in result.pages])
    figure_chunk: dict[int, int] = {}
    for rec in chunks:
        key = chunker.chunk_key(spec.sha256, rec.page_start, rec.ordinal)
        cur = conn.execute(
            'INSERT INTO chunks (chunk_key, source_id, page_start, page_end, label_start, label_end, section_path, '
            'chapter, kind, text, text_hash, char_start, char_end, ocr, token_count) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (key, sid, rec.page_start, rec.page_end, rec.label_start, rec.label_end, rec.section_path or '',
             rec.chapter or '', rec.kind, rec.text, content_key(rec.text), rec.char_start, rec.char_end,
             int(rec.ocr), rec.token_count))
        if rec.figure_index is not None and rec.figure_index not in figure_chunk:
            figure_chunk[rec.figure_index] = cur.lastrowid
    conn.executemany('INSERT INTO figures (source_id, page_no, bbox, caption, chunk_id) VALUES (?,?,?,?,?)',
                     [(sid, f.page_no, json.dumps(list(f.bbox)) if f.bbox else None, f.caption,
                       figure_chunk.get(i)) for i, f in enumerate(result.figures)])
    kinds = Counter(c.kind for c in chunks)
    return {'source_id': sid, 'status': status, 'pages': len(result.pages), 'chunks': len(chunks),
            'ocr_pages': sum(1 for p in result.pages if p.ocr), 'ocr_pending': pending, 'kinds': dict(kinds),
            'labelled_pages': sum(1 for p in result.pages if p.page_label), 'figures': len(result.figures)}


def copy_source(conn, spec: SourceSpec, item: PlanItem, alias: str) -> dict:
    """Copy a source's pages, chunks, figures and embeddings from an attached store ``alias``."""
    old_sid = item.origin_source_id
    row = conn.execute(f'SELECT * FROM {alias}.sources WHERE source_id = ?', (old_sid,)).fetchone()
    values = _source_values(spec, item, status=row['ingest_status'], page_count=row['page_count'],
                            error=row['ingest_error'] or '', pages_ocr_pending=row['pages_ocr_pending'],
                            seconds=row['ingest_seconds'], parser=row['parser'] or '')
    values['ingested_at'] = row['ingested_at']
    sid = _insert_source(conn, values)
    conn.execute(
        f'INSERT INTO pages (source_id, page_no, page_label, label_source, section_path, chapter, text, char_count, '
        f'method, ocr, ocr_engine, ocr_pending, text_quality, width, height) '
        f'SELECT ?, page_no, page_label, label_source, section_path, chapter, text, char_count, method, ocr, '
        f'ocr_engine, ocr_pending, text_quality, width, height FROM {alias}.pages WHERE source_id = ?',
        (sid, old_sid))
    conn.execute(
        f'INSERT INTO chunks (chunk_key, source_id, page_start, page_end, label_start, label_end, section_path, chapter, '
        f'kind, text, text_hash, char_start, char_end, ocr, token_count) '
        f'SELECT chunk_key, ?, page_start, page_end, label_start, label_end, section_path, chapter, kind, text, '
        f'text_hash, char_start, char_end, ocr, token_count FROM {alias}.chunks WHERE source_id = ? ORDER BY chunk_id',
        (sid, old_sid))
    conn.execute(
        f'INSERT INTO embeddings (chunk_id, vec) SELECT nc.chunk_id, oe.vec FROM {alias}.embeddings oe '
        f'JOIN {alias}.chunks oc ON oc.chunk_id = oe.chunk_id JOIN chunks nc ON nc.chunk_key = oc.chunk_key '
        f'WHERE oc.source_id = ?', (old_sid,))
    conn.execute(
        f'INSERT INTO figures (source_id, page_no, bbox, caption, chunk_id) SELECT ?, f.page_no, f.bbox, f.caption, '
        f'nc.chunk_id FROM {alias}.figures f LEFT JOIN {alias}.chunks oc ON oc.chunk_id = f.chunk_id '
        f'LEFT JOIN chunks nc ON nc.chunk_key = oc.chunk_key WHERE f.source_id = ?', (sid, old_sid))
    n = conn.execute('SELECT count(*) FROM chunks WHERE source_id = ?', (sid,)).fetchone()[0]
    return {'source_id': sid, 'status': row['ingest_status'], 'chunks': n}


def mark_duplicates(conn) -> int:
    """Exact duplicates (same lexical_index.content_key): the copy in the most authoritative tier
    (then the lowest chunk id) is canonical; the others point at it."""
    conn.execute('UPDATE chunks SET is_duplicate_of = NULL WHERE is_duplicate_of IS NOT NULL')
    rows = conn.execute(
        'SELECT c.text_hash, c.chunk_id, s.tier FROM chunks c JOIN sources s ON s.source_id = c.source_id '
        'WHERE c.text_hash IN (SELECT text_hash FROM chunks GROUP BY text_hash HAVING count(*) > 1) '
        'ORDER BY c.text_hash, s.tier, c.chunk_id').fetchall()
    updates, canon_for = [], {}
    for text_hash, chunk_id, _tier in rows:
        if text_hash not in canon_for:
            canon_for[text_hash] = chunk_id
        else:
            updates.append((canon_for[text_hash], chunk_id))
    conn.executemany('UPDATE chunks SET is_duplicate_of = ? WHERE chunk_id = ?', updates)
    return len(updates)


def build_fts(conn, *, batch: int = 2000) -> int:
    conn.executescript(FTS_DDL)
    n, last = 0, 0
    while True:
        rows = conn.execute('SELECT chunk_id, text, section_path FROM chunks WHERE chunk_id > ? ORDER BY chunk_id LIMIT ?',
                            (last, batch)).fetchall()
        if not rows:
            break
        conn.executemany('INSERT INTO chunks_fts (rowid, body, section) VALUES (?, ?, ?)',
                         [(r[0], index_tokens(r[1]), index_tokens(r[2] or '')) for r in rows])
        n += len(rows)
        last = rows[-1][0]
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
    conn.executescript(VOCAB_DDL)
    return n


def compute_build_id(conn) -> str:
    rows = conn.execute(
        'SELECT s.sha256, s.parser_version, s.chunker_version, s.cache_state, s.ingest_status, s.tier, '
        '(SELECT count(*) FROM chunks c WHERE c.source_id = s.source_id) FROM sources s ORDER BY s.sha256').fetchall()
    raw = json.dumps([list(r) for r in rows] + [SCHEMA_VERSION, chunker.CHUNKER_VERSION], sort_keys=True)
    return hashlib.sha1(raw.encode('utf-8'), usedforsecurity=False).hexdigest()[:16]


def swap_into_place(building: str, store: str, *, retries: int = SWAP_RETRIES, wait: float = 3.0):
    for attempt in range(retries):
        try:
            os.replace(building, store)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(wait)


def build(registry_path: str, store_path: str, *, page_cache_path: str = '', only=None, max_pages=None,
          apply: bool = False, force: bool = False, use_ocr_cache: bool = True,
          log: Callable[[str], None] = print) -> dict:
    t0 = time.perf_counter()
    specs = select(load_registry(registry_path), only)
    cache = PageCache(page_cache_path) if page_cache_path else None
    building = store_path + '.building'
    old_rows = _source_rows(store_path)
    building_rows = _source_rows(building) if apply and os.path.exists(building) else {}
    if building_rows:
        try:
            conn = sqlite3.connect(f'file:{Path(building).resolve().as_posix()}?mode=ro', uri=True)
            target = dict(conn.execute('SELECT key, value FROM store_meta').fetchall()).get('building_for')
            conn.close()
        except sqlite3.Error:
            target = None
        if target != os.path.abspath(store_path):
            building_rows = {}
    items = plan_build(specs, old_rows=old_rows, building_rows=building_rows, cache=cache, max_pages=max_pages,
                       force=force)
    actions = Counter(i.action for i in items)
    summary = {'apply': apply, 'sources': len(items), 'actions': dict(actions),
               'page_cache': bool(cache and cache.available), 'store': store_path}
    log(f"plan: {len(items)} sources -> {dict(actions)}")
    for i in items:
        if i.action in ('ingest', 'failed') or (i.action == 'exclude' and not apply):
            log(f'  {i.action:7s} tier {i.spec.tier} {i.spec.kind:15s} {i.spec.title[:60]:60s} ({i.reason})')
    if not apply:
        summary['seconds'] = round(time.perf_counter() - t0, 1)
        return summary

    if not building_rows and os.path.exists(building):
        os.remove(building)
    conn = create_store(building)
    conn.close()
    conn = _connect_rw(building)
    conn.execute('PRAGMA foreign_keys=ON')
    set_meta(conn, building_for=os.path.abspath(store_path), building_started=_now())
    conn.commit()
    run_started = _now()

    # Drop rows of an interrupted build that the plan no longer keeps.
    keep_resume = {i.origin_source_id for i in items if i.action == 'resume'}
    for (sid,) in conn.execute('SELECT source_id FROM sources').fetchall():
        if sid not in keep_resume:
            _delete_source_content(conn, sid)
    conn.commit()

    stats = Counter()
    if any(i.action == 'reuse' for i in items):
        conn.execute('ATTACH DATABASE ? AS old', (f'file:{Path(store_path).resolve().as_posix()}?mode=ro',))
    for n_item, item in enumerate(items, start=1):
        spec = item.spec
        t = time.perf_counter()
        if item.action == 'resume':
            stats['resumed'] += 1
            continue
        if item.action == 'reuse':
            info = copy_source(conn, spec, item, 'old')
            conn.commit()
            stats['reused'] += 1
            continue
        if item.action in ('exclude', 'failed'):
            status = 'excluded' if item.action == 'exclude' else 'failed'
            _insert_source(conn, _source_values(spec, item, status=status,
                                                error='' if status == 'excluded' else item.reason))
            conn.commit()
            stats[status] += 1
            continue
        try:
            actual = sha256_file(spec.path)
        except OSError as exc:
            actual, err = None, f'cannot read file: {type(exc).__name__}'
        else:
            err = '' if actual == spec.sha256 else 'file content differs from the registry sha256 (registry stale)'
        if err:
            _insert_source(conn, _source_values(spec, item, status='failed', error=err))
            conn.commit()
            stats['failed'] += 1
            log(f'  [{n_item}/{len(items)}] FAILED {spec.title[:60]}: {err}')
            continue
        try:
            result, chunks, err = ingest_source(spec, item, cache, max_pages=max_pages, use_ocr_cache=use_ocr_cache)
        except MemoryError:
            raise
        except Exception as exc:  # noqa: BLE001  (one bad file must not stop the build)
            result, chunks, err = None, [], f'parser error: {type(exc).__name__}: {str(exc)[:200]}'
        if err:
            _insert_source(conn, _source_values(spec, item, status='failed', error=err,
                                                parser=getattr(result, 'parser', '') or ''))
            conn.commit()
            stats['failed'] += 1
            log(f'  [{n_item}/{len(items)}] FAILED {spec.title[:60]}: {err}')
            continue
        info = write_source(conn, spec, item, result, chunks, time.perf_counter() - t)
        conn.commit()
        stats['ingested'] += 1
        stats['chunks_ingested'] += info['chunks']
        log(f"  [{n_item}/{len(items)}] {info['status']:7s} tier {spec.tier} {spec.title[:50]:50s} pages {info['pages']:5d} "
            f"(ocr {info['ocr_pages']}, ocr pending {info['ocr_pending']}, labelled {info['labelled_pages']}) "
            f"chunks {info['chunks']:6d} {dict(info['kinds'])} {time.perf_counter() - t:6.1f}s")
        del result, chunks
    if any(i.action == 'reuse' for i in items):
        conn.commit()
        conn.execute('DETACH DATABASE old')

    stats['duplicates'] = mark_duplicates(conn)
    conn.commit()
    stats['fts_rows'] = build_fts(conn)
    conn.commit()
    build_id = compute_build_id(conn)
    old_meta = {}
    if os.path.exists(store_path):
        try:
            oc = sqlite3.connect(f'file:{Path(store_path).resolve().as_posix()}?mode=ro', uri=True)
            old_meta = dict(oc.execute('SELECT key, value FROM store_meta').fetchall())
            oc.close()
        except sqlite3.Error:
            old_meta = {}
    carried = {k: v for k, v in old_meta.items() if k.startswith('embed_') and k not in ('embed_build_id',)}
    from .ingest import PARSER_VERSIONS
    set_meta(conn, build_id=build_id, built_at=_now(), chunker_version=chunker.CHUNKER_VERSION,
             parser_versions=PARSER_VERSIONS, code_version=CODE_VERSION, **carried)
    conn.execute('DELETE FROM store_meta WHERE key IN (?, ?)', ('building_for', 'building_started'))
    counts = {k: conn.execute(f'SELECT count(*) FROM {k}').fetchone()[0]
              for k in ('sources', 'pages', 'chunks', 'embeddings', 'figures')}
    conn.execute('INSERT INTO ingest_runs (started_at, finished_at, args_json, stats_json, code_version) VALUES (?,?,?,?,?)',
                 (run_started, _now(), json.dumps({'only': list(only or []), 'max_pages': max_pages, 'force': force,
                                                    'use_ocr_cache': use_ocr_cache}),
                  json.dumps({**stats, **counts}), CODE_VERSION))
    conn.commit()
    conn.execute('ANALYZE')
    check = conn.execute('PRAGMA quick_check').fetchone()[0]
    conn.commit()
    conn.close()
    if cache is not None:
        cache.close()
    if check != 'ok':
        raise RuntimeError(f'quick_check failed on {building}: {check}')
    swap_into_place(building, store_path)
    summary.update({'build_id': build_id, 'stats': dict(stats), 'counts': counts,
                    'seconds': round(time.perf_counter() - t0, 1)})
    log(f"built {store_path}: build {build_id} {counts} {dict(stats)} in {summary['seconds']}s")
    return summary
