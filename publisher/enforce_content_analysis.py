#!/usr/bin/env python3
"""Attach and enforce pre-content analysis + Instagram Feed/Reels policy.

Every active-cycle job receives:
- one precise target public;
- one objective;
- one main message;
- real/absent Insights state;
- recent comparable-post context;
- Instagram feed ranking predictions to optimize;
- format-specific constraints for photo/carousel/reel/video;
- mandatory manual approval when data is incomplete.

No best publication time or performance metric is invented.
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


def format_strategy(fmt: str, instagram: dict) -> dict:
    predictions = instagram.get("predictions_to_optimize", {})
    common = {
        "positive_action_probability": predictions.get("positive_action_probability"),
        "skip_probability": predictions.get("skip_probability"),
        "profile_time_after_post": predictions.get("profile_time_after_post"),
        "direct_share_probability": predictions.get("direct_share_probability"),
        "predicted_time_on_post": predictions.get("predicted_time_on_post"),
        "first_post_skip_probability": predictions.get("first_post_skip_probability"),
        "session_continuation_after_first_post": predictions.get("session_continuation_after_first_post"),
    }
    if fmt == "carousel":
        common["carousel_completion"] = predictions.get("carousel_completion")
        common["first_post_over_10_seconds"] = predictions.get("first_post_over_10_seconds")
    if fmt in {"reel", "video"}:
        common["first_post_over_10_seconds"] = predictions.get("first_post_over_10_seconds")
        common["audio_activation_probability"] = predictions.get("audio_activation_probability")
    return common


def reel_rules(instagram: dict) -> dict:
    return {
        "creative_essentials": instagram.get("reels_creative_essentials", {}),
        "sales_rules": instagram.get("reels_for_sales", {}),
        "results_rules": instagram.get("reels_for_results", {}),
        "editing_rules": instagram.get("reels_editing", {}),
        "ai_assisted_rules": instagram.get("ai_assisted_reels", {}),
    }


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

        instagram = ctx.get("instagram", {})
        if not instagram or not instagram.get("predictions_to_optimize"):
            raise RuntimeError(f"Missing Instagram ranking policy for {j.get('id')}")

        fmt = str(j.get("format") or "photo").lower()

        j["analysis_required"] = True
        j["analysis_status"] = ctx.get("analysis_status")
        j["insights_status"] = ctx.get("insights", {}).get("status")
        j["target_public"] = public
        j["post_objective"] = objective
        j["main_message"] = main_message
        j["comparable_previous_posts"] = ctx.get("comparable_previous_posts", [])
        j["quality_gate"] = ctx.get("quality_gate", {})
        j["cta_policy"] = ctx.get("cta_policy", "ONE_OR_NONE_AND_ONLY_IF_OBJECTIVE_REQUIRES_IT")
        j["manual_approval_required"] = True

        j["instagram_policy_required"] = True
        j["instagram_policy_version"] = instagram.get("policy_version")
        j["instagram_ranking_model"] = instagram.get("ranking_model", {})
        j["instagram_prediction_targets"] = format_strategy(fmt, instagram)
        j["instagram_performance_data_status"] = instagram.get("performance_data_status")
        j["instagram_performance_metrics_expected"] = instagram.get("performance_metrics_expected", [])
        j["instagram_gallery_metadata_policy"] = instagram.get("gallery_suggestion_metadata", {})
        j["instagram_format"] = fmt
        j["instagram_format_mix_note"] = (
            "Current production workflow is constrained to static photo jobs; this does not remove carousel/Reels rules from the master policy."
            if fmt == "photo" else "Format-specific policy applied."
        )

        # Common Feed creative constraints derived from the supplied ranking signals.
        j["instagram_creative_constraints"] = {
            "first_visible_unit_must_work_without_context": True,
            "immediate_target_relevance": True,
            "skip_risk_must_be_reviewed": True,
            "visual_subject_immediately_recognizable": True,
            "visual_text_short": True,
            "photo_overlay_text_not_overloaded": True if fmt == "photo" else None,
            "meaningful_positive_action_not_engagement_bait": True,
            "share_value_should_be_natural_not_forced": True,
            "profile_transition_must_match_brand_positioning": True,
            "deliver_value_after_hook": True,
            "no_slow_generic_intro": True,
        }

        if fmt == "carousel":
            j["instagram_carousel_constraints"] = {
                "card_1_requires_precise_reason_to_continue": True,
                "every_card_adds_new_information": True,
                "no_redundant_padding": True,
                "last_card_closes_information_loop_or_single_action": True,
            }
        else:
            j["instagram_carousel_constraints"] = None

        if fmt in {"reel", "video"}:
            j["instagram_reels_policy"] = reel_rules(instagram)
            j["instagram_reels_constraints"] = {
                "vertical_9_16": True,
                "intentional_audio": True,
                "bottom_35_percent_free_of_essential_text_logo": True,
                "primary_message_in_safe_area": True,
                "first_1_3_seconds_clear": True,
                "reason_to_continue_beyond_10_seconds": True,
                "captions_when_useful_for_context_accessibility": True,
                "brand_visible_and_coherent": True,
                "clips_assets_visually_harmonious": True,
                "phone_footage_allowed_if_clear": True,
                "rights_cleared_audio_required": True,
            }
        else:
            j["instagram_reels_policy"] = reel_rules(instagram)
            j["instagram_reels_constraints"] = {"applicable": False, "reason": f"Current format is {fmt}"}

        timing = ctx.get("publication_timing", {})
        j["publication_timing_status"] = timing.get("status")
        j["recommended_publish_day"] = timing.get("day")
        j["recommended_publish_window"] = timing.get("time_window")
        j["scheduled_at_role"] = "production_cycle_only"

        if j["insights_status"] != "AVAILABLE":
            j["publication_time_verified"] = False
            j["approval_note"] = "INSIGHTS NON DISPONIBILI — ANALISI NON COMPLETA. Non usare un orario di pubblicazione inventato."
        else:
            j["publication_time_verified"] = bool(j.get("recommended_publish_day") and j.get("recommended_publish_window"))
            if not j["publication_time_verified"]:
                j["approval_note"] = "Insights disponibili ma fascia pubblico-online non presente: verificare manualmente prima della programmazione."

        j["prepublish_checklist"] = {
            "public_clear": True,
            "single_objective": True,
            "main_message_clear": True,
            "creative_sharp": None,
            "brand_coherent": None,
            "clean_color_scheme": None,
            "recognizable_image": None,
            "short_visual_text": None,
            "caption_has_no_unnecessary_elements": None,
            "meaningful_for_target": True,
            "cta_connected_to_objective_or_omitted": True,
            "question_is_relevant_if_present": True,
            "sufficiently_distinct_from_recent_posts": None,
            "skip_risk_reviewed": None,
            "dwell_time_value_reviewed": None,
            "direct_share_value_reviewed": None,
            "profile_visit_value_reviewed": None,
            "format_specific_rules_passed": None,
            "carousel_completion_logic_passed": None if fmt != "carousel" else False,
            "reel_9_16_safe_area_audio_passed": None if fmt not in {"reel", "video"} else False,
        }

    q["analysis_policy"] = "ANALISI PRIMA DELLA CREAZIONE DEL POST + full Instagram Feed/Reels prediction policy"
    q["instagram_distribution_policy"] = "publisher/instagram_distribution_policy.json"
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ANALYSIS + INSTAGRAM POLICY ENFORCED on {len(jobs)} jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
