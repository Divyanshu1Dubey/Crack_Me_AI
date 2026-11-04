"""Evidence endpoints under /api/evidence/ (docs/audit/MEDICAL_ACCURACY_DESIGN.md, images group).

Admin (``IsControlTowerAdmin``, throttle scope ``evidence_admin``):
  GET    ''                                       evidence rows, filters question_id / status / origin / stance / source
  GET    questions/<qid>/                         question key + image context, figures, recall pages, all evidence rows
  POST   questions/<qid>/                         manual link {source_sha256, page_start, page_end?, snippet,
                                                  option_letter?, stance?, bbox?, question_image_id?, review_status?,
                                                  student_visible?, note?}; 400 snippet_not_on_page when the text is
                                                  not on the page
  GET    <id>/                                    one row
  PATCH  <id>/                                    review {status, stance?, option_letter?, student_visible?, note?}
  DELETE <id>/                                    reject (rows are never deleted)
  POST   <id>/figure/                             crop {bbox: [x0, y0, x1, y1] PDF points, dpi?}
  GET    sources/?q=&tier=&kind=                  evidence sources
  GET    search/?q=&question_id=&option=&k=       candidate passages from the reference store
  GET    pages/<sha256 or prefix>/<page>/?q=      page text + highlights          (private, no-store)
  GET    pages/<sha256 or prefix>/<page>/image.png?dpi=   full page image         (private, no-store)
  GET    recall-pages/<question_source_id>/image.png?dpi=  the question's recall PDF page (private, no-store)

Student:
  GET    questions/<qid>/citations/               accepted, student-visible, current citations for a viewer entitled
                                                  to the answer; anyone else gets ``{citations: [], locked: true}``
                                                  (HTTP 200, like the reveal panel's other GETs: a 402 would open
                                                  the paywall from a panel); throttle scope ``evidence_student``
  GET    figures/<id>/?t=                         a figure crop: admins, or a valid signed token for that figure

Students never receive file paths, sha256 hashes, page text or full pages.
"""
from __future__ import annotations

import logging
import re

from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions.models import Question, QuestionImage, QuestionSource

from . import services
from .access import TOKEN_PARAM, figure_token_is_valid
from .models import EvidenceFigure, EvidenceSource, QuestionEvidence
from .rendering import clamp_dpi, render_pdf_page
from .serializers import admin_row, figure_dict, option_counts, source_dict

logger = logging.getLogger(__name__)

IMAGE_RESPONSE_CSP = "default-src 'none'; sandbox"
MAX_LIST_PAGE_SIZE = 100
MAX_SEARCH_K = 20
MAX_HIT_TEXT = 1500
MAX_HIGHLIGHTS = 50
_TRUE = ('1', 'true', 'yes', 'y', 'on')


def _is_admin(user) -> bool:
    return bool(user is not None and getattr(user, 'is_authenticated', False)
                and (getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False)))


def _error(exc: services.EvidenceError) -> Response:
    body = {'code': exc.code, 'detail': str(exc)}
    body.update({k: v for k, v in exc.detail.items() if k not in body})
    return Response(body, status=exc.status)


