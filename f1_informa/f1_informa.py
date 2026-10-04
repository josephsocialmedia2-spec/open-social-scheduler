#!/usr/bin/env python3
import argparse, hashlib, json, re, shutil, textwrap, time
from collections import deque
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/"config"/"sources.json").read_text(encoding="utf-8"))
STATE_PATH=ROOT/"state.json"
PUBLIC=ROOT.parent/"f1-content-hub"/"f1-informa-data"
ROME=ZoneInfo("Europe/Rome")
GREEN,DARK,CREAM,WHITE,GOLD="#0E5A3B","#133126","#F6F2E8","#FFFFFF","#D9B45B"
GENERIC={"home","casa","agevolazioni","cittadini"}

def norm(s): return re.sub(r"\s+"," ",unescape(s or "")).strip()
def canon(url):
    url,_=urldefrag(url)
    return url.rstrip("/")
def allowed(url):
    p=urlparse(url)
    return p.scheme in {"http","https"} and p.netloc.lower() in {x.lower() for x in CONFIG["allowed_hosts"]}
def relevant(text,url):
    h=f"{text} {url}".lower()
    return any(k.lower() in h for k in CONFIG["keywords"])

def fetch(url):
    headers={"User-Agent":"Mozilla/5.0 AppleWebKit/537.36 Chrome/131 Safari/537.36 F1Informa/1.0","Accept-Language":"it-IT,it;q=0.9"}
    try:
        r=requests.get(url,headers=headers,timeout=30,allow_redirects=True)
        if r.status_code==200 and len(r.text)>1000: return r.text,r.url,None
        err=f"HTTP {r.status_code}"
    except Exception as e: err=f"REQUEST_ERROR: {e}"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b=p.chromium.launch(headless=True)
            c=b.new_context(locale="it-IT",user_agent="Mozilla/5.0 AppleWebKit/537.36 Chrome/131 Safari/537.36")
            pg=c.new_page(); pg.goto(url,wait_until="domcontentloaded",timeout=45000); pg.wait_for_timeout(900)
            html,final=pg.content(),pg.url; b.close()
            if len(html)>1000: return html,final,None
            return None,final,"PLAYWRIGHT_EMPTY"
    except Exception as e:
        return None,url,f"{err}; PLAYWRIGHT_ERROR: {e}"

def page_title(soup,main,base):
    generic={"menu principale","menu","agenzia delle entrate","home","cittadini","agevolazioni"}
    candidates=[]
    for selector in ("h1","h2","h3"):
        for node in main.find_all(selector,limit=8):
            value=norm(node.get_text(" ",strip=True))
            if value: candidates.append(value)
    if soup.title:
        candidates.append(norm(soup.title.get_text(" ",strip=True)))
    for value in candidates:
        low=value.lower().strip(" -|")
        if low in generic or low.startswith("menu principale"): continue
        if 6 <= len(value) <= 160 and relevant(value,base):
            return re.sub(r"\s*[-|]\s*Agenzia delle Entrate.*$","",value,flags=re.I).strip()
    slug=urlparse(base).path.rstrip("/").split("/")[-1]
    slug=re.sub(r"-(cittadini|infogen.*)$","",slug,flags=re.I)
    value=norm(slug.replace("-"," "))
    return value[:1].upper()+value[1:] if value else "Aggiornamento casa"

def extract(html,base):
    soup=BeautifulSoup(html,"html.parser")
    for tag in soup(["script","style","noscript","svg","footer"]): tag.decompose()
    main=soup.find("main") or soup.find(attrs={"role":"main"}) or soup.body or soup
    title=page_title(soup,main,base)
    text=norm(main.get_text("\n",strip=True))
    links=[]
    for a in main.find_all("a",href=True):
        href=canon(urljoin(base,a.get("href"))); label=norm(a.get_text(" ",strip=True))
        if href and allowed(href): links.append((href,label))
    m=re.search(r"Ultimo aggiornamento\s*:?\s*([0-9]{1,2}\s+[A-Za-zàèéìòù]+\s+[0-9]{4}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",text,re.I)
    return {"title":title,"text":text,"links":links,"updated":m.group(1) if m else ""}

