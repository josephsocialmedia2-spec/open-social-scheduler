#!/usr/bin/env python3
"""Mandatory analysis context before content production.

Implements the operational rules supplied by the user:
- inspect available Insights data before creation;
- compare recent comparable posts;
- choose one precise audience;
- choose one primary objective;
- define one main message;
- use real audience-online data for publication timing when available;
- never invent missing Meta Insights.

This script does not publish. If Meta Insights are unavailable it records that
explicitly and forces manual approval / unverified scheduling rather than
inventing demographics, interests, performance or best posting times.
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


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def recent_comparable(queue: dict, client_id: str, limit: int = 8) -> list[dict]:
    rows = [j for j in queue.get("jobs", []) if j.get("client_id") == client_id]
    rows.sort(key=lambda j: str(j.get("scheduled_at") or ""), reverse=True)
    out = []
    seen = set()
    for j in rows:
        title = str(j.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append({
            "title": title,
            "format": j.get("format"),
            "category": j.get("category"),
            "visual_source": j.get("visual_source"),
            "caption": str(j.get("caption") or "")[:500],
            "likes": None,
            "comments": None,
            "shares": None,
            "cta_clicks": None,
            "metrics_status": "NOT_AVAILABLE_IN_QUEUE",
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


def analyze_client(client: dict, queue: dict) -> dict:
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
        top_posts = insights.get("top_posts") or []
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
        "cta_policy": "ONE_OR_NONE",
        "quality_gate": {
            "sharp_media_required": True,
            "brand_coherence_required": True,
            "recognizable_subject_required": True,
            "short_visual_text_required": True,
            "single_main_idea_required": True,
            "relevant_question_only": True,
        },
        "publication_timing": {
            "status": schedule_status,
            "day": recommended_day,
            "time_window": recommended_window,
            "rule": "Use Page Insights audience-online data. Never invent a best time.",
        },
        "manual_approval_required": True,
    }


def main() -> int:
    queue = load(QUEUE, {"jobs": []})
    clients = []
    for path in sorted(CLIENT_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = load(path, {})
        if data.get("active", False):
            clients.append(data)

    result = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "policy": "ANALISI PRIMA DELLA CREAZIONE DEL POST",
        "clients": {c["id"]: analyze_client(c, queue) for c in clients},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for cid, row in result["clients"].items():
        print(
            f"ANALYSIS {cid}: status={row['analysis_status']} insights={row['insights']['status']} "
            f"public={row['public']} objective={row['objective']} timing={row['publication_timing']['status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
