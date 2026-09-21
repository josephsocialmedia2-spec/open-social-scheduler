from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
PUBLISHER = ROOT / "publisher"
if str(PUBLISHER) not in sys.path:
    sys.path.insert(0, str(PUBLISHER))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import final_asset_publisher as publisher
from publisher.chatgpt_query_runner.core import create_run, blank_state


class AutonomousPipelineTests(unittest.TestCase):
    def test_communication_to_published_without_duplicates(self):
        state = blank_state()
        rows = [{
            "id": "COMM-E2E-TEST",
            "query": "Comunicazione di prova",
            "communication": "Comunicazione di prova",
            "prompt": "Genera una grafica di prova",
            "caption": "Comunicazione di prova",
            "client": "F1 Immobiliare",
            "scope": "network",
            "platforms": ["facebook", "instagram"],
            "scheduled_at": "2026-09-20T14:30:00+02:00",
            "source": "client-communication",
        }]
        run = create_run(state, rows, 1)
        generated = run["jobs"][0]
        self.assertEqual(generated["query_id"], "COMM-E2E-TEST")
        self.assertEqual(generated["prompt"], "Genera una grafica di prova")
        self.assertEqual(generated["caption"], "Comunicazione di prova")

        with tempfile.TemporaryDirectory(dir=ROOT / "publisher" / "final_assets") as tmp:
            asset = Path(tmp) / "comm-e2e-test.png"
            Image.new("RGB", (1080, 1350), (255, 255, 255)).save(asset, "PNG", compress_level=0)
            rel = asset.relative_to(ROOT).as_posix()
            queue_path = Path(tmp) / "queue.json"
            job = {
                "id": "manual-test-e2e",
                "communication_id": "COMM-E2E-TEST",
                "title": "Comunicazione di prova",
                "caption": "Comunicazione di prova",
                "format": "photo",
                "assets": [{"path": rel}],
                "platforms": ["facebook", "instagram"],
                "scope": "network",
                "territory": "",
                "scheduled_at": "2026-09-20T14:30:00+02:00",
                "status": "READY",
                "buffer_posts": [],
                "buffer_scheduled_platforms": [],
                "approval_required": False,
                "manual_approval_required": False,
                "autonomous_publish": True,
            }
            queue = {
                "version": 3,
                "pipeline": "f1-final-assets",
                "asset_policy": "immutable-final-layout",
                "jobs": [job],
            }
            queue_path.write_text(json.dumps(queue), encoding="utf-8")

            created_services = []

            def fake_channels(_api_key, _job):
                return "org-test", {
                    "facebook": {"id": "fb-channel", "service": "facebook", "name": "Facebook"},
                    "instagram": {"id": "ig-channel", "service": "instagram", "name": "Instagram"},
                }

            def fake_create(_api_key, channel_id, service, _buffer_job, _hosted, _now):
                created_services.append(service)
                return {
                    "service": service,
                    "channel_id": channel_id,
                    "post_id": f"{service}-post-1",
                    "buffer_status": "scheduled",
                    "due_at": None,
                    "created_at": "2026-09-20T12:30:00+00:00",
                }

            def fake_status(_api_key, post_id):
                service = "facebook" if post_id.startswith("facebook") else "instagram"
                return {
                    "post_id": post_id,
                    "buffer_status": "sent",
                    "sent_at": "2026-09-20T12:31:00+00:00",
                    "external_link": f"https://example.invalid/{service}/post-1",
                    "channel_id": f"{service}-channel",
                }

            with (
                patch.object(publisher, "QUEUE_PATH", queue_path),
                patch.object(publisher.territory_router, "resolve_job_channels", side_effect=fake_channels),
                patch.object(
                    publisher.base,
                    "ensure_cloudinary_assets",
                    return_value=[{"url": "https://example.invalid/asset.png"}],
                ),
                patch.object(publisher.base, "create_buffer_post", side_effect=fake_create),
                patch.object(publisher.base, "get_buffer_post", side_effect=fake_status),
            ):
                code = publisher.publish_job(
                    queue,
                    job,
                    "buffer-key",
                    "cloudinary://key:secret@cloud",
                    dry_run=False,
                )

            self.assertEqual(code, 0)
            self.assertEqual(job["status"], "PUBLISHED_VERIFIED")
            self.assertEqual(job["attempt_count"], 1)
            self.assertEqual(job["last_step"], "PUBLISHED_VERIFIED")
            self.assertIsNone(job["last_error"])
            self.assertTrue(str(job.get("updated_at") or ""))
            self.assertEqual(created_services, ["facebook", "instagram"])
            self.assertEqual(
                set(job["buffer_scheduled_platforms"]),
                {"facebook", "instagram"},
            )
            self.assertEqual(len(job["buffer_posts"]), 2)
            self.assertEqual(len(job["published_urls"]), 2)
            self.assertIsNone(
                publisher.next_ready(
                    queue,
                    communications_only=True,
                )
            )

    def test_instagram_static_graphic_uses_post_type(self):
        metadata = publisher.base.gql_metadata("instagram", {"format": "photo"})
        self.assertIn("type: post", metadata)
        self.assertNotIn("type: carousel", metadata)


if __name__ == "__main__":
    unittest.main()
