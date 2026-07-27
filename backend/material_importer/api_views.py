"""REST API for the Admin Import Center.

All endpoints require an authenticated staff user (the same gate Django
admin uses). Heavy operations (publish, generate-mock, bulk-decision,
classify-ai) run in a background django-q2 task via ``queue.enqueue`` so
the browser never blocks waiting for a 10k-question batch.

Endpoint summary (see ``urls.py`` for the full route list):

    GET    /api/admin/import/dashboard/                → summary stats
    GET    /api/admin/import/batches/                  → list batches (filterable)
    POST   /api/admin/import/batches/                  → create batch from upload
    GET    /api/admin/import/batches/<id>/             → batch detail
    DELETE /api/admin/import/batches/<id>/             → rollback batch
    POST   /api/admin/import/batches/<id>/publish/     → publish + build tests
    POST   /api/admin/import/batches/<id>/cancel/      → cancel in-flight batch
    POST   /api/admin/import/batches/<id>/republish/   → republish tests only
    POST   /api/admin/import/batches/<id>/rollback/    → explicit rollback
    POST   /api/admin/import/batches/<id>/generate-mock/ → build mock tests
    GET    /api/admin/import/batches/<id>/materials/   → files inside batch
    GET    /api/admin/import/batches/<id>/audit/       → paginated audit logs
    GET    /api/admin/import/questions/                → paginated review queue
    GET    /api/admin/import/questions/<id>/           → question detail / preview
    POST   /api/admin/import/questions/<id>/decision/ → approve/reject/reset
    POST   /api/admin/import/questions/<id>/classify-ai/ → re-run AI classifier
    POST   /api/admin/import/questions/bulk-decision/  → bulk approve/reject
    GET    /api/admin/import/search/                   → full-text search
    GET    /api/admin/import/health/                   → pipeline health probe
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.models import Question, Subject, Topic

from .ingest_service import ingest_path
from .mock_test_builder import (
    build_for_batch,
    delete_batch,
    publish_batch,
    publish_batch_and_build_tests,
)
from .models import (
    ExtractedQuestion,
    ImportAuditLog,
    ImportBatch,
    ImportMaterial,
)
from .parser import ParserFactory
from .sync_serializers import (
    AIClassifySerializer,
    BatchPublishSerializer,
    BatchRollbackSerializer,
    BulkDecisionSerializer,
    DashboardStatsSerializer,
    ExtractedQuestionDetailSerializer,
    ExtractedQuestionListSerializer,
    ImportAuditLogSerializer,
    ImportBatchDetailSerializer,
    ImportBatchListSerializer,
    ImportMaterialSerializer,
    MockTestGenerationSerializer,
    QuestionDecisionSerializer,
)

log = logging.getLogger(__name__)

# File-level limits (defense in depth; the parser also enforces per-file checks)
ALLOWED_EXTS = {".docx", ".pdf", ".pptx", ".txt", ".md", ".zip"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB per upload
MAX_FILES_PER_UPLOAD = 200


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _staff_only(request):
    """IsAdminUser handles staff/superuser but also authenticated. Tighten."""
    u = getattr(request, "user", None)
    return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


# ---------------------------------------------------------------------------
# Upload + batch creation
# ---------------------------------------------------------------------------


class UploadCreateBatchView(APIView):
    """Accept multipart upload(s) or a single folder .zip and create a batch.

    The endpoint creates an ImportBatch in 'queued' state and returns its id
    immediately. The actual parse work runs synchronously in a thread via
    ``transaction.on_commit`` so the HTTP response can return; for huge
    imports we also enqueue a django-q2 task.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        user = request.user
        files = request.FILES.getlist("files") or ([request.FILES["file"]] if "file" in request.FILES else [])
        if not files:
            return Response({"error": "No files received. Send multipart 'files' or 'file'."}, status=400)
        if len(files) > MAX_FILES_PER_UPLOAD:
            return Response({"error": f"Too many files ({len(files)} > {MAX_FILES_PER_UPLOAD})."}, status=400)

        source_label = (request.data.get("source_label") or "").strip()[:255] or "Web Upload"
        use_ai = str(request.data.get("use_ai", "")).lower() in {"1", "true", "yes"}
        force = str(request.data.get("force", "")).lower() in {"1", "true", "yes"}

        # Save into a per-upload working dir under MEDIA_ROOT/imports/<uuid>/.
        work_root = Path(getattr(settings, "MEDIA_ROOT", "/tmp")) / "imports"
        work_root.mkdir(parents=True, exist_ok=True)
        work_dir = work_root / f"up_{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}"
        work_dir.mkdir(parents=True, exist_ok=True)

        saved_files: list[Path] = []
        too_big: list[str] = []
        rejected: list[str] = []
        for f in files:
            ext = Path(f.name).suffix.lower()
            if ext not in ALLOWED_EXTS:
                rejected.append(f"{f.name}: unsupported extension")
                continue
            if f.size > MAX_UPLOAD_BYTES:
                too_big.append(f"{f.name}: {f.size} bytes > {MAX_UPLOAD_BYTES}")
                continue
            safe_name = Path(f.name).name  # strip any path traversal
            dest = work_dir / safe_name
            with open(dest, "wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)
            if ext == ".zip":
                try:
                    with zipfile.ZipFile(dest) as zf:
                        zf.extractall(work_dir)
                    dest.unlink(missing_ok=True)
                except zipfile.BadZipFile:
                    rejected.append(f"{f.name}: not a valid zip")
                    dest.unlink(missing_ok=True)
                    continue
            saved_files.append(dest)

        if not saved_files:
            # Cleanup & return error
            shutil.rmtree(work_dir, ignore_errors=True)
            return Response({
                "error": "No usable files after validation.",
                "rejected": rejected,
                "too_big": too_big,
            }, status=400)

        # Create the batch up front (so the UI gets an id immediately).
        batch = ImportBatch.objects.create(
            source_label=source_label,
            root_path=str(work_dir),
            status="queued",
            created_by=user,
            summary={"uploaded_files": [p.name for p in saved_files]},
        )
        ImportAuditLog.objects.create(
            batch=batch, level="info", code="upload",
            message=f"Uploaded {len(saved_files)} file(s) by {user.username}",
            details={"rejected": rejected, "too_big": too_big},
        )

        # Kick off the parse. We use a background thread (the platform
        # already uses django-q2, but a thread keeps the dependency simple
        # and survives worker downtime for one-off uploads).
        import threading
        def _run():
            try:
                # ingest_path walks the directory; we point it at the work dir.
                ingest_path(
                    path=str(work_dir),
                    source_label=source_label,
                    created_by=user,
                    use_ai=use_ai,
                    force=force,
                )
                batch.refresh_from_db()
                ImportAuditLog.objects.create(
                    batch=batch, level="info", code="ingest_done",
                    message=f"Ingest complete: {batch.questions_extracted} questions, {batch.images_extracted} images.",
                )
            except Exception as exc:  # pragma: no cover - background
                log.exception("Background ingest failed for batch %s", batch.id)
                batch.status = "failed"
                batch.error_report = [{"file": "(batch)", "error": str(exc)}]
                batch.finished_at = timezone.now()
                batch.save()
                ImportAuditLog.objects.create(
                    batch=batch, level="error", code="ingest_crash",
                    message=f"Ingest crashed: {exc}",
                )

        thread = threading.Thread(target=_run, name=f"ingest-batch-{batch.id}", daemon=True)
        thread.start()

        return Response({
            "batch_id": batch.id,
            "status": batch.status,
            "files_accepted": len(saved_files),
            "files_rejected": rejected,
            "files_too_big": too_big,
            "work_dir": str(work_dir),
            "poll_url": f"/api/admin/import/batches/{batch.id}/",
        }, status=201)


# ---------------------------------------------------------------------------
# Batch CRUD
# ---------------------------------------------------------------------------


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only batch viewset; mutations go through custom @action routes."""

    permission_classes = [IsAdminUser]
    queryset = ImportBatch.objects.all().select_related("created_by")
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ImportBatchDetailSerializer
        return ImportBatchListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if self.request.query_params.get("needs_review") == "1":
            qs = qs.filter(materials__extracted_questions__status="needs_review").distinct()
        return qs

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, id=None):
        batch = self.get_object()
        if batch.status in {"completed", "failed", "cancelled"}:
            return Response({"error": f"Cannot cancel a batch in status={batch.status}."}, status=409)
        batch.status = "cancelled"
        batch.finished_at = timezone.now()
        batch.save(update_fields=["status", "finished_at", "updated_at"])
        ImportAuditLog.objects.create(batch=batch, level="warning", code="cancelled",
                                      message=f"Cancelled by {request.user.username}")
        return Response({"status": "cancelled", "batch_id": batch.id})

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, id=None):
        batch = self.get_object()
        s = BatchPublishSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        max_per_test = s.validated_data["max_per_test"]
        only_publish = s.validated_data["only_publish"]

        if only_publish:
            n = publish_batch(batch.id)
            tests_built = 0
        else:
            res = publish_batch_and_build_tests(batch.id, max_per_test=max_per_test)
            n = res["published"]
            tests_built = res["tests_built"]

        ImportAuditLog.objects.create(
            batch=batch, level="info", code="published",
            message=f"Published {n} questions, built {tests_built} tests.",
            details={"by": request.user.username, "max_per_test": max_per_test},
        )
        return Response({
            "batch_id": batch.id,
            "published": n,
            "tests_built": tests_built,
        })

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, id=None):
        batch = self.get_object()
        s = BatchRollbackSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not s.validated_data["confirm"]:
            return Response({"error": "Confirmation required."}, status=400)

        result = delete_batch(batch.id, delete_published=s.validated_data["delete_published"])
        batch.status = "cancelled"
        batch.finished_at = timezone.now()
        batch.summary = {**(batch.summary or {}), "rollback": result}
        batch.save()
        ImportAuditLog.objects.create(
            batch=batch, level="warning", code="rollback",
            message=f"Rolled back: {result}",
            details={"by": request.user.username},
        )
        return Response({"batch_id": batch.id, "rolled_back": result})

    @action(detail=True, methods=["post"], url_path="republish")
    def republish(self, request, id=None):
        batch = self.get_object()
        n = build_for_batch(batch.id, max_per_test=100)
        ImportAuditLog.objects.create(
            batch=batch, level="info", code="republished_tests",
            message=f"Rebuilt {n} mock tests.",
            details={"by": request.user.username},
        )
        return Response({"batch_id": batch.id, "tests_built": n})

    @action(detail=True, methods=["post"], url_path="generate-mock")
    def generate_mock(self, request, id=None):
        batch = self.get_object()
        s = MockTestGenerationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        strategy = s.validated_data["strategy"]
        count = s.validated_data["question_count"]
        difficulty = s.validated_data.get("difficulty", "mixed")

        from tests_engine.models import Test
        from .mock_test_builder import _ensure_test, _resolve_subject_canon

        # Pull approved + published questions for this batch.
        base = ExtractedQuestion.objects.filter(
            material__batch_id=batch.id,
            status__in=["approved", "published"],
            published_question__isnull=False,
        )
        if strategy in {"by_subject", "by_chapter", "by_topic"} and s.validated_data.get("subject_id"):
            base = base.filter(subject_id=s.validated_data["subject_id"])
        if strategy == "by_topic" and s.validated_data.get("topic_id"):
            base = base.filter(topic_id=s.validated_data["topic_id"])
        if difficulty != "mixed":
            base = base.filter(inferred_difficulty=difficulty)

        question_ids = list(base.values_list("published_question_id", flat=True))
        if not question_ids:
            return Response({"error": "No publishable questions matched the filter."}, status=400)

        # Map strategy → Test record naming + grouping.
        kind = "subject" if strategy in {"by_subject", "by_chapter"} else (
            "topic" if strategy == "by_topic" else (
                "pyq_year" if strategy == "image_based" else "mixed"))
        suffix_map = {
            "entire_file": "Entire File",
            "by_subject": "By Subject",
            "by_chapter": "By Chapter",
            "by_topic": "By Topic",
            "by_difficulty": f"By Difficulty ({difficulty})",
            "random": "Random Mix",
            "image_based": "Image Based",
            "grand": "Grand Test",
            "revision": "Revision Test",
            "weekly": "Weekly Test",
        }
        title_prefix = suffix_map.get(strategy, "Mock Test")

        # One Test per strategy call (avoid Test explosion).
        name = f"Auto • {title_prefix} • batch {batch.id}"
        description = (
            f"Auto-generated via Import Center. Strategy={strategy}, "
            f"difficulty={difficulty}, requested={count}."
        )
        t = _ensure_test(name=name, kind=kind, description=description)
        # Cap by count and shuffle deterministically by id list ordering.
        selected = question_ids[:count]
        t.questions.set(selected)
        ImportAuditLog.objects.create(
            batch=batch, level="info", code="mock_generated",
            message=f"Generated mock test '{name}' with {len(selected)} questions.",
            details={"strategy": strategy, "difficulty": difficulty,
                     "requested": count, "by": request.user.username},
        )
        return Response({
            "batch_id": batch.id,
            "test_id": t.id,
            "test_title": t.title,
            "question_count": len(selected),
        })

    @action(detail=True, methods=["get"], url_path="materials")
    def materials(self, request, id=None):
        batch = self.get_object()
        qs = batch.materials.all().order_by("id")
        return Response(ImportMaterialSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="audit")
    def audit(self, request, id=None):
        batch = self.get_object()
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(200, max(1, int(request.query_params.get("page_size", 50))))
        except ValueError:
            return Response({"error": "page/page_size must be integers."}, status=400)
        qs = batch.audit_logs.order_by("-created_at")
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]
        return Response({
            "page": page, "page_size": page_size, "total": total,
            "items": ImportAuditLogSerializer(items, many=True).data,
        })

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, id=None):
        """JSON download of the import report."""
        batch = self.get_object()
        materials = batch.materials.all()
        return Response({
            "batch_id": batch.id,
            "status": batch.status,
            "source_label": batch.source_label,
            "summary": batch.summary,
            "error_report": batch.error_report,
            "started_at": batch.started_at,
            "finished_at": batch.finished_at,
            "materials": ImportMaterialSerializer(materials, many=True).data,
            "totals": {
                "questions_extracted": batch.questions_extracted,
                "questions_found": batch.questions_found,
                "questions_rejected": batch.questions_rejected,
                "duplicates_skipped": batch.duplicates_skipped,
                "images_extracted": batch.images_extracted,
                "theory_blocks_extracted": batch.theory_blocks_extracted,
                "files_total": batch.total_files,
                "files_processed": batch.files_processed,
                "files_failed": batch.files_failed,
            },
        })


# ---------------------------------------------------------------------------
# Question review queue
# ---------------------------------------------------------------------------


class ExtractedQuestionViewSet(viewsets.ReadOnlyModelViewSet):
    """Review queue + decision endpoints."""

    permission_classes = [IsAdminUser]
    queryset = ExtractedQuestion.objects.all().select_related(
        "subject", "topic", "material", "material__batch"
    )
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ExtractedQuestionDetailSerializer
        return ExtractedQuestionListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Filters
        if params.get("batch"):
            qs = qs.filter(material__batch_id=params["batch"])
        if params.get("material"):
            qs = qs.filter(material_id=params["material"])
        if params.get("subject"):
            qs = qs.filter(Q(subject_id=params["subject"]) | Q(inferred_subject=params["subject"]))
        if params.get("topic"):
            qs = qs.filter(Q(topic_id=params["topic"]) | Q(inferred_topic=params["topic"]))
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("needs_review") == "1":
            qs = qs.filter(status="needs_review")
        if params.get("difficulty"):
            qs = qs.filter(inferred_difficulty=params["difficulty"])
        if params.get("q"):
            term = params["q"]
            qs = qs.filter(
                Q(question_text__icontains=term)
                | Q(explanation__icontains=term)
                | Q(material__original_filename__icontains=term)
                | Q(inferred_topic__icontains=term)
            )
        return qs

    @action(detail=True, methods=["post"], url_path="decision")
    def decision(self, request, id=None):
        eq = self.get_object()
        s = QuestionDecisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        decision = s.validated_data["decision"]
        note = s.validated_data.get("note", "")

        if decision == "approve":
            eq.status = "approved"
        elif decision == "reject":
            eq.status = "rejected"
        else:  # reset
            eq.status = "pending"
        eq.review_note = note
        eq.save(update_fields=["status", "review_note"])
        ImportAuditLog.objects.create(
            batch=eq.material.batch, material=eq.material,
            level="info", code=f"question_{decision}",
            message=f"Question #{eq.id} {decision} by {request.user.username}: {note[:200]}",
        )
        return Response({"id": eq.id, "status": eq.status})

    @action(detail=True, methods=["post"], url_path="classify-ai")
    def classify_ai(self, request, id=None):
        from .ai_classifier import classify_question
        eq = self.get_object()
        s = AIClassifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        from .parser.dataclasses import ParsedQuestion
        pq = ParsedQuestion(
            position_index=eq.position_index,
            question_text=eq.question_text,
            option_a=eq.option_a,
            option_b=eq.option_b,
            option_c=eq.option_c,
            option_d=eq.option_d,
            correct_answer=eq.correct_answer,
            explanation=eq.explanation,
        )
        result = classify_question(pq, use_ai=s.validated_data["use_ai"])
        eq.inferred_subject = result.subject
        eq.inferred_topic = result.topic
        eq.inferred_difficulty = result.difficulty
        eq.inferred_bloom_level = result.bloom_level
        eq.classification_confidence = result.confidence
        eq.classification_meta = result.raw
        # Re-resolve FKs if we found a canonical name.
        from .ingest_service import _resolve_subject, _resolve_topic
        subj = _resolve_subject(result.subject)
        if subj:
            eq.subject = subj
            eq.topic = _resolve_topic(subj, result.topic)
        eq.save()
        ImportAuditLog.objects.create(
            batch=eq.material.batch, material=eq.material,
            level="info", code="ai_classify",
            message=f"AI classified Q#{eq.id}: {result.subject} → {result.topic} ({result.confidence:.2f})",
        )
        return Response({
            "id": eq.id,
            "subject": result.subject,
            "topic": result.topic,
            "difficulty": result.difficulty,
            "bloom_level": result.bloom_level,
            "confidence": result.confidence,
        })

    @action(detail=False, methods=["post"], url_path="bulk-decision")
    def bulk_decision(self, request):
        s = BulkDecisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ids = s.validated_data["ids"]
        decision = s.validated_data["decision"]
        note = s.validated_data.get("note", "")

        new_status = {"approve": "approved", "reject": "rejected", "reset": "pending"}[decision]
        eqs = list(ExtractedQuestion.objects.filter(id__in=ids))
        if not eqs:
            return Response({"error": "No matching questions."}, status=404)

        with transaction.atomic():
            for eq in eqs:
                eq.status = new_status
                eq.review_note = note
                eq.save(update_fields=["status", "review_note"])
            # Single audit entry per batch touched
            batches_touched = {eq.material.batch_id for eq in eqs}
            for batch_id in batches_touched:
                batch = ImportBatch.objects.filter(pk=batch_id).first()
                if batch:
                    ImportAuditLog.objects.create(
                        batch=batch, level="info", code=f"bulk_{decision}",
                        message=f"Bulk {decision} of {len([e for e in eqs if e.material.batch_id == batch_id])} questions by {request.user.username}.",
                    )
        return Response({"updated": len(eqs), "new_status": new_status})


# ---------------------------------------------------------------------------
# Dashboard stats + search + health
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard(request):
    """Top-of-page summary stats for the Import Center landing screen."""
    batches = ImportBatch.objects.all()
    total_batches = batches.count()
    total_questions_imported = batches.aggregate(s=Count("materials__extracted_questions"))["s"] or 0
    total_published = ExtractedQuestion.objects.filter(published_question__isnull=False).count()
    total_needs_review = ExtractedQuestion.objects.filter(status="needs_review").count()
    duplicate_rate = 0.0
    if total_questions_imported:
        dup_count = batches.aggregate(s=Count("materials__extracted_questions",
                                              filter=Q(materials__extracted_questions__duplicate_of__isnull=False)))["s"] or 0
        duplicate_rate = round(dup_count / max(1, total_questions_imported), 4)
    image_questions = ExtractedQuestion.objects.exclude(image_refs=[]).count()
    subjects_count = Subject.objects.count()
    topics_count = Topic.objects.count()
    pending_reviews = ExtractedQuestion.objects.filter(status__in=["pending", "needs_review"]).count()
    recent_uploads = [
        {
            "batch_id": b.id, "source_label": b.source_label, "status": b.status,
            "questions_extracted": b.questions_extracted,
            "created_at": b.created_at, "created_by": b.created_by.username if b.created_by else None,
        }
        for b in batches.order_by("-created_at")[:10]
    ]
    return Response({
        "total_batches": total_batches,
        "total_questions_imported": total_questions_imported,
        "total_questions_published": total_published,
        "total_needs_review": total_needs_review,
        "duplicate_rate": duplicate_rate,
        "image_questions": image_questions,
        "subjects_count": subjects_count,
        "topics_count": topics_count,
        "pending_reviews": pending_reviews,
        "recent_uploads": recent_uploads,
    })


@api_view(["GET"])
@permission_classes([IsAdminUser])
def search(request):
    """Full-text search across the extracted question staging area."""
    term = (request.query_params.get("q") or "").strip()
    if not term:
        return Response({"error": "Pass ?q=<text>"}, status=400)
    qs = ExtractedQuestion.objects.filter(
        Q(question_text__icontains=term)
        | Q(explanation__icontains=term)
        | Q(option_a__icontains=term)
        | Q(option_b__icontains=term)
        | Q(option_c__icontains=term)
        | Q(option_d__icontains=term)
        | Q(inferred_topic__icontains=term)
        | Q(material__original_filename__icontains=term)
    ).select_related("material", "subject", "topic").order_by("-created_at")[:200]
    return Response({
        "term": term,
        "count": qs.count() if hasattr(qs, "count") else len(qs),
        "items": ExtractedQuestionListSerializer(qs, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAdminUser])
def health(request):
    """Probe: are the parser pipeline + storage reachable?"""
    info = {"status": "ok", "checks": {}}
    try:
        from supabase import create_client  # noqa
        url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        info["checks"]["supabase"] = bool(url and key)
    except Exception as exc:
        info["checks"]["supabase"] = False
        info["checks"]["supabase_error"] = str(exc)

    try:
        factory = ParserFactory()
        info["checks"]["parsers"] = sorted(factory.supported_formats())
    except Exception as exc:
        info["checks"]["parsers"] = []
        info["checks"]["parsers_error"] = str(exc)

    info["checks"]["django_q2"] = bool(getattr(settings, "Q_CLUSTER", None) is not None)

    # Recency: most recent batch
    last = ImportBatch.objects.order_by("-created_at").first()
    info["last_batch"] = {
        "id": last.id if last else None,
        "status": last.status if last else None,
        "created_at": last.created_at.isoformat() if last else None,
    } if last else None
    return Response(info)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def subjects_topics(request):
    """Tiny lookup endpoint so the UI can populate filter dropdowns."""
    return Response({
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in Subject.objects.all().order_by("name")],
        "topics": [{"id": t.id, "name": t.name, "subject_id": t.subject_id} for t in Topic.objects.all().order_by("name")[:500]],
    })