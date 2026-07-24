"""DRF views for the ingestion app.

All endpoints gated by ``IsIngestionAdmin`` (mirrors
``accounts.permissions.IsControlTowerAdmin``). Mounted under
``/api/ingestion/`` from ``crack_cms/urls.py``.

Endpoints
---------

  GET    /materials/                        list materials
  POST   /materials/upload/                upload a PDF
  GET    /materials/<sha16>/               material detail + linked jobs
  GET    /jobs/                            list jobs
  POST   /jobs/                            create + dispatch an import job
  GET    /jobs/<id>/                       detail + stages + checkpoints
  POST   /jobs/<id>/retry/                 create a retry job
  POST   /jobs/<id>/cancel/                mark a job cancelled
  GET    /jobs/<id>/checkpoints/           list checkpoints
  GET    /jobs/<id>/logs/                  list structured logs
  GET    /jobs/<id>/stages/                list ImportJobStage rows
  GET    /jobs/<id>/staged-questions/      list StagedQuestion rows
  GET    /batches/                         list batches
  POST   /batches/                         create a batch from N materials
  GET    /batches/<id>/                    detail with per-job grid
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from django.conf import settings
from django.http import Http404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import STRATEGY_AUTO_PR_ONLY
from .exceptions import InvalidJobTransitionError, MaterialNotFoundError
from .models import (
    BatchRun,
    ImportCheckpoint,
    ImportJob,
    ImportJobStage,
    ImportLog,
    MaterialAsset,
    StagedQuestion,
)
from .permissions import IsIngestionAdmin
from .retry import plan_retry
from .serializers import (
    BatchRunListSerializer,
    BatchRunSerializer,
    CreateBatchSerializer,
    CreateJobSerializer,
    ImportCheckpointSerializer,
    ImportJobListSerializer,
    ImportJobSerializer,
    ImportJobStageSerializer,
    ImportLogSerializer,
    MaterialAssetSerializer,
    MaterialUploadSerializer,
    StagedQuestionSerializer,
)
from .utils import audit

LOG = logging.getLogger("ingestion.views")


# ------------------------------------------------------------ material helpers

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _page_count(path: Path) -> int:
    try:
        from importers.neetpg.pdf_reader import open_pdf, page_count
        doc = open_pdf(path)
        try:
            return int(page_count(doc))
        finally:
            doc.close()
    except Exception:
        return 0


# ------------------------------------------------------------ Materials

class MaterialAssetListView(generics.ListAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = MaterialAssetSerializer
    pagination_class = None

    def get_queryset(self):
        qs = MaterialAsset.objects.all().order_by("-uploaded_at")
        exam = self.request.query_params.get("exam")
        if exam:
            qs = qs.filter(exam_hint=exam)
        return qs[:500]


class MaterialAssetUploadView(APIView):
    permission_classes = [IsIngestionAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        s = MaterialUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        f = s.validated_data["file"]
        exam_hint = s.validated_data.get("exam_hint") or ""

        # Persist to MEDIA_ROOT/ingestion_uploads/<sha16>/
        media_root = Path(settings.MEDIA_ROOT)
        upload_dir = media_root / "ingestion_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Hash before persisting, so we can dedupe and route to sha16 dir.
        tmp_path = upload_dir / f"_incoming_{f.name}"
        with open(tmp_path, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        try:
            full_hash = _sha256_file(tmp_path)
            sha16 = full_hash[:16]
            final_dir = upload_dir / sha16
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / f.name
            if not final_path.exists():
                tmp_path.replace(final_path)
            else:
                tmp_path.unlink(missing_ok=True)
            page_count = _page_count(final_path)

            asset, created = MaterialAsset.objects.update_or_create(
                sha256=full_hash,
                defaults={
                    "sha256_short": sha16,
                    "original_filename": f.name,
                    "storage_path": str(final_path),
                    "file_size": final_path.stat().st_size,
                    "page_count": page_count,
                    "exam_hint": exam_hint,
                    "is_active": True,
                    "uploaded_by": request.user if request.user.is_authenticated else None,
                },
            )
            audit(
                actor=request.user,
                action="material.uploaded" if created else "material.reuploaded",
                resource_type="material",
                resource_id=sha16,
                detail=asset.original_filename,
                metadata={"created": created, "page_count": page_count,
                          "file_size": asset.file_size},
            )
            return Response(
                MaterialAssetSerializer(asset).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        except Exception as e:  # pragma: no cover - defensive
            tmp_path.unlink(missing_ok=True)
            LOG.exception("material upload failed")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MaterialAssetDetailView(generics.RetrieveAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = MaterialAssetSerializer
    lookup_field = "sha256_short"

    def get_queryset(self):
        return MaterialAsset.objects.all().prefetch_related("jobs")


# ------------------------------------------------------------ Jobs

class ImportJobListView(APIView):
    permission_classes = [IsIngestionAdmin]
    pagination_class = None

    def get(self, request, *args, **kwargs):
        qs = ImportJob.objects.all().select_related("material_asset", "batch_run").order_by("-created_at")
        for q in ("status", "parent_exam", "batch_run"):
            v = request.query_params.get(q)
            if v:
                qs = qs.filter(**{q: v})
        sha = request.query_params.get("material_sha16")
        if sha:
            qs = qs.filter(material_asset__sha256_short=sha)
        return Response(ImportJobListSerializer(qs[:200], many=True).data)

    def post(self, request, *args, **kwargs):
        s = CreateJobSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        sha16 = s.validated_data["material_sha16"]
        parent_exam = s.validated_data["parent_exam"]
        strategy = s.validated_data.get("strategy") or STRATEGY_AUTO_PR_ONLY

        material = MaterialAsset.objects.filter(sha256_short=sha16).first()
        if not material:
            raise MaterialNotFoundError(f"No MaterialAsset with sha16={sha16}")

        batch = None
        batch_id = s.validated_data.get("batch_id")
        if batch_id:
            batch = BatchRun.objects.filter(id=batch_id).first()

        from .orchestrator import create_job
        job = create_job(
            material=material,
            parent_exam=parent_exam,
            created_by=request.user,
            batch=batch,
            config={"strategy": strategy, "force": False},
        )

        from .tasks import dispatch_job
        task_id = dispatch_job(job.id)
        job.summary = {"q_task_id": task_id}
        job.save(update_fields=["summary"])

        audit(
            actor=request.user,
            action="job.created",
            resource_type="job",
            resource_id=str(job.id),
            detail=f"material={sha16} exam={parent_exam} strategy={strategy}",
            metadata={"q_task_id": task_id},
        )
        return Response(
            ImportJobListSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ImportJobDetailView(generics.RetrieveAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = ImportJobSerializer
    queryset = ImportJob.objects.all().select_related(
        "material_asset", "batch_run", "retry_of",
    ).prefetch_related("stages", "checkpoints")


class ImportJobRetryView(APIView):
    permission_classes = [IsIngestionAdmin]

    def post(self, request, job_id: int):
        original = ImportJob.objects.filter(id=job_id).first()
        if not original:
            raise Http404
        try:
            retry_job = plan_retry(original, created_by=request.user)
        except InvalidJobTransitionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        from .tasks import dispatch_job
        task_id = dispatch_job(retry_job.id)
        retry_job.summary = {"q_task_id": task_id, "retry_of_job": original.id}
        retry_job.save(update_fields=["summary"])

        audit(
            actor=request.user,
            action="job.retried",
            resource_type="job",
            resource_id=str(retry_job.id),
            detail=f"retry of {original.id} (was {original.status})",
            metadata={"original_job_id": original.id, "q_task_id": task_id},
        )
        return Response(
            ImportJobListSerializer(retry_job).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ImportJobCancelView(APIView):
    permission_classes = [IsIngestionAdmin]

    def post(self, request, job_id: int):
        job = ImportJob.objects.filter(id=job_id).first()
        if not job:
            raise Http404
        from .orchestrator import cancel_job
        ok = cancel_job(job)
        audit(
            actor=request.user,
            action="job.cancelled" if ok else "job.cancel_rejected",
            resource_type="job",
            resource_id=str(job.id),
            detail=f"status={job.status}",
        )
        return Response(
            {"cancelled": ok, "status": job.status},
            status=status.HTTP_200_OK,
        )


class ImportCheckpointListView(generics.ListAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = ImportCheckpointSerializer
    pagination_class = None

    def get_queryset(self):
        return ImportCheckpoint.objects.filter(job_id=self.kwargs["job_id"]).order_by("-created_at")


class ImportLogListView(generics.ListAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = ImportLogSerializer
    pagination_class = None

    def get_queryset(self):
        qs = ImportLog.objects.filter(job_id=self.kwargs["job_id"]).order_by("-created_at")
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
        return qs[:2000]


class ImportJobStageListView(generics.ListAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = ImportJobStageSerializer
    pagination_class = None

    def get_queryset(self):
        return ImportJobStage.objects.filter(job_id=self.kwargs["job_id"]).order_by("started_at")


class StagedQuestionListView(generics.ListAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = StagedQuestionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = StagedQuestion.objects.filter(job_id=self.kwargs["job_id"]).order_by("page_number", "question_number_in_pdf")
        qa = self.request.query_params.get("qa_status")
        if qa:
            qs = qs.filter(qa_status=qa)
        rs = self.request.query_params.get("review_status")
        if rs:
            qs = qs.filter(review_status=rs)
        return qs[:2000]


# ------------------------------------------------------------ Batches

class BatchRunListView(APIView):
    permission_classes = [IsIngestionAdmin]

    def get(self, request, *args, **kwargs):
        qs = BatchRun.objects.all().order_by("-created_at")
        return Response(BatchRunListSerializer(qs[:200], many=True).data)

    def post(self, request, *args, **kwargs):
        s = CreateBatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        name = s.validated_data["name"]
        sha16s = s.validated_data["material_sha16s"]
        parent_exam = s.validated_data["parent_exam"]
        strategy = s.validated_data.get("strategy") or STRATEGY_AUTO_PR_ONLY

        materials = list(MaterialAsset.objects.filter(sha256_short__in=sha16s))
        if not materials:
            raise MaterialNotFoundError("No MaterialAssets matched the supplied sha16s")

        batch = BatchRun.objects.create(
            name=name,
            status="running",
            total_jobs=len(materials),
            created_by=request.user,
        )
        from .orchestrator import create_job
        from .tasks import dispatch_job
        for m in materials:
            job = create_job(
                material=m,
                parent_exam=parent_exam,
                created_by=request.user,
                batch=batch,
                config={"strategy": strategy, "force": False},
            )
            dispatch_job(job.id)

        audit(
            actor=request.user,
            action="batch.created",
            resource_type="batch",
            resource_id=str(batch.id),
            detail=f"{name} ({len(materials)} jobs, strategy={strategy})",
        )
        return Response(
            BatchRunSerializer(batch).data,
            status=status.HTTP_202_ACCEPTED,
        )


class BatchRunDetailView(generics.RetrieveAPIView):
    permission_classes = [IsIngestionAdmin]
    serializer_class = BatchRunSerializer
    queryset = BatchRun.objects.all().prefetch_related("jobs")
