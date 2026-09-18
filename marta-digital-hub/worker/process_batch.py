#!/usr/bin/env python3
import json, os, re, subprocess, sys, tempfile, urllib.request, urllib.error, unicodedata
from pathlib import Path
from faster_whisper import WhisperModel

EDGE_URL=os.environ.get("MARTA_EDGE_URL","https://nqnmlsmeiynxbdojeyjt.supabase.co/functions/v1/marta-media-worker")
AUDIENCE="marta-digital-hub"
MODEL_NAME=os.environ.get("MARTA_WHISPER_MODEL","base")
BATCH_MAX=16

def get_oidc():
    url=os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    token=os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
    sep="&" if "?" in url else "?"
    req=urllib.request.Request(url+sep+"audience="+AUDIENCE,headers={"Authorization":"bearer "+token})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.load(r)["value"]

def edge(payload):
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(EDGE_URL,data=data,method="POST",headers={
        "Authorization":"Bearer "+get_oidc(),
        "Content-Type":"application/json"
    })
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail=e.read().decode("utf-8","replace")[:2000]
        raise RuntimeError(f"Edge {e.code}: {detail}") from e

def download(url,path):
    req=urllib.request.Request(url,headers={"User-Agent":"MartaDigitalHubWorker/1.0"})
    with urllib.request.urlopen(req,timeout=300) as r,open(path,"wb") as out:
        while True:
            chunk=r.read(1024*1024)
            if not chunk: break
            out.write(chunk)

def upload_signed(url,path,content_type="audio/mpeg"):
    data=Path(path).read_bytes()
    req=urllib.request.Request(url,data=data,method="PUT",headers={"Content-Type":content_type})
    with urllib.request.urlopen(req,timeout=300) as r:
        if r.status<200 or r.status>=300:
            raise RuntimeError(f"Upload audio rifiutato: {r.status}")

def clean(text):
    return re.sub(r"\s+"," ",str(text or "")).strip()

def clip(text,maxlen):
    s=clean(text)
    if len(s)<=maxlen:return s
    cut=s[:maxlen-1]
    p=max(cut.rfind(". "),cut.rfind("! "),cut.rfind("? "),cut.rfind(" "))
    if p>int(maxlen*.65):cut=cut[:p+1]
    return cut.strip()+"…"

def first_sentence(text,maxlen=180):
    s=clean(text)
    m=re.match(r"^(.{1,220}?[.!?])(?:\s|$)",s)
    return clip(m.group(1) if m else s,maxlen)

def hashtag(value):
    s=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode()
    words=re.findall(r"[A-Za-z0-9]+",s)
    if not words:return None
    return "#"+("".join(w[:1].upper()+w[1:] for w in words))[:50]

def joined(*parts):
    return "\n\n".join(p for p in parts if p).strip()

def caption_pack(transcript,title="",category=""):
    body=clean(transcript)
    hook=first_sentence(body,180) or clip(title,180)
    cta="Per approfondire, scrivimi in privato."
    tags=[x for x in [hashtag(category),"#MartaRuffino","#PelvicamenteMarta"] if x]
    tag_line=" ".join(tags)
    def row(variants):
        return {"hook":hook,"cta":cta,"hashtags":tags,"variants":variants}
    return {
        "instagram":row({"short":joined(hook,cta,tag_line),"medium":joined(hook,clip(body,1800),cta,tag_line),"deep":joined(hook,clip(body,4200),cta,tag_line)}),
        "facebook":row({"short":joined(hook,cta),"medium":joined(hook,clip(body,2400),cta),"deep":joined(hook,clip(body,5200),cta)}),
        "tiktok":row({"short":joined(clip(hook,120),cta,tag_line),"medium":joined(clip(hook,140),clip(body,850),cta,tag_line),"deep":joined(clip(hook,160),clip(body,1500),cta,tag_line)}),
        "linkedin":row({"short":joined(hook,cta),"medium":joined(hook,clip(body,2200),cta),"deep":joined(hook,clip(body,4500),cta)}),
        "youtube":row({"title":clip(title or hook,100),"description":joined(hook,clip(body,5000),cta),"tags":[x.lstrip("#") for x in tags],"short_text":joined(clip(hook,140),cta)})
    }

def extract_audio(video,audio):
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(video),
        "-vn","-ac","1","-ar","16000","-b:a","64k","-map_metadata","-1",str(audio)
    ],check=True,timeout=900)

def transcribe(model,audio):
    segments,_=model.transcribe(str(audio),language="it",vad_filter=True,beam_size=5,condition_on_previous_text=True)
    text=" ".join(clean(s.text) for s in segments if clean(s.text)).strip()
    if not text:
        raise RuntimeError("Whisper non ha rilevato parlato comprensibile")
    if len(text)>100000:
        text=text[:100000]
    return text

def main():
    claimed=edge({"action":"claim","limit":BATCH_MAX})
    jobs=list(claimed.get("jobs") or [])[:BATCH_MAX]
    print(f"Marta media pipeline: {len(jobs)} job (max {BATCH_MAX})")
    if not jobs:return 0

    model=WhisperModel(MODEL_NAME,device="cpu",compute_type="int8")
    completed=failed=0
    for index,job in enumerate(jobs,1):
        jid=job["job_id"]
        audio_path=job.get("audio_path")
        print(f"[{index}/{len(jobs)}] {job.get('title') or job.get('filename') or jid}")
        with tempfile.TemporaryDirectory(prefix="marta-media-") as td:
            ext={"video/mp4":".mp4","video/quicktime":".mov","video/webm":".webm"}.get(job.get("mime_type"),".video")
            video=Path(td)/("input"+ext)
            audio=Path(td)/"audio.mp3"
            try:
                download(job["download_url"],video)
                extract_audio(video,audio)
                transcript=transcribe(model,audio)
                captions=caption_pack(transcript,job.get("title",""),job.get("category",""))
                upload_signed(job["audio_upload_url"],audio)
                edge({
                    "action":"complete","job_id":jid,"transcript":transcript,
                    "audio_path":audio_path,"audio_size":audio.stat().st_size,
                    "model":"faster-whisper-"+MODEL_NAME,"captions":captions
                })
                completed+=1
                print(f"  ✓ trascrizione {len(transcript)} caratteri; 5 caption DA_APPROVARE")
            except Exception as exc:
                failed+=1
                msg=(str(exc) or exc.__class__.__name__)[:1800]
                print("  ✗ "+msg,file=sys.stderr)
                try:edge({"action":"fail","job_id":jid,"error":msg,"audio_path":audio_path})
                except Exception as fail_exc:print("  ! impossibile registrare errore: "+str(fail_exc),file=sys.stderr)
    print(f"Completati={completed} Errori={failed}")
    return 0 if completed or not failed else 1

if __name__=="__main__":
    raise SystemExit(main())
