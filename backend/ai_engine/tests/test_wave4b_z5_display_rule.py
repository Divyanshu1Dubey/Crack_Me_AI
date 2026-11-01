"""Regression tests, wave 4b (group Z5-ai): the DISPLAY RULE in AI payloads.

The loader-created subject "Imported" is shown to students as "Expert
Curated" (questions.serializers.public_subject_name). The raw name used to
reach student-facing AI payloads:

* explain-answer ``category`` on every path: stored, cached, freshly
  generated (the prompt told the model to echo ``"category": "Imported"``
  and the result defaulted to it) and offline (the curated explanation and
  the empty offline shell copied Subject.name);
* explain-question: the ``context.subject`` stored in ai_explanation (the
  question detail payload carries that JSON) and its JSON last resort;
* high-yield: the question-bank fallback's ``## Imported`` heading, also
  when served from a cache filled before the fix (and an "Expert Curated"
  subject now shares that one, re-ranked section);
* knowledge base: the citation / search-result ``subject`` (defence in
  depth: today's connectors only write subject slugs).

Similar-PYQ metadata carries no subject at all; a test pins that.

No test reaches an AI provider: clients are never built, AI calls are
patched and the RAG store is never opened.
"""
import json
import os
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from ai_engine import offline
from ai_engine.services import AIService, AIUnavailable
from ai_engine.tests.test_wave2_answer_gate_and_fixes import OPTIONS, RICH, STEM, _Base

User = get_user_model()

RAW = 'Imported'
PUBLIC = 'Expert Curated'

GROUNDED = offline.OfflineAnswer(
    grounded=True,
    answer='> Offline answer\n\n- Digoxin toxicity causes bidirectional VT. *[Harrison p.1]*',
    citations=[{'book': 'Harrison', 'page': 1, 'excerpt': 'Digoxin toxicity causes bidirectional VT',
                'relevance': 0.8}],
    reason=offline.REASON_PROVIDERS_DOWN,
    body='- Digoxin toxicity causes bidirectional VT. *[Harrison p.1]*',
    sentences=[{'text': 'Digoxin toxicity causes bidirectional VT.', 'label': 'Harrison p.1'}],
)
NOT_GROUNDED = offline.OfflineAnswer(grounded=False, answer=offline.NO_GROUNDED_ANSWER)


class PublicSubjectHelperTests(SimpleTestCase):

    def test_only_the_loader_bucket_is_renamed(self):
        for raw in ('Imported', ' imported ', 'IMPORTED'):
            self.assertEqual(offline.public_subject(raw), PUBLIC, raw)
        for other in ('Medicine', 'Imported Drugs', PUBLIC, '', None):
            self.assertEqual(offline.public_subject(other), other, other)

    def test_explanation_category_and_context_subject_are_renamed(self):
        context = {'subject': RAW, 'year': 2019}
        payload = {'category': RAW, 'context': context, 'why_correct': 'Imported malaria is notifiable.'}
        self.assertIs(offline.with_public_subject(payload), payload)
        self.assertEqual(payload['category'], PUBLIC)
        self.assertEqual(payload['context'], {'subject': PUBLIC, 'year': 2019})
        self.assertEqual(context['subject'], RAW, 'the nested dict is replaced, not mutated')
        self.assertEqual(payload['why_correct'], 'Imported malaria is notifiable.', 'body text is not touched')

    def test_other_shapes_are_left_alone(self):
        self.assertEqual(offline.with_public_subject({'why_correct': 'x'}), {'why_correct': 'x'})
        self.assertEqual(offline.with_public_subject({'category': 'Surgery', 'context': 'n/a'}),
                         {'category': 'Surgery', 'context': 'n/a'})
        for value in (None, 'text', ['Imported']):
            self.assertEqual(offline.with_public_subject(value), value)


class _ImportedBase(_Base):
    """The wave-2 fixture with its question in the loader's "Imported" bucket."""

    def setUp(self):
        super().setUp()
        from questions.models import Subject
        self.q.subject = Subject.objects.create(name=RAW, code='IMPORTED')
        self.q.save()

    def assert_no_raw_subject(self, data):
        self.assertNotIn(RAW, json.dumps(data, ensure_ascii=False, default=str))

    def stored_json(self):
        self.q.refresh_from_db()
        return json.loads(self.q.ai_explanation)


# ─── explain-answer ─────────────────────────────────────────────────────

