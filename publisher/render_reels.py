#!/usr/bin/env python3
"""Render clean branded Reel and carousel assets for F1 Immobiliare and Real Media Pro."""
from __future__ import annotations

import hashlib, json, os, shutil, subprocess, sys, tempfile, time
from io import BytesIO
from pathlib import Path
from typing import Any
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
QUEUE_PATH=ROOT/'publisher'/'queue.json'
CLIENT_DIR=ROOT/'publisher'/'clients'
PHOTO_CACHE=Path(os.getenv('SOCIAL_PHOTO_CACHE',str(ROOT/'.cache'/'f1-photos')))
SERIF=Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf')
SANS=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
SANS_B=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
_BG:dict[str,Image.Image]={}

RMP_SOURCES=[
 {"url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Interpreting_Ecommerce_Website_Analytics.jpg/1280px-Interpreting_Ecommerce_Website_Analytics.jpg","credit":"Zuko.io Images / Wikimedia Commons · CC BY 2.0"},
 {"url":"https://upload.wikimedia.org/wikipedia/commons/6/6a/Social_Media_Marketing_Image.jpg","credit":"Today Testing / Wikimedia Commons · CC licensed"},
]

def load_json(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def cfg_for(cid:str)->dict[str,Any]: return load_json(CLIENT_DIR/f'{cid}.json')
def ff(path:Path,size:int): return ImageFont.truetype(str(path),size)

def fallback_photo()->Image.Image:
    im=Image.new('RGB',(1600,1100),'#111820'); d=ImageDraw.Draw(im)
    for y in range(im.height):
        t=y/im.height; c=int(32-16*t); d.line((0,y,im.width,y),fill=(c,c+10,c+8))
    return im

def download(src:dict[str,Any])->Image.Image:
    url=str(src.get('url') or '')
    if not url:return fallback_photo()
    if url in _BG:return _BG[url].copy()
    PHOTO_CACHE.mkdir(parents=True,exist_ok=True)
    cp=PHOTO_CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.jpg')
    if cp.exists() and cp.stat().st_size>12000:
        im=Image.open(cp).convert('RGB'); _BG[url]=im; return im.copy()
    headers={'User-Agent':'Mozilla/5.0 Open-Social-Scheduler/1.0','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'}
    for n in range(3):
        try:
            r=requests.get(url,headers=headers,timeout=60); r.raise_for_status()
            im=Image.open(BytesIO(r.content)).convert('RGB'); im.save(cp,'JPEG',quality=90,optimize=True); _BG[url]=im; return im.copy()
        except Exception as e:
            if n==2: print(f'WARN image {url}: {e}',file=sys.stderr)
            time.sleep(1+n)
    return fallback_photo()

def sources(cfg:dict[str,Any])->list[dict[str,Any]]:
    own=list(cfg.get('brand',{}).get('photo_sources',[]) or [])
    if own:return own
    if str(cfg.get('id'))=='real-media-pro':return RMP_SOURCES
    return [{"url":"","credit":""}]

def compose(im:Image.Image,w:int,h:int)->Image.Image:
    # Full-bleed image, no giant black panel. Keep the subject visible.
    bg=ImageOps.fit(im,(w,h),method=Image.Resampling.LANCZOS,centering=(0.5,0.5)).convert('RGBA')
    shade=Image.new('RGBA',(w,h),(0,0,0,0)); sd=ImageDraw.Draw(shade)
    for y in range(h):
        if y<h*.18:a=70
        elif y>h*.72:a=95
        else:a=16
        sd.line((0,y,w,y),fill=(0,0,0,a))
    bg.alpha_composite(shade)
    return bg.convert('RGB')

def wrap(draw:ImageDraw.ImageDraw,text:str,font:ImageFont.FreeTypeFont,maxw:int)->list[str]:
    words=str(text).split(); lines=[]; cur=''
    for word in words:
        test=(cur+' '+word).strip()
        if draw.textbbox((0,0),test,font=font)[2]<=maxw: cur=test
        else:
            if cur: lines.append(cur)
            cur=word
    if cur:lines.append(cur)
    return lines[:4]

def draw_logo(im:Image.Image,cfg:dict[str,Any],top:int)->None:
    d=ImageDraw.Draw(im); brand=cfg.get('brand',{}); cid=str(cfg.get('id'))
    if cid=='f1-immobiliare' and brand.get('logo_vectors'):
        pw=int(im.width*.30); ph=int(pw*.57); x=(im.width-pw)//2
        d.rounded_rectangle((x,top,x+pw,top+ph),radius=28,fill=(3,6,4,220),outline=brand.get('accent','#92C205'),width=2)
        scale=pw*.74/500; ox=x+int(pw*.13); oy=top+int(ph*.01)
        for poly in brand['logo_vectors'].get('green',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill=brand.get('accent','#92C205'))
        for poly in brand['logo_vectors'].get('white',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill='#FFFFFF')
        f=ff(SANS_B,max(17,int(pw*.05))); label='IMMOBILIARE'; box=d.textbbox((0,0),label,font=f)
        d.text(((im.width-(box[2]-box[0]))/2,top+ph-int(ph*.20)),label,font=f,fill='white')
    else:
        text='REAL MEDIA PRO'; f=ff(SANS_B,46 if im.width>=1000 else 34); box=d.textbbox((0,0),text,font=f); pad=24
        x=(im.width-(box[2]-box[0]))/2
        d.rounded_rectangle((x-pad,top,x+(box[2]-box[0])+pad,top+(box[3]-box[1])+34),radius=22,fill=(5,12,22,225),outline=brand.get('accent','#2D7FF9'),width=2)
        d.text((x,top+13),text,font=f,fill='white')

def draw_whatsapp(im:Image.Image,cfg:dict[str,Any],content_format:str)->None:
    d=ImageDraw.Draw(im); brand=cfg.get('brand',{}); green='#25D366'; phone='371 370 8294'
    h=92 if content_format=='reel' else 72; y=im.height-h-34; w=int(im.width*.70); x=(im.width-w)//2
    d.rounded_rectangle((x,y,x+w,y+h),radius=h//2,fill=(3,8,6,228),outline=green,width=3)
    r=int(h*.28); cx=x+48; cy=y+h//2; d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=green)
    ficon=ff(SANS_B,int(h*.28)); d.text((cx-int(h*.12),cy-int(h*.18)),'☎',font=ficon,fill='white')
    f=ff(SANS_B,37 if content_format=='reel' else 29); txt=f'WhatsApp  {phone}'; box=d.textbbox((0,0),txt,font=f)
    d.text((x+88,y+(h-(box[3]-box[1]))/2-4),txt,font=f,fill='white')

def draw_slide(raw:str,cfg:dict[str,Any],src:dict[str,Any],w:int,h:int,no:int,count:int,fmt:str)->Image.Image:
    im=compose(download(src),w,h); d=ImageDraw.Draw(im); brand=cfg.get('brand',{}); accent=brand.get('accent','#92C205')
    draw_logo(im,cfg,int(h*.025))
    # ONE hook only; no subtitle blocks, no counters, no campaign footer.
    hook=str(raw).split('|')[0].strip() if raw else ''
    if hook:
        fs=78 if fmt=='reel' else 62; f=ff(SANS_B,fs); lines=wrap(d,hook,f,int(w*.78))
        maxw=max((d.textbbox((0,0),ln,font=f)[2] for ln in lines),default=0); lh=fs+10; total=lh*len(lines); y=int(h*.48-total/2)
        pad=34; x=(w-maxw)//2
        d.rounded_rectangle((x-pad,y-pad,w-x+pad,y+total+pad),radius=34,fill=(0,0,0,155))
        for ln in lines:
            box=d.textbbox((0,0),ln,font=f); d.text(((w-(box[2]-box[0]))/2,y),ln,font=f,fill='white',stroke_width=2,stroke_fill='black'); y+=lh
        # small green accent line
        d.rounded_rectangle((int(w*.36),int(h*.61),int(w*.64),int(h*.61)+8),radius=4,fill=accent)
    draw_whatsapp(im,cfg,fmt)
    credit=str(src.get('credit') or '')
    if credit:
        cf=ff(SANS,14 if fmt=='carousel' else 16); d.text((18,h-20),credit,font=cf,fill=(230,230,230))
    return im

def synth(job:dict[str,Any],cfg:dict[str,Any],out:Path)->Path|None:
    vc=cfg.get('brand',{}).get('voice',{}); text=str(job.get('voiceover') or '').strip()
    if not vc.get('enabled',False) or not text:return None
    model=str(vc.get('model') or 'it_IT-paola-medium'); data=Path(os.getenv('PIPER_DATA_DIR',str(ROOT/'.cache'/'piper')))
    subprocess.run([sys.executable,'-m','piper','-m',model,'--data-dir',str(data),'-f',str(out),'--',text],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out if out.exists() else None

def audiodur(p:Path|None)->float:
    if not p:return 0.0
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)],capture_output=True,text=True,check=True)
    try:return float(r.stdout.strip())
    except:return 0.0