def crawl():
    q=deque((canon(u),0,"seed") for u in CONFIG["seeds"]); seen=set(); out=[]
    while q and len(out)<CONFIG["max_pages"]:
        url,depth,via=q.popleft()
        if url in seen or not allowed(url): continue
        seen.add(url); html,final,err=fetch(url)
        if not html: out.append({"url":url,"error":err}); continue
        d=extract(html,final)
        if depth==0 or relevant(d["title"]+" "+d["text"][:5000],final):
            item={"url":canon(final),"title":d["title"],"updated":d["updated"],"text":d["text"],"hash":hashlib.sha256(d["text"].encode()).hexdigest(),"depth":depth,"via":via}
            out.append(item)
            if depth<CONFIG["max_depth"]:
                for href,label in d["links"]:
                    if relevant(label,href): q.append((href,depth+1,d["title"] or url))
        time.sleep(float(CONFIG.get("request_delay_seconds",0.4)))
    return out

def state():
    try:
        d=json.loads(STATE_PATH.read_text(encoding="utf-8")); d.setdefault("hashes",{}); d.setdefault("published_log",[]); return d
    except Exception: return {"hashes":{},"published_log":[]}
def save(d): STATE_PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
def archived(p):
    h=f"{p.get('title','')} {p.get('url','')}".lower()
    return any(w in h for w in ("archivio","2023","2024","under 36")) or "/archiv" in h
def recent(url,s,days=45):
    cutoff=datetime.now(ROME).timestamp()-days*86400
    for row in reversed(s.get("published_log",[])):
        if row.get("url")!=url: continue
        try: return datetime.fromisoformat(row["at"]).timestamp()>=cutoff
        except Exception: return True
    return False

def pick(pages,s):
    year=str(datetime.now(ROME).year); cand=[]
    for p in pages:
        if p.get("error") or len(p.get("text",""))<350: continue
        title=(p.get("title") or "").strip()
        if title.lower() in GENERIC: continue
        if archived(p) and not CONFIG.get("allow_archived",False): continue
        changed=s.get("hashes",{}).get(p["url"])!=p["hash"]
        hay=f"{title} {p.get('text','')[:6000]}".lower()
        score=(20 if changed else 0)+(10 if not recent(p["url"],s) else -20)+(6 if p.get("updated") else 0)+(5 if year in hay else 0)
        if any(k in hay for k in ("prima casa","ristruttur","bonus mobili","riqualificazione","mercato immobiliare","omi","locazione","catast")): score+=5
        score+=min(p.get("depth",0),2)*2; cand.append((score,p))
    return max(cand,key=lambda x:x[0])[1] if cand else None

def sentences(text): return [x.strip() for x in re.split(r"(?<=[.!?])\s+",norm(text)) if len(x.strip())>30]
def snippets(text,terms,n=3):
    out=[]
    for s in sentences(text):
        if any(t.lower() in s.lower() for t in terms) and s not in out: out.append(s)
        if len(out)>=n: break
    return out
def trim(s,n=420):
    s=norm(s)
    return s if len(s)<=n else s[:n].rsplit(" ",1)[0]+"…"
def cards(story):
    t=story["text"]; title=story.get("title") or "Aggiornamento Agenzia delle Entrate"
    return [
      (title,"F1 INFORMA\nCasa, fisco e mercato"),
      ("In breve",trim(" ".join(sentences(t)[:2]) or t,500)),
      ("A chi interessa",trim(" ".join(snippets(t,["a chi","contribuent","proprietar","acquirent","inquilin","condomin"])) or "Consulta la fonte ufficiale per i soggetti interessati.",480)),
      ("Qual è il vantaggio",trim(" ".join(snippets(t,["detraz","imposta","iva","credito","agevol","beneficio"])) or "La pagina ufficiale descrive benefici fiscali e condizioni applicabili.",480)),
      ("Numeri da ricordare",trim(" ".join(snippets(t,["%","euro","rate","anni"],4)) or "Percentuali e importi vanno verificati nella versione aggiornata della fonte.",480)),
      ("Requisiti",trim(" ".join(snippets(t,["requisit","condizion","spetta","possono","necessar"])) or "Verifica requisiti soggettivi, oggettivi e documentali nella fonte ufficiale.",480)),
      ("Date e scadenze",trim(" ".join(snippets(t,["entro","termine","scaden","2026","2027","anno"])) or "Controlla sempre l'anno di spesa e i termini indicati dall'Agenzia.",480)),
      ("Attenzione",trim(" ".join(snippets(t,["attenzione","esclus","decad","non spetta","non sono"])) or "Non applicare automaticamente l'agevolazione al tuo caso: verifica eccezioni e aggiornamenti.",480)),
      ("Cosa fare adesso",trim(" ".join(snippets(t,["richied","present","comunica","indicare","consult","acced"])) or "Apri la fonte, verifica i requisiti e conserva la documentazione prevista.",480)),
      ("Fonte ufficiale",trim(f"Agenzia delle Entrate · {story.get('updated') or 'pagina consultata oggi'}\n{story['url']}",520))
    ]

