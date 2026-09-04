#!/usr/bin/env python3
"""Mandatory analysis context before content production.

Implements the operational rules supplied by the user and the Instagram Feed /
Reels guidance stored in instagram_distribution_policy.json plus the Instagram
Creators best practices stored in instagram_creators_best_practices.json.

Rules:
- inspect available Insights before creation;
- compare recent comparable posts;
- choose one precise audience;
- choose one primary objective;
- define one main message;
- evaluate Instagram ranking predictions/signals, not just likes;
- consider trial Reels, format diversification, share-worthiness, first-3-second hooks,
  highest-resolution media, muted-view comprehension, audio rights and early comment response;
- use real audience-online data for timing when available;
- never invent missing Insights or performance data;
- keep format-specific Feed/Reels requirements available downstream.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "publisher"
QUEUE = PUBLISHER / "queue.json"
CLIENT_DIR = PUBLISHER / "clients"
INSIGHTS_DIR = PUBLISHER / "insights"
OUT = PUBLISHER / "content_analysis.json"
IG_POLICY = PUBLISHER / "instagram_distribution_policy.json"
IG_CREATORS = PUBLISHER / "instagram_creators_best_practices.json"


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def recent_comparable(queue: dict, client_id: str, limit: int = 12) -> list[dict]:
    rows = [j for j in queue.get("jobs", []) if j.get("client_id") == client_id]
    rows.sort(key=lambda j: str(j.get("scheduled_at") or ""), reverse=True)
    out = []
    seen = set()
    for j in rows:
        title = str(j.get("title") or "").strip()
        key = (title, str(j.get("format") or ""), str(j.get("category") or ""))
        if not title or key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "format": j.get("format"),
            "category": j.get("category"),
            "visual_source": j.get("visual_source"),
            "caption": str(j.get("caption") or "")[:700],
            "likes": j.get("likes"),
            "comments": j.get("comments"),
            "shares": j.get("shares"),
            "saves": j.get("saves"),
            "cta_clicks": j.get("cta_clicks"),
            "profile_visits": j.get("profile_visits"),
            "direct_shares": j.get("direct_shares"),
            "dwell_time_seconds": j.get("dwell_time_seconds"),
            "skip_rate": j.get("skip_rate"),
            "carousel_completion_rate": j.get("carousel_completion_rate"),
            "average_watch_time_seconds": j.get("average_watch_time_seconds"),
            "three_second_view_rate": j.get("three_second_view_rate"),
            "ten_second_view_rate": j.get("ten_second_view_rate"),
            "audio_on_rate": j.get("audio_on_rate"),
            "metrics_status": j.get("metrics_status") or "NOT_AVAILABLE_IN_QUEUE",
        })
        if len(out) >= limit:
            break
    return out


def defaults_for(client: dict) -> tuple[str, str, str]:
    cid = str(client.get("id") or "")
    if cid == "f1-immobiliare":
        audience = "Proprietari di immobili residenziali in Valle di Susa che stanno valutando la vendita o vogliono conoscere il valore reale dell'immobile"
        objective = "richiesta informazioni"
        message = "Prima di vendere casa, il valore va verificato con dati, comparabili, microzona e domanda reale."
    elif cid == "real-media-pro":
        audience = "Imprese e commercianti che vogliono migliorare sito, ecommerce e conversione digitale"
        objective = "richiesta informazioni"
        message = "Un sito efficace deve rendere più semplice capire l'offerta e arrivare all'azione."
    else:
        audience = "Potenziali clienti coerenti con il posizionamento del brand"
        objective = "conoscenza del brand"
        message = str(client.get("editorial", {}).get("master_line") or client.get("campaign", {}).get("name") or "Messaggio principale del brand")
    return audience, objective, message


def normalize_top_posts(insights: dict | None) -> list[dict]:
    if not isinstance(insights, dict):
        return []
    rows = insights.get("top_posts") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "type": row.get("type") or row.get("format"),
            "creative": row.get("creative") or row.get("media"),
            "topic": row.get("topic") or row.get("argument"),
            "message": row.get("message"),
            "likes": row.get("likes"),
            "comments": row.get("comments"),
            "shares": row.get("shares"),
            "saves": row.get("saves"),
            "cta_clicks": row.get("cta_clicks"),
            "profile_visits": row.get("profile_visits"),
            "direct_shares": row.get("direct_shares"),
            "dwell_time_seconds": row.get("dwell_time_seconds"),
            "skip_rate": row.get("skip_rate"),
            "carousel_completion_rate": row.get("carousel_completion_rate"),
            "average_watch_time_seconds": row.get("average_watch_time_seconds"),
            "three_second_view_rate": row.get("three_second_view_rate"),
            "ten_second_view_rate": row.get("ten_second_view_rate"),
            "audio_on_rate": row.get("audio_on_rate"),
        })
    return out


def instagram_analysis(policy: dict, creators: dict, insights: dict | None) -> dict:
    available = isinstance(insights, dict)
    return {
        "policy_version": policy.get("version"),
        "creators_policy_version": creators.get("version"),
        "ranking_model": {
            "inventory": policy.get("feed_system", {}).get("inventory"),
            "signals": policy.get("feed_system", {}).get("signals"),
            "predictions": policy.get("feed_system", {}).get("predictions"),
            "ranking_score": policy.get("feed_system", {}).get("ranking_score"),
        },
        "predictions_to_optimize": policy.get("significant_predictions", {}),
        "gallery_suggestion_metadata": policy.get("gallery_suggestion_metadata", {}),
        "reels_creative_essentials": policy.get("reels_creative_essentials", {}),
        "reels_for_sales": policy.get("reels_for_sales", {}),
        "reels_for_results": policy.get("reels_for_results", {}),
        "reels_editing": policy.get("reels_editing", {}),
        "ai_assisted_reels": policy.get("ai_assisted_reels", {}),
        "mandatory_prepublication_checks": policy.get("mandatory_prepublication_checks", []),
        "creators_best_practices": creators,
        "performance_data_status": "AVAILABLE" if available else "NOT_AVAILABLE",
        "performance_metrics_expected": [
            "likes", "comments", "shares", "saves", "cta_clicks", "profile_visits",
            "direct_shares", "dwell_time_seconds", "skip_rate", "carousel_completion_rate",
            "average_watch_time_seconds", "three_second_view_rate", "ten_second_view_rate", "audio_on_rate",
        ],
        "rule": "Use actual account/page data when present. Never fabricate ranking performance, watch-time, skip, share, save, profile-visit or audio metrics.",
    }


def analyze_client(client: dict, queue: dict, policy: dict, creators: dict) -> dict:
    cid = str(client.get("id") or "")
    insights_path = INSIGHTS_DIR / f"{cid}.json"
    insights = load(insights_path, None)
    audience, objective, message = defaults_for(client)

    if isinstance(insights, dict):
        status = "AVAILABLE"
        audience_data = {
            "provenance": insights.get("provenance"),
            "age": insights.get("age"),
            "interests": insights.get("interests"),
            "page_actions": insights.get("page_actions"),
            "cta_clicks": insights.get("cta_clicks"),
        }
        top_posts = normalize_top_posts(insights)
        online = insights.get("audience_online") or {}
        recommended_day = online.get("day")
        recommended_window = online.get("time_window")
        schedule_status = "DATA_DRIVEN" if recommended_day and recommended_window else "INSIGHTS_AVAILABLE_BUT_NO_ONLINE_WINDOW"
    else:
        status = "NOT_AVAILABLE"
        audience_data = {
            "provenance": None,
            "age": None,
            "interests": None,
            "page_actions": None,
            "cta_clicks": None,
        }
        top_posts = []
        recommended_day = None
        recommended_window = None
        schedule_status = "UNVERIFIED_NO_INSIGHTS"

    comparable = recent_comparable(queue, cid)
    return {
        "client_id": cid,
        "analysis_status": "COMPLETE" if status == "AVAILABLE" else "PARTIAL_INSIGHTS_MISSING",
        "insights": {
            "status": status,
            "source_file": str(insights_path.relative_to(ROOT)) if insights_path.exists() else None,
            "audience": audience_data,
            "top_posts": top_posts,
        },
        "comparable_previous_posts": comparable,
        "public": audience,
        "objective": objective,
        "main_message": message,
        "cta_policy": "ONE_OR_NONE_AND_ONLY_IF_OBJECTIVE_REQUIRES_IT",
        "quality_gate": {
            "sharp_media_required": True,
            "brand_coherence_required": True,
            "recognizable_subject_required": True,
            "short_visual_text_required": True,
            "single_main_idea_required": True,
            "relevant_question_only": True,
            "skip_risk_review_required": True,
            "dwell_time_value_review_required": True,
            "direct_share_value_review_required": True,
            "profile_visit_value_review_required": True,
            "format_specific_rules_required": True,
            "share_worthiness_review_required": True,
            "format_diversification_review_required": True,
            "first_three_seconds_or_first_unit_review_required": True,
            "highest_resolution_required": True,
            "muted_view_comprehension_required_for_video": True,
            "audio_rights_review_required_if_audio": True,
            "early_comment_response_plan_required_for_reels": True,
        },
        "instagram": instagram_analysis(policy, creators, insights),
        "publication_timing": {
            "status": schedule_status,
            "day": recommended_day,
            "time_window": recommended_window,
            "rule": "Use actual Page/Instagram Insights audience-online data. Never invent a best time.",
        },
        "manual_approval_required": True,
    }


def main() -> int:
    queue = load(QUEUE, {"jobs": []})
    policy = load(IG_POLICY, {})
    creators = load(IG_CREATORS, {})
    if not policy:
        raise RuntimeError("Missing publisher/instagram_distribution_policy.json")
    if not creators:
        raise RuntimeError("Missing publisher/instagram_creators_best_practices.json")

    clients = []
    for path in sorted(CLIENT_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = load(path, {})
        if data.get("active", False):
            clients.append(data)

    result = {
        "version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "policy": "ANALISI PRIMA DELLA CREAZIONE DEL POST + INSTAGRAM FEED/REELS + INSTAGRAM CREATORS BEST PRACTICES",
        "instagram_policy_file": str(IG_POLICY.relative_to(ROOT)),
        "instagram_creators_policy_file": str(IG_CREATORS.relative_to(ROOT)),
        "clients": {c["id"]: analyze_client(c, queue, policy, creators) for c in clients},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for cid, row in result["clients"].items():
        print(
            f"ANALYSIS {cid}: status={row['analysis_status']} insights={row['insights']['status']} "
            f"public={row['public']} objective={row['objective']} timing={row['publication_timing']['status']} "
            f"ig_policy={row['instagram']['policy_version']} creators_policy={row['instagram']['creators_policy_version']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
