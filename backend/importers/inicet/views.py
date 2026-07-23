"""Recall importer API views.

These views are deliberately thin — they delegate to `runner` and the
existing `QuestionImportJob` model. They DO NOT modify any existing
viewset or endpoint.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions.models import QuestionImportJob

LOG = logging.getLogger(__name__)


class ImportJobListView(generics.ListAPIView):
    """List recall PDF import jobs."""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # simple list, paginate client-side if needed

    def get_queryset(self):
        return (
            QuestionImportJob.objects
            .filter(job_type="pdf")
            .order_by("-created_at")[:200]
        )

    def post(self, request, *args, **kwargs):
        # Admin-only: kick off an import run via django_q.
        if not (request.user and (getattr(request.user, "is_admin", False) or request.user.is_superuser)):
            return Response({"detail": "admin only"}, status=status.HTTP_403_FORBIDDEN)

        source_dir = request.data.get("source_dir")
        if not source_dir or not Path(source_dir).exists():
            return Response({"detail": "valid source_dir required"}, status=status.HTTP_400_BAD_REQUEST)

        # Lazy import to avoid Django startup-time cost.
        from django_q.tasks import async_task
        from .runner import run_import

        job = QuestionImportJob.objects.create(
            job_type="pdf",
            status="queued",
            source_filename=Path(source_dir).name,
            stored_file_path=source_dir,
            summary={"source_dir": source_dir, "force": bool(request.data.get("force"))},
            created_by=request.user if request.user.is_authenticated else None,
        )

        task_id = async_task(
            "importers.neetpg.tasks.run_recall_import",
            job.id,
            source_dir,
            bool(request.data.get("force")),
        )
        job.summary["q_task_id"] = task_id
        job.save(update_fields=["summary"])

        return Response(
            {"job_id": job.id, "status": job.status, "task_id": task_id},
            status=status.HTTP_202_ACCEPTED,
        )


class ImportJobDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(
            QuestionImportJob,
            id=self.kwargs["pk"],
            job_type="pdf",
        )


class ImportJobRetryView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        job = get_object_or_404(QuestionImportJob, id=pk, job_type="pdf")
        if job.status not in ("failed", "completed"):
            return Response(
                {"detail": f"job status is {job.status}, only failed/completed can be retried"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django_q.tasks import async_task
        job.status = "queued"
        job.save(update_fields=["status"])
        task_id = async_task(
            "importers.neetpg.tasks.run_recall_import",
            job.id,
            job.stored_file_path,
            True,  # force
        )
        job.summary["retry_task_id"] = task_id
        job.save(update_fields=["summary"])
        return Response({"job_id": job.id, "status": job.status, "task_id": task_id})


class ImportReportView(APIView):
    """Return the markdown reports bundle for a given run_id."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, run_id: str):
        from .config import get_config
        cfg = get_config()
        rep_dir = cfg.reports_dir / run_id
        if not rep_dir.exists():
            raise Http404("run_id not found")

        bundle = {}
        for fname in ("IMPORT_REPORT.md", "OCR_REPORT.md",
                      "IMAGE_EXTRACTION_REPORT.md", "QUALITY_REPORT.md",
                      "DEDUPLICATION_REPORT.md", "MISSING_DATA_REPORT.md"):
            p = rep_dir / fname
            bundle[fname] = p.read_text(encoding="utf-8") if p.exists() else ""
        return Response({"run_id": run_id, "reports": bundle})