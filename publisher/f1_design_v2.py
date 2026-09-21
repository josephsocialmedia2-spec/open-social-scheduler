#!/usr/bin/env python3
# Design V2 benchmark render trigger
from pathlib import Path
from io import BytesIO
import requests
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance,ImageOps

OUT=Path("publisher/media/generated/f1-design-v2"); OUT.mkdir(parents=True,exist_ok=True)
GREEN=(78,158,21); DARK=(10,13,10); WHITE=(248,248,244); MUTED=(213,218,210)
BASE="https://github.com/josephsocialmedia2-spec/open-social-scheduler/releases/download/f1-feed-latest"
items={
"C12":("Chi è il compratore probabile della tua casa?","TARGET ACQUIRENTE","Definisci prima chi deve innamorarsi della casa."),
"C13":("Prima di firmare un incarico","6 DOMANDE","Dati · strategia · distribuzione · reporting."),
"C14":("Vuoi sapere se possiamo aiutarti?","5 DATI","Comune · tipologia · mq · stato · tempistica."),
"R12":("Poche visite?","PRIMA DI ABBASSARE IL PREZZO","Diagnostica presentazione, distribuzione e target."),
"R13":("Più eredi, una sola vendita","PRIMA L'ALLINEAMENTO","Obiettivo · prezzo minimo · tempi · responsabilità."),
"R14":("Quanto vale davvero casa tua?","VALUTAZIONE SERIA","Comune · tipologia · mq · tempistica.")
}
def font(sz,bold=False):
 p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
 return ImageFont.truetype(p,sz)
def source(code,size):
 name=f"{code}-slide-01.jpg" if code.startswith("C") else f"{code}-cover.jpg"
 r=requests.get(f"{BASE}/{name}",timeout=45); r.raise_for_status()
 im=Image.open(BytesIO(r.content)).convert("RGB")
 im=ImageOps.fit(im,size,method=Image.Resampling.LANCZOS)
 im=im.filter(ImageFilter.GaussianBlur(18)); im=ImageEnhance.Brightness(im).enhance(.58)
 return im
def wrap(d,text,f,width,maxlines=3):
 words=text.split(); lines=[]; cur=""
 for w in words:
  t=(cur+" "+w).strip()
  if d.textbbox((0,0),t,font=f)[2]<=width: cur=t
  else:
   if cur: lines.append(cur)
   cur=w
 if cur: lines.append(cur)
 return lines[:maxlines]
def render(code):
 reel=code.startswith("R"); W,H=(1080,1920) if reel else (1080,1350)
 im=source(code,(W,H)); d=ImageDraw.Draw(im,"RGBA")
 # clean editorial field: strong asymmetry, whitespace, restrained brand chrome
 d.rectangle((0,0,W,int(H*.18)),fill=(248,248,244,248))
 d.rectangle((0,int(H*.18),int(W*.58),H),fill=(248,248,244,244))
 d.rectangle((0,H-118,W,H),fill=(10,13,10,248))
 d.rectangle((0,0,16,H),fill=GREEN+(255,))
 d.text((62,58),"F1",font=font(54,True),fill=GREEN)
 d.text((148,72),"IMMOBILIARE",font=font(30,True),fill=DARK)
 title,kicker,sub=items[code]
 y=int(H*.27)
 d.text((64,y),kicker,font=font(28,True),fill=GREEN); y+=70
 f=font(62 if reel else 58,True)
 for line in wrap(d,title.upper(),f,int(W*.47),4):
  d.text((64,y),line,font=f,fill=DARK); y+=78
 y+=28
 sf=font(29 if reel else 27,False)
 for line in wrap(d,sub,sf,int(W*.45),4):
  d.text((64,y),line,font=sf,fill=(55,61,55)); y+=43
 # CTA
 cy=min(int(H*.70),y+90)
 d.rounded_rectangle((62,cy,500,cy+92),radius=46,fill=GREEN+(255,))
 d.text((96,cy+27),"SCRIVI VALUTAZIONE",font=font(25,True),fill=WHITE)
 # right-side visual aperture
 x0=int(W*.61); top=int(H*.22); bot=H-155
 d.rounded_rectangle((x0,top,W-42,bot),radius=34,outline=WHITE+(210,),width=3)
 d.text((62,H-80),"VALLE DI SUSA  ·  371 370 8294",font=font(24,True),fill=WHITE)
 d.text((W-220,H-80),"F1 / V2",font=font(22,True),fill=GREEN)
 out=OUT/(f"{code}-V2-cover.jpg" if reel else f"{code}-V2-slide-01.jpg")
 im.save(out,"JPEG",quality=95,optimize=True)
 return out
for c in items:
 p=render(c); print(p)
