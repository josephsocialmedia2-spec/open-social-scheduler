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
