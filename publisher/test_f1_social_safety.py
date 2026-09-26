# CI regression suite: F1 Social fail-closed isolation.
import hashlib
import tempfile
import unittest
from pathlib import Path

from publisher.f1_social_safety import (
    SecurityError,
    assert_broker_account,
    assert_job_safety,
)

CLIENT = {
    "id": "f1-social",
    "safety": {
        "exclusive_account_whitelist": True,
        "allow_client_accounts": False,
    },
    "authorized_accounts": {
        "facebook": {
            "url": "https://www.facebook.com/josephrealmedia",
            "handle": "josephrealmedia",
            "authorized": True,
        },
        "instagram": {
            "url": "https://www.instagram.com/realmediaproageency/",
            "handle": "realmediaproageency",
            "authorized": True,
        },
        "tiktok": {
            "url": "https://www.tiktok.com/@realmediapro_agency",
            "handle": "@realmediapro_agency",
            "authorized": True,
        },
        "youtube": {
            "url": "https://www.youtube.com/channel/UC4G1Oq0z-_b0UTwRmYBxbCA",
            "channel_id": "UC4G1Oq0z-_b0UTwRmYBxbCA",
            "authorized": True,
        },
    },
}

ANTICA = {
    "id": "antica-cappella",
    "safety": {
        "exclusive_account_whitelist": True,
        "allow_client_accounts": False,
    },
    "authorized_accounts": {
        "facebook": {
            "url": "https://www.facebook.com/profile.php?id=61550077453442",
            "authorized": True,
        },
        "instagram": {
            "url": "https://www.instagram.com/anticacappella/",
            "handle": "anticacappella",
            "authorized": True,
        },
        "tiktok": {
            "url": "https://www.tiktok.com/@ristoranteanticacappella",
            "handle": "@ristoranteanticacappella",
            "authorized": True,
        },
        "youtube": {
            "url": "https://www.youtube.com/@ristoranteanticacappella",
            "handle": "@ristoranteanticacappella",
            "authorized": True,
        },
    },
}


class F1SocialSafetyTests(unittest.TestCase):
    def test_exact_facebook_account_passes(self):
        assert_broker_account(CLIENT, "facebook", {
            "profile_url": "https://www.facebook.com/josephrealmedia/",
            "account_id": "123",
            "scopes": ["pages_manage_posts"],
            "account_shared": False,
        })

    def test_antica_cappella_facebook_page_id_passes(self):
        assert_broker_account(ANTICA, "facebook", {
            "profile_url": "https://www.facebook.com/AnticaCappella",
            "account_id": "61550077453442",
            "scopes": ["pages_manage_posts"],
            "account_shared": False,
        })

    def test_antica_cappella_wrong_facebook_page_is_blocked(self):
        with self.assertRaisesRegex(SecurityError, "BLOCKED_ACCOUNT_OWNERSHIP_MISMATCH"):
            assert_broker_account(ANTICA, "facebook", {
                "profile_url": "https://www.facebook.com/other-page",
                "account_id": "111111111111111",
                "scopes": ["pages_manage_posts"],
                "account_shared": False,
            })

    def test_wrong_account_is_blocked(self):
        with self.assertRaisesRegex(SecurityError, "BLOCKED_ACCOUNT_OWNERSHIP_MISMATCH"):
            assert_broker_account(CLIENT, "facebook", {
                "profile_url": "https://www.facebook.com/marta.ruffino",
                "account_id": "marta-token-account",
                "scopes": ["pages_manage_posts"],
                "account_shared": False,
            })

    def test_shared_account_is_blocked(self):
        with self.assertRaisesRegex(SecurityError, "ACCOUNT_CONDIVISO"):
            assert_broker_account(CLIENT, "tiktok", {
                "profile_url": "https://www.tiktok.com/@realmediapro_agency",
                "creator_username": "realmediapro_agency",
                "account_id": "shared-account",
                "scopes": ["video.publish"],
                "account_shared": True,
            })

    def test_missing_scope_is_blocked(self):
        with self.assertRaisesRegex(SecurityError, "AUTH_REQUIRED_SCOPE"):
            assert_broker_account(CLIENT, "instagram", {
                "profile_url": "https://www.instagram.com/realmediaproageency/",
                "account_id": "ig-1",
                "scopes": ["instagram_basic"],
                "account_shared": False,
            })

    def test_unwhitelisted_platform_is_blocked(self):
        with self.assertRaisesRegex(SecurityError, "ACCOUNT_NON_AUTORIZZATO"):
            assert_broker_account(CLIENT, "linkedin", {
                "profile_url": "https://www.linkedin.com/in/example/",
                "account_id": "li-1",
                "scopes": ["w_member_social"],
                "account_shared": False,
            })

    def test_youtube_channel_id_passes(self):
        assert_broker_account(CLIENT, "youtube", {
            "profile_url": "https://www.youtube.com/@RealMediaPro",
            "account_id": "UC4G1Oq0z-_b0UTwRmYBxbCA",
            "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
            "account_shared": False,
        })

    def test_media_hash_and_tenant_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "media.png"
            p.write_bytes(b"f1-social-test")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            assert_job_safety(CLIENT, {
                "client_id": "f1-social",
                "provider": "oauth_broker",
                "expected_media_sha256": digest,
            }, [p], ["facebook"])

    def test_media_hash_mismatch_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "media.png"
            p.write_bytes(b"wrong-media")
            with self.assertRaisesRegex(SecurityError, "MEDIA_DIVERSO_DALL_ORIGINALE"):
                assert_job_safety(CLIENT, {
                    "client_id": "f1-social",
                    "provider": "oauth_broker",
                    "expected_media_sha256": "0" * 64,
                }, [p], ["facebook"])

    def test_wrong_tenant_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "media.png"
            p.write_bytes(b"x")
            with self.assertRaisesRegex(SecurityError, "BLOCKED_TENANT_OWNERSHIP_MISMATCH"):
                assert_job_safety(CLIENT, {
                    "client_id": "marta-ruffino",
                    "provider": "oauth_broker",
                }, [p], ["facebook"])

    def test_direct_provider_is_blocked_for_f1_social(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "media.png"
            p.write_bytes(b"x")
            with self.assertRaisesRegex(SecurityError, "F1_SOCIAL_REQUIRES_OAUTH_BROKER"):
                assert_job_safety(CLIENT, {
                    "client_id": "f1-social",
                    "provider": "direct",
                }, [p], ["facebook"])


if __name__ == "__main__":
    unittest.main()