def font(size,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p,size=size) if Path(p).exists() else ImageFont.load_default()
def fit(text,w,h,start=50,minimum=29):
    for size in range(start,minimum-1,-2):
        f=font(size); width=max(10,int(w/(size*.56))); lines=[]
        for para in text.split("\n"): lines.extend(textwrap.wrap(para,width=width,break_long_words=False) or [""])
        spacing=int(size*.3)
        if len(lines)*size+max(0,len(lines)-1)*spacing<=h: return f,lines,spacing
    f=font(minimum); return f,textwrap.wrap(text,width=max(10,int(w/(minimum*.56))),break_long_words=False),int(minimum*.28)
def render(path,idx,heading,body):
    W,H=1080,1350; img=Image.new("RGB",(W,H),CREAM if idx%2 else WHITE); d=ImageDraw.Draw(img)
    d.rectangle([0,0,W,120],fill=GREEN); d.text((70,35),"F1 INFORMA",font=font(42,True),fill=WHITE); d.text((810,42),f"{idx}/10",font=font(30,True),fill=GOLD)
    hf,hl,hs=fit(trim(heading,90),900,150,62,38); y=170
    for line in hl[:3]: d.text((70,y),line,font=hf,fill=DARK); y+=hf.size+hs
    d.rectangle([70,max(290,y+8),235,max(299,y+17)],fill=GOLD); y=max(335,y+55)
    bf,lines,sp=fit(body,900,775,49 if idx!=1 else 43,29)
    for line in lines:
        if y>1135: break
        d.text((70,y),line,font=bf,fill=DARK); y+=bf.size+sp
    d.rectangle([0,1220,W,H],fill=GREEN); d.text((70,1250),"F1 Immobiliare · Fonte: Agenzia delle Entrate",font=font(25),fill=WHITE); d.text((70,1292),"Contenuto informativo, non consulenza fiscale o legale.",font=font(21),fill=WHITE)
    img.save(path,"PNG",optimize=True,compress_level=9)

def prompt(story,cs):
    head=f"""SEI L'EDITOR DI F1 INFORMA — CASA, FISCO E MERCATO.

FONTE UFFICIALE UNICA:
{story['url']}
Titolo: {story.get('title','')}
Ultimo aggiornamento rilevato: {story.get('updated') or 'non indicato'}

TESTO ESTRATTO DALLA FONTE:
{story['text'][:18000]}

COMPITO:
- Verifica che ogni dato sia contenuto nel testo sopra.
- Non aggiungere leggi, percentuali, scadenze o interpretazioni non presenti.
- Riscrivi in italiano semplice e professionale per chi compra, vende, affitta o possiede casa.
- Mantieni 10 card, massimo 420 caratteri per card.
- Card 10: fonte, data e invito a consultare l'Agenzia delle Entrate.
- Crea anche caption social e disclaimer: “Contenuto informativo, non consulenza fiscale o legale.”
- Se la fonte è archiviata/scaduta o riguarda anni precedenti, dichiaralo chiaramente e NON presentarla come novità.

BOZZA SOURCE-LOCKED:
"""
    return head+"\n\n".join(f"CARD {i+1} — {h}\n{b}" for i,(h,b) in enumerate(cs))

