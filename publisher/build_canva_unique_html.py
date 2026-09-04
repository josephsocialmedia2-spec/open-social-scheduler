#!/usr/bin/env python3
"""Create Canva-importable HTML packs from the verified unique-visual F1 queue."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "qualified_14d_queue.json"
OUT = ROOT / "publisher" / "canva_generated"

CSS_COMMON = """
*{box-sizing:border-box}html,body{margin:0;padding:0;background:#111;font-family:Arial,sans-serif}.page{position:relative;overflow:hidden;background:#050805;color:#fff}.bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.32),rgba(0,0,0,.65))}.brand{position:absolute;left:50%;transform:translateX(-50%);top:5%;padding:14px 24px;border:3px solid #9fe000;border-radius:22px;background:rgba(5,8,5,.88);font-size:34px;font-weight:900;letter-spacing:.08em}.panel{position:absolute;left:7%;right:7%;top:24%;padding:48px;border:4px solid #9fe000;border-radius:40px;background:rgba(5,10,6,.88);text-align:center}.headline{font-size:70px;line-height:1.04;font-weight:900;text-transform:uppercase}.footer{position:absolute;left:7%;right:7%;bottom:10%;padding:30px;border-radius:28px;background:#f7f7f4;color:#111;text-align:center;font-size:30px;font-weight:900}.green{color:#92c205}.count{position:absolute;right:8%;bottom:4%;font-size:22px;font-weight:900}.theme{position:absolute;left:7%;bottom:4%;font-size:18px;letter-spacing:.08em;text-transform:uppercase}
"""


def esc(v: object) -> str:
    return html.escape(str(v or ""), quote=True)


def page(job: dict, slide: str, idx: int, total: int, reel: bool) -> str:
    w, h = (1080, 1920) if reel else (1080, 1350)
    cta = "SCRIVI VALUTAZIONE · COMUNE · TIPOLOGIA · MQ · TEMPI" if idx == total - 1 else "F1 IMMOBILIARE · PRIMA I DATI, POI LA STRATEGIA"
    label = f"{job.get('source_item_id')} · {job.get('title')} · {idx+1}/{total}"
    return f'''<section class="page" data-document-role="page" data-label="{esc(label)}" style="width:{w}px;height:{h}px">
<img class="bg" src="{esc(job.get('resolved_visual_url'))}" alt="{esc(job.get('visual_theme'))}"><div class="shade"></div>
<div class="brand">F1 IMMOBILIARE</div>
<div class="panel"><div class="headline">{esc(str(slide).replace('|',' '))}</div></div>
<div class="footer"><span class="green">{esc(cta)}</span></div>
<div class="theme">{esc(job.get('visual_theme'))}</div><div class="count">{idx+1}/{total}</div>
</section>'''


def build(kind: str, jobs: list[dict]) -> str:
    reel = kind == "reel"
    pages = []
    for job in jobs:
        slides = list(job.get("slides") or [])
        for idx, slide in enumerate(slides):
            pages.append(page(job, str(slide), idx, len(slides), reel))
    return "<!doctype html><html><head><meta charset=\"utf-8\"><style>" + CSS_COMMON + "</style></head><body>" + "\n".join(pages) + "</body></html>"


def main() -> int:
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    jobs = list(data.get("jobs") or [])
    if len(jobs) != 28 or any(not j.get("resolved_visual_url") for j in jobs):
        raise RuntimeError("Unique visual queue is incomplete")
    OUT.mkdir(parents=True, exist_ok=True)
    reels = [j for j in jobs if j.get("format") == "reel"]
    cars = [j for j in jobs if j.get("format") == "carousel"]
    (OUT / "reels-latest.html").write_text(build("reel", reels), encoding="utf-8")
    (OUT / "carousels-latest.html").write_text(build("carousel", cars), encoding="utf-8")
    print(f"CANVA HTML GENERATED: reel pages={sum(len(j.get('slides') or []) for j in reels)} carousel pages={sum(len(j.get('slides') or []) for j in cars)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
