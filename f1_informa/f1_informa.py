#!/usr/bin/env python3
import argparse, hashlib, json, os, re, shutil, textwrap, time
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
        if low in generic or low.startswith("menu principale") or low.startswith("menu della sezione"): continue
        if 6 <= len(value) <= 160 and relevant(value,base):
            return re.sub(r"\s*[-|]\s*Agenzia delle Entrate.*$","",value,flags=re.I).strip()
    slug=urlparse(base).path.rstrip("/").split("/")[-1]
    slug=re.sub(r"-(cittadini|infogen.*)$","",slug,flags=re.I)
    value=norm(slug.replace("-"," "))
    return value[:1].upper()+value[1:] if value else "Aggiornamento casa"

def article_text(main):
    lines=[norm(x) for x in main.get_text("\n",strip=True).splitlines() if norm(x)]
    marker=None
    for i,line in enumerate(lines):
        if re.search(r"^Ultimo aggiornamento\s*:",line,re.I):
            marker=i
            break
    if marker is None:
        return norm(" ".join(lines))
    body=lines[marker+1:]
    stop_prefixes=("Link correlati","La dichiarazione precompilata","Chiudi Modalità di accesso","Seguici sul nostro canale")
    clean=[]
    for line in body:
        if any(line.lower().startswith(x.lower()) for x in stop_prefixes):
            break
        clean.append(line)
    return norm(" ".join(clean)) or norm(" ".join(body))

def extract(html,base):
    soup=BeautifulSoup(html,"html.parser")
    for tag in soup(["script","style","noscript","svg","footer"]): tag.decompose()
    main=soup.find("main") or soup.find(attrs={"role":"main"}) or soup.body or soup
    title=page_title(soup,main,base)
    raw_text=norm(main.get_text("\n",strip=True))
    text=article_text(main)
    links=[]
    for a in main.find_all("a",href=True):
        href=canon(urljoin(base,a.get("href"))); label=norm(a.get_text(" ",strip=True))
        if href and allowed(href): links.append((href,label))
    m=re.search(r"Ultimo aggiornamento\s*:?\s*([0-9]{1,2}\s+[A-Za-zàèéìòù]+\s+[0-9]{4}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",raw_text,re.I)
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

def build_caption(story,cs):
    title=story.get("title") or "Aggiornamento casa"
    useful=[]
    for heading,body in cs[1:9]:
        body=norm(body)
        if not body or body.lower().startswith(("consulta la fonte","la pagina ufficiale descrive","verifica requisiti","controlla sempre")):
            continue
        useful.append((heading,trim(body,330)))
    lines=[f"🏠 F1 INFORMA | {title}",""]
    for heading,body in useful[:5]:
        lines.append(f"• {heading}: {body}")
    lines.extend([
        "",
        f"Fonte ufficiale: {story['url']}",
        f"Aggiornamento indicato dalla fonte: {story.get('updated') or 'non specificato'}",
        "",
        "Contenuto informativo, non consulenza fiscale o legale.",
        "#F1Informa #F1Immobiliare #Casa #Immobiliare #AgenziaDelleEntrate",
    ])
    caption="\n".join(lines)
    return caption[:2100].rstrip()

