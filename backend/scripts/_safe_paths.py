"""Locations for the ad-hoc backup / restore scripts in this folder.

The dumps these scripts write or read hold student data (attempts,
bookmarks, notes, flashcards, discussions, subscriptions, Supabase auth
users). Kept inside a source checkout they are one ``git add`` away from
being published -- which is how ``backend/questions_backup.json`` (attempt,
discussion, bookmark and feedback rows) ended up tracked. Same rule as
``manage.py export_questions_backup``: a location outside the repository.

No Django import: the scripts call this before ``django.setup()``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def inside_a_checkout(path) -> bool:
    """True when ``path`` is inside this project or any git working tree."""
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
        return True
    except ValueError:
        pass
    return any((parent / ".git").exists() for parent in (resolved, *resolved.parents))


def external_path(raw, *, what: str) -> Path:
    """``raw`` as an absolute path outside every checkout, else exit."""
    text = str(raw or "").strip()
    if not text:
        raise SystemExit(f"{what} is required: a location outside the repository.")
    path = Path(text).expanduser().resolve()
    if inside_a_checkout(path):
        raise SystemExit(
            f"Refusing to use {path} for {what}: it is inside a source checkout, and these files "
            "hold user data. Choose a location outside the repository."
        )
    return path


def output_dir_from_argv(argv=None, *, description: str) -> Path:
    """Parse ``--output-dir`` (required, outside the repository) and create it."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--output-dir", required=True,
        help="Directory for the dumps. Required, and outside the repository: they contain user data.",
    )
    args = parser.parse_args(argv)
    out = external_path(args.output_dir, what="--output-dir")
    out.mkdir(parents=True, exist_ok=True)
    return out
