"""Regression tests: offline composer + knowledge-base fixes (audit 2026-11, G5).

Offline composer (ai_engine.offline): grounded extractive answers with
[book p.page] citations, an explicit "no grounded answer" below threshold,
past-question lookup that respects the free-tier showcase gate.

Knowledge base:
  KB-01/KB-02  Monica answers the student's question with its own citation
               prompt (no canned fallback string as the prompt, no
               ask_tutor), invalid [n] markers removed.
  KB-04/CFG-19 models cached per process, no hash pseudo-embeddings for
               search, rerank toggle honoured, one-query citations,
               SearchView throttled.
  KB-12        uploads validated (strict booleans, type, size, magic bytes).
  KB-13        ask throttle recorded once, process-stable cache key.
  KB-08        licence constants by name, approval never overwritten, no
               version churn, user uploads get their own attested source,
               refused filenames skipped.
  + AskMonicaView refunds token and freemium slot when the AI fails.

No external service is called: provider calls, model loads and the
textbook retriever are patched.
"""
import os
import shutil
import sys
import tempfile
import types
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import TokenBalance
from ai_engine import offline
from ai_engine.models_usage import get_today_usage
from ai_engine.services import AIService, AIUnavailable

User = get_user_model()

PASSAGES = [
    {'text': (
        'Nephrotic syndrome is characterised by heavy proteinuria, hypoalbuminaemia and edema. '
        'Edema in nephrotic syndrome results from low plasma oncotic pressure caused by hypoalbuminaemia. '
        'See also Nephritic syndrome Minimal change disease Membranous nephropathy. '
        'Smith J. Kidney disease review. doi 10.1000/xyz PMID 123456.'
    ), 'book': 'Ghai Pediatrics', 'page': 12, 'score': 9.0},
    {'text': 'Acute appendicitis presents with periumbilical pain that migrates to the right iliac fossa.',
     'book': 'Bailey', 'page': 40, 'score': 1.0},
]


class OfflineComposerTests(TestCase):
    def setUp(self):
        p = patch('ai_engine.offline._global_idf', return_value=None)
        p.start()
        self.addCleanup(p.stop)

    def test_grounded_answer_cites_book_and_page(self):
        result = offline.compose_offline_answer(
            'What is the mechanism of edema in nephrotic syndrome?', passages=PASSAGES, include_pyq=False,
        )
        self.assertTrue(result.grounded)
        self.assertIn('[Ghai Pediatrics p.12]', result.answer)
        self.assertIn('oncotic pressure', result.answer)
        self.assertTrue(result.answer.startswith('> Offline answer'))
        self.assertLessEqual(len(result.sentences), offline.MAX_SENTENCES)
        self.assertNotIn('doi', result.answer.lower(), 'bibliography lines are not answers')
        self.assertNotIn('See also', result.answer)
        self.assertEqual(result.citations[0]['book'], 'Ghai Pediatrics')

    def test_unrelated_passages_give_no_grounded_answer(self):
        result = offline.compose_offline_answer('cricket world cup winner', passages=PASSAGES, include_pyq=False)
        self.assertFalse(result.grounded)
        self.assertEqual(result.answer, offline.NO_GROUNDED_ANSWER)

    def test_retrieval_uses_the_rag_pipeline_search(self):
        with patch('ai_engine.rag_pipeline.RAGPipeline.search', return_value=PASSAGES) as search:
            result = offline.compose_offline_answer('edema in nephrotic syndrome mechanism', include_pyq=False)
        search.assert_called_once()
        self.assertTrue(result.grounded)

    def test_offline_mode_flag_parsing(self):
        for value, expected in (('1', True), ('true', True), ('YES', True), ('0', False), ('', False), ('no', False)):
            with patch.dict(os.environ, {'AI_OFFLINE_MODE': value}):
                self.assertEqual(offline.ai_offline_mode(), expected, value)

    def test_outage_sentences_are_never_stored_answers(self):
        self.assertTrue(offline.is_unusable_text('All AI services are temporarily unavailable. Please try again.'))
        self.assertTrue(offline.is_unusable_text('AI answer generation is unavailable. Please configure API keys.'))
        self.assertFalse(offline.is_unusable_text('Hypoalbuminaemia lowers oncotic pressure.'))
        row = {'explanation': '', 'why_correct': '',
               'ai_explanation': '{"why_correct": "All AI services are temporarily unavailable."}'}
        self.assertEqual(offline.stored_explanation_text(row), '')


