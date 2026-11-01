"""Wave 4 Z4 (follow-ups of the security pass): public handles, scholarship text.

HANDLE    usernames are public (discussion threads, the leaderboard). Google
          sign-ups (no username in user_metadata) and the dev-only local
          register were named after the email's local part -- for a Gmail user
          the address itself. New accounts now get a generated learner_<hex>
          handle instead, and a learner can change their handle in Settings
          (PATCH /api/auth/profile/, accounts.handles.handle_error). A name
          chosen at sign-up is kept only when it follows the Settings rules
          (format, not a team name -- trusted admins excepted); otherwise the
          account gets a generated handle.
BACKFILL  migration accounts.0027 (and manage.py rename_email_derived_usernames,
          dry run unless --apply) gives existing student accounts whose
          username shows their address a generated handle; admin/staff
          accounts are skipped. Username changes are limited to 10 per hour:
          the "taken" answer tells whether some account uses a name.
SCHOLAR   the scholarship start rows cut an answer key / explanation glued into
          the stem or an option (questions.answer_leak.redact_public_text);
          a failed verify says nothing about how many answers were right, and
          blanks are refused (one guess + four blanks made the score that
          question's right/wrong signal).

No network: the Supabase call is faked (tests_wave1_auth._SupabaseAuthTestCase).
"""
import importlib
import io
import re
from types import SimpleNamespace
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory

from accounts.handles import (
    HANDLE_MAX_LENGTH,
    HANDLE_TAKEN_MESSAGE,
    exposes_email,
    generate_handle,
    handle_error,
    username_for_new_account,
)
from accounts.local_auth import LocalRegisterView
from accounts.tests_wave1_auth import _SupabaseAuthTestCase, _identity
from questions.models import Question, Subject

User = get_user_model()
PROFILE = '/api/auth/profile/'
PASSWORD = 'x-Long-passw0rd'
GENERATED = re.compile(r'^learner_[0-9a-f]{8}$')
# Sign-up names the Settings form refuses (the verifier's probe values):
# team names, HTML/spaces, too long, too short.
REFUSED_SIGN_UP_NAMES = (
    'admin', 'CrackLabs_Official', 'Support', 'Dr Rahul <b>x</b>', 'x' * 120, 'a',
    'Ad.Min_1', 'dr-rahul', '___',
)


def _public_name(username, email):
    from analytics.views import _public_name as leaderboard_name

    return leaderboard_name(SimpleNamespace(username=username, email=email))


class ExposesEmailTests(SimpleTestCase):
    def test_the_local_part_in_any_case_with_a_suffix_or_cut_shows_the_address(self):
        long_local = 'a' * 150
        for username, email in [
            ('rahul.k', 'Rahul.K@gmail.com'),
            ('RAHUL.K_2', 'rahul.k@gmail.com'),
            ('a' * 140, f'{long_local}@example.com'),
            ('a' * 130 + '_3', f'{long_local}@example.com'),
            ('someone@else.org', 'rahul@gmail.com'),
        ]:
            with self.subTest(username=username):
                self.assertTrue(exposes_email(username, email))

    def test_other_handles_do_not(self):
        for username, email in [
            ('cardio_queen', 'rahul@gmail.com'),
            ('rahul_k', 'rahul@gmail.com'),
            ('rahul', ''),
            ('', 'rahul@gmail.com'),
            (None, 'rahul@gmail.com'),
            (12345, 'rahul@gmail.com'),
        ]:
            with self.subTest(username=username):
                self.assertFalse(exposes_email(username, email))

    def test_same_rule_as_the_leaderboard(self):
        long_local = 'b' * 150
        for username, email in [
            ('rahul.k', 'rahul.k@gmail.com'), ('Rahul.K_12', 'rahul.k@gmail.com'),
            ('rahul.k_x', 'rahul.k@gmail.com'), ('cardio', 'rahul@gmail.com'), ('a@b', 'x@y.com'),
            ('b' * 140, f'{long_local}@x.com'), ('b' * 130 + '_4', f'{long_local}@x.com'),
            ('learner', 'learner_1@x.com'), ('rahul', ''), ('learner_1a2b3c4d', 'meera@x.com'),
        ]:
            with self.subTest(username=username, email=email):
                self.assertEqual(exposes_email(username, email), _public_name(username, email) is None)


