"""Write one staged media file onto this server's disk the first time it is asked for (2026-11-07).

``scripts/railway/upload_media_to_db.py`` (run where the files are) stages files in the table
``ops_media_transfer``; ``manage.py restore_media_transfer`` writes them at container start
(``start_web.sh``). A file staged after the last start used to wait for the next restart -- the July 2026
imports' figures (``/media/imported/...``) were never on the production volume and showed "Figure could
not be loaded". The image endpoint now calls ``restore_staged_file`` when a figure's file is missing, so a
staged file serves at once.

Same safeguards as the command: the SHA-256 must match, the write is atomic, the path cannot leave its
root. A miss is remembered for a few minutes, so a figure that was never staged costs one query per
worker per period, not one per page view.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.db import DatabaseError, connection

logger = logging.getLogger(__name__)

TABLE = 'ops_media_transfer'
MISS_TTL_SECONDS = 300
_misses: dict = {}


def _root(target: str) -> Optional[Path]:
    if target == 'media':
        return Path(settings.MEDIA_ROOT)
    if target == 'mirror':
        mirror = getattr(settings, 'SUPABASE_STORAGE_MIRROR_DIR', '') or ''
        return Path(mirror) if mirror else None
    return None


def safe_path(root: Path, rel_path: str) -> Optional[Path]:
    """``root/rel_path`` when it stays inside ``root``, else None."""
    parts = [p for p in (rel_path or '').replace('\\', '/').split('/') if p]
    if not parts or any(p in ('.', '..') for p in parts) or ':' in parts[0] or (rel_path or '').startswith(('/', '\\')):
        return None
    base = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(base, *parts))
    return Path(candidate) if candidate.startswith(base + os.sep) else None


def restore_staged_file(target: str, rel_path: str) -> Optional[str]:
    """The file's path on disk: already there, or written now from ``ops_media_transfer``; else None."""
    root = _root(target)
    path = safe_path(root, rel_path) if root is not None else None
    if path is None:
        return None
    if path.is_file():
        return str(path)
    key = (target, rel_path)
    missed_at = _misses.get(key)
    if missed_at is not None and time.monotonic() - missed_at < MISS_TTL_SECONDS:
        return None
    try:
        if TABLE not in connection.introspection.table_names():
            _misses[key] = time.monotonic()
            return None
        with connection.cursor() as cur:
            cur.execute(f'SELECT sha256, data FROM {TABLE} WHERE target = %s AND rel_path = %s', [target, rel_path])
            row = cur.fetchone()
    except DatabaseError:
        logger.warning('media_restore: could not read %s', TABLE)
        return None
    if not row:
        _misses[key] = time.monotonic()
        return None
    sha, blob = row[0], bytes(row[1])
    if hashlib.sha256(blob).hexdigest() != (sha or '').strip():
        _misses[key] = time.monotonic()
        logger.warning('media_restore: checksum mismatch for a staged %s file; not written', target)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.part')
    partial.write_bytes(blob)
    os.replace(partial, path)
    _misses.pop(key, None)
    logger.info('media_restore: wrote a staged %s file (%s bytes)', target, len(blob))
    return str(path)
