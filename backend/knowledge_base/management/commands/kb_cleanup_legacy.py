"""
python manage.py kb_cleanup_legacy [--apply]

One-off clean-up of knowledge-base rows written before the 2026-11 fixes.
Ingestion no longer creates either kind, but nothing removed the old ones:

1. User-upload chunks stored under the ``internal-notes`` source (the old
   UserUploadsConnector borrowed it), so they carry licence ``internal`` and
   were auto-approved as CrackLabs-authored content. They move to the
   ``user-uploads`` source with licence ``user_attested`` and its
   attribution; an *auto*-approval becomes ``pending`` (an admin's approve /
   reject decision is kept). A chunk whose text already exists under
   ``user-uploads`` is deactivated instead (one row per source + text).
2. KnowledgeEmbedding rows written by the hash pseudo-embedding (the old
   fallback when no model loaded) under real model names. They are deleted,
   so the indexer re-embeds those chunks once a real model is available
   instead of comparing query vectors with noise. Hash vectors are
   recognised by their signature: the SHA-256 seed repeats every 32
   components, which a real embedding never does.

Dry run by default (reports counts only); ``--apply`` writes.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge_base.models import KnowledgeChunk, KnowledgeEmbedding, KnowledgeSource

LEGACY_SOURCE_SLUG = "internal-notes"
UPLOAD_LOCATOR_PREFIX = "user_uploads/"
# _hash_embed: vec[i] = seed[i % 32] (normalised), seed = sha256(text).
HASH_PERIOD = 32
HASH_TOLERANCE = 1e-9


def is_hash_embedding(vector) -> bool:
    """True for a vector produced by ``EmbeddingService._hash_embed``."""
    if not isinstance(vector, (list, tuple)) or len(vector) < 2 * HASH_PERIOD:
        return False
    try:
        values = [float(v) for v in vector]
    except (TypeError, ValueError):
        return False
    if all(abs(v) <= HASH_TOLERANCE for v in values):
        return False  # an all-zero vector is not a hash vector (nor useful)
    return all(
        abs(values[i] - values[i % HASH_PERIOD]) <= HASH_TOLERANCE
        for i in range(HASH_PERIOD, len(values))
    )


class Command(BaseCommand):
    help = ("Relabel user-upload chunks stored as internal notes and delete hash "
            "pseudo-embeddings (dry run unless --apply).")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes (default: report only).")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        moved, deactivated = self._relabel_upload_chunks(apply)
        deleted = self._delete_hash_embeddings(apply)
        verb = "Applied" if apply else "Dry run (use --apply to write)"
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: {moved} user-upload chunk(s) moved to 'user-uploads', "
            f"{deactivated} duplicate(s) deactivated, "
            f"{deleted} hash embedding(s) deleted."
        ))
        return None

    # ─── 1. User uploads stored as internal notes ─────────────────────

    def _relabel_upload_chunks(self, apply: bool) -> tuple[int, int]:
        legacy = KnowledgeChunk.objects.filter(
            source__slug=LEGACY_SOURCE_SLUG,
            locator__startswith=UPLOAD_LOCATOR_PREFIX,
        ).order_by("id")
        if not apply:
            target = KnowledgeSource.objects.filter(slug="user-uploads").first()
            moved = deactivated = 0
            for chunk in legacy.only("id", "text_hash"):
                if target and KnowledgeChunk.objects.filter(source=target, text_hash=chunk.text_hash).exists():
                    deactivated += 1
                else:
                    moved += 1
            return moved, deactivated

        from knowledge_base.connectors.user_uploads import UserUploadsConnector
        target = UserUploadsConnector().source  # get_or_create, licence user_attested
        moved = deactivated = 0
        with transaction.atomic():
            for chunk in legacy.select_for_update():
                if KnowledgeChunk.objects.filter(source=target, text_hash=chunk.text_hash).exists():
                    chunk.is_active = False
                    chunk.save(update_fields=["is_active", "updated_at"])
                    deactivated += 1
                    continue
                chunk.source = target
                chunk.license = target.license
                chunk.attribution = target.attribution
                fields = ["source", "license", "attribution", "updated_at"]
                if chunk.approval_state == KnowledgeChunk.APPROVAL_AUTO:
                    chunk.approval_state = KnowledgeChunk.APPROVAL_PENDING
                    chunk.approved_at = None
                    fields += ["approval_state", "approved_at"]
                chunk.save(update_fields=fields)
                moved += 1
            if moved or deactivated:
                for source in KnowledgeSource.objects.filter(slug__in=[LEGACY_SOURCE_SLUG, target.slug]):
                    source.chunk_count = KnowledgeChunk.objects.filter(source=source, is_active=True).count()
                    source.save(update_fields=["chunk_count", "updated_at"])
        return moved, deactivated

    # ─── 2. Hash pseudo-embeddings ────────────────────────────────────

    def _delete_hash_embeddings(self, apply: bool) -> int:
        hash_ids = [
            row.id
            for row in KnowledgeEmbedding.objects.only("id", "vector").iterator(chunk_size=500)
            if is_hash_embedding(row.vector)
        ]
        if apply and hash_ids:
            for start in range(0, len(hash_ids), 500):
                KnowledgeEmbedding.objects.filter(id__in=hash_ids[start:start + 500]).delete()
        return len(hash_ids)
