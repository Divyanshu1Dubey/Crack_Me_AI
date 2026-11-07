"""The scholarship challenge's question pool (2026-11-07).

Live state: no question was flagged ``is_scholarship_eligible``, so the challenge on /subscription
showed "No scholarship questions available right now". The pool now comes from a reviewed pool file
(``manage.py apply_scholarship_pool``, dry run by default) or the admin questions editor
(``PATCH /api/questions/<id>/scholarship/``). Both refuse a question the challenge cannot show fairly
(text and four options only, 5/5 needed) and never touch a key. The flag stays admin-only: the public
``?is_scholarship_eligible=`` filter listed every challenge question to anyone.
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models_freemium import FreeShowcaseQuestion
from questions import scholarship_pool as pool
from questions.content_hashes import stem_hash
from questions.models import Question, QuestionImage, Subject

User = get_user_model()


def _tmpdir(test) -> Path:
    """A temp dir removed after ``test`` (Django runs TestCase classes before SimpleTestCase ones, so a
    module-level dir removed in tearDownModule is gone before this module's SimpleTestCase runs)."""
    path = tempfile.mkdtemp(prefix='scholarship-pool-tests-')
    test.addCleanup(shutil.rmtree, path, True)
    return Path(path)


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _question(subject, n, **fields):
    data = dict(question_text=f'Pool question {n}: which one is correct?', option_a=f'a{n}', option_b=f'b{n}',
                option_c=f'c{n}', option_d=f'd{n}', correct_answer='ABCD'[n % 4], year=2021, subject=subject,
                explanation=f'Explanation {n}.')
    data.update(fields)
    return Question.objects.create(**data)


def _rows(response):
    return response.data['results'] if isinstance(response.data, dict) and 'results' in response.data else response.data


class PoolFixtureFileTests(SimpleTestCase):
    """The pool file shipped in fixtures/ is well formed and big enough to vary the draws."""

    def test_the_shipped_pool_file(self):
        from accounts.views import SCHOLARSHIP_QUESTION_COUNT

        path = Path(settings.BASE_DIR) / 'fixtures' / 'scholarship_pool.json'
        data = pool.load_pool(path)
        rows = data['questions']
        self.assertGreaterEqual(len(rows), 6 * SCHOLARSHIP_QUESTION_COUNT)
        self.assertEqual(data['status'], 'proposed')
        self.assertIn('does not verify', data['caveat'])
        self.assertTrue(all(row['key_provenance'] in ('import', 'unknown') for row in rows))
        self.assertTrue(all(row.get('review_note') for row in rows))

    def test_bad_pool_files_are_refused(self):
        bad = _tmpdir(self) / 'bad.json'
        for payload in ({'format': 'other', 'questions': [{'id': 1, 'key': 'A', 'stem_hash': 'a' * 64}]},
                        {'format': pool.POOL_FORMAT, 'questions': []},
                        {'format': pool.POOL_FORMAT, 'questions': [{'id': 1, 'key': 'E', 'stem_hash': 'a' * 64}]},
                        {'format': pool.POOL_FORMAT, 'questions': [{'id': 1, 'key': 'A', 'stem_hash': 'short'}]},
                        {'format': pool.POOL_FORMAT, 'questions': [{'id': 1, 'key': 'A', 'stem_hash': 'a' * 64},
                                                                    {'id': 1, 'key': 'B', 'stem_hash': 'b' * 64}]}):
            bad.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaises(ValueError, msg=payload):
                pool.load_pool(bad)


class ScholarshipPoolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Scholarship Pool Subject', code='SCHPOOL')
        cls.subject = subject
        cls.clean = [_question(subject, n) for n in range(6)]
        cls.showcase = _question(subject, 10)
        FreeShowcaseQuestion.objects.create(question=cls.showcase, year=2021, position=0)
        cls.figure = _question(subject, 11)
        QuestionImage.objects.create(question=cls.figure, page_number=0, image_index_in_page=0,
                                     url='/media/recall_images/x.png')
        cls.token = _question(subject, 12)
        cls.token.question_text = 'Identify the finding. [[img:99]]'
        cls.token.save(update_fields=['question_text'])
        cls.no_option = _question(subject, 13, option_d='')
        cls.no_key = _question(subject, 14, correct_answer='')
        cls.disputed = _question(subject, 15, is_disputed=True)
        cls.inactive = _question(subject, 16, is_active=False)
        cls.admin = User.objects.create_superuser(username='pool-admin', email='pool-admin@example.com',
                                                  password='unused-pw-1')
        cls.student = User.objects.create_user(username='pool-student', email='pool-student@example.com',
                                               password='unused-pw-2')

    def setUp(self):
        cache.clear()

    def _patch(self, user, question, eligible):
        return _client(user).patch(f'/api/questions/{question.pk}/scholarship/', {'eligible': eligible}, format='json')

    # ── the refusal rules ────────────────────────────────────────────────
    def test_pool_refusal_names_why_a_question_cannot_join(self):
        self.assertIsNone(pool.pool_refusal(self.clean[0]))
        self.assertEqual(
            [pool.pool_refusal(q) for q in (self.showcase, self.figure, self.token, self.no_option,
                                             self.no_key, self.disputed, self.inactive)],
            ['showcase', 'figure', 'image_token', 'missing_option', 'no_key', 'disputed', 'inactive'])

    # ── admin endpoint ───────────────────────────────────────────────────
    def test_only_admins_change_the_pool(self):
        self.assertIn(self._patch(None, self.clean[0], True).status_code, (401, 403))
        self.assertEqual(self._patch(self.student, self.clean[0], True).status_code, 403)
        self.clean[0].refresh_from_db()
        self.assertFalse(self.clean[0].is_scholarship_eligible)

    def test_admin_adds_and_removes_a_question_and_the_key_is_untouched(self):
        question = self.clean[1]
        before = (question.correct_answer, question.explanation, stem_hash(question))
        res = self._patch(self.admin, question, True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['is_scholarship_eligible'], res.data['pool_size']), (True, 1))
        question.refresh_from_db()
        self.assertTrue(question.is_scholarship_eligible)
        self.assertEqual((question.correct_answer, question.explanation, stem_hash(question)), before)
        res = self._patch(self.admin, question, False)
        self.assertEqual((res.status_code, res.data['pool_size']), (200, 0))
        question.refresh_from_db()
        self.assertFalse(question.is_scholarship_eligible)

    def test_admin_cannot_add_a_question_the_challenge_cannot_show(self):
        for question, reason in ((self.showcase, 'showcase'), (self.figure, 'figure'), (self.no_key, 'no_key')):
            res = self._patch(self.admin, question, True)
            self.assertEqual(res.status_code, 400, reason)
            self.assertEqual((res.data['code'], res.data['reason']), ('scholarship_refused', reason))
            self.assertEqual(res.data['detail'], pool.REFUSALS[reason])
        self.assertEqual(self._patch(self.admin, self.clean[2], 'yes').status_code, 400)
        # Taking a question out always works (e.g. one flagged before it got a figure).
        Question.objects.filter(pk=self.figure.pk).update(is_scholarship_eligible=True)
        self.assertEqual(self._patch(self.admin, self.figure, False).status_code, 200)

    # ── the flag stays admin-only ────────────────────────────────────────
    def test_the_pool_is_never_listed_or_named_to_students(self):
        pool.set_eligible([q.pk for q in self.clean[:5]], True)
        everyone = _client().get('/api/questions/', {'subject': self.subject.pk, 'page_size': 50})
        filtered = _client().get('/api/questions/', {'subject': self.subject.pk, 'page_size': 50,
                                                     'is_scholarship_eligible': 'true'})
        self.assertEqual(filtered.status_code, 200)
        # The filter is ignored for anyone but an admin: the same rows, the challenge ones not singled out.
        self.assertEqual({r['id'] for r in _rows(filtered)}, {r['id'] for r in _rows(everyone)})
        self.assertGreater(len(_rows(filtered)), 5)
        for res in (everyone, _client(self.student).get('/api/questions/', {'subject': self.subject.pk})):
            self.assertTrue(all('is_scholarship_eligible' not in row for row in _rows(res)))
        detail = _client().get(f'/api/questions/{self.clean[0].pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('is_scholarship_eligible', detail.data)
        admin = _client(self.admin).get('/api/questions/', {'subject': self.subject.pk, 'page_size': 50,
                                                            'is_scholarship_eligible': 'true'})
        self.assertEqual({r['id'] for r in _rows(admin)}, {q.pk for q in self.clean[:5]})
        self.assertTrue(all(row['is_scholarship_eligible'] for row in _rows(admin)))

    def test_a_pool_of_five_opens_the_challenge(self):
        self.assertEqual(_client(self.student).post('/api/auth/scholarship/start/').data['questions'], [])
        pool.set_eligible([q.pk for q in self.clean[:5]], True)
        res = _client(self.student).post('/api/auth/scholarship/start/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual({q['id'] for q in res.data['questions']}, {q.pk for q in self.clean[:5]})
        self.assertTrue(all('correct_answer' not in q for q in res.data['questions']))

    # ── the command ──────────────────────────────────────────────────────
    def _pool_file(self, rows):
        path = _tmpdir(self) / 'pool.json'
        path.write_text(json.dumps({'format': pool.POOL_FORMAT, 'status': 'proposed', 'questions': rows}),
                        encoding='utf-8')
        return str(path)

    @staticmethod
    def _entry(question, **over):
        row = {'id': question.pk, 'key': question.correct_answer, 'stem_hash': stem_hash(question)}
        row.update(over)
        return row

    def _run(self, *args):
        out = io.StringIO()
        call_command('apply_scholarship_pool', *args, stdout=out)
        return out.getvalue()

    def test_the_command_is_a_dry_run_by_default_and_skips_what_changed(self):
        rows = [self._entry(q) for q in self.clean[:5]]
        rows.append(self._entry(self.clean[5], key='ABCD'[(5 + 1) % 4]))            # key changed since review
        rows.append(self._entry(self.showcase))                                     # free content
        rows.append(self._entry(self.figure, stem_hash='0' * 64))                   # text changed since review
        rows.append({'id': 999999, 'key': 'A', 'stem_hash': 'f' * 64})               # gone
        path = self._pool_file(rows)

        text = self._run(path)
        self.assertIn('to add: 5 | already in: 0 | skipped: 4', text)
        self.assertIn(f'skipped (key_changed, 1): {self.clean[5].pk}', text)
        self.assertIn(f'skipped (showcase, 1): {self.showcase.pk}', text)
        self.assertIn(f'skipped (content_changed, 1): {self.figure.pk}', text)
        self.assertIn('skipped (missing, 1): 999999', text)
        self.assertIn('would be 5 active questions: the challenge can start', text)
        self.assertIn('nothing written', text)
        self.assertEqual(pool.eligible_count(), 0)

        text = self._run(path, '--apply')
        self.assertIn('added: 5', text)
        self.assertEqual(set(Question.objects.filter(is_scholarship_eligible=True).values_list('id', flat=True)),
                         {q.pk for q in self.clean[:5]})
        self.assertIn('already in: 5', self._run(path, '--apply'))      # idempotent
        for question in self.clean[:5]:
            question.refresh_from_db()
        self.assertEqual([q.correct_answer for q in self.clean[:5]], ['ABCD'[n % 4] for n in range(5)])

        self.assertIn('nothing written', self._run(path, '--revoke'))
        self.assertEqual(pool.eligible_count(), 5)
        text = self._run(path, '--revoke', '--apply')
        self.assertIn('removed: 5', text)
        self.assertIn('stays closed', text)
        self.assertEqual(pool.eligible_count(), 0)

    def test_the_command_refuses_a_bad_file(self):
        with self.assertRaises(CommandError):
            self._run(str(_tmpdir(self) / 'missing.json'))
