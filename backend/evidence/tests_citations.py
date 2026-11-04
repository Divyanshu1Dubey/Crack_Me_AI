"""Student citations: ``GET /api/evidence/questions/<qid>/citations/`` (2026-11).

docs/audit/MEDICAL_ACCURACY_DESIGN.md ground rule 4: students see accepted citations (title, edition,
chapter, page label) and snippets of at most EVIDENCE_SNIPPET_MAX_CHARS, never pages, paths or hashes.
A citation names the option it supports, so it follows the answer's entitlement rule: a viewer who may
not see the answer gets an empty, locked answer (HTTP 200: a 402 would open the paywall from the
reveal panel).
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from accounts.models_freemium import FreeShowcaseQuestion
from evidence.models import EvidenceSource, QuestionEvidence
from evidence.services import snippet_sha1
from questions.content_hashes import stem_hash
from questions.editorial import change_answer_key
from questions.models import Question, Subject

User = get_user_model()

PASSAGE = (
    'Laryngomalacia is the most common congenital anomaly of the larynx. It is the most frequent cause of '
    'congenital stridor in infants. The stridor is inspiratory and worse when the infant lies supine or feeds. '
    'Most cases resolve spontaneously by eighteen to twenty-four months of age without any intervention. '
    'Severe cases with failure to thrive or apnoea are treated with supraglottoplasty. '
    'Subglottic stenosis, vocal cord palsy and laryngeal webs are rarer causes of stridor in this age group.'
)
FORBIDDEN_KEYS = {'sha256', 'source_sha256', 'path', 'file', 'file_path', 'text', 'page_text', 'char_start',
                  'char_end', 'bbox', 'score', 'review_status', 'content_sha256', 'snippet_sha1'}


class StudentCitationsTests(TestCase):
    def setUp(self):
        cache.clear()   # throttle buckets
        self.subject = Subject.objects.create(name='Pediatrics', code='PED')
        self.admin = User.objects.create_superuser(username='ev_admin', email='ev_admin@cracklabs.test',
                                                   password='testpassword123')
        self.student = User.objects.create_user(username='ev_student', email='ev_student@cracklabs.test',
                                                password='testpassword123')
        self.question = Question.objects.create(
            question_text='Most common cause of congenital stridor in an infant is?', option_a='Laryngomalacia',
            option_b='Subglottic stenosis', option_c='Vocal cord palsy', option_d='Laryngeal web',
            correct_answer='A', subject=self.subject, year=2023)
        self.textbook = self.source('a', 'Nelson Textbook of Pediatrics', tier=3, display='snippet', edition='21st')
        self.client = APIClient()

    # ------------------------------------------------------------------ helpers

    def source(self, ch, title, *, tier, display, edition=''):
        return EvidenceSource.objects.create(sha256=ch * 64, title=title, edition=edition, year=2020, tier=tier,
                                             kind='textbook', student_display=display)

    def row(self, source=None, *, snippet=PASSAGE, review_status='accepted', visible=True, verified=True,
            key=None, page_label='1450', option='A', stance='supports', question=None):
        question = question or self.question
        return QuestionEvidence.objects.create(
            question=question, source=source or self.textbook, page_start=1460, page_end=1460, page_label=page_label,
            snippet=snippet, snippet_sha1=snippet_sha1(snippet + str(QuestionEvidence.objects.count())),
            quote_verified=verified, option_letter=option, stance=stance, origin='admin_manual',
            review_status=review_status, student_visible=visible,
            key_at_creation=key if key is not None else question.correct_answer, content_sha256=stem_hash(question))

    def url(self, question=None):
        return f'/api/evidence/questions/{(question or self.question).pk}/citations/'

    def get(self, user=None, question=None):
        self.client.force_authenticate(user=user)
        return self.client.get(self.url(question))

    def showcase(self, question=None):
        FreeShowcaseQuestion.objects.create(question=question or self.question, year=2023, position=1)

    # ------------------------------------------------------------------ entitlement

    def test_viewers_who_may_not_see_the_answer_get_nothing(self):
        self.row()
        for user in (None, self.student):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                res = self.get(user)
                self.assertEqual(res.status_code, 200)
                self.assertEqual((res.data['citations'], res.data['locked']), ([], True))
                self.assertNotIn('image_context', res.data)
                self.assertEqual(res['Cache-Control'], 'private, no-store')

    def test_showcase_questions_are_open_to_everyone(self):
        self.row()
        self.showcase()
        for user in (None, self.student):
            with self.subTest(user=getattr(user, 'username', 'anonymous')):
                res = self.get(user)
                self.assertEqual(res.status_code, 200)
                self.assertFalse(res.data['locked'])
                self.assertEqual(len(res.data['citations']), 1)

    def test_scholarship_questions_stay_locked_for_free_users(self):
        self.row()
        Question.objects.filter(pk=self.question.pk).update(is_scholarship_eligible=True)
        self.showcase()
        self.assertTrue(self.get(self.student).data['locked'])

    def test_premium_students_and_admins_see_citations(self):
        self.row()
        with mock.patch('questions.views._is_premium', return_value=True):
            self.assertEqual(len(self.get(self.student).data['citations']), 1)
        self.assertEqual(len(self.get(self.admin).data['citations']), 1)

    def test_inactive_and_unknown_questions(self):
        self.row()
        self.showcase()
        Question.objects.filter(pk=self.question.pk).update(is_active=False)
        self.assertEqual(self.get(self.student).status_code, 404)
        self.assertEqual(self.get(None).status_code, 404)
        self.assertEqual(self.get(self.admin).status_code, 200)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get('/api/evidence/questions/999999/citations/').status_code, 404)

    # ------------------------------------------------------------------ what a student sees

    def test_citation_shape_never_carries_pages_paths_or_hashes(self):
        self.row()
        citation = self.get(self.admin).data['citations'][0]
        self.assertFalse(FORBIDDEN_KEYS & set(citation), citation)
        self.assertEqual(set(citation['source']), {'title', 'edition', 'year', 'kind'})
        self.assertEqual(citation['citation'], 'Nelson Textbook of Pediatrics, 21st, 2020, p. 1450')
        self.assertEqual((citation['page_label'], citation['option_letter'], citation['stance']), ('1450', 'A', 'supports'))
        self.assertTrue(citation['verified'])

    def test_snippets_are_short_whole_sentences_of_the_passage(self):
        self.assertGreater(len(PASSAGE), 400)
        self.row()
        snippet = self.get(self.admin).data['citations'][0]['snippet']
        self.assertTrue(0 < len(snippet) <= 240, len(snippet))
        self.assertIn(snippet.rstrip('…'), PASSAGE)
        self.assertIn('stridor', snippet.lower())

    def test_citation_only_sources_show_no_snippet(self):
        notes = self.source('b', 'Coaching notes', tier=4, display='citation')
        self.row(notes)
        citation = self.get(self.admin).data['citations'][0]
        self.assertEqual(citation['snippet'], '')
        self.assertTrue(citation['citation'].startswith('Coaching notes'))

    def test_only_accepted_visible_verified_current_rows_of_shown_sources(self):
        paper = self.source('c', 'UPSC CMS 2023 Paper I', tier=5, display='snippet')
        hidden = self.source('d', 'Hidden book', tier=3, display='none')
        self.row(paper)
        self.row(hidden)
        self.row(review_status='pending', visible=False)
        self.row(review_status='rejected', visible=False)
        self.row(review_status='stale', visible=False)
        self.row(verified=False)
        self.row(key='B')                         # recorded for another key
        self.assertEqual(self.get(self.admin).data['citations'], [])
        good = self.row()
        self.assertEqual([c['id'] for c in self.get(self.admin).data['citations']], [good.pk])

    def test_at_most_three_citations_textbooks_first(self):
        notes = self.source('e', 'Coaching notes', tier=4, display='snippet')
        rows = [self.row(notes), self.row(), self.row(), self.row(), self.row()]
        ids = [c['id'] for c in self.get(self.admin).data['citations']]
        self.assertEqual(len(ids), 3)
        self.assertNotIn(rows[0].pk, ids)

    def test_a_key_change_hides_the_old_citations(self):
        self.row()
        with self.captureOnCommitCallbacks(execute=True):
            change_answer_key(Question.objects.get(pk=self.question.pk), 'B', actor=self.admin,
                              reason='Official key says B for this item.')
        self.assertEqual(self.get(self.admin).data['citations'], [])
        self.assertEqual(QuestionEvidence.objects.get().review_status, 'stale')

    # ------------------------------------------------------------------ throttle

    def test_throttle_scope(self):
        from django.conf import settings
        from evidence.views import StudentCitationsView
        self.assertEqual(StudentCitationsView.throttle_scope, 'evidence_student')
        self.assertIn('evidence_student', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        self.showcase()
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'evidence_student': '2/hour'}):
            codes = [self.get(self.student).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
