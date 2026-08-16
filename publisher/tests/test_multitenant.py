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
        self.rmp = json.loads((ROOT / "publisher/clients/real-media-pro.json").read_text(encoding="utf-8"))
        build_daily_queue._APPROVAL_CACHE.clear()

    def test_f1_generates_four_daily_editorial_roles(self) -> None:
        jobs = build_daily_queue.build_for_client(self.f1, date(2026, 8, 17))
        self.assertEqual(4, len(jobs))
        self.assertEqual(["data", "error", "proof", "decision"], [j["category"] for j in jobs])
        self.assertEqual(["09:00", "12:30", "17:30", "20:30"], [j["scheduled_at"][11:16] for j in jobs])
        self.assertEqual(["reel", "reel", "carousel", "carousel"], [j["format"] for j in jobs])
        self.assertTrue(all(j["client_id"] == "f1-immobiliare" for j in jobs))
        self.assertTrue(all(j["approval_key"] == "2026-W34" for j in jobs))
        allowed_roles = {"data", "error", "proof", "decision", "segnalatori", "recruiting", "metodo", "vendere_da_solo", "leggi_documenti", "home_staging"}
        self.assertTrue(all(j["editorial_role"] in allowed_roles for j in jobs))
        self.assertEqual("F1 Growth Blitz 2026", jobs[0]["campaign"])
        self.assertEqual("F1 Core", jobs[1]["campaign"])
        self.assertEqual("F1 Growth Blitz 2026", jobs[2]["campaign"])
        self.assertEqual("F1 Core", jobs[3]["campaign"])
        self.assertTrue(all(j.get("caption") for j in jobs))
        self.assertTrue(all(j.get("hashtags") for j in jobs))
        self.assertTrue(all("#F1Immobiliare" in j["caption"] for j in jobs))
        self.assertTrue(all(j.get("voiceover") for j in jobs if j["format"] == "reel"))

    def test_real_media_pro_generates_weekly_content(self) -> None:
        self.assertTrue(self.rmp["active"])
        jobs = build_daily_queue.build_for_client(self.rmp, date(2026, 8, 17))
        self.assertEqual(4, len(jobs))
        self.assertEqual(["09:15", "12:45", "17:45", "20:45"], [j["scheduled_at"][11:16] for j in jobs])
        self.assertEqual(["reel", "carousel", "reel", "carousel"], [j["format"] for j in jobs])
        self.assertTrue(all(j["client_id"] == "real-media-pro" for j in jobs))
        self.assertTrue(all(j.get("caption") for j in jobs))
        self.assertTrue(all(j.get("voiceover") for j in jobs if j["format"] == "reel"))
        self.assertEqual(60, self.rmp["brand"]["reel"]["target_seconds"])

    def test_f1_positioning_is_fixed(self) -> None:
        editorial = self.f1["editorial"]
        self.assertEqual("F1 IMMOBILIARE = NON A SENSAZIONE. CON I DATI.", editorial["positioning"])
        self.assertEqual("Prima i dati. Poi la strategia. Poi la vendita.", editorial["master_line"])
        self.assertEqual("VALUTAZIONE", self.f1["campaign"]["keyword"])
        self.assertIn("6a814ec3-80cc-83eb-b9b6-a56f02c348e8", editorial["source_chat_url"])

    def test_unapproved_week_blocks_publish_before_integrations(self) -> None:
        jobs = build_daily_queue.build_for_client(self.f1, date(2026, 8, 17))
        self.assertTrue(all(j["status"] == "awaiting_approval" for j in jobs))
        self.assertTrue(all("2026-W34" in j["blocked_reason"] for j in jobs))

    def test_carousel_has_one_media_file_per_slide(self) -> None:
        jobs = build_daily_queue.build_for_client(self.f1, date(2026, 8, 17))
        carousel = jobs[2]
        self.assertEqual("carousel", carousel["format"])
        self.assertIsInstance(carousel["media"], list)
        self.assertEqual(len(carousel["slides"]), len(carousel["media"]))
        self.assertTrue(all(str(x).endswith(".jpg") for x in carousel["media"]))

    def test_direct_api_integrations_are_exposed_for_reels(self) -> None:
        specs, missing = build_daily_queue.integration_specs(self.f1, "reel")
        self.assertEqual([], missing)
        expected_platforms = ["facebook", "instagram", "tiktok", "linkedin", "youtube"]
        self.assertEqual(expected_platforms, [spec["platform"] for spec in specs])
        self.assertTrue(all(spec["integration_id"] == "direct-api" for spec in specs))

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

    def test_instagram_defaults_depend_on_content_format(self) -> None:
        integration = {"id": "ig-f1", "identifier": "instagram", "name": "F1 Immobiliare"}
        reel = postiz_publish.default_settings("instagram", {"title": "Test Reel", "format": "reel"}, integration)
        carousel = postiz_publish.default_settings("instagram", {"title": "Test Carousel", "format": "carousel"}, integration)
        self.assertEqual("instagram", reel["__type"])
        self.assertEqual("reel", reel["post_type"])
        self.assertEqual("post", carousel["post_type"])
        self.assertFalse(reel["is_trial_reel"])


if __name__ == "__main__":
    unittest.main()