class NewAccountUsernameTests(TestCase):
    def test_a_generated_handle_is_learner_hex_and_unused(self):
        self.assertRegex(generate_handle(User), GENERATED)
        User.objects.create_user(username='Learner_DEADBEEF', email='x@example.com')
        with mock.patch('accounts.handles.secrets.token_hex', side_effect=['deadbeef', 'cafef00d']):
            self.assertEqual(generate_handle(User), 'learner_cafef00d')

    def test_no_name_or_a_name_that_shows_the_address_gets_a_generated_handle(self):
        email = 'rahul.k@gmail.com'
        for requested in (None, '', '   ', 12345, {'x': 1}, 'rahul.k', 'Rahul.K_2', 'rahul.k@gmail.com', 'me@other.org'):
            with self.subTest(requested=requested):
                self.assertRegex(username_for_new_account(User, requested, email), GENERATED)

    def test_a_chosen_name_is_kept_and_made_unique_in_any_case(self):
        email = 'meera@gmail.com'
        self.assertEqual(username_for_new_account(User, ' cardio_queen ', email), 'cardio_queen')
        User.objects.create_user(username='cardio_queen', email='other@example.com')
        self.assertEqual(username_for_new_account(User, 'Cardio_Queen', email), 'Cardio_Queen_2')

    def test_a_suffix_that_would_show_the_address_gives_a_generated_handle(self):
        User.objects.create_user(username='abc', email='one@example.com')
        User.objects.create_user(username='abc_2', email='two@example.com')
        self.assertRegex(username_for_new_account(User, 'abc', 'abc_3@gmail.com'), GENERATED)
        # A long name (its suffixed variants used to be the address's 130-char
        # cut, an endless-loop risk) is over 30 characters: a generated handle.
        local = 'a' * 135
        User.objects.create_user(username=local + 'x', email='three@example.com')
        self.assertRegex(username_for_new_account(User, local + 'x', f'{local}@gmail.com'), GENERATED)

    def test_the_suffix_search_is_bounded(self):
        for name in ('doc', 'doc_2', 'doc_3'):
            User.objects.create_user(username=name, email=f'{name}@example.com')
        with mock.patch('accounts.handles._MAX_SUFFIX', 3):
            self.assertRegex(username_for_new_account(User, 'doc', 'meera@gmail.com'), GENERATED)

    def test_a_name_the_settings_form_refuses_gets_a_generated_handle(self):
        # It used to be kept as given: anyone could sign up as "admin" or
        # "CrackLabs_Official" and post as the team.
        for requested in REFUSED_SIGN_UP_NAMES:
            with self.subTest(requested=requested):
                self.assertIsNotNone(handle_error(requested, user=SimpleNamespace(pk=None, email='meera@gmail.com'), User=User))
                self.assertRegex(username_for_new_account(User, requested, 'meera@gmail.com'), GENERATED)

    def test_a_trusted_admin_may_keep_a_team_name_but_not_a_malformed_one(self):
        self.assertEqual(
            username_for_new_account(User, 'CrackLabs_Support', 'ops@cracklabs.app', team_member=True),
            'CrackLabs_Support',
        )
        for requested in ('Dr Rahul <b>x</b>', 'x' * 120, 'a', 'ops'):
            with self.subTest(requested=requested):
                self.assertRegex(username_for_new_account(User, requested, 'ops@cracklabs.app', team_member=True), GENERATED)

    def test_suffixed_names_stay_within_30_characters(self):
        name = 'a' * 29 + 'b'
        User.objects.create_user(username=name, email='one@example.com')
        User.objects.create_user(username='a' * 28 + '_2', email='two@example.com')
        chosen = username_for_new_account(User, name, 'meera@gmail.com')
        self.assertEqual(chosen, 'a' * 28 + '_3')
        self.assertLessEqual(len(chosen), HANDLE_MAX_LENGTH)
        self.assertIsNone(handle_error(chosen, user=SimpleNamespace(pk=None, email='meera@gmail.com'), User=User))

    def test_a_suffixed_variant_that_is_a_team_name_gives_a_generated_handle(self):
        # 29 characters, not reserved; cut to 28 for '_2' it reads "administrator".
        name = 'administrator' + '_' * 15 + 'x'
        User.objects.create_user(username=name, email='one@example.com')
        self.assertRegex(username_for_new_account(User, name, 'meera@gmail.com'), GENERATED)


