"""Background build of PYQ topic notes (django-q, 2026-11, notes group).

``POST /api/questions/topic-notes/build/`` (questions.views_notes.TopicNoteBuildView) queues
``build_topic_notes_task`` when a request plans more than 25 notes. The task runs only while
``python manage.py qcluster`` is up. It builds draft notes (never publishes, never changes an
answer key) exactly as the synchronous path does (``notes_builder.run_build``).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rows kept in the stored task result (django-q saves the return value in its ORM).
RESULT_ROWS = 500


def build_topic_notes_task(params: dict, actor_id=None) -> dict:
    """Build the notes ``params`` plans (the build endpoint's parameters) and return a compact
    report: ``{builder_version, mode, totals, notes: [{note_id, action, subject_id, topic_id,
    exam_type, error}]}``. ``actor_id``: the admin who queued it (``created_by`` of new notes)."""
    from django.contrib.auth import get_user_model

    from questions import notes_builder as nb

    actor = None
    if actor_id:
        actor = get_user_model().objects.filter(pk=actor_id).first()
    report = nb.run_build(dict(params or {}), apply=True, actor=actor)
    logger.info('topic notes build task: %s', report['totals'])
    return {
        'builder_version': report['builder_version'],
        'mode': report['mode'],
        'totals': report['totals'],
        'notes': [
            {name: row.get(name) for name in ('note_id', 'action', 'subject_id', 'topic_id', 'exam_type', 'error')}
            for row in report['notes'][:RESULT_ROWS]
        ],
    }
