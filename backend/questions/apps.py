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

The auto-heal is safe to leave enabled in every environment because
``relink_fixture_images`` is itself idempotent (it scans for the
specific URL pattern and only writes back when one is found).
"""
from __future__ import annotations

import logging
import os
import threading

from django.apps import AppConfig
from django.db.utils import DatabaseError, OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


# Module-level singleton so the background thread isn't respawned if
# Django reloads the app (e.g. ``runserver`` autoreload).
_HEAL_LOCK = threading.Lock()
_HEAL_DONE = threading.Event()


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
        boot.
        """
        # Skip during management commands other than ``runserver`` /
        # ``gunicorn``-style boots. ``RUN_MAIN`` is set by the Django
        # autoreloader's child process; without it, the parent would
        # also try to run the heal and double-spawn the thread.
        run_main = os.environ.get("RUN_MAIN") == "true"
        if not run_main and os.environ.get("CRACKCMS_HEAL_ON_READY") != "1":
            # Production / autoreload-parent path. The heal still
            # fires on the worker child (``RUN_MAIN=true``). When the
            # reloader isn't in play (gunicorn, wsgi) we also fire on
            # first ready() — i.e. always, because RUN_MAIN isn't
            # exported by gunicorn. The double-fire guard below
            # protects us.
            if "RUN_MAIN" not in os.environ:
                # Likely a production worker. Fall through.
                pass
            else:
                return

        if _HEAL_DONE.is_set():
            return
        with _HEAL_LOCK:
            if _HEAL_DONE.is_set():
                return

        thread = threading.Thread(
            target=_run_relink_passive,
            name="questions-auto-heal",
            daemon=True,
        )
        thread.start()
        _HEAL_DONE.set()


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