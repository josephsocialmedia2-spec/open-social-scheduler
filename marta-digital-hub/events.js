$('#loginForm').onsubmit=async e=>{e.preventDefault();$('#loginMsg').textContent='Accesso…';try{await login();$('#loginMsg').textContent=''}catch(x){$('#loginMsg').textContent=x.message}};
$('#signup').onclick=()=>location.replace('./accesso.html?v=18');
$('#claimForm').onsubmit=e=>{e.preventDefault();$('#claimMsg').textContent='Questo account non è autorizzato.'};
$('#claimLogout').onclick=$('#logout').onclick=logout;$('#dlgClose').onclick=()=>$('#dlg').close();$('#refreshContents').onclick=contents;$('#calStatus').onchange=calendar;
$$('#nav button').forEach(b=>b.onclick=()=>view(b.dataset.v));

$('#uploadForm').onsubmit=e=>e.preventDefault();

$('#autoForm').onsubmit=async e=>{e.preventDefault();await db(`autopilot_settings?owner_id=eq.${S.user.id}`,{method:'PATCH',body:{enabled:$('#autoEnabled').checked,posts_per_day:Number($('#autoPosts').value),slots:[$('#autoSlot1').value,$('#autoSlot2').value].filter(Boolean),platforms:['instagram','facebook'],weekdays:[1,2,3,4,5],timezone:'Europe/Rome',horizon_days:7}});toast('Autopilot salvato');await autopilot()};
$('#autoRun').onclick=async()=>{try{let r=await db('rpc/run_autopilot',{method:'POST',body:{}});toast(r?.length?`${r.length} contenuti programmati`:'Nessun contenuto approvato da programmare');await all()}catch(e){toast(e.message,true)}};
$('#leadForm').onsubmit=async e=>{e.preventDefault();await db('leads',{method:'POST',body:{owner_id:S.user.id,name:$('#leadName').value.trim(),contact:$('#leadContact').value.trim(),source:$('#leadSource').value.trim(),platform:$('#leadPlatform').value||null,request:$('#leadRequest').value.trim(),status:'NUOVO'}});e.target.reset();toast('Lead registrato');await all()};
$('#costForm').onsubmit=async e=>{e.preventDefault();await db('service_costs',{method:'POST',body:{owner_id:S.user.id,service:$('#costService').value.trim(),provider:$('#costProvider').value.trim(),cost:Number($('#costValue').value||0),frequency:'mensile',account_owner:'Marta Ruffino'}});e.target.reset();toast('Costo salvato');await costs()};
$('#settingsForm').onsubmit=async e=>{e.preventDefault();await Promise.all([db(`editorial_profiles?owner_id=eq.${S.user.id}`,{method:'PATCH',body:{name:$('#setName').value,voice:$('#setVoice').value,forbidden_claims:$('#setForbidden').value}}),db(`profiles?id=eq.${S.user.id}`,{method:'PATCH',body:{site_url:$('#setSite').value||null}})]);toast('Impostazioni salvate')};
window.addEventListener('storage',e=>{if(e.key==='mr_session'&&!e.newValue)location.replace('./accesso.html?v=18')});
(async()=>{if(!validSession()){clearSession();location.replace('./accesso.html?v=18');return}try{await enter()}catch(e){console.error(e);clearSession();location.replace('./accesso.html?v=18&reason=session')}})();
import('./content-hardening.js?v=13').catch(e=>console.error('content hardening',e));

import('./calendar-leads-hardening.js?v=14').catch(e=>console.error('calendar/leads hardening',e));

import('./backup.js?v=15').catch(e=>console.error('backup',e));

import('./library-caption-dashboard.js?v=18').catch(e=>console.error('library/caption/dashboard',e));
