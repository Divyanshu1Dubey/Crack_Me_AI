"""MCE content IDs keep their digests with ``usedforsecurity=False`` (wave 3, Z8 for Z9).

Stage 10 chunk IDs and Stage 7.5 reference IDs are SHA-1 content
fingerprints, not security hashes. Passing ``usedforsecurity=False`` clears
bandit B324 without a baseline entry; the digest is the same, so IDs already
written to chunk JSONL and the DB stay stable across re-runs.

The pinned values were computed with the call as it was before the change,
``hashlib.sha1(raw.encode('utf-8')).hexdigest()`` (16 hex chars for chunks,
12 for references).

unittest-style so both the Django runner and pytest collect it:
    python manage.py test mce.tests.test_wave3_hash_ids
    python -m pytest mce/tests/test_wave3_hash_ids.py
"""
from __future__ import annotations

import unittest

from mce.stages.stage_10_rag import _chunk_id, _make_chunk
from mce.stages.stage_7_5_llm import _merge


class ChunkIdTests(unittest.TestCase):
    # (question_id, chunk_type, suffix) -> "chk_" + sha1("<qid>|<type>|<suffix>")[:16]
    PINNED = {
        ("q_0001", "stem", ""): "chk_8ae3cb155304ae9d",
        ("q_0001", "options", ""): "chk_ebad8d2b21d1b07b",
        ("q_0042", "table", "tbl_p38_1"): "chk_29b892215948fd80",
    }

    def test_chunk_ids_are_unchanged(self):
        for (qid, chunk_type, suffix), expected in self.PINNED.items():
            with self.subTest(qid=qid, chunk_type=chunk_type, suffix=suffix):
                self.assertEqual(_chunk_id(qid, chunk_type, suffix), expected)

    def test_emitted_chunk_carries_the_same_id(self):
        chunk = _make_chunk({"id": "q_0042"}, "table", "tbl_p38_1", suffix="tbl_p38_1", asset_refs=["tbl_p38_1"])
        self.assertEqual(chunk["chunk_id"], "chk_29b892215948fd80")
        self.assertEqual(_make_chunk({"id": "q_0001"}, "stem", "Stem text")["chunk_id"], "chk_8ae3cb155304ae9d")


class ReferenceIdTests(unittest.TestCase):
    # citation_text -> "ref_" + sha1(citation_text)[:12]
    PINNED = {
        "Harrison 21e, Ch 5": "ref_7fc1eb29327d",
        "Bailey & Love 28e, p. 1102": "ref_f1607590a995",
    }

    def test_llm_reference_ids_are_unchanged(self):
        merged = _merge({}, {"references": [{"citation_text": text} for text in self.PINNED]})
        self.assertEqual([r["id"] for r in merged["references"]], list(self.PINNED.values()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
