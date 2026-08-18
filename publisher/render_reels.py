#!/usr/bin/env python3
"""Render 60-second Reels and carousels for F1 Immobiliare and Real Media Pro."""
from __future__ import annotations
import base64, hashlib, json, os, subprocess, sys, tempfile, time
from io import BytesIO
from pathlib import Path
from typing import Any
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
QUEUE_PATH=ROOT/'publisher'/'queue.json'
CLIENT_DIR=ROOT/'publisher'/'clients'
ASSET_DIR=ROOT/'publisher'/'assets'
PHOTO_CACHE=Path(os.getenv('SOCIAL_PHOTO_CACHE',str(ROOT/'.cache'/'social-photos')))
SANS=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
SANS_B=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
_BG={}
_PRESENTER={}

F1_HOUSE_SOURCES=[
 {"url":"https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential house"},
 {"url":"https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential house"},
 {"url":"https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential interior"},
 {"url":"https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential interior"},
]
RMP_SOURCES=[
 {"url":"https://cdn.pixabay.com/photo/2018/07/31/14/52/ecommerce-3575280_1280.jpg","credit":"Pixabay · ecommerce"},
 {"url":"https://cdn.pixabay.com/photo/2019/06/15/16/06/online-4275963_1280.jpg","credit":"Pixabay · online shopping"},
 {"url":"https://cdn.pixabay.com/photo/2020/09/15/15/17/laptop-5573883_1280.jpg","credit":"Pixabay · digital marketing"},
]

