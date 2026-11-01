"""Regression tests, wave 2 (group W4-ai).

C2   The explain endpoints apply the question bank's entitlement rule
     (questions.views.user_can_view_answer) to every DB question on every
     path -- stored, cached, generated, AI_OFFLINE_MODE and provider outage --
     so a free user can no longer learn the answer of a paywalled question
     (402 upgrade_required, nothing charged, nothing revealed).
C4   Scholarship-test questions are never explained to non-premium users.
AI   is_valid_explanation rejects legacy unparsed rows (raw_response).
AI   The mnemonic endpoint answers 503 ai_unavailable instead of an extract.
AI-08 Page screenshots are saved to question.page_screenshot and returned
     as a URL only; failed lookups are cached; the view is throttled.
AI   An admin regeneration keeps the rich explanation (and vice versa).
AI   textbook-reference returns short locating snippets only.
QB-34 generate_admin_explanation honours the active admin prompt.
KB-01 evaluate_kb survives AIUnavailable per case.
KB   kb_cleanup_legacy relabels user uploads stored as internal notes and
     deletes hash pseudo-embeddings.

No test reaches an AI provider: clients are never built and AI calls are
patched.
"""
import json
import os
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Subscription, TokenBalance
from accounts.models_freemium import FreeShowcaseQuestion
from ai_engine import offline
from ai_engine.services import AIService, AIUnavailable

User = get_user_model()

RICH = {
    'ai_verified_answer': 'C', 'answer_mismatch': False, 'confidence_note': '',
    'why_correct': 'Digoxin toxicity causes bidirectional ventricular tachycardia.',
    'why_wrong': {'A': 'No', 'B': 'No', 'D': 'No'},
    'textbook_reference': {'book': 'Harrison', 'chapter': 'Arrhythmias', 'page': '1', 'section': ''},
    'mnemonic': 'DIG: digoxin', 'core_concept': 'Digoxin toxicity',
    'high_yield_points': ['Hyperkalaemia in acute toxicity'],
}
OPTIONS = {'A': 'Atropine', 'B': 'Adenosine', 'C': 'Digoxin', 'D': 'Amiodarone'}
STEM = 'Bidirectional ventricular tachycardia is classically caused by which drug?'
# 1x1 transparent PNG.
PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f'
       b'\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00'
       b'\x00IEND\xaeB`\x82')


