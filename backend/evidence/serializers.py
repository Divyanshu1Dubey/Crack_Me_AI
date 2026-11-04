"""Payload dicts of the admin evidence endpoints (students use services.student_citations).

Admin payloads carry the source sha256 (the page viewer needs it) and the stored snippet, never a
server file path. Users are referred to by id only.
"""
from __future__ import annotations

from .access import figure_url
from .services import citation_label, is_current, is_section_unit, source_student_displayable


def source_dict(source, *, evidence_count=None) -> dict:
    data = {
        'id': source.pk,
        'sha256': source.sha256,
        'title': source.title,
        'edition': source.edition,
        'year': source.year,
        'kind': source.kind,
        'tier': source.tier,
        'subject': source.subject,
        'licence': source.licence,
        'student_display': source.student_display,
        'student_displayable': source_student_displayable(source),
        'page_unit': 'section' if is_section_unit(source) else 'page',
        'page_count': source.page_count,
        'metadata_source': source.metadata_source,
        'metadata_verified': source.metadata_verified,
        'is_active': source.is_active,
    }
    if evidence_count is not None:
        data['evidence_count'] = evidence_count
    return data


def figure_dict(figure, request=None) -> dict | None:
    if figure is None:
        return None
    return {
        'id': figure.pk,
        'page_no': figure.page_no,
        'bbox': figure.bbox,
        'width': figure.width,
        'height': figure.height,
        'url': figure_url(figure.pk, request) if figure.image else None,
        'created_at': figure.created_at,
    }


def admin_row(row, *, question=None, request=None) -> dict:
    question = question if question is not None else row.question
    return {
        'id': row.pk,
        'question_id': row.question_id,
        'question_image_id': row.question_image_id,
        'source': source_dict(row.source),
        'citation': citation_label(row),
        'page_start': row.page_start,
        'page_end': row.page_end,
        'page_label': row.page_label,
        'chapter': row.chapter,
        'snippet': row.snippet,
        'quote_verified': row.quote_verified,
        'char_start': row.char_start,
        'char_end': row.char_end,
        'bbox': row.bbox,
        'figure': figure_dict(row.figure, request) if row.figure_id else None,
        'option_letter': row.option_letter,
        'stance': row.stance,
        'score': row.score,
        'retrieval_method': row.retrieval_method,
        'origin': row.origin,
        'run_ref': row.run_ref,
        'review_status': row.review_status,
        'student_visible': row.student_visible,
        'is_current': is_current(row, question),
        'key_at_creation': row.key_at_creation,
        'stale_reason': row.stale_reason,
        'created_by_id': row.created_by_id,
        'reviewed_by_id': row.reviewed_by_id,
        'reviewed_at': row.reviewed_at,
        'created_at': row.created_at,
        'updated_at': row.updated_at,
    }


def option_counts(rows, question) -> dict:
    """Per option: current accepted / pending rows that support or contradict it."""
    counts = {letter: {'supports': 0, 'contradicts': 0, 'pending': 0} for letter in ('A', 'B', 'C', 'D')}
    for row in rows:
        letter = row.option_letter
        if letter not in counts or not is_current(row, question):
            continue
        if row.review_status == 'pending':
            counts[letter]['pending'] += 1
        elif row.stance in ('supports', 'contradicts'):
            counts[letter][row.stance] += 1
    return counts
