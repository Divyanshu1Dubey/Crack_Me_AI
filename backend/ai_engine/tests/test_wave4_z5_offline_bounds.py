"""Regression tests: the offline composer's work is bounded by its input
(audit 2026-11, wave 4, Z5 on request of Z9).

* find_similar_pyq de-duplicated the question's words with a list-membership
  test, so a long question cost quadratic time. The probe is now built with a
  dict and capped at MAX_PROBE_CANDIDATES distinct words, and it picks the
  same words as before for ordinary questions.
* compose_offline_answer, retrieve_passages and find_similar_pyq cut their
  text to MAX_QUERY_CHARS as defence in depth (every API caller already caps
  its input). The bound still covers a full-length stem plus the correct
  option that the explain views append.

The textbook store is never opened: the RAG pipeline and the corpus IDF are
patched.
"""
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from ai_engine import offline
from ai_engine.lexical_index import tokenize

User = get_user_model()

# Generous: the linear code needs about 0.1 s for the huge input below, the
# old quadratic de-duplication about a minute.
FAST_SECONDS = 5.0

PASSAGES = [
    {'text': ('Nephrotic syndrome is characterised by heavy proteinuria, hypoalbuminaemia and edema. '
              'Edema in nephrotic syndrome results from low plasma oncotic pressure caused by hypoalbuminaemia.'),
     'book': 'Ghai Pediatrics', 'page': 12, 'score': 9.0},
]


def _huge_text(n: int = 100_000) -> str:
    """About 1.1 MB of distinct ten-character words."""
    return ' '.join(f'term{i:06d}' for i in range(n))


def _previous_probe(text: str) -> list:
    """find_similar_pyq's probe before the fix (reference for equivalence)."""
    raw_terms = []
    for tok in tokenize(text or '', stem=False):
        if len(tok) >= 5 and tok not in raw_terms:
            raw_terms.append(tok)
    return sorted(raw_terms, key=len, reverse=True)[:4]


class ProbeTermTests(SimpleTestCase):
    def test_ordinary_questions_get_the_same_probe_as_before(self):
        vignette = (
            'A 6-year-old boy presents with periorbital puffiness and pedal edema for two weeks. '
            'Urine shows 4+ proteinuria without haematuria; serum albumin is 1.8 g/dL and '
            'cholesterol is raised. Complement levels are normal. Which of the following is the '
            'most likely finding on electron microscopy of the renal biopsy? '
        ) * 12
        samples = [
            'mechanism of edema in nephrotic syndrome',
            'Edema EDEMA edema oedema Nephrotic nephrotic syndrome syndromes',
            'alpha bravo delta gamma kappa sigma',          # length ties keep their order
            'β-blocker overdose: glucagon or atropine?',      # Greek folding
            'the cat is on a mat',                            # no word of five letters
            '',
            vignette,
        ]
        for text in samples:
            with self.subTest(text=text[:40]):
                self.assertEqual(offline._pyq_probe_terms(text), _previous_probe(text))

    def test_a_huge_question_is_probed_in_linear_time(self):
        text = _huge_text()
        start = time.perf_counter()
        probe = offline._pyq_probe_terms(text)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, FAST_SECONDS)
        self.assertEqual(probe, ['term000000', 'term000001', 'term000002', 'term000003'])

    def test_only_the_first_distinct_words_are_candidates(self):
        filler = ' '.join(f'w{i:04d}' for i in range(offline.MAX_PROBE_CANDIDATES + 100))
        probe = offline._pyq_probe_terms(f'{filler} glomerulonephritis')
        self.assertEqual(len(probe), offline.PYQ_PROBE_TERMS)
        self.assertNotIn('glomerulonephritis', probe)
        self.assertIn('glomerulonephritis', offline._pyq_probe_terms('w0001 w0002 glomerulonephritis'))

    def test_query_limit_covers_a_full_stem_plus_the_correct_option(self):
        from ai_engine import views
        self.assertEqual(offline.MAX_QUERY_CHARS,
                         views.MAX_AI_INPUT_CHARS + 1 + views.MAX_OPTION_CHARS)
        legit = 'a' * views.MAX_AI_INPUT_CHARS + ' ' + 'b' * views.MAX_OPTION_CHARS
        self.assertEqual(offline._bounded_query(legit), legit)
        self.assertEqual(len(offline._bounded_query(legit + ' and more')), offline.MAX_QUERY_CHARS)
        self.assertEqual(offline._bounded_query('  edema  '), 'edema')
        self.assertEqual(offline._bounded_query(None), '')


class BoundedComposerTests(TestCase):
    def setUp(self):
        from questions.models import Question, Subject
        for target, value in (('ai_engine.offline._global_idf', None),
                              ('ai_engine.services.rag_disabled', False)):
            p = patch(target, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.rag = MagicMock()
        self.rag.search.return_value = list(PASSAGES)
        p = patch('ai_engine.rag_pipeline.RAGPipeline', return_value=self.rag)
        self.rag_cls = p.start()
        self.addCleanup(p.stop)

        subject = Subject.objects.create(name='Pediatrics PYQ', code='PEDPYQ')
        self.q = Question.objects.create(
            question_text='Edema in nephrotic syndrome is primarily due to which mechanism?',
            option_a='Increased hydrostatic pressure', option_b='Decreased plasma oncotic pressure',
            option_c='Lymphatic obstruction', option_d='Capillary leak', correct_answer='B',
            year=2019, subject=subject, explanation='Hypoalbuminaemia lowers plasma oncotic pressure.',
        )
        self.admin = User.objects.create(username='bounds-admin', role='admin')

    def test_retrieve_passages_searches_with_a_bounded_query(self):
        passages = offline.retrieve_passages(_huge_text(), k=3)
        self.assertEqual(passages, PASSAGES)
        self.rag.search.assert_called_once()
        self.assertLessEqual(len(self.rag.search.call_args[0][0]), offline.MAX_QUERY_CHARS)

        self.rag_cls.reset_mock()
        self.assertEqual(offline.retrieve_passages('   '), [])
        self.rag_cls.assert_not_called()

    def test_a_megabyte_question_is_composed_fast_from_a_bounded_query(self):
        huge = 'What is the mechanism of edema in nephrotic syndrome? ' + _huge_text()
        with patch.object(offline, 'find_similar_pyq', wraps=offline.find_similar_pyq) as pyq, \
                CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            offline.compose_offline_answer(huge, user=self.admin)
            elapsed = time.perf_counter() - start
        self.assertLess(elapsed, FAST_SECONDS)
        self.assertLessEqual(len(self.rag.search.call_args[0][0]), offline.MAX_QUERY_CHARS)
        pyq.assert_called_once()
        self.assertLessEqual(len(pyq.call_args[0][0]), offline.MAX_QUERY_CHARS)
        # One question-bank query, prefiltered on at most PYQ_PROBE_TERMS words.
        self.assertEqual(len(queries), 1)
        self.assertLessEqual(queries[0]['sql'].upper().count(' LIKE '), offline.PYQ_PROBE_TERMS)

    def test_an_ordinary_question_still_gets_textbook_sentences_and_its_past_question(self):
        result = offline.compose_offline_answer('What is the mechanism of edema in nephrotic syndrome?',
                                                user=self.admin)
        self.assertTrue(result.grounded)
        self.assertIn('[Ghai Pediatrics p.12]', result.answer)
        self.assertIsNotNone(result.pyq)
        self.assertEqual(result.pyq['id'], self.q.id)
        self.rag.search.assert_called_once_with(
            'What is the mechanism of edema in nephrotic syndrome?', n_results=8,
        )