class SimilarPYQTests(TestCase):
    def setUp(self):
        from questions.models import Question, Subject
        subject = Subject.objects.create(name='Pediatrics PYQ', code='PEDPYQ')
        self.q = Question.objects.create(
            question_text='Edema in nephrotic syndrome is primarily due to which mechanism?',
            option_a='Increased hydrostatic pressure', option_b='Decreased plasma oncotic pressure',
            option_c='Lymphatic obstruction', option_d='Capillary leak', correct_answer='B',
            year=2019, subject=subject, explanation='Hypoalbuminaemia lowers plasma oncotic pressure.',
        )
        self.free = User.objects.create(username='pyq-free', role='student')
        self.admin = User.objects.create(username='pyq-admin', role='admin')

    def test_strong_match_returns_stored_explanation_for_full_bank_users(self):
        pyq = offline.find_similar_pyq('mechanism of edema in nephrotic syndrome', user=self.admin)
        self.assertIsNotNone(pyq)
        self.assertEqual(pyq['id'], self.q.id)
        self.assertEqual(pyq['correct_answer'], 'B')
        self.assertIn('oncotic', pyq['explanation'])

    def test_free_users_only_get_showcase_questions(self):
        self.assertIsNone(offline.find_similar_pyq('mechanism of edema in nephrotic syndrome', user=self.free))
        from accounts.models_freemium import FreeShowcaseQuestion
        FreeShowcaseQuestion.objects.create(question=self.q, year=2019, position=0)
        self.assertIsNotNone(offline.find_similar_pyq('mechanism of edema in nephrotic syndrome', user=self.free))

    def test_weak_match_returns_nothing(self):
        self.assertIsNone(offline.find_similar_pyq('treatment of falciparum malaria', user=self.admin))


# ─── Knowledge base ─────────────────────────────────────────────────────

def _make_source(slug='kb-test-source', license_code='cc_by'):
    from knowledge_base.models import KnowledgeSource
    return KnowledgeSource.objects.create(slug=slug, name=f'Source {slug}', license=license_code,
                                          attribution=f'Attribution {slug}')


class MonicaTests(TestCase):
    def setUp(self):
        cache.clear()
        for p in (
            patch.object(AIService, '_init_clients', lambda self: None),
            patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_fallback_prompt_is_the_students_question_with_monica_prompt(self):
        from knowledge_base.services.monica import Monica
        legacy = [{'text': 'Edema results from low oncotic pressure.', 'book': 'Ghai', 'page': 12, 'score': 3.0}]
        with patch.object(Monica, 'kb_ready', return_value=False), \
                patch('ai_engine.offline.retrieve_passages', return_value=legacy), \
                patch.object(AIService, 'ask_tutor') as ask_tutor, \
                patch.object(AIService, '_call_ai', return_value='Low oncotic pressure [1]. Also [7].') as call_ai:
            result = Monica().answer('Why does edema occur in nephrotic syndrome?')
        ask_tutor.assert_not_called()
        prompt = call_ai.call_args.args[0]
        self.assertIn('Why does edema occur in nephrotic syndrome?', prompt)
        self.assertIn('Edema results from low oncotic pressure.', prompt)
        self.assertNotIn('No relevant textbook content found', prompt)
        self.assertEqual(call_ai.call_args.kwargs['system'], Monica.SYSTEM_PROMPT)
        self.assertEqual(result.answer, 'Low oncotic pressure [1]. Also .')
        self.assertEqual(result.invalid_citations_removed, 1)
        self.assertFalse(result.used_kb)
        self.assertEqual(result.citations[0]['citation_text'], 'Ghai, p.12')

    def test_ai_failure_raises_with_passages(self):
        from knowledge_base.services.monica import Monica
        legacy = [{'text': 'x' * 50, 'book': 'Ghai', 'page': 1, 'score': 1.0}]
        with patch.object(Monica, 'kb_ready', return_value=False), \
                patch('ai_engine.offline.retrieve_passages', return_value=legacy), \
                patch.object(AIService, '_call_ai', side_effect=AIUnavailable('down')):
            with self.assertRaises(AIUnavailable) as ctx:
                Monica().answer('q?')
        self.assertEqual(ctx.exception.passages, legacy)

    def test_kb_threshold_setting_decides_the_path(self):
        from knowledge_base.services.monica import Monica
        with override_settings(KB_FALLBACK_THRESHOLD=10):
            cache.clear()
            from django.core.cache import caches
            caches['kb_retrieval'].clear()
            self.assertFalse(Monica.kb_ready())
        with override_settings(KB_FALLBACK_THRESHOLD=0):
            self.assertTrue(Monica.kb_ready())


class AskMonicaViewTests(TestCase):
    def setUp(self):
        cache.clear()
        for p in (
            patch.object(AIService, '_init_clients', lambda self: None),
            patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.user = User.objects.create(username='kb-student', role='student')
        self.factory = APIRequestFactory()

    def _ask(self, question='Why edema in nephrotic syndrome?'):
        from knowledge_base.views import AskMonicaView
        request = self.factory.post('/api/knowledge/ask/', {'question': question}, format='json')
        force_authenticate(request, user=self.user)
        return AskMonicaView.as_view()(request)

    def test_ai_failure_refunds_token_and_slot(self):
        from knowledge_base.services.monica import Monica
        with patch.object(Monica, 'answer', side_effect=AIUnavailable('down', passages=PASSAGES)), \
                patch('ai_engine.offline._global_idf', return_value=None), \
                patch('ai_engine.offline.find_similar_pyq', return_value=None):
            resp = self._ask('What is the mechanism of edema in nephrotic syndrome?')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['offline'])
        self.assertIn('[Ghai Pediatrics p.12]', resp.data['answer'])
        bal = TokenBalance.objects.get(user=self.user)
        self.assertEqual(bal.daily_tokens_used, 0)
        self.assertEqual(get_today_usage(self.user), 0)

    def test_ai_failure_without_grounding_is_503(self):
        from knowledge_base.services.monica import Monica
        with patch.object(Monica, 'answer', side_effect=AIUnavailable('down', passages=[])), \
                patch('ai_engine.offline.find_similar_pyq', return_value=None):
            resp = self._ask('zzz')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data['code'], 'ai_unavailable')

    def test_throttles_record_each_request_once(self):
        from rest_framework.throttling import ScopedRateThrottle
        from knowledge_base.views import AskMonicaView, SearchView
        throttles = AskMonicaView().get_throttles()
        self.assertEqual(sum(isinstance(t, ScopedRateThrottle) for t in throttles), 1)
        self.assertEqual(SearchView.throttle_scope, 'ai_tutor')
        self.assertTrue(any(isinstance(t, ScopedRateThrottle) for t in SearchView().get_throttles()))


class UploadValidationTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix='kb-upload-test-')
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        cache.clear()
        self.user = User.objects.create(username='kb-uploader', role='student')
        self.factory = APIRequestFactory()

    def _upload(self, upload, attested='true'):
        from knowledge_base.views import UploadView
        request = self.factory.post('/api/knowledge/upload/', {
            'title': 'My notes', 'source_description': 'own notes', 'rights_attested': attested, 'file': upload,
        }, format='multipart')
        force_authenticate(request, user=self.user)
        return UploadView.as_view()(request)

    def test_false_string_is_not_an_attestation(self):
        resp = self._upload(SimpleUploadedFile('notes.txt', b'my own notes', content_type='text/plain'), attested='false')
        self.assertEqual(resp.status_code, 400)

    def test_disallowed_type_size_and_fake_pdf_are_rejected(self):
        self.assertEqual(self._upload(SimpleUploadedFile('tool.exe', b'MZ...', content_type='application/octet-stream')).status_code, 400)
        self.assertEqual(self._upload(SimpleUploadedFile('fake.pdf', b'not a pdf', content_type='application/pdf')).status_code, 400)
        with patch('knowledge_base.views.KB_UPLOAD_MAX_BYTES', 10):
            self.assertEqual(self._upload(SimpleUploadedFile('big.txt', b'x' * 11, content_type='text/plain')).status_code, 400)

    def test_valid_text_upload_is_accepted_pending_review(self):
        resp = self._upload(SimpleUploadedFile('notes.txt', b'my own notes about edema', content_type='text/plain'))
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['decision'], 'pending')