class SupabaseSignUpHandleTests(_SupabaseAuthTestCase):
    def test_a_google_sign_up_gets_a_generated_handle_not_its_address(self):
        identity = _identity('rahul.sharma@gmail.com', user_metadata={'full_name': 'Rahul Sharma'})
        r = self.bearer('tok-google', identity).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertRegex(r.data['username'], GENERATED)
        self.assertNotIn('rahul', r.data['username'].lower())
        self.assertEqual(r.data['first_name'], 'Rahul')
        user = User.objects.get(email='rahul.sharma@gmail.com')
        # Learners with a generated handle are listed by it on the leaderboard.
        self.assertEqual(_public_name(user.username, user.email), user.username)

    def test_the_handle_chosen_at_sign_up_is_kept(self):
        identity = _identity('meera@gmail.com', user_metadata={'username': 'cardio_queen'})
        r = self.bearer('tok-chosen', identity).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['username'], 'cardio_queen')

    def test_a_sign_up_name_that_shows_the_address_is_replaced(self):
        for token, email, chosen in (
            ('tok-local', 'priya.n@gmail.com', 'priya.n'),
            ('tok-address', 'arjun.m@gmail.com', 'arjun.m@gmail.com'),
        ):
            with self.subTest(chosen=chosen):
                r = self.bearer(token, _identity(email, user_metadata={'username': chosen})).get(PROFILE)
                self.assertEqual(r.status_code, 200, r.data)
                self.assertRegex(r.data['username'], GENERATED)

    def test_a_non_text_username_in_metadata_does_not_break_the_first_sign_in(self):
        # It used to raise AttributeError (500) on .strip().
        r = self.bearer('tok-number', _identity('num@gmail.com', user_metadata={'username': 12345})).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertRegex(r.data['username'], GENERATED)

    def test_a_sign_up_name_the_settings_form_refuses_is_replaced(self):
        # user_metadata.username is whatever the sign-up form (or a direct
        # Supabase sign-up call) sent: team names, HTML, 120 characters, 'a'.
        for i, chosen in enumerate(REFUSED_SIGN_UP_NAMES):
            with self.subTest(chosen=chosen):
                identity = _identity(f'learner{i}@gmail.com', user_metadata={'username': chosen})
                r = self.bearer(f'tok-refused-{i}', identity).get(PROFILE)
                self.assertEqual(r.status_code, 200, r.data)
                self.assertRegex(r.data['username'], GENERATED)
        self.assertFalse(User.objects.filter(username__iexact='admin').exists())

    def test_a_trusted_admin_sign_up_may_keep_a_team_name(self):
        # app_metadata is only writable with the service-role key.
        identity = _identity('ops@cracklabs.app', user_metadata={'username': 'CrackLabs_Support'}, app_metadata={'role': 'admin'})
        r = self.bearer('tok-admin', identity).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['username'], r.data['role']), ('CrackLabs_Support', 'admin'))
        # The same name claimed only in user_metadata (anyone can set it) is not a pass.
        identity = _identity('fake@gmail.com', user_metadata={'username': 'CrackLabs_Help', 'role': 'admin'})
        r = self.bearer('tok-fake-admin', identity).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertRegex(r.data['username'], GENERATED)
        self.assertEqual(r.data['role'], 'student')


