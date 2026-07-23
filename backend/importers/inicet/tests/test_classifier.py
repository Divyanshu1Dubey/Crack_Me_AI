"""Classifier module tests."""
import unittest

from backend.importers.neetpg import classifier as cls


class GarbledRatioTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(cls.garbled_ratio(""), 0.0)

    def test_normal_text(self):
        self.assertLess(cls.garbled_ratio("Hello world this is a question stem."), 0.01)


class ClassifyTests(unittest.TestCase):
    def test_blank(self):
        f = cls.features_for(1, "", 0)
        self.assertEqual(cls.classify(f), "blank")

    def test_digital(self):
        text = "Q.1 A 23-year-old male presents with chest pain radiating to the left arm."
        f = cls.features_for(1, text, 0)
        self.assertEqual(cls.classify(f), "digital")

    def test_scanned(self):
        f = cls.features_for(1, "", 3)
        self.assertEqual(cls.classify(f), "scanned")

    def test_hybrid_short_text(self):
        f = cls.features_for(1, "Q1. stem", 1)
        # text under HYBRID threshold (250) but >= 50 and image present
        self.assertEqual(cls.classify(f), "hybrid")


class AggregateTests(unittest.TestCase):
    def test_counts(self):
        feats = [
            cls.features_for(1, "Q.1 " + "x" * 200, 0),
            cls.features_for(2, "", 2),
            cls.features_for(3, "Q.2 " + "y" * 200, 1),
        ]
        agg = cls.aggregate(feats)
        self.assertEqual(agg["total_pages"], 3)
        self.assertEqual(agg["pages_digital"] + agg["pages_scanned"] + agg["pages_hybrid"], 3)


if __name__ == "__main__":
    unittest.main()