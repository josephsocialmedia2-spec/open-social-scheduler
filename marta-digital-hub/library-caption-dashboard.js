import {buildLocalCaptionPack} from './caption-local.mjs?v=16';

const MR_PLATFORMS=['instagram','facebook','tiktok','youtube','linkedin'];
let mrPreviewObjectUrl=null,mrLocalPreviewUrls=[],mrContentRows=[],mrBatchBusy=false;
const mrBaseOpen=globalThis.openContent;

function mrFmtDuration(value){
  const n=Number(value);if(!Number.isFinite(n)||n<=0)return '—';
  const s=Math.round(n),m=Math.floor(s/60),r=s%60;
  return m?m+'m '+String(r).padStart(2,'0')+'s':r+'s';
}
function mrBytes(n){n=Number(n||0);return n>=1048576?(n/1048576).toFixed(1)+' MB':(n/1024).toFixed(1)+' KB'}
function mrStorageAuthenticatedUrl(bucket,path){
  const ep=String(path||'').split('/').map(encodeURIComponent).join('/');
  return `${SUPA}/storage/v1/object/authenticated/${encodeURIComponent(bucket)}/${ep}`;
}
async function mrDownloadBlob(path,retried=false){
  let r=await fetch(mrStorageAuthenticatedUrl('marta-content-originals',path),{headers:hdr(false)});
  if(r.status===401&&!retried){await refresh();return mrDownloadBlob(path,true)}
  if(!r.ok)throw Error(`Video non leggibile dal cloud (${r.status})`);
  return r.blob();
}
function mrVideoDuration(blob){
  return new Promise(resolve=>{
    const url=URL.createObjectURL(blob),v=document.createElement('video');
    let done=false,t=setTimeout(()=>finish(null),10000);
    function finish(value){if(done)return;done=true;clearTimeout(t);v.removeAttribute('src');try{v.load()}catch{}URL.revokeObjectURL(url);resolve(value)}
    v.preload='metadata';v.onloadedmetadata=()=>finish(Number.isFinite(v.duration)&&v.duration>0?v.duration:null);v.onerror=()=>finish(null);v.src=url;
  });
}
async function mrValidateVideo(file){
  if(!file)throw Error('File mancante.');
  if(!MARTA_ALLOWED_VIDEO_TYPES.has(file.type))throw Error('Formato non consentito. Usa MP4, MOV o WEBM.');
  if(file.size<=0)throw Error('Il file è vuoto.');
  if(file.size>MARTA_MAX_VIDEO_BYTES)throw Error('Il video supera 50 MB.');
  if(!await martaVideoSignatureOk(file))throw Error('Il contenuto del file non corrisponde al formato video dichiarato.');
}
function mrClearLocalPreviews(){mrLocalPreviewUrls.forEach(URL.revokeObjectURL);mrLocalPreviewUrls=[]}
function mrRenderSelectedFiles(){
  const input=document.querySelector('#upFile'),host=document.querySelector('#uploadPreview');if(!input||!host)return;
  mrClearLocalPreviews();
  const files=[...input.files];
  host.innerHTML=files.length?files.map(f=>{
    const url=URL.createObjectURL(f);mrLocalPreviewUrls.push(url);
    return `<div class="item"><video controls muted preload="metadata" src="${url}" style="width:120px;max-height:90px;border-radius:9px;background:#111"></video><div style="flex:1"><b>${esc(f.name)}</b><p>${mrBytes(f.size)} · ${esc(f.type||'tipo sconosciuto')}</p></div></div>`;
  }).join(''):'';
}
function mrInstallMultiUpload(){
  const input=document.querySelector('#upFile'),form=document.querySelector('#uploadForm');if(!input||!form)return;
  input.multiple=true;
  const label=input.closest('.drop');if(label)label.childNodes[0].textContent='Video MP4 / MOV / WEBM, uno o più file, max 50 MB ciascuno ';
  if(!document.querySelector('#uploadPreview')){
    const preview=document.createElement('div');preview.id='uploadPreview';preview.className='stack';label?.insertAdjacentElement('afterend',preview);
    const queue=document.createElement('div');queue.id='uploadQueue';queue.className='stack';preview.insertAdjacentElement('afterend',queue);
  }
  input.addEventListener('change',mrRenderSelectedFiles);
  form.onsubmit=async e=>{
    e.preventDefault();if(mrBatchBusy)return;
    const files=[...input.files],baseTitle=document.querySelector('#upTitle').value.trim(),category=document.querySelector('#upCat').value.trim(),notes=document.querySelector('#upNotes').value.trim();
    const queue=document.querySelector('#uploadQueue'),button=document.querySelector('#uploadSubmit');
    if(!files.length){toast('Scegli almeno un video.',true);return}
    if(!baseTitle||baseTitle.length>200){toast('Inserisci un titolo valido.',true);return}
    mrBatchBusy=true;if(button)button.disabled=true;queue.innerHTML='';
    let ok=0,failed=0;
    for(let i=0;i<files.length;i++){
      const file=files[i],row=document.createElement('div');row.className='item';
      row.innerHTML=`<div style="flex:1"><b>${esc(file.name)}</b><p class="qtext">Controllo file…</p><div class="progress"><i></i></div></div><span class="status">IN CODA</span>`;
      queue.appendChild(row);const text=row.querySelector('.qtext'),bar=row.querySelector('.progress i'),badge=row.querySelector('.status');
      let c=null,sp=null,storageClean=true;
      try{
        await mrValidateVideo(file);const duration=await mrVideoDuration(file);
        const title=(files.length>1?`${baseTitle} ${i+1}`:baseTitle).slice(0,200);
        c=await martaReserveUpload({title,category,notes,filename:martaDisplayFilename(file.name),mime:file.type,size:file.size});
        sp=`${S.user.id}/${c.id}/${Date.now()}-${martaSafeStorageFilename(file.name,file.type)}`;
        await db(`contents?id=eq.${c.id}`,{method:'PATCH',body:{storage_path:sp,...(duration?{duration_seconds:Number(duration.toFixed(3))}:{})}});
        text.textContent='Upload nel cloud…';badge.textContent='UPLOAD';
        await martaUploadOriginal(file,sp,p=>{bar.style.width=p+'%';text.textContent=`Upload nel cloud… ${p}%`});
        await db(`contents?id=eq.${c.id}`,{method:'PATCH',body:{status:'CARICATO'}});
        text.textContent=`✓ Salvato${duration?' · '+mrFmtDuration(duration):''}`;badge.textContent='CARICATO';badge.className='status PRONTO';ok++;
      }catch(err){
        failed++;badge.textContent='ERRORE';badge.className='status ERRORE';text.textContent=err.message;text.className='qtext danger';
        if(c?.id&&sp){try{await martaDeleteStorageObject('marta-content-originals',sp)}catch{storageClean=false}}
        if(c?.id&&storageClean)await martaTryDeleteReservation(c.id);
      }
    }
    mrBatchBusy=false;if(button)button.disabled=false;
    if(ok){form.reset();mrClearLocalPreviews();document.querySelector('#uploadPreview').innerHTML='';toast(`${ok} video caricati${failed?' · '+failed+' non caricati':''}`,!!failed)}
    else toast('Nessun video caricato.',true);
    await Promise.allSettled([mrContents(),mrDash()]);
  };
}

