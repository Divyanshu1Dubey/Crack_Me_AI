"""Topic-notes builder endpoints (2026-11, notes group; routes in questions/urls_notes.py).

* ``POST topic-notes/build/``                  admin: plan + build notes (async above 25 notes)
* ``GET  topic-notes/library/<pk>/sources/``   admin: the questions a built note cites / excludes
* ``GET  topic-notes/published/<pk>/``         student: one published note, filtered per viewer
* ``generate_response`` / ``generation_throttles``: the old generate endpoints (questions.views)
  delegate here when TOPIC_NOTES_BUILDER is on.
* ``published_list_response``: the published list (questions.views.PublishedTopicNoteListView),
  filtered per viewer whatever the flag says (an entitlement fix, not a feature).

Entitlement: a note restates answers, so a free viewer reads only the points whose questions are
all free showcase questions (``questions.views.free_showcase_rows``); a manual note citing premium
questions is withheld from free viewers. The builder routes answer 404 ``feature_disabled``
while TOPIC_NOTES_BUILDER is off.
"""
from __future__ import annotations

import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions import notes_builder as nb
from questions.models import TopicNote, TopicNoteSource
from questions.serializers_notes import PublishedTopicNoteSerializer, TopicNoteSourceSerializer

logger = logging.getLogger(__name__)

ASYNC_THRESHOLD = 25
FEATURE_DISABLED = {
    'code': 'feature_disabled',
    'detail': 'The PYQ notes builder is switched off (TOPIC_NOTES_BUILDER).',
}


def _disabled() -> Response:
    return Response(FEATURE_DISABLED, status=status.HTTP_404_NOT_FOUND)


def _flag(data, name, default=False) -> bool:
    if data is None or name not in data or data.get(name) in (None, ''):
        return default
    return nb._truthy(data.get(name))


def _int(value, default, lo, hi):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def parse_build_options(data) -> tuple:
    """``(options, error)`` of a generate / build request body."""
    data = data if hasattr(data, 'get') else {}
    mode = str(data.get('mode') or 'extractive').strip().lower()
    if mode not in nb.MODES:
        return None, f'mode must be one of {", ".join(nb.MODES)}'
    return {
        'mode': mode,
        'include_provisional': _flag(data, 'include_provisional', True),
        'verified_only': _flag(data, 'verified_only'),
        'dry_run': _flag(data, 'dry_run'),
        'force': _flag(data, 'force'),
        'min_questions': _int(data.get('min_questions'), nb.MIN_PYQS, 1, 50),
        'evidence': _flag(data, 'evidence', True),
    }, ''


def viewer_context(request) -> tuple:
    """``(full_access, free_ids)``: staff / premium read everything; others the free showcase."""
    from accounts.utils import is_premium
    from questions.views import _is_staff_user, free_showcase_rows

    user = getattr(request, 'user', None)
    full = bool(_is_staff_user(user) or (user is not None and getattr(user, 'is_authenticated', False)
                                         and is_premium(user)))
    free_ids = set() if full else set(free_showcase_rows().values_list('question_id', flat=True))
    return full, free_ids


def _views_for(notes, request) -> dict:
    """``{note_id: viewer_view}`` for a page of notes; built notes whose sources changed are
    marked stale (one update)."""
    full, free_ids = viewer_context(request)
    built = [note.pk for note in notes if nb.is_built(note)]
    states = nb.source_state(built)
    stale_now = [nid for nid, state in states.items() if state['hidden']]
    if stale_now:
        TopicNote.objects.filter(pk__in=stale_now, is_stale=False).update(is_stale=True)
        for note in notes:
            if note.pk in stale_now:
                note.is_stale = True
    return {note.pk: nb.viewer_view(note, full_access=full, free_ids=free_ids, state=states.get(note.pk))
            for note in notes}