@override_settings(LOCAL_DEV_AUTH=True)
class LocalRegisterHandleTests(TestCase):
    def setUp(self):
        cache.clear()  # throttle history

    def register(self, **data):
        request = APIRequestFactory().post('/api/auth/local/register/', {'password': 'Local-Dev-Passw0rd!', **data}, format='json')
        response = LocalRegisterView.as_view()(request)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['user']['username']

    def test_no_username_gets_a_generated_handle(self):
        self.assertRegex(self.register(email='rahul.k@local.test'), GENERATED)

    def test_the_email_local_part_is_not_used(self):
        self.assertRegex(self.register(email='priya@local.test', username='Priya'), GENERATED)

    def test_a_chosen_username_is_kept(self):
        self.assertEqual(self.register(email='meera@local.test', username='cardio_queen'), 'cardio_queen')

    def test_a_username_the_settings_form_refuses_is_replaced(self):
        for i, chosen in enumerate(REFUSED_SIGN_UP_NAMES):
            with self.subTest(chosen=chosen):
                self.assertRegex(self.register(email=f'local{i}@local.test', username=chosen), GENERATED)


class ProfileUsernameTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='learner_0a1b2c3d', email='rahul.k@gmail.com', password=PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def patch(self, client=None, **data):
        return (client or self.client).patch(PROFILE, data, format='json')

    def test_a_learner_can_choose_a_handle(self):
        r = self.patch(username='cardio_queen')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['username'], 'cardio_queen')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'cardio_queen')
        self.assertEqual(_public_name(self.user.username, self.user.email), 'cardio_queen')

    def test_invalid_handles_are_refused_with_the_reason(self):
        for value, reason in [
            ('ab', '3 to 30 characters'),
            ('x' * 31, '3 to 30 characters'),
            ('dr rahul', 'letters, numbers'),
            ('dr-rahul', 'letters, numbers'),
            ('rahul@clinic.org', 'email address'),
            ('___', 'at least one letter or number'),
            ('rahul.k', 'part of your email'),
            ('RAHUL.K_2', 'part of your email'),
            ('admin', 'reserved'),
            ('Ad.Min_1', 'reserved'),
            ('CrackLabs_Team', 'reserved'),
        ]:
            with self.subTest(value=value):
                cache.clear()  # 11 attempts: over the 10/hour username-change limit
                r = self.patch(username=value)
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(reason, str(r.data['username']))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'learner_0a1b2c3d')

    def test_a_handle_used_by_another_account_is_refused_in_any_case(self):
        User.objects.create_user(username='Cardio_Queen', email='meera@gmail.com', password=PASSWORD)
        r = self.patch(username='cardio_queen')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(HANDLE_TAKEN_MESSAGE, str(r.data['username']))

    def test_a_handle_taken_between_the_check_and_the_save_is_a_400(self):
        User.objects.create_user(username='twin_name', email='twin@gmail.com', password=PASSWORD)
        with mock.patch('accounts.handles.handle_error', return_value=None):
            r = self.patch(username='twin_name', college='AIIMS')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(HANDLE_TAKEN_MESSAGE, str(r.data['username']))
        self.user.refresh_from_db()
        self.assertEqual((self.user.username, self.user.college), ('learner_0a1b2c3d', ''))

    def test_staff_may_use_a_reserved_name(self):
        staff = User.objects.create_user(username='ops_person', email='ops@cracklabs.app', password=PASSWORD, is_staff=True)
        client = APIClient()
        client.force_authenticate(staff)
        r = self.patch(client, username='CrackLabs_Support')
        self.assertEqual(r.status_code, 200, r.data)

    def test_an_unchanged_older_username_never_blocks_a_profile_save(self):
        for legacy in ('rahul.k', 'Dr Rahul'):
            with self.subTest(legacy=legacy):
                # The email's local part / a space: both predate the handle rules.
                self.user.username = legacy
                self.user.save(update_fields=['username'])
                r = self.patch(username=legacy, college='AIIMS Delhi')
                self.assertEqual(r.status_code, 200, r.data)
                r = self.patch(phone='9999999999')
                self.assertEqual(r.status_code, 200, r.data)
                self.user.refresh_from_db()
                self.assertEqual((self.user.username, self.user.college), (legacy, 'AIIMS Delhi'))

    def test_the_email_stays_read_only(self):
        r = self.patch(email='other@gmail.com', username='cardio_queen')
        self.assertEqual(r.status_code, 200, r.data)
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.username), ('rahul.k@gmail.com', 'cardio_queen'))