function mrInstallContentFilters(){
  const list=document.querySelector('#contentsList');if(!list||document.querySelector('#mrContentFilters'))return;
  const box=document.createElement('div');box.id='mrContentFilters';box.className='row';box.style.marginBottom='12px';
  box.innerHTML=`<input id="mrSearch" placeholder="Cerca titolo, categoria, note o file"><select id="mrStatus"><option value="">Tutti gli stati</option>${['CARICATO','IN_ELABORAZIONE','PRONTO','DA_APPROVARE','APPROVATO','PROGRAMMATO','PUBBLICATO','ERRORE'].map(x=>`<option>${x}</option>`).join('')}</select><select id="mrSort"><option value="new">Più recenti</option><option value="old">Meno recenti</option><option value="title">Titolo A–Z</option></select>`;
  list.insertAdjacentElement('beforebegin',box);
  ['mrSearch','mrStatus','mrSort'].forEach(id=>document.getElementById(id).addEventListener(id==='mrSearch'?'input':'change',mrRenderContents));
}
function mrRenderContents(){
  const host=document.querySelector('#contentsList');if(!host)return;
  const q=(document.querySelector('#mrSearch')?.value||'').trim().toLowerCase(),st=document.querySelector('#mrStatus')?.value||'',sort=document.querySelector('#mrSort')?.value||'new';
  let rows=mrContentRows.filter(x=>{
    const hay=[x.title,x.category,x.notes,x.original_filename].filter(Boolean).join(' ').toLowerCase();
    return (!q||hay.includes(q))&&(!st||x.status===st);
  });
  rows.sort((a,b)=>sort==='title'?String(a.title).localeCompare(String(b.title),'it'):sort==='old'?new Date(a.created_at)-new Date(b.created_at):new Date(b.created_at)-new Date(a.created_at));
  host.innerHTML=rows.length?rows.map(x=>`<div class="item"><div><b>${esc(x.title)}</b><p>${esc(x.category||'Senza categoria')} · ${mrFmtDuration(x.duration_seconds)} · ${mrBytes(x.file_size)} · ${fmt(x.created_at)}</p></div><div class="actions"><span class="status ${x.status}">${x.status}</span><button class="ghost smallbtn open" data-id="${x.id}">Apri</button></div></div>`).join(''):'<p class="hint">Nessun contenuto corrisponde ai filtri.</p>';
}
async function mrContents(){
  mrInstallContentFilters();mrContentRows=await db('contents?select=*&order=created_at.desc&limit=500');mrRenderContents();
}
globalThis.contents=mrContents;
const refreshButton=document.querySelector('#refreshContents');if(refreshButton)refreshButton.onclick=mrContents;

