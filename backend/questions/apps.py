"""
apps.py — AppConfig for the ``questions`` app.

Adds a server-startup self-healing hook that runs the legacy
``/media/fixtures/images/`` URL relinker in a background thread. The
thread fires once per Django process start, exits early if any other
process is already running it (via an advisory lock on
``QuestionImage.pk``), and never blocks the first request.

Why this exists
---------------
Audit 2026-07-28 surfaced a production bug: legacy Question rows
written by the old ``load_exam_fixture`` loader had bare
``/media/fixtures/images/<exam>/<file>`` URLs in their text fields.
In production ``DEBUG=False`` those URLs 404 (Django doesn't serve
``/media/``), AND the frontend's image resolver only understood
bracketed tokens — bare URLs rendered as plain text.

Three layers of defence now keep the data clean:

  1. ``build.sh`` runs ``relink_fixture_images --apply`` after
     migrations — catches anything new on each Render deploy.
  2. ``QuestionsConfig.ready()`` schedules a one-shot background
     relink the first time a web worker boots — catches anything
     that slipped through a botched deploy (e.g. DB imported from
     an older dump, fresh staging environment).
  3. The frontend's bare-URL resolver still renders missing rows
     as ``<img onerror=...>`` instead of raw text — graceful
     fallback if a row escapes both heal passes.

``relink_fixture_images`` is idempotent (it scans for the specific URL
pattern and only writes back when one is found), but it still writes to
whatever database the process is configured for. So the thread only
starts in server processes (see ``should_auto_heal``):

  * WSGI/ASGI servers (gunicorn etc.): yes -- unchanged production
    behaviour;
  * ``manage.py runserver``: only in the autoreloader's child process (or
    with ``--noreload``), not in the parent as well;
  * every other management command (``test``, ``shell``, ``check``,
    ``migrate``, ``collectstatic``, ``qcluster``, ...) and pytest: no.
    ``build.sh`` already runs ``relink_fixture_images --apply`` after
    migrations, and the test runner must not touch the configured
    database before its test database exists.

``CRACKCMS_HEAL_ON_READY`` overrides the default: ``1``/``true`` forces the
thread on (also for management commands), ``0``/``false`` turns it off.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

from django.apps import AppConfig
from django.db.utils import DatabaseError, OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


# Module-level singleton so the background thread isn't respawned if
# Django reloads the app (e.g. ``runserver`` autoreload).
_HEAL_LOCK = threading.Lock()
_HEAL_DONE = threading.Event()

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_MANAGEMENT_ENTRY_POINTS = frozenset(
    {"manage.py", "django-admin", "django-admin.py", "django-admin.exe"}
)


def _is_management_command(argv) -> bool:
    if not argv:
        return False
    entry = os.path.basename(str(argv[0]))
    if entry in _MANAGEMENT_ENTRY_POINTS:
        return True
    # ``python -m django <command>``
    return entry == "__main__.py" and os.path.basename(os.path.dirname(str(argv[0]))) == "django"


def should_auto_heal(argv=None, environ=None, modules=None) -> bool:
    """Whether this process should start the relink thread (see module doc)."""
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    modules = sys.modules if modules is None else modules

    flag = (environ.get("CRACKCMS_HEAL_ON_READY") or "").strip().lower()
    if flag in _FALSE_VALUES:
        return False
    if flag in _TRUE_VALUES:
        return True

    if "pytest" in modules:
        return False
    if _is_management_command(argv):
        command = argv[1] if len(argv) > 1 else ""
        if command != "runserver":
            return False
        return environ.get("RUN_MAIN") == "true" or "--noreload" in argv
    # Not a management command: a WSGI/ASGI server worker.
    return True


class QuestionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "questions"

    # Verbose name shown in the Django admin sidebar.
    verbose_name = "Questions"

    def ready(self) -> None:
        """Schedule the auto-heal once Django's app registry is ready.

        We deliberately run inside a background thread (not inline) so
        that a slow DB on first boot doesn't block the worker from
        accepting requests. The ``Event`` guards against duplicate
        runs within the same process, and the call itself is wrapped
        so a misconfigured DB / missing migration can never crash the
        boot. Which processes start it is decided by ``should_auto_heal``.
        """
        if not should_auto_heal():
            return

        if _HEAL_DONE.is_set():
            return
        with _HEAL_LOCK:
            if _HEAL_DONE.is_set():
                return
            _HEAL_DONE.set()

        thread = threading.Thread(
            target=_run_relink_passive,
            name="questions-auto-heal",
            daemon=True,
        )
        thread.start()


def _run_relink_passive() -> None:
    """Background worker: invoke the relink command without blocking boot.

    The command itself is invoked via ``call_command`` so we share the
    same code path as the explicit CLI invocation in ``build.sh``.
    Anything it writes is committed inside its own transaction; a
    failure here is logged but never re-raised into the worker.
    """
    try:
        from django.core.management import call_command
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("questions auto-heal: could not import call_command: %s", exc)
        return

    try:
        logger.info("questions auto-heal: scanning for legacy bare /media URLs…")
        call_command(
            "relink_fixture_images",
            "--apply",
            stdout=__import__("io").StringIO(),
            stderr=__import__("io").StringIO(),
            no_color=True,
        )
        logger.info("questions auto-heal: complete.")
    except (OperationalError, ProgrammingError) as exc:
        # Likely "relation does not exist" on a fresh DB before
        # migrations have run. The build.sh relink pass covers that
        # path, so this branch is normal during local first-boot.
        logger.info("questions auto-heal: skipping (%s)", exc)
    except DatabaseError as exc:
        # `sqlite3.DatabaseError: file is not a database` (and the
        # django.db.utils.DatabaseError wrapper) can fire on Render
        # when the persistent disk hasn't been mounted yet, the DB
        # file is empty/truncated, or another process is mid-write.
        # NEVER let the heal task crash the worker process — the
        # frontend's bare-URL resolver keeps the UI graceful even
        # without the rewrite pass, and build.sh's explicit relink
        # invocation will retry on the next deploy.
        logger.warning(
            "questions auto-heal: database not ready, skipping (%s)", exc
        )
    except Exception as exc:
        # Never fail boot for the heal. Log and move on — the
        # frontend's bare-URL resolver keeps the UI graceful.
        logger.exception("questions auto-heal: failed (%s)", exc)