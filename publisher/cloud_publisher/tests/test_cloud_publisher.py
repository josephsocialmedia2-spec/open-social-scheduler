from __future__ import annotations

import unittest

from publisher.cloud_publisher.browser.base import expected_handle
from publisher.cloud_publisher.runtime import api_ready
from publisher.cloud_publisher.queue import PublicationJob, normalize_platform


class CloudPublisherTests(unittest.TestCase):
    def test_platform_normalization(self):
        self.assertEqual("linkedin-page", normalize_platform("linkedin"))
        self.assertEqual("facebook", normalize_platform("FACEBOOK"))

    def test_api_ready_requires_verified_enabled_and_no_reauth(self):
        self.assertTrue(
            api_ready(
                {
                    "enabled": True,
                    "verified": True,
                    "reauthorization_required": False,
                    "connection_status": "COLLEGATO",
                    "provider": "oauth_broker",
                }
            )
        )
        self.assertFalse(
            api_ready(
                {
                    "enabled": True,
                    "verified": False,
                    "reauthorization_required": False,
                    "connection_status": "COLLEGATO",
                    "provider": "oauth_broker",
                }
            )
        )
        self.assertFalse(
            api_ready(
                {
                    "enabled": True,
                    "verified": True,
                    "reauthorization_required": True,
                    "connection_status": "COLLEGATO",
                    "provider": "oauth_broker",
                }
            )
        )
        self.assertFalse(
            api_ready(
                {
                    "enabled": True,
                    "verified": True,
                    "reauthorization_required": False,
                    "connection_status": "ACCOUNT_CONDIVISO",
                    "provider": "oauth_broker",
                }
            )
        )

    def test_expected_handles(self):
        self.assertEqual(
            "61550077453442",
            expected_handle(
                "facebook",
                "https://www.facebook.com/profile.php?id=61550077453442",
            ),
        )
        self.assertEqual(
            "anticacappella",
            expected_handle(
                "instagram",
                "https://www.instagram.com/anticacappella/",
            ),
        )
        self.assertEqual(
            "ristoranteanticacappella",
            expected_handle(
                "tiktok",
                "https://www.tiktok.com/@ristoranteanticacappella",
            ),
        )

    def test_publication_job_accepts_media_dict_as_list(self):
        row = {
            "id": "1",
            "owner_id": "o",
            "client_id": "c",
            "content_id": "x",
            "calendar_id": None,
            "platform": "facebook",
            "scheduled_at": "2026-09-27T12:00:00Z",
            "content_type": "FOTO",
            "caption": "test",
            "media_payload": {"file_name": "a.jpg"},
            "metadata": {},
            "attempt_count": 0,
        }
        job = PublicationJob.from_row(row)
        self.assertEqual(1, len(job.media_payload))


if __name__ == "__main__":
    unittest.main()
