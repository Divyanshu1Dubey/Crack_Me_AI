"""Backup / restore of the core catalogue (exam tracks, subjects, topics, jobs).

Used by the admin "Backup data" / "Restore data" buttons
(accounts.views.AdminSystemBackupDataView / AdminSystemRestoreDataView) and
by the ``backup_core_data`` / ``restore_core_data`` management commands.

Fixes over the original crack_cms/management/commands versions, which never
worked but always reported success:
  * the commands lived in ``crack_cms`` (not an installed app), so
    ``call_command`` could not find them;
  * the model list named ``questions.exam``, which does not exist
    (``questions.ExamTrack`` does), and the error was swallowed after the
    fixture file had already been truncated;
  * restore returned quietly when the file was missing.

Now the dump goes to a temporary file that replaces the backup only when it
is complete, and every failure raises ``CoreDataBackupError``.

Set ``CORE_DATA_BACKUP_PATH`` to a file on a persistent volume: container
disks on the hosting platform are wiped on every redeploy, so a backup there
looks complete and is gone after the next deploy. Outside DEBUG the default
``<BASE_DIR>/core_data_seed.json`` is therefore refused
(``CoreDataBackupNotConfigured``) unless a path is given explicitly
(``backup_core_data --output PATH`` / ``restore_core_data --input PATH``).
Local development (DEBUG) keeps the default. ``manage.py check --deploy``
reports a missing CORE_DATA_BACKUP_PATH (accounts.W003).
"""
from __future__ import annotations

import json
import os
import tempfile

from django.conf import settings
from django.core.management import call_command

CORE_DATA_MODELS = (
    'questions.examtrack',
    'questions.subject',
    'questions.topic',
    'jobs.jobcategory',  # Job.category is a FK; without it a restore into an empty DB fails
    'jobs.job',
)


class CoreDataBackupError(Exception):
    """Backup or restore did not complete."""


class CoreDataBackupNotConfigured(CoreDataBackupError):
    """No persistent backup location is configured (production without CORE_DATA_BACKUP_PATH)."""


def core_data_backup_path() -> str:
    """CORE_DATA_BACKUP_PATH, or the BASE_DIR default in DEBUG only."""
    configured = os.getenv('CORE_DATA_BACKUP_PATH', '').strip()
    if configured:
        return configured
    if not settings.DEBUG:
        raise CoreDataBackupNotConfigured(
            'CORE_DATA_BACKUP_PATH is not set. The default file would be on the container disk, '
            'which every redeploy wipes; point CORE_DATA_BACKUP_PATH at a persistent volume.'
        )
    return os.path.join(str(settings.BASE_DIR), 'core_data_seed.json')


def _read_fixture(path: str) -> list:
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise CoreDataBackupError('Backup file is not a Django fixture (expected a JSON list).')
    return data


def backup_core_data(path: str | None = None) -> tuple[str, int]:
    """Dump CORE_DATA_MODELS to ``path`` atomically. Returns (path, object_count)."""
    path = path or core_data_backup_path()
    directory = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix='.core_data_seed.', suffix='.json.tmp', dir=directory)
        os.close(fd)
    except OSError as exc:
        raise CoreDataBackupError(f'Cannot write backup to {directory}: {exc}') from exc
    try:
        call_command('dumpdata', *CORE_DATA_MODELS, indent=2, output=tmp_path, verbosity=0)
        count = len(_read_fixture(tmp_path))
        os.replace(tmp_path, path)
    except CoreDataBackupError:
        _discard(tmp_path)
        raise
    except Exception as exc:
        _discard(tmp_path)
        raise CoreDataBackupError(f'Core data backup failed: {exc}') from exc
    return path, count


def restore_core_data(path: str | None = None) -> int:
    """Load a backup written by backup_core_data. Returns the object count."""
    path = path or core_data_backup_path()
    if not os.path.isfile(path):
        raise CoreDataBackupError(f'No backup file found at {path}. Run a backup first.')
    try:
        data = _read_fixture(path)
    except (OSError, ValueError) as exc:
        raise CoreDataBackupError(f'Backup file is unreadable: {exc}') from exc
    if not data:
        raise CoreDataBackupError('Backup file is empty; nothing to restore.')
    allowed = set(CORE_DATA_MODELS)
    unexpected = sorted({str(obj.get('model', '')).lower() for obj in data if isinstance(obj, dict)} - allowed)
    if unexpected or not all(isinstance(obj, dict) for obj in data):
        raise CoreDataBackupError(f'Backup file contains unexpected records: {", ".join(unexpected) or "malformed entries"}.')
    try:
        call_command('loaddata', path, verbosity=0)
    except Exception as exc:
        raise CoreDataBackupError(f'Core data restore failed: {exc}') from exc
    return len(data)


def _discard(tmp_path: str) -> None:
    try:
        os.unlink(tmp_path)
    except FileNotFoundError:
        pass