async function mrCopyText(value){try{await navigator.clipboard.writeText(value);toast('Link copiato')}catch{toast('Non riesco a copiare automaticamente.',true)}}
function mrRenderTracking(rows){
  const host=document.querySelector('#mrTracking');if(!host)return;
  host.innerHTML=rows.length?rows.map(x=>`<div class="item"><div><b>${esc(x.platform)}</b><p style="word-break:break-all">${esc(x.tracked_url||'')}</p></div><button class="ghost smallbtn mrCopyLink" data-url="${esc(x.tracked_url||'')}">Copia</button></div>`).join(''):'<p class="hint">Nessun link UTM generato.</p>';
  host.querySelectorAll('.mrCopyLink').forEach(b=>b.onclick=()=>mrCopyText(b.dataset.url));
}
async function mrGenerateTracking(contentId){
  const p=(await db('profiles?select=site_url,default_utm_campaign'))[0]||{};
  if(!p.site_url)throw Error('Imposta prima il sito pubblico nelle Impostazioni.');
  let base;try{base=new URL(p.site_url)}catch{throw Error('URL del sito non valido.')}
  if(!['http:','https:'].includes(base.protocol))throw Error('Il sito deve usare http o https.');
  const rows=MR_PLATFORMS.map(platform=>{
    const u=new URL(base.href);u.searchParams.set('utm_source',platform);u.searchParams.set('utm_medium','social');u.searchParams.set('utm_campaign',p.default_utm_campaign||'marta_ruffino_social');u.searchParams.set('utm_content',contentId);
    return {owner_id:S.user.id,content_id:contentId,platform,destination_url:base.href,utm_source:platform,utm_medium:'social',utm_campaign:p.default_utm_campaign||'marta_ruffino_social',utm_content:contentId,tracked_url:u.href};
  });
  await db('marta_tracking_links?on_conflict=content_id,platform',{method:'POST',body:rows,prefer:'resolution=merge-duplicates,return=representation'});
  return db(`marta_tracking_links?content_id=eq.${contentId}&select=*&order=platform`);
}
function mrInstallPostPreview(){
  const vbox=document.querySelector('#variantBox');if(!vbox||document.querySelector('#mrPostPreview'))return;
  const box=document.createElement('div');box.id='mrPostPreview';box.className='panel';box.style.marginTop='12px';
  vbox.insertAdjacentElement('afterend',box);mrUpdatePostPreview();
}
function mrUpdatePostPreview(){
  const host=document.querySelector('#mrPostPreview');if(!host)return;
  const p=document.querySelector('#variantTabs button.active')?.dataset.p||'social',hook=document.querySelector('#vHook')?.value||'',text=document.querySelector('#vText')?.value||'',cta=document.querySelector('#vCta')?.value||'',tags=document.querySelector('#vTags')?.value||'';
  host.innerHTML=`<h3 style="margin-top:0">Anteprima ${esc(p)}</h3><div style="white-space:pre-wrap;line-height:1.55">${esc([hook,text,cta,tags].filter(Boolean).join('\n\n'))||'<span class="hint">Nessun testo ancora.</span>'}</div>`;
}
document.addEventListener('input',e=>{if(['vHook','vText','vCta','vTags'].includes(e.target?.id))mrUpdatePostPreview()});
document.addEventListener('click',e=>{if(e.target?.closest?.('#variantTabs'))setTimeout(mrUpdatePostPreview,0)});

