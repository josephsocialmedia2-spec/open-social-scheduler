from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from publisher.chatgpt_query_runner.core import (
    advance_after_completed,
    blank_state,
    build_prompt,
    create_run,
    deterministic_image_name,
    finalize_run,
    get_or_create_run,
    load_state,
    migrate_state,
    normalize_query,
    save_state,
    transition,
)


QUERIES = [
    {"id": "Q1", "query": "immobili in vendita a Susa"},
    {"id": "Q2", "query": "case in vendita a Susa"},
    {"id": "Q3", "query": "lavoro agenzia immobiliare Susa prima esperienza"},
    {"id": "Q4", "query": "appartamenti in vendita a Susa"},
]


class CoreTests(unittest.TestCase):
    def test_prompt_exact(self):
        self.assertEqual(
            build_prompt("immobili in vendita a Susa"),
            "Genera un'immagine ultrarealistica, cerchiamo immobili in vendita a Susa.",
        )

    def test_prompt_normalizes_only_whitespace(self):
        self.assertEqual(normalize_query("  immobili   in vendita\n a Susa  "), "immobili in vendita a Susa")
        self.assertEqual(
            build_prompt("  immobili   in vendita\n a Susa  "),
            "Genera un'immagine ultrarealistica, cerchiamo immobili in vendita a Susa.",
        )

    def test_legacy_completed_is_not_trusted(self):
        old = {"next_index": 3, "completed": [{"id": "Q1", "query": "x"}]}
        migrated = migrate_state(old)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["next_index"], 0)
        self.assertEqual(len(migrated["legacy_unverified"]), 1)
        self.assertIsNone(migrated["active_run"])

    def test_create_run_builds_four_prompts(self):
        state = blank_state()
        run = create_run(state, QUERIES, 4, now=datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc))
        self.assertEqual(len(run["jobs"]), 4)
        self.assertTrue(all(job["status"] == "QUERY_CARICATA" for job in run["jobs"]))
        self.assertEqual(
            run["jobs"][2]["prompt"],
            "Genera un'immagine ultrarealistica, cerchiamo lavoro agenzia immobiliare Susa prima esperienza.",
        )

    def test_fresh_run_preserves_previous_active_run_in_history(self):
        state = blank_state()
        old_run = create_run(state, QUERIES, 4)
        old_id = old_run["run_id"]
        old_run["jobs"][0]["status"] = "ERRORE"
        new_run = create_run(state, QUERIES, 1)
        self.assertNotEqual(new_run["run_id"], old_id)
        self.assertEqual(state["runs"][-1]["run_id"], old_id)
        self.assertEqual(state["runs"][-1]["status"], "ANNULLATO")
        self.assertIn("fresh-run", state["runs"][-1]["error"])

    def test_next_index_cannot_advance_before_completed(self):
        state = blank_state()
        run = create_run(state, QUERIES, 1)
        job = run["jobs"][0]
        with self.assertRaises(ValueError):
            advance_after_completed(state, job, len(QUERIES))
        transition(job, "COMPLETED")
        with self.assertRaises(ValueError):
            advance_after_completed(state, job, len(QUERIES))

    def test_next_index_advances_only_with_saved_image(self):
        state = blank_state()
        run = create_run(state, QUERIES, 1)
        job = run["jobs"][0]
        transition(job, "IMMAGINE_SALVATA", image_path="publisher/final_assets/chatgpt_generated/x.png")
        transition(job, "COMPLETED")
        advance_after_completed(state, job, len(QUERIES))
        self.assertEqual(state["next_index"], 1)

    def test_partial_run_is_resumed(self):
        state = blank_state()
        run = create_run(state, QUERIES, 4)
        run["status"] = "PARZIALE"
        run["jobs"][0]["image_path"] = "x.png"
        run["jobs"][0]["status"] = "COMPLETED"
        resumed = get_or_create_run(state, QUERIES, 4)
        self.assertEqual(resumed["run_id"], run["run_id"])
        self.assertEqual(resumed["status"], "RUNNING")

    def test_finalize_requires_all_images_for_ready(self):
        state = blank_state()
        run = create_run(state, QUERIES, 2)
        for job in run["jobs"]:
            job["submitted_at"] = "2026-09-06T23:00:00+02:00"
            job["generation_completed_at"] = "2026-09-06T23:01:00+02:00"
            job["image_path"] = f"{job['query_id']}.png"
            job["status"] = "COMPLETED"
        self.assertEqual(finalize_run(state), "GRAFICHE_PRONTE")

    def test_finalize_partial_when_only_one_succeeds(self):
        state = blank_state()
        run = create_run(state, QUERIES, 2)
        job = run["jobs"][0]
        job["submitted_at"] = "x"
        job["generation_completed_at"] = "x"
        job["image_path"] = "x.png"
        job["status"] = "COMPLETED"
        self.assertEqual(finalize_run(state), "PARZIALE")

    def test_deterministic_name(self):
        self.assertEqual(
            deterministic_image_name("20260906", 1, "immobili in vendita a Susa"),
            "20260906_001_immobili-in-vendita-a-susa.png",
        )

    def test_atomic_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = blank_state()
            create_run(state, QUERIES, 1)
            save_state(path, state)
            loaded = load_state(path)
            self.assertEqual(loaded["version"], 2)
            self.assertEqual(loaded["active_run"]["jobs"][0]["query_id"], "Q1")


if __name__ == "__main__":
    unittest.main()
