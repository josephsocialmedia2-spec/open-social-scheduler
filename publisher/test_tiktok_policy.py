from __future__ import annotations

import unittest

import direct_api_publish as mod


class TikTokPolicyTests(unittest.TestCase):
    def creator(self, **overrides):
        base = {
            "creator_nickname": "Tester",
            "creator_username": "tester",
            "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
            "comment_disabled": False,
            "duet_disabled": False,
            "stitch_disabled": False,
            "max_video_post_duration_sec": 180,
        }
        base.update(overrides)
        return base

    def settings(self, **overrides):
        base = {
            "mode": "DIRECT_POST",
            "privacy_level": "SELF_ONLY",
            "allow_comment": False,
            "allow_duet": False,
            "allow_stitch": False,
            "commercial_content": False,
            "your_brand": False,
            "branded_content": False,
            "caption": "Demo",
            "consent_confirmed": True,
        }
        base.update(overrides)
        return base

    def test_direct_post_requires_explicit_consent(self):
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(
                self.settings(consent_confirmed=False),
                self.creator(),
                30,
            )

    def test_privacy_must_be_returned_by_creator_info(self):
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(
                self.settings(privacy_level="NOT_ALLOWED"),
                self.creator(),
                30,
            )

    def test_no_interaction_can_override_creator_privacy(self):
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(
                self.settings(allow_comment=True),
                self.creator(comment_disabled=True),
                30,
            )

    def test_branded_content_cannot_be_private(self):
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(
                self.settings(
                    commercial_content=True,
                    branded_content=True,
                    privacy_level="SELF_ONLY",
                ),
                self.creator(),
                30,
            )

    def test_duration_is_revalidated(self):
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(self.settings(), self.creator(max_video_post_duration_sec=15), 20)

    def test_draft_mode_does_not_require_privacy(self):
        mod.tiktok_validate_settings(
            self.settings(mode="DRAFT_UPLOAD", privacy_level=""),
            self.creator(),
            20,
        )

    def test_caption_uses_utf16_limit(self):
        self.assertEqual(mod.tiktok_utf16_units("abc"), 3)
        self.assertEqual(mod.tiktok_utf16_units("😀"), 2)
        with self.assertRaises(mod.PlatformReviewRequired):
            mod.tiktok_validate_settings(
                self.settings(caption="😀" * 1101),
                self.creator(),
                20,
            )

    def test_chunk_plan_stays_under_tiktok_limit(self):
        chunk, count = mod.tiktok_chunk_plan(200 * 1024 * 1024)
        self.assertLessEqual(chunk, 64 * 1024 * 1024)
        self.assertGreater(count, 1)


if __name__ == "__main__":
    unittest.main()
