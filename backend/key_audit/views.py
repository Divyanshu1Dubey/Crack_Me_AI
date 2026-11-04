"""Answer-key review queue API, under /api/key-audit/ (admin only).

* ``GET  queue/``                      audits, highest priority first; filters: ``status`` (comma list),
                                       ``reason``, ``exam``, ``year``, ``suggested_from``,
                                       ``has_suggestion=true``, ``unclaimed=true``, ``q`` (question id),
                                       ``include_inactive=true``
* ``GET  queue/summary/``              counts by status, by reason and by open signal
* ``GET  queue/<id>/``                 one audit with the question, signals, printed source keys, reviews
                                       (AI output labelled as a review signal), decisions, key history
* ``POST / DELETE queue/<id>/claim/``  claim a question for 15 minutes / release the claim
* ``POST queue/<id>/resolve/``         record a decision (``AuditResolution``, immutable); a key change goes
                                       through ``questions.editorial.change_answer_key`` and nothing else
* ``POST queue/accept-source-keys/``   accept the printed source key for up to 25 questions the reviewer
                                       ticked, each checked and recorded as its own decision

A decision never makes a key "verified" by itself: the audit re-classifies the question afterwards, and
only a decision that cites strong evidence (official key, errata, guideline, page-cited passage) gives
``verified``; one without is ``likely_correct``.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from key_audit.models import AuditResolution, QuestionAudit, ReviewClaim, SourceKey
from key_audit.serializers import (
    QuestionAuditDetailSerializer, QuestionAuditListSerializer, ResolveAuditRequestSerializer,
)
from key_audit.services import audit_questions
from questions.content_hashes import stem_hash, valid_key
from questions.models import Question

CLAIM_MINUTES = 15


class ReviewQueuePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class _AdminView(APIView):
    permission_classes = [IsControlTowerAdmin]
    throttle_scope = 'review_queue'


def _active_claims(question_ids=None) -> dict:
    qs = ReviewClaim.objects.filter(expires_at__gt=timezone.now()).select_related('claimed_by')
    if question_ids is not None:
        qs = qs.filter(question_id__in=list(question_ids))
    return {c.question_id: c for c in qs}


def _queue(request):
    params = request.query_params
    qs = QuestionAudit.objects.select_related('question', 'question__subject')
    if params.get('include_inactive') != 'true':
        qs = qs.filter(question__is_active=True, question__is_dropped=False)
    statuses = [s for s in (params.get('status') or '').split(',') if s]
    if statuses:
        qs = qs.filter(status__in=statuses)
    if params.get('reason'):
        qs = qs.filter(status_reason=params['reason'])
    if params.get('exam'):
        qs = qs.filter(question__exam_type=params['exam'])
    if params.get('year'):
        try:
            qs = qs.filter(question__year=int(params['year']))
        except ValueError:
            qs = qs.none()
    if params.get('has_suggestion') == 'true':
        qs = qs.exclude(suggested_key='')
    if params.get('suggested_from'):
        qs = qs.filter(evidence_summary__suggested_from=params['suggested_from'])
    if params.get('q'):
        try:
            qs = qs.filter(question_id=int(params['q']))
        except ValueError:
            qs = qs.none()
    if params.get('unclaimed') == 'true':   # hide what other reviewers hold; your own claims stay listed
        qs = qs.exclude(question_id__in=[qid for qid, claim in _active_claims().items()
                                         if claim.claimed_by_id != request.user.pk])
    return qs.order_by('-priority', 'question_id')


class ReviewQueueListView(_AdminView):
    def get(self, request):
        paginator = ReviewQueuePagination()
        page = paginator.paginate_queryset(_queue(request), request)
        claims = {qid: c.claimed_by.username for qid, c in _active_claims(a.question_id for a in page).items()}
        data = QuestionAuditListSerializer(page, many=True, context={'claims': claims}).data
        return paginator.get_paginated_response(data)


class ReviewQueueSummaryView(_AdminView):
    """Counts for the queue's tabs and filters (aggregated in the database; the open-signal counts read
    only the signal lists, cached for a minute)."""

    CACHE_SECONDS = 60

    def get(self, request):
        from django.core.cache import cache
        from django.db.models import Count
        from django.db.models.fields.json import KT

        qs = QuestionAudit.objects.all()
        include_inactive = request.query_params.get('include_inactive') == 'true'
        exam = request.query_params.get('exam') or ''
        if not include_inactive:
            qs = qs.filter(question__is_active=True, question__is_dropped=False)
        if exam:
            qs = qs.filter(question__exam_type=exam)
        statuses = Counter({row['status']: row['n'] for row in qs.values('status').annotate(n=Count('id'))})
        reasons = Counter({f"{row['status']}/{row['status_reason']}": row['n']
                           for row in qs.values('status', 'status_reason').annotate(n=Count('id'))})
        sources = Counter({row['source'] or 'unknown': row['n'] for row in qs.exclude(suggested_key='').annotate(
            source=KT('evidence_summary__suggested_from')).values('source').annotate(n=Count('id'))})
        from django.db.models import Max
        version = QuestionAudit.objects.aggregate(n=Count('id'), at=Max('updated_at'))
        stamp = version['at'].timestamp() if version['at'] else 0
        cache_key = f"key_audit:open_signals:{exam}:{int(include_inactive)}:{version['n']}:{stamp}"
        signals = cache.get(cache_key)
        if signals is None:
            counts = Counter()
            for row in qs.values_list('signals', flat=True).iterator(chunk_size=2000):
                for signal in row or []:
                    if signal.get('opens_review') and not signal.get('settled_by_review'):
                        counts[signal.get('code')] += 1
            signals = dict(counts.most_common())
            cache.set(cache_key, signals, self.CACHE_SECONDS)
        return Response({
            'total': sum(statuses.values()), 'stale': qs.filter(is_stale=True).count(),
            'status': dict(statuses.most_common()), 'reasons': dict(reasons.most_common()),
            'open_signals': signals, 'suggested_from': dict(sources.most_common()),
            'claimed': len(_active_claims()),
        })


class ReviewQueueDetailView(_AdminView):
    def get(self, request, question_id: int):
        audit = get_object_or_404(
            QuestionAudit.objects.select_related('question', 'question__subject', 'question__topic')
            .prefetch_related('question__images', 'question__source_keys'),
            question_id=question_id,
        )
        claim = _active_claims([question_id]).get(question_id)
        data = QuestionAuditDetailSerializer(audit, context={'claim': claim, 'user_id': request.user.pk}).data
        return Response(data)


class ReviewClaimView(_AdminView):
    def post(self, request, question_id: int):
        question = get_object_or_404(Question, pk=question_id)
        now = timezone.now()
        expires = now + timedelta(minutes=CLAIM_MINUTES)
        with transaction.atomic():
            claim = ReviewClaim.objects.select_for_update().filter(question=question).first()
            if claim is None:
                # Two requests can find no claim at once (a double click, React's development double
                # effect): the loser of the insert race reads the winner's row instead of failing.
                try:
                    with transaction.atomic():
                        claim = ReviewClaim.objects.create(question=question, claimed_by=request.user,
                                                           claimed_at=now, expires_at=expires)
                except IntegrityError:
                    claim = ReviewClaim.objects.select_for_update().get(question=question)
            if claim.expires_at > now and claim.claimed_by_id != request.user.pk:
                return Response({'code': 'claimed', 'claimed_by': claim.claimed_by.username,
                                 'expires_at': claim.expires_at}, status=status.HTTP_409_CONFLICT)
            if claim.claimed_by_id != request.user.pk or claim.expires_at != expires:
                claim.claimed_by, claim.claimed_at, claim.expires_at = request.user, now, expires
                claim.save(update_fields=['claimed_by', 'claimed_at', 'expires_at'])
        return Response({'question_id': question.pk, 'claimed_by': request.user.username, 'mine': True,
                         'expires_at': claim.expires_at})

    def delete(self, request, question_id: int):
        get_object_or_404(Question, pk=question_id)
        ReviewClaim.objects.filter(question_id=question_id, claimed_by=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewResolveView(_AdminView):
    def post(self, request, question_id: int):
        serializer = ResolveAuditRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        resolution = data['resolution']

        with transaction.atomic():
            question = get_object_or_404(Question.objects.select_for_update(), pk=question_id)
            audit = QuestionAudit.objects.select_for_update().filter(question=question).first()
            claim = ReviewClaim.objects.filter(question=question, expires_at__gt=timezone.now()).first()
            if claim and claim.claimed_by_id != request.user.pk:
                return Response({'code': 'claimed', 'claimed_by': claim.claimed_by.username,
                                 'expires_at': claim.expires_at}, status=status.HTTP_409_CONFLICT)
            current = valid_key(question.correct_answer)
            if data['expected_key'] and data['expected_key'] != current:
                return Response({'code': 'key_changed', 'current_key': current,
                                 'detail': 'The key changed since this question was loaded; reload it.'},
                                status=status.HTTP_409_CONFLICT)
            evidence = data['evidence']
            bad = self._check_source_keys(question, evidence)
            if bad:
                return Response({'evidence': [bad]}, status=status.HTTP_400_BAD_REQUEST)
            if resolution == 'key_confirmed' and not current:
                return Response({'resolution': ['The stored key is not A-D: change it instead of confirming it.']},
                                status=status.HTTP_400_BAD_REQUEST)

            status_before = audit.status if audit else ''
            key_change = None
            try:
                if resolution == 'key_changed':
                    from questions.editorial import change_answer_key
                    key_change = change_answer_key(
                        question, data['new_key'], actor=request.user, reason=data['reason'], evidence=evidence,
                        source='review_queue', explanation_fields=data['explanation_fields'] or None)
                elif resolution == 'explanation_fixed':
                    from questions.editorial import save_explanation
                    save_explanation(question, data['explanation_fields'], actor=request.user, for_key=current)
            except DjangoValidationError as exc:
                return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)

            if resolution == 'key_confirmed' and question.is_disputed:
                question.is_disputed = False
                question.save(update_fields=['is_disputed'])
            elif resolution == 'question_deactivated':
                question.is_active = False
                question.save(update_fields=['is_active'])
            elif resolution == 'dropped':
                question.is_dropped = True
                question.save(update_fields=['is_dropped'])

            question.refresh_from_db()
            record = AuditResolution.objects.create(
                question=question, audit=audit, resolution=resolution, reason=data['reason'], evidence=evidence,
                key_change=key_change, status_before=status_before, stored_key=valid_key(question.correct_answer),
                stem_hash=stem_hash(question), resolved_by=request.user,
            )
            ReviewClaim.objects.filter(question=question).delete()
            self._log(request, question, record, status_before)

        prepared = audit_questions([Question.objects.get(pk=question.pk)], save=True)[0]
        return Response({
            'question_id': question.pk, 'resolution_id': record.pk, 'resolution': resolution,
            'current_key': valid_key(question.correct_answer), 'key_change_id': key_change.pk if key_change else None,
            'audit_status': prepared.fields['status'], 'audit_reason': prepared.fields['status_reason'],
            'priority': prepared.fields['priority'],
        })

    @staticmethod
    def _check_source_keys(question, evidence) -> str:
        return check_source_key_evidence(question, evidence)

    @staticmethod
    def _log(request, question, record, status_before) -> None:
        log_resolution(request, question, record, status_before)


BATCH_MAX = 25


class ReviewBatchSourceKeyView(_AdminView):
    """Accept the printed source key for several questions the reviewer ticked, one decision each.

    ``POST queue/accept-source-keys/`` ``{reason, items: [{question_id, expected_key, source_key_id}]}``
    (at most 25). For every item: the key the reviewer saw is still the key, no other admin holds a claim,
    the SourceKey belongs to the question, is confident (stem located, option order checked) and was
    recovered for the current content, and names another letter. Each accepted item is its own
    ``change_answer_key(..., source='review_queue')`` with the source key as evidence (tier 4: the result
    is "likely correct", not "verified") and its own AuditResolution; a failing item does not stop the others.
    """

    def post(self, request):
        reason = (request.data.get('reason') or '').strip() if isinstance(request.data.get('reason'), str) else ''
        items = request.data.get('items')
        if len(reason) < 10:
            return Response({'reason': ['At least 10 characters.']}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(items, list) or not items or len(items) > BATCH_MAX:
            return Response({'items': [f'1 to {BATCH_MAX} items.']}, status=status.HTTP_400_BAD_REQUEST)
        results, seen = [], set()
        for item in items:
            qid = item.get('question_id') if isinstance(item, dict) else None
            if not isinstance(qid, int) or qid in seen:
                results.append({'question_id': qid, 'ok': False, 'error': 'bad_or_duplicate_item'})
                continue
            seen.add(qid)
            results.append(self._accept(request, qid, item, reason))
        refreshed = [r['question_id'] for r in results if r.get('ok')]
        if refreshed:
            prepared = {p.question.pk: p for p in audit_questions(list(Question.objects.filter(pk__in=refreshed)),
                                                                  save=True)}
            for row in results:
                if row.get('ok') and row['question_id'] in prepared:
                    row['audit_status'] = prepared[row['question_id']].fields['status']
        return Response({'accepted': len(refreshed), 'results': results})

    @staticmethod
    def _accept(request, qid, item, reason) -> dict:
        from questions.editorial import change_answer_key

        with transaction.atomic():
            question = Question.objects.select_for_update().filter(pk=qid).first()
            if question is None:
                return {'question_id': qid, 'ok': False, 'error': 'not_found'}
            claim = ReviewClaim.objects.filter(question=question, expires_at__gt=timezone.now()).first()
            if claim and claim.claimed_by_id != request.user.pk:
                return {'question_id': qid, 'ok': False, 'error': 'claimed'}
            current = valid_key(question.correct_answer)
            if valid_key(item.get('expected_key')) != current:
                return {'question_id': qid, 'ok': False, 'error': 'key_changed', 'current_key': current}
            row = SourceKey.objects.filter(question=question, pk=item.get('source_key_id')).first()
            if row is None or not row.confident:
                return {'question_id': qid, 'ok': False, 'error': 'not_a_confident_source_key'}
            if row.stem_hash != stem_hash(question):
                return {'question_id': qid, 'ok': False, 'error': 'source_key_for_other_content'}
            if row.letter == current:
                return {'question_id': qid, 'ok': False, 'error': 'already_this_key'}
            evidence = [{
                'kind': 'source_key', 'source_key_id': row.pk, 'source_title': row.source_file[:200],
                'page_label': f'PDF p. {row.question_page}'[:40],
                'text': (f'Q{row.question_number} prints {row.printed_letter}'
                         + (f' (answer table, PDF p. {row.answer_page})' if row.answer_page else ''))[:600],
            }]
            audit = QuestionAudit.objects.select_for_update().filter(question=question).first()
            status_before = audit.status if audit else ''
            change = change_answer_key(question, row.letter, actor=request.user, reason=reason, evidence=evidence,
                                       source='review_queue')
            record = AuditResolution.objects.create(
                question=question, audit=audit, resolution='key_changed', reason=reason, evidence=evidence,
                key_change=change, status_before=status_before, stored_key=row.letter, stem_hash=stem_hash(question),
                resolved_by=request.user)
            ReviewClaim.objects.filter(question=question).delete()
            log_resolution(request, question, record, status_before)
        return {'question_id': qid, 'ok': True, 'old_key': current, 'new_key': row.letter, 'key_change_id': change.pk}


def check_source_key_evidence(question, evidence) -> str:
    ids = [item['source_key_id'] for item in evidence if item.get('kind') == 'source_key']
    if not ids:
        return ''
    found = set(SourceKey.objects.filter(question=question, pk__in=ids).values_list('pk', flat=True))
    missing = sorted(set(ids) - found)
    return f'source_key_id {missing[0]} is not a source key of this question' if missing else ''


def log_resolution(request, question, record, status_before) -> None:
    try:
        from accounts.models import AdminAuditLog
        AdminAuditLog.objects.create(
            actor=request.user, action='audit_resolution', resource_type='question', resource_id=str(question.pk),
            detail=f'{record.resolution}: {record.reason[:200]}',
            metadata={'resolution_id': record.pk, 'status_before': status_before,
                      'key_change_id': record.key_change_id, 'stored_key': record.stored_key,
                      'evidence_kinds': [item.get('kind') for item in record.evidence]},
        )
    except Exception:  # noqa: BLE001 - the resolution itself is the record; the log is extra
        import logging
        logging.getLogger('key_audit.views').exception('admin audit log failed for question %s', question.pk)