def _bad(code: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({'code': code, 'detail': detail}, status=status_code)


def _no_store(resp):
    resp['Cache-Control'] = 'private, no-store'
    return resp


def _harden(resp):
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Content-Security-Policy'] = IMAGE_RESPONSE_CSP
    return resp


def _png_response(data: bytes):
    return _no_store(_harden(HttpResponse(data, content_type='image/png')))


def _bool(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class _AdminView(APIView):
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'evidence_admin'


def _question_or_404(qid):
    question = Question.objects.filter(pk=qid).first()
    if question is None:
        raise Http404('Question not found')
    return question


class EvidenceListView(_AdminView):
    def get(self, request):
        params = request.query_params
        qs = QuestionEvidence.objects.select_related('source', 'figure', 'question').order_by('-updated_at', '-id')
        question_id = _int(params.get('question_id'))
        if question_id:
            qs = qs.filter(question_id=question_id)
        for name, field in (('status', 'review_status'), ('origin', 'origin'), ('stance', 'stance')):
            value = (params.get(name) or '').strip()
            if value:
                qs = qs.filter(**{field: value})
        source = (params.get('source') or '').strip().lower()
        if source:
            if not re.fullmatch(r'[0-9a-f]{8,64}', source):
                return _bad('invalid_source', 'source must be a sha256 or a prefix of at least 8 hex characters')
            qs = qs.filter(source__sha256__startswith=source)
        page_size = max(1, min(_int(params.get('page_size'), 50), MAX_LIST_PAGE_SIZE))
        page = max(1, _int(params.get('page'), 1))
        total = qs.count()
        rows = list(qs[(page - 1) * page_size: page * page_size])
        return Response({'count': total, 'page': page, 'page_size': page_size,
                         'results': [admin_row(row, request=request) for row in rows]})


class QuestionEvidenceView(_AdminView):
    def get(self, request, qid):
        from questions.image_context import active_images, image_context, serialize_image_for_admin
        from questions.content_hashes import stem_hash, valid_key

        question = _question_or_404(qid)
        rows = list(QuestionEvidence.objects.filter(question=question).select_related('source', 'figure')
                    .order_by('source__tier', '-score', 'id'))
        images = active_images(question)
        memo: dict = {}
        recall_pages = [
            {
                'id': qs_row.pk,
                'recall_source_id': qs_row.recall_source_id,
                'file_name': qs_row.recall_source.pdf_filename,
                'page_number': qs_row.page_number,
                'question_number_in_pdf': qs_row.question_number_in_pdf,
                'image_url': f'/api/evidence/recall-pages/{qs_row.pk}/image.png',
            }
            for qs_row in QuestionSource.objects.filter(question=question).select_related('recall_source')
            .order_by('recall_source_id', 'page_number', 'id')
        ]
        return Response({
            'question': {
                'id': question.pk,
                'correct_answer': valid_key(question.correct_answer),
                'stem_hash': stem_hash(question),
                'is_image_based': question.is_image_based,
                'question_type': question.question_type,
                'answer_key_status': getattr(question, 'answer_key_status', ''),
                'is_active': question.is_active,
            },
            'image_context': image_context(question, images=images),
            'images': [serialize_image_for_admin(img, question=question, request=request, memo=memo) for img in images],
            'recall_pages': recall_pages,
            'evidence': [admin_row(row, question=question, request=request) for row in rows],
            'option_counts': option_counts(rows, question),
            'store_available': services.store_available(),
        })

    def post(self, request, qid):
        question = _question_or_404(qid)
        data = request.data
        sha = str(data.get('source_sha256') or data.get('sha256') or '').strip()
        page_start = _int(data.get('page_start', data.get('page')))
        snippet = data.get('snippet') if isinstance(data.get('snippet'), str) else ''
        if not sha or page_start is None or not snippet.strip():
            return _bad('invalid_evidence', 'source_sha256, page_start and snippet are required')
        stance = str(data.get('stance') or 'supports')
        review_status = str(data.get('review_status') or 'accepted')
        if review_status not in ('accepted', 'pending'):
            return _bad('invalid_evidence', "review_status must be 'accepted' or 'pending'")
        question_image = None
        image_id = data.get('question_image_id')
        if image_id not in (None, ''):
            question_image = QuestionImage.objects.filter(pk=_int(image_id, -1), question=question).first()
            if question_image is None:
                return _bad('invalid_evidence', 'question_image_id is not an image of this question')
        source = services.resolve_source(sha)
        if source is None:
            return _bad('unknown_source', 'no evidence source with this sha256')
        try:
            row = services.link_manual(
                question, actor=request.user, sha256=source.sha256, page_start=page_start,
                page_end=_int(data.get('page_end')), snippet=snippet, option_letter=data.get('option_letter') or '',
                stance=stance, bbox=data.get('bbox'), question_image=question_image,
                accept=review_status == 'accepted', student_visible=_bool(data.get('student_visible')),
                note=str(data.get('note') or '')[:2000],
            )
        except services.EvidenceError as exc:
            return _error(exc)
        row = QuestionEvidence.objects.select_related('source', 'figure').get(pk=row.pk)
        return Response(admin_row(row, question=question, request=request), status=status.HTTP_201_CREATED)


class EvidenceDetailView(_AdminView):
    def _row(self, pk):
        row = QuestionEvidence.objects.select_related('source', 'figure', 'question').filter(pk=pk).first()
        if row is None:
            raise Http404('Evidence not found')
        return row

    def get(self, request, pk):
        return Response(admin_row(self._row(pk), request=request))

    def patch(self, request, pk):
        row = self._row(pk)
        data = request.data
        status_value = str(data.get('status') or data.get('review_status') or row.review_status)
        if status_value == 'stale':
            return _bad('invalid_evidence', "give status 'accepted', 'rejected' or 'pending' (rows become "
                                            "'stale' only when the question changes)")
        try:
            services.review(
                row, actor=request.user, status=status_value, stance=data.get('stance'),
                option_letter=data.get('option_letter') if 'option_letter' in data else None,
                student_visible=_bool(data.get('student_visible')), note=str(data.get('note') or ''),
            )
        except services.EvidenceError as exc:
            return _error(exc)
        return Response(admin_row(self._row(pk), request=request))

    def delete(self, request, pk):
        row = self._row(pk)
        body = request.data if hasattr(request.data, 'get') else {}
        try:
            services.review(row, actor=request.user, status='rejected', note=str(body.get('note') or 'rejected'))
        except services.EvidenceError as exc:
            return _error(exc)
        return Response(admin_row(self._row(pk), request=request))


class EvidenceFigureCreateView(_AdminView):
    def post(self, request, pk):
        row = QuestionEvidence.objects.filter(pk=pk).first()
        if row is None:
            raise Http404('Evidence not found')
        try:
            figure = services.create_figure(row, actor=request.user, bbox=request.data.get('bbox'),
                                            dpi=_int(request.data.get('dpi'), services.DEFAULT_FIGURE_DPI))
        except services.EvidenceError as exc:
            return _error(exc)
        return Response(figure_dict(figure, request), status=status.HTTP_201_CREATED)


class EvidenceSourceListView(_AdminView):
    def get(self, request):
        params = request.query_params
        qs = EvidenceSource.objects.annotate(evidence_count=Count('question_evidence')).order_by('tier', 'title')
        q = (params.get('q') or '').strip()[:200]
        if q:
            qs = qs.filter(title__icontains=q)
        tier = _int(params.get('tier'))
        if tier:
            qs = qs.filter(tier=tier)
        kind = (params.get('kind') or '').strip()
        if kind:
            qs = qs.filter(kind=kind)
        active = _bool(params.get('active'))
        if active is not None:
            qs = qs.filter(is_active=active)
        rows = list(qs[:200])
        return Response({'count': len(rows), 'store_available': services.store_available(),
                         'results': [source_dict(src, evidence_count=src.evidence_count) for src in rows]})


def _source_or_404(sha):
    source = services.resolve_source(sha)
    if source is None:
        raise Http404('Unknown source')
    return source


def _check_page(source, page_no):
    if page_no < 1 or (source.page_count and page_no > source.page_count):
        raise Http404('Page out of range')


class EvidencePageView(_AdminView):
    def get(self, request, sha, page_no):
        source = _source_or_404(sha)
        _check_page(source, page_no)
        data = services.page_text(source.sha256, page_no)
        if data is None:
            code = 'page_unavailable' if services.store_available() else 'reference_store_unavailable'
            return _no_store(_bad(code, 'the page text is not available here', status.HTTP_503_SERVICE_UNAVAILABLE))
        text = data['text']
        highlights = []
        q = (request.query_params.get('q') or '').strip()[:300]
        if q:
            found = services.locate_snippet(text, q)
            if found:
                highlights.append({'start': found[0], 'end': found[1]})
            else:
                for match in re.finditer(re.escape(q), text, re.IGNORECASE):
                    highlights.append({'start': match.start(), 'end': match.end()})
                    if len(highlights) >= MAX_HIGHLIGHTS:
                        break
        labels = source.page_labels if isinstance(source.page_labels, dict) else {}
        return _no_store(Response({
            'source': source_dict(source),
            'page_no': page_no,
            'page_label': (data.get('page_label') or labels.get(str(page_no), '') or '').strip(),
            'chapter': (data.get('chapter') or '').strip(),
            'text': text,
            'highlights': highlights,
            'image_url': f'/api/evidence/pages/{source.sha256}/{page_no}/image.png',
        }))


class EvidencePageImageView(_AdminView):
    def get(self, request, sha, page_no):
        source = _source_or_404(sha)
        _check_page(source, page_no)
        png = services.render_page_png(source.sha256, page_no, dpi=clamp_dpi(request.query_params.get('dpi')))
        if not png:
            return _no_store(_bad('page_image_unavailable', 'the page cannot be rendered here (file not on this server)',
                                  status.HTTP_503_SERVICE_UNAVAILABLE))
        return _png_response(png)


class RecallPageImageView(_AdminView):
    def get(self, request, qs_id):
        row = QuestionSource.objects.select_related('recall_source').filter(pk=qs_id).first()
        if row is None:
            raise Http404('Recall page not found')
        recall_source = row.recall_source
        dpi = clamp_dpi(request.query_params.get('dpi'))
        png = None
        if recall_source.pdf_sha256:
            png = services.render_page_png(recall_source.pdf_sha256, row.page_number, dpi=dpi)
        if not png:
            png = render_pdf_page(recall_source.pdf_path, row.page_number, dpi)
        if not png:
            return _no_store(_bad('page_image_unavailable', 'the recall PDF is not on this server',
                                  status.HTTP_503_SERVICE_UNAVAILABLE))
        return _png_response(png)


class EvidenceSearchView(_AdminView):
    def get(self, request):
        from questions.image_context import strip_tokens

        params = request.query_params
        query = (params.get('q') or '').strip()[:500]
        question_id = _int(params.get('question_id'))
        option = (params.get('option') or '').strip().upper()[:1]
        if option and option not in services.OPTION_LETTERS:
            return _bad('invalid_option', 'option must be A-D')
        question = Question.objects.filter(pk=question_id).first() if question_id else None
        if question_id and question is None:
            raise Http404('Question not found')
        if not query and question is not None:
            parts = [strip_tokens(question.question_text)]
            if option:
                parts.append(strip_tokens(getattr(question, f'option_{option.lower()}', '')))
            query = ' '.join(p for p in parts if p)[:500]
        if not query:
            return _bad('query_required', 'give q, or question_id (and option)')
        api = services.reference_api()
        if api is None:
            return _bad('reference_store_unavailable', 'the reference store is not available here',
                        status.HTTP_503_SERVICE_UNAVAILABLE)
        k = max(1, min(_int(params.get('k'), 8), MAX_SEARCH_K))
        try:
            hits = api.search(query, k=k, tiers=(1, 2, 3, 4), exclude_question_id=question.pk if question else None)
        except Exception as exc:  # noqa: BLE001 - the store is optional here
            logger.warning('evidence search failed (%s)', type(exc).__name__)
            return _bad('reference_store_unavailable', 'the reference store search failed',
                        status.HTTP_503_SERVICE_UNAVAILABLE)
        linked = set()
        if question is not None:
            linked = set(QuestionEvidence.objects.filter(question=question)
                         .values_list('source__sha256', 'page_start'))
        results = []
        for hit in hits or []:
            if not isinstance(hit, dict):
                continue
            src = hit.get('source') or {}
            sha = str(src.get('sha256') or '')
            results.append({
                'chunk_key': hit.get('chunk_key'),
                'source': {key: src.get(key) for key in ('sha256', 'title', 'edition', 'year', 'tier', 'kind')},
                'page_start': hit.get('page_start'),
                'page_end': hit.get('page_end'),
                'page_label': hit.get('page_label') or '',
                'section': hit.get('section') or '',
                'text': str(hit.get('text') or '')[:MAX_HIT_TEXT],
                'score': hit.get('score'),
                'retrieval_mode': hit.get('retrieval_mode') or '',
                'already_linked': (sha, hit.get('page_start')) in linked,
            })
        return Response({'query': query, 'results': results})


class StudentCitationsView(APIView):
    """Accepted, student-visible, current citations of one question for a viewer entitled to its
    answer: title, edition, chapter, page label and a short verified snippet, plus a signed figure
    crop where the source allows it.

    A citation names the option it supports, so it follows the answer's entitlement rule
    (``questions.views.user_can_view_answer``). A viewer who may not see the answer gets HTTP 200
    ``{citations: [], locked: true}`` -- nothing about the evidence, not even whether there is any --
    as the reveal panel's AI-text GETs do; a 402 would open the global upgrade dialog from a panel
    that only loads after the answer is shown."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'evidence_student'

    def get(self, request, qid):
        from questions.image_context import student_image_context
        from questions.views import user_can_view_answer

        question = Question.objects.filter(pk=qid).first()
        user = getattr(request, 'user', None)
        if question is None or (not question.is_active and not _is_admin(user)):
            raise Http404('Question not found')
        if not user_can_view_answer(user, question):
            return _no_store(Response({'question_id': question.pk, 'citations': [], 'locked': True}))
        citations = services.student_citations(question, revealed=True, request=request)
        return _no_store(Response({
            'question_id': question.pk,
            'citations': citations,
            'locked': False,
            'image_context': student_image_context(question),
        }))


class EvidenceFigureServeView(APIView):
    """A figure crop: admins always; anyone else with a valid ``?t=`` token for this figure, and
    only while the figure belongs to a citation students may see."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        figure = EvidenceFigure.objects.filter(pk=pk).first()
        if figure is None or not figure.image:
            raise Http404('Figure not found')
        admin = _is_admin(getattr(request, 'user', None))
        if not admin:
            if not figure_token_is_valid(pk, request.query_params.get(TOKEN_PARAM)):
                return Response({'code': 'figure_token_required',
                                 'detail': 'Figure links come with the citations; reload them for a fresh link.'},
                                status=status.HTTP_403_FORBIDDEN)
            if not services.figure_publicly_viewable(figure):
                raise Http404('Figure not found')
        try:
            handle = figure.image.open('rb')
        except (FileNotFoundError, OSError, ValueError):
            raise Http404('Figure not found')
        head = handle.read(8)
        handle.seek(0)
        if not head.startswith(b'\x89PNG\r\n\x1a\n'):
            handle.close()
            raise Http404('Figure not found')
        resp = _harden(FileResponse(handle, content_type='image/png'))
        resp['Cache-Control'] = 'private, no-store' if admin else 'private, max-age=300'
        return resp
