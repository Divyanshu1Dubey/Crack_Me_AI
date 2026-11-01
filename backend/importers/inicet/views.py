"""INI-CET recall importer API views.

The same admin-only views as ``importers.neetpg.views`` (this file used to
be a byte-identical copy of it, so it queued
``importers.neetpg.tasks.run_recall_import`` and would have imported
INI-CET PDFs as NEET PG). Here every view dispatches the INI-CET task and
reads the INI-CET report folder.

Not mounted yet: add ``path("api/imports/inicet/", include("importers.inicet.urls"))``
to ``crack_cms/urls.py`` to expose it.
"""
from __future__ import annotations

from importers.neetpg import views as _recall_views

INICET_TASK = "importers.inicet.tasks.run_recall_import"
INICET_CONFIG = "importers.inicet.config"


class ImportJobListView(_recall_views.ImportJobListView):
    task_path = INICET_TASK


class ImportJobDetailView(_recall_views.ImportJobDetailView):
    pass


class ImportJobRetryView(_recall_views.ImportJobRetryView):
    task_path = INICET_TASK


class ImportReportView(_recall_views.ImportReportView):
    config_module = INICET_CONFIG