class _Base(TestCase):
    def setUp(self):
        from questions.models import Question, Subject
        cache.clear()
        for p in (
            patch.object(AIService, '_init_clients', lambda self: None),
            patch.object(AIService, 'rag', new_callable=PropertyMock, return_value=None),
            patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.factory = APIRequestFactory()
        self.free = User.objects.create(username='w4-free', role='student')
        self.premium = User.objects.create(username='w4-premium', role='student')
        Subscription.objects.create(user=self.premium, plan='1_month', status='active',
                                    expires_at=timezone.now() + timedelta(days=30))
        self.admin = User.objects.create(username='w4-admin', role='admin')
        subject = Subject.objects.create(name='Medicine W4', code='MEDW4')
        self.q = Question.objects.create(
            question_text=STEM, option_a=OPTIONS['A'], option_b=OPTIONS['B'],
            option_c=OPTIONS['C'], option_d=OPTIONS['D'], correct_answer='C', year=2021,
            subject=subject, explanation='Curated: digoxin causes bidirectional VT.',
        )

    def call(self, view, data, user, method='post', **kwargs):
        if method == 'post':
            request = self.factory.post('/api/ai/x/', data, format='json')
        else:
            request = self.factory.get('/api/ai/x/', data)
        force_authenticate(request, user=user)
        return view.as_view()(request, **kwargs)

    def explain_answer(self, data, user):
        from ai_engine.views import ExplainAfterAnswerView
        return self.call(ExplainAfterAnswerView, data, user)

    def explain_question(self, data, user):
        from ai_engine.views import ExplainQuestionView
        return self.call(ExplainQuestionView, data, user, question_id=self.q.id)

    def store_rich(self, data=None):
        self.q.ai_explanation = json.dumps(data or RICH)
        self.q.ai_generated_at = timezone.now()
        self.q.save()

    def assert_paywalled(self, resp):
        self.assertEqual(resp.status_code, 402, getattr(resp, 'data', None))
        self.assertEqual(resp.data['code'], 'upgrade_required')
        self.assertFalse(resp.data['charged'])
        body = json.dumps(resp.data)
        for leak in ('why_correct', 'ai_verified_answer', 'is_correct', 'explanation"', 'digoxin causes'):
            self.assertNotIn(leak, body)

    def assert_nothing_charged(self, user):
        self.assertFalse(TokenBalance.objects.filter(user=user, total_tokens_used__gt=0).exists())


# ─── C2: explain-answer ─────────────────────────────────────────────────

class ExplainAnswerGateTests(_Base):

    def test_free_user_cannot_read_stored_explanation_or_probe_the_key(self):
        self.store_rich()
        with patch.object(AIService, 'explain_after_answer') as explain:
            for letter in 'ABCD':
                resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': letter}, self.free)
                self.assert_paywalled(resp)
        explain.assert_not_called()
        self.assert_nothing_charged(self.free)

    def test_exact_stem_and_options_match_is_gated_too(self):
        self.store_rich()
        resp = self.explain_answer({'question_text': STEM, 'options': OPTIONS,
                                    'correct_answer': 'A', 'selected_answer': 'A'}, self.free)
        self.assert_paywalled(resp)

    def test_cached_explanation_is_gated(self):
        cache.set(AIService.explanation_cache_key(STEM, OPTIONS, 'C', self.q.id), dict(RICH), 60)
        resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.free)
        self.assert_paywalled(resp)

    def test_offline_mode_does_not_serve_curated_explanation(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                patch('ai_engine.views.compose_offline_answer') as composer:
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.free)
        self.assert_paywalled(resp)
        composer.assert_not_called()

    def test_outage_path_is_gated(self):
        with patch.object(AIService, 'explain_after_answer', side_effect=AIUnavailable('down')) as explain:
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.free)
        self.assert_paywalled(resp)
        explain.assert_not_called()
        self.assert_nothing_charged(self.free)

    def test_offline_helper_itself_refuses_a_non_entitled_caller(self):
        from ai_engine.views import ExplainAfterAnswerView
        resp = ExplainAfterAnswerView._offline(
            SimpleNamespace(user=self.free), self.q, STEM, OPTIONS, 'C', 'C', '', '',
            offline.REASON_PROVIDERS_DOWN,
        )
        self.assert_paywalled(resp)

    def test_showcase_question_is_explained_to_free_users(self):
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        self.store_rich()
        resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.free)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['is_correct'])
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])

    def test_premium_and_admin_are_entitled(self):
        self.store_rich()
        for user in (self.premium, self.admin):
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'A'}, user)
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertFalse(resp.data['is_correct'])

    def test_premium_offline_mode_still_gets_the_curated_explanation(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                patch('ai_engine.views.compose_offline_answer',
                      return_value=offline.OfflineAnswer(grounded=False, answer=offline.NO_GROUNDED_ANSWER)):
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertEqual(resp.data['why_correct'], self.q.explanation)

    def test_scholarship_question_is_never_explained_to_free_users(self):
        self.q.is_scholarship_eligible = True
        self.q.save()
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        self.store_rich()
        self.assert_paywalled(self.explain_answer({'question_id': self.q.id}, self.free))
        self.assertEqual(self.explain_answer({'question_id': self.q.id}, self.premium).status_code, 200)

    def test_ad_hoc_question_still_works_for_free_users(self):
        """AI-generated practice questions are not in the bank: explained
        against the client's key, nothing stored."""
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)) as explain:
            resp = self.explain_answer({
                'question_text': 'A generated question?', 'options': {'A': 'p', 'B': 'q', 'C': 'r', 'D': 's'},
                'correct_answer': 'B', 'selected_answer': 'B',
            }, self.free)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(explain.call_args.args[2], 'B', 'the client key, not a DB key')
        self.q.refresh_from_db()
        self.assertEqual(self.q.ai_explanation, '')


# ─── C2: explain-question ───────────────────────────────────────────────

class ExplainQuestionGateTests(_Base):

    def test_free_user_gets_402_on_stored_generated_and_offline_paths(self):
        self.store_rich()
        self.assert_paywalled(self.explain_question({}, self.free))
        with patch.object(AIService, 'analyze_question', return_value='C is right') as analyze:
            self.assert_paywalled(self.explain_question({'prompt': 'Why?'}, self.free))
            self.assert_paywalled(self.explain_question({'force_regenerate': True}, self.free))
        analyze.assert_not_called()
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            self.assert_paywalled(self.explain_question({'prompt': 'Why?'}, self.free))
        self.assert_nothing_charged(self.free)

    def test_offline_helper_itself_refuses_a_non_entitled_caller(self):
        from ai_engine.views import ExplainQuestionView
        resp = ExplainQuestionView._offline(SimpleNamespace(user=self.free), self.q, offline.REASON_OFFLINE_MODE)
        self.assert_paywalled(resp)

    def test_entitled_user_gets_the_stored_markdown(self):
        self.store_rich()
        resp = self.explain_question({}, self.premium)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['cached'])
        self.assertIn(RICH['why_correct'], resp.data['explanation'])


