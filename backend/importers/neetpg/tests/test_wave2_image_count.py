"""images_unlinked counts every ambiguous image, not just the reported ones (wave 2, W10)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from importers import image_linking
from importers.image_linking import link_images_by_page
from importers.neetpg.db_writer import DjangoWriter
from importers.neetpg.models import ImageRecord
from importers.neetpg.tests.test_wave1_recall_writer import _pq, _WriterCase


class UnlinkedImageCountTests(_WriterCase):
    def _img(self, page, idx, sha):
        from PIL import Image
        path = Path(self.media) / f"p{page}_{idx}.png"
        Image.new("RGB", (3, 3), (page * 20, idx * 40, 90)).save(path, format="PNG")
        return ImageRecord(source_sha16="s" * 16, page_number=page, image_index_in_page=idx,
                           file_path=str(path), sha256=sha * 4, sha256_short=sha)

    def test_count_is_not_capped_by_the_detail_list(self):
        w = DjangoWriter()
        written = []
        for p in (
            _pq("Page one first figure?", page=1, qno=1, image_based=True),
            _pq("Page one second figure?", page=1, qno=2, image_based=True),
        ):
            written.append((p, w.write_question(p, self.rs)))
        # Five different images on a page with two image questions: all ambiguous.
        images = [self._img(1, i, f"{i}" * 16) for i in range(5)]

        with patch.object(image_linking, "MAX_REPORTED_UNLINKED", 2):
            stats = link_images_by_page(w, written, images, self.rs)

        self.assertEqual(stats["images_linked"], 0)
        self.assertEqual(stats["images_unlinked"], 5)
        self.assertEqual(len(stats["unlinked_images"]), 2)
        self.assertTrue(stats["unlinked_images_truncated"])
        self.assertEqual(stats["questions_flagged_for_image_review"], 2)
