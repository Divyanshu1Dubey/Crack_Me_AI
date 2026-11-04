"""Blog post serializers.

BlogPostSerializer is what /admin/blog writes and what a post page reads
(every field). Writes are validated so a post saved in the admin cannot break
the public page: list items have the shape the page renders, links are
internal paths or http(s) URLs (never javascript:), dates are ISO dates, and a
post is published only with a real body. Every static post passes this
validation unchanged (tests_blog_api), so a seeded post can be saved as is.
"""
from __future__ import annotations

import re
from datetime import date

from rest_framework import serializers

from .models import BlogPost
from .seeding import is_placeholder_body

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ANCHOR_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# Paths under /blog/ that are other pages, not posts.
RESERVED_SLUGS = frozenset({"category", "tag", "author", "feed", "feed-xml", "og", "page", "opengraph-image"})
MAX_ITEMS = 200
MAX_TAGS = 40
MAX_TAG_LENGTH = 80

PUBLISH_NEEDS_BODY = "Add the article body before publishing this post."


def is_safe_link(value: str) -> bool:
    """An internal path (not protocol-relative) or an http(s) URL."""
    if value.startswith("/"):
        return not value.startswith("//") and not any(c.isspace() for c in value)
    return bool(re.fullmatch(r"https?://[^\s/]+[^\s]*", value, flags=re.IGNORECASE))


def _is_iso_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _text(item: dict, key: str, label: str, index: int, *, required: bool = True) -> str:
    value = item.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise serializers.ValidationError(f"Item {index + 1}: {label} must be text.")
    value = value.strip()
    if required and not value:
        raise serializers.ValidationError(f"Item {index + 1}: {label} is empty.")
    return value


def _items(value, allowed: set[str]) -> list[dict]:
    if not isinstance(value, list):
        raise serializers.ValidationError("Must be a list.")
    if len(value) > MAX_ITEMS:
        raise serializers.ValidationError(f"At most {MAX_ITEMS} items.")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise serializers.ValidationError(f"Item {index + 1} must be an object.")
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise serializers.ValidationError(f"Item {index + 1}: unknown field(s) {', '.join(unknown)}.")
    return value


