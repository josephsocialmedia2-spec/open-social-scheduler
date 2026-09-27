#!/usr/bin/env python3
"""Generate owned Real Media Pro starter creatives into F1 Content Hub.

Creates deterministic branded static posts from publisher/content_bank/real-media-pro.json,
uploads them to the private f1-content-media bucket and creates Content Hub rows.
Idempotent: each bank slug is inserted once through distribution_plan.seed_key.
"""
from __future__ import annotations
import io, json, os, re, textwrap, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
BANK=ROOT/"publisher"/"content_bank"/"real-media-pro.json"
SUPABASE_URL=os.environ.get("SUPABASE_URL","https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
SERVICE_KEY=os.environ.get("SUPABASE_SERVICE_ROLE_KEY","").strip()
BUCKET="f1-content-media"
LIMIT=max(1,min(6,int(os.environ.get("RMP_SEED_LIMIT","3"))))
TIMEOUT=90

def now_iso()->str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def headers(extra:dict[str,str]|None=None)->dict[str,str]:
    h={"apikey":SERVICE_KEY,"Authorization":f"Bearer {SERVICE_KEY}","Content-Type":"application/json"}
    if extra:h.update(extra)
    return h

def rest_get(table:str,params:dict[str,str])->list[dict[str,Any]]:
    r=requests.get(f"{SUPABASE_URL}/rest/v1/{table}",headers=headers(),params=params,timeout=TIMEOUT)
    r.raise_for_status()
    data=r.json()
    return data if isinstance(data,list) else []

def rest_post(table:str,payload:dict[str,Any],representation:bool=False)->list[dict[str,Any]]:
    r=requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers({"Prefer":"return=representation" if representation else "return=minimal"}),
        json=payload,timeout=TIMEOUT,
    )
    if not r.ok:raise RuntimeError(f"POST {table}: {r.status_code} {r.text[:500]}")
    if representation and r.text.strip():
        data=r.json();return data if isinstance(data,list) else []
    return []

def storage_upload(path:str,data:bytes,content_type:str)->None:
    encoded="/".join(quote(part,safe="") for part in path.split("/"))
    r=requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{encoded}",
        headers={"apikey":SERVICE_KEY,"Authorization":f"Bearer {SERVICE_KEY}","Content-Type":content_type,"x-upsert":"false"},
        data=data,timeout=TIMEOUT,
    )
    if not r.ok:raise RuntimeError(f"Storage upload: {r.status_code} {r.text[:500]}")

def font(size:int,bold:bool=False):
    candidates=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:return ImageFont.truetype(path,size)
        except Exception:pass
    return ImageFont.load_default()

def wrap(draw:ImageDraw.ImageDraw,text:str,fnt,max_width:int)->list[str]:
    words=str(text).split();lines=[];line=[]
    for w in words:
        trial=" ".join(line+[w])
        if draw.textbbox((0,0),trial,font=fnt)[2] <= max_width:
            line.append(w)
        else:
            if line:lines.append(" ".join(line))
            line=[w]
    if line:lines.append(" ".join(line))
    return lines

def render_card(title:str,eyebrow:str)->bytes:
    w,h=1080,1350
    img=Image.new("RGB",(w,h),"#020916")
    px=img.load()
    for y in range(h):
        t=y/max(1,h-1)
        base=(2+int(3*t),9+int(10*t),22+int(20*t))
        for x in range(w):
            glow=max(0,1-(((x-820)/520)**2+((y-180)/480)**2))
            px[x,y]=(min(255,base[0]+int(10*glow)),min(255,base[1]+int(55*glow)),min(255,base[2]+int(95*glow)))
    d=ImageDraw.Draw(img,"RGBA")
    for gx in range(0,w,72):d.line((gx,0,gx,h),fill=(32,199,255,13),width=1)
    for gy in range(0,h,72):d.line((0,gy,w,gy),fill=(32,199,255,13),width=1)
    d.ellipse((675,-170,1195,350),outline=(32,199,255,70),width=3)
    d.ellipse((735,-105,1135,295),outline=(57,242,138,38),width=2)
    d.rounded_rectangle((58,55,1022,1295),radius=34,fill=(4,17,34,224),outline=(32,199,255,100),width=2)
    d.rounded_rectangle((78,78,1002,118),radius=18,fill=(12,54,83,210))
    d.text((100,84),"F1 SOCIAL INTELLIGENCE  ·  REAL MEDIA PRO",font=font(27,True),fill=(150,238,255,255))
    d.text((100,188),eyebrow.upper(),font=font(24,True),fill=(57,242,138,255))
    tf=font(64,True)
    y=260
    for line in wrap(d,title,tf,820):
        d.text((100,y),line,font=tf,fill=(245,248,252,255));y+=82
    d.rounded_rectangle((100,930,980,1060),radius=26,fill=(8,39,65,225),outline=(57,242,138,105),width=2)
    d.text((135,966),"STRATEGIA  ·  AUTOMAZIONE  ·  CRESCITA",font=font(29,True),fill=(219,255,235,255))
    d.text((100,1140),"Real Media Pro",font=font(32,True),fill=(94,231,255,255))
    d.text((100,1192),"Social Intelligence for real results",font=font(24),fill=(166,194,220,255))
    buf=io.BytesIO();img.save(buf,"PNG",optimize=True);return buf.getvalue()

