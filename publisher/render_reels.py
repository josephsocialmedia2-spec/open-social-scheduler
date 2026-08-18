#!/usr/bin/env python3
"""Deluxe renderer: 10 clean visuals, natural female voice, no subtitles."""
from __future__ import annotations
import asyncio, base64, hashlib, html, json, math, os, re, struct, subprocess, sys, tempfile, time, wave
from io import BytesIO
from pathlib import Path
from typing import Any
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'publisher'/'queue.json'; CLIENTS=ROOT/'publisher'/'clients'; ASSETS=ROOT/'publisher'/'assets'
CACHE=Path(os.getenv('SOCIAL_PHOTO_CACHE',str(ROOT/'.cache'/'social-photos')))
SANS=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'); BOLD=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')

F1=[
 'https://pixabay.com/photos/modern-villa-exterior-9804538/',
 'https://pixabay.com/photos/contemporary-villa-facade-9804533/',
 'https://pixabay.com/photos/luxury-villa-facade-9804536/',
 'https://pixabay.com/photos/living-room-modern-interior-9795892/',
 'https://pixabay.com/photos/living-room-interior-design-modern-8572596/',
 'https://pixabay.com/photos/kitchen-interior-modern-real-estate-8260437/',
 'https://pixabay.com/photos/bedroom-real-estate-interior-modern-8260423/',
 'https://pixabay.com/photos/bathroom-interior-design-modern-8556101/',
 'https://pixabay.com/photos/real-estate-kitchen-interior-design-8428506/',
 'https://pixabay.com/photos/bedroom-interior-design-modern-8572584/',
]
# Authentic photography only: no legacy Python mockups and no AI-generated stock.
RMP=[
 'https://pixabay.com/photos/laptop-workspace-web-design-work-2443749/',
 'https://pixabay.com/photos/desk-work-business-office-finance-3139127/',
 'https://pixabay.com/photos/laptop-office-web-design-coding-8305452/',
 'https://pixabay.com/photos/desk-laptop-notebook-pen-workspace-593327/',
 'https://pixabay.com/photos/laptop-notebook-work-keyboard-2443052/',
 'https://pixabay.com/photos/office-internet-web-design-computer-4009348/',
 'https://pixabay.com/photos/web-design-notebook-computer-office-1419696/',
 'https://pixabay.com/photos/woman-laptop-coworking-entrepreneur-4780153/',
 'https://pixabay.com/photos/meeting-business-office-group-team-5395567/',
 'https://pixabay.com/photos/laptop-woman-business-woman-data-8474325/',
]

def load(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def ff(p:Path,n:int): return ImageFont.truetype(str(p),n)
def cfg(cid:str): return load(CLIENTS/f'{cid}.json')

def resolve_pixabay(url:str)->str:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'it-IT,it;q=0.9'},timeout=25); r.raise_for_status()
    for pat in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'):
        m=re.search(pat,r.text,re.I)
        if m:return html.unescape(m.group(1))
    raise RuntimeError(f'Pixabay image not resolved: {url}')

def get_image(url:str)->Image.Image:
    direct=resolve_pixabay(url) if 'pixabay.com/' in url and 'cdn.pixabay.com/' not in url else url
    CACHE.mkdir(parents=True,exist_ok=True); p=CACHE/(hashlib.sha256(direct.encode()).hexdigest()+'.jpg')
    if p.exists() and p.stat().st_size>12000:return Image.open(p).convert('RGB')
    r=requests.get(direct,headers={'User-Agent':'Mozilla/5.0 Open-Social-Scheduler/Deluxe','Accept':'image/*'},timeout=35); r.raise_for_status()
    im=Image.open(BytesIO(r.content)).convert('RGB'); im.save(p,'JPEG',quality=94,optimize=True); return im

def fit(url:str,w:int,h:int)->Image.Image:
    return ImageOps.fit(get_image(url),(w,h),method=Image.Resampling.LANCZOS,centering=(.5,.5)).convert('RGB')

