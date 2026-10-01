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


    def test_real_media_pro_has_protected_oauth_wizard(self):
        html = (ROOT / "f1-content-hub" / "index.html").read_text(encoding="utf-8")
        for token in [
            "COLLEGA TUTTI OAUTH",
            "f1ConnectAllRmpOAuth",
            "f1ContinueRmpOAuth",
            "f1-rmp-connect-all",
            "PROFILO UFFICIALE RICHIESTO",
            "LINKEDIN IN ATTESA",
            'const targets=["facebook","instagram","tiktok","youtube"]',
            'setTab(requestedView||"connections")',
        ]:
            self.assertIn(token, html)

    def test_rmp_oauth_config_is_explicit(self):
        cfg = json.loads((ROOT / "publisher" / "clients" / "real-media-pro.json").read_text(encoding="utf-8"))
        oauth = cfg.get("oauth") or {}
        self.assertTrue(oauth.get("enabled"))
        self.assertEqual(oauth.get("provider"), "supabase_edge_function")
        self.assertEqual(oauth.get("broker_function"), "f1-social-oauth")
        self.assertEqual(oauth.get("token_storage"), "supabase_encrypted")
        self.assertEqual(oauth.get("account_lock_platforms"), ["facebook", "instagram", "tiktok", "youtube"])
        self.assertEqual(oauth.get("linkedin_mode"), "pending_author_type")
        for platform in ["facebook", "instagram", "tiktok", "youtube"]:
            self.assertEqual(cfg["integrations"][platform].get("auth"), "oauth_broker")
        self.assertEqual(cfg["integrations"]["linkedin"].get("auth"), "pending_author_type")

    def test_oauth_callback_returns_to_selected_connections_view(self):
        edge = (ROOT / "supabase" / "functions" / "f1-social-oauth" / "index.ts").read_text(encoding="utf-8")
        self.assertIn("function hubReturnUrl", edge)
        self.assertIn('target.searchParams.set("view", "connections")', edge)
        self.assertIn('target.searchParams.set("client", String(client.slug))', edge)
        self.assertIn("function oauthReturnUrl", edge)
        self.assertIn(
            'return state?.invite_id ? inviteReturnUrl(oauthState, platform) : hubReturnUrl(client, oauthState, platform);',
            edge,
        )
        self.assertIn('return redirect(oauthReturnUrl(client, state, "connected", platform))', edge)
        self.assertIn('return redirect(hubReturnUrl(client, "select_account", platform))', edge)

    def test_oauth_account_lock_can_be_scoped_per_platform(self):
        edge = (ROOT / "supabase" / "functions" / "f1-social-oauth" / "index.ts").read_text(encoding="utf-8")
        self.assertIn("oauth_whitelist_platforms", edge)
        self.assertIn("exclusiveWhitelist(client, platform)", edge)


if __name__ == "__main__":
    unittest.main()
