"""Write media files staged in the database onto this server's disk (persistent volume).

A new host starts with an empty volume, and Railway cannot upload files into a volume from outside.
``scripts/railway/upload_media_to_db.py`` (run on a machine that has the files) stages them in the
table ``ops_media_transfer``; this command (run on the server, e.g. from release.sh) writes each one to
``MEDIA_ROOT/<rel_path>`` (target ``media``) or ``SUPABASE_STORAGE_MIRROR_DIR/<rel_path>`` (target
``mirror``), verifies its SHA-256 and skips files already present with the same size.

    python manage.py restore_media_transfer             # write missing files (idempotent)
    python manage.py restore_media_transfer --dry-run   # count only
    python manage.py restore_media_transfer --drop      # after a COMPLETE restore, drop the table

A missing table is not an error (nothing staged).
"""
import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

TABLE = 'ops_media_transfer'


def _table_exists() -> bool:
    with connection.cursor() as cur:
        cur.execute('SELECT to_regclass(%s)', [f'public.{TABLE}'])
        return cur.fetchone()[0] is not None


def _safe_target(root: Path, rel_path: str) -> Path:
    parts = [p for p in rel_path.replace('\\', '/').split('/') if p]
    if not parts or any(p in ('.', '..') for p in parts) or rel_path.startswith(('/', '\\')) or ':' in parts[0]:
        raise CommandError(f'unsafe path in {TABLE}: {rel_path!r}')
    target = (root / Path(*parts)).resolve()
    if not str(target).startswith(str(root.resolve()) + os.sep):
        raise CommandError(f'path escapes its root: {rel_path!r}')
    return target


class Command(BaseCommand):
    help = 'Write media files staged in ops_media_transfer onto MEDIA_ROOT / SUPABASE_STORAGE_MIRROR_DIR.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--drop', action='store_true', help='drop the table after every file was restored and verified')
        parser.add_argument('--batch', type=int, default=50)

    def handle(self, *args, **opts):
        if connection.vendor != 'postgresql':
            self.stdout.write('restore_media_transfer: PostgreSQL only; skipped')
            return
        if not _table_exists():
            self.stdout.write('restore_media_transfer: nothing staged (no ops_media_transfer table)')
            return
        roots = {'media': Path(settings.MEDIA_ROOT)}
        mirror = getattr(settings, 'SUPABASE_STORAGE_MIRROR_DIR', '') or ''
        if mirror:
            roots['mirror'] = Path(mirror)
        with connection.cursor() as cur:
            cur.execute(f'SELECT id, target, rel_path, sha256, size FROM {TABLE} ORDER BY id')
            rows = cur.fetchall()
        written = skipped = no_root = failed = 0
        todo = []
        for row_id, target, rel_path, sha, size in rows:
            root = roots.get(target)
            if root is None:
                no_root += 1
                continue
            path = _safe_target(root, rel_path)
            if path.is_file() and path.stat().st_size == size:
                skipped += 1
                continue
            todo.append((row_id, path, sha))
        self.stdout.write(f'restore_media_transfer: {len(rows)} staged, {skipped} already on disk, '
                          f'{len(todo)} to write, {no_root} without a configured root')
        if opts['dry_run']:
            return
        for start in range(0, len(todo), opts['batch']):
            part = todo[start:start + opts['batch']]
            with connection.cursor() as cur:
                cur.execute(f'SELECT id, data FROM {TABLE} WHERE id = ANY(%s)', [[r[0] for r in part]])
                data = {row_id: bytes(blob) for row_id, blob in cur.fetchall()}
            for row_id, path, sha in part:
                blob = data.get(row_id)
                if blob is None or hashlib.sha256(blob).hexdigest() != sha:
                    failed += 1
                    self.stderr.write(f'  checksum mismatch / missing data for row {row_id}')
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + '.part')
                tmp.write_bytes(blob)
                os.replace(tmp, path)
                written += 1
        self.stdout.write(f'restore_media_transfer: wrote {written}, failed {failed}')
        if opts['drop']:
            if failed or no_root:
                raise CommandError('not dropping: some files failed or had no configured root')
            with connection.cursor() as cur:
                cur.execute(f'DROP TABLE {TABLE}')
            self.stdout.write(f'restore_media_transfer: dropped {TABLE}')