def presenter(name:str)->Image.Image|None:
    p=ASSETS/f'{name}_presenter.jpg.b64'
    if not p.exists():return None
    try:return Image.open(BytesIO(base64.b64decode(p.read_text().strip()))).convert('RGB')
    except Exception:return None

def f1_logo(im:Image.Image,c:dict[str,Any],top:int)->int:
    d=ImageDraw.Draw(im,'RGBA'); brand=c['brand']; v=brand.get('logo_vectors',{}); green=brand.get('accent','#92C205')
    pw=int(im.width*.36); ph=int(pw*.55); x=(im.width-pw)//2
    d.rounded_rectangle((x,top,x+pw,top+ph),radius=26,fill=(255,255,255,228))
    scale=pw*.72/500; ox=x+int(pw*.14); oy=top+int(ph*.02)
    for poly in v.get('green',[]):d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill=green)
    for poly in v.get('white',[]):d.polygon([(ox+int(a*scale),oy+int(b*scale)) for a,b in poly],fill='#0A0B0A')
    label='IMMOBILIARE'; f=ff(BOLD,max(18,int(pw*.055))); b=d.textbbox((0,0),label,font=f)
    d.text(((im.width-(b[2]-b[0]))/2,top+ph-int(ph*.20)),label,font=f,fill='#111')
    return top+ph

def header(im:Image.Image,c:dict[str,Any],fmt:str)->None:
    cid=c['id']; d=ImageDraw.Draw(im,'RGBA'); top=int(im.height*.025)
    if cid=='f1-immobiliare':
        bottom=f1_logo(im,c,top); text='RICHIEDI UNA VALUTAZIONE GRATUITA DEL TUO IMMOBILE'; f=ff(BOLD,30 if fmt=='reel' else 23); b=d.textbbox((0,0),text,font=f); y=bottom+20
        d.rounded_rectangle(((im.width-(b[2]-b[0]))/2-18,y-9,(im.width+(b[2]-b[0]))/2+18,y+(b[3]-b[1])+15),radius=18,fill=(255,255,255,224))
        d.text(((im.width-(b[2]-b[0]))/2,y),text,font=f,fill=c['brand'].get('accent','#92C205'))
    else:
        text='REAL MEDIA PRO'; f=ff(BOLD,44 if fmt=='reel' else 34); b=d.textbbox((0,0),text,font=f); w=b[2]-b[0]; x=(im.width-w)//2
        d.rounded_rectangle((x-28,top,x+w+28,top+94),radius=28,fill=(5,16,31,230),outline=(45,127,249,240),width=3); d.text((x,top+20),text,font=f,fill='white')

