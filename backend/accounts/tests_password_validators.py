"""accounts.password_validators.PublishedPasswordValidator: published passwords are refused everywhere."""
from django.contrib.auth.password_validation import get_default_password_validators, validate_password
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from accounts.password_validators import (
    BUILTIN_PUBLISHED_PASSWORD_SHA256,
    PublishedPasswordValidator,
    is_published_password,
    normalised_password_digest,
)

# A stand-in "published" password for the tests (the real one is never written into the repository).
STAND_IN = 'Stand-In-Published-Pw-42!'


class PublishedPasswordValidatorTests(SimpleTestCase):
    def test_builtin_digests_are_sha256_hex(self):
        self.assertTrue(BUILTIN_PUBLISHED_PASSWORD_SHA256)
        for digest in BUILTIN_PUBLISHED_PASSWORD_SHA256:
            self.assertRegex(digest, r'^[0-9a-f]{64}$')

    def test_digest_ignores_case_and_surrounding_spaces(self):
        self.assertEqual(normalised_password_digest(STAND_IN), normalised_password_digest(f'  {STAND_IN.upper()} '))

    def test_a_listed_password_is_refused_with_its_code(self):
        with override_settings(PUBLISHED_PASSWORD_SHA256=normalised_password_digest(STAND_IN)):
            self.assertTrue(is_published_password(STAND_IN.lower()))
            with self.assertRaises(ValidationError) as refused:
                PublishedPasswordValidator().validate(STAND_IN)
            self.assertEqual(refused.exception.error_list[0].code, 'password_published')
            # And through Django's validator chain (sign-up, password change and reset call it).
            with self.assertRaises(ValidationError):
                validate_password(STAND_IN)
        PublishedPasswordValidator().validate(STAND_IN)  # not listed any more: accepted

    def test_registered_in_auth_password_validators(self):
        names = [type(v).__name__ for v in get_default_password_validators()]
        self.assertIn('PublishedPasswordValidator', names)