# ─── Admin regeneration vs. explain-answer ──────────────────────────────

class RegenerationCoexistenceTests(_Base):

    def test_admin_regeneration_keeps_the_rich_explanation(self):
        self.store_rich()
        with patch.object(AIService, 'analyze_question', return_value='## Admin markdown analysis'):
            resp = self.explain_question({'force_regenerate': True}, self.admin)
        self.assertTrue(resp.data['persisted'])
        stored = json.loads(Question_refresh(self.q).ai_explanation)
        self.assertEqual(stored['why_correct'], RICH['why_correct'])
        self.assertEqual(stored['analysis'], '## Admin markdown analysis')

        # Students' explain-answer still serves the rich JSON for free...
        with patch.object(AIService, 'explain_after_answer') as explain:
            rich = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        explain.assert_not_called()
        self.assertEqual(rich.data['why_correct'], RICH['why_correct'])
        self.assertNotIn('analysis', rich.data)
        # ...and explain-question serves the admin's analysis.
        md = self.explain_question({}, self.premium)
        self.assertTrue(md.data['cached'])
        self.assertEqual(md.data['explanation'], '## Admin markdown analysis')

    def test_explain_answer_keeps_an_existing_markdown_analysis(self):
        self.q.ai_explanation = json.dumps({'analysis': 'Shared analysis', 'context': {'year': 2021}})
        self.q.save()
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)):
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        self.assertEqual(resp.status_code, 200)
        stored = json.loads(Question_refresh(self.q).ai_explanation)
        self.assertEqual(stored['why_correct'], RICH['why_correct'])
        self.assertEqual(stored['analysis'], 'Shared analysis')
        self.assertEqual(self.explain_question({}, self.premium).data['explanation'], 'Shared analysis')


def Question_refresh(q):
    q.refresh_from_db()
    return q


# ─── Legacy unparsed rows ───────────────────────────────────────────────

class LegacyExplanationRowTests(_Base):
    LEGACY = {
        'why_correct': '{"ai_verified_answer": "C", "why_correct": "Digoxin',
        'why_wrong': {}, 'mnemonic': '',
        'raw_response': '{"ai_verified_answer": "C", "why_correct": "Digoxin',
    }

    def test_is_valid_explanation_rejects_legacy_shapes(self):
        self.assertFalse(AIService.is_valid_explanation(self.LEGACY))
        self.assertFalse(AIService.is_valid_explanation(dict(RICH, raw_response='x')))
        self.assertFalse(AIService.is_valid_explanation(dict(RICH, why_correct='```json\n{"a": 1}\n```')))
        self.assertFalse(AIService.is_valid_explanation(dict(RICH, why_correct='{"why_correct": "x"}')))
        self.assertTrue(AIService.is_valid_explanation(dict(RICH)))

    def test_legacy_row_is_regenerated_and_replaced(self):
        self.store_rich(self.LEGACY)
        with patch.object(AIService, 'explain_after_answer', return_value=dict(RICH)) as explain:
            resp = self.explain_answer({'question_id': self.q.id, 'selected_answer': 'C'}, self.premium)
        explain.assert_called_once()
        self.assertEqual(resp.data['why_correct'], RICH['why_correct'])
        stored = json.loads(Question_refresh(self.q).ai_explanation)
        self.assertNotIn('raw_response', stored)
        self.assertEqual(stored['why_correct'], RICH['why_correct'])

    def test_offline_text_skips_legacy_rows(self):
        row = {'explanation': '', 'why_correct': '', 'ai_explanation': json.dumps(self.LEGACY)}
        self.assertEqual(offline.stored_explanation_text(row), '')


class SimilarPyqScholarshipTests(_Base):
    def test_free_users_never_get_a_scholarship_question_back(self):
        FreeShowcaseQuestion.objects.create(question=self.q, year=2021, position=0)
        probe = 'bidirectional ventricular tachycardia caused by which drug classically'
        self.assertIsNotNone(offline.find_similar_pyq(probe, user=self.free))
        self.q.is_scholarship_eligible = True
        self.q.save()
        self.assertIsNone(offline.find_similar_pyq(probe, user=self.free))
        self.assertIsNotNone(offline.find_similar_pyq(probe, user=self.premium))