def ready(job:dict[str,Any])->bool:
    m=job.get('media'); vals=m if isinstance(m,list) else [m]; vals=[str(x) for x in vals if x]
    return bool(vals) and all((ROOT/x).exists() and (ROOT/x).stat().st_size>10000 for x in vals)

def render_reel(job:dict[str,Any],cfg:dict[str,Any])->Path:
    rc=cfg.get('brand',{}).get('reel',{}); w,h=int(rc.get('width',1080)),int(rc.get('height',1920)); slides=list(job.get('slides') or [job.get('title','')]); out=ROOT/str(job['media']); out.parent.mkdir(parents=True,exist_ok=True)
    ss=sources(cfg)
    with tempfile.TemporaryDirectory(prefix='oss-reel-') as td:
        tmp=Path(td); voice=synth(job,cfg,tmp/'voice.wav'); dur=audiodur(voice); sec=max(2.5,(dur+1)/max(1,len(slides))) if dur else float(rc.get('seconds_per_slide',3.0)); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); frames=[]
        for i,raw in enumerate(slides,1):
            p=tmp/f's{i:02d}.jpg'; draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,i,len(slides),'reel').save(p,'JPEG',quality=92,optimize=True); frames.append(p)
        con=tmp/'concat.txt'
        with con.open('w',encoding='utf-8') as fh:
            for p in frames: fh.write(f"file '{p.as_posix()}'\nduration {sec:.3f}\n")
            fh.write(f"file '{frames[-1].as_posix()}'\n")
        cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',str(con)]
        if voice:cmd+=['-i',str(voice)]
        cmd+=['-vf','fps=30,format=yuv420p','-c:v','libx264','-crf','20','-preset','medium','-movflags','+faststart']
        if voice:cmd+=['-c:a','aac','-b:a','160k','-af','apad','-shortest']
        cmd+=[str(out)]; subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out