def published_list_response(view, request) -> Response:
    """Body of GET topic-notes/published/ (paged), each note filtered for this viewer."""
    queryset = view.filter_queryset(view.get_queryset())
    page = view.paginate_queryset(queryset)
    notes = list(page if page is not None else queryset)
    context = {'views': _views_for(notes, request), 'request': request}
    data = PublishedTopicNoteSerializer(notes, many=True, context=context).data
    return view.get_paginated_response(data) if page is not None else Response(data)


def generation_throttles(request, throttles) -> list:
    """The generate endpoints keep the ``ai_heavy`` scope only for a request that may call an LLM."""
    if not nb.builder_enabled():
        return throttles
    try:
        mode = str((request.data or {}).get('mode') or 'extractive').strip().lower()
    except Exception:  # noqa: BLE001 - unparsable body: keep every throttle
        return throttles
    if mode in ('llm', 'auto'):
        return throttles
    return [throttle for throttle in throttles if not isinstance(throttle, ScopedRateThrottle)]


def generate_response(request, note, *, shape='note') -> Response:
    """The old generate endpoints with the builder (TOPIC_NOTES_BUILDER on). ``shape`` keeps each
    endpoint's response keys: 'note' = the note's fields (+ build), 'library' = {detail, content}
    (+ note, build). Never 503: the extractive build needs no AI provider."""
    from questions.serializers import TopicNoteSerializer

    options, error = parse_build_options(request.data)
    if error:
        return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
    result = nb.build_topic_note(
        note, mode=options['mode'], include_provisional=options['include_provisional'],
        verified_only=options['verified_only'], dry_run=options['dry_run'], force=options['force'],
        min_questions=options['min_questions'], evidence=options['evidence'],
    )
    build = result.summary()
    if result.error == 'no_subject_or_topic':
        return Response({'error': 'This note has no subject/topic to generate from.', 'build': build},
                        status=status.HTTP_400_BAD_REQUEST)
    if not result.built:
        return Response({
            'error': f"Fewer than {options['min_questions']} usable PYQs for this note.",
            'counts': result.counts, 'counts_by_reason': result.counts_by_reason, 'build': build,
        }, status=status.HTTP_400_BAD_REQUEST)
    if options['dry_run']:
        build['preview'] = {'markdown': result.markdown, 'structured': result.structured}
    if note.pk:
        note.refresh_from_db()
    data = TopicNoteSerializer(note).data if note.pk else {}
    if shape == 'library':
        detail = ('Dry run: nothing was saved.' if options['dry_run']
                  else ('Note generated.' if result.changed else 'Note unchanged.'))
        return Response({'detail': detail, 'content': result.markdown if options['dry_run'] else note.content,
                         'note': data, 'build': build})
    return Response({**data, 'build': build})


