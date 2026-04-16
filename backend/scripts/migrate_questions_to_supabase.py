#!/usr/bin/env python3
"""Migrate question-bank data from local SQLite to Supabase Postgres."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
MANAGE_PY = BACKEND_DIR / "manage.py"


def run_manage(args: list[str], env: dict[str, str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(MANAGE_PY), *args]
    return subprocess.run(
        cmd,
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def validate_supabase_url(database_url: str) -> None:
    if not database_url:
        raise ValueError("Supabase database URL is required.")
    lowered = database_url.lower()
    if "[your-password]" in lowered:
        raise ValueError("DATABASE_URL still contains [YOUR-PASSWORD]. Replace it with your real Supabase DB password.")

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use postgres:// or postgresql://")

    host = (parsed.hostname or "").lower()
    is_supabase_cloud = host.endswith(".supabase.co")
    is_supabase_local = host in {"127.0.0.1", "localhost"}
    if not (is_supabase_cloud or is_supabase_local):
        raise ValueError(
            "Expected a Supabase host (*.supabase.co) or local Supabase host (127.0.0.1/localhost)."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate question data from local SQLite to Supabase Postgres.")
    parser.add_argument(
        "--database-url",
        default=(os.environ.get("SUPABASE_DATABASE_URL") or "").strip(),
        help="Supabase Postgres URL. Defaults to SUPABASE_DATABASE_URL env var.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not delete existing Subject/Topic/Question rows in Supabase before import.",
    )
    args = parser.parse_args()

    database_url = (args.database_url or "").strip()
    validate_supabase_url(database_url)

    source_env = os.environ.copy()
    source_env.pop("DATABASE_URL", None)

    target_env = os.environ.copy()
    target_env["DATABASE_URL"] = database_url

    with tempfile.TemporaryDirectory(prefix="questions-migration-") as tmpdir:
        fixture_path = Path(tmpdir) / "questions_fixture.json"

        print("[1/5] Exporting Subject/Topic/Question data from local SQLite...")
        run_manage(
            [
                "dumpdata",
                "questions.Subject",
                "questions.Topic",
                "questions.Question",
                "--natural-foreign",
                "--natural-primary",
                "--indent",
                "2",
                "--output",
                str(fixture_path),
            ],
            env=source_env,
        )

        print("[2/5] Running migrations on Supabase database...")
        run_manage(["migrate", "--noinput"], env=target_env)

        if not args.keep_existing:
            print("[3/5] Clearing existing question-bank tables in Supabase...")
            run_manage(
                [
                    "shell",
                    "-c",
                    (
                        "from django.db import transaction; "
                        "from questions.models import Question, Topic, Subject; "
                        "with transaction.atomic(): "
                        " Question.objects.all().delete(); "
                        " Topic.objects.all().delete(); "
                        " Subject.objects.all().delete(); "
                        "print('Cleared existing question-bank rows')"
                    ),
                ],
                env=target_env,
            )
        else:
            print("[3/5] Keeping existing Supabase rows (no table cleanup).")

        print("[4/5] Importing fixture into Supabase...")
        run_manage(["loaddata", str(fixture_path)], env=target_env)

        print("[5/5] Verifying imported row counts...")
        result = run_manage(
            [
                "shell",
                "-c",
                (
                    "from questions.models import Subject, Topic, Question; "
                    "print({'subjects': Subject.objects.count(), 'topics': Topic.objects.count(), 'questions': Question.objects.count()})"
                ),
            ],
            env=target_env,
            capture_output=True,
        )
        print(result.stdout.strip())

    print("Migration complete. Your question bank is now stored in Supabase Postgres.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        raise SystemExit(exc.returncode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