def graphics_prompt(story,cs,caption):
    outline="\n\n".join(f"CARD {i+1} — {h}\n{b}" for i,(h,b) in enumerate(cs))
    return f"""CREA LA GRAFICA COMPLETA DEL CAROSELLO SOCIAL F1 INFORMA PER F1 IMMOBILIARE.

OBIETTIVO
Genera un unico progetto grafico coerente composto da 10 GRAFICHE SEPARATE, una per ogni card del carosello.
Le 10 immagini devono appartenere alla stessa realizzazione: stessa palette, stessi font, stessa gerarchia, stessa direzione artistica.
Formato di OGNI immagine: verticale 4:5, pensato per Instagram e Facebook.
Non creare una sola tavola con 10 riquadri: servono 10 immagini separate.

BRAND
F1 IMMOBILIARE
Rubrica: F1 INFORMA · Casa, fisco e mercato
Palette: verde immobiliare profondo, bianco/panna, accenti oro.
Stile: elegante, professionale, moderno, autorevole, immobiliare.
Usa fotografia immobiliare, ambienti casa, elementi architettonici, icone e grandi numeri quando utili.
Evita card composte quasi esclusivamente da lunghi paragrafi.
Il testo deve essere breve, leggibile e visivamente gerarchizzato.

REGOLA FONDAMENTALE
Usa ESCLUSIVAMENTE i dati contenuti nella caption e nella bozza source-locked sotto.
NON inventare percentuali, importi, scadenze, requisiti, leggi o interpretazioni.
Mantieni esatti numeri, date e condizioni.
Inserisci discretamente "Fonte: Agenzia delle Entrate".
Contenuto informativo, non consulenza fiscale o legale.

CAPTION GENERATA AUTOMATICAMENTE DA F1 INFORMA:
--- INIZIO CAPTION ---
{caption}
--- FINE CAPTION ---

FONTE UFFICIALE:
{story['url']}
Ultimo aggiornamento rilevato: {story.get('updated') or 'non indicato'}

STRUTTURA SOURCE-LOCKED DELLE 10 CARD:
{outline}

DIREZIONE DELLE CARD
1. Copertina forte e molto visiva.
2. Sintesi immediata.
3. A chi interessa.
4. Vantaggio principale.
5. Numeri importanti con forte gerarchia grafica.
6. Requisiti con icone/check visivi.
7. Date/scadenze con elemento calendario.
8. Attenzione/limiti.
9. Cosa fare adesso.
10. Chiusura F1 INFORMA + fonte ufficiale.

STRATEGIA DI GENERAZIONE AUTOMATICA
NON generare mai una tavola unica, una griglia o un collage con più card.
Il worker automatico richiederà UNA SOLA CARD ALLA VOLTA, in 10 richieste consecutive nella stessa chat.
Ogni richiesta deve produrre UNA SOLA IMMAGINE verticale 4:5.
Mantieni identici stile, palette, font, gerarchia, margini, footer e direzione artistica tra una card e la successiva.

OUTPUT DEL PROGETTO
10 FILE IMMAGINE DISTINTI, numerati 1/10 … 10/10, da pubblicare insieme come un unico carosello.
"""