class TopicNoteBuildView(APIView):
    """POST /api/questions/topic-notes/build/ (admin).

    Body: ``exam_type`` (cms | neet_pg | ini_cet | all; default cms), ``combined`` (build the
    cross-exam notes instead), ``level`` (subject | topic | both; default subject), ``subject`` /
    ``topic`` (ids, optional), ``mode``, ``min_questions``, ``include_provisional``,
    ``verified_only``, ``force``, ``dry_run``. Creates missing draft notes (never publishes) and
    builds them; more than 25 notes go to the background worker (202 ``{task_id}``)."""
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'ai_heavy'

    def get_throttles(self):
        return generation_throttles(self.request, super().get_throttles())

    def post(self, request):
        if not nb.builder_enabled():
            return _disabled()
        options, error = parse_build_options(request.data)
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data if hasattr(request.data, 'get') else {}
        exam_type = str(data.get('exam_type') or 'cms').strip().lower()
        if exam_type not in (*nb.EXAMS, 'all'):
            return Response({'error': 'exam_type must be cms, neet_pg, ini_cet or all'}, status=400)
        level = str(data.get('level') or 'subject').strip().lower()
        if level not in ('subject', 'topic', 'both'):
            return Response({'error': 'level must be subject, topic or both'}, status=400)
        combined = _flag(data, 'combined')
        params = {
            **options,
            'exams': () if combined else (nb.EXAMS if exam_type == 'all' else (exam_type,)),
            'combined': combined,
            'levels': ('subject', 'topic') if level == 'both' else (level,),
            'subject_id': _int(data.get('subject'), None, 1, 2 ** 31) if data.get('subject') not in (None, '') else None,
            'topic_id': _int(data.get('topic'), None, 1, 2 ** 31) if data.get('topic') not in (None, '') else None,
        }
        specs = nb.plan_notes(exams=params['exams'], combined=combined, levels=params['levels'],
                              subject_id=params['subject_id'], topic_id=params['topic_id'],
                              min_questions=params['min_questions'])
        if not specs:
            return Response({'error': f"No subject / topic has {params['min_questions']} or more active dated PYQs "
                                      f"for this selection.", 'notes': 0}, status=status.HTTP_400_BAD_REQUEST)
        if len(specs) > ASYNC_THRESHOLD and not options['dry_run']:
            from django_q.tasks import async_task
            task_id = async_task('questions.tasks_notes.build_topic_notes_task', params, timeout=3600)
            return Response({'queued': True, 'task_id': task_id, 'notes': len(specs)}, status=status.HTTP_202_ACCEPTED)
        report = nb.run_build(params, apply=not options['dry_run'])
        return Response(report)


class TopicNoteSourcesView(APIView):
    """GET /api/questions/topic-notes/library/<pk>/sources/ (admin): every question a built note
    cites or excluded, with its key status, reason and whether it changed since the build."""
    permission_classes = [IsControlTowerAdmin]

    def get(self, request, pk):
        if not nb.builder_enabled():
            return _disabled()
        note = TopicNote.objects.filter(pk=pk).first()
        if note is None:
            return Response({'error': 'TopicNote not found'}, status=status.HTTP_404_NOT_FOUND)
        rows = TopicNoteSource.objects.filter(note=note).select_related('question').order_by(
            '-cited', 'key_status', 'question_id')
        cited = request.query_params.get('cited')
        if cited not in (None, ''):
            rows = rows.filter(cited=nb._truthy(cited))
        hidden = nb.source_state([note.pk])[note.pk]['hidden']
        data = TopicNoteSourceSerializer(rows[:2000], many=True, context={'hidden': hidden}).data
        counts = {
            'cited': TopicNoteSource.objects.filter(note=note, cited=True).count(),
            'not_cited': TopicNoteSource.objects.filter(note=note, cited=False).count(),
            'changed_since_build': len(hidden),
        }
        return Response({'note_id': note.pk, 'is_stale': note.is_stale or bool(hidden),
                         'builder_version': note.builder_version, 'built_at': note.built_at,
                         'excluded_reasons': (note.structured or {}).get('excluded_reasons', {}),
                         'counts': counts, 'results': data})


class PublishedTopicNoteDetailView(APIView):
    """GET /api/questions/topic-notes/published/<pk>/: one published note for the caller.

    Staff / premium read every point; free accounts the points whose questions are all free
    showcase questions (``locked_points`` counts the rest; empty sections are dropped). Points
    whose questions changed since the build are hidden and the note is marked stale."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if not nb.builder_enabled():
            return _disabled()
        from questions.views import _is_staff_user

        notes = TopicNote.objects.select_related('subject', 'topic').filter(pk=pk, is_active=True)
        if not _is_staff_user(request.user):
            notes = notes.filter(is_published=True)
        note = notes.first()
        if note is None:
            return Response({'error': 'Note not found'}, status=status.HTTP_404_NOT_FOUND)
        views = _views_for([note], request)
        return Response(PublishedTopicNoteSerializer(note, context={'views': views, 'detail': True,
                                                                     'request': request}).data)
