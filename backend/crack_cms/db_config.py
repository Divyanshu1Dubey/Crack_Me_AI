"""Database settings helpers, imported by ``crack_cms/settings.py`` (kept
outside it so they can be unit tested; crack_cms/tests_wave3_infra.py)."""
from __future__ import annotations

# Supabase's transaction-mode pooler listens on 6543 (Supavisor on
# *.pooler.supabase.com, and the dedicated PgBouncer on db.<ref>.supabase.co).
# Session mode (5432) keeps one server connection per client session, where
# server-side cursors work.
TRANSACTION_POOLER_PORT = 6543

_TRUE = ('1', 'true', 'yes', 'on')
_FALSE = ('0', 'false', 'no', 'off')


def server_side_cursors_unsupported(db: dict, override: str | None = None) -> bool:
    """True when ``db`` (a ``DATABASES`` entry) reaches PostgreSQL through a
    transaction-mode connection pooler.

    There each transaction may run on another server connection, so a
    server-side cursor -- ``QuerySet.iterator()`` on PostgreSQL -- opened in
    one transaction cannot be read in the next (Django docs, "Transaction
    pooling and server-side cursors"); such a connection needs
    ``DISABLE_SERVER_SIDE_CURSORS``. ``override`` (the
    DB_DISABLE_SERVER_SIDE_CURSORS env value) forces the answer with
    true / false, e.g. for another pooler in transaction mode; otherwise
    Supabase's transaction port is detected.
    """
    flag = str(override or '').strip().lower()
    if flag in _TRUE:
        return True
    if flag in _FALSE:
        return False
    try:
        port = int(str(db.get('PORT') or '').strip() or 0)
    except ValueError:
        return False
    return port == TRANSACTION_POOLER_PORT


def statement_timeout_option(value: str | None) -> str:
    """libpq ``options`` fragment setting a server-side ``statement_timeout``,
    or '' when off.

    ``value`` is DB_STATEMENT_TIMEOUT_MS: a whole number of milliseconds;
    unset, 0, negative or not a number means no timeout (PostgreSQL's
    default). PostgreSQL then cancels any statement that runs longer, so one
    pathological query cannot hold a database backend (and the gunicorn
    thread waiting on it) indefinitely. It applies to every connection the
    process opens -- migrations and long management commands included -- so
    set it on the web service only. A connection pooler must forward the
    ``options`` startup parameter (check before enabling it in production).
    """
    try:
        ms = int(str(value or '').strip() or 0)
    except ValueError:
        return ''
    return f'-c statement_timeout={ms}' if ms > 0 else ''
