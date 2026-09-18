const MARTA_TZ='Europe/Rome';
const MARTA_LEAD_LIMITS={name:200,contact:500,source:200,request:4000};
let martaAutoWeekdays=[1,2,3,4,5];

function martaRomeParts(date){
  const parts=new Intl.DateTimeFormat('en-GB',{
    timeZone:MARTA_TZ,year:'numeric',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'
  }).formatToParts(date);
  return Object.fromEntries(parts.filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));
}
function martaRomeInputValue(iso){
  const p=martaRomeParts(new Date(iso));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}
function martaRomeDisplay(iso){
  return new Date(iso).toLocaleString('it-IT',{
    timeZone:MARTA_TZ,dateStyle:'short',timeStyle:'short'
  });
}
function martaRomeOffsetMs(date){
  const p=martaRomeParts(date);
  return Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute,+p.second)-date.getTime();
}
function martaRomeLocalToIso(value){
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value||''))throw Error('Scegli data e ora.');
  const [d,t]=value.split('T'),[y,m,day]=d.split('-').map(Number),[h,mi]=t.split(':').map(Number);
  const target=Date.UTC(y,m-1,day,h,mi,0);
  let guess=new Date(target);
  for(let i=0;i<4;i++)guess=new Date(target-martaRomeOffsetMs(guess));
  const p=martaRomeParts(guess);
  if(+p.year!==y||+p.month!==m||+p.day!==day||+p.hour!==h||+p.minute!==mi){
    throw Error('Questo orario non esiste nel fuso Europe/Rome (cambio ora legale).');
  }
  return guess.toISOString();
}

async function martaCalendar(){
  const status=document.querySelector('#calStatus')?.value||'';
  let q='schedules?select=id,content_id,platform,status,scheduled_for&order=scheduled_for.asc&limit=300';
  if(status)q+='&status=eq.'+encodeURIComponent(status);
  const [rows,contents]=await Promise.all([db(q),db('contents?select=id,title')]);
  const names=Object.fromEntries(contents.map(x=>[x.id,x.title]));
  const host=document.querySelector('#calendarList');
  if(!host)return;
  host.innerHTML=rows.length?rows.map(x=>{
    const editable=x.status==='PROGRAMMATO';
    const controls=editable?`<div class="actions" style="margin-top:8px">
      <input class="calWhen" type="datetime-local" value="${martaRomeInputValue(x.scheduled_for)}" style="max-width:220px">
      <button type="button" class="ghost smallbtn calMove" data-id="${esc(x.id)}">Sposta</button>
      <button type="button" class="ghost smallbtn danger calCancel" data-id="${esc(x.id)}">Annulla</button>
    </div>`:'';
    return `<div class="item"><div><b>${esc(names[x.content_id]||'Contenuto')}</b><p>${esc(x.platform)} · ${martaRomeDisplay(x.scheduled_for)} · Europe/Rome</p>${controls}</div><span class="status ${x.status}">${x.status}</span></div>`;
  }).join(''):'<p class="hint">Nessuna programmazione.</p>';

  host.querySelectorAll('.calMove').forEach(btn=>btn.onclick=async()=>{
    try{
      const input=btn.closest('.item').querySelector('.calWhen');
      const iso=martaRomeLocalToIso(input.value);
      if(new Date(iso)<=new Date())throw Error('Scegli una data futura.');
      btn.disabled=true;
      await db('rpc/marta_reschedule_item',{method:'POST',body:{p_schedule_id:btn.dataset.id,p_when:iso}});
      toast('Programmazione spostata');
      await martaCalendar();await dash();
    }catch(err){toast(err.message||'Impossibile spostare la programmazione',true);btn.disabled=false}
  });
  host.querySelectorAll('.calCancel').forEach(btn=>btn.onclick=async()=>{
    if(!confirm('Annullare questa pubblicazione programmata?'))return;
    try{
      btn.disabled=true;
      await db('rpc/marta_cancel_schedule',{method:'POST',body:{p_schedule_id:btn.dataset.id}});
      toast('Programmazione annullata');
      await martaCalendar();await dash();await contents();
    }catch(err){toast(err.message||'Impossibile annullare la programmazione',true);btn.disabled=false}
  });
}
globalThis.calendar=martaCalendar;
const calStatus=document.querySelector('#calStatus');
if(calStatus)calStatus.onchange=martaCalendar;

