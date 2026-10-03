(function(){
"use strict";

/* F1 Social V7: approved demo UX layered over the existing real-data engine. */
var V7={
  tab:"dashboard",
  publicationMode:"week",
  publicationOffset:0,
  pendingCsv:null,
  emailData:null,
  localDb:null
};

var baseSetTab=setTab;
var baseRenderMetrics=renderMetrics;
var baseRenderClients=renderClients;
var baseRenderPlanner=renderPlanner;
var baseRenderArchiveCurrent=renderArchiveCurrent;
var baseRenderPublicationCenter=renderPublicationCenter;
var baseRenderSocialConnections=renderSocialConnections;
var baseEmailRender=window.f1RenderEmailWorkspace;
var basePublisherRender=window.f1RenderClientPublisherWorkspace;

function v7Client(){
  return (clients||[]).find(function(c){return c.id===selectedClientId})||null;
}
function v7Safe(v){return esc(v==null?"":v)}
function v7Pad(n){return String(n).padStart(2,"0")}
function v7DateKey(d){
  return d.getFullYear()+"-"+v7Pad(d.getMonth()+1)+"-"+v7Pad(d.getDate());
}
function v7DayStart(d){var x=new Date(d);x.setHours(0,0,0,0);return x}
function v7AddDays(d,n){var x=new Date(d);x.setDate(x.getDate()+n);return x}
function v7Monday(d){
  var x=v7DayStart(d),day=(x.getDay()+6)%7;x.setDate(x.getDate()-day);return x;
}
function v7MonthName(i){return ["GENNAIO","FEBBRAIO","MARZO","APRILE","MAGGIO","GIUGNO","LUGLIO","AGOSTO","SETTEMBRE","OTTOBRE","NOVEMBRE","DICEMBRE"][i]}
function v7ShortMonth(i){return ["GEN","FEB","MAR","APR","MAG","GIU","LUG","AGO","SET","OTT","NOV","DIC"][i]}
function v7Weekday(d){return ["DOM","LUN","MAR","MER","GIO","VEN","SAB"][d.getDay()]}
function v7EventDateKey(row){
  var c=v7Client(),tz=(c&&c.timezone)||"Europe/Rome";
  return f1DateKey(row.publication_at,tz);
}
function v7ScopedCalendar(){
  if(!selectedClientId)return [];
  return (calendar||[]).filter(function(x){return x.client_id===selectedClientId});
}
function v7EventsForDate(date){
  var key=v7DateKey(date);
  return v7ScopedCalendar().filter(function(x){return v7EventDateKey(x)===key}).sort(function(a,b){return new Date(a.publication_at)-new Date(b.publication_at)});
}
function v7EventHtml(x){
  var title=x.f1_content_items?x.f1_content_items.title:"Contenuto";
  var t=new Date(x.publication_at).toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"});
  return '<div class="v7-cal-event" draggable="'+(!x.queue_job_id?"true":"false")+'" '+(!x.queue_job_id?'ondragstart="event.dataTransfer.setData(\'text/f1-calendar-id\',\''+v7Safe(x.id)+'\')"':"")+'>'+
    '<b>'+v7Safe(t)+' · '+v7Safe(platformLabel(x.platform||""))+'</b>'+
    '<small>'+v7Safe(title)+' · '+v7Safe(x.status||"")+'</small></div>';
}

function v7ServiceBadge(label,on){
  return '<span class="badge '+(on?"green":"")+'">'+v7Safe(label+(on?" ATTIVO":""))+'</span>';
}
function v7ClientDescription(c){
  var meta=c.profile_metadata||{};
  if(meta.description)return String(meta.description);
  var parts=[c.business_sector||c.category,c.city,c.region].filter(Boolean);
  return parts.join(" · ")||"Cliente F1 Social";
}
function v7ClientProblemCount(c){
  var social=(socialChannels||[]).filter(function(x){return x.client_id===c.id});
  var socialIssues=social.filter(function(x){return !(x.enabled&&x.verified)}).length;
  var cutoff=Date.now()-30*86400000;
  var eventIssues=(publicationEvents||[]).filter(function(x){
    return x.client_id===c.id&&new Date(x.created_at||0).getTime()>=cutoff&&eventIsError(x);
  }).length;
  return socialIssues+eventIssues;
}
function v7ClientServices(c){
  var meta=c.profile_metadata||{},s=meta.services||{};
  var social=s.social===true||(socialChannels||[]).some(function(x){return x.client_id===c.id&&x.enabled&&x.verified});
  var email=c.email_service_enabled===true||s.email===true;
  var site=!!c.website||s.site===true;
  var adv=s.adv===true;
  return [
    v7ServiceBadge("SOCIAL",social),
    v7ServiceBadge("EMAIL",email),
    v7ServiceBadge("SITO",site),
    v7ServiceBadge("ADV",adv)
  ].join("");
}

renderMetrics=function(){
  var active=(clients||[]).filter(function(c){return c.status==="ATTIVO"}).length;
  var contents=(items||[]).length;
  var now=Date.now();
  var scheduled=(calendar||[]).filter(function(x){
    return new Date(x.publication_at).getTime()>=now&&!/ANNULLATO|CANCEL/i.test(String(x.status||""));
  }).length;
  var health=globalThis.F1ClientHealth?F1ClientHealth.dashboard(clients,socialChannels,calendar,items):[];
  var hc=globalThis.F1ClientHealth?F1ClientHealth.counters(health):{warning:0,critical:0};
  var problems=Number(hc.warning||0)+Number(hc.critical||0);
  var host=el("metrics");if(!host)return;
  host.className="metrics v7-metrics-one-line";
  host.innerHTML=[
    [active,"CLIENTI ATTIVI"],
    [contents,"CONTENUTI"],
    [scheduled,"PROGRAMMATI"],
    [problems,"PROBLEMI"]
  ].map(function(x){return '<div class="metric"><b>'+x[0]+'</b><span>'+x[1]+'</span></div>'}).join("");
};

renderClients=function(){
  var host=el("clientCards");if(!host)return;
  var active=(clients||[]).filter(function(c){return c.status==="ATTIVO"});
  host.className="v7-client-list";
  host.innerHTML=active.map(function(c){
    var ownItems=(items||[]).filter(function(x){return x.client_id===c.id});
    var ownCal=(calendar||[]).filter(function(x){return x.client_id===c.id&&new Date(x.publication_at).getTime()>=Date.now()});
    var connected=(socialChannels||[]).filter(function(x){return x.client_id===c.id&&x.enabled&&x.verified}).length;
    var issues=v7ClientProblemCount(c);
    return '<article class="v7-client-row '+(selectedClientId===c.id?"is-selected":"")+'">'+
      '<div class="v7-client-main"><small>CLIENTE</small><h3>'+v7Safe(c.name)+'</h3><div class="v7-client-description" title="'+v7Safe(v7ClientDescription(c))+'">'+v7Safe(v7ClientDescription(c))+'</div></div>'+
      '<div class="v7-client-services">'+v7ClientServices(c)+'</div>'+
      '<div class="v7-client-kpis">'+
        '<div class="v7-client-kpi"><b>'+ownItems.length+'</b><span>CONTENUTI</span></div>'+
        '<div class="v7-client-kpi"><b>'+connected+'</b><span>CANALI</span></div>'+
        '<div class="v7-client-kpi"><b>'+ownCal.length+'</b><span>PROGRAMMATI</span></div>'+
        '<div class="v7-client-kpi"><b>'+issues+'</b><span>PROBLEMI</span></div>'+
      '</div>'+
      '<button class="btn small primary" onclick="window.f1V7OpenClient(\''+v7Safe(c.id)+'\')">APRI</button>'+
    '</article>';
  }).join("")||'<div class="empty">Nessun cliente attivo.</div>';
  var admin=el("clientsAdmin");
  if(admin)admin.innerHTML=host.innerHTML;
};

window.f1V7SetClient=async function(id,destination){
  var chosen=(clients||[]).find(function(c){return c.id===id});
  selectedClientId=chosen?id:"";
  fillClientSelects();
  var url=new URL(location.href);
  if(chosen)url.searchParams.set("client",chosen.slug||chosen.id);else url.searchParams.delete("client");
  url.searchParams.delete("oauth");
  history.replaceState({},document.title,url.pathname+(url.searchParams.toString()?"?"+url.searchParams.toString():""));
  await renderAll();
  setTab(destination||V7.tab||"dashboard");
};
window.f1V7OpenClient=function(id){return window.f1V7SetClient(id,"calendar")};
window.f1SetClientScope=function(id){
  var destination=V7.tab&&V7.tab!=="dashboard"?V7.tab:"dashboard";
  return window.f1V7SetClient(id,destination);
};

function v7ApplyTab(tab){
  V7.tab=tab;
  var selector=el("globalClientSelect");
  if(selector){
    if(tab==="dashboard"){
      selector.value="";
      selector.disabled=true;
    }else{
      selector.disabled=false;
      selector.value=selectedClientId||"";
    }
  }
  var context=el("clientContext");
  if(context)context.classList.toggle("hidden",tab==="dashboard"||tab==="analytics");
  var newBtn=el("openClientBtn");
  if(newBtn)newBtn.classList.toggle("v7-hidden",tab!=="dashboard");

  if(tab==="archive"){
    v7RenderArchiveHeader();
    v7RenderLocalArchive();
  }
  if(tab==="publications"){
    window.f1V7RenderPublicationCalendar();
    window.f1V7AccordionizePublisher();
  }
  if(tab==="connections")v7FixConnectionActions();
  if(tab==="email")window.f1V7RenderEmail();
}
setTab=function(tab,options){
  baseSetTab(tab,options);
  v7ApplyTab(tab);
};

var globalSelect=el("globalClientSelect");
if(globalSelect){
  globalSelect.onchange=function(){
    if(V7.tab==="dashboard"){this.value="";return}
    window.f1V7SetClient(this.value,V7.tab);
  };
}

/* Archive: strict client scope + local PC folder. */
renderArchiveCurrent=async function(){
  v7RenderArchiveHeader();
  if(!selectedClientId){
    if(el("archiveGrid"))el("archiveGrid").innerHTML='<div class="empty">Seleziona un cliente dalla Dashboard o dal selettore superiore per vedere il suo archivio.</div>';
    v7RenderLocalArchive();
    return;
  }
  if(el("clientFilter"))el("clientFilter").value=selectedClientId;
  await baseRenderArchiveCurrent();
  v7RenderLocalArchive();
};

function v7RenderArchiveHeader(){
  var c=v7Client();
  var name=c?c.name:"Seleziona un cliente";
  var n=el("archiveClientNameV7");if(n)n.textContent=name;
  var sub=el("archiveClientSubV7");if(sub)sub.textContent=c?"Archivio esclusivo del cliente selezionato":"Nessun cliente selezionato";
}
function v7LocalDb(){
  if(V7.localDb)return Promise.resolve(V7.localDb);
  return new Promise(function(resolve,reject){
    var req=indexedDB.open("f1-social-local-v7",1);
    req.onupgradeneeded=function(){
      var db=req.result;
      if(!db.objectStoreNames.contains("folders"))db.createObjectStore("folders",{keyPath:"clientId"});
    };
    req.onsuccess=function(){V7.localDb=req.result;resolve(req.result)};
    req.onerror=function(){reject(req.error)};
  });
}
async function v7GetFolder(clientId){
  try{
    var db=await v7LocalDb();
    return await new Promise(function(resolve,reject){
      var r=db.transaction("folders","readonly").objectStore("folders").get(clientId);
      r.onsuccess=function(){resolve(r.result&&r.result.handle?r.result.handle:null)};
      r.onerror=function(){reject(r.error)};
    });
  }catch(_){return null}
}
async function v7SaveFolder(clientId,handle){
  var db=await v7LocalDb();
  return await new Promise(function(resolve,reject){
    var r=db.transaction("folders","readwrite").objectStore("folders").put({clientId:clientId,handle:handle,name:handle.name,updatedAt:new Date().toISOString()});
    r.onsuccess=function(){resolve()};r.onerror=function(){reject(r.error)};
  });
}
async function v7FolderPermission(handle,write){
  if(!handle)return false;
  var opts={mode:write?"readwrite":"read"};
  if((await handle.queryPermission(opts))==="granted")return true;
  return (await handle.requestPermission(opts))==="granted";
}
window.f1V7ChooseFolder=async function(){
  var c=v7Client();if(!c)return alert("Seleziona prima un cliente.");
  if(!window.showDirectoryPicker)return alert("Questo browser non consente il collegamento diretto della cartella. Usa Chrome o Edge aggiornato, oppure il caricamento manuale.");
  try{
    var handle=await window.showDirectoryPicker({mode:"readwrite"});
    await v7SaveFolder(c.id,handle);
    await v7RenderLocalArchive();
  }catch(e){if(e&&e.name!=="AbortError")alert(e.message||String(e))}
};
window.f1V7OpenClientFolder=async function(){
  var c=v7Client();if(!c)return alert("Seleziona prima un cliente.");
  var handle=await v7GetFolder(c.id);
  if(!handle)return window.f1V7ChooseFolder();
  if(!(await v7FolderPermission(handle,false)))return alert("Autorizza nuovamente la cartella del cliente.");
  await v7RenderLocalArchive();
  var box=el("v7LocalArchive");if(box)box.scrollIntoView({behavior:"smooth",block:"nearest"});
};
window.f1V7ImportLocalFiles=async function(){
  var c=v7Client();if(!c)return alert("Seleziona prima un cliente.");
  if(!window.showOpenFilePicker||!window.showDirectoryPicker){
    if(el("uploadClient"))el("uploadClient").value=c.id;
    openModal("uploadModal");
    return;
  }
  var folder=await v7GetFolder(c.id);
  if(!folder){
    await window.f1V7ChooseFolder();
    folder=await v7GetFolder(c.id);
  }
  if(!folder||!(await v7FolderPermission(folder,true)))return;
  try{
    var picks=await window.showOpenFilePicker({multiple:true});
    for(var i=0;i<picks.length;i++){
      var file=await picks[i].getFile();
      var dest=await folder.getFileHandle(file.name,{create:true});
      var writable=await dest.createWritable();
      await writable.write(file);
      await writable.close();
    }
    await v7RenderLocalArchive();
    alert(picks.length+" file salvati nell'archivio locale di "+c.name+".");
  }catch(e){if(e&&e.name!=="AbortError")alert(e.message||String(e))}
};
window.f1V7FromWhatsApp=function(){
  if(!selectedClientId)return alert("Seleziona prima un cliente.");
  setTab("whatsapp");
  var s=el("waClientSelect");if(s)s.value=selectedClientId;
};
async function v7RenderLocalArchive(){
  var host=el("v7LocalArchive");if(!host)return;
  var c=v7Client();
  if(!c){host.innerHTML='<div class="v7-local-note">Seleziona un cliente per collegare la sua cartella locale.</div>';return}
  var handle=await v7GetFolder(c.id);
  if(!handle){
    host.innerHTML='<div class="v7-local-note"><b>Nessuna cartella locale collegata a '+v7Safe(c.name)+'.</b> Usa APRI CARTELLA CLIENTE per autorizzarla.</div>';
    return;
  }
  var ok=false;try{ok=(await handle.queryPermission({mode:"read"}))==="granted"}catch(_){}
  if(!ok){
    host.innerHTML='<div class="v7-local-note"><b>Cartella: '+v7Safe(handle.name)+'</b> · autorizzazione da rinnovare. Premi APRI CARTELLA CLIENTE.</div>';
    return;
  }
  var files=[];
  try{
    for await (var entry of handle.values()){
      if(entry.kind==="file")files.push(entry.name);
      if(files.length>=100)break;
    }
  }catch(e){
    host.innerHTML='<div class="v7-local-note">Cartella collegata ma non leggibile: '+v7Safe(e.message||e)+'</div>';return;
  }
  host.innerHTML='<div class="v7-local-archive-head"><div><b>Archivio locale · '+v7Safe(c.name)+'</b><div class="muted">'+v7Safe(handle.name)+' · '+files.length+' file visibili</div></div><button class="btn tiny ghost" onclick="window.f1V7ChooseFolder()">CAMBIA CARTELLA</button></div>'+
    '<div class="v7-local-files">'+(files.length?files.map(function(name){return '<div class="v7-local-file"><b>'+v7Safe(name)+'</b><small>PC LOCALE</small><span class="badge green">ARCHIVIATO</span></div>'}).join(""):'<div class="v7-local-note">La cartella è vuota.</div>')+'</div>';
}

/* Real calendar in Month / Week 00-24 / Day 00-24. */
function v7CalendarAnchor(mode,offset){
  var base=v7DayStart(new Date());
  if(mode==="month")return new Date(base.getFullYear(),base.getMonth()+offset,1);
  if(mode==="day")return v7AddDays(base,offset);
  return v7AddDays(v7Monday(base),offset*7);
}
function v7RenderMonth(target,mode,offset,clickFn){
  var anchor=v7CalendarAnchor("month",offset);
  var first=new Date(anchor.getFullYear(),anchor.getMonth(),1);
  var start=v7Monday(first);
  var today=v7DateKey(new Date());
  var html='<div class="v7-calendar-month"><div class="v7-month-weekdays"><div>LUN</div><div>MAR</div><div>MER</div><div>GIO</div><div>VEN</div><div>SAB</div><div>DOM</div></div><div class="v7-month-grid">';
  for(var i=0;i<42;i++){
    var d=v7AddDays(start,i),key=v7DateKey(d),outside=d.getMonth()!==anchor.getMonth(),events=v7EventsForDate(d);
    html+='<div class="v7-month-day '+(outside?"outside ":"")+(key===today?"today":"")+'" onclick="'+clickFn+'(\''+key+'\')" ondragover="window.f1CalendarDragOver(event)" ondragleave="window.f1CalendarDragLeave(event)" ondrop="window.f1MoveCalendarEvent(event,\''+key+'\')">'+
      '<div class="v7-month-date">'+d.getDate()+' '+v7ShortMonth(d.getMonth())+'</div>'+events.map(v7EventHtml).join("")+'</div>';
  }
  html+='</div></div>';
  target.innerHTML=html;
}
function v7RenderWeek(target,offset){
  var start=v7CalendarAnchor("week",offset);
  var days=[];for(var i=0;i<7;i++)days.push(v7AddDays(start,i));
  var html='<div class="v7-calendar-week"><div class="v7-week-grid"><div class="v7-week-corner">ORA</div>';
  days.forEach(function(d){html+='<div class="v7-week-head">'+v7Weekday(d)+' '+d.getDate()+'<br><span class="muted">'+v7ShortMonth(d.getMonth())+'</span></div>'});
  for(var hour=0;hour<=24;hour++){
    html+='<div class="v7-week-time">'+v7Pad(hour)+':00</div>';
    days.forEach(function(d){
      var key=v7DateKey(d);
      var events=hour<24?v7EventsForDate(d).filter(function(x){return new Date(x.publication_at).getHours()===hour}):[];
      html+='<div class="v7-week-cell" ondragover="window.f1CalendarDragOver(event)" ondragleave="window.f1CalendarDragLeave(event)" ondrop="window.f1V7MoveCalendarEvent(event,\''+key+'\','+hour+')">'+events.map(v7EventHtml).join("")+'</div>';
    });
  }
  target.innerHTML=html+'</div></div>';
}
function v7RenderDay(target,offset){
  var d=v7CalendarAnchor("day",offset),events=v7EventsForDate(d),key=v7DateKey(d);
  var html='<div class="v7-calendar-day"><div class="v7-day-head">'+v7Weekday(d)+' '+d.getDate()+' '+v7MonthName(d.getMonth())+' '+d.getFullYear()+'</div>';
  for(var hour=0;hour<=24;hour++){
    var slot=hour<24?events.filter(function(x){return new Date(x.publication_at).getHours()===hour}):[];
    html+='<div class="v7-hour-row"><div class="v7-hour-label">'+v7Pad(hour)+':00</div><div class="v7-hour-cell" ondragover="window.f1CalendarDragOver(event)" ondragleave="window.f1CalendarDragLeave(event)" ondrop="window.f1V7MoveCalendarEvent(event,\''+key+'\','+hour+')">'+slot.map(v7EventHtml).join("")+'</div></div>';
  }
  target.innerHTML=html+'</div>';
}
window.f1V7MoveCalendarEvent=async function(ev,dateKey,hour){
  ev.preventDefault();
  var id=ev.dataTransfer?ev.dataTransfer.getData("text/f1-calendar-id"):"";
  var row=(calendar||[]).find(function(x){return x.id===id});if(!row)return;
  if(row.queue_job_id)return alert("Pubblicazione già in coda: non può essere spostata da qui.");
  if(/PUBBLICAT|PUBLISHED|COMPLETED/i.test(String(row.status||"")))return alert("Una pubblicazione già confermata non può essere spostata.");
  var old=new Date(row.publication_at);
  var target=new Date(dateKey+"T00:00:00");
  target.setHours(hour>=24?23:hour,old.getMinutes(),0,0);
  var u=await sb.from("f1_content_calendar").update({publication_at:target.toISOString()}).eq("id",row.id).eq("client_id",row.client_id);
  if(u.error)return alert(u.error.message);
  await loadAll();renderCalendar();window.f1V7RenderPublicationCalendar();
};
window.f1V7OpenCalendarDay=function(key){
  var p=key.split("-").map(Number),target=new Date(p[0],p[1]-1,p[2]),base=v7DayStart(new Date());
  calendarViewMode="day";
  calendarWeekOffset=Math.round((v7DayStart(target)-base)/86400000);
  renderCalendar();
};
renderPlanner=function(){
  baseRenderPlanner();
  var target=el("weekCalendar");if(!target)return;
  target.className="v7-calendar-shell";
  if(!selectedClientId){
    target.innerHTML='<div class="empty" style="padding:28px">Seleziona un cliente per visualizzare il calendario.</div>';return;
  }
  if(calendarViewMode==="month"){
    v7RenderMonth(target,"month",calendarWeekOffset,"window.f1V7OpenCalendarDay");
  }else if(calendarViewMode==="day"){
    v7RenderDay(target,calendarWeekOffset);
  }else{
    v7RenderWeek(target,calendarWeekOffset);
  }
};

window.f1V7PublicationMode=function(mode){
  if(["month","week","day"].indexOf(mode)<0)return;
  V7.publicationMode=mode;V7.publicationOffset=0;window.f1V7RenderPublicationCalendar();
};
window.f1V7PublicationMove=function(delta){V7.publicationOffset+=delta;window.f1V7RenderPublicationCalendar()};
window.f1V7PublicationToday=function(){V7.publicationOffset=0;window.f1V7RenderPublicationCalendar()};
window.f1V7OpenPublicationDay=function(key){
  var p=key.split("-").map(Number),target=new Date(p[0],p[1]-1,p[2]),base=v7DayStart(new Date());
  V7.publicationMode="day";V7.publicationOffset=Math.round((v7DayStart(target)-base)/86400000);window.f1V7RenderPublicationCalendar();
};
window.f1V7RenderPublicationCalendar=function(){
  var target=el("publicationCalendarV7");if(!target)return;
  var c=v7Client(),lab=el("publicationCalendarClientV7");
  if(lab)lab.textContent=c?("Programmazioni future · "+c.name):"Seleziona un cliente";
  ["Month","Week","Day"].forEach(function(n){
    var b=el("publicationMode"+n+"V7");if(!b)return;
    var on=V7.publicationMode===n.toLowerCase();b.classList.toggle("primary",on);b.classList.toggle("ghost",!on);
  });
  var period=el("publicationPeriodV7");
  if(!c){target.innerHTML='<div class="empty" style="padding:28px">Seleziona un cliente per vedere le pubblicazioni.</div>';if(period)period.textContent="—";return}
  if(V7.publicationMode==="month"){
    var a=v7CalendarAnchor("month",V7.publicationOffset);if(period)period.textContent=v7MonthName(a.getMonth())+" "+a.getFullYear();
    v7RenderMonth(target,"month",V7.publicationOffset,"window.f1V7OpenPublicationDay");
  }else if(V7.publicationMode==="day"){
    var d=v7CalendarAnchor("day",V7.publicationOffset);if(period)period.textContent=v7Weekday(d)+" "+d.getDate()+" "+v7MonthName(d.getMonth())+" "+d.getFullYear();
    v7RenderDay(target,V7.publicationOffset);
  }else{
    var s=v7CalendarAnchor("week",V7.publicationOffset),e=v7AddDays(s,6);if(period)period.textContent=s.getDate()+" "+v7ShortMonth(s.getMonth())+" — "+e.getDate()+" "+v7ShortMonth(e.getMonth())+" "+e.getFullYear();
    v7RenderWeek(target,V7.publicationOffset);
  }
};

renderPublicationCenter=function(){
  baseRenderPublicationCenter();
  window.f1V7RenderPublicationCalendar();
};

/* Existing real publisher workspace, now accordionized inside Publications. */
window.f1V7AccordionizePublisher=function(){
  var root=el("clientPublisherWorkspace");if(!root)return;
  root.classList.add("v7-publisher-in-publications");
  root.querySelectorAll(".distribution-row").forEach(function(row,index){
    if(row.dataset.v7Accordion==="1")return;
    row.dataset.v7Accordion="1";
    row.classList.add("v7-channel-accordion");
    if(index>0)row.classList.add("v7-collapsed");
    var head=row.children[0];if(!head)return;
    var toggle=document.createElement("button");
    toggle.type="button";toggle.className="v7-channel-toggle";
    toggle.innerHTML='<span>'+head.innerHTML+'</span><span class="v7-channel-chevron">⌄</span>';
    head.innerHTML="";head.appendChild(toggle);
    toggle.onclick=function(ev){ev.preventDefault();ev.stopPropagation();row.classList.toggle("v7-collapsed")};
  });
};
if(basePublisherRender){
  window.f1RenderClientPublisherWorkspace=async function(){
    await basePublisherRender();
    window.f1V7AccordionizePublisher();
  };
}

/* Connections keep real OAuth, only simplify the action wording. */
function v7FixConnectionActions(){
  var host=el("socialConnectionsDedicated");if(!host)return;
  if(!selectedClientId){
    host.innerHTML='<div class="empty">Seleziona un cliente per verificare le sue connessioni.</div>';return;
  }
  host.querySelectorAll(".lineitem").forEach(function(row){
    var badge=row.querySelector(".badge");
    var state=badge?String(badge.textContent||"").trim():"";
    row.querySelectorAll("button").forEach(function(btn){
      var t=String(btn.textContent||"").trim();
      if(state!=="COLLEGATO"&&(t==="COLLEGA"||t==="RIAUTORIZZA"))btn.textContent="RISOLVI";
    });
  });
}
renderSocialConnections=function(){
  baseRenderSocialConnections();
  v7FixConnectionActions();
};

/* Email V7 — real account state + isolated plan tables + CSV import. */
async function v7EmailApi(action,payload){
  var s=await sb.auth.getSession();
  var token=s&&s.data&&s.data.session&&s.data.session.access_token;
  if(!token)throw new Error("Sessione scaduta.");
  var r=await fetch(SUPABASE_URL+"/functions/v1/f1-client-email",{
    method:"POST",
    headers:{apikey:SUPABASE_KEY,Authorization:"Bearer "+token,"Content-Type":"application/json"},
    body:JSON.stringify(Object.assign({action:action},payload||{}))
  });
  var data={};try{data=await r.json()}catch(_){}
  if(!r.ok||data.ok===false)throw new Error(data.error||data.message||("Errore EMAIL "+r.status));
  return data;
}
function v7EmailPrompt(c){
  var meta=c.profile_metadata||{};
  var desc=meta.description||v7ClientDescription(c);
  var services=[];
  var s=meta.services||{};
  if(s.social)services.push("social media");
  if(c.email_service_enabled||s.email)services.push("email marketing");
  if(c.website||s.site)services.push("sito web");
  if(s.adv)services.push("advertising");
  if(!services.length)services.push(c.category||"servizi professionali");
  var website=c.website||"da definire";
  return "CREA UN PIANO CONTENUTISTICO EMAIL COMPLETO DI 12 MESI PER:\\n\\n"+
    "AZIENDA / PROFESSIONISTA:\\n"+c.name+"\\n\\n"+
    "DESCRIZIONE:\\n"+desc+"\\n\\n"+
    "SETTORE:\\n"+(c.business_sector||c.category||"da definire")+"\\n\\n"+
    "SERVIZI:\\n"+services.join(", ")+"\\n\\n"+
    "SITO / LINK PRINCIPALE:\\n"+website+"\\n\\n"+
    "OBIETTIVO:\\nMantenere il contatto con il database CRM, educare il potenziale cliente, creare fiducia e generare richieste di contatto o appuntamento coerenti con l'attività.\\n\\n"+
    "FREQUENZA:\\n1 email alla settimana per 12 mesi.\\n\\n"+
    "PERIODO:\\nda ottobre 2026 a settembre 2027.\\n\\n"+
    "Crea una strategia annuale coerente e non ripetitiva. Alterna contenuti educativi, problema/soluzione, casi pratici, curiosità, autorevolezza, territorio, servizi, fiducia e conversione. "+
    "Scrivi anche il contenuto completo di ogni email. Programma preferibilmente il giovedì alle 10:00; se un mese contiene 5 giovedì, crea 5 email.\\n\\n"+
    "PER OGNI EMAIL GENERA:\\n"+
    "1. cliente\\n2. data_invio (YYYY-MM-DD)\\n3. ora_invio (HH:MM)\\n4. mese\\n5. settimana\\n6. tema\\n7. obiettivo\\n8. oggetto_email\\n9. preheader\\n10. corpo_email completo\\n11. cta_testo\\n12. cta_url\\n13. segmento_crm\\n14. stato\\n\\n"+
    "Usa TUTTI_I_CONTATTI come segmento CRM salvo necessità diversa. Usa PROGRAMMATA come stato nel CSV.\\n\\n"+
    "ALLA FINE CREA UN CSV UTF-8 IMPORTABILE IN F1 SOCIAL. L'HEADER DEVE ESSERE ESATTAMENTE:\\n"+
    "cliente,data_invio,ora_invio,mese,settimana,tema,obiettivo,oggetto_email,preheader,corpo_email,cta_testo,cta_url,segmento_crm,stato\\n\\n"+
    "REGOLE CSV:\\n- una riga = una email;\\n- nessuna colonna extra;\\n- campi testuali tra virgolette;\\n- raddoppia le virgolette interne;\\n- mantieni correttamente virgole e ritorni a capo dentro i campi quotati;\\n- nel campo cliente scrivi sempre: "+c.name+";\\n- usa il link "+website+" quando pertinente;\\n- non inserire spiegazioni dentro il CSV.\\n\\n"+
    "OUTPUT: prima una breve sintesi mensile, poi il CSV completo pronto per F1 Social.";
}
function v7CsvDelimiter(text){
  var line=(text.split(/\\r?\\n/)[0]||"");
  return ((line.match(/;/g)||[]).length>(line.match(/,/g)||[]).length)?";":",";
}
function v7ParseCsv(text){
  text=String(text||"").replace(/^\\uFEFF/,"");
  var d=v7CsvDelimiter(text),rows=[],row=[],field="",quoted=false;
  for(var i=0;i<text.length;i++){
    var ch=text[i];
    if(quoted){
      if(ch==='"'){
        if(text[i+1]==='"'){field+='"';i++}else quoted=false;
      }else field+=ch;
    }else{
      if(ch==='"')quoted=true;
      else if(ch===d){row.push(field);field=""}
      else if(ch==="\\n"){row.push(field);field="";if(row.some(function(v){return String(v).trim()!==""}))rows.push(row);row=[]}
      else if(ch!=="\\r")field+=ch;
    }
  }
  row.push(field);if(row.some(function(v){return String(v).trim()!==""}))rows.push(row);
  if(!rows.length)return [];
  var headers=rows[0].map(function(x){return x.trim()});
  return rows.slice(1).map(function(cols){
    var o={};headers.forEach(function(h,i){o[h]=String(cols[i]||"").trim()});return o;
  });
}
function v7ValidateCsv(rows,c){
  var required=["cliente","data_invio","ora_invio","mese","settimana","tema","obiettivo","oggetto_email","preheader","corpo_email","cta_testo","cta_url","segmento_crm","stato"];
  if(!rows.length)throw new Error("CSV vuoto.");
  var missing=required.filter(function(k){return !(k in rows[0])});
  if(missing.length)throw new Error("Colonne mancanti: "+missing.join(", "));
  rows.forEach(function(r,idx){
    if(String(r.cliente||"").trim().toLowerCase()!==String(c.name).trim().toLowerCase())throw new Error("Riga "+(idx+2)+": cliente diverso da "+c.name+".");
    if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(r.data_invio||""))throw new Error("Riga "+(idx+2)+": data_invio non valida.");
    if(!/^\\d{2}:\\d{2}$/.test(r.ora_invio||""))throw new Error("Riga "+(idx+2)+": ora_invio non valida.");
    if(!r.tema||!r.oggetto_email||!r.corpo_email)throw new Error("Riga "+(idx+2)+": tema, oggetto o corpo email mancanti.");
    var dt=new Date(r.data_invio+"T"+r.ora_invio+":00");if(isNaN(dt.getTime()))throw new Error("Riga "+(idx+2)+": data/ora impossibile.");
  });
  return rows;
}
function v7CsvQuote(v){return '"'+String(v==null?"":v).replace(/"/g,'""')+'"'}
window.f1V7DownloadCsvTemplate=function(){
  var c=v7Client();if(!c)return alert("Seleziona prima un cliente.");
  var header=["cliente","data_invio","ora_invio","mese","settimana","tema","obiettivo","oggetto_email","preheader","corpo_email","cta_testo","cta_url","segmento_crm","stato"];
  var sample=[c.name,"2026-10-08","10:00","OTTOBRE 2026","1","Tema della settimana","Obiettivo","Oggetto email","Preheader","Corpo completo email","Scopri di più",c.website||"","TUTTI_I_CONTATTI","PROGRAMMATA"];
  var csv="\\uFEFF"+header.join(",")+"\\r\\n"+sample.map(v7CsvQuote).join(",");
  var blob=new Blob([csv],{type:"text/csv;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="modello-piano-email-"+slugify(c.name)+".csv";document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
};
window.f1V7CopyEmailPrompt=async function(){
  var ta=el("v7EmailPrompt");if(!ta)return;
  try{await navigator.clipboard.writeText(ta.value)}catch(_){ta.select();document.execCommand("copy")}
  alert("Prompt copiato.");
};
window.f1V7OpenChatGPT=function(){
  var w=window.open("https://chatgpt.com/","_blank","noopener");
  window.f1V7CopyEmailPrompt();
  if(!w)alert("Il browser ha bloccato la nuova scheda. Il prompt è comunque stato copiato.");
};
window.f1V7CsvSelected=function(file){
  if(!file)return;
  var c=v7Client();if(!c)return alert("Seleziona prima un cliente.");
  var reader=new FileReader();
  reader.onload=function(){
    try{
      var rows=v7ValidateCsv(v7ParseCsv(reader.result),c);
      V7.pendingCsv={fileName:file.name,rows:rows,clientId:c.id};
      var host=el("v7EmailCsvPreview"),status=el("v7EmailCsvStatus");
      if(status){status.className="v7-email-statusline ok";status.innerHTML='<b>'+rows.length+' email valide</b> · '+v7Safe(file.name)+' · pronte per l\'importazione.'}
      if(host){
        host.innerHTML='<table><thead><tr><th>DATA</th><th>OGGETTO</th><th>TEMA</th><th>CTA</th><th>STATO CSV</th></tr></thead><tbody>'+
          rows.slice(0,12).map(function(r){return '<tr><td>'+v7Safe(r.data_invio)+' '+v7Safe(r.ora_invio)+'</td><td>'+v7Safe(r.oggetto_email)+'</td><td>'+v7Safe(r.tema)+'</td><td>'+v7Safe(r.cta_testo)+'</td><td>'+v7Safe(r.stato)+'</td></tr>'}).join("")+
          '</tbody></table><div class="v7-email-actions"><button class="btn green" onclick="window.f1V7ImportEmailPlan()">IMPORTA PIANO</button><button class="btn ghost" onclick="window.f1V7CancelCsv()">ANNULLA</button></div>';
      }
    }catch(e){
      V7.pendingCsv=null;
      var s=el("v7EmailCsvStatus");if(s){s.className="v7-email-statusline";s.textContent="CSV non valido: "+(e.message||e)}
    }
  };
  reader.readAsText(file,"UTF-8");
};
window.f1V7CancelCsv=function(){V7.pendingCsv=null;var p=el("v7EmailCsvPreview");if(p)p.innerHTML="";var s=el("v7EmailCsvStatus");if(s)s.textContent="Nessun CSV in attesa di importazione."};
window.f1V7ImportEmailPlan=async function(){
  var c=v7Client(),pending=V7.pendingCsv;
  if(!c||!pending||pending.clientId!==c.id)return alert("Carica prima un CSV valido per il cliente selezionato.");
  if(!user)return alert("Sessione non disponibile.");
  var rows=pending.rows.map(function(r){
    var dt=new Date(r.data_invio+"T"+r.ora_invio+":00");
    return {
      owner_id:user.id,client_id:c.id,scheduled_at:dt.toISOString(),month_label:r.mese||"",week_number:Number(r.settimana)||null,
      theme:r.tema||"",objective:r.obiettivo||"",subject:r.oggetto_email||"",preheader:r.preheader||"",body_text:r.corpo_email||"",
      cta_text:r.cta_testo||"",cta_url:r.cta_url||"",crm_segment:r.segmento_crm||"TUTTI_I_CONTATTI",
      status:"IMPORTATA",source_status:r.stato||"PROGRAMMATA",source_file_name:pending.fileName,
      metadata:{csv_date:r.data_invio,csv_time:r.ora_invio,csv_month:r.mese||"",csv_week:r.settimana||""},updated_at:new Date().toISOString()
    };
  });
  var setting=await sb.from("f1_email_plan_settings").upsert({
    owner_id:user.id,client_id:c.id,active:true,cadence:"WEEKLY",send_weekday:4,send_time:"10:00",timezone:c.timezone||"Europe/Rome",updated_at:new Date().toISOString()
  },{onConflict:"owner_id,client_id"});
  if(setting.error)return alert(setting.error.message);
  var up=await sb.from("f1_email_plan_items").upsert(rows,{onConflict:"owner_id,client_id,scheduled_at"});
  if(up.error)return alert(up.error.message);
  V7.pendingCsv=null;
  await window.f1V7RenderEmail();
  alert(rows.length+" email importate nel piano annuale di "+c.name+". Nessuna email è stata inviata.");
};
window.f1V7ToggleEmailAI=function(){var box=el("v7EmailAI");if(box)box.classList.toggle("open")};
window.f1V7TogglePlanMonth=function(node){if(node)node.classList.toggle("open")};
window.f1V7LegacyEmailAccount=async function(){
  if(!baseEmailRender)return alert("Modulo account email non disponibile.");
  await baseEmailRender(true);
  if(window.f1EmailSetView)window.f1EmailSetView("account");
};
window.f1V7ConfigureEmailAuto=async function(){
  var c=v7Client();if(!c||!user)return;
  var current=V7.emailData&&V7.emailData.setting;
  var next=!(current&&current.active);
  var r=await sb.from("f1_email_plan_settings").upsert({
    owner_id:user.id,client_id:c.id,active:next,cadence:"WEEKLY",send_weekday:4,send_time:"10:00",timezone:c.timezone||"Europe/Rome",updated_at:new Date().toISOString()
  },{onConflict:"owner_id,client_id"});
  if(r.error)return alert(r.error.message);
  await window.f1V7RenderEmail();
};
async function v7LoadEmailData(c){
  var result={status:null,setting:null,plan:[],crmCount:0};
  try{result.status=await v7EmailApi("STATUS",{client_id:c.id})}catch(e){result.status={error:e.message,accounts:[],campaigns:[]}}
  var setting=await sb.from("f1_email_plan_settings").select("*").eq("client_id",c.id).maybeSingle();
  if(!setting.error)result.setting=setting.data||null;
  var plan=await sb.from("f1_email_plan_items").select("*").eq("client_id",c.id).order("scheduled_at",{ascending:true});
  if(!plan.error)result.plan=plan.data||[];
  try{
    var crm=await v7EmailApi("CRM_COUNT",{client_id:c.id});
    result.crmCount=Number(crm.count||0);
  }catch(_){
    var campaigns=(result.status&&result.status.campaigns)||[];
    result.crmCount=Math.max.apply(null,[0].concat(campaigns.map(function(x){return Number(x.total_recipients||0)})));
  }
  return result;
}
function v7EmailAccountCard(c,data){
  var accounts=(data.status&&data.status.accounts)||[],a=accounts[0]||null;
  var state=a?(a.connection_status||"DA VERIFICARE"):"NON CONFIGURATA";
  var address=a?(a.email_address||a.connected_email||"—"):(c.email||"Email non configurata");
  var provider=a?(a.provider||""):"";
  var connected=state==="COLLEGATO";
  return '<div class="v7-email-account-grid">'+
    '<div class="v7-email-card"><div class="meta">EMAIL CLIENTE</div><div class="v7-email-address">'+v7Safe(address)+'</div><div class="muted">'+v7Safe(provider)+'</div>'+
      '<div class="v7-email-actions"><span class="badge '+(connected?"green":"amber")+'">'+v7Safe(state.replaceAll("_"," "))+'</span>'+
      '<button class="btn '+(connected?"ghost":"green")+'" onclick="window.f1V7LegacyEmailAccount()">'+(connected?"GESTISCI ACCOUNT":"COLLEGA EMAIL")+'</button>'+
      '<button class="btn ghost" onclick="window.f1V7RenderEmail()">VERIFICA</button></div></div>'+
    '<div class="v7-email-card"><div class="meta">EMAIL NEL CRM</div><div class="v7-email-crm-count">'+data.crmCount+'</div><div class="muted">Contatti email associati al cliente</div></div>'+
  '</div>';
}
function v7EmailAIHtml(c){
  return '<div id="v7EmailAI" class="v7-email-ai">'+
    '<button class="v7-email-ai-head" onclick="window.f1V7ToggleEmailAI()"><div><b>✨ IA · CREA PIANO EMAIL · 12 MESI</b><small>Genera il piano in ChatGPT e importalo con un CSV</small></div><span>⌄</span></button>'+
    '<div class="v7-email-ai-body"><textarea id="v7EmailPrompt" class="input" readonly>'+v7Safe(v7EmailPrompt(c))+'</textarea>'+
    '<div class="v7-email-actions"><button class="btn primary" onclick="window.f1V7OpenChatGPT()">✨ APRI CHATGPT</button><button class="btn ghost" onclick="window.f1V7CopyEmailPrompt()">COPIA PROMPT</button>'+
    '<button class="btn ghost" onclick="window.f1V7DownloadCsvTemplate()">SCARICA MODELLO CSV</button><button class="btn green" onclick="document.getElementById(\'v7EmailCsvInput\').click()">CARICA CSV</button></div>'+
    '<input id="v7EmailCsvInput" type="file" accept=".csv,text/csv" hidden onchange="window.f1V7CsvSelected(this.files&&this.files[0])">'+
    '<div id="v7EmailCsvStatus" class="v7-email-statusline">Nessun CSV in attesa di importazione.</div><div id="v7EmailCsvPreview" class="v7-email-preview"></div></div></div>';
}
function v7EmailAutomationHtml(c,data){
  var active=!!(data.setting&&data.setting.active);
  return '<div class="v7-email-card"><div class="section-title"><div><h3>Automazione email</h3><div class="muted">Generazione e programmazione del cliente selezionato</div></div><span class="badge '+(active?"green":"amber")+'">'+(active?"ATTIVA":"NON CONFIGURATA")+'</span></div>'+
    '<div class="v7-email-auto-summary"><div class="v7-email-auto-cell"><span>AUTOMAZIONE</span><b>Contenuto + email</b></div>'+
    '<div class="v7-email-auto-cell"><span>FREQUENZA</span><b>1 volta alla settimana</b></div>'+
    '<div class="v7-email-auto-cell"><span>STATO</span><b>'+(active?"ATTIVA":"DISATTIVA")+'</b></div>'+
    '<button class="btn primary" onclick="window.f1V7ConfigureEmailAuto()">'+(active?"DISATTIVA AUTO":"CONFIGURA AUTO")+'</button></div>'+
    '<div class="v7-email-statusline"><b>PROGRAMMATA IN AUTOMATICO 1 VOLTA ALLA SETTIMANA</b> · '+v7Safe(c.name)+
    '<br><span class="muted">Il piano importato non invia nulla al caricamento. Gli invii reali restano soggetti a account collegato, destinatari validi, test/approvazione e conferma provider.</span></div></div>';
}
function v7EmailPlanHtml(c,data){
  var rows=data.plan||[];
  if(!rows.length)return '<div class="v7-email-card"><div class="section-title"><div><h3>Piano automatico email · 12 mesi</h3><div class="muted">1 email a settimana · '+v7Safe(c.name)+'</div></div></div><div class="empty">Nessun piano importato. Usa IA · CREA PIANO EMAIL e carica il CSV.</div></div>';
  var groups={};
  rows.forEach(function(r){
    var d=new Date(r.scheduled_at),key=r.month_label||v7MonthName(d.getMonth())+" "+d.getFullYear();
    (groups[key]||(groups[key]=[])).push(r);
  });
  var body=Object.keys(groups).map(function(month){
    var list=groups[month],first=list[0],link=(list.find(function(x){return x.cta_url})||{}).cta_url||c.website||"—";
    var details=list.map(function(r){
      var d=new Date(r.scheduled_at);
      return '<div class="v7-email-item"><b>'+v7Safe(d.toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</b><span>'+v7Safe(r.subject||r.theme)+'</span><span>'+v7Safe(r.crm_segment||"TUTTI_I_CONTATTI")+'</span><span class="badge '+(r.status==="INVIATA"?"green":r.status==="ERRORE"?"":"amber")+'">'+v7Safe(r.status)+'</span>'+
        '<div class="v7-email-item-body"><b>Tema:</b> '+v7Safe(r.theme)+'\\n<b>Obiettivo:</b> '+v7Safe(r.objective)+'\\n<b>Preheader:</b> '+v7Safe(r.preheader)+'\\n<b>CTA:</b> '+v7Safe(r.cta_text)+' · '+v7Safe(r.cta_url)+'\\n\\n'+v7Safe(r.body_text)+'</div></div>';
    }).join("");
    return '<div class="v7-email-plan-row" onclick="window.f1V7TogglePlanMonth(this)"><b>'+v7Safe(month)+'</b><span>'+v7Safe(first.theme||"Piano email")+'</span><b>'+list.length+' EMAIL</b><span title="'+v7Safe(link)+'">'+v7Safe(link)+'</span><b>'+data.crmCount+' contatti</b><span class="v7-email-plan-chevron">⌄</span><div class="v7-email-plan-details">'+details+'</div></div>';
  }).join("");
  return '<div class="v7-email-card"><div class="section-title"><div><h3>Piano automatico email · 12 mesi</h3><div class="muted">1 email a settimana · '+v7Safe(c.name)+' · contatti CRM letti dinamicamente</div></div><span class="badge green">'+rows.length+' EMAIL</span></div>'+
    '<div class="v7-email-plan-head"><div>MESE</div><div>CONTENUTO</div><div>EMAIL</div><div>LINK</div><div>CONTATTI</div><div></div></div><div class="v7-email-plan-list">'+body+'</div></div>';
}
window.f1V7RenderEmail=async function(){
  var root=el("emailWorkspace");if(!root)return;
  var c=v7Client();
  if(!c){root.innerHTML='<div class="empty">Seleziona un cliente per aprire la sua email.</div>';return}
  root.innerHTML='<div class="empty">Caricamento email di '+v7Safe(c.name)+'…</div>';
  try{
    var data=await v7LoadEmailData(c);V7.emailData=data;
    if(v7Client()&&v7Client().id!==c.id)return;
    root.innerHTML='<div class="v7-email-shell">'+v7EmailAccountCard(c,data)+v7EmailAIHtml(c)+v7EmailAutomationHtml(c,data)+v7EmailPlanHtml(c,data)+'</div>';
  }catch(e){root.innerHTML='<div class="notice error">Email non caricata: '+v7Safe(e.message||e)+'</div>'}
};
window.f1RenderEmailWorkspace=window.f1V7RenderEmail;

/* Final DOM adaptation after the base app has loaded. */
function v7Init(){
  if(el("clientFilter"))el("clientFilter").classList.add("v7-client-filter-hidden");
  var selector=el("globalClientSelect");
  if(selector)selector.disabled=true;
  v7ApplyTab("dashboard");
}
v7Init();

})();