# ─── Mnemonic ───────────────────────────────────────────────────────────

class MnemonicUnavailableTests(_Base):
    def mnemonic(self, user=None):
        from ai_engine.views import GenerateMnemonicView
        return self.call(GenerateMnemonicView, {'topic': 'causes of pancreatitis'}, user or self.free)

    def test_outage_is_a_free_503_not_an_extract(self):
        from ai_engine.models_usage import get_today_usage
        with patch.object(AIService, 'generate_mnemonic', side_effect=AIUnavailable('down')), \
                patch('ai_engine.views.compose_offline_answer') as composer:
            resp = self.mnemonic()
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')
        self.assertNotIn('mnemonic', resp.data)
        self.assertFalse(resp.data['offline'])
        composer.assert_not_called()
        self.assertEqual(TokenBalance.objects.get(user=self.free).daily_tokens_used, 0)
        self.assertEqual(get_today_usage(self.free), 0)

    def test_offline_mode_is_a_503_without_any_ai_call(self):
        with patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                patch.object(AIService, 'generate_mnemonic') as generate, \
                patch('ai_engine.views.compose_offline_answer') as composer:
            resp = self.mnemonic()
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(resp.data['offline'])
        self.assertIn('offline mode', resp.data['message'])
        generate.assert_not_called()
        composer.assert_not_called()

    def test_unusable_model_text_is_a_503(self):
        with patch.object(AIService, 'generate_mnemonic',
                          return_value='All AI services are temporarily unavailable.'):
            resp = self.mnemonic()
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn('mnemonic', resp.data)

    def test_success_returns_the_mnemonic(self):
        with patch.object(AIService, 'generate_mnemonic', return_value='I GET SMASHED'):
            resp = self.mnemonic(self.premium)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['mnemonic'], 'I GET SMASHED')


# ─── Page screenshots ───────────────────────────────────────────────────

class PageScreenshotTests(_Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp(prefix='w4-media-')
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.q.book_name = 'Harrison'
        self.q.page_number = '1234-1236'
        self.q.save()

    def screenshot(self, user=None):
        from ai_engine.views import PageScreenshotView
        return self.call(PageScreenshotView, {}, user or self.premium, method='get', question_id=self.q.id)

    @staticmethod
    def fake_render(pdf_path, page_num, output_dir, dpi=200):
        path = os.path.join(output_dir, f'harrison_page_{page_num + 1}.png')
        with open(path, 'wb') as fh:
            fh.write(PNG)
        return path

    def test_new_render_is_saved_and_returned_as_a_url(self):
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_find_pdf', return_value='/books/harrison.pdf'), \
                patch('ai_engine.document_processor.DocumentProcessor.extract_page_image',
                      side_effect=self.fake_render) as render:
            first = self.screenshot()
            second = self.screenshot()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertNotIn('screenshot_path', first.data)
        url = first.data['screenshot_url']
        self.assertTrue(url.startswith('http://testserver/media/question_screenshots/'), url)
        self.assertTrue(url.endswith('.png'))
        self.assertEqual(render.call_count, 1, 'the stored render is reused')
        self.assertEqual(render.call_args.args[1], 1233, "page '1234-1236' -> 0-based 1233")
        self.assertEqual(second.data['screenshot_url'], url)
        self.q.refresh_from_db()
        self.assertTrue(self.q.page_screenshot.name.startswith('question_screenshots/'))
        self.assertTrue(os.path.isfile(self.q.page_screenshot.path))

    def test_failed_lookup_is_cached(self):
        from ai_engine.views import PageScreenshotView
        with patch.object(PageScreenshotView, '_find_pdf', return_value=None) as find:
            first = self.screenshot()
            second = self.screenshot()
        self.assertEqual(first.status_code, 404)
        self.assertEqual(second.status_code, 404)
        self.assertNotIn('screenshot_url', second.data)
        self.assertEqual(find.call_count, 1, 'the miss is remembered')

    def test_concurrent_render_is_not_started_twice(self):
        from ai_engine.views import PageScreenshotView
        cache.set(f'ai_page_screenshot_lock_v1:{self.q.id}', 1, 60)
        with patch.object(PageScreenshotView, '_render_and_store') as render:
            resp = self.screenshot()
        self.assertEqual(resp.status_code, 202)
        self.assertNotIn('screenshot_url', resp.data)
        render.assert_not_called()

    def test_view_is_throttled(self):
        from rest_framework.throttling import ScopedRateThrottle
        from ai_engine.views import PageScreenshotView
        self.assertEqual(PageScreenshotView.throttle_scope, 'ai_tutor')
        self.assertTrue(any(isinstance(t, ScopedRateThrottle) for t in PageScreenshotView().get_throttles()))