async function mrGenerateCaptions(id,c){
  if(['APPROVATO','PROGRAMMATO','PUBBLICATO'].includes(c.status))throw Error('Riapri prima il contenuto per modificare le caption.');
  if(!c.storage_path)throw Error('Il video non è presente nello storage.');
  const text=document.querySelector('#transcript')?.value.trim()||'';if(!text)throw Error('Prima inserisci o salva la trascrizione.');
  const previous=(await db(`transcripts?content_id=eq.${id}&select=original_text,source_model`))[0];
  await db('transcripts?on_conflict=content_id',{method:'POST',body:{owner_id:S.user.id,content_id:id,original_text:previous?.original_text||text,corrected_text:text,language:'it',source_model:previous?.source_model||'manual'},prefer:'resolution=merge-duplicates,return=representation'});
  const pack=buildLocalCaptionPack(text,{title:c.title,category:c.category});
  const rows=[
    ['instagram',pack.instagram],['facebook',pack.facebook],['tiktok',pack.tiktok],['youtube',pack.youtube],['linkedin',pack.linkedin]
  ].map(([platform,variants])=>({owner_id:S.user.id,content_id:id,platform,hook:pack.hook,cta:pack.cta,hashtags:platform==='youtube'?pack.youtube.tags.map(x=>'#'+x):pack.hashtags,variants,status:'DA_APPROVARE',approved_at:null}));
  await db('social_variants?on_conflict=content_id,platform',{method:'POST',body:rows,prefer:'resolution=merge-duplicates,return=representation'});
  await db(`contents?id=eq.${id}`,{method:'PATCH',body:{status:'DA_APPROVARE'}});
}
async function mrOpenContent(id){
  await mrBaseOpen(id);
  const [rows,links]=await Promise.all([db(`contents?id=eq.${id}&select=*`),db(`marta_tracking_links?content_id=eq.${id}&select=*&order=platform`)]);
  const c=rows[0];if(!c)return;
  const body=document.querySelector('#dlgBody');
  const meta=document.createElement('div');meta.id='mrContentMeta';meta.className='panel';
  meta.innerHTML=`<div class="row"><label>Titolo<input id="mrTitle" maxlength="200" value="${esc(c.title)}"></label><button id="mrSaveTitle" type="button">Salva titolo</button></div>
  <p class="hint">File: ${esc(c.original_filename||'—')} · ${mrBytes(c.file_size)} · durata ${mrFmtDuration(c.duration_seconds)}<br>Percorso privato: <code>${esc(c.storage_path||'—')}</code></p>
  <div class="actions"><button id="mrPreviewBtn" type="button" class="ghost">Anteprima video</button><button id="mrDuplicateBtn" type="button" class="ghost">Duplica contenuto</button><button id="mrUtmBtn" type="button" class="ghost">Genera link UTM</button></div>
  <div id="mrVideoPreview" style="margin-top:12px"></div><h3>Link tracciati</h3><div id="mrTracking" class="stack"></div>`;
  body.prepend(meta);mrRenderTracking(links);
  document.querySelector('#mrSaveTitle').onclick=async()=>{
    const title=document.querySelector('#mrTitle').value.trim();if(!title||title.length>200){toast('Titolo non valido.',true);return}
    await db(`contents?id=eq.${id}`,{method:'PATCH',body:{title}});document.querySelector('#dlgTitle').textContent=title;toast('Titolo aggiornato');await Promise.allSettled([mrContents(),mrDash()]);
  };
  document.querySelector('#mrPreviewBtn').onclick=async e=>{
    if(!c.storage_path){toast('Video non presente.',true);return}
    e.currentTarget.disabled=true;
    try{
      const blob=await mrDownloadBlob(c.storage_path);if(mrPreviewObjectUrl)URL.revokeObjectURL(mrPreviewObjectUrl);mrPreviewObjectUrl=URL.createObjectURL(blob);
      document.querySelector('#mrVideoPreview').innerHTML=`<video controls playsinline preload="metadata" src="${mrPreviewObjectUrl}" style="width:100%;max-height:430px;border-radius:12px;background:#111"></video>`;
      if(!c.duration_seconds){const d=await mrVideoDuration(blob);if(d)await db(`contents?id=eq.${id}`,{method:'PATCH',body:{duration_seconds:Number(d.toFixed(3))}})}
    }catch(err){toast(err.message,true)}finally{e.currentTarget.disabled=false}
  };
  document.querySelector('#mrDuplicateBtn').onclick=async e=>{
    e.currentTarget.disabled=true;let copy=null,sp=null,clean=true;
    try{
      if(!c.storage_path)throw Error('Video originale non disponibile.');
      const blob=await mrDownloadBlob(c.storage_path),mime=c.mime_type||blob.type||'video/mp4',filename=martaDisplayFilename(c.original_filename||martaSafeStorageFilename(c.title,mime));
      copy=await martaReserveUpload({title:(c.title+' · copia').slice(0,200),category:c.category||'',notes:c.notes||'',filename,mime,size:blob.size});
      sp=`${S.user.id}/${copy.id}/${Date.now()}-copy-${martaSafeStorageFilename(filename,mime)}`;
      await db(`contents?id=eq.${copy.id}`,{method:'PATCH',body:{storage_path:sp,duplicate_of:c.id,...(c.duration_seconds?{duration_seconds:c.duration_seconds}:{})}});
      await martaUploadOriginal(new Blob([blob],{type:mime}),sp);
      await db(`contents?id=eq.${copy.id}`,{method:'PATCH',body:{status:'CARICATO'}});
      toast('Copia creata');await Promise.allSettled([mrContents(),mrDash()]);await mrOpenContent(copy.id);
    }catch(err){
      if(copy?.id&&sp){try{await martaDeleteStorageObject('marta-content-originals',sp)}catch{clean=false}}
      if(copy?.id&&clean)await martaTryDeleteReservation(copy.id);
      toast(err.message,true);
    }finally{e.currentTarget.disabled=false}
  };
  document.querySelector('#mrUtmBtn').onclick=async e=>{e.currentTarget.disabled=true;try{const r=await mrGenerateTracking(id);mrRenderTracking(r);toast('Link UTM aggiornati')}catch(err){toast(err.message,true)}finally{e.currentTarget.disabled=false}};
  const ai=document.querySelector('#aiInfo');if(ai){ai.textContent='Crea 5 caption dal testo (€0)';ai.onclick=async()=>{ai.disabled=true;try{await mrGenerateCaptions(id,c);toast('5 caption create: restano da approvare');await mrOpenContent(id);await Promise.allSettled([mrContents(),mrDash()])}catch(err){toast(err.message,true)}finally{ai.disabled=false}}}
  mrInstallPostPreview();
}
globalThis.openContent=mrOpenContent;
document.addEventListener('click',e=>{
  const b=e.target?.closest?.('.open');if(!b?.dataset?.id)return;
  e.preventDefault();e.stopImmediatePropagation();mrOpenContent(b.dataset.id).catch(err=>toast(err.message,true));
},true);

