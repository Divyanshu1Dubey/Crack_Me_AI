#!/usr/bin/env bash
# Web start command (Railway). Railway attaches a volume to ONE service, and the
# django-q worker writes media (imports, generated videos) into MEDIA_ROOT, so by
# default the worker runs inside the web container next to gunicorn and shares
# the volume. Set RUN_QCLUSTER_IN_WEB=0 when a separate worker service has its
# own access to the same storage.
set -o errexit

# Safety net: release.sh (Railway's pre-deploy step) has already migrated, so this
# is a no-op that takes a few seconds. It matters when the pre-deploy step did not
# run: the code must never serve a database without its migrations (2026-11-04,
# every signed-in request answered 500). A failed migrate stops the start, so the
# deploy fails its health check and the previous version keeps serving. One
# process, before gunicorn forks its workers: migrating at worker import (the
# unused crack_cms/startup.py) made the workers race for the lock (ee5ab79).
python manage.py migrate --no-input

# Media steps need the volume, which Railway mounts only here (not in the
# pre-deploy container of release.sh). They run in the background so the
# health check does not wait for the first restore (~300 MB); every step is
# idempotent, so a restart simply resumes. Set RUN_MEDIA_STEPS=0 to skip.
if [ "${RUN_MEDIA_STEPS:-1}" = "1" ]; then
    (
        python manage.py shell -c "from pathlib import Path; from django.conf import settings; p = Path(settings.MEDIA_ROOT) / 'recall_images'; p.mkdir(parents=True, exist_ok=True); print('Bootstrapped', p)" || true
        # Files staged in the database by scripts/railway/upload_media_to_db.py.
        python manage.py restore_media_transfer || true
        # After the restore, so the fixture images it looks for are on disk.
        python manage.py relink_fixture_images --apply || true
        echo "start_web.sh: media steps complete"
    ) &
fi

# Answer-key audit signals shipped in key_audit/data/ (printed source keys, AI review signals;
# docs/ANSWER_KEY_AUDIT.md): each file is imported once per version, then every question is audited.
# Signals for the review queue only: no key is ever changed. In the background, because the first
# import takes a few minutes; a later start finds nothing new at once. Set RUN_KEY_AUDIT_IMPORT=0 to skip.
if [ "${RUN_KEY_AUDIT_IMPORT:-1}" = "1" ]; then
    (
        python manage.py import_bundled_key_audit --apply || true
        echo "start_web.sh: key-audit signals checked"
    ) &
fi

if [ "${RUN_QCLUSTER_IN_WEB:-1}" = "1" ]; then
    (
        # Restart the worker if it exits; it must never take gunicorn down.
        while true; do
            python manage.py qcluster || true
            echo "qcluster exited; restarting in 10 s" >&2
            sleep 10
        done
    ) &
fi

exec gunicorn crack_cms.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --log-file -