class ExplainAnswerDisplayTests(_ImportedBase):

    def ask(self):
        return self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)

    def test_stored_explanation_from_before_the_fix(self):
        self.store_rich({**RICH, 'category': RAW})
        with patch.object(AIService, '_call_ai') as call_ai:
            resp = self.ask()
        call_ai.assert_not_called()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        self.assertEqual(resp.data['category'], PUBLIC)
        self.assert_no_raw_subject(resp.data)

    def test_cached_explanation_from_before_the_fix(self):
        cache.set(AIService.explanation_cache_key(STEM, OPTIONS, 'C', self.q.id), {**RICH, 'category': RAW}, 60)
        with patch.object(AIService, '_call_ai') as call_ai:
            resp = self.ask()
        call_ai.assert_not_called()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['category'], PUBLIC)
        self.assert_no_raw_subject(resp.data)

    def test_generation_prompt_result_store_and_cache_use_the_public_label(self):
        prompts = []

        def model(prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps({**RICH, 'category': RAW})  # a model still echoing the raw name

        with patch.object(AIService, '_call_ai', side_effect=model):
            resp = self.ask()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['category'], PUBLIC)
        self.assert_no_raw_subject(resp.data)
        self.assertEqual(len(prompts), 1)
        self.assertIn(f'Subject: {PUBLIC}', prompts[0])
        self.assertIn(f'"category": "{PUBLIC}"', prompts[0])
        self.assertNotIn(RAW, prompts[0])
        self.assertEqual(self.stored_json()['category'], PUBLIC)
        cached = cache.get(AIService.explanation_cache_key(STEM, OPTIONS, 'C', self.q.id))
        self.assertEqual(cached['category'], PUBLIC)

    def test_model_without_a_category_defaults_to_the_public_label(self):
        with patch.object(AIService, '_call_ai', return_value=json.dumps(RICH)):
            resp = self.ask()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['category'], PUBLIC)

    def test_offline_mode_curated_explanation(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                patch('ai_engine.views.compose_offline_answer', return_value=NOT_GROUNDED):
            resp = self.ask()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['offline'])
        self.assertEqual(resp.data['why_correct'], self.q.explanation)
        self.assertEqual(resp.data['category'], PUBLIC)
        self.assert_no_raw_subject(resp.data)

    def test_outage_offline_shell_without_a_curated_explanation(self):
        self.q.explanation = ''
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer', return_value=GROUNDED):
            resp = self.ask()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['offline'])
        self.assertIn('Digoxin toxicity causes bidirectional VT.', resp.data['why_correct'])
        self.assertEqual(resp.data['category'], PUBLIC)
        self.assert_no_raw_subject(resp.data)

    def test_kept_explain_question_context_is_stored_with_the_public_label(self):
        self.q.ai_explanation = json.dumps({'analysis': 'Shared analysis', 'context': {'subject': RAW}})
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)):
            resp = self.ask()
        self.assertEqual(resp.status_code, 200, resp.data)
        stored = self.stored_json()
        self.assertEqual(stored['analysis'], 'Shared analysis')
        self.assertEqual(stored['context'], {'subject': PUBLIC})


class RealSubjectIsUnchangedTests(_Base):

    def test_a_real_subject_reaches_prompt_and_category_as_is(self):
        prompts = []

        def model(prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps(RICH)

        with patch.object(AIService, '_call_ai', side_effect=model):
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['category'], 'Medicine W4')
        self.assertIn('Subject: Medicine W4', prompts[0])


# ─── explain-question ───────────────────────────────────────────────────

class ExplainQuestionDisplayTests(_ImportedBase):

    def test_stored_context_subject_is_the_public_label(self):
        with patch.object(AIService, 'analyze_question', return_value='## Analysis\nDigoxin toxicity.'):
            resp = self.explain_question({}, self.premium)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['persisted'])
        self.assertEqual(self.stored_json()['context']['subject'], PUBLIC)

    def test_json_last_resort_never_shows_the_raw_subject(self):
        inner = {'topic_deep_dive': 'Digoxin inhibits the Na/K ATPase.', 'category': RAW}
        self.q.ai_explanation = json.dumps({'analysis': json.dumps(inner), 'context': {'subject': RAW}})
        self.q.save()
        with patch.object(AIService, 'analyze_question') as analyze:
            resp = self.explain_question({}, self.premium)
        analyze.assert_not_called()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['cached'])
        self.assertIn('Digoxin inhibits the Na/K ATPase.', resp.data['explanation'])
        self.assertIn(PUBLIC, resp.data['explanation'])
        self.assertNotIn(RAW, resp.data['explanation'])


# ─── high-yield ─────────────────────────────────────────────────────────

