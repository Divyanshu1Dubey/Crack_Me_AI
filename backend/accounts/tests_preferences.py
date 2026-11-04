"""Per-user layout preferences: GET / PATCH /api/auth/preferences/ (accounts/preferences.py).

ALLOW-LISTS  ids are unique; every opening page is a sidebar link; the upgrade row is a widget.
VALIDATION   known keys only, ids from the allow-lists, no repeats, bounded lists and body
             (413 over MAX_BODY_BYTES), JSON only (415), the free plan's upgrade row cannot be
             hidden, and a refused body saves nothing (not even its valid parts).
MERGE        PATCH replaces the top-level keys it names and keeps the others; null or {} removes
             a key; empty lists are not stored; a stored value the allow-lists no longer accept is
             dropped on read.
ACCESS       anonymous -> 401; a student and an admin each read and write only their own row
             (no user parameter; a user id in the query is ignored, in the body refused); the
             profile endpoint cannot write the field; saves are rate limited, reads are not.
SIGN-IN      the same through the Supabase bearer path (faked, no network) and a Django-native
             session (AUTH_PROVIDER=django).
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.native_sessions import issue_session_tokens
from accounts.preferences import (
    DASHBOARD_ALWAYS_SHOWN_IDS,
    DASHBOARD_WIDGET_IDS,
    LANDING_PAGE_IDS,
    MAX_BODY_BYTES,
    SIDEBAR_ITEM_IDS,
    SIDEBAR_SECTION_IDS,
    PreferencesError,
    _PreferencesSaveThrottle,
    clean_stored,
    merge_preferences,
    validate_patch,
)
from accounts.tests_native_auth import DEVICE_A, DEVICE_B, NATIVE, bearer, make_user
from accounts.tests_wave1_auth import _SupabaseAuthTestCase, _identity

User = get_user_model()
URL = '/api/auth/preferences/'
PASSWORD = 'x-Long-passw0rd'

SIDEBAR = {
    'sections': ['account', 'study', 'ai-tools', 'resources'],
    'items': ['questions', 'dashboard', 'leaderboard'],
    'hidden': ['quests', 'jobs'],
}
DASHBOARD = {'order': ['mastery', 'welcome', 'upgrade'], 'hidden': ['toolkit', 'announcements']}
FULL = {'sidebar': SIDEBAR, 'dashboard': DASHBOARD, 'landing_page': 'questions'}


def _student(username='stu'):
    return User.objects.create_user(username=username, email=f'{username}@example.com', password=PASSWORD)


def _admin(username='ops'):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password=PASSWORD,
        role='admin', is_superuser=True, is_staff=True,
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _stored(user):
    return User.objects.get(pk=user.pk).ui_preferences


class AllowListTests(SimpleTestCase):
    def test_ids_are_unique(self):
        for ids in (SIDEBAR_SECTION_IDS, SIDEBAR_ITEM_IDS, DASHBOARD_WIDGET_IDS, LANDING_PAGE_IDS):
            with self.subTest(ids=ids):
                self.assertEqual(len(ids), len(set(ids)))

    def test_opening_pages_are_sidebar_links_and_the_upgrade_row_is_a_widget(self):
        self.assertTrue(set(LANDING_PAGE_IDS) <= set(SIDEBAR_ITEM_IDS))
        self.assertIn('dashboard', LANDING_PAGE_IDS)
        self.assertTrue(set(DASHBOARD_ALWAYS_SHOWN_IDS) <= set(DASHBOARD_WIDGET_IDS))
        # Admin tools are not customisable and an admin-only page is no opening page.
        self.assertNotIn('upload', LANDING_PAGE_IDS)
        self.assertFalse([i for i in SIDEBAR_ITEM_IDS if i.startswith('admin')])


class ValidatePatchTests(SimpleTestCase):
    def test_a_valid_body_comes_back_unchanged(self):
        self.assertEqual(validate_patch(FULL), FULL)
        self.assertEqual(validate_patch({}), {})
        # Order lists may name only some ids; every allowed id may be named once.
        every = {'sidebar': {'items': list(SIDEBAR_ITEM_IDS)}, 'dashboard': {'order': list(DASHBOARD_WIDGET_IDS)}}
        self.assertEqual(validate_patch(every), every)

    def test_null_empty_objects_and_empty_lists_mean_the_default(self):
        self.assertEqual(
            validate_patch({'sidebar': None, 'dashboard': {}, 'landing_page': None}),
            {'sidebar': None, 'dashboard': None, 'landing_page': None},
        )
        self.assertEqual(
            validate_patch({'sidebar': {'sections': [], 'hidden': ['quests']}, 'dashboard': {'hidden': []}}),
            {'sidebar': {'hidden': ['quests']}, 'dashboard': None},
        )

    def test_refusals(self):
        too_many_items = list(SIDEBAR_ITEM_IDS) + ['dashboard']
        cases = [
            ([], 'non_field_errors'),
            ('dashboard', 'non_field_errors'),
            ({'theme': 'dark'}, 'theme'),
            ({'user_id': 2}, 'user_id'),
            ({'sidebar': ['study']}, 'sidebar'),
            ({'sidebar': 'study'}, 'sidebar'),
            ({'sidebar': {'order': ['study']}}, 'sidebar.order'),
            ({'sidebar': {'items': 'questions'}}, 'sidebar.items'),
            ({'sidebar': {'items': [1]}}, 'sidebar.items'),
            ({'sidebar': {'items': [None]}}, 'sidebar.items'),
            ({'sidebar': {'items': ['admin']}}, 'sidebar.items'),
            ({'sidebar': {'items': ['/admin/review-queue']}}, 'sidebar.items'),
            ({'sidebar': {'items': ['Questions']}}, 'sidebar.items'),  # ids are case-sensitive
            ({'sidebar': {'sections': ['study', 'admin']}}, 'sidebar.sections'),
            ({'sidebar': {'sections': ['questions']}}, 'sidebar.sections'),  # a link is no section
            ({'sidebar': {'hidden': ['tests', 'tests']}}, 'sidebar.hidden'),
            ({'sidebar': {'items': too_many_items}}, 'sidebar.items'),
            ({'sidebar': {'sections': ['study'] * 50}}, 'sidebar.sections'),
            ({'dashboard': ['welcome']}, 'dashboard'),
            ({'dashboard': {'order': ['questions']}}, 'dashboard.order'),  # a link is no widget
            ({'dashboard': {'hidden': ['upgrade']}}, 'dashboard.hidden'),
            ({'dashboard': {'hidden': ['welcome', 'welcome']}}, 'dashboard.hidden'),
            ({'dashboard': {'visible': ['welcome']}}, 'dashboard.visible'),
            ({'landing_page': 'upload'}, 'landing_page'),
            ({'landing_page': '/admin'}, 'landing_page'),
            ({'landing_page': 'https://example.com/'}, 'landing_page'),
            ({'landing_page': ''}, 'landing_page'),
            ({'landing_page': 3}, 'landing_page'),
            ({'landing_page': ['tests']}, 'landing_page'),
        ]
        for body, field in cases:
            with self.subTest(body=body):
                with self.assertRaises(PreferencesError) as caught:
                    validate_patch(body)
                self.assertIn(field, caught.exception.errors)

    def test_every_problem_is_reported_and_messages_stay_short(self):
        with self.assertRaises(PreferencesError) as caught:
            validate_patch({'sidebar': {'items': ['x' * 10_000]}, 'landing_page': 'nowhere', 'extra': 1})
        errors = caught.exception.errors
        self.assertEqual(set(errors), {'sidebar.items', 'landing_page', 'extra'})
        self.assertLess(len(errors['sidebar.items']), 80)

    def test_a_body_full_of_unknown_keys_gets_a_bounded_answer(self):
        with self.assertRaises(PreferencesError) as caught:
            validate_patch({f'k{i}': i for i in range(500)})
        self.assertLessEqual(len(caught.exception.errors), 10)


class CleanStoredAndMergeTests(SimpleTestCase):
    def test_values_the_allow_lists_no_longer_accept_are_dropped(self):
        raw = {
            'sidebar': {'sections': ['study', 'gone', 'study'], 'items': 'questions', 'hidden': ['quests', 7],
                        'extra': ['x']},
            'dashboard': {'order': ['welcome', 'old-widget'], 'hidden': ['upgrade']},
            'landing_page': 'gone',
            'theme': 'dark',
        }
        self.assertEqual(clean_stored(raw), {
            'sidebar': {'sections': ['study'], 'hidden': ['quests']},
            'dashboard': {'order': ['welcome']},
        })
        for junk in (None, [], 'x', 3, {'sidebar': 'x', 'dashboard': None}):
            with self.subTest(junk=junk):
                self.assertEqual(clean_stored(junk), {})

    def test_merge_replaces_named_keys_only(self):
        stored = {'sidebar': SIDEBAR, 'landing_page': 'tests'}
        self.assertEqual(
            merge_preferences(stored, {'sidebar': {'hidden': ['jobs']}, 'dashboard': DASHBOARD}),
            {'sidebar': {'hidden': ['jobs']}, 'dashboard': DASHBOARD, 'landing_page': 'tests'},
        )
        self.assertEqual(merge_preferences(stored, {'landing_page': None, 'sidebar': None}), {})
        self.assertEqual(stored, {'sidebar': SIDEBAR, 'landing_page': 'tests'})  # not mutated


class PreferencesEndpointTests(TestCase):
    def setUp(self):
        cache.clear()  # DRF throttle history lives in the default cache
        self.student = _student()
        self.other = _student('other')
        self.admin = _admin()

    def test_anonymous_gets_401(self):
        anonymous = APIClient()
        for response in (anonymous.get(URL), anonymous.patch(URL, FULL, format='json')):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response['WWW-Authenticate'], 'Bearer realm="api"')
        self.assertEqual(_stored(self.student), {})

    def test_a_new_account_has_the_defaults(self):
        self.assertEqual(self.student.ui_preferences, {})
        response = _client(self.student).get(URL)
        self.assertEqual((response.status_code, response.data), (200, {'preferences': {}}))

    def test_patch_saves_and_get_reads_it_back(self):
        client = _client(self.student)
        response = client.patch(URL, FULL, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {'preferences': FULL})
        self.assertEqual(_stored(self.student), FULL)
        self.assertEqual(client.get(URL).data, {'preferences': FULL})

    def test_patch_merges_top_level_keys(self):
        client = _client(self.student)
        client.patch(URL, {'sidebar': SIDEBAR}, format='json')
        client.patch(URL, {'landing_page': 'tests'}, format='json')
        self.assertEqual(_stored(self.student), {'sidebar': SIDEBAR, 'landing_page': 'tests'})
        client.patch(URL, {'dashboard': DASHBOARD}, format='json')
        self.assertEqual(_stored(self.student), {'sidebar': SIDEBAR, 'dashboard': DASHBOARD, 'landing_page': 'tests'})
        # A named key is replaced as a whole (no deep merge).
        response = client.patch(URL, {'sidebar': {'hidden': ['leaderboard']}}, format='json')
        self.assertEqual(response.data['preferences']['sidebar'], {'hidden': ['leaderboard']})
        self.assertEqual(_stored(self.student)['dashboard'], DASHBOARD)

    def test_null_resets_a_key_and_all_nulls_reset_everything(self):
        client = _client(self.student)
        client.patch(URL, FULL, format='json')
        response = client.patch(URL, {'sidebar': None, 'dashboard': {}}, format='json')
        self.assertEqual(response.data, {'preferences': {'landing_page': 'questions'}})
        response = client.patch(URL, {'sidebar': None, 'dashboard': None, 'landing_page': None}, format='json')
        self.assertEqual((response.status_code, response.data), (200, {'preferences': {}}))
        self.assertEqual(_stored(self.student), {})

    def test_a_refused_patch_saves_nothing(self):
        client = _client(self.student)
        client.patch(URL, FULL, format='json')
        response = client.patch(
            URL, {'landing_page': 'tests', 'dashboard': {'hidden': ['upgrade']}}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'invalid_preferences')
        self.assertEqual(set(response.data['errors']), {'dashboard.hidden'})
        self.assertEqual(_stored(self.student), FULL)  # the valid landing_page was not applied either

    def test_a_body_over_the_limit_is_413(self):
        body = json.dumps({'landing_page': 'x' * (MAX_BODY_BYTES + 1)})
        response = _client(self.student).patch(URL, body, content_type='application/json')
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data['code'], 'preferences_too_large')
        self.assertEqual(_stored(self.student), {})

    def test_json_only(self):
        client = _client(self.student)
        form = client.patch(URL, 'landing_page=tests', content_type='application/x-www-form-urlencoded')
        self.assertEqual(form.status_code, 415)
        broken = client.patch(URL, '{"landing_page": ', content_type='application/json')
        self.assertEqual(broken.status_code, 400)
        self.assertEqual(_stored(self.student), {})

    def test_other_methods_are_not_allowed(self):
        client = _client(self.student)
        self.assertEqual(client.put(URL, FULL, format='json').status_code, 405)
        self.assertEqual(client.post(URL, FULL, format='json').status_code, 405)
        self.assertEqual(client.delete(URL).status_code, 405)
        self.assertEqual(_stored(self.student), {})

    def test_one_user_cannot_read_or_change_another_users_preferences(self):
        alice, bob = _client(self.student), _client(self.other)
        alice.patch(URL, FULL, format='json')
        self.assertEqual(bob.get(URL).data, {'preferences': {}})
        self.assertEqual(bob.get(URL, {'user': self.student.pk, 'user_id': self.student.pk}).data,
                         {'preferences': {}})
        refused = bob.patch(URL, {'user_id': self.student.pk, 'landing_page': 'tests'}, format='json')
        self.assertEqual(refused.status_code, 400)
        bob.patch(URL, {'landing_page': 'flashcards'}, format='json')
        self.assertEqual(_stored(self.other), {'landing_page': 'flashcards'})
        self.assertEqual(_stored(self.student), FULL)
        self.assertEqual(alice.get(URL).data, {'preferences': FULL})

    def test_an_admin_has_their_own_preferences_only(self):
        _client(self.student).patch(URL, FULL, format='json')
        ops = _client(self.admin)
        self.assertEqual(ops.get(URL).data, {'preferences': {}})  # never the student's
        response = ops.patch(URL, {'sidebar': {'hidden': ['upload'], 'items': ['upload', 'resources']}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(_stored(self.admin), {'sidebar': {'hidden': ['upload'], 'items': ['upload', 'resources']}})
        self.assertEqual(_stored(self.student), FULL)
        # The same rules apply to admins (the Admin group is not customisable).
        self.assertEqual(ops.patch(URL, {'sidebar': {'items': ['admin']}}, format='json').status_code, 400)

    def test_values_no_longer_allowed_are_dropped_on_read_and_on_save(self):
        User.objects.filter(pk=self.student.pk).update(ui_preferences={
            'sidebar': {'items': ['retired-link', 'tests']}, 'landing_page': 'retired-page', 'beta': True,
        })
        client = _client(self.student)
        self.assertEqual(client.get(URL).data, {'preferences': {'sidebar': {'items': ['tests']}}})
        client.patch(URL, {'landing_page': 'tests'}, format='json')
        self.assertEqual(_stored(self.student), {'sidebar': {'items': ['tests']}, 'landing_page': 'tests'})

    def test_the_profile_endpoint_cannot_write_preferences(self):
        client = _client(self.student)
        response = client.patch('/api/auth/profile/', {'ui_preferences': {'landing_page': 'tests', 'x': 1}},
                                format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn('ui_preferences', response.data)
        self.assertEqual(_stored(self.student), {})

    def test_saves_are_rate_limited_and_reads_are_not(self):
        client = _client(self.student)
        with mock.patch.object(_PreferencesSaveThrottle, 'rate', '2/min'):
            self.assertEqual(client.patch(URL, {'landing_page': 'tests'}, format='json').status_code, 200)
            self.assertEqual(client.patch(URL, {'landing_page': 'flashcards'}, format='json').status_code, 200)
            self.assertEqual(client.patch(URL, {'landing_page': 'analytics'}, format='json').status_code, 429)
            for _ in range(3):
                self.assertEqual(client.get(URL).status_code, 200)
            # Another account has its own budget.
            self.assertEqual(_client(self.other).patch(URL, {'landing_page': 'tests'}, format='json').status_code,
                             200)
        self.assertEqual(_stored(self.student), {'landing_page': 'flashcards'})


class PreferencesSupabaseBearerTests(_SupabaseAuthTestCase):
    def test_each_signed_in_user_reads_and_writes_their_own(self):
        User.objects.create_user(username='alice', email='alice@example.com', password=PASSWORD)
        User.objects.create_user(username='bob', email='bob@example.com', password=PASSWORD)
        alice = self.bearer('tok-alice', _identity('alice@example.com'))
        bob = self.bearer('tok-bob', _identity('bob@example.com'))
        self.assertEqual(alice.patch(URL, {'landing_page': 'tests'}, format='json').status_code, 200)
        self.assertEqual(bob.get(URL).data, {'preferences': {}})
        self.assertEqual(alice.get(URL).data, {'preferences': {'landing_page': 'tests'}})
        invalid = APIClient()
        invalid.credentials(HTTP_AUTHORIZATION='Bearer not-a-valid-token')
        self.assertEqual(invalid.get(URL).status_code, 401)


@override_settings(**NATIVE)
class PreferencesNativeSessionTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_native_session_reads_and_writes_its_own_user(self):
        first = make_user('native1', 'native1@example.com')
        second = make_user('native2', 'native2@example.com')
        one = bearer(issue_session_tokens(first, None, 'password')['access'], DEVICE_A)
        two = bearer(issue_session_tokens(second, None, 'password')['access'], DEVICE_B)
        response = one.patch(URL, {'dashboard': {'hidden': ['streak']}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(two.get(URL).data, {'preferences': {}})
        self.assertEqual(one.get(URL).data, {'preferences': {'dashboard': {'hidden': ['streak']}}})
        self.assertEqual(APIClient().get(URL).status_code, 401)
