"""Which question figures this server can serve (2026-11-04). Read-only.

Supabase Storage was shut down on 2026-11-03. The image endpoint
(``/api/questions/images/<id>/serve/``) serves a figure from its image file (uploads since then, on
the volume), from MEDIA_ROOT (``/media/...`` addresses: recall imports, fixtures) or, for the old
Supabase addresses, from the restored copy (``SUPABASE_STORAGE_MIRROR_DIR``). This report counts,
for the active figures of active questions, where each figure's bytes come from and whether this
server has them, so a missing file shows up here instead of as a broken figure in front of a student.

Run it where the files are (the web container: the volume is mounted only there):
``GET /api/questions/images/health/`` as an admin, or ``python manage.py image_health``.
Figures on another live host (``external``) are served by a redirect and are not checked.
"""
from __future__ import annotations

from django.conf import settings

from .image_context import has_local_file, is_retired_storage_url

SOURCES = ('file', 'media', 'retired_storage', 'external', 'none')


def figure_source(img) -> str:
    """Where the image endpoint looks for this figure's bytes (see SOURCES)."""
    if getattr(img, 'file', None):
        return 'file'
    url = (getattr(img, 'url', '') or '').strip()
    if url.startswith('/media/'):
        return 'media'
    if is_retired_storage_url(url):
        return 'retired_storage'
    if url.startswith(('http://', 'https://')):
        return 'external'
    return 'none'


def image_health_report(*, sample_limit: int = 200) -> dict:
    """Counts per source, the number of figures this server cannot serve, and a sample of them
    (image id, question id, source) for the admin to re-upload. Ids only, no content."""
    from .models import QuestionImage

    by_source = {source: {'total': 0, 'missing': 0} for source in SOURCES}
    missing_sample = []
    questions_with_missing = set()
    rows = (QuestionImage.objects.filter(is_active=True, question__is_active=True)
            .only('id', 'question_id', 'file', 'url').order_by('question_id', 'id'))
    for img in rows.iterator(chunk_size=500):
        source = figure_source(img)
        by_source[source]['total'] += 1
        if source == 'external' or has_local_file(img):
            continue
        by_source[source]['missing'] += 1
        questions_with_missing.add(img.question_id)
        if len(missing_sample) < sample_limit:
            missing_sample.append({'image_id': img.id, 'question_id': img.question_id, 'source': source})
    total = sum(entry['total'] for entry in by_source.values())
    missing = sum(entry['missing'] for entry in by_source.values())
    external = by_source['external']['total']
    return {
        'total': total,
        'servable': total - missing - external,
        'missing': missing,
        'external_unchecked': external,
        'questions_with_missing_figures': len(questions_with_missing),
        'mirror_configured': bool(getattr(settings, 'SUPABASE_STORAGE_MIRROR_DIR', '')),
        'by_source': by_source,
        'missing_sample': missing_sample,
    }
