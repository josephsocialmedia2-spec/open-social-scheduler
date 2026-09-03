(()=>{
  const RADAR_URL='https://josephsocialmedia2-spec.github.io/immobili-in-zona/seller_radar_auto/data/giro_acquisizione.csv';
  const LAUNCHER='https://josephsocialmedia2-spec.github.io/launcher-dashboard/';
  const ROUTE=['susa','bussoleno','chianocco','san giorio di susa','bruzolo','san didero','borgone susa','villar focchiardo','sant antonino di susa'];
  const RANK=new Map(ROUTE.map((x,i)=>[x,i]));
  let radarRows=[];

  const norm=s=>String(s||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[’']/g,' ').replace(/\s+/g,' ');
  function comune(s){let n=norm(s);if(n==='borgone di susa')return'borgone susa';if(n==='santantonino di susa')return'sant antonino di susa';return n}
  function parseCSV(t){t=t.replace(/^\uFEFF/,'');let rows=[],r=[],c='',q=false;for(let i=0;i<t.length;i++){let x=t[i];if(q){if(x==='"'&&t[i+1]==='"'){c+='"';i++}else if(x==='"')q=false;else c+=x}else if(x==='"')q=true;else if(x===','){r.push(c);c=''}else if(x==='\n'){r.push(c);rows.push(r);r=[];c=''}else if(x!=='\r')c+=x}if(c||r.length){r.push(c);rows.push(r)}if(rows.length<2)return[];let h=rows.shift();return rows.filter(x=>x.some(Boolean)).map(x=>Object.fromEntries(h.map((k,i)=>[k.trim(),(x[i]||'').trim()]))) }
  function maps(r){return'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent((r.DOVE_ANDRE||'')+', '+(r.COMUNE||'')+', TO, Italia')}
  function validRadar(r){const c=comune(r.COMUNE);if(!RANK.has(c))return false;if(c==='sant ambrogio di torino')return false;return !/DA VERIFICARE/i.test(r.DOVE_ANDRE||'')}
  function radarSort(a,b){return(RANK.get(comune(a.COMUNE))??999)-(RANK.get(comune(b.COMUNE))??999)||(+b.SCORE||0)-(+a.SCORE||0)}
  async function loadRadar(){
    try{
      const res=await fetch(RADAR_URL+'?v='+Date.now(),{cache:'no-store'});
      if(!res.ok)throw Error('HTTP '+res.status);
      radarRows=parseCSV(await res.text()).filter(validRadar).sort(radarSort);
      return radarRows;
    }catch(e){radarRows=[];return[]}
  }

  const coreAiLocal=aiLocal;
  aiLocal=function(){
    const core=coreAiLocal();
    if(core&&core.type!=='FARMING')return core;
    const r=radarRows.find(x=>/VAI IN ZONA/i.test(x.AZIONE||''))||radarRows[0];
    if(r)return{type:'RADAR',title:'VAI A '+String(r.COMUNE||'').toUpperCase()+' · '+(r.DOVE_ANDRE||'INDIRIZZO'),body:(r.COSA_CERCO||'Lavora questo indirizzo.')+(r.PREZZO?' · '+r.PREZZO:''),info:'oggi',radar:r};
    return core;
  };

  const coreSync=sync;
  sync=async function(){
    await coreSync();
    await loadRadar();
    renderToday();
  };

  const coreExecute=execute;
  execute=function(){
    const a=currentAction||aiLocal();
    if(a?.type==='RADAR'&&a.radar){
      const r=a.radar;
      openModal('VAI IN ZONA',`<h3>${esc(r.COMUNE||'')} · ${esc(r.DOVE_ANDRE||'')}</h3><p>${esc(r.COSA_CERCO||'Lavora questo indirizzo secondo la procedura assegnata.')}</p><p class="muted">Vai sul posto. Osserva solo fatti reali. Se parli con qualcuno, registra esclusivamente ciò che ti viene detto. Non inventare conclusioni.</p><div class="row"><a class="btn primary linkbtn" target="_blank" rel="noopener" href="${maps(r)}">APRI MAPPA</a>${r.URL?`<a class="btn linkbtn" target="_blank" rel="noopener" href="${esc(r.URL)}">APRI FONTE</a>`:''}<button class="btn" id="radarDone">FATTO → AVANTI</button></div>`);
      setTimeout(()=>{const b=document.querySelector('#radarDone');if(b)b.onclick=()=>{document.querySelector('#modal').close();toast('Attività terminata. Registra eventuali informazioni nel CRM.');}},0);
      return;
    }
    return coreExecute();
  };

  const coreShowInfo=showInfo;
  showInfo=function(k){
    coreShowInfo(k);
    if(k==='oggi')setTimeout(()=>{
      const body=document.querySelector('#modalBody');
      if(!body||document.querySelector('#f1SystemMap'))return;
      const box=document.createElement('div');
      box.innerHTML='<hr style="border:0;border-top:1px solid #d9ded9;margin:16px 0"><button class="btn" id="f1SystemMap">FUNZIONI DEL SISTEMA</button>';
      body.appendChild(box);
      document.querySelector('#f1SystemMap').onclick=()=>openModal('COSA FA F1 OS',`<p><b>Tu parti sempre da OGGI.</b> Il sistema apre gli strumenti quando servono.</p><div class="stack"><a class="item" href="${LAUNCHER}telefonate-oggi.html"><b>Centrale telefonate</b><small>Chiamate guidate e registrazione esiti.</small></a><a class="item" href="${LAUNCHER}seller-radar-unico.html"><b>Seller Radar</b><small>Segnali territoriali e priorità.</small></a><a class="item" href="${LAUNCHER}market-intelligence.html"><b>Market Intelligence</b><small>Dati da usare prima di appuntamenti e valutazioni.</small></a><a class="item" href="${LAUNCHER}radar-edilizio.html"><b>Radar edilizio</b><small>Permessi, cantieri e segnali pubblici.</small></a><a class="item" href="${LAUNCHER}giro-acquisizione.html"><b>Giro acquisizione</b><small>Percorso operativo sul territorio.</small></a><button class="item" id="goPractices"><b>Pratiche</b><small>Incarichi, documenti, Open House e piano marketing.</small></button></div><p class="muted">Queste funzioni non sono un secondo software: sono strumenti interni di F1 OS. L’AI decide quando usarli.</p>`);
      setTimeout(()=>{const g=document.querySelector('#goPractices');if(g)g.onclick=()=>{document.querySelector('#modal').close();nav('pratiche');}},0);
    },0);
  };

  function applyEntryMode(){
    const p=new URLSearchParams(location.search),screen=p.get('screen');
    if(['oggi','crm','pratiche'].includes(screen))nav(screen);
    if(p.get('source')==='pc'||location.pathname.includes('/launcher-dashboard/'))document.body.dataset.device='pc';
    const topSmall=document.querySelector('.top small');
    if(topSmall)topSmall.textContent='F1 OS IMMOBILIARE · UNICA APP PC + TELEFONO';
  }

  function addDesktopGuide(){
    if(document.querySelector('#f1UnifiedBadge'))return;
    const hero=document.querySelector('.hero');if(!hero)return;
    const b=document.createElement('div');b.id='f1UnifiedBadge';b.className='state';b.textContent='STESSO F1 OS · STESSO CRM · PC E TELEFONO';hero.appendChild(b);
  }

  async function runSelfDiagnosis(){
    const hero=document.querySelector('.hero');if(!hero)return;
    let box=document.querySelector('#f1Diag');
    if(!box){box=document.createElement('div');box.id='f1Diag';box.className='state';hero.appendChild(box)}
    const errors=[];
    ['actionTitle','actionBody','executeBtn','cloudState','priority','contacts','practices'].forEach(id=>{if(!document.getElementById(id))errors.push('interfaccia:'+id)});
    ['sync','renderToday','nav','openModal','pushAction'].forEach(fn=>{try{if(typeof globalThis[fn]!=='function'&&typeof eval(fn)!=='function')errors.push('funzione:'+fn)}catch(e){errors.push('funzione:'+fn)}});
    const checks=['telefonate-oggi.html','seller-radar-unico.html','market-intelligence.html','giro-acquisizione.html'];
    const results=await Promise.all(checks.map(async p=>{try{const r=await fetch(LAUNCHER+p+'?diag='+Date.now(),{cache:'no-store'});return r.ok}catch(e){return false}}));
    results.forEach((ok,i)=>{if(!ok)errors.push('modulo:'+checks[i])});
    if(!radarRows.length){const r=await loadRadar();if(!r.length)errors.push('radar')}
    if(errors.length){box.textContent='AUTODIAGNOSI · ATTENZIONE: '+errors.join(', ');box.style.color='#a32626'}else{box.textContent='AUTODIAGNOSI · SISTEMA OK';box.style.color='#16814a'}
  }

  Promise.resolve(loadRadar()).then(()=>{try{renderToday()}catch(e){};runSelfDiagnosis()});
  applyEntryMode();
  addDesktopGuide();
})();