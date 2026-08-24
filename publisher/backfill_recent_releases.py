#!/usr/bin/env python3
import base64, json, os, shutil, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image

REPO=os.environ["GITHUB_REPOSITORY"]; TOKEN=os.environ["GH_TOKEN"]
ROOT=Path("/tmp/social-backfill"); ROOT.mkdir(parents=True,exist_ok=True)
cutoff=(datetime.now(ZoneInfo("Europe/Rome")).date()-timedelta(days=2)).isoformat()
headers={"Authorization":f"Bearer {TOKEN}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}

def api(path):
    req=urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",headers=headers)
    with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)

def queue_at(sha):
    data=api(f"contents/publisher/queue.json?ref={sha}")
    return json.loads(base64.b64decode(data["content"]).decode("utf-8"))

def manual_candidates(job):
    cid=job.get("client_id",""); pos=int(job.get("cycle_position") or 1)
    if cid=="f1-immobiliare":
        folder=Path("publisher/manual_images/f1-immobiliare/RIC LAVORO F1") if pos==2 else Path("publisher/manual_images/f1-immobiliare")
    else:
        folder=Path("publisher/manual_images/real-media-pro/RIC LAVORO RMP") if pos==2 else Path("publisher/manual_images/real-media-pro")
    if not folder.exists(): return []
    items=folder.rglob("*") if pos==2 else folder.glob("*")
    return sorted(p for p in items if p.is_file() and p.suffix.lower() in {".jpg",".jpeg",".png",".webp"})

def save_jpeg(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with Image.open(source) as im:
        if im.mode not in ("RGB","L"): im=im.convert("RGB")
        im.save(target,"JPEG",quality=94,optimize=True)

def download(url,target):
    req=urllib.request.Request(url,headers={"User-Agent":"Open-Social-Scheduler/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r,open(target,"wb") as f:shutil.copyfileobj(r,f)

commits=api(f"commits?path=publisher/queue.json&since={cutoff}T00:00:00Z&per_page=100")
cycles={}
for cm in commits:
    try:
        q=queue_at(cm["sha"]); key=str(q.get("current_cycle") or "")
        if not key or key[:10]<cutoff or key in cycles: continue
        cycles[key]=q
    except Exception as exc: print("SKIP COMMIT",cm.get("sha"),exc)

for key,q in sorted(cycles.items()):
    tag="social-preview-archive-"+key.replace(":","-"); out=ROOT/tag; out.mkdir(parents=True,exist_ok=True)
    jobs=[j for j in q.get("jobs",[]) if j.get("cycle_key")==key and j.get("format")=="photo" and j.get("client_id") in {"f1-immobiliare","real-media-pro"}]
    for idx,j in enumerate(jobs):
        media=str(j.get("media") or "")
        if not media: continue
        target=out/media.removeprefix("publisher/media/generated/").replace("/","__")
        urls=j.get("visual_asset_urls") or []; source=None
        try:
            if urls:
                ext=Path(urllib.parse.urlparse(urls[0]).path).suffix or ".jpg"
                temp=out/("_source_"+str(idx)+ext); download(urls[0],temp); source=temp
            else:
                candidates=manual_candidates(j)
                if candidates: source=candidates[idx%len(candidates)]
            if source:
                save_jpeg(source,target)
                if str(source).startswith(str(out)) and source!=target: source.unlink(missing_ok=True)
        except Exception as exc: print("PHOTO UNAVAILABLE",key,j.get("id"),exc)
    archived=dict(q); archived["jobs"]=jobs
    (out/"queue.json").write_text(json.dumps(archived,ensure_ascii=False,indent=2),encoding="utf-8")
    print(tag,len(jobs),len(list(out.glob("*.jpg"))))
