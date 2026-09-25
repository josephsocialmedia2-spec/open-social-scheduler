import os
import unittest
from unittest.mock import patch, Mock

import oauth_broker


class OAuthBrokerTests(unittest.TestCase):
    def test_disabled_without_explicit_flag(self):
        with patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": "secret"}, clear=True):
            self.assertFalse(oauth_broker.enabled())

    def test_successful_token_response(self):
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {
            "access_token": "token-value",
            "account_name": "Example",
            "author_urn": "urn:li:person:123",
        }
        env = {
            "F1_OAUTH_BROKER_ENABLED": "true",
            "SUPABASE_SERVICE_ROLE_KEY": "service-key",
            "F1_OAUTH_BROKER_URL": "https://example.test/functions/v1/f1-social-oauth",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "oauth_broker.requests.get", return_value=response
        ) as get:
            result = oauth_broker.token({"id": "client-slug"}, "linkedin")
        self.assertEqual(result["access_token"], "token-value")
        get.assert_called_once()

    def test_auth_required_is_distinct(self):
        response = Mock()
        response.ok = False
        response.status_code = 409
        response.json.return_value = {"error": "AUTH_REQUIRED"}
        env = {
            "F1_OAUTH_BROKER_ENABLED": "true",
            "SUPABASE_SERVICE_ROLE_KEY": "service-key",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "oauth_broker.requests.get", return_value=response
        ):
            with self.assertRaises(oauth_broker.BrokerError) as ctx:
                oauth_broker.token({"id": "client-slug"}, "tiktok")
        self.assertTrue(ctx.exception.auth_required)


if __name__ == "__main__":
    unittest.main()
