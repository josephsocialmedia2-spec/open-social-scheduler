#!/usr/bin/env python3
from __future__ import annotations

import json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"publisher/multiclient_test_manifest.json"
QUEUE=ROOT/"publisher/queue.json"
OUT=ROOT/"publisher/media/generated/multiclient-test-20260926"
REPORT=ROOT/"publisher/multiclient_test_report.json"
SB=os.getenv("SUPABASE_URL","").rstrip("/")
KEY=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()

def sh(*args):
    print("+"," ".join(map(str,args)))
    subprocess.run([str(x) for x in args],check=True)

def duration(path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)],check=True,capture_output=True,text=True)
    return float(p.stdout.strip())

def rest(table,params):
    r=requests.get(f"{SB}/rest/v1/{table}",headers={"apikey":KEY,"Authorization":f"Bearer {KEY}"},params=params,timeout=60)
    r.raise_for_status()
    return r.json()

def download(filename):
    OUT.mkdir(parents=True,exist_ok=True)
    dest=OUT/(re.sub(r"[^A-Za-z0-9._-]+","_",filename))
    if dest.exists() and dest.stat().st_size>1000: return dest
    url="https://commons.wikimedia.org/wiki/Special:Redirect/file/"+quote(filename,safe="")
    with requests.get(url,stream=True,timeout=180,allow_redirects=True,headers={"User-Agent":"F1SocialPublisher/1.0"}) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for ch in r.iter_content(1024*1024):
                if ch: f.write(ch)
    if dest.stat().st_size<1000: raise RuntimeError("downloaded source is empty")
    return dest

def stamp(t,comma=True):
    ms=int(round(t*1000)); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02}{',' if comma else '.'}{ms:03}"

def subs(text,dur,slug):
    words=text.split(); chunks=[" ".join(words[i:i+9]) for i in range(0,len(words),9)]
    total=sum(len(x.split()) for x in chunks); t=0.0; sr=[]; vt=["WEBVTT",""]
    for i,x in enumerate(chunks,1):
        span=dur*len(x.split())/total; end=min(dur,t+span)
        sr += [str(i),f"{stamp(t)} --> {stamp(end)}",x,""]
        vt += [f"{stamp(t,False)} --> {stamp(end,False)}",x,""]
        t=end
    sp=OUT/f"{slug}.srt"; vp=OUT/f"{slug}.vtt"
    sp.write_text("\n".join(sr),encoding="utf-8"); vp.write_text("\n".join(vt),encoding="utf-8")
    return sp,vp

def audio(text,slug):
    tp=OUT/f"{slug}.txt"; wp=OUT/f"{slug}.wav"; tp.write_text(text,encoding="utf-8")
    for speed in [132,126,138,120,145]:
        sh("espeak","-v","it","-s",speed,"-f",tp,"-w",wp)
        d=duration(wp)
        if 50<=d<=70: break
    return wp

def video(src,kind,wav,srt,slug):
    out=OUT/f"{slug}-spoken-test.mp4"; d=duration(wav)
    sf=str(srt).replace("\\","/").replace(":","\\:")
    vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,"+f"subtitles='{sf}':force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H66000000,BorderStyle=3,Outline=2,Alignment=2,MarginV=160'"
    if kind=="video":
        sh("ffmpeg","-y","-stream_loop","-1","-i",src,"-i",wav,"-map","0:v:0","-map","1:a:0","-vf",vf,"-t",f"{d:.3f}","-r","25","-c:v","libx264","-preset","veryfast","-crf","27","-c:a","aac","-b:a","128k","-movflags","+faststart",out)
    else:
        sh("ffmpeg","-y","-loop","1","-i",src,"-i",wav,"-map","0:v:0","-map","1:a:0","-vf",vf,"-t",f"{d:.3f}","-r","25","-c:v","libx264","-preset","veryfast","-crf","27","-c:a","aac","-b:a","128k","-movflags","+faststart",out)
    return out,d

def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else {"version":6,"jobs":[]}

