#!/usr/bin/env python3
"""Build a privacy-safe F1 Seller queue for Postiz from launcher-dashboard output."""
from __future__ import annotations
import json, os, re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
import qrcode

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.getenv("SELLER_OUTBOX", ROOT/"seller-source"/"data"/"postiz-outbox.json"))
TERRITORY=Path(os.getenv("SELLER_TERRITORY_CONFIG", ROOT/"seller-source"/"config"/"territory.json"))
CLIENT=ROOT/"publisher"/"clients"/"f1-immobiliare.json"
QUEUE=Path(os.getenv("SOCIAL_QUEUE", ROOT/"publisher"/"f1-seller-postiz-queue.json"))
MEDIA_ROOT=ROOT/"publisher"/"media"/"seller-postiz"
TZ=ZoneInfo("Europe/Rome")
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def load(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def norm(v):
    return re.sub(r"\s+"," ",str(v or "").strip()).casefold()

def territory_set(cfg):
    return {norm(x) for side in ("sinistra","destra") for x in (cfg.get(side) or []) if str(x).strip()}

def integration_specs(client):
    bindings=client.get("postiz_integrations") or {}
    specs=[]; missing=[]
    for platform,cfg in bindings.items():
        iid=str((cfg or {}).get("id") or "").strip()
        if iid: specs.append({"platform":platform,"integration_id":iid})
        elif (cfg or {}).get("required"): missing.append(platform)
    return specs,missing

def next_slots(now, slots, count):
    out=[]; cursor=now
    for _ in range(3):
        candidates=[]
        for day_off in range(0,4):
            day=(cursor+timedelta(days=day_off)).date()
            for raw in slots:
                hh,mm=map(int,raw.split(":"))
                dt=datetime(day.year,day.month,day.day,hh,mm,tzinfo=TZ)
                if dt>cursor+timedelta(minutes=10): candidates.append(dt)
        if not candidates: break
        chosen=min(candidates); out.append(chosen); cursor=chosen
        if len(out)>=count: break
    return out

def wrap(draw,text,font,max_width):
    words=str(text).split(); lines=[]; current=""
    for word in words:
        candidate=(current+" "+word).strip()
        if draw.textbbox((0,0),candidate,font=font)[2] <= max_width: current=candidate
        else:
            if current: lines.append(current)
            current=word
    if current: lines.append(current)
    return lines[:5]

def render(job, valuation_url):
    out=ROOT/job["media"]; out.parent.mkdir(parents=True,exist_ok=True)
    im=Image.new("RGB",(1080,1350),"#07100a"); d=ImageDraw.Draw(im)
    green="#39f28a"; white="#f7f7f4"; muted="#b9c3bc"
    fb=ImageFont.truetype(BOLD,54); fh=ImageFont.truetype(BOLD,78); fm=ImageFont.truetype(BOLD,42); fs=ImageFont.truetype(FONT,32)
    d.text((70,65),"F1 IMMOBILIARE",font=fb,fill=green)
    d.text((70,135),"VALLE DI SUSA",font=fs,fill=muted)
    y=275
    for line in wrap(d,job["title"],fh,900):
        d.text((70,y),line,font=fh,fill=white); y+=92
    comune=job.get("territory") or "Valle di Susa"
    d.rounded_rectangle((70,760,1010,855),22,fill="#122219",outline=green,width=3)
    d.text((105,784),comune.upper()[:38],font=fm,fill=green)
    d.text((70,930),"VALUTAZIONE PROFESSIONALE GRATUITA",font=fm,fill=white)
    d.text((70,995),"Scansiona il QR code",font=fs,fill=muted)
    qr=qrcode.make(valuation_url).convert("RGB").resize((230,230))
    im.paste(qr,(760,1040))
    d.text((70,1110),"Prime case · Seconde case",font=fs,fill=white)
    d.text((70,1160),"Locali commerciali",font=fs,fill=white)
    d.text((70,1240),"Condivisibile con amici e parenti",font=fs,fill=muted)
    im.save(out,"JPEG",quality=92,optimize=True)
    return out

def main():
    source=load(SOURCE,{"drafts":[]}); territory=load(TERRITORY,{})
    client=load(CLIENT,{})
    seller_cfg=client.get("seller_postiz") or {}
    allowed=territory_set(territory)
    drafts=[d for d in source.get("drafts",[]) if isinstance(d,dict) and norm(d.get("comune")) in allowed]
    old=load(QUEUE,{"version":1,"jobs":[]}); jobs=list(old.get("jobs") or [])
    seen={str(j.get("source_id") or "") for j in jobs if j.get("source_id")}
    fresh=[d for d in drafts if str(d.get("id") or "") not in seen]
    max_posts=int(seller_cfg.get("max_daily_posts",3) or 3)
    fresh=fresh[:max_posts]
    specs,missing=integration_specs(client)
    slots=next_slots(datetime.now(TZ),seller_cfg.get("slots") or ["09:00","14:00","19:00"],len(fresh))
    valuation=seller_cfg.get("valuation_url") or "https://www.agentpricing.com/j.malafronte"
    for draft,when in zip(fresh,slots):
        sid=str(draft.get("id") or "")
        comune=str(draft.get("comune") or "Valle di Susa")
        raw_title=str(draft.get("title") or "Novita immobiliare nella zona")
        caption=(str(draft.get("text") or "").strip()+"\n\n"
                 +f"Valutazione Professionale Gratuita: {valuation}\n\n"
                 +"Puoi condividere questo link con amici, conoscenti o parenti che abbiano necessita di vendere o acquistare un immobile.")
        job={
          "id":f"f1-seller-{when.date().isoformat()}-{sid[:12] or len(jobs)}",
          "source_id":sid,"client_id":"f1-immobiliare","client_name":"F1 Immobiliare",
          "campaign":"F1 Seller Lead Engine","campaign_type":draft.get("campaign_type"),
          "format":"photo","title":raw_title,"caption":caption,"territory":comune,
          "cta":"VALUTAZIONE PROFESSIONALE GRATUITA","link":valuation,
          "media":f"publisher/media/seller-postiz/{when.date().isoformat()}/{sid[:12] or 'seller'}.jpg",
          "scheduled_at":when.isoformat(),"platforms":specs,"enabled":True,
          "status":"awaiting_integrations" if missing or not specs else "ready",
          "missing_integrations":missing,"published_platforms":[],"postiz_results":[],
          "created_by":"f1-seller-postiz-bridge","source_generated_at":source.get("generated_at")
        }
        render(job,valuation); jobs.append(job)
    jobs=jobs[-120:]
    payload={"version":1,"updated_at":datetime.now(TZ).isoformat(),"source_generated_at":source.get("generated_at"),
             "postiz_binding_status":"READY" if specs and not missing else "AWAITING_INTEGRATIONS",
             "missing_integrations":missing,"jobs":jobs}
    QUEUE.parent.mkdir(parents=True,exist_ok=True)
    QUEUE.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"fresh":len(fresh),"eligible_source":len(drafts),"postiz":payload["postiz_binding_status"],"missing":missing}))
    return 0
if __name__=="__main__": raise SystemExit(main())
