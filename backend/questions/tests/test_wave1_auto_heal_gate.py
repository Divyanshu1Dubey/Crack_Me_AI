"""Which processes start the questions auto-heal thread (audit issue CFG-16).

The relink thread writes to whatever database the process is configured for.
It used to start in every process, including ``manage.py test`` (before the
test database exists), ``shell``, ``check`` and ``migrate``, and no setting
could turn it off.
"""
from __future__ import annotations

import threading
from unittest import mock

from django.apps import apps
from django.test import SimpleTestCase

from questions import apps as questions_apps
from questions.apps import should_auto_heal

MANAGE = "/srv/app/backend/manage.py"


class ShouldAutoHealTests(SimpleTestCase):
    def test_wsgi_server_workers_still_heal_by_default(self):
        self.assertTrue(should_auto_heal(["/venv/bin/gunicorn", "crack_cms.wsgi:application"], {}, {}))
        self.assertTrue(should_auto_heal(["/venv/bin/uvicorn", "crack_cms.asgi:application"], {}, {}))
        for server in ("/venv/bin/daphne", "/venv/bin/hypercorn", "/usr/bin/uwsgi",
                       r"C:\venv\Scripts\waitress-serve.exe", r"C:\venv\Scripts\uvicorn.exe"):
            self.assertTrue(should_auto_heal([server, "crack_cms.asgi:application"], {}, {}), server)
        # A server that sets SERVER_SOFTWARE but is not listed by name.
        self.assertTrue(should_auto_heal(["/opt/server/bin/run"], {"SERVER_SOFTWARE": "Apache/2.4"}, {}))

    def test_standalone_scripts_and_interactive_sessions_do_not_heal(self):
        # CFG-16: these call django.setup() and used to start the
        # DB-writing thread against whatever DATABASE_URL backend/.env held.
        for argv in (
            ["test_all.py", "--quick"],
            ["/srv/app/backend/backfill_display_number.py"],
            ["fix_qs.py"],
            ["scripts/_export_questions.py"],
            ["-c"],
            ["/venv/lib/python3.12/site-packages/ipykernel_launcher.py", "-f", "kernel.json"],
            [""],
            [],
        ):
            self.assertFalse(should_auto_heal(argv, {}, {}), argv)
        # A blank SERVER_SOFTWARE is not a server.
        self.assertFalse(should_auto_heal(["test_all.py"], {"SERVER_SOFTWARE": "  "}, {}))

    def test_management_commands_do_not_heal(self):
        for command in ("test", "shell", "check", "migrate", "makemigrations", "collectstatic", "qcluster"):
            self.assertFalse(should_auto_heal([MANAGE, command], {}, {}), command)
        self.assertFalse(should_auto_heal(["/venv/bin/django-admin", "shell"], {}, {}))
        self.assertFalse(should_auto_heal(["/venv/lib/python3.12/site-packages/django/__main__.py", "test"], {}, {}))

    def test_python_dash_m_gunicorn_is_a_server_not_a_management_command(self):
        self.assertTrue(
            should_auto_heal(["/venv/lib/python3.12/site-packages/gunicorn/__main__.py", "crack_cms.wsgi"], {}, {})
        )
        self.assertTrue(
            should_auto_heal(["/venv/lib/python3.12/site-packages/uvicorn/__main__.py", "crack_cms.asgi"], {}, {})
        )

    def test_runserver_heals_only_in_the_reloader_child(self):
        self.assertFalse(should_auto_heal([MANAGE, "runserver", "8000"], {}, {}))
        self.assertTrue(should_auto_heal([MANAGE, "runserver", "8000"], {"RUN_MAIN": "true"}, {}))
        self.assertTrue(should_auto_heal([MANAGE, "runserver", "--noreload"], {}, {}))

    def test_pytest_never_heals(self):
        self.assertFalse(should_auto_heal(["/venv/bin/pytest"], {}, {"pytest": object()}))

    def test_env_switch_overrides_the_default(self):
        for value in ("0", "false", "False", "no", "off"):
            env = {"CRACKCMS_HEAL_ON_READY": value}
            self.assertFalse(should_auto_heal(["/venv/bin/gunicorn"], env, {}), value)
            self.assertFalse(should_auto_heal([MANAGE, "runserver"], {**env, "RUN_MAIN": "true"}, {}), value)
        for value in ("1", "true", "yes"):
            env = {"CRACKCMS_HEAL_ON_READY": value}
            self.assertTrue(should_auto_heal([MANAGE, "shell"], env, {}), value)
            self.assertTrue(should_auto_heal(["/opt/custom-server"], env, {}), value)
        # Unknown values keep the default.
        self.assertTrue(should_auto_heal(["/venv/bin/gunicorn"], {"CRACKCMS_HEAL_ON_READY": "maybe"}, {}))

    def test_this_test_run_did_not_start_the_thread(self):
        names = {t.name for t in threading.enumerate()}
        self.assertNotIn("questions-auto-heal", names)


class ReadyGateTests(SimpleTestCase):
    def test_ready_starts_no_thread_when_gate_is_closed(self):
        config = apps.get_app_config("questions")
        with mock.patch.object(questions_apps, "should_auto_heal", return_value=False), \
                mock.patch.object(questions_apps.threading, "Thread") as thread_cls:
            config.ready()
        thread_cls.assert_not_called()

    def test_ready_starts_the_thread_once_when_gate_is_open(self):
        config = apps.get_app_config("questions")
        done = threading.Event()
        with mock.patch.object(questions_apps, "should_auto_heal", return_value=True), \
                mock.patch.object(questions_apps, "_HEAL_DONE", done), \
                mock.patch.object(questions_apps.threading, "Thread") as thread_cls:
            config.ready()
            config.ready()
        thread_cls.assert_called_once()
        thread_cls.return_value.start.assert_called_once()