class HighYieldDisplayTests(_Base):

    def setUp(self):
        super().setUp()
        from questions.models import Question, Subject, Topic
        imported = Subject.objects.create(name=RAW, code='IMPORTED')
        for subject, topic_name in ((imported, 'Vaccines'), (self.q.subject, 'Arrhythmias')):
            topic = Topic.objects.create(subject=subject, name=topic_name)
            for year in (2019, 2020):
                Question.objects.create(
                    question_text=f'{topic_name} {year}', option_a='a', option_b='b', option_c='c',
                    option_d='d', correct_answer='A', year=year, subject=subject, topic=topic,
                )

    def high_yield(self):
        from ai_engine.views import HighYieldTopicsView
        return self.call(HighYieldTopicsView, {}, self.premium, method='get')

    def test_question_bank_fallback_heading(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            resp = self.high_yield()
        self.assertEqual(resp.status_code, 200, resp.data)
        markdown = resp.data['predictions']
        self.assertIn(f'## {PUBLIC}\n1. **Vaccines** (2 PYQs in 2 years) (★★)', markdown)
        self.assertIn('## Medicine W4\n1. **Arrhythmias**', markdown)
        self.assertNotIn(RAW, markdown)

    def test_imported_and_expert_curated_subjects_form_one_ranked_section(self):
        from questions.models import Question, Subject, Topic
        curated = Subject.objects.create(name=PUBLIC, code='EXPCUR')
        topic = Topic.objects.create(subject=curated, name='Biostatistics')
        Question.objects.create(question_text='Biostatistics 2021', option_a='a', option_b='b', option_c='c',
                                option_d='d', correct_answer='A', year=2021, subject=curated, topic=topic)
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            markdown = self.high_yield().data['predictions']
        self.assertEqual(markdown.count(f'## {PUBLIC}'), 1)
        self.assertIn(f'## {PUBLIC}\n1. **Vaccines** (2 PYQs in 2 years) (★★)\n'
                      '2. **Biostatistics** (1 PYQs in 1 years) (★)', markdown)

    def test_list_cached_before_the_fix(self):
        stale = (f'> Offline answer.\n\n## {RAW}\n1. **Vaccines** (2 PYQs in 2 years) (★★)\n\n'
                 '## Medicine\n1. **HTN** (★★★)')
        cache.set('ai_high_yield_v1:all', {'predictions': stale, 'subject': None, 'offline': True,
                                            'offline_reason': offline.REASON_OFFLINE_MODE,
                                            'generated_at': '2026-11-01T00:00:00'}, 60)
        with patch.object(AIService, 'predict_high_yield_topics') as predict:
            resp = self.high_yield()
        predict.assert_not_called()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['cached'])
        markdown = resp.data['predictions']
        self.assertIn(f'## {PUBLIC}\n1. **Vaccines**', markdown)
        self.assertIn('## Medicine\n1. **HTN** (★★★)', markdown)
        self.assertNotIn(RAW, markdown)

    def test_model_heading_and_its_cached_copy(self):
        with patch.object(AIService, 'predict_high_yield_topics',
                          return_value=f'## {RAW}\n1. **Vaccines**\n## Surgery\n1. **Hernia**'):
            resp = self.high_yield()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['predictions'], f'## {PUBLIC}\n1. **Vaccines**\n## Surgery\n1. **Hernia**')
        self.assertNotIn(RAW, cache.get('ai_high_yield_v1:all')['predictions'])


# ─── similar-PYQ metadata ───────────────────────────────────────────────

class SimilarPyqMetadataTests(_ImportedBase):

    def test_similar_pyq_payloads_carry_no_subject(self):
        pyq = offline.find_similar_pyq(STEM, user=self.admin)
        self.assertIsNotNone(pyq)
        self.assertEqual(pyq['id'], self.q.id)
        self.assertNotIn('subject', pyq)
        self.assert_no_raw_subject(pyq)
        self.assertNotIn(RAW, offline.pyq_summary(pyq))


# ─── knowledge base ─────────────────────────────────────────────────────

def _chunk(subject, chunk_id):
    from knowledge_base.retrieval.pipeline import RetrievedChunk
    return RetrievedChunk(
        chunk_id=chunk_id, text='Digoxin toxicity causes bidirectional ventricular tachycardia.',
        source_slug='internal-notes', source_name='Own notes', attribution='Own notes',
        license='own', locator='notes/cardio.md', subject=subject, topic='Arrhythmias',
        final_score=0.9,
    )


class KnowledgeBaseDisplayTests(TestCase):

    def test_monica_citation_subject(self):
        from knowledge_base.services.monica import Monica
        _context, citations = Monica(retrieval=MagicMock())._build_context(
            [_chunk(RAW, 1), _chunk('medicine', 2)], 4000)
        self.assertEqual([c['subject'] for c in citations], [PUBLIC, 'medicine'])

    def test_search_result_subject(self):
        from knowledge_base.retrieval.pipeline import RetrievalPipeline
        from knowledge_base.views import SearchView
        request = APIRequestFactory().post('/api/knowledge/search/', {'query': 'digoxin toxicity'}, format='json')
        force_authenticate(request, user=User.objects.create(username='z5-kb-student', role='student'))
        with patch.object(RetrievalPipeline, 'search', return_value=[_chunk(RAW, 1), _chunk('medicine', 2)]):
            resp = SearchView.as_view()(request)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['subject'] for r in resp.data['results']], [PUBLIC, 'medicine'])
