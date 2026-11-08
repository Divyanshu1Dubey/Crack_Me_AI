"""The AI explanation batch (questions/explanation_batch.py): which questions, the checks before anything is saved
(the AI's answer is the key, a usable structure, no made-up citations), provenance, checkpoints and claims, the admin
API and the review queue."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from ai_engine.services import AIOutputUnusable, AIUnavailable
from questions import explanation_batch as batch
from questions.content_hashes import stem_hash
from questions.models import ExplanationBatchItem, Question, QuestionImage, Subject

User = get_user_model()
ONLINE = mock.patch('ai_engine.offline.ai_offline_mode', return_value=False)

GOOD = {
    'ai_verified_answer': 'B', 'answer_mismatch': False,
    'why_correct': 'Bupivacaine is an amide local anaesthetic with the longest duration of action of these agents.',
    'why_wrong': {'A': 'Lignocaine is intermediate acting.', 'C': 'Prilocaine is intermediate acting.',
                  'D': 'Ropivacaine is long acting but shorter than bupivacaine (Miller, p. 1032).'},
    'core_concept': 'Duration of action of local anaesthetics depends on protein binding.',
    'mnemonic': 'Bupi = Big and long',
    'high_yield_points': ['Bupivacaine is the most cardiotoxic.', 'Textbook Reference: Miller, Chapter 42'],
    'clinical_pearl': 'Use ropivacaine when cardiotoxicity is a concern.',
    'textbook_reference': {'book': 'Miller', 'chapter': '42', 'page': '1032'},
    'similar_pyq': 'CMS 2022 Paper 1 asked this.',
}


class FakeAI:
    last_provider = 'fake/provider'

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def explain_after_answer(self, **kwargs):
        self.calls += 1
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return dict(result)


class _Bank(TestCase):

    def setUp(self):
        self.subject = Subject.objects.create(name='Anaesthesia', code='AN-B')

    def q(self, **kw):
        kw.setdefault('question_text', 'Which drug is the longest acting local anaesthetic?')
        for letter, text in zip('abcd', ('Lignocaine', 'Bupivacaine', 'Prilocaine', 'Ropivacaine')):
            kw.setdefault(f'option_{letter}', text)
        kw.setdefault('correct_answer', 'B')
        kw.setdefault('exam_type', 'cms')
        kw.setdefault('year', 2020)
        return Question.objects.create(subject=self.subject, **kw)


class SelectionTests(_Bank):

    def test_which_questions_need_an_explanation(self):
        missing = self.q()
        placeholder = self.q(explanation='Reference: NEET PG previous year question bank.', exam_type='neet_pg')
        tokens = self.q(explanation='[[img:3]]')
        stale = self.q(explanation='Old text for C', explanation_for_key='C')
        has_one = self.q(explanation='Bupivacaine lasts longest.', explanation_for_key='B')
        locked = self.q(lock_explanation=True)
        no_key = self.q(correct_answer='')
        hidden = self.q(is_active=False)
        figure = self.q()
        QuestionImage.objects.create(question=figure, url='/media/x.png', role='primary', page_number=1)
        ids = set(batch.needs_explanation().values_list('pk', flat=True))
        self.assertEqual(ids, {missing.pk, placeholder.pk, tokens.pk, stale.pk})
        self.assertEqual(set(batch.needs_explanation(include_stale=False).values_list('pk', flat=True)),
                         {missing.pk, placeholder.pk, tokens.pk})
        self.assertEqual(set(batch.needs_explanation(exam_type='neet_pg').values_list('pk', flat=True)),
                         {placeholder.pk})
        self.assertFalse({has_one.pk, locked.pk, no_key.pk, hidden.pk, figure.pk} & ids)

    def test_the_count_by_exam_counts_questions(self):
        # needs_explanation is DISTINCT: a values_list count over it counted exam x ordering combinations
        for year in (2018, 2019, 2020):
            self.q(year=year, question_text=f'CMS question {year}')
        self.q(exam_type='neet_pg', year=2021, question_text='NEET PG question')
        self.assertEqual(batch.needed_by_exam(), {'cms': 3, 'neet_pg': 1})
        self.assertEqual(batch.needed_by_exam(exam_type='cms', years=[2019]), {'cms': 1})


@ONLINE
class ProcessingTests(_Bank):

    def test_a_saved_explanation_has_provenance_and_no_made_up_citations(self, _online):
        q = self.q()
        run = batch.create_run()
        stats = batch.run_batch(run, ai=FakeAI(GOOD))
        self.assertEqual(stats['done'], 1)
        q.refresh_from_db()
        self.assertEqual((q.explanation_status, q.explanation_origin, q.explanation_for_key),
                         ('ai_generated', 'ai', 'B'))
        self.assertEqual(q.explanation_stem_hash, stem_hash(q))
        self.assertIn('**Answer: B. Bupivacaine**', q.explanation)
        self.assertIn('- **A. Lignocaine**: Lignocaine is intermediate acting.', q.explanation)
        self.assertNotIn('Miller', q.explanation)
        self.assertNotIn('Textbook Reference', q.explanation)
        self.assertNotIn('CMS 2022', q.explanation)
        self.assertEqual(q.concept_explanation, GOOD['core_concept'])
        self.assertEqual(q.mnemonic, 'Bupi = Big and long')
        item = ExplanationBatchItem.objects.get(question=q)
        self.assertEqual((item.status, item.provider), ('done', 'fake/provider'))

    def test_an_ai_that_picks_another_answer_saves_nothing(self, _online):
        q = self.q()
        run = batch.create_run()
        stats = batch.run_batch(run, ai=FakeAI(dict(GOOD, ai_verified_answer='D', answer_mismatch=True)))
        self.assertEqual(stats['disagrees'], 1)
        q.refresh_from_db()
        self.assertEqual(q.explanation, '')
        item = ExplanationBatchItem.objects.get(question=q)
        self.assertEqual(item.status, 'disagrees')
        self.assertIn('AI chose D; stored key B', item.detail)

    def test_unusable_output_and_outages_are_retried_then_given_up(self, _online):
        self.q()
        self.q(question_text='Second question about local anaesthetics')
        run = batch.create_run()
        ai = FakeAI(AIOutputUnusable('bad json'))
        stats = batch.run_batch(run, ai=ai)
        self.assertEqual(stats['retry'], 4)
        self.assertEqual(stats['invalid'], 2)
        self.assertEqual(ai.calls, 6)  # 3 attempts each
        run2 = batch.create_run()
        stats = batch.run_batch(run2, ai=FakeAI(AIUnavailable('all providers down')))
        self.assertEqual(stats['failed'], 2)
        thin = dict(GOOD, why_wrong={'A': 'Intermediate acting.'})
        run3 = batch.create_run()
        self.assertEqual(batch.run_batch(run3, ai=FakeAI(thin))['invalid'], 2)

    def test_offline_mode_stops_without_spending_an_attempt(self, _online):
        self.q()
        run = batch.create_run()
        stats = batch.run_batch(run, ai=FakeAI(AIUnavailable('offline', offline=True)))
        self.assertEqual(stats['stopped: AI is offline'], 1)
        item = ExplanationBatchItem.objects.get(run=run)
        self.assertEqual((item.status, item.attempts), ('queued', 0))
        with mock.patch('ai_engine.offline.ai_offline_mode', return_value=True):
            self.assertEqual(batch.run_batch(run, ai=FakeAI(GOOD))['refused: AI_OFFLINE_MODE is on'], 1)

    def test_a_question_edited_or_answered_since_it_was_queued_is_skipped(self, _online):
        edited = self.q()
        written = self.q(question_text='Another local anaesthetic question')
        run = batch.create_run()
        Question.objects.filter(pk=edited.pk).update(question_text='An admin rewrote this question')
        Question.objects.filter(pk=written.pk).update(explanation='An editor wrote this.', explanation_for_key='B')
        stats = batch.run_batch(run, ai=FakeAI(GOOD))
        self.assertEqual(stats['skipped'], 2)
        written.refresh_from_db()
        self.assertEqual(written.explanation, 'An editor wrote this.')

    def test_claims_never_hand_out_one_question_twice_and_expire(self, _online):
        self.q()
        self.q(question_text='Another local anaesthetic question')
        run = batch.create_run()
        first, second = batch.claim_next(run), batch.claim_next(run)
        self.assertNotEqual(first.pk, second.pk)
        self.assertIsNone(batch.claim_next(run))
        from django.utils import timezone
        from datetime import timedelta
        later = timezone.now() + timedelta(seconds=batch.LEASE_SECONDS + 5)
        self.assertEqual(batch.claim_next(run, now=later).pk, first.pk)  # an abandoned claim is taken again

    def test_a_finished_run_processes_nothing_again(self, _online):
        self.q()
        run = batch.create_run()
        batch.run_batch(run, ai=FakeAI(GOOD))
        ai = FakeAI(GOOD)
        self.assertEqual(sum(batch.run_batch(run, ai=ai).values()), 0)
        self.assertEqual(ai.calls, 0)


class CleanTextTests(SimpleTestCase):

    def test_made_up_references_are_removed(self):
        text = 'Bupivacaine lasts longest (Miller, p. 1032).\nReference: Miller 9th ed, Chapter 42\nMore text [cite: 3].'
        self.assertEqual(batch.clean_text(text), 'Bupivacaine lasts longest.\nMore text.')

    def test_provider_noise_is_unusable(self):
        self.assertEqual(batch.clean_text('Sorry, rate limit exceeded for this API key.'), '')
        self.assertEqual(batch.clean_text(None), '')


@ONLINE
class ApiTests(_Bank):

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.admin = User.objects.create_user(username='expl-admin', password='x', role='admin', is_staff=True)
        self.student = User.objects.create_user(username='expl-student', password='x')

    def test_admin_only_counts_runs_and_queues_processing(self, _online):
        self.q()
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/questions/explanation-batches/').status_code, 403)
        self.client.force_authenticate(self.admin)
        overview = self.client.get('/api/questions/explanation-batches/').json()
        self.assertEqual(overview['needed'], {'total': 1, 'by_exam': {'cms': 1}})
        created = self.client.post('/api/questions/explanation-batches/', {'exam_type': 'cms'}, format='json')
        self.assertEqual(created.status_code, 201)
        run_id = created.json()['id']
        self.assertEqual(created.json()['counts'], {'queued': 1})
        with mock.patch('django_q.tasks.async_task', return_value='task-1') as queue:
            started = self.client.post(f'/api/questions/explanation-batches/{run_id}/process/', {'max_items': 50},
                                       format='json')
        self.assertEqual(started.status_code, 202)
        self.assertEqual(queue.call_args.args[:3], ('questions.tasks.run_explanation_batch_task', run_id, 50))
        with mock.patch('ai_engine.offline.ai_offline_mode', return_value=True):
            self.assertEqual(self.client.post(f'/api/questions/explanation-batches/{run_id}/process/', {},
                                              format='json').status_code, 409)

    def test_the_review_queue_lists_unreviewed_ai_explanations(self, _online):
        q = self.q()
        run = batch.create_run()
        batch.run_batch(run, ai=FakeAI(GOOD))
        self.client.force_authenticate(self.admin)
        queue = self.client.get('/api/questions/explanation-review/').json()
        self.assertEqual([row['question_id'] for row in queue['results']], [q.pk])
        reviewed = self.client.post(f'/api/questions/{q.pk}/review-explanation/', {}, format='json')
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(self.client.get('/api/questions/explanation-review/').json()['count'], 0)
        items = self.client.get(f'/api/questions/explanation-batches/{run.pk}/items/', {'status': 'done'}).json()
        self.assertEqual(items['count'], 1)