async function mrDash(){
  const [c,l,s,i,j]=await Promise.all([
    db('contents?select=id,title,category,status,created_at&order=created_at.desc&limit=500'),
    db('leads?select=id,status&limit=500'),
    db('schedules?select=id,content_id,platform,status,scheduled_for&order=scheduled_for.asc&limit=500'),
    db('integrations?select=platform,enabled,status'),
    db('marta_processing_jobs?select=status&limit=500')
  ]);
  const cards=[
    ['Contenuti',c.length],['In elaborazione',c.filter(x=>['CARICATO','IN_ELABORAZIONE','PRONTO'].includes(x.status)).length],
    ['Da approvare',c.filter(x=>x.status==='DA_APPROVARE').length],['Approvati',c.filter(x=>x.status==='APPROVATO').length],
    ['Programm.',s.filter(x=>x.status==='PROGRAMMATO').length],['Pubblicati',s.filter(x=>x.status==='PUBBLICATO').length],
    ['Errori',c.filter(x=>x.status==='ERRORE').length+j.filter(x=>x.status==='ERRORE').length+s.filter(x=>x.status==='ERRORE').length],
    ['Social collegati',i.filter(x=>x.enabled).length+'/5'],['Lead nuovi',l.filter(x=>x.status==='NUOVO').length],['Clienti',l.filter(x=>x.status==='CLIENTE').length]
  ];
  document.querySelector('#kpis').innerHTML=cards.map(x=>`<div class="card"><small>${esc(x[0])}</small><b>${x[1]}</b></div>`).join('');
  const a=c.filter(x=>x.status==='DA_APPROVARE').slice(0,6);document.querySelector('#approvals').innerHTML=a.length?a.map(x=>itemContent(x)).join(''):'<p class="hint">Niente in attesa.</p>';
  const u=s.filter(x=>x.status==='PROGRAMMATO'&&new Date(x.scheduled_for)>new Date()).slice(0,6);document.querySelector('#upcoming').innerHTML=u.length?u.map(x=>`<div class="item"><div><b>${esc(x.platform)}</b><p>${fmt(x.scheduled_for)}</p></div><span class="status ${x.status}">${x.status}</span></div>`).join(''):'<p class="hint">Nessuna pubblicazione futura.</p>';
  await quota();
}
globalThis.dash=mrDash;