def load_json(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def cfg_for(cid:str)->dict[str,Any]: return load_json(CLIENT_DIR/f'{cid}.json')
def ff(path:Path,size:int): return ImageFont.truetype(str(path),size)

def fallback(seed:int=0)->Image.Image:
    w,h=1600,1100
    im=Image.new('RGB',(w,h),'#edf2ee'); d=ImageDraw.Draw(im)
    d.rectangle((90,80,w-90,h-90),fill='#ffffff',outline='#d5ddd7',width=4)
    d.rounded_rectangle((250,210,1350,850),radius=34,fill='#f7f8f7',outline='#cdd5d0',width=4)
    d.rectangle((350,300,1250,680),fill='#dce6df')
    d.text((500,730),'REAL MEDIA PRO',font=ff(SANS_B,72),fill='#1f2622')
    return im

def load_presenter(name:str):
    if name in _PRESENTER:return _PRESENTER[name].copy()
    p=ASSET_DIR/f'{name}_presenter.jpg.b64'
    if not p.exists(): return None
    try:
        raw=base64.b64decode(p.read_text(encoding='utf-8').strip())
        im=Image.open(BytesIO(raw)).convert('RGB')
        _PRESENTER[name]=im
        return im.copy()
    except Exception:
        return None

def download(src:dict[str,Any])->Image.Image:
    url=str(src.get('url') or '')
    if not url:return fallback()
    if url in _BG:return _BG[url].copy()
    PHOTO_CACHE.mkdir(parents=True,exist_ok=True)
    cp=PHOTO_CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.jpg')
    if cp.exists() and cp.stat().st_size>12000:
        im=Image.open(cp).convert('RGB'); _BG[url]=im; return im.copy()
    headers={'User-Agent':'Mozilla/5.0 Open-Social-Scheduler/2.0','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'}
    for n in range(3):
        try:
            r=requests.get(url,headers=headers,timeout=40)
            r.raise_for_status()
            im=Image.open(BytesIO(r.content)).convert('RGB')
            im.save(cp,'JPEG',quality=92,optimize=True)
            _BG[url]=im
            return im.copy()
        except Exception as e:
            if n==2: print(f'WARN image {url}: {e}',file=sys.stderr)
            time.sleep(1+n)
    return fallback()

def sources(cfg):
    cid=str(cfg.get('id'))
    if cid=='f1-immobiliare': return F1_HOUSE_SOURCES
    if cid=='real-media-pro': return RMP_SOURCES
    own=list(cfg.get('brand',{}).get('photo_sources',[]) or [])
    return own or RMP_SOURCES

def compose(im,w,h):
    bg=ImageOps.fit(im,(w,h),method=Image.Resampling.LANCZOS,centering=(0.5,0.5)).convert('RGBA')
    shade=Image.new('RGBA',(w,h),(0,0,0,0)); sd=ImageDraw.Draw(shade)
    for y in range(h):
        a=40 if y<h*.18 else (58 if y>h*.78 else 4)
        sd.line((0,y,w,y),fill=(0,0,0,a))
    bg.alpha_composite(shade)
    return bg.convert('RGB')

def wrap(draw,text,font,maxw):
    words=str(text).split(); lines=[]; cur=''
    for word in words:
        test=(cur+' '+word).strip()
        if draw.textbbox((0,0),test,font=font)[2]<=maxw: cur=test
        else:
            if cur:lines.append(cur)
            cur=word
    if cur:lines.append(cur)
    return lines[:4]

def draw_logo(im,cfg,top):
    d=ImageDraw.Draw(im); cid=str(cfg.get('id')); brand=cfg.get('brand',{})
    if cid=='f1-immobiliare' and brand.get('logo_vectors'):
        pw=int(im.width*.27); ph=int(pw*.57); x=(im.width-pw)//2
        scale=pw*.74/500; ox=x+int(pw*.13); oy=top+int(ph*.01)
        for poly in brand['logo_vectors'].get('green',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill=brand.get('accent','#92C205'))
        for poly in brand['logo_vectors'].get('white',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill='#FFFFFF')
        f=ff(SANS_B,max(16,int(pw*.05))); label='IMMOBILIARE'; box=d.textbbox((0,0),label,font=f)
        d.text(((im.width-(box[2]-box[0]))/2,top+ph-int(ph*.20)),label,font=f,fill='white')
    else:
        text='REAL MEDIA PRO'; f=ff(SANS_B,52); box=d.textbbox((0,0),text,font=f); pad=22
        x=(im.width-(box[2]-box[0]))/2
        d.rounded_rectangle((x-pad,top,x+(box[2]-box[0])+pad,top+82),radius=24,fill=(255,255,255,235),outline='#61A844',width=3)
        d.text((x,top+12),text,font=f,fill='#151a17')

def draw_whatsapp(im,fmt):
    d=ImageDraw.Draw(im); phone='371 370 8294'
    h=94 if fmt=='reel' else 74; y=im.height-h-24; w=int(im.width*.76); x=(im.width-w)//2
    d.rounded_rectangle((x,y,x+w,y+h),radius=h//2,fill=(255,255,255,240),outline='#61A844',width=3)
    f=ff(SANS_B,40 if fmt=='reel' else 28)
    d.text((x+62,y+20),f'WHATSAPP  {phone}',font=f,fill='#111111')

def draw_presenter(im,name):
    if not name:return
    pic=load_presenter(name)
    if pic is None:return
    target_h=int(im.height*.28); ratio=target_h/pic.height; target_w=int(pic.width*ratio)
    pic=pic.resize((target_w,target_h),Image.Resampling.LANCZOS)
    mask=Image.new('L',pic.size,0); md=ImageDraw.Draw(mask); md.rounded_rectangle((0,0,pic.width-1,pic.height-1),radius=28,fill=255)
    tile=Image.new('RGBA',pic.size,(0,0,0,0)); tile.paste(pic,(0,0),mask)
    base=im.convert('RGBA'); base.alpha_composite(tile,(im.width-target_w-22,im.height-target_h-115))
    im.paste(base.convert('RGB'))

def draw_slide(raw,cfg,src,w,h,fmt,presenter=None):
    im=compose(download(src),w,h); d=ImageDraw.Draw(im); cid=str(cfg.get('id'))
    draw_logo(im,cfg,int(h*.025))
    hook=str(raw).split('|')[0].strip() if raw else ''
    if hook:
        fs=78 if fmt=='reel' else 60; f=ff(SANS_B,fs); lines=wrap(d,hook,f,int(w*.80))
        lh=fs+8; total=lh*len(lines); y=int(h*.40-total/2)
        for ln in lines:
            box=d.textbbox((0,0),ln,font=f)
            fill='#61A844' if cid=='real-media-pro' else 'white'
            d.text(((w-(box[2]-box[0]))/2,y),ln,font=f,fill=fill,stroke_width=2,stroke_fill='#111111')
            y+=lh
    if fmt=='reel': draw_presenter(im,presenter)
    draw_whatsapp(im,fmt)
    return im

def synth(job,cfg,out):
    vc=cfg.get('brand',{}).get('voice',{}); text=str(job.get('voiceover') or '').strip()
    if not vc.get('enabled',False) or not text:return None
    model=str(vc.get('model') or 'it_IT-paola-medium')
    data=Path(os.getenv('PIPER_DATA_DIR',str(ROOT/'.cache'/'piper')))
    subprocess.run([sys.executable,'-m','piper','-m',model,'--data-dir',str(data),'-f',str(out),'--',text],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out if out.exists() else None

def render_reel(job,cfg):
    rc=cfg.get('brand',{}).get('reel',{}); w,h=int(rc.get('width',1080)),int(rc.get('height',1920))
    slides=list(job.get('slides') or [job.get('title','')]); out=ROOT/str(job['media']); out.parent.mkdir(parents=True,exist_ok=True)
    ss=sources(cfg); target=float(rc.get('target_seconds',60) or 60); sec=target/max(1,len(slides)); presenter=str(job.get('_presenter') or '') or None
    with tempfile.TemporaryDirectory(prefix='oss-reel-') as td:
        tmp=Path(td); voice=synth(job,cfg,tmp/'voice.wav'); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); frames=[]
        for i,raw in enumerate(slides,1):
            p=tmp/f's{i:02d}.jpg'; draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,'reel',presenter).save(p,'JPEG',quality=92,optimize=True); frames.append(p)
        con=tmp/'concat.txt'
        with con.open('w',encoding='utf-8') as fh:
            for p in frames: fh.write(f"file '{p.as_posix()}'\nduration {sec:.3f}\n")
            fh.write(f"file '{frames[-1].as_posix()}'\n")
        cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',str(con)]
        if voice:cmd+=['-i',str(voice)]
        cmd+=['-vf','fps=30,format=yuv420p','-c:v','libx264','-crf','20','-preset','medium','-movflags','+faststart']
        if voice:cmd+=['-c:a','aac','-b:a','160k','-af','apad']
        cmd+=['-t',f'{target:.3f}',str(out)]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out

def render_carousel(job,cfg):
    cc=cfg.get('brand',{}).get('carousel',{}); w,h=int(cc.get('width',1080)),int(cc.get('height',1350))
    slides=list(job.get('slides') or []); media=list(job.get('media') or []); ss=sources(cfg); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0)
    for i,(raw,rel) in enumerate(zip(slides,media),1):
        out=ROOT/str(rel); out.parent.mkdir(parents=True,exist_ok=True)
        draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,'carousel').save(out,'JPEG',quality=92,optimize=True)

def main():
    if not QUEUE_PATH.exists():return 0
    q=load_json(QUEUE_PATH); reel_count={}
    for job in q.get('jobs',[]):
        if not job.get('enabled',True) or job.get('status') in {'scheduled','published','disabled'}:continue
        if not job.get('client_id') or not job.get('media'):continue
        cid=str(job['client_id']); cfg=cfg_for(cid)
        if str(job.get('format') or 'reel')=='carousel':
            render_carousel(job,cfg)
        else:
            k=reel_count.get(cid,0)
            if k%2==0: job['_presenter']='joseph' if (k//2)%2==0 else 'francesca'
            else: job['_presenter']=''
            reel_count[cid]=k+1
            render_reel(job,cfg)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
