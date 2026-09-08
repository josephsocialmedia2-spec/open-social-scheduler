#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import random
import re
import shutil
import unicodedata
from pathlib import Path

import requests
from ddgs import DDGS
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import f1_premium_renderer as f1

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "publisher/github_graphics/queries.json"
OUT = ROOT / "property-preview"
SIZE = (1080, 1350)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
BAD = ("owl","gufo","bird","uccello","cat","gatto","dog","cane","food","cibo","etsy","pinterest","cnn","banner","young ssbbw","dnyaneshwar")
PROPERTY = ("villa","ville","appartamento","appartamenti")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def font(sz, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try: return ImageFont.truetype(p, sz)
    except Exception: return ImageFont.load_default()


def wrap(d, text, width, sz, max_lines, bold=True):
    words = str(text).split()
    for size in range(sz, 23, -2):
        ft, lines, line = font(size, bold), [], ""
        for w in words:
            t = (line + " " + w).strip()
            if d.textbbox((0,0), t, font=ft)[2] <= width: line = t
            else:
                if line: lines.append(line)
                line = w
        if line: lines.append(line)
        if len(lines) <= max_lines: return ft, lines
    return font(24, bold), [" ".join(words)]


def download(url):
    r = requests.get(url, headers={"User-Agent":UA,"Accept":"image/*,*/*;q=0.8"}, timeout=18)
    r.raise_for_status()
    if len(r.content) < 35000: raise RuntimeError("small")
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if im.width < 700 or im.height < 500: raise RuntimeError("low resolution")
    return im


def result_is_relevant(row, commune):
    text = norm(" ".join(str(row.get(k,"")) for k in ("title","url","image","source")))
    c = norm(commune)
    distinctive = [x for x in c.split() if len(x) >= 4 and x not in {"susa","torino","della","delle"}]
    place_ok = c in text or any(x in text for x in distinctive)
    property_ok = any(norm(x) in text for x in PROPERTY)
    bad = any(norm(x) in text for x in BAD)
    return place_ok and property_ok and not bad


def web_home(commune, idx):
    # Regola F1: la ricerca visuale usa esclusivamente APPARTAMENTO o VILLA + COMUNE.
    searches = [
        f'Appartamento "{commune}"',
        f'Villa "{commune}"',
    ]
    errors=[]
    for q in searches:
        try: rows=list(DDGS().images(q, region="it-it", safesearch="moderate", max_results=40))
        except Exception as e:
            errors.append(str(e)); continue
        random.Random(8800+idx).shuffle(rows)
        for row in rows:
            if not result_is_relevant(row, commune): continue
            u=row.get("image") or row.get("url")
            if not str(u).startswith("http"): continue
            try:
                return download(str(u)), {"query":q,"url":str(u),"title":row.get("title","")}
            except Exception as e: errors.append(str(e))
    # Safe fallback: only configured F1 real-estate sources, never random web imagery.
    cfg=f1.load_json(f1.F1_CFG,{})
    for item in cfg.get("brand",{}).get("photo_sources",[]):
        if not isinstance(item,dict) or not item.get("url"): continue
        txt=norm(" ".join(str(v) for v in item.values()))
        if any(norm(x) in txt for x in BAD): continue
        try:
            return f1.robust_local_get(str(item["url"])), {"query":"F1 safe fallback","url":str(item["url"]),"title":str(item.get("credit",""))}
        except Exception as e: errors.append(str(e))
    raise RuntimeError("No valid apartment/villa image: "+" | ".join(errors[-3:]))


def twilight(im):
    base=ImageOps.fit(im.convert("RGB"),SIZE,Image.Resampling.LANCZOS)
    base=ImageEnhance.Contrast(base).enhance(1.12)
    dark=ImageEnhance.Brightness(base).enhance(.68).convert("RGBA")
    dark=Image.alpha_composite(dark,Image.new("RGBA",SIZE,(20,40,76,82)))
    grad=Image.new("RGBA",SIZE,(0,0,0,0)); gd=ImageDraw.Draw(grad)
    for y in range(0,700):
        a=int(105*(1-y/700)); gd.line((0,y,1080,y),fill=(255,118,46,a),width=1)
    dark=Image.alpha_composite(dark,grad)
    lum=base.convert("L")
    mask=lum.point(lambda p:255 if p>182 else 0).filter(ImageFilter.GaussianBlur(12))
    glow=Image.new("RGBA",SIZE,(255,180,75,0)); glow.putalpha(mask.point(lambda p:int(p*.62)))
    return Image.alpha_composite(dark,glow).convert("RGB")


def location_badge(d, comune):
    d.rounded_rectangle((720,45,1030,130),radius=18,fill=(5,8,7))
    d.ellipse((745,68,773,96),outline=(205,165,90),width=4); d.ellipse((755,78,763,86),fill=(205,165,90))
    ft,ls=wrap(d,comune.upper(),225,25,2,True); y=60
    for line in ls:
        d.text((792,y),line,font=ft,fill=f1.WHITE); y+=int(getattr(ft,"size",22)*1.04)


def render(item, image):
    comune=item["commune"]; query=item["query"]
    canvas=twilight(image)
    ov=Image.new("RGBA",SIZE,(0,0,0,0)); od=ImageDraw.Draw(ov)
    od.rectangle((0,0,1080,150),fill=(5,8,7,205)); od.rectangle((0,545,1080,1350),fill=(5,8,7,178))
    canvas=Image.alpha_composite(canvas.convert("RGBA"),ov).convert("RGB"); d=ImageDraw.Draw(canvas)
    f1.draw_brand(d,42,36); location_badge(d,comune)
    d.text((58,615),"CERCHI CASA A",font=font(33),fill=f1.WHITE)
    ft,ls=wrap(d,comune.upper()+"?",920,76,2,True); y=658
    for line in ls:
        d.text((58,y),line,font=ft,fill=(205,165,90)); y+=int(getattr(ft,"size",60)*1.02)
    d.text((58,y+12),"Scopri le opportunità immobiliari del territorio.",font=font(28),fill=f1.WHITE)
    d.text((58,y+50),"Ricevi foto, prezzi e planimetrie delle case disponibili.",font=font(26),fill=f1.WHITE)
    for txt,yy in [("NATURA E TRANQUILLITÀ",865),("SERVIZI A PORTATA DI MANO",920),("CASE SELEZIONATE",975)]:
        d.ellipse((62,yy,90,yy+28),outline=(205,165,90),width=3); d.text((108,yy),txt,font=font(20,True),fill=f1.WHITE)
    d.rounded_rectangle((58,1048,680,1135),radius=18,fill=(205,165,90)); d.text((88,1070),"SCRIVI CASA SU WHATSAPP",font=font(28,True),fill=f1.BLACK)
    fq,ql=wrap(d,"QUERY: "+query,930,17,2,False); qy=1155
    for line in ql:
        d.text((60,qy),line,font=fq,fill=(210,215,210)); qy+=22
    f1.draw_footer(canvas)
    return canvas


def build_index(outputs):
    cards="".join(f'<article><img src="{x["index"]:02d}.jpg"><h2>{x["query"]}</h2><a href="{x["index"]:02d}.jpg" target="_blank">Apri grafica</a></article>' for x in outputs)
    html=f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>F1 · Anteprima grafiche</title><style>body{{margin:0;background:#070907;color:#f7f7f4;font-family:Arial}}header{{padding:28px 5vw;border-bottom:1px solid #c8a15a}}h1{{color:#c8a15a}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px;padding:28px 5vw}}article{{background:#101610;padding:14px;border-radius:18px;border:1px solid #303730}}img{{width:100%;border-radius:12px}}h2{{font-size:16px}}a{{display:inline-block;background:#c8a15a;color:#070907;padding:10px 14px;border-radius:9px;text-decoration:none;font-weight:700}}</style></head><body><header><h1>F1 IMMOBILIARE · 10 GRAFICHE QUERY</h1><p>Stesso modello di ricerca, cambia soltanto il comune. Foto Appartamento/Villa pertinenti + trattamento tramonto e luci accese.</p></header><main>{cards}</main></body></html>'''
    (OUT/"index.html").write_text(html,encoding="utf-8")


def main():
    data=json.loads(QUERIES.read_text(encoding="utf-8")); selected=(data.get("queries") or [])[:10]
    OUT.mkdir(parents=True,exist_ok=True)
    for p in OUT.glob("[0-9][0-9].jpg"): p.unlink()
    outputs=[]
    for i,item in enumerate(selected,1):
        image,source=web_home(item["commune"],i)
        out=OUT/f"{i:02d}.jpg"; render(item,image).save(out,"JPEG",quality=94,optimize=True)
        outputs.append({"index":i,"id":item.get("id"),"commune":item["commune"],"query":item["query"],"source":source,"output":str(out.relative_to(ROOT))})
    shutil.copyfile(OUT/"01.jpg",OUT/"latest.jpg")
    (OUT/"meta.json").write_text(json.dumps({"batch":data.get("batch"),"count":len(outputs),"size":SIZE,"visual_rule":"APPARTAMENTO or VILLA + municipality -> sunset -> lights on","outputs":outputs},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    raw="https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/property-preview"
    md=["# F1 · 10 grafiche query","","Query contenuto bloccata: cambia solo il nome del comune. Ricerca immagini: Appartamento/Villa + comune.",""]
    for x in outputs: md += [f'## {x["index"]:02d} · {x["query"]}',"",f'![{x["query"]}]({raw}/{x["index"]:02d}.jpg)',""]
    (OUT/"README.md").write_text("\n".join(md),encoding="utf-8"); build_index(outputs)
    print("READY",len(outputs))
    return 0

if __name__ == "__main__": raise SystemExit(main())
