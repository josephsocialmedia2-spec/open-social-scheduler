const SUPA='https://nqnmlsmeiynxbdojeyjt.supabase.co', KEY='sb_publishable_Clz5qPTkTtvwV0rqWTcfMQ_sCDSRgnu';
let S=null,currentContent=null;try{S=JSON.parse(localStorage.getItem('mr_session')||sessionStorage.getItem('mr_session')||'null')}catch{}
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)], esc=(v='')=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const T={profiles:'marta_profiles',contents:'marta_contents',transcripts:'marta_transcripts',social_variants:'marta_social_variants',schedules:'marta_schedules',integrations:'marta_integrations',leads:'marta_leads',performance_metrics:'marta_performance_metrics',service_costs:'marta_service_costs',editorial_profiles:'marta_editorial_profiles',autopilot_settings:'marta_autopilot_settings',audit_logs:'marta_audit_logs',media_versions:'marta_media_versions'};
const R={initialize_user:'marta_initialize_user',approve_content:'marta_approve_content',reopen_content:'marta_reopen_content',schedule_content:'marta_schedule_content',run_autopilot:'marta_run_autopilot'};
const fmt=v=>v?new Date(v).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'}):'—', toast=(m,b=false)=>{let e=$('#toast');if(!e)return;e.textContent=m;e.style.background=b?'#8b3040':'#14233b';e.hidden=false;clearTimeout(window.tt);window.tt=setTimeout(()=>e.hidden=true,4200)};
function validSession(s=S){return !!(s?.access_token&&s?.refresh_token&&s?.user?.id)}
function saveSession(s){if(!validSession(s))throw Error('Sessione non valida');S=s;let raw=JSON.stringify(s);localStorage.setItem('mr_session',raw);sessionStorage.setItem('mr_session',raw)}
function clearSession(){S=null;localStorage.removeItem('mr_session');sessionStorage.removeItem('mr_session')}
function path(p){if(p.startsWith('rpc/'))return 'rpc/'+(R[p.slice(4)]||p.slice(4));let q=p.indexOf('?'),n=q<0?p:p.slice(0,q);return (T[n]||n)+(q<0?'':p.slice(q))}
function hdr(json=true){let h={apikey:KEY,Authorization:`Bearer ${S?.access_token||''}`};if(json)h['Content-Type']='application/json';return h}
async function refresh(){if(!S?.refresh_token)throw Error('Sessione scaduta');let r=await fetch(SUPA+'/auth/v1/token?grant_type=refresh_token',{method:'POST',headers:{apikey:KEY,'Content-Type':'application/json'},body:JSON.stringify({refresh_token:S.refresh_token})});let d=await r.json();if(!r.ok)throw Error('Sessione scaduta');saveSession(d)}
async function db(p,o={},retried=false){if(!S?.access_token)throw Error('Accedi prima');let r=await fetch(SUPA+'/rest/v1/'+path(p),{method:o.method||'GET',headers:{...hdr(),Prefer:o.prefer||'return=representation'},body:o.body===undefined?undefined:JSON.stringify(o.body)});if(r.status===401&&!retried){await refresh();return db(p,o,true)}let tx=await r.text(),d;try{d=tx?JSON.parse(tx):null}catch{d=tx}if(!r.ok)throw Error(typeof d==='string'?d:(d.message||JSON.stringify(d)));return d}
async function auth(endpoint,body){let r=await fetch(SUPA+'/auth/v1/'+endpoint,{method:'POST',headers:{apikey:KEY,'Content-Type':'application/json'},body:JSON.stringify(body)}),d=await r.json();if(!r.ok)throw Error(d.msg||d.error_description||d.error||'Operazione non riuscita');return d}
async function login(){let d=await auth('token?grant_type=password',{email:$('#email').value.trim(),password:$('#password').value});saveSession(d);await enter()}
async function profileExists(){if(!validSession())throw Error('Sessione non valida');return !!(await db(`profiles?id=eq.${S.user.id}&select=id`))?.length}
async function enter(){if(!validSession())throw Error('Sessione non valida');if(!await profileExists()){await db('rpc/initialize_user',{method:'POST',body:{}});if(!await profileExists())throw Error('Account non autorizzato per Marta Digital Hub')}$('#login').hidden=true;$('#claim').hidden=true;$('#app').hidden=false;await all()}
async function logout(){let old=S;clearSession();if(old?.access_token){try{await fetch(SUPA+'/auth/v1/logout',{method:'POST',headers:{apikey:KEY,Authorization:'Bearer '+old.access_token},keepalive:true})}catch{}}location.replace('./accesso.html?v=12')}
function view(v){$$('.view').forEach(x=>x.classList.toggle('active',x.id===v));$$('#nav button').forEach(x=>x.classList.toggle('active',x.dataset.v===v));let b=$(`#nav button[data-v="${v}"]`);$('#title').textContent=b?.textContent||'Digital Hub'}
async function quota(){
 const DERIVED_RESERVE=57671680,budget=800000000;
 const [c,v]=await Promise.all([
  db(`contents?owner_id=eq.${S.user.id}&select=id,file_size,audio_file_size,publish_file_size`),
  db(`media_versions?owner_id=eq.${S.user.id}&select=content_id,file_size`)
 ]);
 const byContent=new Map;
 for(const x of v)byContent.set(x.content_id,(byContent.get(x.content_id)||0)+Number(x.file_size||0));
 let actual=0,used=0;
 for(const x of c){
  const original=Number(x.file_size||0),derived=Number(x.audio_file_size||0)+Number(x.publish_file_size||0)+(byContent.get(x.id)||0);
  actual+=original+derived;
  used+=original+Math.max(DERIVED_RESERVE,derived);
  byContent.delete(x.id);
 }
 const orphanDerived=[...byContent.values()].reduce((a,n)=>a+n,0);
 actual+=orphanDerived;used+=orphanDerived;
 $('#quota').innerHTML=`<b>${(used/1024/1024).toFixed(1)} MB</b> impegnati su budget interno prudenziale ${(budget/1024/1024).toFixed(0)} MB · ${(100*used/budget).toFixed(1)}%<br><span class="hint">Spazio fisico registrato: ${(actual/1024/1024).toFixed(1)} MB. La differenza è una riserva prudenziale per i file derivati.</span>`;
 return {used,budget,actual}
}
async function dash(){let [c,l,s]=await Promise.all([db('contents?select=id,title,status,created_at&order=created_at.desc&limit=100'),db('leads?select=id,status&limit=100'),db('schedules?select=id,content_id,platform,status,scheduled_for&order=scheduled_for.asc&limit=100')]);let ks=[['Contenuti',c.length],['Da approvare',c.filter(x=>x.status==='DA_APPROVARE').length],['Lead nuovi',l.filter(x=>x.status==='NUOVO').length],['Programm.',s.filter(x=>x.status==='PROGRAMMATO').length]];$('#kpis').innerHTML=ks.map(x=>`<div class=card><small>${x[0]}</small><b>${x[1]}</b></div>`).join('');let a=c.filter(x=>x.status==='DA_APPROVARE').slice(0,6);$('#approvals').innerHTML=a.length?a.map(x=>itemContent(x)).join(''):'<p class=hint>Niente in attesa.</p>';let u=s.filter(x=>x.status==='PROGRAMMATO'&&new Date(x.scheduled_for)>new Date()).slice(0,6);$('#upcoming').innerHTML=u.length?u.map(x=>`<div class=item><div><b>${esc(x.platform)}</b><p>${fmt(x.scheduled_for)}</p></div><span class="status ${x.status}">${x.status}</span></div>`).join(''):'<p class=hint>Nessuna pubblicazione futura.</p>';await quota();bindOpen()}
function itemContent(x){return `<div class=item><div><b>${esc(x.title)}</b><p>${esc(x.category||'')} · ${fmt(x.created_at)}</p></div><div class=actions><span class="status ${x.status}">${x.status}</span><button class="ghost smallbtn open" data-id="${x.id}">Apri</button></div></div>`}
async function contents(){let c=await db('contents?select=*&order=created_at.desc&limit=200');$('#contentsList').innerHTML=c.length?c.map(itemContent).join(''):'<p class=hint>Archivio vuoto.</p>';bindOpen()}
function bindOpen(){$$('.open').forEach(b=>b.onclick=()=>openContent(b.dataset.id))}
