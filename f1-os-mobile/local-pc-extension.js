(()=>{
  const qs=new URLSearchParams(location.search);
  const port=qs.get('bridge');
  if(!port||!/^[0-9]{2,5}$/.test(port))return;
  const base='http://127.0.0.1:'+port;
  document.body.dataset.device='pc';
  let linkedRefresh='';

  function currentSession(){
    try{return JSON.parse(localStorage.getItem('f1_session')||'null')}catch(e){return null}
  }
  function practiceHref(contactId=''){
    let u=base+'/incarico';
    if(contactId)u+='?contact_id='+encodeURIComponent(contactId);
    return u;
  }
  async function linkCloudSession(){
    const s=currentSession();
    if(!s?.refresh_token||!s?.user?.id||s.refresh_token===linkedRefresh)return;
    try{
      const r=await fetch(base+'/api/cloud-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:s.refresh_token,user_id:s.user.id,email:s.user.email||'f1immobiliaresusa@outlook.it'})});
      if(!r.ok)throw Error('HTTP '+r.status);
      linkedRefresh=s.refresh_token;
      const badge=document.getElementById('f1UnifiedBadge');
      if(badge)badge.textContent='STESSO F1 OS · STESSO CRM · MOTORE PC + CLOUD COLLEGATI';
    }catch(e){
      const badge=document.getElementById('f1UnifiedBadge');
      if(badge)badge.textContent='F1 OS UNIFICATO · MOTORE PC IN ATTESA DEL COLLEGAMENTO CRM';
    }
  }

  function addLocalPracticeTools(){
    const card=document.querySelector('[data-screen="pratiche"] article.card');
    if(!card||document.getElementById('f1LocalPracticeTools'))return;
    const box=document.createElement('div');
    box.id='f1LocalPracticeTools';
    box.className='card';
    box.style.marginTop='12px';
    box.innerHTML=`<div class="section"><h2>MOTORE PRATICHE PC</h2><button class="infoSmall" id="localPracticeInfo">ⓘ</button></div><p class="muted">Questi comandi aprono i moduli installati sul PC. La sessione CRM viene collegata automaticamente al motore locale.</p><div class="row"><a class="btn primary linkbtn" href="${practiceHref()}">COMPILA INCARICO DI VENDITA</a><a class="btn linkbtn" href="${base}/marketing">GUIDA MARKETING CLIENTE</a></div><div class="state">MOTORE LOCALE F1 · porta ${port}</div>`;
    card.appendChild(box);
    document.getElementById('localPracticeInfo').onclick=()=>openModal('MOTORE PRATICHE PC',`<p><b>Perché esiste:</b> la compilazione completa dell’incarico e i documenti locali richiedono il motore installato sul PC.</p><p><b>Fai così:</b> apri il cliente nel CRM e premi COMPILA INCARICO. Il modulo precompila ciò che conosce, controlla i documenti e prepara la stampa in due copie.</p><p>La pratica viene poi sincronizzata nello stesso CRM centrale che vedi sul telefono.</p>`);
  }

  function addContactPracticeButton(cid){
    const dlg=document.getElementById('modal');
    if(!cid||!dlg?.open||document.getElementById('f1ContactPractice'))return;
    const row=document.querySelector('#modalBody .row');
    if(!row)return;
    const a=document.createElement('a');a.id='f1ContactPractice';a.className='btn primary linkbtn';a.href=practiceHref(cid);a.textContent='▤ COMPILA INCARICO';row.appendChild(a);
  }

  function markLocalEngine(){
    const badge=document.getElementById('f1UnifiedBadge');
    if(badge)badge.textContent='STESSO F1 OS · STESSO CRM · MOTORE PC COLLEGATO';
  }

  function boot(){addLocalPracticeTools();markLocalEngine();linkCloudSession()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
  document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>setTimeout(()=>{addLocalPracticeTools();linkCloudSession()},0)));
  document.addEventListener('click',e=>{const item=e.target.closest('[data-contact]');if(item)setTimeout(()=>addContactPracticeButton(item.dataset.contact),20)});
  setInterval(linkCloudSession,4000);
})();