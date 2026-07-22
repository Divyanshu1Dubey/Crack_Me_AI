"""Deduplicator tests — sha + fuzzy + image-hash."""
import unittest

from backend.importers.neetpg import deduplicator
from backend.importers.neetpg.models import ImageRecord, ParsedOption, ParsedQuestion


def _q(stem: str, sha16: str = "abc") -> ParsedQuestion:
    return ParsedQuestion(
        source_sha16=sha16, page_number=1,
        stem=stem, stem_raw=stem,
        options=[ParsedOption(label="A", text="a"), ParsedOption(label="B", text="b")],
        answer_labels=["A"],
    )


def _img(phash: str = "", sha: str = "") -> ImageRecord:
    return ImageRecord(
        source_sha16="abc", page_number=1, image_index_in_page=0,
        file_path="/tmp/x.png", sha256=sha, sha256_short=sha[:16], phash=phash,
    )


class NormaliseTests(unittest.TestCase):
    def test_strips_image_refs(self):
        s = deduplicator.normalise("[image] What is shown?  Q.1 stem")
        self.assertNotIn("[image]", s)
        self.assertNotIn("q.1", s)


class ShaTests(unittest.TestCase):
    def test_identical_text_same_sha(self):
        self.assertEqual(
            deduplicator.text_sha256("Q.1 What is X?"),
            deduplicator.text_sha256("Q.1   What is X?"),
        )

    def test_different_text_different_sha(self):
        self.assertNotEqual(
            deduplicator.text_sha256("Q.1 What is X?"),
            deduplicator.text_sha256("Q.1 What is Y?"),
        )


class DedupBatchTests(unittest.TestCase):
    def test_exact_sha_duplicate(self):
        qs = [_q("Identical stem here."), _q("Identical stem here.")]
        r = deduplicator.dedup_batch(qs, [])
        self.assertEqual(r.new_canonical, 1)
        self.assertEqual(r.exact_sha_duplicates, 1)

    def test_image_dedup(self):
        imgs = [_img(phash="00000000"), _img(phash="00000000")]
        r = deduplicator.dedup_batch([], imgs)
        self.assertGreaterEqual(r.image_duplicates, 1)


class HammingTests(unittest.TestCase):
    def test_distance(self):
        self.assertEqual(deduplicator.hamming("0000", "0001"), 1)
        self.assertEqual(deduplicator.hamming("0000", "1111"), 4)
        self.assertEqual(deduplicator.hamming("", ""), 99)


if __name__ == "__main__":
    unittest.main()