class UsernameChangeThrottleTests(TestCase):
    """10 username changes (or attempts) per account per hour.

    "This username is taken" tells the caller that some account uses a name;
    unthrottled (600 requests/min), that probed for hidden email-derived
    names. Other profile saves are not counted.
    """
    LIMIT = 10

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='learner_0a1b2c3d', email='prober@gmail.com', password=PASSWORD)
        User.objects.create_user(username='rahul.sharma', email='rahul.sharma@gmail.com', password=PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def patch(self, client=None, **data):
        return (client or self.client).patch(PROFILE, data, format='json')

    def test_the_eleventh_username_attempt_in_an_hour_is_refused(self):
        statuses = []
        for i in range(self.LIMIT):
            # Probing taken names, free names and malformed ones all count.
            value = ('Rahul.Sharma', f'free_name_{i}', 'no spaces allowed')[i % 3]
            statuses.append(self.patch(username=value).status_code)
        self.assertNotIn(429, statuses)
        self.assertIn(400, statuses)
        self.assertIn(200, statuses)
        before = User.objects.get(pk=self.user.pk).username
        r = self.patch(username='Rahul.Sharma')
        self.assertEqual(r.status_code, 429, r.data)
        self.assertIn('Too many username changes', str(r.data['detail']))
        self.assertNotIn('taken', str(r.data).lower())
        self.assertTrue(r.has_header('Retry-After'))
        r = self.patch(username='another_free_name')
        self.assertEqual(r.status_code, 429, r.data)
        self.assertEqual(User.objects.get(pk=self.user.pk).username, before)

    def test_saves_that_keep_the_username_and_reads_are_not_counted(self):
        for i in range(self.LIMIT + 5):
            current = User.objects.get(pk=self.user.pk).username
            self.assertEqual(self.patch(college=f'College {i}').status_code, 200)
            self.assertEqual(self.patch(username=f' {current} ', phone=f'98765432{i:02d}').status_code, 200)
            self.assertEqual(self.client.get(PROFILE).status_code, 200)
        r = self.patch(username='cardio_queen')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['username'], 'cardio_queen')

    def test_the_limit_is_per_account(self):
        for i in range(self.LIMIT + 1):
            self.patch(username=f'probe_{i}')
        self.assertEqual(self.patch(username='probe_x').status_code, 429)
        other = User.objects.create_user(username='learner_99887766', email='other@gmail.com', password=PASSWORD)
        client = APIClient()
        client.force_authenticate(other)
        r = self.patch(client, username='cardio_queen')
        self.assertEqual(r.status_code, 200, r.data)
        # The throttled account can still save the rest of its profile.
        self.assertEqual(self.patch(college='AIIMS').status_code, 200)


class ScholarshipStartRedactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Medicine', code='med-z4')
        common = {'year': 2024, 'subject': subject, 'is_scholarship_eligible': True}
        cls.option_leak = Question.objects.create(
            question_text='Which statements are correct?', option_a='I and II only', option_b='II and III only',
            option_c='I, II and IV only', option_d='I and IV only Correct Answer: C. I, II and IV only',
            correct_answer='C', **common,
        )
        cls.stem_leak = Question.objects.create(
            question_text='First-line drug for type 2 diabetes?\n\nExplanation: Metformin, because it lowers hepatic glucose output.',
            option_a='Metformin', option_b='Insulin', option_c='Glipizide', option_d='Acarbose',
            correct_answer='A', **common,
        )
        for i in range(3):
            Question.objects.create(
                question_text=f'Clean question {i}?', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='B', **common,
            )

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='scholar_z4', email='scholar@local.test', password=PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_answer_keys_and_explanations_in_the_text_are_cut(self):
        r = self.client.post('/api/auth/scholarship/start/')
        self.assertEqual(r.status_code, 200, r.data)
        rows = {row['id']: row for row in r.data['questions']}
        self.assertEqual(len(rows), 5)  # exactly five eligible: both leaking rows are issued
        self.assertEqual(rows[self.option_leak.id]['option_d'], 'I and IV only')
        self.assertEqual(rows[self.stem_leak.id]['question_text'], 'First-line drug for type 2 diabetes?')
        for row in rows.values():
            text = ' '.join(str(value) for value in row.values())
            self.assertNotIn('Correct Answer', text)
            self.assertNotIn('Explanation', text)
            self.assertNotIn('hepatic', text)
        # Scoring still uses the stored question.
        answers = {str(qid): Question.objects.get(pk=qid).correct_answer for qid in rows}
        v = self.client.post('/api/auth/verify-scholarship/', {'answers': answers, 'challenge_token': r.data['challenge_token']}, format='json')
        self.assertEqual(v.status_code, 200, v.data)
        self.assertEqual(v.data['status'], 'passed')


class ScholarshipVerifyDisclosureTests(TestCase):
    """A failed scholarship attempt is no right/wrong signal for any question.

    The verifier's probe: one guess plus four blanks answered 'You scored 1/5'
    when the guess was right and '0/5' when it was wrong; '0/5' also marked
    all five chosen letters wrong.
    """
    START = '/api/auth/scholarship/start/'
    VERIFY = '/api/auth/verify-scholarship/'

    @classmethod
    def setUpTestData(cls):
        subject = Subject.objects.create(name='Medicine Z4V', code='med-z4v')
        for i in range(5):
            Question.objects.create(
                question_text=f'Challenge question {i}?', option_a='A1', option_b='B1', option_c='C1', option_d='D1',
                correct_answer='ABCD'[i % 4], year=2024, subject=subject, is_scholarship_eligible=True,
            )

    def setUp(self):
        cache.clear()

    def start(self, username):
        user = User.objects.create_user(username=username, email=f'{username}@local.test', password=PASSWORD)
        client = APIClient()
        client.force_authenticate(user)
        r = client.post(self.START)
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['questions']]
        truth = {qid: Question.objects.get(pk=qid).correct_answer for qid in ids}
        return user, client, ids, truth, r.data['challenge_token']

    def verify(self, client, answers, token):
        return client.post(self.VERIFY, {'answers': {str(k): v for k, v in answers.items()}, 'challenge_token': token}, format='json')

    @staticmethod
    def wrong(letter):
        return 'B' if letter == 'A' else 'A'

    def test_one_guess_and_four_blanks_is_refused_without_using_an_attempt(self):
        for guess_is_right in (True, False):
            with self.subTest(guess_is_right=guess_is_right):
                user, client, ids, truth, token = self.start(f'probe_{int(guess_is_right)}')
                first = ids[0]
                answers = {qid: '' for qid in ids}
                answers[first] = truth[first] if guess_is_right else self.wrong(truth[first])
                r = self.verify(client, answers, token)
                self.assertEqual(r.status_code, 400, r.data)
                self.assertEqual(r.data, {'error': 'Answer all 5 questions before submitting.'})
                user.refresh_from_db()
                self.assertEqual((user.scholarship_test_attempts, user.scholarship_test_passed), (0, False))
                # Whitespace or a missing value is a blank too.
                answers[ids[1]] = '  '
                answers[ids[2]] = None
                self.assertEqual(self.verify(client, answers, token).status_code, 400)

    def test_a_failed_attempt_says_nothing_about_how_many_were_right(self):
        responses = []
        for name, right in (('four_right', 4), ('one_right', 1), ('none_right', 0)):
            _user, client, ids, truth, token = self.start(name)
            answers = {qid: (truth[qid] if n < right else self.wrong(truth[qid])) for n, qid in enumerate(ids)}
            r = self.verify(client, answers, token)
            self.assertEqual(r.status_code, 200, r.data)
            responses.append(r.data)
        # Identical whatever the count: no score, no "x/5" in the message.
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[0], responses[2])
        self.assertEqual(responses[0]['status'], 'failed')
        self.assertIsNone(responses[0]['score'])
        self.assertNotRegex(responses[0]['message'], r'[0-4]\s*/\s*5')
        self.assertIn('1 attempt remaining', responses[0]['message'])

    def test_the_last_failed_attempt_says_nothing_either_and_a_pass_reports_five(self):
        user, client, ids, truth, token = self.start('second_try')
        self.verify(client, {qid: self.wrong(truth[qid]) for qid in ids}, token)
        r = client.post(self.START)
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['questions']]
        answers = {qid: Question.objects.get(pk=qid).correct_answer for qid in ids}
        answers[ids[0]] = self.wrong(answers[ids[0]])
        v = self.verify(client, answers, r.data['challenge_token'])
        self.assertEqual((v.data['status'], v.data['score']), ('failed', None))
        self.assertNotRegex(v.data['message'], r'[0-4]\s*/\s*5')
        self.assertIn('No attempts remaining', v.data['message'])

        _user, client, ids, truth, token = self.start('perfect')
        v = self.verify(client, truth, token)
        self.assertEqual((v.data['status'], v.data['score']), ('passed', 5))