class IngestionPolicyTests(TestCase):

    def _connector(self, source_slug, chunks):
        from knowledge_base.connectors.base import ConnectorBase, RawChunk

        class FakeConnector(ConnectorBase):
            def fetch(self, **kwargs):
                for text, locator in chunks:
                    yield RawChunk(text=text, locator=locator)

        conn = FakeConnector()
        conn.source_slug = source_slug
        return conn

    TEXT = 'Edema in nephrotic syndrome results from low plasma oncotic pressure and sodium retention.'

    def test_non_commercial_licence_is_not_auto_approved(self):
        from knowledge_base.models import KnowledgeChunk
        from knowledge_base.services.ingestion import AUTO_APPROVE_LICENSES, IngestionService
        self.assertIn('cc_by_sa', AUTO_APPROVE_LICENSES)
        self.assertNotIn('cc_by_nc_sa', AUTO_APPROVE_LICENSES)
        _make_source('nc-source', 'cc_by_nc_sa')
        IngestionService(self._connector('nc-source', [(self.TEXT, 'ch1')])).run()
        self.assertEqual(KnowledgeChunk.objects.get().approval_state, KnowledgeChunk.APPROVAL_PENDING)

    def test_reingest_keeps_moderation_and_does_not_churn_versions(self):
        from knowledge_base.models import KnowledgeChunk
        from knowledge_base.services.ingestion import IngestionService
        _make_source('by-source', 'cc_by')
        IngestionService(self._connector('by-source', [(self.TEXT, 'ch1')])).run()
        chunk = KnowledgeChunk.objects.get()
        self.assertEqual(chunk.approval_state, KnowledgeChunk.APPROVAL_AUTO)
        chunk.approval_state = KnowledgeChunk.APPROVAL_REJECTED
        chunk.save()

        result = IngestionService(self._connector('by-source', [(self.TEXT, 'ch1')])).run()
        chunk.refresh_from_db()
        self.assertEqual(chunk.approval_state, KnowledgeChunk.APPROVAL_REJECTED, 'admin decision survives')
        self.assertEqual(chunk.version, 1, 'nothing changed, no version bump')
        self.assertEqual(result.status, 'success')

        IngestionService(self._connector('by-source', [(self.TEXT, 'ch2')])).run()
        chunk.refresh_from_db()
        self.assertEqual(chunk.version, 2)
        self.assertEqual(chunk.locator, 'ch2')
        self.assertEqual(chunk.approval_state, KnowledgeChunk.APPROVAL_REJECTED)


class UserUploadsConnectorTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix='kb-uploads-conn-')
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create(username='kb-attester', role='student')

    def _approved_upload(self, name, body):
        from knowledge_base.models import UserUploadAttestation
        return UserUploadAttestation.objects.create(
            user=self.user, title='Notes', source_description='mine', rights_attested=True,
            file=SimpleUploadedFile(name, body), decision='approved',
        )

    def test_refused_filename_is_skipped(self):
        from knowledge_base.connectors.user_uploads import UserUploadsConnector, refused_marker
        self.assertEqual(refused_marker('harrison_cardiology_notes.txt'), 'harrison')
        self.assertIsNone(refused_marker('parking_rules.txt'))
        self._approved_upload('harrison_cardiology_notes.txt', b'Heart failure ' * 30)
        self.assertEqual(list(UserUploadsConnector().fetch()), [])

    def test_uploads_use_their_own_attested_source_and_wait_for_review(self):
        from knowledge_base.connectors.user_uploads import UserUploadsConnector
        from knowledge_base.models import KnowledgeChunk, LICENSE_USER_ATTESTED
        from knowledge_base.services.ingestion import IngestionService
        self._approved_upload('my_edema_notes.txt', b'Edema occurs when plasma oncotic pressure falls. ' * 5)
        connector = UserUploadsConnector()
        self.assertEqual(connector.source.slug, 'user-uploads')
        self.assertEqual(connector.source.license, LICENSE_USER_ATTESTED)
        IngestionService(connector).run()
        chunk = KnowledgeChunk.objects.get()
        self.assertEqual(chunk.license, LICENSE_USER_ATTESTED)
        self.assertEqual(chunk.approval_state, KnowledgeChunk.APPROVAL_PENDING)


