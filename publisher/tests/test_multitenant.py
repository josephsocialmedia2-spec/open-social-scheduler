from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from publisher import build_daily_queue
from publisher import postiz_publish

ROOT = Path(__file__).resolve().parents[2]


class MultiTenantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.f1 = json.loads((ROOT / "publisher/clients/f1-immobiliare.json").read_text(encoding="utf-8"))

    def test_f1_generates_four_daily_slots(self) -> None:
        jobs = build_daily_queue.build_for_client(self.f1, date(2026, 8, 16))
        self.assertEqual(4, len(jobs))
        self.assertEqual(["attract", "nurture", "hyperlocal", "convert"], [j["category"] for j in jobs])
        self.assertEqual(["09:00", "12:30", "17:30", "20:30"], [j["scheduled_at"][11:16] for j in jobs])
        self.assertTrue(all(j["client_id"] == "f1-immobiliare" for j in jobs))

    def test_unconfigured_required_accounts_block_publish(self) -> None:
        specs, missing = build_daily_queue.integration_specs(self.f1)
        self.assertEqual([], specs)
        self.assertIn("facebook", missing)
        self.assertIn("instagram", missing)

    def test_exact_integration_id_is_verified(self) -> None:
        integrations = [
            {"id": "fb-f1", "identifier": "facebook", "name": "F1 Immobiliare", "disabled": False},
            {"id": "fb-other", "identifier": "facebook", "name": "Other Client", "disabled": False},
        ]
        item = postiz_publish.verify_exact_integration(integrations, "facebook", "fb-f1")
        self.assertEqual("F1 Immobiliare", item["name"])
        with self.assertRaises(RuntimeError):
            postiz_publish.verify_exact_integration(integrations, "instagram", "fb-f1")

    def test_legacy_guessing_is_off_by_default(self) -> None:
        integrations = [{"id": "x", "identifier": "facebook", "name": "F1 Immobiliare"}]
        if not postiz_publish.ALLOW_LEGACY_HINTS:
            with self.assertRaises(RuntimeError):
                postiz_publish.legacy_select(integrations, "facebook", "F1")

    def test_instagram_video_defaults_to_reel(self) -> None:
        integration = {"id": "ig-f1", "identifier": "instagram", "name": "F1 Immobiliare"}
        settings = postiz_publish.default_settings("instagram", {"title": "Test Reel"}, integration)
        self.assertEqual("instagram", settings["__type"])
        self.assertEqual("reel", settings["post_type"])
        self.assertFalse(settings["is_trial_reel"])


if __name__ == "__main__":
    unittest.main()
