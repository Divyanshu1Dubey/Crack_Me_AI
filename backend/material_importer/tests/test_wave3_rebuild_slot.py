"""The test rebuild (republish) has its own short-lived slot (wave 3, Z8).

Republish used to take ``summary["publish"]`` as {'state': 'running', 'kind':
'republish'} and give it back only in ``finally``. When the synchronous
request died (gunicorn's 120 s timeout, a worker restart) the batch page
showed "Publishing in the background" for 30 minutes, Publish / Republish /
Rollback stayed disabled and the previous publish result was lost.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from material_importer import api_views
from material_importer.models import ImportBatch
from material_importer.tests.test_wave2_imports import _AdminClientMixin


def _running(minutes_ago=0, **extra):
    ts = (timezone.now() - timedelta(minutes=minutes_ago)).isoformat()
    return {"state": "running", "started_at": ts, "heartbeat_at": ts, "by": "other", **extra}


class RebuildSlotTests(_AdminClientMixin, TestCase):
    DONE = {"state": "done", "published": 3, "tests_built": 2}

    def test_rebuild_uses_its_own_slot_and_keeps_the_last_publish_result(self):
        batch = self.make_batch(publish=self.DONE)
        seen = {}

        def fake_build(batch_id, max_per_test=100):
            summary = ImportBatch.objects.get(pk=batch_id).summary
            seen["publish"] = summary.get("publish")
            seen["rebuild"] = summary.get("rebuild")
            seen["publish_claimed"] = api_views._claim_publish(batch_id, _running())[0]
            seen["rebuild_claimed"] = api_views._claim_publish(batch_id, _running(), key="rebuild")[0]
            return 4

        with patch.object(api_views, "build_for_batch", side_effect=fake_build):
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/republish/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(seen["publish"], self.DONE, "the last publish result is not replaced")
        self.assertEqual((seen["rebuild"]["state"], seen["rebuild"]["kind"]), ("running", "republish"))
        self.assertFalse(seen["publish_claimed"], "no publish while tests are rebuilt")
        self.assertFalse(seen["rebuild_claimed"], "no second rebuild either")
        batch.refresh_from_db()
        self.assertEqual(batch.summary["publish"], self.DONE)
        self.assertNotIn("rebuild", batch.summary)

    def test_a_rebuild_whose_request_died_stops_blocking_after_five_minutes(self):
        batch = self.make_batch(publish=self.DONE, rebuild=_running(minutes_ago=6, kind="republish"))
        with patch.object(api_views, "build_for_batch", return_value=1) as build:
            r = self.client.post(f"/api/admin/import/batches/{batch.id}/republish/")
        self.assertEqual(r.status_code, 200, r.data)
        build.assert_called_once()
        batch.refresh_from_db()
        self.assertEqual(batch.summary["publish"], self.DONE)
        claimed, _ = api_views._claim_publish(batch.id, _running())
        self.assertTrue(claimed)

    def test_a_live_rebuild_blocks_publish_and_rollback(self):
        batch = self.make_batch(rebuild=_running(minutes_ago=1, kind="republish"))
        self.make_eq(batch)
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/publish/", {}, format="json")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn("rebuilt", r.data["error"])
        r = self.client.post(f"/api/admin/import/batches/{batch.id}/rollback/", {"confirm": True}, format="json")
        self.assertEqual(r.status_code, 409, r.data)

    def test_legacy_in_slot_rebuild_state_uses_the_short_window(self):
        live = self.make_batch(publish=_running(minutes_ago=1, kind="republish"))
        self.assertFalse(api_views._claim_publish(live.id, _running())[0])
        dead = self.make_batch(publish=_running(minutes_ago=6, kind="republish"))
        self.assertTrue(api_views._claim_publish(dead.id, _running())[0])
        # A real background publish keeps the 30-minute window.
        publishing = self.make_batch(publish=_running(minutes_ago=6))
        self.assertFalse(api_views._claim_publish(publishing.id, _running())[0])