def render_carousel(job:dict[str,Any],cfg:dict[str,Any])->list[Path]:
    cc=cfg.get('brand',{}).get('carousel',{}); w,h=int(cc.get('width',1080)),int(cc.get('height',1350)); slides=list(job.get('slides') or []); media=list(job.get('media') or []); ss=sources(cfg); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); outs=[]
    if len(slides)!=len(media):raise RuntimeError(f"Carousel {job.get('id')} mismatch")
    for i,(raw,rel) in enumerate(zip(slides,media),1):
        out=ROOT/str(rel); out.parent.mkdir(parents=True,exist_ok=True); draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,i,len(slides),'carousel').save(out,'JPEG',quality=92,optimize=True); outs.append(out)
    return outs

def main()->int:
    if not QUEUE_PATH.exists():return 0
    q=load_json(QUEUE_PATH); n=0
    for job in q.get('jobs',[]):
        if not job.get('enabled',True) or job.get('status') in {'scheduled','published','disabled'}:continue
        if not job.get('client_id') or not job.get('media'):continue
        cfg=cfg_for(str(job['client_id']))
        if str(job.get('format') or 'reel')=='carousel':render_carousel(job,cfg)
        else:render_reel(job,cfg)
        n+=1
    print(f'Rendered {n} social asset set(s).')
    return 0
if __name__=='__main__':raise SystemExit(main())