class RenameEmailDerivedUsernamesTests(_SupabaseAuthTestCase):
    def setUp(self):
        super().setUp()
        make = User.objects.create_user
        self.rahul = make(username='rahul.sharma', email='rahul.sharma@gmail.com', password=None)
        self.priya = make(username='Priya_2', email='priya@gmail.com', password=None)
        self.address = make(username='someone@mail.com', email='someone@mail.com', password=None)
        self.chosen = make(username='cardio_queen', email='meera@gmail.com', password=None)
        self.admin = make(username='boss', email='boss@cracklabs.app', password=PASSWORD, role='admin', is_staff=True)
        self.staff = make(username='ops', email='ops@cracklabs.app', password=PASSWORD, is_staff=True)
        self.students = (self.rahul, self.priya, self.address)
        self.before = dict(User.objects.values_list('pk', 'username'))

    def run_command(self, *args):
        out = io.StringIO()
        call_command('rename_email_derived_usernames', *args, stdout=out)
        text = out.getvalue()
        # Ids only: never a username or an address.
        for private in ('rahul', 'priya', 'someone', 'gmail', 'boss', '@'):
            self.assertNotIn(private, text.lower())
        return text

    def usernames(self):
        return dict(User.objects.values_list('pk', 'username'))

    def test_dry_run_reports_ids_and_changes_nothing(self):
        out = self.run_command()
        self.assertIn('3 account(s)', out)
        self.assertIn('Skipped 2 admin/staff account(s)', out)
        self.assertIn('Dry run: nothing changed', out)
        self.assertEqual(self.usernames(), self.before)

    def test_apply_renames_only_students_whose_username_shows_their_address(self):
        out = self.run_command('--apply')
        self.assertIn('Renamed 3 account(s)', out)
        after = self.usernames()
        renamed = [after[user.pk] for user in self.students]
        for name in renamed:
            self.assertRegex(name, GENERATED)
        self.assertEqual(len(set(renamed)), 3)
        for user in (self.chosen, self.admin, self.staff):
            self.assertEqual(after[user.pk], self.before[user.pk])
        # A second run has nothing left to rename.
        out = self.run_command('--apply')
        self.assertIn('0 account(s)', out)
        self.assertEqual(self.usernames(), after)

    def test_a_renamed_learner_still_signs_in_and_keeps_the_new_handle(self):
        self.run_command('--apply')
        handle = User.objects.get(pk=self.rahul.pk).username
        identity = _identity('rahul.sharma@gmail.com', user_metadata={'username': 'rahul.sharma'})
        r = self.bearer('tok-rahul', identity).get(PROFILE)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['id'], r.data['username']), (self.rahul.pk, handle))

    def test_a_username_changed_meanwhile_is_left_alone(self):
        from accounts.management.commands import rename_email_derived_usernames as command

        real, calls = command.generate_handle, []

        def learner_picks_a_handle_first(User_):
            # Rahul (the first account renamed) picks a handle in Settings
            # between the scan and the rename.
            if not calls:
                User.objects.filter(pk=self.rahul.pk).update(username='picked_in_settings')
            calls.append(1)
            return real(User_)

        with mock.patch.object(command, 'generate_handle', side_effect=learner_picks_a_handle_first):
            out = self.run_command('--apply')
        self.assertIn('Left 1 account(s)', out)
        self.assertEqual(User.objects.get(pk=self.rahul.pk).username, 'picked_in_settings')
        self.assertRegex(User.objects.get(pk=self.priya.pk).username, GENERATED)


