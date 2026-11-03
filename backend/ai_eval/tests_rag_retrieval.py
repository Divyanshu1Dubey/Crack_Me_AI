"""Regression tests for textbook retrieval (ai_engine.lexical_index + RAGPipeline).

Before 2026-11 the store was scanned only up to RAG_MAX_SEARCH_CHUNKS rows in
rowid order (74% of chunks were never searched), the tokenizer dropped Greek
letters, alias copies filled the top-k, personal/administrative PDFs were
retrievable, constructing the pipeline wrote to the git-tracked store, and a
total provider failure returned an operator message as the answer.
"""
import json
import os
import shutil
import sqlite3
import tempfile
from unittest import mock

from django.test import SimpleTestCase, override_settings

from ai_engine import lexical_index as lx


def make_store(path, rows):
    """rows: (id, text, book, page, source_file)"""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, document TEXT NOT NULL, book TEXT NOT NULL, "
                 "page INTEGER DEFAULT 0, chunk_index INTEGER DEFAULT 0, source_file TEXT DEFAULT '', tokens TEXT DEFAULT '')")
    conn.execute("CREATE TABLE idf_cache (term TEXT PRIMARY KEY, idf REAL NOT NULL)")
    conn.executemany("INSERT INTO chunks (id, document, book, page, source_file, tokens) VALUES (?, ?, ?, ?, ?, ?)",
                     [(cid, text, book, page, src, json.dumps([])) for cid, text, book, page, src in rows])
    conn.commit()
    conn.close()


class TokenizerTests(SimpleTestCase):
    def test_greek_letters_diacritics_hyphens(self):
        self.assertEqual(lx.tokenize('β-blockers in Sjögren syndrome'), ['beta', 'blocker', 'sjogren', 'syndrome'])
        self.assertIn('alpha1', lx.tokenize('α1 antitrypsin'))

    def test_stopwords_and_plural_stemming(self):
        self.assertEqual(lx.tokenize('The kidneys and the arteries'), ['kidney', 'artery'])
        # Query and documents are stemmed the same way, so 'diabetes' matching 'diabete' is fine.
        self.assertEqual(lx.tokenize('Diabetes mellitus'), ['diabete', 'mellitus'])
        self.assertEqual(lx.tokenize('virus'), ['virus'])  # -us kept
        self.assertEqual(lx.tokenize('Diabetes mellitus', stem=False), ['diabetes', 'mellitus'])

    def test_content_key_ignores_case_and_spacing(self):
        self.assertEqual(lx.content_key('Malaria  is\nCOMMON.'), lx.content_key('malaria is common'))


class CorpusPolicyTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, 'rag_store.sqlite3')
        rows = [
            # same file indexed under two aliases with different chunking: keep the finer one
            ('a1', 'Malaria fine chunk one about artesunate.', 'med_malaria', 1, 'med_malaria.md'),
            ('a2', 'Malaria fine chunk two about chloroquine.', 'med_malaria', 1, 'med_malaria.md'),
            ('b1', 'Malaria coarse chunk about artesunate and chloroquine.', 'Med Malaria (web_knowledge)', 1, 'med_malaria.md'),
            # identical content twice
            ('c1', 'Typhoid fever is caused by Salmonella Typhi.', 'med_typhoid', 1, 'med_typhoid.md'),
            ('c2', 'typhoid FEVER is caused by salmonella typhi', 'notes', 1, 'notes.md'),
            # personal / administrative document
            ('d1', 'Affidavit malaria name change declaration', 'Affidavit For Name', 1, 'AFFIDAVIT FOR NAME_x.pdf'),
            # raw question paper
            ('e1', 'Q12. Drug of choice for malaria? A) x B) artesunate', 'CMS PYQ 2021 Paper 1', 1, '2021paper1.txt'),
            ('f1', 'Topic frequency of malaria questions by year.', 'CMS PYQ Database 2018-2024', 1, 'cms_pyq_database_2018_2024.md'),
        ]
        make_store(self.path, rows)

    def test_policy(self):
        docs, stats = lx.load_documents(self.path)
        ids = {d.chunk_id for d in docs}
        self.assertTrue({'a1', 'a2'} <= ids)
        self.assertNotIn('b1', ids)                     # alias copy
        self.assertEqual(len(ids & {'c1', 'c2'}), 1)    # duplicate content
        self.assertNotIn('d1', ids)                     # excluded document
        papers = {d.chunk_id for d in docs if d.question_paper}
        self.assertEqual(papers, {'e1'})                # the PYQ *database* is not a paper
        self.assertEqual((stats.dropped_alias_copies, stats.dropped_excluded_documents), (1, 1))

    def test_question_papers_only_with_explicit_book(self):
        index = lx.BM25Index(lx.load_documents(self.path)[0])
        default = [d.chunk_id for _s, d in index.search('drug of choice malaria', 10)]
        self.assertNotIn('e1', default)
        self.assertNotIn('d1', default)
        explicit = [d.chunk_id for _s, d in index.search('drug of choice malaria', 10, book='CMS PYQ 2021 Paper 1')]
        self.assertEqual(explicit, ['e1'])


class RagPipelineTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, 'rag_store.sqlite3')
        filler = [(f'f{i}', f'Filler passage number {i} about general clinical medicine and history taking.',
                   f'Filler Book {i % 7}', i, f'filler{i % 7}.md') for i in range(2500)]
        target = [('target', 'Kawasaki disease is treated with intravenous immunoglobulin and aspirin. '
                   'Coronary artery aneurysm is the most serious complication of Kawasaki disease.',
                   'peds_kawasaki', 3, 'peds_kawasaki.md')]
        make_store(self.path, filler + target)
        lx.invalidate()
        self.addCleanup(lx.invalidate)
        self.settings_cm = override_settings(CHROMA_DB_DIR=self.dir)
        self.settings_cm.enable()
        self.addCleanup(self.settings_cm.disable)

    def _rag(self):
        from ai_engine.rag_pipeline import RAGPipeline
        return RAGPipeline()

    def test_chunks_beyond_old_scan_cap_are_found(self):
        results = self._rag().search('treatment of Kawasaki disease', n_results=3)
        self.assertEqual(results[0]['book'], 'peds_kawasaki')
        self.assertEqual(results[0]['page'], 3)

    def test_constructor_does_not_write_to_the_store(self):
        before = os.stat(self.path).st_mtime_ns
        rag = self._rag()
        rag.search('kawasaki', 1)
        rag.get_stats()
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)
        self.assertFalse(os.path.exists(self.path + '-wal'))

    def test_index_rebuilds_when_store_changes(self):
        rag = self._rag()
        self.assertFalse([r for r in rag.search('organophosphate poisoning atropine', 5) if r['book'] == 'tox'])
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO chunks (id, document, book, page, source_file) VALUES "
                     "('new', 'Organophosphate poisoning is treated with atropine and pralidoxime.', 'tox', 9, 'tox.md')")
        conn.commit()
        conn.close()
        self.assertEqual(rag.search('organophosphate poisoning atropine', 5)[0]['book'], 'tox')

    def test_n_results_is_clamped(self):
        rag = self._rag()
        self.assertEqual(len(rag.search('kawasaki', 0)), 1)
        self.assertLessEqual(len(rag.search('kawasaki', 'x')), 5)
        self.assertEqual(rag.search('   ', 5), [])

    def test_offline_mode_answers_extractively_without_any_llm(self):
        rag = self._rag()
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': '1'}), \
                mock.patch.object(type(rag), '_init_ai_clients', side_effect=AssertionError('no LLM in offline mode')):
            res = rag.rag_answer('What is the treatment of Kawasaki disease?')
        self.assertFalse(res['generated'])
        self.assertTrue(res['offline'])
        self.assertIn('immunoglobulin', res['answer'])
        self.assertIn('[peds_kawasaki p.3]', res['answer'])

    def test_total_provider_failure_falls_back_to_extractive_answer(self):
        rag = self._rag()
        with mock.patch.object(type(rag), '_generate_answer', return_value=None):
            res = rag.rag_answer('Kawasaki disease complication coronary aneurysm')
        self.assertFalse(res['generated'])
        self.assertNotIn('configure API keys', res['answer'])
        self.assertIn('Coronary artery aneurysm', res['answer'])

    def test_generated_answer_is_flagged(self):
        rag = self._rag()
        with mock.patch.dict(os.environ, {'AI_OFFLINE_MODE': ''}), \
                mock.patch.object(type(rag), '_generate_answer', return_value='IVIG plus aspirin.'):
            res = rag.rag_answer('treatment of Kawasaki disease')
        self.assertTrue(res['generated'])
        self.assertEqual(res['answer'], 'IVIG plus aspirin.')


class HermeticTestRunTests(SimpleTestCase):
    """The test runner must never inherit live credentials from backend/.env."""

    def test_external_service_secrets_are_blank_under_the_test_runner(self):
        from django.conf import settings
        for name in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'CEREBRAS_API_KEY', 'OPENROUTER_API_KEY',
                     'OMNIROUTE_API_KEY', 'MISTRAL_API_KEY', 'GITHUB_TOKEN'):
            self.assertEqual(getattr(settings, name, ''), '', name)
        for name in ('SENTRY_DSN', 'OPENROUTER_API_KEY2', 'DEEPSEEK_API_KEY', 'RAZORPAY_KEY_SECRET'):
            self.assertEqual(os.environ.get(name, ''), '', name)


class ExtractiveAnswerTests(SimpleTestCase):
    def test_no_overlap_returns_none(self):
        self.assertIsNone(lx.extractive_answer('appendicitis signs', [{'text': 'Measles causes Koplik spots on buccal mucosa.', 'book': 'b', 'page': 1}]))

    def test_sentences_are_verbatim_and_cited(self):
        passages = [{'text': 'Measles causes Koplik spots on the buccal mucosa. It is a paramyxovirus.', 'book': 'peds_measles', 'page': 2}]
        res = lx.extractive_answer('What are Koplik spots in measles?', passages)
        self.assertIn('Measles causes Koplik spots on the buccal mucosa. [peds_measles p.2]', res['answer'])
        self.assertEqual(res['citations'][0]['book'], 'peds_measles')
