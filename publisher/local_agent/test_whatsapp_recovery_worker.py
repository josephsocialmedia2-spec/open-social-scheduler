from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publisher.local_agent import whatsapp_recovery_worker as wa


class WhatsAppRecoveryWorkerTests(unittest.TestCase):
    def test_parse_ios_and_android_messages(self):
        text = (
            "[01/09/26, 09:15:01] Marta Ruffino: IMG-20260901-WA0001.jpg\n"
            "[01/09/26, 09:16:01] Marta Ruffino: testo\n"
            "02/09/26, 18:22 - Marta Ruffino: VID-20260902-WA0002.mp4\n"
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "_chat.txt"
            path.write_text(text, encoding="utf-8")
            messages = wa.parse_chat_file(path, "Europe/Rome")
        self.assertEqual(3, len(messages))
        self.assertEqual("Marta Ruffino", messages[0].sender)
        self.assertEqual(1, messages[0].when.day)
        self.assertEqual(2, messages[2].when.day)

    def test_media_date_from_filename(self):
        value = wa.media_date_from_filename("IMG-20260901-WA0001.jpg", "Europe/Rome")
        self.assertIsNotNone(value)
        self.assertEqual("2026-09-01", value.date().isoformat())

    def test_referenced_media(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / "IMG-20260901-WA0001.jpg"
            message = wa.Message(
                when=wa.datetime(2026, 9, 1, 9, 15, tzinfo=wa.ZoneInfo("Europe/Rome")),
                sender="Marta Ruffino",
                body="IMG-20260901-WA0001.jpg",
            )
            refs = wa.referenced_media([message], [media])
        self.assertIn("img-20260901-wa0001.jpg", refs)


if __name__ == "__main__":
    unittest.main()
