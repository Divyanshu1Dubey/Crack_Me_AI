"""
Management command: seed_blogs

Imports the static blog posts (frontend/src/content/blog, exported to
blog_engine/seed_data/static_posts.json) into BlogPost. The database is the
source of truth of the public /blog pages; admins edit it at /admin/blog.

    python manage.py seed_blogs                    # every deploy (release.sh, build.sh)
    python manage.py seed_blogs --dry-run          # report what would change, write nothing
    python manage.py seed_blogs --update           # also overwrite posts edited in the admin
    python manage.py seed_blogs --restore          # also re-create posts deleted or renamed in the admin
    python manage.py seed_blogs --slug a --slug b  # only these slugs (with any of the above)
    python manage.py seed_blogs --clear            # delete every post and the import log first

Without flags, for each static post:

* no row, never imported               -> created, published (a placeholder body never is);
* no row, imported before              -> skipped: it was deleted or renamed in the admin;
* the row already equals the static post -> unchanged;
* the row was not edited since seed_blogs wrote it (BlogSeedImport.content_hash),
  or it is a row of the previous seed that nobody edited (a placeholder body, or
  a match in seed_data/legacy_fingerprints.json) -> updated to the static post;
* otherwise it was edited in the admin  -> kept as it is (``--update`` overwrites it).

An update keeps the publish state, except that a stub (placeholder body) is
published once it has the article. The previous seed also wrote one-paragraph
summaries under 24 slugs the public blog never used (the full posts have other
slugs); such a row is unpublished once, while untouched (an admin may publish
it again). Nothing is deleted, except with ``--clear``. Every write runs in
one transaction. Removing or renaming a static post file never touches the
database: delete or rename the post at /admin/blog as well.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from blog_engine.models import BlogPost, BlogSeedImport
from blog_engine.seeding import (
    SeedDataError,
    content_hash,
    field_defaults,
    is_placeholder_body,
    legacy_fingerprint,
    load_legacy_fingerprints,
    load_static_posts,
    row_values,
    seed_values,
)
from blog_engine.text_stats import count_words

# Module attributes so tests can patch the seed data.
try:
    BLOG_POSTS = load_static_posts()
    LEGACY_FINGERPRINTS = load_legacy_fingerprints()
    _LOAD_ERROR = None
except SeedDataError as exc:  # reported when the command runs
    BLOG_POSTS, LEGACY_FINGERPRINTS, _LOAD_ERROR = [], {}, exc

MESSAGES = {
    "create": "create {slug}",
    "restore": "re-create {slug} (deleted or renamed in the admin; --restore)",
    "update": "update {slug} (not edited since it was imported)",
    "fill": "update {slug} (a stub or an untouched row of the previous seed)",
    "overwrite": "overwrite {slug} (edited in the admin; --update)",
    "keep": "keep {slug}: edited in the admin (--update overwrites it)",
    "skip": "skip {slug}: deleted or renamed in the admin (--restore re-creates it)",
    "unpublish": "unpublish {slug}: untouched row of the previous seed under a slug the public blog never had",
    "keep-legacy": "keep {slug}: row of the previous seed, edited in the admin (left as it is)",
}
SUMMARY = (
    ("created", ("create", "restore")),
    ("updated", ("update", "fill", "overwrite")),
    ("unchanged", ("unchanged",)),
    ("kept (edited in the admin)", ("keep", "keep-legacy")),
    ("skipped (deleted or renamed in the admin)", ("skip",)),
    ("unpublished", ("unpublish",)),
)


@dataclass
class Step:
    kind: str
    slug: str
    row: BlogPost | None = None
    values: dict = field(default_factory=dict)
    hash: str = ""
    publish: bool = True
    imported: BlogSeedImport | None = None


def plan(records, rows, imports, legacy, *, update=False, restore=False, only=frozenset()):
    """The steps one run takes. ``rows`` / ``imports``: slug -> BlogPost / BlogSeedImport."""
    defaults = field_defaults()
    steps = []
    static_slugs = {record["slug"] for record in records}
    # Oldest first: posts created in one run then list newest first on the
    # site, in the order of the snapshot (BlogPost.Meta.ordering).
    for record in reversed(records):
        slug = record["slug"]
        if only and slug not in only:
            continue
        values = seed_values(record, defaults)
        new_hash = content_hash(values)
        row, imported = rows.get(slug), imports.get(slug)
        if row is None:
            if imported is None:
                steps.append(Step("create", slug, values=values, hash=new_hash,
                                  publish=not is_placeholder_body(values["body"])))
            elif restore:
                steps.append(Step("restore", slug, values=values, hash=new_hash, imported=imported,
                                  publish=not is_placeholder_body(values["body"])))
            else:
                steps.append(Step("skip", slug))
            continue
        current = row_values(row)
        current_hash = content_hash(current)
        if current_hash == new_hash:
            steps.append(Step("unchanged", slug, row=row, hash=new_hash, imported=imported))
            continue
        if imported is not None:
            untouched = bool(imported.content_hash) and current_hash == imported.content_hash
            kind = "update"
        else:
            untouched = is_placeholder_body(row.body) or legacy.get(slug) == legacy_fingerprint(current)
            kind = "fill"
        if untouched or update:
            # A stub becomes published once it has the article; otherwise the
            # publish state is the admin's.
            publish = row.is_published or (is_placeholder_body(row.body) and not is_placeholder_body(values["body"]))
            steps.append(Step(kind if untouched else "overwrite", slug, row=row, values=values,
                              hash=new_hash, publish=publish, imported=imported))
        else:
            steps.append(Step("keep", slug, row=row, imported=imported))
    for slug, fingerprint in sorted(legacy.items()):
        if slug in static_slugs or (only and slug not in only):
            continue
        row = rows.get(slug)
        # Handled once: an admin may publish the row again afterwards.
        if row is None or not row.is_published or slug in imports:
            continue
        if is_placeholder_body(row.body) or legacy_fingerprint(row_values(row)) == fingerprint:
            steps.append(Step("unpublish", slug, row=row))
        else:
            steps.append(Step("keep-legacy", slug, row=row))
    return steps


def record_import(step, content_hash_value):
    BlogSeedImport.objects.update_or_create(slug=step.slug, defaults={"content_hash": content_hash_value})


def apply(steps):
    now = timezone.now()
    for step in steps:
        if step.kind in ("create", "restore"):
            BlogPost.objects.create(slug=step.slug, is_published=step.publish, **step.values)
            record_import(step, step.hash)
        elif step.kind in ("update", "fill", "overwrite"):
            # .update() bypasses BlogPost.save(), which counts the body otherwise.
            BlogPost.objects.filter(pk=step.row.pk).update(
                is_published=step.publish, updated=now, body_word_count=count_words(step.values["body"]),
                **step.values)
            record_import(step, step.hash)
        elif step.kind == "unchanged":
            if step.imported is None or step.imported.content_hash != step.hash:
                record_import(step, step.hash)
        elif step.kind == "keep":
            if step.imported is None:
                record_import(step, "")  # imported, but the content is the admin's
        elif step.kind == "unpublish":
            BlogPost.objects.filter(pk=step.row.pk).update(is_published=False, updated=now)
            record_import(step, "")  # handled; a later deploy leaves the row to the admin


class Command(BaseCommand):
    help = "Import the static blog posts into the database without overwriting admin edits."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change; write nothing")
        parser.add_argument("--update", action="store_true",
                            help="Also overwrite posts edited in the admin with the static post")
        parser.add_argument("--restore", action="store_true",
                            help="Also re-create static posts that were deleted or renamed in the admin")
        parser.add_argument("--slug", action="append", default=[], metavar="SLUG",
                            help="Only this slug (repeatable)")
        parser.add_argument("--clear", action="store_true",
                            help="Delete every blog post and the import log first (full reset)")

    def handle(self, *args, **options):
        if _LOAD_ERROR is not None:
            raise CommandError(str(_LOAD_ERROR))
        dry_run = options["dry_run"]
        only = frozenset(options["slug"])
        records = BLOG_POSTS
        legacy = LEGACY_FINGERPRINTS
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: nothing is written."))
        for slug in sorted(only - {r["slug"] for r in records} - set(legacy)):
            self.stdout.write(self.style.WARNING(f"No static post has the slug {slug!r}."))

        import_table = BlogSeedImport._meta.db_table in connection.introspection.table_names()
        if not import_table and not dry_run:
            raise CommandError("The blog_engine 0003 migration is not applied: run `manage.py migrate` first.")
        if not import_table:
            self.stdout.write(self.style.WARNING(
                "The blog_engine 0003 migration is not applied; reporting as if nothing was imported yet."))

        with transaction.atomic():
            if options["clear"]:
                posts, logged = BlogPost.objects.count(), BlogSeedImport.objects.count() if import_table else 0
                if dry_run:
                    self.stdout.write(f"Would delete {posts} posts and {logged} import records first.")
                else:
                    BlogPost.objects.all().delete()
                    BlogSeedImport.objects.all().delete()
                    self.stdout.write(self.style.WARNING(f"Deleted {posts} posts and {logged} import records."))
            clear_now = options["clear"]
            rows = {} if clear_now else {post.slug: post for post in BlogPost.objects.all()}
            imports = {} if (clear_now or not import_table) else {
                item.slug: item for item in BlogSeedImport.objects.all()}
            steps = plan(records, rows, imports, legacy, update=options["update"],
                         restore=options["restore"], only=only)
            if not dry_run:
                apply(steps)

        if options["verbosity"] >= 1:
            for step in steps:
                if step.kind in MESSAGES:
                    line = MESSAGES[step.kind].format(slug=step.slug)
                    self.stdout.write(f"  [DRY-RUN] {line}" if dry_run else f"  {line}")
        counts = ", ".join(f"{label}: {sum(1 for s in steps if s.kind in kinds)}" for label, kinds in SUMMARY)
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nDry-run summary ({len(records)} static posts). Would be {counts}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nDone ({len(records)} static posts). {counts}."))