async function mrAnalytics(){
  const [metrics,leads,costs,investments]=await Promise.all([
    db('performance_metrics?select=*'),db('leads?select=status,acquired,value,margin_value,appointment_at'),db('service_costs?select=cost'),db('marta_investment_entries?select=amount')
  ]);
  const sum=(arr,k)=>arr.reduce((a,x)=>a+Number(x[k]||0),0),clients=leads.filter(x=>x.status==='CLIENTE'||x.acquired),revenue=sum(clients,'value'),marginRows=clients.filter(x=>x.margin_value!==null&&x.margin_value!==undefined),margin=sum(marginRows,'margin_value'),investment=sum(investments,'amount'),serviceCosts=sum(costs,'cost'),avg=clients.length?revenue/clients.length:null,avgMargin=marginRows.length?margin/marginRows.length:null,cac=clients.length?investment/clients.length:null,breakEven=avgMargin&&avgMargin>0?Math.ceil(investment/avgMargin):null;
  const cards=[
    ['Visualizzazioni',metrics.length?sum(metrics,'views'):'—'],['Click social',metrics.length?sum(metrics,'clicks'):'—'],['Visite sito UTM',metrics.length?sum(metrics,'site_visits'):'—'],
    ['Contatti',leads.length],['Appuntamenti',leads.filter(x=>x.appointment_at).length],['Clienti',clients.length],
    ['Conversione',leads.length?((clients.length/leads.length)*100).toFixed(1)+'%':'—'],['Valore medio €',avg===null?'—':avg.toFixed(2)],['CAC €',cac===null?'—':cac.toFixed(2)],
    ['Ricavi €',revenue.toFixed(2)],['Margine €',marginRows.length?margin.toFixed(2):'—'],['Investimento €',investment.toFixed(2)],
    ['Costi servizi €',serviceCosts.toFixed(2)],['Break-even',breakEven===null?'—':breakEven+' clienti']
  ];
  document.querySelector('#analyticsCards').innerHTML=cards.map(x=>`<div class="card"><small>${esc(x[0])}</small><b>${x[1]}</b></div>`).join('');
}
globalThis.analytics=mrAnalytics;

