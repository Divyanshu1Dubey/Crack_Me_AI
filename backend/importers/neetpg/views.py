"""Recall importer API views.

These views are deliberately thin — they delegate to `runner` and the
existing `QuestionImportJob` model. They DO NOT modify any existing
viewset or endpoint.

Every endpoint is admin-only (``IsControlTowerAdmin``): import jobs and
their reports are internal. ``source_dir`` must lie inside an allow-listed
root (``RECALL_IMPORT_ALLOWED_ROOTS``, os.pathsep-separated; default: the
repo's ``material/`` folder and ``MEDIA_ROOT/ingestion_uploads`` /
``MEDIA_ROOT/recall_uploads``) and ``run_id`` must be a plain token, so the
API cannot be pointed at arbitrary server paths.

The views are parameterised by ``task_path`` / ``config_module`` /
``importer`` so the INI-CET importer reuses them with its own task, output
folder and jobs. Each job records the importer that created it
(``summary["importer"]``); the list, detail and retry endpoints only see
their own importer's jobs, so a NEET PG job can never be listed by, or
re-run through, the INI-CET API (and the reverse). Jobs created before the
importer was recorded are NEET PG's.
"""
from __future__ import annotations

import importlib
import logging
import os
import re
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions.models import QuestionImportJob

LOG = logging.getLogger(__name__)

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NEETPG_TASK = "importers.neetpg.tasks.run_recall_import"
NEETPG_CONFIG = "importers.neetpg.config"
IMPORTER_NEETPG = "neetpg"
IMPORTER_INICET = "inicet"


def recall_jobs(importer: str):
    """The recall import jobs (``job_type='pdf'``) of one importer.

    Jobs without a recorded importer predate it and are NEET PG's.
    """
    qs = QuestionImportJob.objects.filter(job_type="pdf")
    if importer == IMPORTER_NEETPG:
        return qs.filter(Q(summary__importer=IMPORTER_NEETPG) | ~Q(summary__has_key="importer"))
    return qs.filter(summary__importer=importer)


class QuestionImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionImportJob
        fields = [
            "id", "job_type", "status", "source_filename",
            "summary", "error_report", "created_at", "updated_at",
        ]
        read_only_fields = fields


def allowed_source_roots() -> list[Path]:
    raw = os.environ.get("RECALL_IMPORT_ALLOWED_ROOTS", "")
    roots = [Path(p) for p in raw.split(os.pathsep) if p.strip()]
    if not roots:
        media = Path(settings.MEDIA_ROOT)
        roots = [
            Path(settings.BASE_DIR).parent / "material",
            media / "ingestion_uploads",
            media / "recall_uploads",
        ]
    return [r.resolve() for r in roots]


def validate_source_dir(raw) -> Path | None:
    """Resolved ``raw`` if it is an existing directory inside an allowed root."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        candidate = Path(raw).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if not candidate.is_dir():
        return None
    for root in allowed_source_roots():
        try:
            candidate.relative_to(root)
            return candidate
        except ValueError:
            continue
    return None


class ImportJobListView(generics.ListAPIView):
    """List recall PDF import jobs (GET) and start an import run (POST).

    GET is paginated with the project default (``count`` / ``next`` /
    ``results``; 20 per page, ``?page_size=`` up to 100), newest first.
    The serializer leaves out ``stored_file_path`` and ``created_by``.
    """
    permission_classes = [IsControlTowerAdmin]
    serializer_class = QuestionImportJobSerializer
    task_path = NEETPG_TASK
    importer = IMPORTER_NEETPG

    def get_queryset(self):
        return recall_jobs(self.importer).order_by("-created_at", "-id")

    def post(self, request, *args, **kwargs):
        source_dir = validate_source_dir(request.data.get("source_dir"))
        if source_dir is None:
            return Response(
                {"detail": "source_dir must be an existing folder inside an allowed import root."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Lazy import to avoid Django startup-time cost.
        from django_q.tasks import async_task

        force = bool(request.data.get("force"))
        job = QuestionImportJob.objects.create(
            job_type="pdf",
            status="queued",
            source_filename=source_dir.name,
            stored_file_path=str(source_dir),
            summary={"source_dir": str(source_dir), "force": force, "importer": self.importer},
            created_by=request.user if request.user.is_authenticated else None,
        )

        task_id = async_task(self.task_path, job.id, str(source_dir), force)
        job.summary["q_task_id"] = task_id
        job.save(update_fields=["summary"])

        return Response(
            {"job_id": job.id, "status": job.status, "task_id": task_id},
            status=status.HTTP_202_ACCEPTED,
        )


class ImportJobDetailView(generics.RetrieveAPIView):
    permission_classes = [IsControlTowerAdmin]
    serializer_class = QuestionImportJobSerializer
    importer = IMPORTER_NEETPG

    def get_object(self):
        return get_object_or_404(recall_jobs(self.importer), id=self.kwargs["pk"])


class ImportJobRetryView(APIView):
    permission_classes = [IsControlTowerAdmin]
    task_path = NEETPG_TASK
    importer = IMPORTER_NEETPG

    def post(self, request, pk: int):
        job = get_object_or_404(recall_jobs(self.importer), id=pk)
        if job.status not in ("failed", "completed"):
            return Response(
                {"detail": f"job status is {job.status}, only failed/completed can be retried"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source_dir = validate_source_dir(job.stored_file_path)
        if source_dir is None:
            return Response(
                {"detail": "the job's source folder is missing or outside the allowed import roots"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django_q.tasks import async_task
        job.status = "queued"
        job.save(update_fields=["status"])
        task_id = async_task(
            self.task_path,
            job.id,
            str(source_dir),
            True,  # force: re-parse; the writer still never overwrites admin edits
        )
        job.summary["retry_task_id"] = task_id
        job.save(update_fields=["summary"])
        return Response({"job_id": job.id, "status": job.status, "task_id": task_id})


class ImportReportView(APIView):
    """Return the markdown reports bundle for a given run_id."""
    permission_classes = [IsControlTowerAdmin]
    config_module = NEETPG_CONFIG

    def get(self, request, run_id: str):
        if not RUN_ID_RE.match(run_id or ""):
            raise Http404("run_id not found")
        cfg = importlib.import_module(self.config_module).get_config()
        reports_root = cfg.reports_dir.resolve()
        rep_dir = (reports_root / run_id).resolve()
        if rep_dir.parent != reports_root or not rep_dir.is_dir():
            raise Http404("run_id not found")

        bundle = {}
        for fname in ("IMPORT_REPORT.md", "OCR_REPORT.md",
                      "IMAGE_EXTRACTION_REPORT.md", "QUALITY_REPORT.md",
                      "DEDUPLICATION_REPORT.md", "MISSING_DATA_REPORT.md"):
            p = rep_dir / fname
            bundle[fname] = p.read_text(encoding="utf-8") if p.exists() else ""
        return Response({"run_id": run_id, "reports": bundle})
