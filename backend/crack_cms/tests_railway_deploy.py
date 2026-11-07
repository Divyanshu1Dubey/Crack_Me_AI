"""Railway deploy contract (docs/DEPLOY_RAILWAY.md): health check, release / start scripts."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from crack_cms.settings import RAILWAY_HEALTHCHECK_HOST, _with_railway_healthcheck_host

BACKEND_DIR = Path(settings.BASE_DIR)


def _commands(name: str) -> list[str]:
    text = (BACKEND_DIR / name).read_text(encoding='utf-8')
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#')]


class RailwayHealthCheckTests(TestCase):
    def test_healthcheck_host_is_added_only_on_railway(self):
        self.assertEqual(_with_railway_healthcheck_host(['api.cracklabs.app'], {}), ['api.cracklabs.app'])
        self.assertEqual(
            _with_railway_healthcheck_host(['api.cracklabs.app'], {'RAILWAY_ENVIRONMENT_ID': 'env-1'}),
            ['api.cracklabs.app', RAILWAY_HEALTHCHECK_HOST],
        )
        self.assertEqual(
            _with_railway_healthcheck_host([RAILWAY_HEALTHCHECK_HOST], {'RAILWAY_ENVIRONMENT_ID': 'env-1'}),
            [RAILWAY_HEALTHCHECK_HOST],
        )
        self.assertEqual(_with_railway_healthcheck_host(['a'], {'RAILWAY_ENVIRONMENT_ID': '  '}), ['a'])

    @override_settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=[RAILWAY_HEALTHCHECK_HOST, 'api.cracklabs.app'])
    def test_health_check_answers_200_over_plain_http_while_everything_else_redirects(self):
        res = self.client.get('/api/health/', HTTP_HOST=RAILWAY_HEALTHCHECK_HOST)
        self.assertEqual(res.status_code, 200)
        other = self.client.get('/api/questions/', HTTP_HOST='api.cracklabs.app')
        self.assertEqual(other.status_code, 301)
        self.assertTrue(other['Location'].startswith('https://api.cracklabs.app/'))


class RailwayDeployScriptTests(SimpleTestCase):
    def test_scripts_use_unix_line_endings(self):
        # bash on the Linux host fails on CRLF; .gitattributes keeps *.sh LF on Windows checkouts too.
        for name in ('release.sh', 'start_web.sh'):
            self.assertNotIn(b'\r', (BACKEND_DIR / name).read_bytes(), name)

    def test_railway_json_wires_the_scripts_and_the_health_check(self):
        cfg = json.loads((BACKEND_DIR / 'railway.json').read_text(encoding='utf-8'))
        self.assertEqual(cfg['deploy']['preDeployCommand'], ['bash release.sh'])
        self.assertEqual(cfg['deploy']['startCommand'], 'bash start_web.sh')
        self.assertEqual(cfg['deploy']['healthcheckPath'], '/api/health/')

    def test_release_sh_touches_only_the_database(self):
        # Railway's pre-deploy container has no volume and discards its files.
        commands = _commands('release.sh')
        self.assertIn('python manage.py migrate --no-input', commands)
        for needle in ('restore_media_transfer', 'relink_fixture_images', 'MEDIA_ROOT', 'recall_images'):
            self.assertFalse([c for c in commands if needle in c], needle)
        for needle in ('--replace', 'flush', 'cleanup_seed_samples', 'remove_from_bank', 'delete', 'bootstrap_admin'):
            self.assertFalse([c for c in commands if needle in c], needle)

    def test_every_start_path_migrates_before_gunicorn(self):
        # Railway skips release.sh (its pre-deploy step) when the service is not using backend/railway.json,
        # then starts the Procfile web command; it never runs the Procfile release line. 2026-11-04: the new
        # code served a database without its migrations and every signed-in request answered 500. 2026-11-07:
        # that path also ran no django-q worker, so queued AI sections and reminders never ran. The Procfile
        # web line is now start_web.sh itself: both start paths migrate first, in one process, start the
        # worker and the media steps, and start gunicorn only after a successful migrate.
        web = dict(line.split(':', 1) for line in _commands('Procfile'))['web'].strip()
        self.assertEqual(web, 'bash start_web.sh')
        self.assertEqual(json.loads((BACKEND_DIR / 'railway.json').read_text(encoding='utf-8'))['deploy']['startCommand'],
                         web)

        text = (BACKEND_DIR / 'start_web.sh').read_text(encoding='utf-8')
        migrate_at = text.index('\npython manage.py migrate --no-input\n')
        self.assertLess(text.index('\nset -o errexit\n'), migrate_at)   # a failed migrate stops the start
        for later in ('RUN_MEDIA_STEPS:-1', 'RUN_QCLUSTER_IN_WEB:-1', 'exec gunicorn'):
            self.assertLess(migrate_at, text.index(later), later)

    def test_start_web_restores_media_in_the_background_before_gunicorn(self):
        text = (BACKEND_DIR / 'start_web.sh').read_text(encoding='utf-8')
        restore = text.index('python manage.py restore_media_transfer')
        relink = text.index('python manage.py relink_fixture_images --apply')
        gunicorn = text.index('exec gunicorn')
        self.assertLess(restore, relink)
        self.assertLess(relink, gunicorn)
        block = text[text.index('RUN_MEDIA_STEPS'):gunicorn]
        self.assertIn(') &', block)  # backgrounded: the health check never waits for the restore
