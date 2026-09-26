import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SocialOAuthUiTests(unittest.TestCase):
    def test_meta_platforms_use_oauth_broker_when_requested(self):
        src = (ROOT / "publisher" / "direct_api_publish.py").read_text(encoding="utf-8")
        self.assertIn('platform in {"facebook", "instagram", "tiktok", "linkedin", "linkedin-page", "youtube"}', src)
        self.assertIn('oauth_broker.token(client, "facebook"', src)
        self.assertIn('oauth_broker.token(client, "instagram"', src)

    def test_frontend_has_full_social_controls(self):
        html = (ROOT / "f1-content-hub" / "index.html").read_text(encoding="utf-8")
        for token in [
            "APRI PAGINA",
            "SALVA LINK",
            "SCOPRI SOCIAL",
            "SELEZIONA ACCOUNT",
            "/profile-url",
            "/discover-socials",
            "/meta/select",
            "/verify",
        ]:
            self.assertIn(token, html)

    def test_buffer_is_preserved(self):
        html = (ROOT / "f1-content-hub" / "index.html").read_text(encoding="utf-8")
        self.assertIn('row&&row.provider==="buffer"', html)
        self.assertIn("Questo canale è gestito da Buffer", html)

    def test_meta_migration_is_data_driven(self):
        sql = (ROOT / "supabase" / "migrations" / "20260926_social_links_meta_oauth.sql").read_text(encoding="utf-8")
        self.assertIn("profile_url", sql)
        self.assertIn("'facebook', 'oauth_broker'", sql)
        self.assertIn("'instagram', 'oauth_broker'", sql)
        self.assertIn("before_social_links_meta_oauth_20260926", sql)

    def test_new_clients_still_seed_five_channels(self):
        sql = (ROOT / "supabase" / "migrations" / "20260926_social_links_meta_oauth.sql").read_text(encoding="utf-8")
        for p in ["facebook", "instagram", "linkedin-page", "tiktok", "youtube"]:
            self.assertIn(f"'{p}'", sql)

    def test_shared_tiktok_accounts_are_blocked_in_queue(self):
        src = (ROOT / "publisher" / "supabase_queue_bridge.py").read_text(encoding="utf-8")
        self.assertIn('reason = "ACCOUNT_CONDIVISO"', src)
        self.assertIn('platform == "tiktok"', src)
        html = (ROOT / "f1-content-hub" / "index.html").read_text(encoding="utf-8")
        self.assertIn('"ACCOUNT_CONDIVISO"', html)


if __name__ == "__main__":
    unittest.main()
