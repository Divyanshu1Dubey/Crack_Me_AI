"""Fingerprint module tests — text normalisation + sha helpers."""
import hashlib
import unittest

from backend.importers.neetpg import fingerprints as fp


class NormaliseTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(fp.normalise_text("a   b\n\nc\t\td"), "a b c d")

    def test_strips_header_footer(self):
        s = "Header: www.example.com  body content  Page 12 of 230"
        self.assertIn("body content", fp.normalise_text(s))
        self.assertNotIn("Page 12", fp.normalise_text(s))


class HashTests(unittest.TestCase):
    def test_sha256_short_deterministic(self):
        a = fp.sha256_short("hello world")
        b = fp.sha256_short("hello world")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        # Cross-check against hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()[:16]
        self.assertEqual(a, expected)

    def test_page_text_hash_normalises(self):
        a = fp.page_text_hash("Q.1  foo")
        b = fp.page_text_hash("  Q.1   foo  ")
        # page_text_hash should normalise before hashing
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()