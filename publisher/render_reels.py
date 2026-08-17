#!/usr/bin/env python3
"""Render clean branded 60-second Reels and carousels for F1 Immobiliare and Real Media Pro."""
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
PHOTO_CACHE=Path(os.getenv('SOCIAL_PHOTO_CACHE',str(ROOT/'.cache'/'f1-photos')))
SERIF=Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf')
SANS=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
SANS_B=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
_BG:dict[str,Image.Image]={}
_PRESENTER:dict[str,Image.Image]={}

# Only residential-property imagery for F1. Unsplash images are used under the Unsplash licence.
F1_HOUSE_SOURCES=[
 {"url":"https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential house"},
 {"url":"https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential house"},
 {"url":"https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential interior"},
 {"url":"https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?auto=format&fit=crop&w=1800&q=88","credit":"Unsplash · residential interior"},
]
RMP_SOURCES=[{"url":f"generated://shopify-{i}","credit":"Original Shopify-style storefront mockup · Real Media Pro"} for i in range(1,9)]

def load_json(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def cfg_for(cid:str)->dict[str,Any]: return load_json(CLIENT_DIR/f'{cid}.json')
def ff(path:Path,size:int): return ImageFont.truetype(str(path),size)

def fallback_house(seed:int=0)->Image.Image:
    w,h=1600,1100
    im=Image.new('RGB',(w,h),'#cfd8df'); d=ImageDraw.Draw(im)
    # sky / lawn
    for y in range(h):
        if y<int(h*.62):
            t=y/(h*.62); c=(int(210-35*t),int(225-25*t),int(238-18*t))
        else:
            t=(y-h*.62)/(h*.38); c=(int(74-24*t),int(118-30*t),int(74-20*t))
        d.line((0,y,w,y),fill=c)
    # modern house
    x0=210+(seed%4)*22; y0=365
    d.rectangle((x0,y0,x0+1040,y0+450),fill='#e9e7e0')
    d.rectangle((x0+90,y0-135,x0+770,y0+95),fill='#f6f4ef')
    d.rectangle((x0+820,y0+70,x0+1100,y0+450),fill='#2c2d2d')
    # windows
    for x in (x0+150,x0+420,x0+690):
        d.rectangle((x,y0+75,x+210,y0+360),fill='#18323a',outline='#d7d7d7',width=5)
        d.line((x+105,y0+75,x+105,y0+360),fill='#7da2ad',width=3)
    d.rectangle((x0+260,y0-65,x0+650,y0+70),fill='#24414b')
    d.rectangle((x0+900,y0+160,x0+1030,y0+450),fill='#6f4d33')
    # terrace + warm lights
    d.rectangle((x0+40,y0+365,x0+820,y0+385),fill='#4e4d49')
    for x in range(x0+110,x0+790,150): d.ellipse((x,y0+395,x+18,y0+413),fill='#ffd67a')
    return im

def shopify_mockup(seed:int)->Image.Image:
    w,h=1600,1100
    im=Image.new('RGB',(w,h),'#eef1ed'); d=ImageDraw.Draw(im)
    green=(95,171,72); dark=(28,34,31); muted=(110,118,113)
    # desk shadow and browser
    d.rounded_rectangle((105,90,1495,1010),radius=34,fill='#ffffff',outline='#cdd4cf',width=4)
    d.rounded_rectangle((105,90,1495,165),radius=34,fill='#222826')
    d.rectangle((105,130,1495,165),fill='#222826')
    for x,c in [(145,'#ff6b6b'),(180,'#ffd166'),(215,'#4cd97b')]: d.ellipse((x,116,x+22,138),fill=c)
    d.rounded_rectangle((285,108,1110,145),radius=16,fill='#3a423f')
    d.text((320,114),'mystore.com',font=ff(SANS,23),fill='#dfe7e2')
    # nav
    d.text((155,205),'SHOPIFY',font=ff(SANS_B,42),fill=green)
    nav=['Home','Shop','Collections','About','Contact']
    nx=430
    for n in nav:
        d.text((nx,215),n,font=ff(SANS,22),fill=dark); nx+=155
    # hero
    palette=[('#e8e0d5','#5a6e51'),('#e5edf1','#345c6e'),('#eee6e2','#724b42'),('#e7eee4','#49624b')]
    hero_bg,hero_accent=palette[seed%len(palette)]
    d.rounded_rectangle((150,275,1450,565),radius=24,fill=hero_bg)
    d.text((205,325),'NEW COLLECTION',font=ff(SANS_B,54),fill=dark)
    d.text((205,400),'A clean storefront built for mobile and conversion.',font=ff(SANS,28),fill=muted)
    d.rounded_rectangle((205,465,430,525),radius=12,fill=green)
    d.text((255,480),'SHOP NOW',font=ff(SANS_B,24),fill='white')
    # hero products
    for i,x in enumerate((880,1060,1240)):
        col=[(82,105,82),(36,36,38),(183,167,142),(104,74,54)][(i+seed)%4]
        d.rounded_rectangle((x,320,x+125,500),radius=18,fill=col)
        d.ellipse((x+38,285,x+88,335),fill='#d8d1c5')
    # product grid
    d.text((155,610),'Featured products',font=ff(SANS_B,34),fill=dark)
    for i in range(5):
        x=155+i*255
        d.rounded_rectangle((x,665,x+210,880),radius=18,fill='#f4f5f3',outline='#dce2de',width=2)
        col=[(52,57,55),(126,144,115),(205,191,164),(87,91,98),(163,121,95)][(i+seed)%5]
        d.rounded_rectangle((x+48,710,x+162,810),radius=14,fill=col)
        d.text((x+18,902),f'Product {i+1}',font=ff(SANS_B,20),fill=dark)
        d.text((x+18,935),f'€ {49+i*25},00',font=ff(SANS,19),fill=muted)
    return im

def load_presenter(name:str)->Image.Image|None:
    if name in _PRESENTER:return _PRESENTER[name].copy()
    p=ASSET_DIR/f'{name}_presenter.jpg.b64'
    if not p.exists():return None
    try:
        raw=base64.b64decode(p.read_text(encoding='utf-8').strip())
        im=Image.open(BytesIO(raw)).convert('RGB')
        _PRESENTER[name]=im
        return im.copy()
    except Exception as e:
        print(f'WARN presenter {name}: {e}',file=sys.stderr); return None

def download(src:dict[str,Any])->Image.Image:
    url=str(src.get('url') or '')
    if url.startswith('generated://shopify-'):
        try: seed=int(url.rsplit('-',1)[1])
        except: seed=1
        return shopify_mockup(seed)
    if url.startswith('generated://house-'):
        try: seed=int(url.rsplit('-',1)[1])
        except: seed=1
        return fallback_house(seed)
    if not url:return fallback_house()
    if url in _BG:return _BG[url].copy()
    PHOTO_CACHE.mkdir(parents=True,exist_ok=True)
    cp=PHOTO_CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.jpg')
    if cp.exists() and cp.stat().st_size>12000:
        im=Image.open(cp).convert('RGB'); _BG[url]=im; return im.copy()
    headers={'User-Agent':'Mozilla/5.0 Open-Social-Scheduler/1.0','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'}
    for n in range(2):
        try:
            r=requests.get(url,headers=headers,timeout=35); r.raise_for_status()
            im=Image.open(BytesIO(r.content)).convert('RGB'); im.save(cp,'JPEG',quality=90,optimize=True); _BG[url]=im; return im.copy()
        except Exception as e:
            if n==1: print(f'WARN image {url}: {e}',file=sys.stderr)
            time.sleep(1+n)
    return fallback_house(int(hashlib.sha1(url.encode()).hexdigest()[:2],16))

def sources(cfg:dict[str,Any])->list[dict[str,Any]]:
    cid=str(cfg.get('id'))
    if cid=='f1-immobiliare': return F1_HOUSE_SOURCES
    if cid=='real-media-pro': return RMP_SOURCES
    own=list(cfg.get('brand',{}).get('photo_sources',[]) or [])
    return own or [{"url":"generated://house-1","credit":"Original residential visual"}]

def compose(im:Image.Image,w:int,h:int)->Image.Image:
    bg=ImageOps.fit(im,(w,h),method=Image.Resampling.LANCZOS,centering=(0.5,0.5)).convert('RGBA')
    shade=Image.new('RGBA',(w,h),(0,0,0,0)); sd=ImageDraw.Draw(shade)
    for y in range(h):
        if y<h*.18:a=62
        elif y>h*.74:a=88
        else:a=8
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
        pw=int(im.width*.27); ph=int(pw*.57); x=(im.width-pw)//2
        d.rounded_rectangle((x,top,x+pw,top+ph),radius=24,fill=(3,6,4,215),outline=brand.get('accent','#92C205'),width=2)
        scale=pw*.74/500; ox=x+int(pw*.13); oy=top+int(ph*.01)
        for poly in brand['logo_vectors'].get('green',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill=brand.get('accent','#92C205'))
        for poly in brand['logo_vectors'].get('white',[]): d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill='#FFFFFF')
        f=ff(SANS_B,max(16,int(pw*.05))); label='IMMOBILIARE'; box=d.textbbox((0,0),label,font=f)
        d.text(((im.width-(box[2]-box[0]))/2,top+ph-int(ph*.20)),label,font=f,fill='white')
    else:
        text='REAL MEDIA PRO'; f=ff(SANS_B,46 if im.width>=1000 else 34); box=d.textbbox((0,0),text,font=f); pad=24
        x=(im.width-(box[2]-box[0]))/2
        d.rounded_rectangle((x-pad,top,x+(box[2]-box[0])+pad,top+(box[3]-box[1])+34),radius=22,fill=(5,12,22,220),outline='#61A844',width=2)
        d.text((x,top+13),text,font=f,fill='white')