# ─── Textbook references ────────────────────────────────────────────────

class TextbookReferenceSnippetTests(_Base):
    def test_excerpts_are_short_snippets(self):
        from ai_engine.views import TextbookReferenceView
        refs = [{'book': f'Book {i}', 'page': i, 'excerpt': 'word ' * 120, 'relevance_score': 0.5} for i in range(5)]
        with patch.object(AIService, 'find_textbook_reference', return_value=refs):
            resp = self.call(TextbookReferenceView, {'question_text': 'septic shock'}, self.free)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['references']), TextbookReferenceView.MAX_REFERENCES)
        for ref in resp.data['references']:
            self.assertLessEqual(len(ref['excerpt']), TextbookReferenceView.REFERENCE_EXCERPT_CHARS + 1)
            self.assertTrue(ref['excerpt'].endswith('…'))
            self.assertIn('book', ref)


# ─── QB-34: admin prompt version ────────────────────────────────────────

class AdminExplanationPromptTests(_Base):
    GENERATED = json.dumps({'explanation': 'C is right', 'why_correct': 'Because'})

    def test_active_admin_prompt_leads_the_prompt(self):
        with patch.object(AIService, '_call_ai', return_value=self.GENERATED) as call_ai:
            result = AIService().generate_admin_explanation(
                STEM, OPTIONS, 'C', user_prompt='Always cite Harrison 21st edition.',
            )
        prompt = call_ai.call_args.args[0]
        self.assertTrue(prompt.startswith('Always cite Harrison 21st edition.'))
        self.assertIn('VERIFIED CORRECT ANSWER: C', prompt)
        self.assertEqual(result['explanation'], 'C is right')

    def test_without_a_prompt_the_default_prompt_is_unchanged(self):
        with patch.object(AIService, '_call_ai', return_value=self.GENERATED) as call_ai:
            AIService().generate_admin_explanation(STEM, OPTIONS, 'C')
        self.assertTrue(call_ai.call_args.args[0].startswith('You are a medical educator'))

    def test_admin_prompt_is_capped(self):
        with patch.object(AIService, '_call_ai', return_value=self.GENERATED) as call_ai:
            AIService().generate_admin_explanation(STEM, OPTIONS, 'C', user_prompt='x' * 10000)
        prompt = call_ai.call_args.args[0]
        self.assertIn('x' * AIService.MAX_ADMIN_PROMPT_CHARS, prompt)
        self.assertNotIn('x' * (AIService.MAX_ADMIN_PROMPT_CHARS + 1), prompt)


# ─── KB-01: evaluation harness ──────────────────────────────────────────

class EvalHarnessTests(TestCase):
    def test_ai_unavailable_is_recorded_per_case(self):
        from knowledge_base.eval import harness
        from knowledge_base.models import EvalRun
        passages = [{'text': 'x', 'book': 'B', 'page': 1}, {'text': 'y', 'book': 'B', 'page': 2}]
        with patch.object(harness, 'Monica') as monica:
            monica.return_value.answer.side_effect = AIUnavailable('down', passages=passages)
            result = harness.run_evaluation(max_cases=3)
        self.assertEqual(result['testcases_total'], 3)
        self.assertEqual(result['errors'], 3)
        for row in result['results']:
            self.assertEqual(row['error'], 'ai_unavailable')
            self.assertFalse(row['ok'])
            self.assertEqual(row['retrieval_count'], 2)
        self.assertIn('ai_unavailable', EvalRun.objects.get(id=result['eval_run_id']).notes)

    def test_command_reports_errors(self):
        from knowledge_base.eval import harness
        out = StringIO()
        with patch.object(harness, 'Monica') as monica:
            monica.return_value.answer.side_effect = AIUnavailable('down', offline=True)
            call_command('evaluate_kb', '--max', '1', stdout=out)
        self.assertIn('no AI answer', out.getvalue())


# ─── KB: legacy clean-up ────────────────────────────────────────────────