def main():
    if not SB or not KEY: raise RuntimeError("Supabase service configuration missing")
    cfg=json.loads(MANIFEST.read_text(encoding="utf-8"))
    clients=rest("f1_content_clients",{"select":"id,name,slug","status":"eq.ATTIVO"})
    idslug={str(x["id"]):x["slug"] for x in clients}
    channels=rest("f1_client_social_channels",{"select":"client_id,platform,provider,account_name,external_channel_id,enabled,verified,connection_status,scopes"})
    rows=[]
    for x in channels:
        slug=idslug.get(str(x.get("client_id")))
        if slug in cfg["clients"]:
            x=dict(x); x["slug"]=slug; rows.append(x)

    tid={}
    for x in rows:
        if x.get("platform")=="tiktok" and x.get("enabled") and x.get("verified") and x.get("external_channel_id"):
            tid.setdefault(str(x["external_channel_id"]),[]).append(x["slug"])
    duplicate={k:v for k,v in tid.items() if len(v)>1}

    q=load_queue(); jobs=q.setdefault("jobs",[]); existing={str(x.get("id")) for x in jobs}
    report={"test_id":cfg["test_id"],"created_at":datetime.now(timezone.utc).isoformat(),"duplicated_tiktok_accounts":duplicate,"clients":{}}

    for slug,c in cfg["clients"].items():
        print("\n===",c["name"],"===")
        src=download(c["source_file"]); wav=audio(c["narration"],slug); d=duration(wav)
        srt,vtt=subs(c["narration"],d,slug); mp4,d=video(src,c["kind"],wav,srt,slug)
        rel=str(mp4.relative_to(ROOT)).replace("\\","/")
        cr={"territory":c["territory"],"source_page":c["source_page"],"license":c["license"],"author":c["author"],"duration_seconds":round(d,2),"narration":c["narration"],"caption_master":c["narration"]+"\n\n"+c["cta"]+"\n\n"+" ".join(c["hashtags"]),"audio_caption_match":1.0,"srt":str(srt.relative_to(ROOT)),"vtt":str(vtt.relative_to(ROOT)),"jobs":[],"skipped":[]}
        for x in [r for r in rows if r["slug"]==slug]:
            p=str(x.get("platform") or "").lower(); p="linkedin" if p=="linkedin-page" else p
            if p not in {"facebook","instagram","linkedin","tiktok","youtube"}: continue
            if not (x.get("enabled") and x.get("verified") and x.get("connection_status")=="COLLEGATO"):
                cr["skipped"].append({"platform":p,"reason":"NON_COLLEGATO"}); continue
            if p=="tiktok" and str(x.get("external_channel_id") or "") in duplicate:
                cr["skipped"].append({"platform":"tiktok","reason":"BLOCCATO_ACCOUNT_DUPLICATO","account_name":x.get("account_name"),"external_channel_id":x.get("external_channel_id"),"mapped_clients":duplicate[str(x.get("external_channel_id"))]}); continue
            jid=f"multiclient-test-{cfg['test_id']}-{slug}-{p}"
            cap=c["narration"]+"\n\n"+c["cta"]+"\n\n"+" ".join(c["hashtags"])
            job={"id":jid,"enabled":True,"status":"ready","client_id":slug,"client_name":c["name"],"title":c["name"]+" · test parlato 60 secondi","caption":cap,"format":"reel","media":[rel],"scheduled_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"platforms":["linkedin-page" if p=="linkedin" else p],"published_platforms":[],"source":"MULTICLIENT_LICENSED_TEST","provider":x.get("provider") or "direct","provider_channel_id":x.get("external_channel_id"),"created_by":"multiclient-test-generator","autonomous_publish":True,"license":{"source":c["source_page"],"license":c["license"],"author":c["author"]},"audio_caption_match":1.0}
            if p=="youtube": job["youtube_privacy_status"]="private"
            if jid not in existing: jobs.append(job); existing.add(jid)
            cr["jobs"].append({"job_id":jid,"platform":p,"provider":job["provider"],"account_name":x.get("account_name"),"external_channel_id":x.get("external_channel_id")})
        report["clients"][slug]=cr

    q["version"]=max(int(q.get("version") or 0),6); q["updated_at"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
    QUEUE.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","jobs":sum(len(x["jobs"]) for x in report["clients"].values()),"tiktok_duplicate":duplicate},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