def draw_whatsapp(im:Image.Image,content_format:str)->None:
    d=ImageDraw.Draw(im); green='#25D366'; phone='371 370 8294'
    h=96 if content_format=='reel' else 74; y=im.height-h-28; w=int(im.width*.74); x=(im.width-w)//2
    d.rounded_rectangle((x,y,x+w,y+h),radius=h//2,fill=(3,8,6,235),outline=green,width=3)
    r=int(h*.29); cx=x+52; cy=y+h//2; d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=green)
    ficon=ff(SANS_B,int(h*.28)); d.text((cx-int(h*.12),cy-int(h*.18)),'☎',font=ficon,fill='white')
    f=ff(SANS_B,39 if content_format=='reel' else 29); txt=f'WHATSAPP  {phone}'; box=d.textbbox((0,0),txt,font=f)
    d.text((x+100,y+(h-(box[3]-box[1]))/2-5),txt,font=f,fill='white')

def draw_presenter(im:Image.Image,name:str|None,slide_index:int)->None:
    if not name:return
    pic=load_presenter(name)
    if pic is None:return
    target_h=int(im.height*.29); ratio=target_h/pic.height; target_w=int(pic.width*ratio)
    pic=pic.resize((target_w,target_h),Image.Resampling.LANCZOS)
    x=im.width-target_w-28; y=int(im.height*.60)+(8 if slide_index%2 else -8)
    # rounded portrait tile with soft green edge; small and out of the main hook area
    mask=Image.new('L',pic.size,0); md=ImageDraw.Draw(mask); md.rounded_rectangle((0,0,pic.width-1,pic.height-1),radius=26,fill=255)
    tile=Image.new('RGBA',pic.size,(0,0,0,0)); tile.paste(pic,(0,0),mask)
    base=im.convert('RGBA'); shadow=Image.new('RGBA',base.size,(0,0,0,0)); sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x-7,y-7,x+target_w+7,y+target_h+7),radius=32,fill=(0,0,0,130),outline=(146,194,5,230),width=4)
    base.alpha_composite(shadow); base.alpha_composite(tile,(x,y)); im.paste(base.convert('RGB'))