class KbCleanupLegacyTests(TestCase):
    TEXT = 'Edema in nephrotic syndrome results from low plasma oncotic pressure and sodium retention.'

    def setUp(self):
        from knowledge_base.models import KnowledgeChunk, KnowledgeEmbedding, KnowledgeSource
        self.KnowledgeChunk = KnowledgeChunk
        self.KnowledgeEmbedding = KnowledgeEmbedding
        internal = KnowledgeSource.objects.create(slug='internal-notes', name='Internal notes',
                                                  license='internal', attribution='CrackLabs Internal')
        self.upload = KnowledgeChunk.objects.create(
            source=internal, text=self.TEXT, text_hash='h-upload', license='internal',
            attribution='CrackLabs Internal', approval_state=KnowledgeChunk.APPROVAL_AUTO,
            locator='user_uploads/my_notes.txt', approved_at=timezone.now(),
        )
        self.note = KnowledgeChunk.objects.create(
            source=internal, text=self.TEXT + ' (internal)', text_hash='h-note', license='internal',
            attribution='CrackLabs Internal', approval_state=KnowledgeChunk.APPROVAL_AUTO,
            locator='notes/nephrology.md',
        )
        from knowledge_base.services.embedding import EmbeddingService
        hash_vec = EmbeddingService(model='bge-small-en-v1.5')._hash_embed(self.TEXT)
        real_vec = [((i * 37) % 101) / 101.0 - 0.5 for i in range(384)]
        self.hash_emb = KnowledgeEmbedding.objects.create(chunk=self.upload, model='bge-small-en-v1.5',
                                                          dim=384, vector=hash_vec)
        self.real_emb = KnowledgeEmbedding.objects.create(chunk=self.note, model='bge-small-en-v1.5',
                                                          dim=384, vector=real_vec)

    def test_hash_signature(self):
        from knowledge_base.management.commands.kb_cleanup_legacy import is_hash_embedding
        self.assertTrue(is_hash_embedding(self.hash_emb.vector))
        self.assertFalse(is_hash_embedding(self.real_emb.vector))
        self.assertFalse(is_hash_embedding([0.0] * 384))
        self.assertFalse(is_hash_embedding('not a vector'))

    def test_dry_run_changes_nothing(self):
        out = StringIO()
        call_command('kb_cleanup_legacy', stdout=out)
        self.assertIn('1 user-upload chunk(s) moved', out.getvalue())
        self.assertIn('1 hash embedding(s) deleted', out.getvalue())
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.source.slug, 'internal-notes')
        self.assertTrue(self.KnowledgeEmbedding.objects.filter(id=self.hash_emb.id).exists())

    def test_apply_relabels_uploads_and_deletes_hash_vectors(self):
        from knowledge_base.models import LICENSE_USER_ATTESTED
        call_command('kb_cleanup_legacy', '--apply', stdout=StringIO())
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.source.slug, 'user-uploads')
        self.assertEqual(self.upload.license, LICENSE_USER_ATTESTED)
        self.assertEqual(self.upload.approval_state, self.KnowledgeChunk.APPROVAL_PENDING)
        self.assertIsNone(self.upload.approved_at)
        self.note.refresh_from_db()
        self.assertEqual((self.note.source.slug, self.note.license), ('internal-notes', 'internal'))
        self.assertFalse(self.KnowledgeEmbedding.objects.filter(id=self.hash_emb.id).exists())
        self.assertTrue(self.KnowledgeEmbedding.objects.filter(id=self.real_emb.id).exists())

    def test_admin_decision_survives_and_duplicates_are_deactivated(self):
        from knowledge_base.connectors.user_uploads import UserUploadsConnector
        self.upload.approval_state = self.KnowledgeChunk.APPROVAL_REJECTED
        self.upload.save()
        target = UserUploadsConnector().source
        dup_source = self.KnowledgeChunk.objects.create(
            source=self.upload.source, text=self.TEXT + ' again', text_hash='h-dup', license='internal',
            attribution='x', approval_state=self.KnowledgeChunk.APPROVAL_AUTO, locator='user_uploads/dup.txt',
        )
        self.KnowledgeChunk.objects.create(
            source=target, text=self.TEXT + ' again', text_hash='h-dup', license=target.license,
            attribution=target.attribution, approval_state=self.KnowledgeChunk.APPROVAL_PENDING,
            locator='user_uploads/dup.txt',
        )
        call_command('kb_cleanup_legacy', '--apply', stdout=StringIO())
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.approval_state, self.KnowledgeChunk.APPROVAL_REJECTED)
        dup_source.refresh_from_db()
        self.assertFalse(dup_source.is_active)
        self.assertEqual(dup_source.source.slug, 'internal-notes')
