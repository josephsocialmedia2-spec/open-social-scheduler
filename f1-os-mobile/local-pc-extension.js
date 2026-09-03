(()=>{
  const qs=new URLSearchParams(location.search);
  const port=qs.get('bridge');
  if(!port||!/^[0-9]{2,5}$/.test(port))return;
  const base='http://127.0.0.1:'+port;
  document.body.dataset.device='pc';

  function addLocalPracticeTools(){
    const card=document.querySelector('[data-screen="pratiche"] article.card');
    if(!card||document.getElementById('f1LocalPracticeTools'))return;
    const box=document.createElement('div');
    box.id='f1LocalPracticeTools';
    box.className='card';
    box.style.marginTop='12px';
    box.innerHTML=`<div class="section"><h2>MOTORE PRATICHE PC</h2><button class="infoSmall" id="localPracticeInfo">ⓘ</button></div><p class="muted">Questi comandi aprono i moduli installati sul PC. I dati salvati restano collegati al CRM F1.</p><div class="row"><a class="btn primary linkbtn" href="${base}/incarico">COMPILA INCARICO DI VENDITA</a><a class="btn linkbtn" href="${base}/marketing">GUIDA MARKETING CLIENTE</a></div><div class="state">MOTORE LOCALE F1 · porta ${port}</div>`;
    card.appendChild(box);
    document.getElementById('localPracticeInfo').onclick=()=>openModal('MOTORE PRATICHE PC',`<p><b>Perché esiste:</b> la compilazione completa dell’incarico e i documenti locali richiedono il motore installato sul PC.</p><p><b>Fai così:</b> apri il cliente nel CRM, vai su PRATICHE e premi COMPILA INCARICO. Il modulo controlla i dati, i documenti e prepara la stampa in due copie.</p><p>Il telefono continua a mostrare lo stato della pratica nello stesso CRM.</p>`);
  }

  function markLocalEngine(){
    const badge=document.getElementById('f1UnifiedBadge');
    if(badge)badge.textContent='STESSO F1 OS · STESSO CRM · MOTORE PC COLLEGATO';
  }

  function boot(){addLocalPracticeTools();markLocalEngine()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>setTimeout(addLocalPracticeTools,0)));
})();