class EmailDerivedUsernameMigrationTests(TestCase):
    """Migration 0027 runs the backfill in the release that makes usernames writable.

    Otherwise PATCH /api/auth/profile/ {username: 'Rahul.Sharma'} -> "taken"
    told any learner that someone with the address rahul.sharma@... uses
    CrackLabs, although the leaderboard hides that name.
    """
    MIGRATION = 'accounts.migrations.0027_rename_email_derived_usernames'

    def setUp(self):
        cache.clear()
        make = User.objects.create_user
        self.rahul = make(username='rahul.sharma', email='rahul.sharma@gmail.com', password=None)
        self.priya = make(username='PRIYA_2', email='priya@gmail.com', password=None)
        self.address = make(username='someone@mail.com', email='someone@mail.com', password=None)
        self.chosen = make(username='cardio_queen', email='meera@gmail.com', password=None)
        self.admin = make(username='boss', email='boss@cracklabs.app', password=PASSWORD, role='admin', is_staff=True)
        self.root = make(username='root.user', email='root.user@cracklabs.app', password=PASSWORD, is_superuser=True)
        self.before = dict(User.objects.values_list('pk', 'username'))

    def migrate_forward(self):
        importlib.import_module(self.MIGRATION).rename_email_derived_usernames(django_apps, None)
        return dict(User.objects.values_list('pk', 'username'))

    def test_the_migration_is_applied_after_the_legacy_plans_one(self):
        module = importlib.import_module(self.MIGRATION)
        self.assertEqual(module.Migration.dependencies, [('accounts', '0026_restore_paid_legacy_plans')])
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(('accounts', '0027_rename_email_derived_usernames'), applied)

    def test_student_usernames_that_show_the_address_are_renamed(self):
        after = self.migrate_forward()
        for user in (self.rahul, self.priya, self.address):
            self.assertRegex(after[user.pk], GENERATED)
        # A chosen handle and the team's accounts are kept (admin sign-in by username).
        for user in (self.chosen, self.admin, self.root):
            self.assertEqual(after[user.pk], self.before[user.pk])
        # Nothing left for the command to rename; a second run changes nothing.
        self.assertEqual(self.migrate_forward(), after)

    def test_after_the_migration_the_taken_answer_reveals_no_hidden_name(self):
        prober = User.objects.create_user(username='learner_0a1b2c3d', email='prober@gmail.com', password=PASSWORD)
        client = APIClient()
        client.force_authenticate(prober)
        self.assertEqual(client.patch(PROFILE, {'username': 'Rahul.Sharma'}, format='json').status_code, 400)
        self.migrate_forward()
        r = client.patch(PROFILE, {'username': 'Rahul.Sharma'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # The renamed learner is listed by the new handle on the leaderboard
        # (signing in after a rename: RenameEmailDerivedUsernamesTests).
        self.rahul.refresh_from_db()
        self.assertEqual(_public_name(self.rahul.username, self.rahul.email), self.rahul.username)
