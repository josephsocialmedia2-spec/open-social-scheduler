#!/usr/bin/env python3
"""Burn compact green emoji captions into generated Reels.
Captions advance phrase-by-phrase under the top logo while preserving voice audio.
"""
from __future__ import annotations
import json,re,shutil,subprocess,tempfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'publisher'/'queue.json'
EMOJIS=['🏠','📊','💡','🚀','📱','✅','🎯','✨']

def load(p:Path)->dict[str,Any]: return json.loads(p.read_text(encoding='utf-8'))
def duration(p:Path)->float:
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)],capture_output=True,text=True,check=True)
    return float(r.stdout.strip())
def chunks(text:str,target:int=7)->list[str]:
    words=re.sub(r'\s+',' ',str(text or '')).strip().split()
    if not words:return []
    out=[]
    for i in range(0,len(words),target): out.append(' '.join(words[i:i+target]))
    return out
def ass_time(s:float)->str:
    h=int(s//3600); s-=h*3600; m=int(s//60); s-=m*60
    return f'{h}:{m:02d}:{s:05.2f}'
def esc(s:str)->str: return s.replace('\\','\\\\').replace('{','\\{').replace('}','\\}').replace('\n',' ')
def write_ass(path:Path,text:str,total:float)->None:
    cs=chunks(text)
    if not cs: path.write_text('',encoding='utf-8'); return
    usable=max(.5,total-.1); span=usable/len(cs)
    header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Caption,DejaVu Sans,54,&H0005C292,&H0005C292,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,3,0,8,90,90,295,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'''
    lines=[]
    for i,c in enumerate(cs):
        start=i*span; end=min(usable,(i+1)*span); emoji=EMOJIS[i%len(EMOJIS)]
        # subtle vertical movement: phrase rises by ~32 px while visible
        textline=f'{{\\move(540,345,540,313)}}{emoji} {esc(c)}'
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{textline}')
    path.write_text(header+'\n'.join(lines)+'\n',encoding='utf-8')

def burn(job:dict[str,Any])->bool:
    if str(job.get('format') or '').lower()!='reel':return False
    media=job.get('media'); text=str(job.get('voiceover') or '').strip()
    if not isinstance(media,str) or not media.endswith('.mp4') or not text:return False
    video=ROOT/media
    if not video.exists() or video.stat().st_size<10000:return False
    total=duration(video)
    with tempfile.TemporaryDirectory(prefix='oss-captions-') as td:
        td=Path(td); ass=td/'captions.ass'; out=td/'captioned.mp4'; write_ass(ass,text,total)
        vf=f"ass='{str(ass).replace(':','\\:').replace('\\\\','/')}'"
        subprocess.run(['ffmpeg','-y','-i',str(video),'-vf',vf,'-c:v','libx264','-crf','20','-preset','medium','-c:a','copy','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        shutil.copy2(out,video)
    return True

def main()->int:
    if not QUEUE.exists():return 0
    q=load(QUEUE); n=0
    for job in q.get('jobs',[]):
        if job.get('enabled',True) and burn(job): n+=1
    print(f'Green emoji captions added to {n} Reel(s).')
    return 0
if __name__=='__main__': raise SystemExit(main())
