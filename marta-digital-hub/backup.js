import {encryptBackup,decryptBackup} from './backup-crypto.mjs?v=15';

const MR_BACKUP_TABLES=[
  ['profiles','marta_profiles','id'],
  ['contents','marta_contents','id'],
  ['transcripts','marta_transcripts','id'],
  ['social_variants','marta_social_variants','id'],
  ['media_versions','marta_media_versions','id'],
  ['schedules','marta_schedules','id'],
  ['integrations','marta_integrations','owner_id,platform'],
  ['leads','marta_leads','id'],
  ['performance_metrics','marta_performance_metrics','id'],
  ['service_costs','marta_service_costs','id'],
  ['editorial_profiles','marta_editorial_profiles','id'],
  ['autopilot_settings','marta_autopilot_settings','owner_id'],
  ['investment_entries','marta_investment_entries','id'],
  ['tracking_links','marta_tracking_links','id']
];

async function mrFetchAll(table){
  const out=[];
  for(let offset=0;offset<100000;offset+=1000){
    const rows=await db(`${table}?select=*&limit=1000&offset=${offset}`);
    out.push(...rows);
    if(rows.length<1000)return out;
  }
  throw Error('Troppi record per il backup gratuito: esportazione fermata in sicurezza.');
}
async function mrLogBackup(status,bytes,note){
  try{
    await db('marta_backup_runs',{method:'POST',body:{owner_id:S.user.id,status,bytes:Number(bytes||0),note:String(note||'').slice(0,1000)},prefer:'return=minimal'});
  }catch(e){console.warn('backup log',e)}
}
function mrDownload(name,text){
  const blob=new Blob([text],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
  return blob.size;
}
async function mrExportBackup(){
  const pass=document.querySelector('#backupPass')?.value||'';
  if(pass.length<12)throw Error('Scegli una password backup di almeno 12 caratteri.');
  const data={};
  for(const [key,table] of MR_BACKUP_TABLES)data[key]=await mrFetchAll(table);
  const payload={
    app:'Marta Ruffino Digital Hub',
    app_version:'0.8.0',
    schema_version:1,
    exported_at:new Date().toISOString(),
    owner_id:S.user.id,
    scope:'metadata-and-storage-references',
    data
  };
  const envelope=await encryptBackup(payload,pass);
  const text=JSON.stringify(envelope);
  const stamp=new Date().toISOString().replace(/[:.]/g,'-');
  const bytes=mrDownload(`marta-digital-hub-${stamp}.mrbackup`,text);
  await mrLogBackup('ESPORTATO',bytes,'Backup cifrato metadata + riferimenti storage');
  return bytes;
}
function mrForceOwner(rows){
  return (Array.isArray(rows)?rows:[]).map(r=>({...r,owner_id:S.user.id}));
}
function mrSafeContents(rows){
  return mrForceOwner(rows).map(r=>({
    ...r,
    status:['APPROVATO','PROGRAMMATO','PUBBLICATO'].includes(r.status)?'DA_APPROVARE':r.status
  }));
}
function mrSafeVariants(rows){
  return mrForceOwner(rows).map(r=>r.status==='APPROVATO'?{...r,status:'DA_RIVEDERE',approved_at:null}:r);
}
function mrSafeSchedules(rows){
  return mrForceOwner(rows).map(r=>({
    ...r,
    status:['PROGRAMMATO','INVIATO','MANUALE_ASSISTITO'].includes(r.status)?'ANNULLATO':r.status
  }));
}
function mrSafeIntegrations(rows){
  return mrForceOwner(rows).map(({id,...r})=>({
    ...r,owner_id:S.user.id,enabled:false,status:'NON_CONFIGURATO',
    external_integration_id:null,last_checked_at:null
  }));
}
function mrSafeProfiles(rows){
  const r=(Array.isArray(rows)&&rows[0])?rows[0]:{};
  return [{...r,id:S.user.id,display_name:r.display_name||'Marta Ruffino',role:r.role||'OWNER'}];
}
function mrSafeAutopilot(rows){
  return mrForceOwner(rows).map(r=>({...r,enabled:false,timezone:'Europe/Rome'}));
}
async function mrUpsert(table,rows,onConflict){
  if(!rows?.length)return 0;
  let done=0;
  for(let i=0;i<rows.length;i+=100){
    const batch=rows.slice(i,i+100);
    await db(`${table}?on_conflict=${encodeURIComponent(onConflict)}`,{
      method:'POST',body:batch,prefer:'resolution=merge-duplicates,return=minimal'
    });
    done+=batch.length;
  }
  return done;
}
async function mrRestorePayload(payload){
  if(!payload||payload.app!=='Marta Ruffino Digital Hub'||payload.schema_version!==1||!payload.data)throw Error('Contenuto backup non compatibile.');
  const d=payload.data,total={};
  const plan=[
    ['marta_profiles',mrSafeProfiles(d.profiles),'id'],
    ['marta_contents',mrSafeContents(d.contents),'id'],
    ['marta_transcripts',mrForceOwner(d.transcripts),'id'],
    ['marta_social_variants',mrSafeVariants(d.social_variants),'id'],
    ['marta_media_versions',mrForceOwner(d.media_versions),'id'],
    ['marta_integrations',mrSafeIntegrations(d.integrations),'owner_id,platform'],
    ['marta_leads',mrForceOwner(d.leads),'id'],
    ['marta_performance_metrics',mrForceOwner(d.performance_metrics),'id'],
    ['marta_service_costs',mrForceOwner(d.service_costs),'id'],
    ['marta_editorial_profiles',mrForceOwner(d.editorial_profiles),'id'],
    ['marta_autopilot_settings',mrSafeAutopilot(d.autopilot_settings),'owner_id'],
    ['marta_investment_entries',mrForceOwner(d.investment_entries),'id'],
    ['marta_tracking_links',mrForceOwner(d.tracking_links),'id'],
    ['marta_schedules',mrSafeSchedules(d.schedules),'id']
  ];
  for(const [table,rows,conflict] of plan)total[table]=await mrUpsert(table,rows,conflict);
  return Object.values(total).reduce((a,b)=>a+b,0);
}
async function mrRestoreBackup(file){
  if(!file)throw Error('Scegli il file .mrbackup.');
  if(file.size>20*1024*1024)throw Error('Backup troppo grande: ripristino fermato in sicurezza.');
  const pass=document.querySelector('#backupPass')?.value||'';
  const payload=await decryptBackup(await file.text(),pass);
  const count=await mrRestorePayload(payload);
  await mrLogBackup('RIPRISTINATO',file.size,`Restore sicuro: ${count} record; Autopilot disattivato; approvazioni riaperte`);
  return count;
}
async function mrBackupHistory(){
  const host=document.querySelector('#backupHistory');if(!host)return;
  try{
    const rows=await db('marta_backup_runs?select=status,bytes,note,created_at&order=created_at.desc&limit=12');
    host.innerHTML=rows.length?rows.map(x=>`<div class="item"><div><b>${esc(x.status)}</b><p>${fmt(x.created_at)} · ${(Number(x.bytes||0)/1024).toFixed(1)} KB<br>${esc(x.note||'')}</p></div></div>`).join(''):'<p class="hint">Nessun backup registrato.</p>';
  }catch(e){host.innerHTML=`<p class="danger">${esc(e.message)}</p>`}
}
function mrInstallBackupUI(){
  if(document.querySelector('#backup'))return;
  const nav=document.querySelector('#nav'),settingsButton=nav?.querySelector('[data-v="settings"]');
  const btn=document.createElement('button');btn.dataset.v='backup';btn.textContent='Backup';
  if(settingsButton)nav.insertBefore(btn,settingsButton);else nav?.appendChild(btn);
  btn.onclick=()=>{view('backup');mrBackupHistory()};

  const settings=document.querySelector('#settings');
  const section=document.createElement('section');section.id='backup';section.className='view';
  section.innerHTML=`<div class="grid2">
    <article class="panel"><h2>Backup cifrato</h2>
      <p class="hint">Salva database, caption, calendario, impostazioni, lead, statistiche e riferimenti ai video. I file video restano nello storage privato cloud.</p>
      <label>Password del backup<input id="backupPass" type="password" minlength="12" maxlength="200" autocomplete="new-password" placeholder="Almeno 12 caratteri"></label>
      <div class="actions" style="margin-top:12px"><button id="backupExport" type="button">Esporta backup cifrato</button></div>
      <p class="warn"><b>Conserva la password.</b> Non viene memorizzata e senza di essa il file non può essere aperto.</p>
    </article>
    <article class="panel"><h2>Ripristina</h2>
      <p class="hint">Il restore è prudenziale: disattiva Autopilot, riapre le approvazioni e scollega gli OAuth importati per evitare pubblicazioni involontarie.</p>
      <label>File backup<input id="backupFile" type="file" accept=".mrbackup,application/json"></label>
      <button id="backupRestore" type="button" class="ghost">Ripristina backup</button>
      <p id="backupState" class="hint"></p>
    </article>
  </div><article class="panel"><h2>Storico backup</h2><div id="backupHistory" class="stack"></div></article>`;
  settings?.insertAdjacentElement('beforebegin',section);

  document.querySelector('#backupExport').onclick=async e=>{
    e.currentTarget.disabled=true;
    const state=document.querySelector('#backupState');
    try{state.textContent='Creo e cifro il backup…';const bytes=await mrExportBackup();state.textContent=`✓ Backup creato (${(bytes/1024).toFixed(1)} KB).`;toast('Backup cifrato creato');await mrBackupHistory()}
    catch(err){state.textContent=err.message;toast(err.message,true)}
    finally{e.currentTarget.disabled=false}
  };
  document.querySelector('#backupRestore').onclick=async e=>{
    const file=document.querySelector('#backupFile').files[0],state=document.querySelector('#backupState');
    if(!confirm('Ripristinare questo backup? Le pubblicazioni automatiche verranno disattivate.'))return;
    e.currentTarget.disabled=true;
    try{state.textContent='Decifro e ripristino…';const count=await mrRestoreBackup(file);state.textContent=`✓ Ripristino completato: ${count} record elaborati.`;toast('Backup ripristinato');await all();await mrBackupHistory()}
    catch(err){state.textContent=err.message;toast(err.message,true)}
    finally{e.currentTarget.disabled=false}
  };
}
mrInstallBackupUI();
mrBackupHistory();
export {mrRestorePayload};
