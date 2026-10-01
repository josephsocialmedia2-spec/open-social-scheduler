import unittest
from pathlib import Path

from publisher import f1_intelligence_worker as worker

ROOT = Path(__file__).resolve().parents[1]


class GraphicCaptionIntelligenceTests(unittest.TestCase):
    def test_clean_graphic_text_deduplicates_lines(self):
        raw = "OFFERTA SPECIALE\n  Torino   e provincia \nOFFERTA SPECIALE\n"
        self.assertEqual(
            worker.clean_graphic_text(raw),
            "OFFERTA SPECIALE\nTorino e provincia",
        )

    def test_media_fingerprint_changes_with_graphic(self):
        a = [{"id": "1", "storage_path": "a.png", "file_size": 100, "mime_type": "image/png", "source": "WEB"}]
        b = [{"id": "1", "storage_path": "a.png", "file_size": 101, "mime_type": "image/png", "source": "WEB"}]
        self.assertNotEqual(worker.graphic_media_fingerprint(a), worker.graphic_media_fingerprint(b))

    def test_caption_is_grounded_in_graphic_text(self):
        client = {"name": "Cliente Demo"}
        item = {"title": "Titolo vecchio", "description": "Descrizione vecchia"}
        graphic = "VALUTAZIONE IMMOBILE\nRichiedi informazioni"
        for platform in worker.CAPTION_PLATFORMS:
            caption = worker.caption_from_graphic(platform, client, item, graphic)
            self.assertIn("VALUTAZIONE IMMOBILE", caption)
            self.assertIn("Richiedi informazioni", caption)

    def test_missing_graphic_falls_back_to_content_text(self):
        item = {
            "title": "Titolo contenuto",
            "description": "Testo disponibile senza grafica",
            "distribution_plan": {},
        }
        result = worker.extract_graphic_text(item, [])
        self.assertEqual(result["source"], "CONTENT_TEXT_FALLBACK")
        self.assertFalse(result["ocr_used"])
        self.assertIn("Testo disponibile senza grafica", result["text"])

    def test_template_noise_is_removed_from_public_caption(self):
        client = {"name": "Real Media Pro"}
        item = {
            "title": "Google Ads intercetta domanda già attiva",
            "description": "Google Ads funziona quando keyword, annuncio e pagina rispondono allo stesso intento.",
        }
        graphic = (
            "F1 SOCIAL INTELLIGENCE - REAL MEDIA PRO\n"
            "ATTRACT\n"
            "Google Ads intercetta\n"
            "m N n\n"
            "domanda gia attiva\n"
            "STRATEGIA : AUTOMAZIONE - CRESCITA\n"
            "Real Media Pro\n"
            "Social Intelligence for real results"
        )
        caption = worker.caption_from_graphic("facebook", client, item, graphic, "GRAPHIC_TEXT")
        self.assertIn("Google Ads intercetta domanda già attiva", caption)
        self.assertIn("keyword, annuncio e pagina", caption)
        self.assertNotIn("m N n", caption)
        self.assertNotIn("ATTRACT", caption)
        self.assertNotIn("STRATEGIA : AUTOMAZIONE", caption)
        self.assertNotIn("Social Intelligence for real results", caption)

    def test_fallback_caption_uses_clean_content_context(self):
        client = {"name": "F1 Immobiliare"}
        item = {
            "title": "Vendere casa: il prezzo è solo il punto di partenza",
            "description": "Una valutazione considera dati, immobile e mercato.",
        }
        caption = worker.caption_from_graphic(
            "facebook",
            client,
            item,
            item["description"],
            "CONTENT_TEXT_FALLBACK",
        )
        self.assertTrue(caption.startswith(item["title"]))
        self.assertIn(item["description"], caption)

    def test_platform_lengths_are_bounded(self):
        client = {"name": "Cliente Demo"}
        item = {"title": "Test"}
        graphic = "TESTO " * 2000
        limits = {
            "instagram": 2200,
            "tiktok": 1800,
            "youtube": 4500,
            "linkedin-page": 3000,
            "pinterest": 800,
            "facebook": 5000,
        }
        for platform, limit in limits.items():
            self.assertLessEqual(len(worker.caption_from_graphic(platform, client, item, graphic)), limit)

    def test_workspace_marks_manual_caption_and_allows_all_clients(self):
        js = (ROOT / "f1-content-hub" / "client-workspace.js").read_text(encoding="utf-8")
        self.assertIn('caption_manual=true', js)
        self.assertIn('caption_source="MANUAL"', js)
        self.assertNotIn('F1 Immobiliare è in modalità manual publish-only', js)
        self.assertNotIn('manualF1', js)
        self.assertIn('graphic_caption&&plan.intelligence.graphic_caption.text', js)

    def test_compact_folder_replaces_verbose_copy(self):
        js = (ROOT / "f1-content-hub" / "client-workspace.js").read_text(encoding="utf-8")
        css = (ROOT / "f1-content-hub" / "client-workspace.css").read_text(encoding="utf-8")
        self.assertIn("intel-folder-mini", js)
        self.assertIn(".intel-folder-mini", css)
        self.assertNotIn("CARTELLA AUTOMATICA CLIENTE", js)
        self.assertNotIn("Il percorso è assegnato dal software", js)
        self.assertNotIn("Nessun intervento necessario: se non modifichi nulla", js)

    def test_workspace_navigation_is_compact(self):
        html = (ROOT / "f1-content-hub" / "index.html").read_text(encoding="utf-8")
        self.assertIn(".workspace-nav .btn{padding:4px 6px;font-size:9px", html)


if __name__ == "__main__":
    unittest.main()
