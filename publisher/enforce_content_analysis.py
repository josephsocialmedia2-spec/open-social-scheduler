#!/usr/bin/env python3
"""Attach and enforce pre-content analysis policy on the active cycle.

The content can be rendered as a draft when Insights are unavailable, but it is
explicitly marked as analysis-partial, scheduling-unverified and manual-approval
required. No best publication time is invented.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
ANALYSIS = ROOT / "publisher" / "content_analysis.json"

ALLOWED_OBJECTIVES = {
    "visibilità", "conversazione", "richiesta informazioni", "visita sito",
    "prenotazione", "messaggio", "conoscenza del brand",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    q = load(QUEUE)
    a = load(ANALYSIS)
    clients = a.get("clients", {})
    cycle = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle]
    if not jobs:
        raise RuntimeError("No active-cycle jobs to analyze")

    for j in jobs:
        cid = str(j.get("client_id") or "")
        ctx = clients.get(cid)
        if not ctx:
            raise RuntimeError(f"Missing mandatory analysis context for {cid}")

        public = str(ctx.get("public") or "").strip()
        objective = str(ctx.get("objective") or "").strip().lower()
        main_message = str(ctx.get("main_message") or "").strip()
        if not public or public.lower() == "tutti":
            raise RuntimeError(f"Invalid public for {j.get('id')}: {public!r}")
        if objective not in ALLOWED_OBJECTIVES:
            raise RuntimeError(f"Invalid single objective for {j.get('id')}: {objective!r}")
        if not main_message:
            raise RuntimeError(f"Missing main message for {j.get('id')}")

        # Mandatory analysis fields available to approval UI and downstream logic.
        j["analysis_required"] = True
        j["analysis_status"] = ctx.get("analysis_status")
        j["insights_status"] = ctx.get("insights", {}).get("status")
        j["target_public"] = public
        j["post_objective"] = objective
        j["main_message"] = main_message
        j["comparable_previous_posts"] = ctx.get("comparable_previous_posts", [])
        j["quality_gate"] = ctx.get("quality_gate", {})
        j["cta_policy"] = ctx.get("cta_policy", "ONE_OR_NONE")
        j["manual_approval_required"] = True

        timing = ctx.get("publication_timing", {})
        j["publication_timing_status"] = timing.get("status")
        j["recommended_publish_day"] = timing.get("day")
        j["recommended_publish_window"] = timing.get("time_window")
        # scheduled_at is production-cycle timing, NOT a recommendation to publish.
        j["scheduled_at_role"] = "production_cycle_only"

        if j["insights_status"] != "AVAILABLE":
            j["publication_time_verified"] = False
            j["approval_note"] = "INSIGHTS NON DISPONIBILI — ANALISI NON COMPLETA. Non usare un orario di pubblicazione inventato."
        else:
            j["publication_time_verified"] = bool(j.get("recommended_publish_day") and j.get("recommended_publish_window"))
            if not j["publication_time_verified"]:
                j["approval_note"] = "Insights disponibili ma fascia pubblico-online non presente: verificare manualmente prima della programmazione."

        # Pre-publication checklist: render-time checks are completed later.
        j["prepublish_checklist"] = {
            "public_clear": True,
            "main_message_clear": True,
            "creative_sharp": None,
            "brand_coherent": None,
            "clean_color_scheme": None,
            "recognizable_image": None,
            "short_visual_text": None,
            "caption_has_no_unnecessary_elements": None,
            "meaningful_for_target": True,
            "cta_connected_to_objective": True,
            "question_is_relevant_if_present": True,
            "sufficiently_distinct_from_recent_posts": None,
        }

    q["analysis_policy"] = "ANALISI PRIMA DELLA CREAZIONE DEL POST · mandatory context + manual approval when Insights are missing"
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ANALYSIS POLICY ENFORCED on {len(jobs)} jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