def contact(im:Image.Image,c:dict[str,Any],fmt:str)->None:
    d=ImageDraw.Draw(im,'RGBA'); h=104 if fmt=='reel' else 82; y=im.height-h-24; w=int(im.width*.88); x=(im.width-w)//2; accent=c['brand'].get('accent','#2D7FF9')
    d.rounded_rectangle((x,y,x+w,y+h),radius=h//2,fill=(255,255,255,238),outline=accent,width=4)
    text='371 370 8294  •  371 424 6300' if c['id']=='f1-immobiliare' else '371 370 8294'; f=ff(BOLD,37 if fmt=='reel' else 28); b=d.textbbox((0,0),text,font=f)
    d.text(((im.width-(b[2]-b[0]))/2,y+(h-(b[3]-b[1]))/2-5),text,font=f,fill='#0A0B0A')

def add_presenter(im:Image.Image,name:str|None)->None:
    if not name:return
    pic=presenter(name)
    if pic is None:return
    th=int(im.height*.27); ratio=th/pic.height; pic=pic.resize((int(pic.width*ratio),th),Image.Resampling.LANCZOS)
    mask=Image.new('L',pic.size,0); ImageDraw.Draw(mask).rounded_rectangle((0,0,pic.width-1,pic.height-1),radius=28,fill=255)
    tile=Image.new('RGBA',pic.size,(0,0,0,0)); tile.paste(pic,(0,0),mask); base=im.convert('RGBA'); x=im.width-pic.width-24; y=im.height-th-128
    sh=Image.new('RGBA',base.size,(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle((x-7,y-7,x+pic.width+7,y+pic.height+7),radius=34,fill=(0,0,0,80)); base.alpha_composite(sh); base.alpha_composite(tile,(x,y)); im.paste(base.convert('RGB'))

def wrap(d:ImageDraw.ImageDraw,text:str,f,maxw:int)->list[str]:
    lines=[]; cur=''
    for word in str(text).split():
        t=(cur+' '+word).strip()
        if d.textbbox((0,0),t,font=f)[2]<=maxw:cur=t
        else:
            if cur:lines.append(cur)
            cur=word
    if cur:lines.append(cur)
    return lines[:4]

def carousel_title(im:Image.Image,c:dict[str,Any],text:str)->None:
    if not text:return
    d=ImageDraw.Draw(im,'RGBA'); f=ff(BOLD,62); lines=wrap(d,text,f,int(im.width*.80)); lh=76; total=lh*len(lines); y=int(im.height*.50-total/2); maxw=max(d.textbbox((0,0),x,font=f)[2] for x in lines); x=(im.width-maxw)//2
    d.rounded_rectangle((x-34,y-28,im.width-x+34,y+total+28),radius=32,fill=(255,255,255,230)); fill=c['brand'].get('accent','#92C205') if c['id']=='f1-immobiliare' else '#07111F'
    for line in lines:
        b=d.textbbox((0,0),line,font=f); d.text(((im.width-(b[2]-b[0]))/2,y),line,font=f,fill=fill); y+=lh

def frame(c:dict[str,Any],url:str,w:int,h:int,fmt:str,title:str='',who:str|None=None)->Image.Image:
    im=fit(url,w,h); ov=Image.new('RGBA',im.size,(0,0,0,0)); od=ImageDraw.Draw(ov); od.rectangle((0,0,w,int(h*.17)),fill=(0,0,0,22)); od.rectangle((0,int(h*.83),w,h),fill=(0,0,0,32)); base=im.convert('RGBA'); base.alpha_composite(ov); im=base.convert('RGB')
    header(im,c,fmt)
    if fmt=='carousel':carousel_title(im,c,title)
    if c['id']=='f1-immobiliare' and fmt=='reel':add_presenter(im,who)
    contact(im,c,fmt); return im

async def edge_save(text:str,out:Path)->None:
    import edge_tts
    await edge_tts.Communicate(text=text,voice='it-IT-IsabellaNeural',rate='-4%',volume='+0%').save(str(out))

def voice(job:dict[str,Any],temp:Path)->Path|None:
    text=str(job.get('voiceover') or '').strip()
    if not text:return None
    out=temp/'voice.mp3'
    try:
        asyncio.run(edge_save(text,out))
        if out.exists() and out.stat().st_size>1000:return out
    except Exception as e:print(f'WARN Edge TTS: {e}',file=sys.stderr)
    p=temp/'voice.wav'; data=Path(os.getenv('PIPER_DATA_DIR',str(ROOT/'.cache'/'piper')))
    try:
        subprocess.run([sys.executable,'-m','piper','-m','it_IT-paola-medium','--data-dir',str(data),'-f',str(p),'--',text],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE); return p if p.exists() else None
    except Exception as e:print(f'WARN Piper: {e}',file=sys.stderr); return None

def music(out:Path,seconds:float=60)->Path:
    sr=22050; notes=[220,277.18,329.63,415.30,246.94,311.13,369.99,466.16]; total=int(sr*seconds)
    with wave.open(str(out),'w') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        for i in range(total):
            t=i/sr; f0=notes[int(t/1.5)%len(notes)]; env=.38+.62*(.5-.5*math.cos(2*math.pi*((t%1.5)/1.5))); sample=(math.sin(2*math.pi*f0*t)*.55+math.sin(2*math.pi*f0*.5*t)*.25+math.sin(2*math.pi*f0*1.5*t)*.12)*env*.10; wf.writeframes(struct.pack('<h',max(-32767,min(32767,int(sample*32767)))))
    return out

def make_video(frames:list[Path],v:Path|None,m:Path,out:Path,target:float=60)->None:
    n=len(frames); tr=.6; dur=(target+(n-1)*tr)/n; cmd=['ffmpeg','-y']
    for p in frames:cmd+=['-loop','1','-t',f'{dur:.3f}','-i',str(p)]
    vi=None
    if v:vi=n; cmd+=['-i',str(v)]
    mi=n+(1 if v else 0); cmd+=['-i',str(m)]; filters=[]; fc=max(1,int(round(dur*30)))
    for i in range(n):filters.append(f"[{i}:v]scale=1188:2112:force_original_aspect_ratio=increase,crop=1188:2112,zoompan=z='min(zoom+0.0004,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fc}:s=1080x1920:fps=30,format=yuv420p[v{i}]")
    cur='v0'
    for i in range(1,n):
        o=f'x{i}'; filters.append(f'[{cur}][v{i}]xfade=transition=fade:duration={tr}:offset={i*(dur-tr):.3f}[{o}]'); cur=o
    if vi is not None:filters += [f'[{vi}:a]volume=1.0,apad[voice]',f'[{mi}:a]volume=0.055[music]','[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]']
    else:filters += [f'[{mi}:a]volume=0.07,apad[aout]']
    cmd += ['-filter_complex',';'.join(filters),'-map',f'[{cur}]','-map','[aout]','-c:v','libx264','-crf','20','-preset','veryfast','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',f'{target:.3f}',str(out)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

def render_reel(job:dict[str,Any],c:dict[str,Any])->Path:
    w,h=1080,1920; out=ROOT/str(job['media']); out.parent.mkdir(parents=True,exist_ok=True); src=F1 if c['id']=='f1-immobiliare' else RMP; who=str(job.get('_presenter') or '') or None
    with tempfile.TemporaryDirectory(prefix='oss-deluxe-') as td:
        t=Path(td); v=voice(job,t); m=music(t/'music.wav'); frames=[]; seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0)
        for i in range(10):
            p=t/f'f{i:02d}.jpg'; frame(c,src[(i+seed)%10],w,h,'reel',who=who).save(p,'JPEG',quality=94,optimize=True); frames.append(p)
        make_video(frames,v,m,out,60)
    return out

def render_carousel(job:dict[str,Any],c:dict[str,Any])->list[Path]:
    slides=(list(job.get('slides') or [])+['']*10)[:10]; media=list(job.get('media') or []); src=F1 if c['id']=='f1-immobiliare' else RMP
    if len(media)!=10:raise RuntimeError(f"Carousel {job.get('id')} must have 10 files")
    seed=int(str(job.get('scheduled_at') or '0000-00-00')[8:10] or 0); outs=[]
    for i,(title,rel) in enumerate(zip(slides,media)):
        out=ROOT/str(rel); out.parent.mkdir(parents=True,exist_ok=True); frame(c,src[(i+seed)%10],1080,1350,'carousel',title=title).save(out,'JPEG',quality=94,optimize=True); outs.append(out)
    return outs

def main()->int:
    if not QUEUE.exists():return 0
    q=load(QUEUE); jobs=[j for j in q.get('jobs',[]) if j.get('enabled',True) and j.get('status') not in {'scheduled','published','disabled'}]
    if jobs:
        day=max(str(j.get('scheduled_at') or '')[:10] for j in jobs); jobs=[j for j in jobs if str(j.get('scheduled_at') or '')[:10]==day]
    counts={}; done=0
    for job in jobs:
        cid=str(job.get('client_id') or '')
        if cid not in {'f1-immobiliare','real-media-pro'} or not job.get('media'):continue
        c=cfg(cid)
        if str(job.get('format') or 'reel')=='carousel':render_carousel(job,c)
        else:
            k=counts.get(cid,0); job['_presenter']=('joseph' if k%2==0 else 'francesca') if cid=='f1-immobiliare' else ''; counts[cid]=k+1; render_reel(job,c)
        done+=1
    print(f'Rendered {done} deluxe premium asset set(s).'); return 0

if __name__=='__main__':raise SystemExit(main())