def flatten_bank()->list[dict[str,Any]]:
    data=json.loads(BANK.read_text(encoding="utf-8"))
    out=[]
    for section in ("attract","nurture","hyperlocal","convert"):
        for row in data.get(section,[]):
            out.append({**row,"section":section})
    return out

def existing_seed_keys(client_id:str)->set[str]:
    rows=rest_get("f1_content_items",{
        "select":"distribution_plan",
        "client_id":f"eq.{client_id}",
        "campaign":"eq.RMP_INTELLIGENCE_AUTO",
        "limit":"500",
    })
    keys=set()
    for row in rows:
        plan=row.get("distribution_plan") if isinstance(row.get("distribution_plan"),dict) else {}
        key=str(plan.get("seed_key") or "")
        if key:keys.add(key)
    return keys

def main()->int:
    if not SERVICE_KEY:raise SystemExit("SUPABASE_SERVICE_ROLE_KEY missing")
    clients=rest_get("f1_content_clients",{"select":"*","slug":"eq.real-media-pro","limit":"1"})
    if not clients:raise SystemExit("Real Media Pro client missing")
    client=clients[0];client_id=str(client["id"]);owner_id=str(client["owner_id"])
    existing=existing_seed_keys(client_id)
    selected=[]
    for row in flatten_bank():
        key=f"rmp-bank:{row['section']}:{row['slug']}"
        if key not in existing:
            selected.append((key,row))
        if len(selected)>=LIMIT:break
    if not selected:
        print("No new Real Media Pro seed creatives required")
        return 0
    created=0
    for key,row in selected:
        title=str(row.get("title") or row.get("slug") or "Real Media Pro")
        caption=str(row.get("caption") or "").replace("{cta}","Richiedi un'analisi strategica gratuita")
        item_rows=rest_post("f1_content_items",{
            "owner_id":owner_id,"client_id":client_id,"title":title,
            "description":caption,"source_text":caption,"content_type":"FOTO",
            "source":"F1_RMP_AUTOGEN","status":"IN ARRIVO","priority":"NORMALE",
            "campaign":"RMP_INTELLIGENCE_AUTO","tags":["RealMediaPro","F1SocialIntelligence","Automazione"],
            "notes":"Creatività proprietaria generata automaticamente dal content bank Real Media Pro.",
            "distribution_plan":{
                "seed_key":key,"category":str(row.get("section") or "branding").upper(),
                "intelligence_auto_generated":True,"generated_at":now_iso(),
            },
        },representation=True)
        if not item_rows:raise RuntimeError("Content item not created")
        item=item_rows[0];content_id=str(item["id"])
        png=render_card(title,str(row.get("section") or "Real Media Pro"))
        safe=re.sub(r"[^A-Za-z0-9._-]+","-",str(row["slug"])).strip("-")+".png"
        storage_path=f"{owner_id}/{client_id}/{content_id}/rmp-autogen-{uuid.uuid4().hex[:10]}-{safe}"
        storage_upload(storage_path,png,"image/png")
        rest_post("f1_content_media",{
            "owner_id":owner_id,"content_id":content_id,"client_id":client_id,
            "file_name":safe,"mime_type":"image/png","storage_path":storage_path,
            "file_size":len(png),"source":"F1_RMP_AUTOGEN",
        })
        rest_post("f1_intelligence_events",{
            "owner_id":owner_id,"client_id":client_id,"content_id":content_id,
            "stage":"CARICATO","status":"COMPLETED",
            "message":"Creatività Real Media Pro generata automaticamente e caricata nel cloud",
            "progress":15,"details":{"seed_key":key,"generator":"rmp_content_seed_worker"},
        })
        created+=1
        print(f"CREATED {content_id} {title}")
    print(json.dumps({"created":created,"client":"real-media-pro"},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
