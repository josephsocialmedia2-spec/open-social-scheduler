#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'publisher'/'final_content_queue.json'
GREEN='#6BC200'; DARK='#07100A'; WHITE='#FFFFFF'; MUTED='#EAF2E4'
CTA_URL='https://www.agentpricing.com/j.malafronte'
CTA='CLICCA SUL LINK 👉\n'+CTA_URL+'\n🏡“Contattaci per una Valutazione Strategica e di Posizionamento del tuo immobile: analizziamo prezzo, concorrenza e strategia di vendita per aumentare le possibilità di vendere meglio e in tempi più efficienti.”'

def font(size:int,bold:bool=False):
    p='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p,size)

def wrap(draw,text,f,maxw):
    words=str(text or '').split(); lines=[]; line=''
    for w in words:
        test=(line+' '+w).strip()
        if draw.textbbox((0,0),test,font=f)[2] <= maxw: line=test
        else:
            if line: lines.append(line)
            line=w
    if line: lines.append(line)
    return lines

def next_ready(data):
    ready=[j for j in data.get('jobs',[]) if str(j.get('status'))=='READY']
    ready.sort(key=lambda j:(str(j.get('scheduled_at') or ''),str(j.get('id') or '')))
    return ready[0] if ready else None

def build_copy(job):
    title=str(job.get('title') or '').strip()
    objective=str(job.get('objective') or '')
    if objective=='SELLER':
        body=(f'{title}\n\nA Villar Dora una strategia di vendita efficace parte dalla lettura del mercato locale, '
              'dalla concorrenza attiva e dalle caratteristiche specifiche dell’immobile. '
              'F1 Immobiliare lavora sul posizionamento prima di decidere come presentare la casa al mercato.')
        graphic='Mercato locale e strategia immobiliare.'
    else:
        body=(f'{title}\n\nConoscere Villar Dora significa capire il territorio in cui si sceglie di vivere: '
              'servizi, comunità, patrimonio locale e qualità della vita fanno parte della decisione immobiliare, insieme alla casa.')
        graphic='Territorio, servizi e vita locale.'
    if job.get('source_name'):
        body += f"\n\nFonte di riferimento: {job['source_name']}. Informazioni da verificare alla data di pubblicazione."
    job['caption']=body+'\n\n'+CTA
    job['cta']=CTA_URL
    job['graphic_cta']=CTA
    job['graphic_body']=graphic

def render(job):
    path=ROOT/str(job['assets'][0]); path.parent.mkdir(parents=True,exist_ok=True)
    img=Image.new('RGB',(1080,1350),GREEN); d=ImageDraw.Draw(img)
    d.rounded_rectangle((48,45,1032,1305),radius=34,fill=DARK)
    d.text((84,90),'F1 IMMOBILIARE',font=font(48,True),fill=WHITE)
    d.text((84,150),'VILLAR DORA',font=font(24,True),fill=GREEN)
    titlef=font(48,True); bodyf=font(27); small=font(19); smallb=font(19,True)
    y=245
    for line in wrap(d,job.get('title'),titlef,900)[:5]:
        d.text((84,y),line,font=titlef,fill=WHITE); y+=61
    y+=18
    for line in wrap(d,job.get('graphic_body') or '',bodyf,900)[:4]:
        d.text((84,y),line,font=bodyf,fill=MUTED); y+=40
    d.line((84,y+18,996,y+18),fill=GREEN,width=4); y+=52
    for idx,part in enumerate(str(job.get('graphic_cta') or CTA).split('\n')):
        f=smallb if idx<2 else small; fill=GREEN if idx<2 else WHITE
        for line in wrap(d,part,f,900):
            if y>1190: break
            d.text((84,y),line,font=f,fill=fill); y+=28
        y+=4
    d.text((84,1245),'F1 CASA E IMPRESE · VALLE DI SUSA',font=font(18,True),fill=MUTED)
    img.save(path,'PNG',optimize=True)
    print(path)

def main():
    data=json.loads(QUEUE.read_text(encoding='utf-8'))
    job=next_ready(data)
    if not job:
        print('NO READY JOB'); return 0
    build_copy(job)
    QUEUE.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    render(job)
    return 0
if __name__=='__main__': raise SystemExit(main())