class EmbeddingAndRerankCacheTests(TestCase):
    def setUp(self):
        from knowledge_base.retrieval import pipeline
        from knowledge_base.services import embedding
        self.embedding = embedding
        self.pipeline = pipeline
        embedding._ST_MODELS.clear()
        embedding._ST_FAILED.clear()
        pipeline._CE_STATE.update(model=None, failed_at=None)
        self.addCleanup(embedding._ST_MODELS.clear)
        self.addCleanup(embedding._ST_FAILED.clear)
        self.addCleanup(pipeline._CE_STATE.update, model=None, failed_at=None)

    def _fake_st_module(self, counter):
        module = types.ModuleType('sentence_transformers')

        class FakeST:
            def __init__(self, repo, **kwargs):
                counter['st'] += 1

            def encode(self, inputs, **kwargs):
                return [[0.5, 0.5] for _ in inputs]

        class FakeCE:
            def __init__(self, name, **kwargs):
                counter['ce'] += 1
                counter['ce_kwargs'] = kwargs

            def predict(self, pairs):
                return [0.1 for _ in pairs]

        module.SentenceTransformer = FakeST
        module.CrossEncoder = FakeCE
        return module

    def test_models_load_once_per_process(self):
        counter = {'st': 0, 'ce': 0}
        with patch.dict(sys.modules, {'sentence_transformers': self._fake_st_module(counter)}):
            from knowledge_base.services.embedding import EmbeddingService
            EmbeddingService().embed('a')
            EmbeddingService().embed('b')
            self.pipeline.get_cross_encoder()
            self.pipeline.get_cross_encoder()
        self.assertEqual(counter['st'], 1)
        self.assertEqual(counter['ce'], 1)

    def test_offline_mode_loads_models_from_local_files_only(self):
        counter = {'st': 0, 'ce': 0}
        with patch.dict(sys.modules, {'sentence_transformers': self._fake_st_module(counter)}), \
                patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}):
            self.pipeline.get_cross_encoder()
        self.assertEqual(counter['ce_kwargs'], {'local_files_only': True})

    def test_no_provider_means_no_vectors(self):
        from knowledge_base.services.embedding import EmbeddingService
        with patch('knowledge_base.services.embedding.get_sentence_transformer', return_value=None):
            service = EmbeddingService()
            self.assertEqual(service.embed('edema'), [])
            self.assertIsNone(service.embed_query('edema'))
            self.assertEqual(len(service.embed('edema', allow_hash_fallback=True)[0]), service.dim)

    def test_failed_load_is_not_retried_on_every_request(self):
        from knowledge_base.services.embedding import get_sentence_transformer
        module = types.ModuleType('sentence_transformers')
        calls = {'n': 0}

        class Broken:
            def __init__(self, *a, **k):
                calls['n'] += 1
                raise OSError('no network')

        module.SentenceTransformer = Broken
        with patch.dict(sys.modules, {'sentence_transformers': module}):
            self.assertIsNone(get_sentence_transformer('BAAI/bge-small-en-v1.5'))
            self.assertIsNone(get_sentence_transformer('BAAI/bge-small-en-v1.5'))
        self.assertEqual(calls['n'], 1)


class RetrievalPipelineTests(TestCase):
    def setUp(self):
        from knowledge_base.models import KnowledgeChunk
        self.source = _make_source('pipe-source', 'cc_by')
        texts = [
            'Edema in nephrotic syndrome results from hypoalbuminaemia and low oncotic pressure.',
            'Malaria is treated with artemisinin combination therapy in most regions.',
            'Appendicitis typically starts with periumbilical pain migrating to the right iliac fossa.',
        ]
        for i, text in enumerate(texts):
            KnowledgeChunk.objects.create(source=self.source, text=text, text_hash=f'h{i}', license='cc_by',
                                          attribution='A', approval_state=KnowledgeChunk.APPROVAL_AUTO,
                                          locator=f'ch{i}')

    def _pipeline(self):
        from knowledge_base.retrieval.pipeline import RetrievalPipeline

        class NoEmbedding:
            def embed_query(self, query):
                return None

        return RetrievalPipeline(embedding=NoEmbedding(), cache=None)

    def test_cache_key_is_stable_and_not_hash_based(self):
        from knowledge_base.retrieval.pipeline import RetrievalPipeline
        a = RetrievalPipeline.cache_key('edema', 8, None, None, True, True)
        self.assertEqual(a, RetrievalPipeline.cache_key('edema', 8, None, None, True, True))
        self.assertTrue(a.startswith('kb:ret:v2:'))
        self.assertNotEqual(a, RetrievalPipeline.cache_key('edema', 8, None, None, False, True))

    def test_bm25_finds_the_relevant_chunk_and_rerank_toggle_is_honoured(self):
        pipeline = self._pipeline()
        with patch('knowledge_base.retrieval.pipeline.get_cross_encoder', return_value=None), \
                patch.object(type(pipeline), '_rerank') as rerank, \
                override_settings(KB_USE_RERANK=False, KB_USE_KG_BOOST=False):
            results = pipeline.search('nephrotic syndrome edema', top_k=2)
        rerank.assert_not_called()
        self.assertTrue(results)
        self.assertIn('nephrotic', results[0].text)
        self.assertEqual(results[0].citation['source_slug'], 'pipe-source')

    def test_citations_are_fetched_in_one_query(self):
        from knowledge_base.retrieval.pipeline import RetrievedChunk
        chunks = [RetrievedChunk(chunk_id=c.id, text=c.text, source_slug='pipe-source', source_name='S',
                                 attribution='A', license='cc_by')
                  for c in self.source.chunks.all()]
        with self.assertNumQueries(1):
            self._pipeline()._attach_citations(chunks)
        self.assertTrue(all(c.citation for c in chunks))
