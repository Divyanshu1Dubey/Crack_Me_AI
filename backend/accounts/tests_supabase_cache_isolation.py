"""Regression: Supabase token-validation cache must never mix up users.

The cache key used to be token[:64] -- for Supabase JWTs that is only the
JWT header, identical for every user -- so user B could be authenticated
as user A for up to five minutes.
"""
import base64
import io
import json
import time
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.supabase_rest_auth import SupabaseJWTAuthentication


def _b64(data):
    return base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).rstrip(b'=').decode()


HEADER = _b64({'alg': 'HS256', 'kid': 'abcdEFGHij1234', 'typ': 'JWT'})


def _token(sub):
    # A live token: _fetch_supabase_user refuses expired / exp-less values locally.
    payload = _b64({'iss': 'https://example.supabase.co/auth/v1', 'sub': sub, 'exp': int(time.time()) + 3600})
    return f'{HEADER}.{payload}.signature-{sub}'


class _FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'sb-iso'}})
class SupabaseTokenCacheIsolationTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_tokens_sharing_a_header_do_not_share_identity(self):
        token_a, token_b = _token('user-a'), _token('user-b')
        self.assertEqual(token_a[:64], token_b[:64])  # the old (buggy) key collided

        identities = {
            token_a: {'id': 'a', 'email': 'a@example.com'},
            token_b: {'id': 'b', 'email': 'b@example.com'},
        }

        def fake_urlopen(req, timeout=8):
            bearer = req.headers['Authorization'].split(' ', 1)[1]
            return _FakeResponse(json.dumps(identities[bearer]).encode())

        auth = SupabaseJWTAuthentication()
        env = {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_ANON_KEY': 'anon'}
        with mock.patch.dict('os.environ', env), \
                mock.patch('accounts.supabase_rest_auth.request.urlopen', side_effect=fake_urlopen):
            first = auth._fetch_supabase_user(token_a)
            second = auth._fetch_supabase_user(token_b)
            again = auth._fetch_supabase_user(token_a)

        self.assertEqual(first['email'], 'a@example.com')
        self.assertEqual(second['email'], 'b@example.com')
        self.assertEqual(again['email'], 'a@example.com')