def draw_slide(raw:str,cfg:dict[str,Any],src:dict[str,Any],w:int,h:int,no:int,count:int,fmt:str,presenter:str|None=None)->Image.Image:
    im=compose(download(src),w,h); d=ImageDraw.Draw(im); brand=cfg.get('brand',{}); accent=brand.get('accent','#92C205')
    draw_logo(im,cfg,int(h*.025))
    # One large title/hook only. No subtitles, counters or campaign footer.
    hook=str(raw).split('|')[0].strip() if raw else ''
    if hook:
        fs=82 if fmt=='reel' else 64; f=ff(SANS_B,fs); lines=wrap(d,hook,f,int(w*.78))
        maxw=max((d.textbbox((0,0),ln,font=f)[2] for ln in lines),default=0); lh=fs+10; total=lh*len(lines); y=int(h*.43-total/2)
        pad=34; x=(w-maxw)//2
        d.rounded_rectangle((x-pad,y-pad,w-x+pad,y+total+pad),radius=34,fill=(0,0,0,152))
        for ln in lines:
            box=d.textbbox((0,0),ln,font=f); d.text(((w-(box[2]-box[0]))/2,y),ln,font=f,fill='white',stroke_width=2,stroke_fill='black'); y+=lh
        d.rounded_rectangle((int(w*.35),int(h*.555),int(w*.65),int(h*.555)+9),radius=4,fill=accent)
    if fmt=='reel': draw_presenter(im,presenter,no)
    draw_whatsapp(im,fmt)
    credit=str(src.get('credit') or '')
    if credit:
        cf=ff(SANS,14 if fmt=='carousel' else 15); d.text((18,h-18),credit,font=cf,fill=(230,230,230))
    return im