function martaEnsureAutoControls(){
  const form=document.querySelector('#autoForm');if(!form)return;
  if(!document.querySelector('#autoSlot3')){
    const slot2=document.querySelector('#autoSlot2')?.closest('label');
    const label=document.createElement('label');
    label.innerHTML='Orario 3<input id="autoSlot3" type="time">';
    slot2?.insertAdjacentElement('afterend',label);
  }
  if(!document.querySelector('#autoPlatforms')){
    const button=form.querySelector('button');
    const box=document.createElement('div');
    box.id='autoPlatforms';
    box.innerHTML='<b>Piattaforme</b><div class="actions" style="margin-top:7px">'+
      ['instagram','facebook','tiktok','youtube','linkedin'].map(p=>`<label style="display:flex;align-items:center;gap:5px;font-weight:500"><input type="checkbox" class="autoPlatform" value="${p}" style="width:auto"> ${p}</label>`).join('')+
      '</div>';
    button?.insertAdjacentElement('beforebegin',box);
  }
}
async function martaAutopilot(){
  martaEnsureAutoControls();
  const a=(await db('autopilot_settings?select=*'))[0];if(!a)return;
  martaAutoWeekdays=Array.isArray(a.weekdays)&&a.weekdays.length?a.weekdays:[1,2,3,4,5];
  document.querySelector('#autoEnabled').checked=a.enabled;
  document.querySelector('#autoPosts').value=String(a.posts_per_day);
  document.querySelector('#autoSlot1').value=(a.slots?.[0]||'09:00').slice(0,5);
  document.querySelector('#autoSlot2').value=(a.slots?.[1]||'18:00').slice(0,5);
  document.querySelector('#autoSlot3').value=(a.slots?.[2]||'').slice(0,5);
  document.querySelectorAll('.autoPlatform').forEach(x=>x.checked=(a.platforms||[]).includes(x.value));
  document.querySelector('#autoState').textContent=a.enabled
    ?'Autopilot attivo. Usa solo contenuti e caption già approvati.'
    :'Autopilot disattivato.';
}
globalThis.autopilot=martaAutopilot;

function martaBindAutoForm(){
  const form=document.querySelector('#autoForm');if(!form)return;
  form.onsubmit=async e=>{
    e.preventDefault();
    try{
      const posts=Number(document.querySelector('#autoPosts').value);
      const slots=['#autoSlot1','#autoSlot2','#autoSlot3'].map(s=>document.querySelector(s)?.value).filter(Boolean);
      const platforms=[...document.querySelectorAll('.autoPlatform:checked')].map(x=>x.value);
      if(!platforms.length)throw Error('Seleziona almeno una piattaforma.');
      if(slots.length<posts)throw Error(`Per ${posts} post al giorno servono almeno ${posts} orari.`);
      await db(`autopilot_settings?owner_id=eq.${S.user.id}`,{method:'PATCH',body:{
        enabled:document.querySelector('#autoEnabled').checked,
        posts_per_day:posts,slots,platforms,weekdays:martaAutoWeekdays,
        timezone:MARTA_TZ,horizon_days:7
      }});
      toast('Autopilot salvato');await martaAutopilot();
    }catch(err){toast(err.message||'Impossibile salvare Autopilot',true)}
  };
}

function martaBindLeadForm(){
  const ids={leadName:'name',leadContact:'contact',leadSource:'source',leadRequest:'request'};
  for(const [id,key] of Object.entries(ids)){
    const el=document.getElementById(id);if(el)el.maxLength=MARTA_LEAD_LIMITS[key];
  }
  const form=document.querySelector('#leadForm');if(!form)return;
  form.onsubmit=async e=>{
    e.preventDefault();
    const name=document.querySelector('#leadName').value.trim();
    const contact=document.querySelector('#leadContact').value.trim();
    const source=document.querySelector('#leadSource').value.trim();
    const request=document.querySelector('#leadRequest').value.trim();
    if(!name&&!contact){toast('Inserisci almeno nome oppure contatto.',true);return}
    try{
      await db('leads',{method:'POST',body:{
        owner_id:S.user.id,name:name||null,contact:contact||null,source:source||null,
        platform:document.querySelector('#leadPlatform').value||null,request:request||null,status:'NUOVO'
      }});
      form.reset();toast('Lead registrato');await all();
    }catch(err){toast(err.message||'Impossibile registrare il lead',true)}
  };
}

martaEnsureAutoControls();
martaBindAutoForm();
martaBindLeadForm();
if(S?.access_token){
  Promise.allSettled([martaCalendar(),martaAutopilot()]).catch(()=>{});
}
