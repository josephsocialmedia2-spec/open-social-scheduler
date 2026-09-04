#!/usr/bin/env python3
"""Automated producer-side gate for F1 qualified-seller content.

The browser Ranking Gate is a human audit UI. This script is the GitHub-side
counterpart: it rejects duplicate, incoherent or weakly-qualified assets before
rendering. It never predicts Instagram's internal score.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
FEEDBACK = ROOT / "publisher" / "gate_feedback.json"

SELLER_TERMS = {"vendere", "vendita", "proprietari", "proprietario", "casa", "immobile", "valutazione"}
BUYER_ONLY = {"cerco casa", "cerco affitto", "affitto cercasi", "inquilino"}
BAIT = {
    "metti like", "lascia un like", "tagga un amico", "tagga 3 amici",
    "condividi se sei d'accordo", "commenta sì", "scrivi sì nei commenti",
}
REQUIRED_QUALIFICATION = {"comune", "tipologia", "mq", "tempistica_vendita"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9àèéìòù]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    stop = {"il","lo","la","i","gli","le","un","una","uno","di","a","da","in","con","su","per","tra","fra","e","o","che","è","non","più","del","della","dei","delle","al","alla","nel","nella","se","come","prima","poi","f1","immobiliare","valle","susa"}
    return {x for x in norm(text).split() if len(x) > 2 and x not in stop}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def job_text(job: dict) -> str:
    return " ".join([
        str(job.get("title") or ""),
        str(job.get("main_message") or ""),
        " ".join(job.get("slides") or []),
        str(job.get("voiceover") or ""),
        str(job.get("caption") or ""),
    ])


def check_job(job: dict) -> list[str]:
    reasons: list[str] = []
    text = norm(job_text(job))
    audience = norm(job.get("target_public"))
    objective = norm(job.get("post_objective"))
    fmt = str(job.get("format") or "").lower()
    slides = [norm(x) for x in job.get("slides") or [] if norm(x)]
    required_fields = {str(x) for x in job.get("lead_qualification_required_fields") or []}

    if not audience or "proprietari" not in audience or "vendita" not in audience:
        reasons.append("target_not_precise_seller")
    if objective != "richiesta informazioni":
        reasons.append("objective_not_single_or_wrong")
    if not norm(job.get("main_message")):
        reasons.append("missing_main_message")
    if not (SELLER_TERMS & set(text.split())):
        reasons.append("seller_intent_missing")
    if any(x in text for x in BUYER_ONLY):
        reasons.append("buyer_or_rental_intent_detected")
    if any(x in text for x in BAIT):
        reasons.append("engagement_bait")
    if str(job.get("lead_keyword") or "").upper() != "VALUTAZIONE":
        reasons.append("qualification_keyword_missing")
    if not REQUIRED_QUALIFICATION.issubset(required_fields):
        reasons.append("qualification_fields_incomplete")

    # The qualifying CTA must actually be visible in the caption.
    cap = norm(job.get("caption"))
    for needle in ("valutazione", "comune", "tipologia", "mq", "quando"):
        if needle not in cap:
            reasons.append(f"qualifying_cta_missing_{needle}")

    # Topic coherence: at least two declared topic concepts must be reflected in the actual asset.
    keywords = [norm(x) for x in job.get("topic_keywords") or [] if norm(x)]
    hits = sum(1 for kw in keywords if all(part in text for part in kw.split()))
    if keywords and hits < min(2, len(keywords)):
        reasons.append("message_mismatch")

    # Slides must add content rather than repeat the same text unit.
    if len(slides) != len(set(slides)):
        reasons.append("redundant_slides")

    if fmt == "reel":
        if not 6 <= len(slides) <= 8:
            reasons.append("reel_slide_count_out_of_range")
        if int(job.get("reel_width") or 0) != 1080 or int(job.get("reel_height") or 0) != 1920:
            reasons.append("reel_not_9_16")
        if float(job.get("essential_content_safe_bottom_fraction") or 0) < 0.35:
            reasons.append("reel_safe_area_missing")
        if not job.get("muted_view_comprehension_required"):
            reasons.append("muted_view_not_supported")
        if float(job.get("reel_duration_seconds") or 0) > 35:
            reasons.append("reel_too_long_for_this_batch")
        if float(job.get("first_hook_seconds") or 99) > 3:
            reasons.append("hook_too_slow")
        if not str(job.get("audio_rights") or ""):
            reasons.append("audio_rights_missing")
    elif fmt == "carousel":
        if not 7 <= len(slides) <= 10:
            reasons.append("carousel_slide_count_out_of_range")
        if len(slides) >= 2 and slides[0] == slides[-1]:
            reasons.append("carousel_loop_not_closed")
    else:
        reasons.append("unsupported_format")

    if job.get("publication_time_verified") is not False:
        reasons.append("unverified_publish_time_claim")
    if job.get("publish_automatically"):
        reasons.append("automatic_publish_not_allowed")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    data = load(QUEUE)
    jobs = list(data.get("jobs") or [])
    rows = []

    # First run content-level checks.
    for job in jobs:
        reasons = check_job(job)
        rows.append({"job_id": job["id"], "format": job.get("format"), "reasons": reasons})

    # Then detect creative fatigue across the batch. CTA boilerplate is excluded by comparing title + main message only.
    signatures = {j["id"]: tokens(str(j.get("title") or "") + " " + str(j.get("main_message") or "")) for j in jobs}
    for i, a in enumerate(jobs):
        for b in jobs[i + 1:]:
            sim = jaccard(signatures[a["id"]], signatures[b["id"]])
            if sim >= 0.68:
                for target in (a["id"], b["id"]):
                    row = next(x for x in rows if x["job_id"] == target)
                    row["reasons"].append(f"creative_fatigue_similarity_{sim:.2f}")

    feedback_by_id = {r["job_id"]: r for r in rows}
    for job in jobs:
        reasons = sorted(set(feedback_by_id[job["id"]]["reasons"]))
        job["gate_reasons"] = reasons
        job["gate_status"] = "BLOCKED" if reasons else "PASSED"
        job["status"] = "needs_regeneration" if reasons else "awaiting_manual_approval"

    blocked = [j for j in jobs if j["gate_status"] == "BLOCKED"]
    passed = [j for j in jobs if j["gate_status"] == "PASSED"]
    data["gate_summary"] = {"passed": len(passed), "blocked": len(blocked), "total": len(jobs)}
    save(QUEUE, data)

    feedback = {
        "version": 1,
        "source": "producer_side_instagram_gate",
        "purpose": "qualified_seller_leads",
        "summary": data["gate_summary"],
        "blocked": [{"job_id": j["id"], "reasons": j["gate_reasons"]} for j in blocked],
        "passed": [j["id"] for j in passed],
        "note": "This gate checks policy compliance and content coherence; it does not estimate Instagram's internal ranking score.",
    }
    save(FEEDBACK, feedback)
    print(f"GATE F1 QUALIFIED: passed={len(passed)} blocked={len(blocked)} total={len(jobs)}")
    for j in blocked:
        print("BLOCKED", j["id"], ",".join(j["gate_reasons"]))
    return 1 if blocked and args.fail_on_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
