"""Figures from the question bank that relate to an AI Tutor question (2026-11).

The tutor answers in text; many topics are clearer with an image (an ECG, a radiograph, a specimen).
The bank holds such figures with past questions, and students already see them in practice, so the
tutor shows up to four of them next to an answer, each linked to its question. No textbook pages
(students never see full copyrighted pages) and no images from the internet.

* Only stem-side figures (stored role primary / option / illustration) of active questions; never an
  explanation figure. Each figure is serialized with ``serialize_image_for_student(revealed=False)``
  (neutral alt text, no caption that names the answer).
* Free viewers only get questions they may open (``questions.views.free_showcase_rows``); premium and
  staff get every active question. Scholarship-challenge questions are never used.
* Matching is lexical: words of the question text, the figure's alt text and any caption that does not
  reveal the answer, weighted by rarity (IDF) over the figure questions. A figure needs two shared words,
  or one rare one, so a vague query returns nothing rather than a random image.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

CACHE_KEY = 'ai:related_figures:index:v1'
CACHE_SECONDS = 15 * 60
STEM_ROLES = ('primary', 'option', 'illustration')
MAX_RESULTS = 4
MAX_QUERY_CHARS = 2000

_WORD_RE = re.compile(r'[a-z][a-z0-9\-]{2,}')
_STOP = frozenset('''
the and for with that this from which what when where who whom whose why how are was were been being have has had
not but all any can may might must shall should will would into onto over under about above below between after
before during most more less least very much many some such than then there these those their they them its it's
patient patients following true false except correct incorrect regarding statement statements given shown image
images figure picture photograph identify diagnosis likely probable common commonly seen case year years old male
female man woman boy girl child presents presented presenting history examination features feature finding
findings option options answer best next step management treatment drug drugs explain describe pathophysiology
cause causes caused due also used use using one two three four type types know about tell please
'''.split())


def tokens(text: str) -> set:
    words = _WORD_RE.findall((text or '').lower())
    return {w.strip('-') for w in words if w not in _STOP and len(w.strip('-')) >= 3}


def _build_index() -> list:
    from questions.models import QuestionImage

    rows = {}
    images = (QuestionImage.objects
              .filter(is_active=True, role__in=STEM_ROLES, question__is_active=True,
                      question__is_scholarship_eligible=False)
              .select_related('question', 'question__subject')
              .only('id', 'role', 'alt_text', 'caption', 'caption_reveals_answer', 'page_number',
                    'image_index_in_page', 'question__id', 'question__question_text', 'question__exam_type',
                    'question__year', 'question__subject__name')
              .order_by('question_id', 'page_number', 'image_index_in_page', 'id'))
    for img in images:
        q = img.question
        row = rows.setdefault(q.pk, {'question_id': q.pk, 'image_id': img.id, 'exam_type': q.exam_type,
                                     'year': q.year, 'subject': q.subject.name if q.subject_id else '',
                                     'text': (q.question_text or '')[:1200], 'extra': []})
        row['extra'].append(img.alt_text or '')
        if img.caption and not img.caption_reveals_answer:
            row['extra'].append(img.caption)
    index = []
    for row in rows.values():
        words = tokens(row['text'] + ' ' + ' '.join(row.pop('extra')))
        if words:
            row['tokens'] = sorted(words)
            index.append(row)
    return index


def figure_index() -> list:
    index = cache.get(CACHE_KEY)
    if index is None:
        index = _build_index()
        cache.set(CACHE_KEY, index, CACHE_SECONDS)
    return index


def related_figures(query: str, *, allowed_ids=None, limit: int = MAX_RESULTS) -> list:
    """Best-matching index rows for ``query`` (``allowed_ids``: restrict to these question ids)."""
    wanted = tokens((query or '')[:MAX_QUERY_CHARS])
    if not wanted:
        return []
    index = figure_index()
    if not index:
        return []
    df = Counter(word for row in index for word in row['tokens'] if word in wanted)
    n = len(index)
    weight = {word: math.log((n + 1) / (df[word] + 0.5)) for word in wanted if df[word]}
    rare = math.log((n + 1) / 3.5)   # a word on at most ~3 figure questions
    scored = []
    for row in index:
        if allowed_ids is not None and row['question_id'] not in allowed_ids:
            continue
        shared = [word for word in row['tokens'] if word in weight]
        if not shared:
            continue
        if len(shared) < 2 and max(weight[w] for w in shared) < rare:
            continue
        scored.append((sum(weight[w] for w in shared), len(shared), row))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]['question_id']))
    return [row for _score, _n, row in scored[:max(0, limit)]]


class RelatedFiguresView(APIView):
    """``GET /api/ai/related-figures/?q=<text>`` -> ``{figures: [...]}`` (authenticated; no token cost)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = 'ai_figures'

    def get(self, request):
        from accounts.utils import is_premium
        from questions.image_context import serialize_image_for_student
        from questions.models import Question, QuestionImage
        from questions.views import free_showcase_rows

        query = (request.query_params.get('q') or '').strip()
        if not query:
            return Response({'figures': []})
        staff = bool(getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)
                     or getattr(request.user, 'is_admin', False))
        allowed = None
        if not (staff or is_premium(request.user)):
            allowed = set(free_showcase_rows().values_list('question_id', flat=True))
        rows = related_figures(query, allowed_ids=allowed)
        if not rows:
            return Response({'figures': []})
        questions = {q.pk: q for q in Question.objects.filter(pk__in=[r['question_id'] for r in rows], is_active=True)}
        images = {img.pk: img for img in QuestionImage.objects.filter(
            pk__in=[r['image_id'] for r in rows], is_active=True)}
        figures = []
        for row in rows:
            question, img = questions.get(row['question_id']), images.get(row['image_id'])
            if question is None or img is None:
                continue   # changed since the index was built
            stem = ' '.join(re.sub(r'\[\[img:\d+\]\]', ' ', question.question_text or '').split())
            figures.append({
                'question_id': question.pk,
                'exam_type': question.exam_type,
                'year': question.year,
                'subject': row['subject'],
                'stem': stem[:160] + ('…' if len(stem) > 160 else ''),
                'image': serialize_image_for_student(img, revealed=False, question=question, request=request),
            })
        return Response({'figures': figures})
