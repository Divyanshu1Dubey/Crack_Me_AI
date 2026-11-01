"""REST API for the Admin Import Center.

All endpoints require an authenticated staff user (the same gate Django
admin uses). The two long operations — parsing an upload and publishing a
batch (publish + auto-test build) — run in an in-process background
thread (``_start_background``) so the HTTP request returns at once (202 /
201) and never hits the gunicorn timeout. They do not depend on a
django-q worker. Their state is recorded on the ImportBatch (``status``
for parsing, ``summary["publish"]`` for publishing) and the UI polls it;
a run that stopped updating (e.g. the process restarted) is reported as
stale instead of "still running". Both operations are idempotent, so a
stale run can simply be started again.

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
import random
import shutil
import tempfile
import threading
import zipfile
from datetime import timedelta
from pathlib import Path, PurePosixPath

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
# Extensions accepted from inside a .zip (no nested archives).
ALLOWED_ZIP_MEMBER_EXTS = ALLOWED_EXTS - {".zip"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB per upload
MAX_FILES_PER_UPLOAD = 200
# Zip-bomb guards: limits on what a single uploaded .zip may expand to.
MAX_ZIP_MEMBERS = 500
MAX_ZIP_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024  # 1 GiB

# A background run (parse or publish) that has not written progress for this
# long is reported as stale: its thread most likely died with the process.
STALE_AFTER = timedelta(minutes=30)


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _staff_only(request):
    """IsAdminUser handles staff/superuser but also authenticated. Tighten."""
    u = getattr(request, "user", None)
    return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


# ---------------------------------------------------------------------------
# Background execution + zip safety helpers
# ---------------------------------------------------------------------------


def _start_background(target, *, name: str) -> None:
    """Run ``target()`` in a daemon thread and release its DB connections.

    Kept as a module-level function so tests can patch it to run inline.
    """
    def _runner():
        from django.db import connections
        try:
            target()
        finally:
            connections.close_all()

    threading.Thread(target=_runner, name=name, daemon=True).start()


def _safe_member_path(dest_dir: Path, member_name: str) -> Path | None:
    """Destination for a zip member, or None if it would escape ``dest_dir``."""
    parts = [p for p in PurePosixPath(member_name.replace("\\", "/")).parts
             if p not in ("", ".", "..", "/") and ":" not in p]
    if not parts:
        return None
    target = dest_dir.joinpath(*parts)
    try:
        target.resolve().relative_to(dest_dir.resolve())
    except ValueError:
        return None
    return target


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> list[str]:
    """Extract the allowed members of ``zip_path`` into ``dest_dir``.

    Enforces MAX_ZIP_MEMBERS and MAX_ZIP_UNCOMPRESSED_BYTES on the declared
    sizes before writing anything, and again on the bytes actually written
    (a forged header cannot inflate past the budget). Returns the names of
    members that were skipped (disallowed type / unsafe path).
    Raises ``ValueError`` when a limit is exceeded and ``zipfile.BadZipFile``
    for a corrupt archive.
    """
    skipped: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [i for i in zf.infolist() if not i.is_dir()]
        if len(members) > MAX_ZIP_MEMBERS:
            raise ValueError(f"archive has {len(members)} files (limit {MAX_ZIP_MEMBERS})")
        declared = sum(max(0, i.file_size) for i in members)
        if declared > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"archive expands to {declared} bytes (limit {MAX_ZIP_UNCOMPRESSED_BYTES})"
            )
        budget = MAX_ZIP_UNCOMPRESSED_BYTES
        for info in members:
            if Path(info.filename).suffix.lower() not in ALLOWED_ZIP_MEMBER_EXTS:
                skipped.append(f"{info.filename}: unsupported extension")
                continue
            target = _safe_member_path(dest_dir, info.filename)
            if target is None:
                skipped.append(f"{info.filename}: unsafe path")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    budget -= len(chunk)
                    if budget < 0:
                        raise ValueError(
                            f"archive expands past the {MAX_ZIP_UNCOMPRESSED_BYTES}-byte limit"
                        )
                    out.write(chunk)
    return skipped


def _is_stale(ts) -> bool:
    """True if ``ts`` (datetime or ISO string) is older than STALE_AFTER."""
    if not ts:
        return False
    if isinstance(ts, str):
        from django.utils.dateparse import parse_datetime
        ts = parse_datetime(ts)
        if ts is None:
            return False
    return timezone.now() - ts > STALE_AFTER


def _set_publish_state(batch_id: int, state: dict) -> dict:
    """Write ``summary["publish"]`` with a queryset update (no stale overwrite)."""
    summary = dict(
        ImportBatch.objects.filter(pk=batch_id).values_list("summary", flat=True).first() or {}
    )
    summary["publish"] = state
    ImportBatch.objects.filter(pk=batch_id).update(summary=summary, updated_at=timezone.now())
    return state


# ---------------------------------------------------------------------------
# Upload + batch creation
# ---------------------------------------------------------------------------


class UploadCreateBatchView(APIView):
    """Accept multipart upload(s) or a single folder .zip and create a batch.

    The endpoint creates an ImportBatch in 'queued' state and returns its id
    immediately. The parse runs in a background thread that fills THAT
    batch (``ingest_path(batch=...)``), so the id the UI polls is the one
    that reaches ``completed`` / ``partial`` and owns the materials.
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
                # Each archive expands into its own sub-folder so a rejected
                # archive can be removed without touching the other files.
                extract_dir = work_dir / f"{Path(safe_name).stem}_zip"
                extract_dir.mkdir(parents=True, exist_ok=True)
                try:
                    skipped = _safe_extract_zip(dest, extract_dir)
                    rejected.extend(f"{f.name}/{s}" for s in skipped)
                except zipfile.BadZipFile:
                    rejected.append(f"{f.name}: not a valid zip")
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    continue
                except ValueError as exc:
                    rejected.append(f"{f.name}: {exc}")
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    continue
                finally:
                    dest.unlink(missing_ok=True)
                if not any(p.is_file() for p in extract_dir.rglob("*")):
                    rejected.append(f"{f.name}: no supported files inside")
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    continue
                dest = extract_dir
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

        # Kick off the parse in a background thread. ingest_path fills the
        # batch created above (it used to create a second batch, leaving this
        # one "queued" with 0 files forever). No django-q worker is needed.
        batch_id = batch.id

        def _run():
            try:
                done = ingest_path(
                    path=str(work_dir),
                    source_label=source_label,
                    created_by=user,
                    use_ai=use_ai,
                    force=force,
                    batch=ImportBatch.objects.get(pk=batch_id),
                )
                ImportAuditLog.objects.create(
                    batch=done, level="info", code="ingest_done",
                    message=(
                        f"Ingest {done.status}: {done.questions_extracted} questions, "
                        f"{done.images_extracted} images."
                    ),
                )
            except Exception as exc:  # pragma: no cover - background
                log.exception("Background ingest failed for batch %s", batch_id)
                ImportBatch.objects.filter(pk=batch_id).update(
                    status="failed",
                    error_report=[{"file": "(batch)", "error": str(exc)[:500]}],
                    finished_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                ImportAuditLog.objects.create(
                    batch_id=batch_id, level="error", code="ingest_crash",
                    message=f"Ingest crashed: {exc}",
                )

        # on_commit: the thread must never start before the batch row is
        # visible to its own DB connection.
        transaction.on_commit(lambda: _start_background(_run, name=f"ingest-batch-{batch_id}"))

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
        """Stop a queued / processing parse. The ingest loop checks the
        status between files and stops; already-parsed files stay staged."""
        batch = self.get_object()
        if batch.status not in {"queued", "processing"}:
            return Response(
                {"error": f"Only a queued or processing batch can be cancelled (status={batch.status})."},
                status=409,
            )
        updated = ImportBatch.objects.filter(
            pk=batch.pk, status__in=["queued", "processing"],
        ).update(status="cancelled", finished_at=timezone.now(), updated_at=timezone.now())
        if not updated:
            batch.refresh_from_db()
            return Response({"error": f"Batch already finished (status={batch.status})."}, status=409)
        ImportAuditLog.objects.create(batch=batch, level="warning", code="cancelled",
                                      message=f"Cancelled by {request.user.username}")
        return Response({"status": "cancelled", "batch_id": batch.id})

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, id=None):
        """Publish approved rows (and build auto-tests) in the background.

        Returns 202 at once; progress is ``summary["publish"]`` on the batch
        (``running`` → ``done`` / ``failed``), which the batch page polls.
        Publishing synchronously used to run past the 120 s gunicorn timeout
        on large batches, killing the worker mid-way.
        """
        batch = self.get_object()
        s = BatchPublishSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        max_per_test = s.validated_data["max_per_test"]
        only_publish = s.validated_data["only_publish"] or not s.validated_data["build_tests"]

        if batch.status not in {"completed", "partial"}:
            return Response(
                {"error": f"Batch is {batch.status}; publish once parsing has finished."},
                status=409,
            )
        current = (batch.summary or {}).get("publish") or {}
        if current.get("state") == "running" and not _is_stale(current.get("heartbeat_at") or current.get("started_at")):
            return Response(
                {"error": "A publish is already running for this batch.", "publish": current},
                status=409,
            )

        username = request.user.username
        state = _set_publish_state(batch.id, {
            "state": "running",
            "started_at": timezone.now().isoformat(),
            "heartbeat_at": timezone.now().isoformat(),
            "by": username,
            "only_publish": only_publish,
            "max_per_test": max_per_test,
        })
        batch_id = batch.id

        def _run():
            started = state["started_at"]

            def _heartbeat(done_rows):
                _set_publish_state(batch_id, {
                    **state, "heartbeat_at": timezone.now().isoformat(), "rows_done": done_rows,
                })

            try:
                if only_publish:
                    n = publish_batch(batch_id, on_progress=_heartbeat)
                    tests_built = 0
                else:
                    res = publish_batch_and_build_tests(
                        batch_id, max_per_test=max_per_test, on_progress=_heartbeat,
                    )
                    n = res["published"]
                    tests_built = res["tests_built"]
                _set_publish_state(batch_id, {
                    "state": "done", "started_at": started,
                    "finished_at": timezone.now().isoformat(), "by": username,
                    "published": n, "tests_built": tests_built,
                    "only_publish": only_publish, "max_per_test": max_per_test,
                })
                ImportAuditLog.objects.create(
                    batch_id=batch_id, level="info", code="published",
                    message=f"Published {n} questions, built {tests_built} tests.",
                    details={"by": username, "max_per_test": max_per_test},
                )
            except Exception as exc:  # pragma: no cover - background
                log.exception("Background publish failed for batch %s", batch_id)
                _set_publish_state(batch_id, {
                    "state": "failed", "started_at": started,
                    "finished_at": timezone.now().isoformat(), "by": username,
                    "error": str(exc)[:500],
                })
                ImportAuditLog.objects.create(
                    batch_id=batch_id, level="error", code="publish_failed",
                    message=f"Publish failed: {exc}",
                )

        transaction.on_commit(lambda: _start_background(_run, name=f"publish-batch-{batch_id}"))
        return Response({"batch_id": batch_id, "publish": state}, status=202)

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, id=None):
        batch = self.get_object()
        s = BatchRollbackSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not s.validated_data["confirm"]:
            return Response({"error": "Confirmation required."}, status=400)
        if batch.status in {"queued", "processing"}:
            return Response(
                {"error": "This batch is still parsing. Cancel it first, then roll back."},
                status=409,
            )
        publish_state = (batch.summary or {}).get("publish") or {}
        if publish_state.get("state") == "running" and not _is_stale(
            publish_state.get("heartbeat_at") or publish_state.get("started_at")
        ):
            return Response({"error": "A publish is running for this batch; wait for it to finish."},
                            status=409)

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
        from .mock_test_builder import _ensure_test, _record_batch_test_ids

        # Pull approved + published questions (still live) for this batch.
        base = ExtractedQuestion.objects.filter(
            material__batch_id=batch.id,
            status__in=["approved", "published"],
            published_question__isnull=False,
            published_question__is_active=True,
        )
        if strategy in {"by_subject", "by_chapter", "by_topic"} and s.validated_data.get("subject_id"):
            base = base.filter(subject_id=s.validated_data["subject_id"])
        if strategy == "by_topic" and s.validated_data.get("topic_id"):
            base = base.filter(topic_id=s.validated_data["topic_id"])
        if difficulty != "mixed":
            base = base.filter(inferred_difficulty=difficulty)
        if strategy == "image_based":
            base = base.filter(
                Q(published_question__is_image_based=True)
                | Q(published_question__images__is_active=True)
                | ~Q(image_refs=[])
            )

        rows = list(
            base.order_by("material_id", "position_index", "id")
            .values_list("published_question_id", "subject_id")
        )
        # Dedupe (the image join can repeat rows) while keeping source order.
        seen: set[int] = set()
        ordered: list[tuple[int, int | None]] = []
        for qid, subj_id in rows:
            if qid not in seen:
                seen.add(qid)
                ordered.append((qid, subj_id))
        if not ordered:
            return Response({"error": "No publishable questions matched the filter."}, status=400)

        # Selection per strategy (each one now does what its label says):
        #   random / revision / weekly → random sample
        #   grand                      → balanced round-robin across subjects
        #   everything else            → source order (after the filters above;
        #                                 "by chapter" filters by subject, as
        #                                 chapters are not modelled on imports)
        if strategy in {"random", "revision", "weekly"}:
            question_ids = [qid for qid, _ in ordered]
            selected = random.sample(question_ids, min(count, len(question_ids)))
        elif strategy == "grand":
            buckets: dict = {}
            for qid, subj_id in ordered:
                buckets.setdefault(subj_id, []).append(qid)
            selected = []
            queues = list(buckets.values())
            while len(selected) < count and any(queues):
                for q_list in queues:
                    if q_list and len(selected) < count:
                        selected.append(q_list.pop(0))
        else:
            selected = [qid for qid, _ in ordered][:count]

        # Map strategy → Test record naming + grouping.
        kind = "subject" if strategy in {"by_subject", "by_chapter"} else (
            "topic" if strategy == "by_topic" else "mixed")
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
        t.questions.set(selected)
        Test.objects.filter(pk=t.pk).update(num_questions=len(selected))
        _record_batch_test_ids(batch.id, "mock_test_ids", [t.id], replace=False)
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
        info["checks"]["parsers"] = sorted(factory.supported_extensions())
    except Exception as exc:
        info["checks"]["parsers"] = []
        info["checks"]["parsers_error"] = str(exc)
        info["status"] = "degraded"

    # The parsers import their libraries lazily, so a missing library only
    # shows up as a failed upload. Report it here instead.
    import importlib.util
    libraries = {
        "docx": bool(importlib.util.find_spec("docx")),
        "pptx": bool(importlib.util.find_spec("pptx")),
        "pdf": bool(importlib.util.find_spec("pypdf") or importlib.util.find_spec("pdfplumber")),
        "pillow": bool(importlib.util.find_spec("PIL")),
    }
    info["checks"]["parser_libraries"] = libraries
    missing = sorted(k for k, ok in libraries.items() if not ok)
    if missing:
        info["status"] = "degraded"
        info["checks"]["parser_libraries_missing"] = missing

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