def synth(job:dict[str,Any],cfg:dict[str,Any],out:Path)->Path|None:
    vc=cfg.get('brand',{}).get('voice',{}); text=str(job.get('voiceover') or '').strip()
    if not vc.get('enabled',False) or not text:return None
    model=str(vc.get('model') or 'it_IT-paola-medium'); data=Path(os.getenv('PIPER_DATA_DIR',str(ROOT/'.cache'/'piper')))
    subprocess.run([sys.executable,'-m','piper','-m',model,'--data-dir',str(data),'-f',str(out),'--',text],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return out if out.exists() else None

def render_reel(job:dict[str,Any],cfg:dict[str,Any])->Path:
    rc=cfg.get('brand',{}).get('reel',{}); w,h=int(rc.get('width',1080)),int(rc.get('height',1920)); slides=list(job.get('slides') or [job.get('title','')]); out=ROOT/str(job['media']); out.parent.mkdir(parents=True,exist_ok=True)
    ss=sources(cfg); target=float(rc.get('target_seconds',60) or 60); sec=target/max(1,len(slides)); presenter=str(job.get('_presenter') or '') or None
    with tempfile.TemporaryDirectory(prefix='oss-reel-') as td:
        tmp=Path(td); voice=synth(job,cfg,tmp/'voice.wav'); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); frames=[]
        for i,raw in enumerate(slides,1):
            p=tmp/f's{i:02d}.jpg'; draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,i,len(slides),'reel',presenter).save(p,'JPEG',quality=92,optimize=True); frames.append(p)
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

def render_carousel(job:dict[str,Any],cfg:dict[str,Any])->list[Path]:
    cc=cfg.get('brand',{}).get('carousel',{}); w,h=int(cc.get('width',1080)),int(cc.get('height',1350)); slides=list(job.get('slides') or []); media=list(job.get('media') or []); ss=sources(cfg); seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); outs=[]
    if len(slides)!=len(media):raise RuntimeError(f"Carousel {job.get('id')} mismatch")
    for i,(raw,rel) in enumerate(zip(slides,media),1):
        out=ROOT/str(rel); out.parent.mkdir(parents=True,exist_ok=True); draw_slide(raw,cfg,ss[(i-1+seed)%len(ss)],w,h,i,len(slides),'carousel').save(out,'JPEG',quality=92,optimize=True); outs.append(out)
    return outs

def main()->int:
    if not QUEUE_PATH.exists():return 0
    q=load_json(QUEUE_PATH); n=0; reel_count:dict[str,int]={}
    for job in q.get('jobs',[]):
        if not job.get('enabled',True) or job.get('status') in {'scheduled','published','disabled'}:continue
        if not job.get('client_id') or not job.get('media'):continue
        cid=str(job['client_id']); cfg=cfg_for(cid)
        if str(job.get('format') or 'reel')=='carousel':
            render_carousel(job,cfg)
        else:
            k=reel_count.get(cid,0)
            # Presenter one Reel yes / one Reel no. When present, Joseph and Francesca alternate.
            if k%2==0: job['_presenter']='joseph' if (k//2)%2==0 else 'francesca'
            else: job['_presenter']=''
            reel_count[cid]=k+1
            render_reel(job,cfg)
        n+=1
    print(f'Rendered {n} social asset set(s).')
    return 0
if __name__=='__main__':raise SystemExit(main())
