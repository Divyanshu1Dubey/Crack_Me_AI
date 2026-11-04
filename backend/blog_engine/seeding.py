"""Seed data and change detection for ``manage.py seed_blogs``.

``seed_data/static_posts.json``
    The static blog posts (frontend/src/content/blog) as BlogPost field
    values, newest first. Generated, never edited by hand:
    frontend/tests/unit/blog-seed-snapshot.test.ts checks it against the
    static modules and rewrites it with ``UPDATE_BLOG_SEED=1``.

``seed_data/legacy_fingerprints.json``
    A fingerprint (``legacy_fingerprint``) of each row the previous version
    of seed_blogs wrote. That version carried a hard-coded copy of 125 posts
    whose bodies were the placeholder "Full article content here." or a
    one-paragraph summary, 24 of them under slugs the public blog never used.
    A row that still matches its fingerprint was never edited, so seed_blogs
    may replace it with the full static post (or unpublish it, for the 24).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"
STATIC_POSTS_FILE = SEED_DATA_DIR / "static_posts.json"
LEGACY_FINGERPRINTS_FILE = SEED_DATA_DIR / "legacy_fingerprints.json"

# The BlogPost fields that make up a post's content: what seed_blogs writes
# and compares. The publish state, id and timestamps are not content.
CONTENT_FIELDS = (
    "title",
    "description",
    "excerpt",
    "cover_image",
    "category",
    "subcategory",
    "tags",
    "difficulty",
    "author_id",
    "reviewed_by",
    "author",
    "author_role",
    "date_published",
    "date_modified",
    "updated_at",
    "reading_time",
    "word_count",
    "primary_cta",
    "related_exam_paths",
    "faqs",
    "toc",
    "references",
    "revision_log",
    "body",
    "prelude",
    "outro",
    "pinned",
    "trending",
)

# Fields that changed under rows the old seed wrote although nobody edited
# them: the cover (older seed runs kept the unshipped /blog/og/ paths) and the
# byline (migration 0002 credited the editorial team). The legacy fingerprint
# leaves them out.
LEGACY_IGNORED_FIELDS = frozenset({"cover_image", "author_id", "reviewed_by", "author", "author_role"})
LEGACY_FIELDS = tuple(f for f in CONTENT_FIELDS if f not in LEGACY_IGNORED_FIELDS)

# Required in every static record (the model has no default for them).
REQUIRED_FIELDS = ("slug", "title", "description", "excerpt", "category", "author", "author_role",
                   "date_published", "body")

# Stub bodies the old seed wrote instead of an article. Such a post is never
# shown publicly and never published by seed_blogs.
PLACEHOLDER_BODIES = frozenset({"", "full article content here."})

# Cover folders the static posts point at that frontend/public does not ship
# (the social image is generated: app/blog/[slug]/opengraph-image.tsx).
UNSHIPPED_COVER_PREFIXES = ("/blog/og/", "/blog/obg/")


class SeedDataError(ValueError):
    """The seed snapshot is missing or malformed."""


def is_placeholder_body(body) -> bool:
    """True for an empty body or the stub text the old seed wrote."""
    return (body or "").strip().lower() in PLACEHOLDER_BODIES


def field_defaults() -> dict:
    """The model default of every content field (what a missing key becomes on create)."""
    from blog_engine.models import BlogPost

    return {name: BlogPost._meta.get_field(name).get_default() for name in CONTENT_FIELDS}


def seed_values(record: dict, defaults: dict) -> dict:
    """The content seed_blogs writes for one static post: every content field,
    missing keys at the model default, an unshipped cover path left empty."""
    values = {name: copy.deepcopy(record[name] if name in record else defaults[name])
              for name in CONTENT_FIELDS}
    if str(values.get("cover_image") or "").startswith(UNSHIPPED_COVER_PREFIXES):
        values["cover_image"] = ""
    return values


def row_values(post) -> dict:
    """The current content of a BlogPost row."""
    return {name: getattr(post, name) for name in CONTENT_FIELDS}


def content_hash(values: dict, fields=CONTENT_FIELDS) -> str:
    """SHA-256 of the given fields as canonical JSON (key order and JSON
    object order do not matter; a row reads back equal to what was written)."""
    payload = json.dumps({name: values.get(name) for name in fields}, sort_keys=True,
                         ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def legacy_fingerprint(values: dict) -> str:
    """content_hash over the fields the old seed's rows still hold unchanged."""
    return content_hash(values, LEGACY_FIELDS)


def load_static_posts(path=STATIC_POSTS_FILE) -> list[dict]:
    """The static post records, newest first. Raises SeedDataError when malformed."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SeedDataError(f"cannot read the blog seed snapshot {path}: {exc}") from exc
    posts = data.get("posts") if isinstance(data, dict) else data
    if not isinstance(posts, list):
        raise SeedDataError(f"{path}: no 'posts' list")
    known = set(CONTENT_FIELDS) | {"slug"}
    seen = set()
    for index, record in enumerate(posts):
        if not isinstance(record, dict):
            raise SeedDataError(f"{path}: post #{index} is not an object")
        missing = [name for name in REQUIRED_FIELDS if not isinstance(record.get(name), str)]
        unknown = sorted(set(record) - known)
        if missing or unknown:
            raise SeedDataError(f"{path}: post #{index} ({record.get('slug')!r}): "
                                f"missing {missing}, unknown {unknown}")
        if record["slug"] in seen:
            raise SeedDataError(f"{path}: duplicate slug {record['slug']!r}")
        seen.add(record["slug"])
    return posts


def load_legacy_fingerprints(path=LEGACY_FINGERPRINTS_FILE) -> dict:
    """slug -> legacy fingerprint of the rows the old seed wrote."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SeedDataError(f"cannot read {path}: {exc}") from exc
    fingerprints = data.get("fingerprints") if isinstance(data, dict) else None
    if not isinstance(fingerprints, dict):
        raise SeedDataError(f"{path}: no 'fingerprints' object")
    return {str(slug): str(value) for slug, value in fingerprints.items()}
