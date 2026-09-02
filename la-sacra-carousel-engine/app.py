from flask import Flask, request, render_template_string, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests, re, json, html

app = Flask(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"}

DEFAULT_BRAND = {
    "bg": "#ffffff",
    "fg": "#171717",
    "accent": "#8b7355",
    "muted": "#f3f1ed",
    "heading_font": "Arial, Helvetica, sans-serif",
    "body_font": "Arial, Helvetica, sans-serif",
}

def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return r

def uniq(seq):
    out=[]; seen=set()
    for x in seq:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

def normalize_image(u, base):
    if not u: return None
    if u.startswith('//'): u='https:'+u
    elif u.startswith('/'): u=urljoin(base,u)
    u=u.replace('\\u0026','&')
    return u

def extract_product(url):
    text=get(url).text
    soup=BeautifulSoup(text,'html.parser')
    title=(soup.find('meta',property='og:title') or {}).get('content') or (soup.title.string.strip() if soup.title and soup.title.string else 'Immobile')
    description=(soup.find('meta',property='og:description') or {}).get('content') or ''
    price=''
    images=[]
    for m in soup.find_all('meta'):
        prop=m.get('property','')
        name=m.get('name','')
        content=m.get('content','')
        if prop in ('og:image','og:image:secure_url') or name in ('twitter:image','twitter:image:src'):
            images.append(normalize_image(content,url))
    for s in soup.find_all('script',type='application/ld+json'):
        try:
            data=json.loads(s.string or '{}')
            nodes=data if isinstance(data,list) else [data]
            for d in nodes:
                if not isinstance(d,dict): continue
                im=d.get('image')
                if isinstance(im,str): images.append(normalize_image(im,url))
                elif isinstance(im,list): images += [normalize_image(x,url) for x in im if isinstance(x,str)]
                offers=d.get('offers')
                if isinstance(offers,dict) and offers.get('price'): price=str(offers['price'])
        except Exception:
            pass
    # Shopify CDN URLs embedded in HTML / JSON data
    raw=re.findall(r'https?:\\?/\\?/[A-Za-z0-9._~:/?#@!$&()*+,;=%-]+', text)
    for x in raw:
        x=x.replace('\\/','/')
        if 'cdn.shopify.com' in x and re.search(r'\\.(?:jpg|jpeg|png|webp)(?:\\?|$)',x,re.I): images.append(x)
    for img in soup.find_all('img'):
        for a in ('src','data-src','data-original'):
            images.append(normalize_image(img.get(a),url))
        srcset=img.get('srcset','')
        for item in srcset.split(','):
            if item.strip(): images.append(normalize_image(item.strip().split()[0],url))
    images=[x for x in uniq(images) if x and not any(k in x.lower() for k in ('logo','icon','payment','badge','placeholder'))]
    return {"title": title, "description": description, "price": price, "images": images, "html": text}

def extract_brand(site='https://lasacraimmobiliare.it/'):
    b=DEFAULT_BRAND.copy()
    try:
        t=get(site).text
        soup=BeautifulSoup(t,'html.parser')
        css=t
        for link in soup.find_all('link',rel='stylesheet')[:8]:
            href=link.get('href')
            if href:
                try: css += '\n'+get(urljoin(site,href)).text
                except Exception: pass
        # Shopify themes often expose color variables and font families.
        colors=re.findall(r'#[0-9a-fA-F]{6}',css)
        filtered=[c.lower() for c in colors if c.lower() not in ('#ffffff','#000000')]
        if filtered: b['accent']=filtered[0]
        fontvars=re.findall(r'--font-(?:heading|body)-family\\s*:\\s*([^;}{]+)',css,re.I)
        if fontvars:
            b['heading_font']=fontvars[0].strip()
            b['body_font']=fontvars[-1].strip()
    except Exception:
        pass
    return b

def price_text(p):
    if not p: return '€139.000'
    try:
        n=float(str(p).replace('.','').replace(',','.'))
        return '€{:,.0f}'.format(n).replace(',','.')
    except Exception: return str(p)

def slides_for(data):
    p=price_text(data.get('price'))
    return [
      {"name":"01 Prezzo / spazio","slides":[
        ("100 M² A MONCALIERI",p),("SPAZIO VERO","Circa 100 m² da vivere"),("2 CAMERE","Più una grande zona giorno"),("LIBERO SUBITO","Niente attese per la consegna"),("STRADA GENOVA","Moncalieri"),("VEDILO DAL VIVO","Immobiliare La Sacra") ]},
      {"name":"02 Confronto mercato","slides":[
        ("QUANTO COSTANO 100 M² A MONCALIERI?","Un confronto aiuta a capire il posizionamento"),("QUESTO IMMOBILE",p),("CIRCA 100 M²","Prezzo richiesto ≈ €1.390/m²"),("NON SOLO PREZZO","Contano stato, piano, esposizione e dotazioni"),("VA ANALIZZATO","Non giudicato da una sola cifra"),("PRENOTA LA VISITA","Immobiliare La Sacra") ]},
      {"name":"03 Famiglia","slides":[
        ("QUANDO UNA CAMERA NON BASTA PIÙ","Lo spazio cambia le giornate"),("DUE CAMERE","Per famiglia, studio o ospiti"),("LIVING AMPIO","Soggiorno e cucina a vista"),("100 M² CIRCA","Spazi più facili da organizzare"),("POSTO AUTO + CANTINA","Praticità quotidiana"),("MONCALIERI",p) ]},
      {"name":"04 Prima casa","slides":[
        ("LA PRIMA CASA DEVE ESSERE PICCOLA?","Non necessariamente"),("100 M² CIRCA","Più margine per il futuro"),("2 CAMERE","Senza dover cambiare casa subito"),("RISCALDAMENTO AUTONOMO","Gestione più diretta"),("LIBERO SUBITO","Pronto per essere valutato"),("STRADA GENOVA",p) ]},
      {"name":"05 Libero subito","slides":[
        ("LA CASA C'È. ED È GIÀ LIBERA.","Disponibilità immediata"),("VISITALA","Senza attendere liberazioni future"),("VALUTALA","Con calma e con dati reali"),("ORGANIZZA IL MUTUO","Con tempi più prevedibili"),("PROGRAMMA IL TRASFERIMENTO","Senza dipendere da un inquilino"),("MONCALIERI",p) ]},
      {"name":"06 Riscaldamento autonomo","slides":[
        ("IL COMFORT LO GESTISCI TU","Riscaldamento autonomo"),("QUANDO ACCENDERLO","Decidi tu"),("CHE TEMPERATURA TENERE","Decidi tu"),("COME GESTIRE I CONSUMI","Più controllo"),("UNA DOTAZIONE CONCRETA","Da valutare prima dell'acquisto"),("100 M² · MONCALIERI",p) ]},
      {"name":"07 Tripla esposizione","slides":[
        ("LA LUCE CAMBIA UNA CASA","Tripla esposizione"),("PIÙ AFFACCI","Più aperture verso l'esterno"),("PIÙ LUCE NATURALE","Durante diversi momenti della giornata"),("LIVING DA VIVERE","La zona giorno è protagonista"),("GUARDALA DAL VIVO","Le foto non raccontano tutto"),("STRADA GENOVA",p) ]},
      {"name":"08 Dotazioni","slides":[
        ("UNA CASA NON FINISCE ALLA PORTA","Le dotazioni contano"),("POSTO AUTO INTERNO","Un problema in meno"),("CANTINA","Spazio che serve davvero"),("BALCONE","Uno sfogo esterno"),("RIPOSTIGLIO","Ordine quotidiano"),("MONCALIERI",p) ]},
      {"name":"09 Zona","slides":[
        ("NON COMPRARE SOLO LA CASA","Guarda cosa c'è intorno"),("STRADA GENOVA","Moncalieri"),("SERVIZI","Scuole, negozi e attività nell'area"),("COLLEGAMENTI","Asse urbano comodo per gli spostamenti"),("VITA QUOTIDIANA","La zona pesa quanto i metri quadri"),("VISITA CASA + QUARTIERE",p) ]},
      {"name":"10 Trasparenza","slides":[
        ("100 M² A QUESTO PREZZO. QUAL È IL COMPROMESSO?","Nessuna casa è perfetta"),("UN SOLO BAGNO","Da valutare rispetto alle tue esigenze"),("NIENTE ASCENSORE","Elemento importante per alcuni acquirenti"),("NESSUN TERRAZZO","È presente il balcone"),("CLASSE ENERGETICA E","Dato da conoscere prima della scelta"),("È ADATTA A TE?",p) ]},
      {"name":"11 Qualificazione","slides":[
        ("QUESTA CASA È PER TE?","6 domande rapide"),("VUOI CIRCA 100 M²?","Sì / No"),("TI SERVONO DUE CAMERE?","Sì / No"),("VUOI L'AUTONOMO?","Sì / No"),("POSTO AUTO E CANTINA TI SERVONO?","Sì / No"),("HAI RISPOSTO SÌ?","Allora ha senso visitarla") ]},
      {"name":"12 Visita","slides":[
        ("LE FOTO NON BASTANO PER CAPIRE 100 M²","La visita serve a verificare"),("SPAZI","Come sono distribuiti davvero"),("LUCE","Quanto entra negli ambienti"),("RUMORI E AFFACCI","Cose che una foto non mostra"),("SENSAZIONE GENERALE","Quella non si misura online"),("PRENOTA UNA VISITA","Immobiliare La Sacra") ]}
    ]

PAGE='''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>La Sacra Carousel Engine</title>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script><script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
<style>:root{--bg:{{brand.bg}};--fg:{{brand.fg}};--accent:{{brand.accent}};--muted:{{brand.muted}};--head:{{brand.heading_font|safe}};--body:{{brand.body_font|safe}}}*{box-sizing:border-box}body{margin:0;background:#ece9e3;color:#222;font-family:var(--body)}header{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #ddd;padding:14px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}header strong{font-family:var(--head);font-size:20px}input{flex:1;min-width:320px;padding:12px 14px;border:1px solid #bbb;border-radius:8px}button{border:0;border-radius:8px;padding:11px 14px;background:var(--fg);color:#fff;font-weight:700;cursor:pointer}.secondary{background:#fff;color:#222;border:1px solid #bbb}.status{font-size:13px;color:#666}.wrap{max-width:1280px;margin:24px auto;padding:0 18px}.meta{background:#fff;border-radius:14px;padding:18px;margin-bottom:24px}.campaign{margin:30px 0 44px}.campaign h2{font-family:var(--head);font-size:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}.slide{aspect-ratio:4/5;background:var(--bg);position:relative;overflow:hidden;border-radius:2px;box-shadow:0 6px 20px #0002}.slide img{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}.overlay{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.06),rgba(0,0,0,.62))}.content{position:absolute;left:0;right:0;bottom:0;padding:30px;color:white}.kicker{font-size:12px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;margin-bottom:10px}.title{font-family:var(--head);font-size:29px;line-height:1.02;font-weight:800;text-transform:uppercase}.sub{font-size:15px;line-height:1.3;margin-top:10px;max-width:90%}.brand{position:absolute;top:18px;left:20px;color:#fff;font-weight:800;font-size:12px;letter-spacing:.12em}.num{position:absolute;top:18px;right:20px;color:#fff;font-size:12px}.noimg{background:linear-gradient(135deg,var(--fg),var(--accent))}.toolbar{display:flex;gap:8px;margin:10px 0 14px}.toolbar button{font-size:12px}.warning{padding:10px 12px;background:#fff4d6;border-left:4px solid #d39b00;margin-top:12px}</style></head><body>
<header><strong>IMMOBILIARE LA SACRA · Carousel Engine</strong><form method="get" style="display:flex;gap:8px;flex:1"><input name="url" value="{{url}}" placeholder="Incolla il link dell'immobile"><button>ANALIZZA</button></form><button class="secondary" onclick="downloadAll()">SCARICA TUTTI I PNG</button><span class="status" id="st"></span></header>
<div class="wrap">{% if data %}<div class="meta"><b>{{data.title}}</b><br>{{data.images|length}} immagini recuperate dal sito. <span>{{price}}</span>{% if data.images|length<3 %}<div class="warning">Sono state trovate poche immagini. Il motore continuerà a usare solo quelle reali disponibili, senza stock e senza immagini generate.</div>{% endif %}</div>{% endif %}
{% for c in campaigns %}<section class="campaign"><h2>{{c.name}}</h2><div class="toolbar"><button onclick="downloadCampaign({{loop.index0}})">Scarica carosello</button></div><div class="grid campaign-grid" data-campaign="{{loop.index0}}">{% for s in c.slides %}<div class="slide {% if not data.images %}noimg{% endif %}" id="c{{loop.index0}}s{{loop.index0}}-{{loop.index}}">{% if data.images %}<img crossorigin="anonymous" src="{{data.images[(loop.index0 + loop.index0*2) % data.images|length]}}"><div class="overlay"></div>{% endif %}<div class="brand">IMMOBILIARE LA SACRA</div><div class="num">{{'%02d'|format(loop.index)}} / {{'%02d'|format(c.slides|length)}}</div><div class="content"><div class="kicker">MONCALIERI · STRADA GENOVA</div><div class="title">{{s[0]}}</div><div class="sub">{{s[1]}}</div></div></div>{% endfor %}</div></section>{% endfor %}</div>
<script>async function shot(el){return await html2canvas(el,{useCORS:true,allowTaint:false,scale:2,backgroundColor:null})} async function addGrid(zip,grid,prefix){let els=[...grid.querySelectorAll('.slide')];for(let i=0;i<els.length;i++){document.querySelector('#st').textContent=`Esporto ${prefix} ${i+1}/${els.length}`;let c=await shot(els[i]);let b=await new Promise(r=>c.toBlob(r,'image/png'));zip.file(`${prefix}_${String(i+1).padStart(2,'0')}.png`,b)}} async function downloadCampaign(i){let zip=new JSZip();await addGrid(zip,document.querySelector(`[data-campaign="${i}"]`),`carosello_${String(i+1).padStart(2,'0')}`);let blob=await zip.generateAsync({type:'blob'});save(blob,`LaSacra_carosello_${String(i+1).padStart(2,'0')}.zip`);document.querySelector('#st').textContent='Pronto'} async function downloadAll(){let zip=new JSZip();let grids=[...document.querySelectorAll('.campaign-grid')];for(let i=0;i<grids.length;i++)await addGrid(zip,grids[i],`carosello_${String(i+1).padStart(2,'0')}`);let blob=await zip.generateAsync({type:'blob'});save(blob,'LaSacra_Moncalieri_12_caroselli.zip');document.querySelector('#st').textContent='Pronto'} function save(blob,name){let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000)}</script></body></html>'''

@app.route('/')
def home():
    url=request.args.get('url','https://lasacraimmobiliare.it/products/alloggio-a-moncalieri-di-4-locali?variant=54853547065671').strip()
    data=None; err=''
    try: data=extract_product(url) if url else None
    except Exception as e: err=str(e); data={"title":"Immobile","description":"","price":"","images":[]}
    brand=extract_brand()
    campaigns=slides_for(data or {})
    return render_template_string(PAGE,url=url,data=data,brand=brand,campaigns=campaigns,price=price_text((data or {}).get('price')),err=err)

@app.route('/api/extract')
def api_extract():
    try:
        d=extract_product(request.args['url']); d.pop('html',None); return jsonify(d)
    except Exception as e: return jsonify({"error":str(e)}),400

if __name__=='__main__':
    app.run(host='127.0.0.1',port=5055,debug=False)
