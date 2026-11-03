"""Database writer for the INI-CET recall importer.

This module used to be a verbatim copy of ``importers.neetpg.db_writer``
with the exam constants swapped, so every fix had to be made twice (and
was not). It now reuses that writer with the exam fixed to INI-CET, so the
same contract applies to both importers:

- re-imports never overwrite admin-corrected rows and only fill empty
  fields of other existing rows;
- a new question without a valid A–D answer, or with an unresolved
  subject, goes to the extraction review queue (no "A" default, no
  first-Subject fallback);
- ``exam_type`` / ``exam_source`` are INI-CET's;
- ``rollback_for_job`` matches the writer's exact ``source_job_ref``;
- an image shared by two questions is linked to both.

Usage:
    writer = DjangoWriter(import_job=<QuestionImportJob instance>)
    for question in parsed_questions:
        writer.write_question(question, recall_source)
"""
from __future__ import annotations

from typing import Optional

from importers.neetpg.db_writer import (  # noqa: F401 - re-exported
    DjangoWriter as _RecallDjangoWriter,
    WriterStats,
    is_protected,
)
from questions.models import QuestionImportJob

from .config import EXAM_SOURCE, EXAM_TYPE


class DjangoWriter(_RecallDjangoWriter):
    """INI-CET flavour of the recall writer (exam fixed to INI-CET)."""

    def __init__(self, import_job: Optional[QuestionImportJob] = None,
                 batch_size: int = 500,
                 source_job_ref: Optional[str] = None):
        super().__init__(
            import_job=import_job,
            batch_size=batch_size,
            exam_type=EXAM_TYPE,
            exam_source=EXAM_SOURCE,
            source_job_ref=source_job_ref,
        )


__all__ = ["DjangoWriter", "WriterStats"]
