"""INI-CET recall importer API views (mounted at ``/api/imports/inicet/``).

The same admin-only views as ``importers.neetpg.views`` (this file used to
be a byte-identical copy of it, so it queued
``importers.neetpg.tasks.run_recall_import`` and would have imported
INI-CET PDFs as NEET PG). Here every view dispatches the INI-CET task, reads
the INI-CET report folder and only sees INI-CET jobs: a job records the
importer that created it (``summary["importer"] = "inicet"``), and the
list, detail and retry endpoints of each importer filter on it, so a NEET PG
job is never listed here or re-run with the INI-CET task.
"""
from __future__ import annotations

from importers.neetpg import views as _recall_views

INICET_TASK = "importers.inicet.tasks.run_recall_import"
INICET_CONFIG = "importers.inicet.config"
INICET_IMPORTER = _recall_views.IMPORTER_INICET


class ImportJobListView(_recall_views.ImportJobListView):
    task_path = INICET_TASK
    importer = INICET_IMPORTER


class ImportJobDetailView(_recall_views.ImportJobDetailView):
    importer = INICET_IMPORTER


class ImportJobRetryView(_recall_views.ImportJobRetryView):
    task_path = INICET_TASK
    importer = INICET_IMPORTER


class ImportReportView(_recall_views.ImportReportView):
    config_module = INICET_CONFIG
