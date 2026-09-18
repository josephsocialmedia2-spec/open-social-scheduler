$('#loginForm').onsubmit=async e=>{e.preventDefault();$('#loginMsg').textContent='Accesso…';try{await login();$('#loginMsg').textContent=''}catch(x){$('#loginMsg').textContent=x.message}};
$('#signup').onclick=()=>location.replace('./accesso.html?v=15');
$('#claimForm').onsubmit=e=>{e.preventDefault();$('#claimMsg').textContent='Questo account non è autorizzato.'};
$('#claimLogout').onclick=$('#logout').onclick=logout;$('#dlgClose').onclick=()=>$('#dlg').close();$('#refreshContents').onclick=contents;$('#calStatus').onchange=calendar;
$$('#nav button').forEach(b=>b.onclick=()=>view(b.dataset.v));

$('#uploadForm').onsubmit=async e=>{
 e.preventDefault();
 if(martaUploadBusy)return;
 const f=$('#upFile').files[0],title=$('#upTitle').value.trim(),button=$('#uploadSubmit');
 if(!f){toast('Scegli un video da caricare.',true);return}
 if(!title||title.length>200){toast('Inserisci un titolo valido (massimo 200 caratteri).',true);return}
 if(!MARTA_ALLOWED_VIDEO_TYPES.has(f.type)){toast('Formato non consentito. Usa MP4, MOV o WEBM.',true);return}
 if(f.size<=0){toast('Il file è vuoto.',true);return}
 if(f.size>MARTA_MAX_VIDEO_BYTES){toast('Il video supera il limite di 50 MB.',true);return}
 try{if(!await martaVideoSignatureOk(f)){toast('Il contenuto del file non corrisponde a un video MP4, MOV o WEBM valido.',true);return}}catch{toast('Non riesco a leggere il file selezionato.',true);return}

 martaUploadBusy=true;button.disabled=true;
 let c=null,sp=null;
 try{
   const displayName=martaDisplayFilename(f.name);
   c=await martaReserveUpload({title,category:$('#upCat').value.trim(),notes:$('#upNotes').value.trim(),filename:displayName,mime:f.type,size:f.size});
   const safe=martaSafeStorageFilename(f.name,f.type);
   sp=`${S.user.id}/${c.id}/${Date.now()}-${safe}`;

   await db(`contents?id=eq.${c.id}`,{method:'PATCH',body:{storage_path:sp}});

   $('#upState').innerHTML='<p>Upload in corso…</p><div class=progress><i id=bar></i></div>';
   await martaUploadOriginal(f,sp,p=>{const bar=$('#bar');if(bar)bar.style.width=p+'%'});

   let finalized=false,lastFinalizeError=null;
   for(let attempt=0;attempt<2&&!finalized;attempt++){
     try{await db(`contents?id=eq.${c.id}`,{method:'PATCH',body:{status:'CARICATO'}});finalized=true}
     catch(err){lastFinalizeError=err;if(!attempt)await new Promise(r=>setTimeout(r,700))}
   }
   if(!finalized){
     $('#upState').innerHTML='<p class="warn"><b>Video salvato.</b> La connessione non ha confermato lo stato finale. Il record resta visibile come IN_ELABORAZIONE per il recupero.</p>';
     toast('Video nel cloud; stato da verificare nell’Archivio.',true);
     await all().catch(()=>{});
     console.warn('upload finalize',lastFinalizeError);
     return;
   }

   $('#upState').innerHTML='<p>✓ Video salvato nel cloud privato.</p>';
   e.target.reset();toast('Video caricato');await all();
 }catch(err){
   let storageClean=true;
   if(c?.id&&sp){try{await martaDeleteStorageObject('marta-content-originals',sp)}catch{storageClean=false}}
   if(c?.id&&storageClean)await martaTryDeleteReservation(c.id);
   if(c?.id&&!storageClean){
     $('#upState').innerHTML='<p class="warn"><b>Upload interrotto.</b> Ho mantenuto il record di recupero nell’Archivio per non perdere il riferimento al file.</p>';
   }else $('#upState').innerHTML='<p class="danger">Upload non completato. La prenotazione è stata ripulita.</p>';
   toast(err?.message||'Upload non riuscito',true);
 }finally{
   martaUploadBusy=false;button.disabled=false;
 }
};

$('#autoForm').onsubmit=async e=>{e.preventDefault();await db(`autopilot_settings?owner_id=eq.${S.user.id}`,{method:'PATCH',body:{enabled:$('#autoEnabled').checked,posts_per_day:Number($('#autoPosts').value),slots:[$('#autoSlot1').value,$('#autoSlot2').value].filter(Boolean),platforms:['instagram','facebook'],weekdays:[1,2,3,4,5],timezone:'Europe/Rome',horizon_days:7}});toast('Autopilot salvato');await autopilot()};
$('#autoRun').onclick=async()=>{try{let r=await db('rpc/run_autopilot',{method:'POST',body:{}});toast(r?.length?`${r.length} contenuti programmati`:'Nessun contenuto approvato da programmare');await all()}catch(e){toast(e.message,true)}};
$('#leadForm').onsubmit=async e=>{e.preventDefault();await db('leads',{method:'POST',body:{owner_id:S.user.id,name:$('#leadName').value.trim(),contact:$('#leadContact').value.trim(),source:$('#leadSource').value.trim(),platform:$('#leadPlatform').value||null,request:$('#leadRequest').value.trim(),status:'NUOVO'}});e.target.reset();toast('Lead registrato');await all()};
$('#costForm').onsubmit=async e=>{e.preventDefault();await db('service_costs',{method:'POST',body:{owner_id:S.user.id,service:$('#costService').value.trim(),provider:$('#costProvider').value.trim(),cost:Number($('#costValue').value||0),frequency:'mensile',account_owner:'Marta Ruffino'}});e.target.reset();toast('Costo salvato');await costs()};
$('#settingsForm').onsubmit=async e=>{e.preventDefault();await Promise.all([db(`editorial_profiles?owner_id=eq.${S.user.id}`,{method:'PATCH',body:{name:$('#setName').value,voice:$('#setVoice').value,forbidden_claims:$('#setForbidden').value}}),db(`profiles?id=eq.${S.user.id}`,{method:'PATCH',body:{site_url:$('#setSite').value||null}})]);toast('Impostazioni salvate')};
window.addEventListener('storage',e=>{if(e.key==='mr_session'&&!e.newValue)location.replace('./accesso.html?v=15')});
(async()=>{if(!validSession()){clearSession();location.replace('./accesso.html?v=15');return}try{await enter()}catch(e){console.error(e);clearSession();location.replace('./accesso.html?v=15&reason=session')}})();
import('./content-hardening.js?v=13').catch(e=>console.error('content hardening',e));

import('./calendar-leads-hardening.js?v=14').catch(e=>console.error('calendar/leads hardening',e));

import('./backup.js?v=15').catch(e=>console.error('backup',e));