def write(story,pages):
    now=datetime.now(ROME); date=now.strftime("%Y-%m-%d"); out=PUBLIC/date; out.mkdir(parents=True,exist_ok=True); cs=cards(story)
    for i,(h,b) in enumerate(cs,1): render(out/f"{i:02d}.png",i,h,b)
    caption=f"""🏠 F1 INFORMA | {story.get('title','Aggiornamento casa')}

Abbiamo consultato una fonte ufficiale dell’Agenzia delle Entrate e riassunto i punti principali in 10 card.

Fonte: {story['url']}
Aggiornamento indicato dalla fonte: {story.get('updated') or 'non specificato'}

Salva il post e consulta sempre la pagina ufficiale per il testo completo e aggiornato.

Contenuto informativo, non consulenza fiscale o legale.
#F1Informa #F1Immobiliare #Casa #Immobiliare #AgenziaDelleEntrate"""
    (out/"caption.txt").write_text(caption,encoding="utf-8"); (out/"prompt-chatgpt.txt").write_text(prompt(story,cs),encoding="utf-8")
    meta={"generated_at":now.isoformat(),"status":"DA_APPROVARE","story":{k:story.get(k) for k in ["title","url","updated","hash"]},"pages_checked":len([p for p in pages if not p.get("error")]),"errors":[p for p in pages if p.get("error")][:15]}
    (out/"sources.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    shutil.make_archive(str(out),"zip",root_dir=out)
    latest={"ready":True,"date":date,"path":f"f1-informa-data/{date}","title":story.get("title"),"status":"DA_APPROVARE","source_url":story.get("url"),"updated":story.get("updated") or ""}
    PUBLIC.mkdir(parents=True,exist_ok=True); (PUBLIC/"latest.json").write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding="utf-8")
    return out

def prune(days=45):
    if not PUBLIC.exists(): return
    cutoff=datetime.now(ROME).timestamp()-days*86400
    for x in PUBLIC.iterdir():
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(\.zip)?",x.name): continue
        stem=x.name.replace(".zip","")
        try: ts=datetime.strptime(stem,"%Y-%m-%d").replace(tzinfo=ROME).timestamp()
        except ValueError: continue
        if ts<cutoff: shutil.rmtree(x) if x.is_dir() else x.unlink(missing_ok=True)

def update(pages,story):
    s=state(); s["hashes"]={p["url"]:p["hash"] for p in pages if p.get("url") and p.get("hash")}
    s.setdefault("published_log",[]).append({"url":story["url"],"at":datetime.now(ROME).isoformat()}); s["published_log"]=s["published_log"][-300:]; s["last_story"]=story["url"]; s["last_run"]=datetime.now(ROME).isoformat(); save(s)
def should(force=False):
    if force: return True
    now=datetime.now(ROME)
    return now.hour==17 and not state().get("last_run","").startswith(now.strftime("%Y-%m-%d"))
def selftest():
    fake={"title":"Test F1 Informa","url":"https://www.agenziaentrate.gov.it/portale/aree-tematiche/casa","updated":"4 ottobre 2026","hash":"x","text":"Questa è una pagina di test. I contribuenti possono verificare i requisiti nella fonte ufficiale. La detrazione di esempio è indicata solo nel test. È necessario consultare la pagina aggiornata. Attenzione alle esclusioni e alle scadenze indicate dalla fonte."}
    cs=cards(fake); assert len(cs)==10
    sample=BeautifulSoup("<html><head><title>Acquisto prima casa - Agenzia delle Entrate</title></head><body><main><h1>Menu principale</h1><h2>Acquisto prima casa</h2><p>Agevolazioni per la casa.</p></main></body></html>","html.parser")
    sample_main=sample.find("main")
    assert page_title(sample,sample_main,"https://www.agenziaentrate.gov.it/portale/schede/agevolazioni/scheda-acquisto-prima-casa/acquisto-prima-casa-a-chi-interessa-cittadini")=="Acquisto prima casa"
    tmp=ROOT/".self-test-card.png"; render(tmp,1,*cs[0]); assert tmp.stat().st_size>1000; tmp.unlink(); print("F1_INFORMA_SELF_TEST_OK")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--force",action="store_true"); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: selftest(); return
    if not should(a.force): print("Fuori dalla finestra delle 17:00 Europe/Rome o già eseguito oggi."); return
    pages=crawl(); story=pick(pages,state())
    if not story: print("Nessun contenuto valido trovato."); return
    out=write(story,pages); update(pages,story); prune(int(CONFIG.get("retention_days",45))); print(f"F1 INFORMA generato in DA_APPROVARE: {out}")
if __name__=="__main__": main()
