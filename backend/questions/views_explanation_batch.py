"""Admin API of the AI explanation batch and its review queue (questions/explanation_batch.py).

  GET  /api/questions/explanation-batches/                 how many questions need one + the runs
  POST /api/questions/explanation-batches/                 {exam_type, years, include_stale, limit, note}: a run
  POST /api/questions/explanation-batches/<id>/process/    {max_items, sleep_seconds}: queue processing (worker)
  GET  /api/questions/explanation-batches/<id>/items/      ?status=disagrees|invalid|failed|skipped|done&page=
  GET  /api/questions/explanation-review/                  AI-generated explanations not reviewed yet (?exam_type=)

Reviewing one is POST /api/questions/<id>/review-explanation/ (views_editorial); editing it is the question editor.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsControlTowerAdmin
from questions import explanation_batch as batch

PAGE_SIZE = 50


def _page(request):
    try:
        return max(1, int(request.query_params.get('page', 1)))
    except (TypeError, ValueError):
        return 1


def _preview(text, limit=240):
    text = ' '.join(str(text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


class ExplanationBatchListView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        from questions.models import ExplanationBatchRun

        needed = batch.needed_by_exam()
        runs = [batch.run_summary(run) for run in ExplanationBatchRun.objects.all()[:20]]
        return Response({'needed': {'total': sum(needed.values()), 'by_exam': needed}, 'runs': runs})

    def post(self, request):
        data = request.data or {}
        exam_type = str(data.get('exam_type') or '').strip() or None
        try:
            years = [int(y) for y in (data.get('years') or [])]
            limit = int(data.get('limit') or 0) or None
        except (TypeError, ValueError):
            return Response({'error': 'years must be numbers, limit a number'}, status=status.HTTP_400_BAD_REQUEST)
        run = batch.create_run(exam_type=exam_type, years=years or None,
                               include_stale=bool(data.get('include_stale', True)), limit=limit, user=request.user,
                               note=str(data.get('note') or ''))
        return Response(batch.run_summary(run), status=status.HTTP_201_CREATED)


class ExplanationBatchProcessView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def post(self, request, pk):
        from ai_engine.offline import ai_offline_mode
        from django_q.tasks import async_task
        from questions.models import ExplanationBatchRun

        run = ExplanationBatchRun.objects.filter(pk=pk).first()
        if run is None:
            return Response({'error': 'No such run'}, status=status.HTTP_404_NOT_FOUND)
        if ai_offline_mode():
            return Response({'code': 'ai_offline', 'error': 'AI_OFFLINE_MODE is on: no explanation can be generated'},
                            status=status.HTTP_409_CONFLICT)
        try:
            max_items = min(max(int(request.data.get('max_items') or 100), 1), 500)
            sleep_seconds = min(max(float(request.data.get('sleep_seconds') or 1.0), 0.0), 30.0)
        except (TypeError, ValueError):
            return Response({'error': 'max_items and sleep_seconds must be numbers'},
                            status=status.HTTP_400_BAD_REQUEST)
        task_id = async_task('questions.tasks.run_explanation_batch_task', run.pk, max_items, sleep_seconds,
                             timeout=max(600, int(max_items * (sleep_seconds + 60))))
        return Response({'queued': True, 'task_id': task_id, 'max_items': max_items, **batch.run_summary(run)},
                        status=status.HTTP_202_ACCEPTED)


class ExplanationBatchItemsView(APIView):
    permission_classes = [IsControlTowerAdmin]

    def get(self, request, pk):
        from questions.models import ExplanationBatchItem

        items = ExplanationBatchItem.objects.filter(run_id=pk).select_related('question')
        wanted = request.query_params.get('status')
        if wanted:
            items = items.filter(status=wanted)
        page = _page(request)
        total = items.count()
        rows = items.order_by('pk')[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        return Response({'count': total, 'page': page, 'results': [{
            'question_id': item.question_id, 'status': item.status, 'detail': item.detail, 'attempts': item.attempts,
            'provider': item.provider, 'key': item.key, 'exam_type': item.question.exam_type,
            'year': item.question.year, 'paper': item.question.paper, 'display_number': item.question.display_number,
            'question_preview': _preview(item.question.question_text), 'updated_at': item.updated_at,
        } for item in rows]})


class ExplanationReviewQueueView(APIView):
    """AI-generated explanations nobody reviewed yet, newest first."""
    permission_classes = [IsControlTowerAdmin]

    def get(self, request):
        from questions.models import Question

        qs = Question.objects.filter(is_active=True, explanation_status='ai_generated').order_by('-updated_at', '-pk')
        exam_type = request.query_params.get('exam_type')
        if exam_type:
            qs = qs.filter(exam_type=exam_type)
        page = _page(request)
        total = qs.count()
        rows = qs.only('id', 'exam_type', 'year', 'paper', 'display_number', 'question_text', 'correct_answer',
                       'explanation', 'explanation_for_key', 'updated_at')[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        return Response({'count': total, 'page': page, 'results': [{
            'question_id': q.pk, 'exam_type': q.exam_type, 'year': q.year, 'paper': q.paper,
            'display_number': q.display_number, 'correct_answer': q.correct_answer,
            'question_preview': _preview(q.question_text), 'explanation': q.explanation or '',
            'explanation_for_key': q.explanation_for_key, 'updated_at': q.updated_at,
        } for q in rows]})