class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = [
            "id",
            "slug",
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
            "is_published",
            "created_at",
            "updated",
        ]
        read_only_fields = ["id", "created_at", "updated"]
        # A draft may be saved before its body is written; validate() keeps a
        # post without one from being published.
        extra_kwargs = {"body": {"allow_blank": True}}

    # ── plain fields ────────────────────────────────────────────────────

    def validate_slug(self, value):
        value = value.strip()
        if not SLUG_RE.fullmatch(value):
            raise serializers.ValidationError(
                "Use lowercase letters, numbers and single hyphens, e.g. upsc-cms-revision-plan.")
        if value in RESERVED_SLUGS:
            raise serializers.ValidationError(f"/blog/{value} is another page; choose another slug.")
        return value

    def validate_date_published(self, value):
        if not _is_iso_date(value.strip()):
            raise serializers.ValidationError("Use a date like 2026-11-04.")
        return value.strip()

    def _optional_date(self, value):
        value = (value or "").strip()
        if value and not _is_iso_date(value):
            raise serializers.ValidationError("Use a date like 2026-11-04, or leave it empty.")
        return value

    def validate_date_modified(self, value):
        return self._optional_date(value)

    def validate_updated_at(self, value):
        return self._optional_date(value)

    def validate_author_id(self, value):
        value = value.strip()
        if not SLUG_RE.fullmatch(value):
            raise serializers.ValidationError("Use an author profile slug, e.g. crackcms-editorial.")
        return value

    def validate_reviewed_by(self, value):
        value = (value or "").strip()
        if value and not SLUG_RE.fullmatch(value):
            raise serializers.ValidationError("Use a profile slug, e.g. crackcms-editorial, or leave it empty.")
        return value

    def validate_cover_image(self, value):
        value = (value or "").strip()
        if value and not is_safe_link(value):
            raise serializers.ValidationError("Use a path such as /blog/cover.png or an https:// URL.")
        return value

    def validate_reading_time(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give a reading time, e.g. 8 min.")
        return value

    def validate_word_count(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Must be zero or more.")
        return value

    # ── structured fields (JSON) ────────────────────────────────────────

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of tags.")
        tags, seen = [], set()
        for index, tag in enumerate(value):
            if not isinstance(tag, str):
                raise serializers.ValidationError(f"Tag {index + 1} must be text.")
            tag = tag.strip()
            if not tag or tag.lower() in seen:
                continue
            if len(tag) > MAX_TAG_LENGTH:
                raise serializers.ValidationError(f"Tag {index + 1} is longer than {MAX_TAG_LENGTH} characters.")
            seen.add(tag.lower())
            tags.append(tag)
        if len(tags) > MAX_TAGS:
            raise serializers.ValidationError(f"At most {MAX_TAGS} tags.")
        return tags

    def validate_related_exam_paths(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of paths.")
        paths = []
        for index, path in enumerate(value):
            if not isinstance(path, str) or not path.strip():
                raise serializers.ValidationError(f"Path {index + 1} is empty.")
            path = path.strip()
            if not (path.startswith("/") and is_safe_link(path)):
                raise serializers.ValidationError(f"Path {index + 1} must be a site path such as /cms.")
            paths.append(path)
        return paths

    def validate_primary_cta(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object with a label and a link.")
        data = dict(value)
        # The frontend type spells these eventName / eventParams; store one spelling.
        for camel, snake in (("eventName", "event_name"), ("eventParams", "event_params")):
            if camel in data:
                data.setdefault(snake, data.pop(camel))
        unknown = sorted(set(data) - {"label", "href", "event_name", "event_params"})
        if unknown:
            raise serializers.ValidationError(f"Unknown field(s) {', '.join(unknown)}.")
        label = data.get("label") or ""
        href = data.get("href") or ""
        if not isinstance(label, str) or not isinstance(href, str):
            raise serializers.ValidationError("The label and the link must be text.")
        label, href = label.strip(), href.strip()
        if not label and not href and not data.get("event_name") and not data.get("event_params"):
            return {}
        if not label or not href:
            raise serializers.ValidationError("Give both a button label and a link (or neither).")
        if not is_safe_link(href):
            raise serializers.ValidationError("The link must be a site path such as /questions or an https:// URL.")
        cta = {"label": label, "href": href}
        event_name = data.get("event_name") or ""
        if event_name:
            if not isinstance(event_name, str) or not EVENT_NAME_RE.fullmatch(event_name.strip()):
                raise serializers.ValidationError("The event name uses lowercase letters, digits and _.")
            cta["event_name"] = event_name.strip()
        params = data.get("event_params")
        if params not in (None, {}, ""):
            if not isinstance(params, dict) or not all(
                    isinstance(k, str) and isinstance(v, (str, int, float, bool)) for k, v in params.items()):
                raise serializers.ValidationError("Event parameters must map names to text, numbers or true/false.")
            cta["event_params"] = params
        return cta

    def validate_faqs(self, value):
        return [{"q": _text(item, "q", "the question", i), "a": _text(item, "a", "the answer", i)}
                for i, item in enumerate(_items(value, {"q", "a"}))]

    def validate_toc(self, value):
        toc = []
        for i, item in enumerate(_items(value, {"id", "label"})):
            anchor = _text(item, "id", "the anchor id", i)
            if not ANCHOR_RE.fullmatch(anchor):
                raise serializers.ValidationError(f"Item {i + 1}: the anchor id uses lowercase letters, digits and hyphens.")
            toc.append({"id": anchor, "label": _text(item, "label", "the label", i)})
        return toc

    def validate_references(self, value):
        references = []
        for i, item in enumerate(_items(value, {"label", "url", "published"})):
            reference = {"label": _text(item, "label", "the label", i)}
            url = _text(item, "url", "the link", i, required=False)
            if url:
                if not re.fullmatch(r"https?://\S+", url, flags=re.IGNORECASE):
                    raise serializers.ValidationError(f"Item {i + 1}: the link must start with https:// or http://.")
                reference["url"] = url
            published = _text(item, "published", "the publication date", i, required=False)
            if published:
                reference["published"] = published
            references.append(reference)
        return references

    def validate_revision_log(self, value):
        log = []
        for i, item in enumerate(_items(value, {"date", "note"})):
            day = _text(item, "date", "the date", i)
            if not _is_iso_date(day):
                raise serializers.ValidationError(f"Item {i + 1}: use a date like 2026-11-04.")
            log.append({"date": day, "note": _text(item, "note", "the note", i)})
        return log

    # ── whole post ──────────────────────────────────────────────────────

    def validate(self, attrs):
        instance = self.instance
        published = attrs.get("is_published", instance.is_published if instance else True)
        body = attrs.get("body", instance.body if instance else "")
        if published and is_placeholder_body(body):
            raise serializers.ValidationError({"is_published": PUBLISH_NEEDS_BODY})
        return attrs


class BlogPostListSerializer(serializers.ModelSerializer):
    """Summary of a post: admin list rows and the public catalog (no body or lists)."""

    is_stub = serializers.SerializerMethodField(
        help_text="The body is empty or the old seed placeholder: never shown publicly.")

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "slug",
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
            "pinned",
            "trending",
            "is_published",
            "is_stub",
            "created_at",
            "updated",
        ]
        read_only_fields = fields

    def get_is_stub(self, obj) -> bool:
        return is_placeholder_body(obj.body)
