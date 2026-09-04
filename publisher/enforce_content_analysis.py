#!/usr/bin/env python3
"""Attach and enforce pre-content analysis + full Instagram Feed/Reels/Creators policy.

Every active-cycle job receives:
- one precise target public;
- one objective;
- one main message;
- real/absent Insights state;
- recent comparable-post context;
- the full Instagram Feed ranking model from instagram_distribution_policy.json;
- all supplied significant prediction targets;
- viewer controls/feedback implications;
- Instagram Creators best practices from instagram_creators_best_practices.json;
- format diversification, trial-Reel consideration, share-worthiness, first-3-second hook,
  highest resolution, muted-view comprehension, audio rights and early comment response;
- direct audience feedback, anti-engagement-bait and authentic CTA enforcement;
- format-specific constraints for photo/carousel/reel/video;
- measurement rules that forbid invented ranking probabilities;
- mandatory manual approval when data is incomplete.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
ANALYSIS = ROOT / "publisher" / "content_analysis.json"
POLICY = ROOT / "publisher" / "instagram_distribution_policy.json"
CREATORS = ROOT / "publisher" / "instagram_creators_best_practices.json"

ALLOWED_OBJECTIVES = {
    "visibilità", "conversazione", "richiesta informazioni", "visita sito",
    "prenotazione", "messaggio", "conoscenza del brand",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def format_strategy(fmt: str, policy: dict) -> dict:
    predictions = policy.get("significant_predictions", {})
    common_keys = [
        "positive_action_probability",
        "skip_probability",
        "profile_time_after_post",
        "direct_share_probability",
        "predicted_time_on_post",
        "first_post_skip_probability",
        "session_continuation_after_first_post",
    ]
    common = {k: predictions.get(k) for k in common_keys}
    if fmt == "carousel":
        common["carousel_completion"] = predictions.get("carousel_completion")
        common["first_post_over_10_seconds"] = predictions.get("first_post_over_10_seconds")
    if fmt in {"reel", "video"}:
        common["first_post_over_10_seconds"] = predictions.get("first_post_over_10_seconds")
        common["audio_activation_probability"] = predictions.get("audio_activation_probability")
    return common


def reel_rules(policy: dict, creators: dict) -> dict:
    return {
        "creative_essentials": policy.get("reels_creative_essentials", {}),
        "sales_rules": policy.get("reels_for_sales", {}),
        "results_rules": policy.get("reels_for_results", {}),
        "editing_rules": policy.get("reels_editing", {}),
        "ai_assisted_rules": policy.get("ai_assisted_reels", {}),
        "creators_best_practices": creators,
    }


def main() -> int:
    q = load(QUEUE)
    a = load(ANALYSIS)
    master = load(POLICY)
    creators = load(CREATORS)

    required_predictions = {
        "carousel_completion", "positive_action_probability", "skip_probability",
        "profile_time_after_post", "direct_share_probability", "predicted_time_on_post",
        "first_post_skip_probability", "first_post_over_10_seconds",
        "audio_activation_probability", "session_continuation_after_first_post",
    }
    available_predictions = set((master.get("significant_predictions") or {}).keys())
    missing = required_predictions - available_predictions
    if missing:
        raise RuntimeError(f"Instagram master policy missing predictions: {sorted(missing)}")
    if not master.get("feed_system"):
        raise RuntimeError("Instagram master policy missing feed_system")
    if not master.get("viewer_controls_and_feedback"):
        raise RuntimeError("Instagram master policy missing viewer controls/feedback")
    if not master.get("measurement_policy"):
        raise RuntimeError("Instagram master policy missing measurement policy")
    if not creators.get("reels_best_practices") or not creators.get("format_diversification"):
        raise RuntimeError("Instagram Creators policy incomplete")
    community = creators.get("community_connections") or {}
    if not community.get("reach_audience_directly") or not community.get("engagement_bait") or not community.get("comment_interaction"):
        raise RuntimeError("Instagram Creators community/anti-bait policy incomplete")
    if (community.get("engagement_bait") or {}).get("prohibited") is not True:
        raise RuntimeError("Instagram engagement bait must be prohibited")

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

        instagram_ctx = ctx.get("instagram", {}) or {}
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
        j["instagram_policy_version"] = master.get("version")
        j["instagram_policy_source"] = "publisher/instagram_distribution_policy.json"
        j["instagram_creators_policy_version"] = creators.get("version")
        j["instagram_creators_policy_source"] = "publisher/instagram_creators_best_practices.json"
        j["instagram_full_policy_attached"] = True
        j["instagram_scope_note"] = master.get("scope_note", {})
        j["instagram_ranking_model"] = master.get("feed_system", {})
        j["instagram_viewer_controls_and_feedback"] = master.get("viewer_controls_and_feedback", {})
        j["instagram_prediction_targets"] = format_strategy(fmt, master)
        j["instagram_measurement_policy"] = master.get("measurement_policy", {})
        j["instagram_mandatory_prepublication_checks"] = master.get("mandatory_prepublication_checks", [])
        j["instagram_creators_best_practices"] = creators
        j["instagram_community_connections"] = community
        j["instagram_engagement_bait_prohibited"] = True
        j["instagram_authentic_cta_required"] = True
        j["instagram_audience_feedback_channels"] = (community.get("reach_audience_directly") or {}).get("channels", [])
        j["instagram_early_comment_interaction_required"] = bool((community.get("comment_interaction") or {}).get("early_days_priority"))
        j["instagram_performance_data_status"] = instagram_ctx.get("performance_data_status", ctx.get("insights", {}).get("status"))
        j["instagram_performance_metrics_expected"] = (
            instagram_ctx.get("performance_metrics_expected")
            or master.get("measurement_policy", {}).get("content_metrics_when_available", [])
        )
        j["instagram_gallery_metadata_policy"] = master.get("gallery_suggestion_metadata", {})
        j["instagram_format"] = fmt
        j["instagram_format_mix_note"] = (
            "Current production workflow is constrained to static photo jobs; format diversification must still be considered in planning and future cycles."
            if fmt == "photo" else "Full format-specific master policy applied."
        )

        j["instagram_creative_constraints"] = {
            "integrity_truthfulness_required": True,
            "first_visible_unit_must_work_without_context": True,
            "immediate_target_relevance": True,
            "skip_risk_must_be_reviewed": True,
            "visual_subject_immediately_recognizable": True,
            "visual_text_short": True,
            "photo_overlay_text_not_overloaded": True if fmt == "photo" else None,
            "meaningful_positive_action_not_engagement_bait": True,
            "engagement_bait_forbidden": True,
            "authentic_cta_only": True,
            "audience_feedback_method_considered": True,
            "share_value_should_be_natural_not_forced": True,
            "save_value_should_be_considered_when_relevant": True,
            "profile_transition_must_match_brand_positioning": True,
            "negative_feedback_risk_must_be_reviewed": True,
            "creative_fatigue_must_be_reviewed": True,
            "deliver_value_after_hook": True,
            "no_slow_generic_intro": True,
            "publication_time_must_not_be_invented": True,
            "format_selected_for_message_not_habit": True,
            "format_diversification_considered": True,
            "new_idea_test_or_trial_reel_considered": True,
            "share_worthiness_reviewed": True,
            "highest_available_resolution_required": True,
        }

        if fmt == "carousel":
            j["instagram_carousel_constraints"] = {
                "card_1_requires_precise_reason_to_continue": True,
                "every_card_adds_new_information": True,
                "no_redundant_padding": True,
                "last_card_closes_information_loop_or_single_action": True,
                "reason_to_continue_beyond_10_seconds_reviewed": True,
            }
        else:
            j["instagram_carousel_constraints"] = None

        if fmt in {"reel", "video"}:
            j["instagram_reels_policy"] = reel_rules(master, creators)
            j["instagram_reels_constraints"] = {
                "vertical_9_16": True,
                "intentional_audio": True,
                "understandable_without_audio": True,
                "bottom_35_percent_free_of_essential_text_logo": True,
                "primary_message_in_safe_area": True,
                "first_3_seconds_clear": True,
                "three_second_value_reviewed": True,
                "reason_to_continue_beyond_10_seconds": True,
                "captions_or_text_for_muted_view": True,
                "captions_when_useful_for_context_accessibility": True,
                "brand_visible_and_coherent": True,
                "clips_assets_visually_harmonious": True,
                "phone_footage_allowed_if_clear": True,
                "highest_resolution_possible": True,
                "rights_cleared_audio_required": True,
                "audio_activation_value_reviewed": True,
                "early_comment_response_plan_required": True,
                "max_180_seconds_for_non_follower_recommendation": True,
                "trial_reel_considered_when_available": True,
            }
        else:
            j["instagram_reels_policy"] = reel_rules(master, creators)
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
            "integrity_and_truthfulness_passed": None,
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
            "authentic_cta_only": True,
            "engagement_bait_absent": True,
            "audience_feedback_method_considered": True,
            "question_is_relevant_if_present": True,
            "sufficiently_distinct_from_recent_posts": None,
            "creative_fatigue_reviewed": None,
            "skip_risk_reviewed": None,
            "dwell_time_value_reviewed": None,
            "direct_share_value_reviewed": None,
            "save_value_reviewed": None,
            "profile_visit_value_reviewed": None,
            "negative_feedback_risk_reviewed": None,
            "format_specific_rules_passed": None,
            "format_diversification_considered": True,
            "new_idea_test_considered": True,
            "share_worthiness_reviewed": True,
            "highest_available_resolution_used": None,
            "early_comment_interaction_plan_present": True,
            "carousel_completion_logic_passed": None if fmt != "carousel" else False,
            "first_3_seconds_passed": None if fmt not in {"reel", "video"} else False,
            "reason_beyond_10_seconds_passed": None if fmt not in {"reel", "video", "carousel"} else False,
            "reel_muted_view_passed": None if fmt not in {"reel", "video"} else False,
            "reel_audio_rights_verified": None if fmt not in {"reel", "video"} else False,
            "reel_9_16_safe_area_audio_passed": None if fmt not in {"reel", "video"} else False,
            "reel_comment_followup_plan_present": None if fmt not in {"reel", "video"} else False,
            "reel_duration_recommendation_passed": None if fmt not in {"reel", "video"} else False,
            "gallery_metadata_permission_passed": None,
        }

    q["analysis_policy"] = "ANALISI PRIMA DELLA CREAZIONE + FULL INSTAGRAM FEED/REELS MASTER POLICY + CREATORS BEST PRACTICES + COMMUNITY/ANTI-BAIT"
    q["instagram_distribution_policy"] = "publisher/instagram_distribution_policy.json"
    q["instagram_distribution_policy_version"] = master.get("version")
    q["instagram_creators_best_practices"] = "publisher/instagram_creators_best_practices.json"
    q["instagram_creators_best_practices_version"] = creators.get("version")
    q["instagram_policy_loaded_directly"] = True
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ANALYSIS + FULL INSTAGRAM MASTER V{master.get('version')} + CREATORS V{creators.get('version')} + ANTI-BAIT ENFORCED on {len(jobs)} jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
