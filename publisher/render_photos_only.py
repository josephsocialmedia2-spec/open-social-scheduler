#!/usr/bin/env python3
"""Render the active cycle as STATIC PHOTOS ONLY.

F1 Immobiliare:
- use only geographically coherent, configured Valle di Susa / Avigliana imagery;
- never fall back to generic luxury villas or foreign-looking stock photography;
- if no approved local image is usable, fail instead of publishing the wrong visual.

Real Media Pro:
- extract media directly from the authorised public Shopify storefront URLs configured
  for Real Media Pro;
- transform the selected storefront asset into an original branded RMP composition;
- use generic stock only if the job does not explicitly require Shopify assets.
"""
from __future__ import annotations

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps

import render_fresh_visuals as fv
from shopify_public_media import extract as extract_shopify

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "publisher" / "queue.json"
HISTORY = ROOT / "publisher" / "image_history.json"
MANUAL_ROOT = ROOT / "publisher" / "manual_images"
F1_CFG = ROOT / "publisher" / "clients" / "f1-immobiliare.json"
RMP_CFG = ROOT / "publisher" / "clients" / "real-media-pro.json"
SIZE = (1080, 1350)
MAX_HISTORY = 1000
ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
LOCAL_MARKERS = (
    "avigliana", "valle di susa", "val di susa", "susa", "almese", "sant'ambrogio",
    "oulx", "bardonecchia", "sauze", "condove", "villar dora", "bussoleno",
    "borgone", "chiusa di san michele", "piemonte",
)
_SHOPIFY_CACHE: list[str] | None = None
_F1_LOCAL_CACHE: list[str] | None = None


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def center_crop(image: Image.Image, size: tuple[int, int] = SIZE) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def source_key(source: str) -> str:
    return source if source.startswith("manual://") else fv.photo_key(source)


def recent_keys(history: dict, cid: str) -> set[str]:
    rows = history.get("brands", {}).get(cid, {}).get("recent", [])
    return {str(row.get("key") or "") for row in rows if isinstance(row, dict) and row.get("key")}


def unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        key = source_key(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def configured_f1_local_candidates() -> list[str]:
    global _F1_LOCAL_CACHE
    if _F1_LOCAL_CACHE is not None:
        return list(_F1_LOCAL_CACHE)
    cfg = load_json(F1_CFG, {})
    rows: list[str] = []
    for item in cfg.get("brand", {}).get("photo_sources", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        credit = str(item.get("credit") or "").lower()
        if url and any(marker in credit for marker in LOCAL_MARKERS):
            rows.append(url)
    _F1_LOCAL_CACHE = unique(rows)
    return list(_F1_LOCAL_CACHE)


def shopify_candidates() -> list[str]:
    global _SHOPIFY_CACHE
    if _SHOPIFY_CACHE is not None:
        return list(_SHOPIFY_CACHE)

    cfg = load_json(RMP_CFG, {})
    urls = [str(x).strip() for x in cfg.get("campaign", {}).get("shopify_public_sources", []) if str(x).strip()]
    found: list[str] = []
    errors: list[str] = []
    for page_url in urls:
        try:
            media = extract_shopify(page_url)
            found.extend(media.images)
        except Exception as exc:
            errors.append(f"{page_url}: {exc}")
            print(f"WARN Shopify storefront extraction failed: {page_url}: {exc}")

    _SHOPIFY_CACHE = unique(found)
    print(f"SHOPIFY SOURCE: {len(_SHOPIFY_CACHE)} unique image(s) extracted from {len(urls)} configured page(s); errors={len(errors)}")
    return list(_SHOPIFY_CACHE)


def manual_candidates(cid: str) -> list[tuple[str, Path]]:
    folder = MANUAL_ROOT / cid
    if not folder.exists():
        return []
    rows: list[tuple[str, Path]] = []
    for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix().casefold()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED:
            continue
        rel = path.relative_to(ROOT).as_posix()
        rows.append((f"manual://{rel}", path))
    return rows


def open_manual(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.width < 500 or image.height < 500:
        raise RuntimeError(f"manual image too small: {path} = {image.size}")
    return image


def choose_remote(
    urls: list[str], recent: set[str], session: set[str], source_type: str
) -> tuple[str, Image.Image, bool, str] | None:
    fresh: list[str] = []
    reused: list[str] = []
    for url in unique(urls):
        key = source_key(url)
        if key in session:
            continue
        (reused if key in recent else fresh).append(url)

    for is_fresh, bucket in ((True, fresh), (False, reused)):
        for url in bucket:
            try:
                return url, fv.direct_get_image(url), is_fresh, source_type
            except Exception as exc:
                print(f"WARN remote visual rejected {url}: {exc}")
    return None


def choose_one(job: dict, history: dict, session: set[str]) -> tuple[str, Image.Image, bool, str]:
    cid = str(job.get("client_id") or "")
    recent = recent_keys(history, cid)

    # F1: LOCAL MEANS LOCAL. No generic Pixabay fallback is allowed for property acquisition posts.
    if cid == "f1-immobiliare" and bool(job.get("local_visual_required", False)):
        local_urls = configured_f1_local_candidates()
        picked = choose_remote(local_urls, recent, session, "f1-approved-local-valle-susa")
        if picked:
            return picked
        raise RuntimeError(
            f"F1 local visual policy blocked {job.get('id')}: no approved Valle di Susa/Piemonte source was usable. "
            "The engine refuses to publish a generic or foreign-looking house."
        )

    # RMP: Shopify storefront media is the primary and required source for the current policy.
    if cid == "real-media-pro" and bool(job.get("shopify_asset_required", False)):
        picked = choose_remote(shopify_candidates(), recent, session, "shopify-storefront-authorised")
        if picked:
            return picked
        raise RuntimeError(
            f"RMP Shopify visual policy blocked {job.get('id')}: no configured storefront image was usable. "
            "The engine refuses to silently replace it with Pixabay stock."
        )

    # Generic fallback path retained only for future clients/policies that do not require strict sources.
    manual = manual_candidates(cid)
    manual_reuse: list[tuple[str, Path]] = []
    for source, path in manual:
        key = source_key(source)
        if key in session:
            continue
        if key in recent:
            manual_reuse.append((source, path))
            continue
        try:
            return source, open_manual(path), True, "manual-upload"
        except Exception as exc:
            print(f"WARN manual photo rejected {path}: {exc}")
    for source, path in manual_reuse:
        key = source_key(source)
        if key in session:
            continue
        try:
            return source, open_manual(path), False, "manual-upload"
        except Exception as exc:
            print(f"WARN reusable manual photo rejected {path}: {exc}")

    candidates = fv.discover(job, max_urls=100) + fv.fallback_for(job)
    picked = choose_remote(candidates, recent, session, "pixabay-fallback-static-photo")
    if picked:
        return picked
    raise RuntimeError(f"No usable static photo found for {job.get('id')}")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_title(draw: ImageDraw.ImageDraw, text: str, width: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(54, 29, -2):
        f = font(size, True)
        lines = textwrap.wrap(text, width=26)
        if all(draw.textbbox((0, 0), line, font=f)[2] <= width for line in lines):
            return f
    return font(30, True)


def rmp_shopify_composition(image: Image.Image, title: str) -> Image.Image:
    """Transform an authorised Shopify storefront image into an original RMP social creative."""
    canvas = Image.new("RGB", SIZE, "#07111F")
    draw = ImageDraw.Draw(canvas)
    draw.text((64, 55), "REAL MEDIA PRO", font=font(28, True), fill="#F5F8FC")
    draw.text((64, 96), "SITI WEB · ECOMMERCE · SHOPIFY", font=font(18, True), fill="#6EE7A8")

    visual = ImageOps.fit(image.convert("RGB"), (952, 760), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    mask = Image.new("L", visual.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, visual.width - 1, visual.height - 1), radius=28, fill=255)
    canvas.paste(visual, (64, 165), mask)

    draw.rounded_rectangle((64, 955, 1016, 1258), radius=28, fill="#0D1B2D")
    draw.text((92, 990), "DAL PROGETTO REALE ALLA CREATIVITÀ", font=font(17, True), fill="#6EE7A8")
    title_text = str(title or "SHOPIFY · PROGETTO DIGITALE").upper()
    tf = fit_title(draw, title_text, 870)
    y = 1035
    for line in textwrap.wrap(title_text, width=28)[:3]:
        draw.text((92, y), line, font=tf, fill="#F5F8FC")
        y += int(getattr(tf, "size", 34) * 1.16)
    draw.text((92, 1195), "371 370 8294", font=font(22, True), fill="#B8C7E0")
    return canvas


def record(history: dict, cid: str, source: str, job_id: str, source_type: str) -> None:
    brands = history.setdefault("brands", {})
    brand = brands.setdefault(cid, {"recent": []})
    rows = list(brand.get("recent", []))
    key = source_key(source)
    rows = [r for r in rows if str(r.get("key") or "") != key]
    rows.append({
        "key": key,
        "url": source,
        "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "job_id": job_id,
        "output_type": "static-photo",
        "source_type": source_type,
    })
    brand["recent"] = rows[-MAX_HISTORY:]


def main() -> int:
    q = load_json(QUEUE, {"jobs": []})
    cycle = q.get("current_cycle")
    jobs = [j for j in q.get("jobs", []) if j.get("cycle_key") == cycle]
    if len(jobs) != 6:
        raise RuntimeError(f"Expected 6 current-cycle jobs, got {len(jobs)}")
    if any(j.get("format") != "photo" for j in jobs):
        raise RuntimeError("PHOTO-ONLY renderer received a non-photo job")

    history = load_json(HISTORY, {"version": 1, "brands": {}})
    session: dict[str, set[str]] = {"f1-immobiliare": set(), "real-media-pro": set()}

    for job in jobs:
        cid = str(job.get("client_id") or "")
        source_id, source, fresh, source_type = choose_one(job, history, session.setdefault(cid, set()))
        key = source_key(source_id)
        session[cid].add(key)
        out = ROOT / str(job["media"])
        out.parent.mkdir(parents=True, exist_ok=True)

        if cid == "real-media-pro" and bool(job.get("shopify_transform_required", False)):
            final = rmp_shopify_composition(source, str(job.get("title") or ""))
            transform = "rmp-branded-shopify-transform"
        else:
            final = center_crop(source)
            transform = "local-photo-crop"
        final.save(out, "JPEG", quality=94, optimize=True, progressive=True)

        if not out.exists() or out.stat().st_size < 20000:
            raise RuntimeError(f"Static photo was not rendered correctly: {out}")

        job["visual_asset_urls"] = [source_id]
        job["visual_source"] = source_type
        job["visual_transform"] = transform
        job["visual_count"] = 1
        job["fresh_visual_count"] = 1 if fresh else 0
        job["reused_visual_count"] = 0 if fresh else 1
        job["production_status"] = "PHOTO READY"
        job["publication_ready"] = True
        job["output_type"] = "static-photo"
        job["no_video"] = True
        job["no_audio"] = True
        record(history, cid, source_id, str(job.get("id") or ""), source_type)
        print(f"PHOTO READY {cid}: {out} <- {source_type}: {source_id}")

    history["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    q["output_policy"] = "STATIC PHOTOS ONLY - F1 VERIFIED LOCAL SOURCES - RMP SHOPIFY STOREFRONT TRANSFORM"
    q["updated_by"] = "Strict local F1 + direct Shopify RMP renderer"
    save_json(HISTORY, history)
    save_json(QUEUE, q)
    print("DONE: F1 local-only visuals + RMP transformed Shopify storefront visuals; zero reels/mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