def _supabase_headers():
    key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()
    if not key: return None
    return {"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}

def enqueue_graphics(story,caption,gprompt,date,card_specs):
    headers=_supabase_headers()
    if not headers:
        return {"queued":False,"reason":"SUPABASE_SERVICE_ROLE_KEY non disponibile"}
    base=os.getenv("SUPABASE_URL","https://nqnmlsmeiynxbdojeyjt.supabase.co").rstrip("/")
    for attempt in range(1,4):
        try:
            rc=requests.get(
                f"{base}/rest/v1/f1_content_clients",
                headers=headers,
                params={"select":"id,owner_id","slug":"eq.f1-immobiliare","limit":"1"},
                timeout=30,
            )
            rc.raise_for_status(); clients=rc.json()
            if not clients: raise RuntimeError("Cliente f1-immobiliare non trovato")
            client=clients[0]
            unique=f"f1-informa-graphics:{date}:{story.get('hash','')[:16]}"
            recheck=requests.get(
                f"{base}/rest/v1/f1_intelligence_jobs",
                headers=headers,
                params={"select":"id,status","owner_id":f"eq.{client['owner_id']}","unique_key":f"eq.{unique}","limit":"1"},
                timeout=30,
            )
            recheck.raise_for_status(); existing=recheck.json()
            if existing:
                return {"queued":True,"job_id":existing[0]["id"],"status":existing[0].get("status"),"reused":True}
            payload={
                "owner_id":client["owner_id"],
                "client_id":client["id"],
                "job_type":"F1_INFORMA_CHATGPT_GRAPHICS",
                "status":"QUEUED",
                "stage":"GRAFICA_IN_CODA",
                "unique_key":unique,
                "max_attempts":3,
                "payload":{
                    "date":date,
                    "title":story.get("title"),
                    "caption":caption,
                    "graphics_prompt":gprompt,
                    "cards":[
                        {"index":i+1,"title":h,"body":b}
                        for i,(h,b) in enumerate(card_specs)
                    ],
                    "generation_strategy":"one_card_per_request",
                    "source_url":story.get("url"),
                    "source_updated":story.get("updated"),
                    "source_hash":story.get("hash"),
                    "expected_images":10,
                    "target_platforms":["facebook","instagram"],
                    "auto_publish":True,
                    "image_made_with_ai":True,
                    "brand":"F1 Immobiliare",
                    "rubric":"F1 INFORMA",
                },
            }
            rp=requests.post(
                f"{base}/rest/v1/f1_intelligence_jobs",
                headers={**headers,"Prefer":"return=representation"},
                json=payload,
                timeout=30,
            )
            rp.raise_for_status(); rows=rp.json()
            if not rows: raise RuntimeError("Job F1 INFORMA non creato")
            return {"queued":True,"job_id":rows[0]["id"],"status":"QUEUED","reused":False}
        except Exception as e:
            if attempt==3:
                return {"queued":False,"reason":str(e)[:500]}
            time.sleep(attempt*2)

def write(story,pages):
    now=datetime.now(ROME); date=now.strftime("%Y-%m-%d"); out=PUBLIC/date; out.mkdir(parents=True,exist_ok=True); cs=cards(story)
    # Le card Pillow restano una bozza source-locked di sicurezza. La grafica
    # finale destinata alla pubblicazione viene prodotta dal worker ChatGPT.
    for i,(h,b) in enumerate(cs,1): render(out/f"{i:02d}.png",i,h,b)
    caption=build_caption(story,cs)
    gprompt=graphics_prompt(story,cs,caption)
    (out/"caption.txt").write_text(caption,encoding="utf-8")
    (out/"prompt-chatgpt.txt").write_text(gprompt,encoding="utf-8")
    queue=enqueue_graphics(story,caption,gprompt,date,cs)
    status="GRAFICA_IN_CODA" if queue.get("queued") else "ERRORE_AUTOMAZIONE"
    meta={
        "generated_at":now.isoformat(),
        "status":status,
        "story":{k:story.get(k) for k in ["title","url","updated","hash"]},
        "pages_checked":len([p for p in pages if not p.get("error")]),
        "graphics_job":queue,
        "errors":[p for p in pages if p.get("error")][:15],
    }
    (out/"sources.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    shutil.make_archive(str(out),"zip",root_dir=out)
    latest={
        "ready":True,
        "date":date,
        "path":f"f1-informa-data/{date}",
        "title":story.get("title"),
        "status":status,
        "source_url":story.get("url"),
        "updated":story.get("updated") or "",
        "graphics_job_id":queue.get("job_id"),
        "graphics_queue_error":queue.get("reason"),
    }
    PUBLIC.mkdir(parents=True,exist_ok=True)
    (PUBLIC/"latest.json").write_text(json.dumps(latest,ensure_ascii=False,indent=2),encoding="utf-8")
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
    cap=build_caption(fake,cs); assert "F1 INFORMA" in cap
    gp=graphics_prompt(fake,cs,cap); assert "10 GRAFICHE SEPARATE" in gp and cap in gp
    sample=BeautifulSoup("<html><head><title>Acquisto prima casa - Agenzia delle Entrate</title></head><body><main><h1>Menu principale</h1><h2>Menu della sezione Acquisto prima casa</h2><h2>Agevolazione acquisto prima casa - Che cos'è</h2><p>Facebook e navigazione</p><p>Ultimo aggiornamento: 29 maggio 2026</p><p>L'agevolazione consente di pagare imposte ridotte.</p><p>Imposta di registro al 2% in presenza delle condizioni previste.</p><p>Link correlati</p><p>Rumore successivo</p></main></body></html>","html.parser")
    sample_main=sample.find("main")
    assert page_title(sample,sample_main,"https://www.agenziaentrate.gov.it/portale/schede/agevolazioni/scheda-acquisto-prima-casa/infogen-agevolazioni-acquisto-prima-casa-cittadini")=="Agevolazione acquisto prima casa - Che cos'è"
    cleaned=article_text(sample_main)
    assert cleaned.startswith("L'agevolazione consente")
    assert "Facebook" not in cleaned and "Rumore successivo" not in cleaned
    tmp=ROOT/".self-test-card.png"; render(tmp,1,*cs[0]); assert tmp.stat().st_size>1000; tmp.unlink(); print("F1_INFORMA_SELF_TEST_OK")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--force",action="store_true"); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: selftest(); return
    if not should(a.force): print("Fuori dalla finestra delle 17:00 Europe/Rome o già eseguito oggi."); return
    pages=crawl(); story=pick(pages,state())
    if not story: print("Nessun contenuto valido trovato."); return
    out=write(story,pages); update(pages,story); prune(int(CONFIG.get("retention_days",45))); print(f"F1 INFORMA generato e inviato all'autopilota grafico: {out}")
if __name__=="__main__": main()