async function mrInvestments(){
  const host=document.querySelector('#mrInvestmentList');if(!host)return;
  const rows=await db('marta_investment_entries?select=*&order=incurred_on.desc,created_at.desc&limit=100');
  host.innerHTML=rows.length?rows.map(x=>`<div class="item"><div><b>${esc(x.service)}</b><p>${esc(x.incurred_on)} · ${esc(x.note||'')}</p></div><b>€ ${Number(x.amount||0).toFixed(2)}</b></div>`).join(''):'<p class="hint">Nessun investimento registrato.</p>';
}
function mrInstallInvestment(){
  const costs=document.querySelector('#costs');if(!costs||document.querySelector('#mrInvestmentPanel'))return;
  const panel=document.createElement('article');panel.id='mrInvestmentPanel';panel.className='panel';panel.innerHTML=`<h2>Investimento marketing</h2><form id="mrInvestmentForm"><div class="row"><label>Voce<input id="mrInvService" maxlength="200" required></label><label>Importo €<input id="mrInvAmount" type="number" min="0" step=".01" required></label><label>Data<input id="mrInvDate" type="date" required></label></div><label>Nota<input id="mrInvNote" maxlength="1000"></label><button>Registra investimento</button></form><div id="mrInvestmentList" class="stack" style="margin-top:14px"></div>`;costs.appendChild(panel);
  document.querySelector('#mrInvDate').value=new Date().toISOString().slice(0,10);
  document.querySelector('#mrInvestmentForm').onsubmit=async e=>{e.preventDefault();try{await db('marta_investment_entries',{method:'POST',body:{owner_id:S.user.id,service:document.querySelector('#mrInvService').value.trim(),amount:Number(document.querySelector('#mrInvAmount').value),incurred_on:document.querySelector('#mrInvDate').value,note:document.querySelector('#mrInvNote').value.trim()||null}});e.target.reset();document.querySelector('#mrInvDate').value=new Date().toISOString().slice(0,10);toast('Investimento registrato');await Promise.all([mrInvestments(),mrAnalytics()])}catch(err){toast(err.message,true)}};
}
async function mrLogs(){
  const host=document.querySelector('#mrLogs');if(!host)return;
  const [audit,publish,jobs]=await Promise.all([db('audit_logs?select=*&order=created_at.desc&limit=80'),db('marta_publish_logs?select=*&order=created_at.desc&limit=80'),db('marta_processing_jobs?select=*&order=created_at.desc&limit=80')]);
  const rows=[
    ...audit.map(x=>({at:x.created_at,label:`${x.module||'audit'} · ${x.action||''}`,status:x.outcome||'OK',error:x.error})),
    ...publish.map(x=>({at:x.created_at,label:`social · ${x.platform||''}`,status:x.outcome||x.status||'INFO',error:x.error||x.last_error})),
    ...jobs.map(x=>({at:x.created_at,label:`job · ${x.job_type||x.type||'processing'}`,status:x.status||'INFO',error:x.error||x.last_error}))
  ].sort((a,b)=>new Date(b.at)-new Date(a.at)).slice(0,150);
  host.innerHTML=rows.length?rows.map(x=>`<div class="item"><div><b>${esc(x.label)}</b><p>${fmt(x.at)}${x.error?' · '+esc(x.error):''}</p></div><span class="status ${x.status==='ERRORE'?'ERRORE':''}">${esc(x.status)}</span></div>`).join(''):'<p class="hint">Nessun log operativo.</p>';
}
function mrInstallLogs(){
  if(document.querySelector('#logs'))return;
  const nav=document.querySelector('#nav'),settings=nav?.querySelector('[data-v="settings"]'),btn=document.createElement('button');btn.dataset.v='logs';btn.textContent='Log';
  if(settings)nav.insertBefore(btn,settings);else nav?.appendChild(btn);btn.onclick=()=>{view('logs');mrLogs()};
  const settingsView=document.querySelector('#settings'),section=document.createElement('section');section.id='logs';section.className='view';section.innerHTML='<article class="panel"><div class="row"><h2>Log operativi</h2><button id="mrRefreshLogs" class="ghost smallbtn">Aggiorna</button></div><div id="mrLogs" class="stack"></div></article>';
  settingsView?.insertAdjacentElement('beforebegin',section);document.querySelector('#mrRefreshLogs').onclick=mrLogs;
}

mrInstallMultiUpload();mrInstallContentFilters();mrInstallInvestment();mrInstallLogs();
Promise.allSettled([mrContents(),mrDash(),mrAnalytics(),mrInvestments(),mrLogs()]);
