(function(){
"use strict";

const WS_PLATFORMS=[
  {id:"facebook",label:"Facebook",time:"11:00"},
  {id:"instagram",label:"Instagram",time:"13:30"},
  {id:"tiktok",label:"TikTok",time:"18:30"},
  {id:"youtube",label:"YouTube",time:"21:00"},
  {id:"linkedin-page",label:"LinkedIn",time:"09:30"}
];

function h(value){return String(value==null?"":value).replace(/[&<>"']/g,function(m){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]})}
function clone(v){return JSON.parse(JSON.stringify(v||{}))}
function currentClient(){return (clients||[]).find(function(x){return x.id===selectedClientId})||null}
function prefFor(client,platform){
  const prefs=client&&client.publishing_preferences&&typeof client.publishing_preferences==="object"?client.publishing_preferences:{};
  const found=prefs[platform]&&typeof prefs[platform]==="object"?prefs[platform]:{};
  const def=WS_PLATFORMS.find(function(x){return x.id===platform})||{time:"12:00"};
  return {time:String(found.time||def.time),enabled:found.enabled!==false}
}
function channelFor(clientId,platform){return (socialChannels||[]).find(function(x){return x.client_id===clientId&&x.platform===platform})||null}
function channelState(clientId,platform){
  const row=channelFor(clientId,platform);
  if(!row)return "CANALE_DA_COLLEGARE";
  try{
    if(typeof effectiveSocialState==="function"&&typeof socialCollisionMap==="function")return effectiveSocialState(row,socialCollisionMap());
  }catch(_){}
  return row.enabled&&row.verified?"COLLEGATO":(row.connection_status||"CANALE_DA_COLLEGARE");
}
function cleanTitle(name){
  return String(name||"Contenuto").replace(/\.[a-z0-9]{2,5}$/i,"").replace(/[_-]+/g," ").replace(/\s+/g," ").trim()||"Contenuto";
}
function contentTypeFromMime(mime){
  mime=String(mime||"");
  if(mime.startsWith("image/"))return "FOTO";
  if(mime.startsWith("video/"))return "VIDEO";
  if(mime.startsWith("audio/"))return "AUDIO";
  return "DOCUMENTO";
}
function classify(text){
  const s=String(text||"").toLowerCase();
  if(/matrimon|spos|cerimoni|battesim|comunion|cresim/.test(s))return "CERIMONIE";
  if(/menu|menù|piatt|risott|carne|pesce|dolce|dessert|cucin|pranzo|cena/.test(s))return "MENU";
  if(/evento|serata|party|festa|musica/.test(s))return "EVENTO";
  if(/recension|review|cliente|ospit/.test(s))return "RECENSIONE";
  if(/sala|location|esterno|vista|panoram|ristorante/.test(s))return "LOCATION";
  if(/offerta|promo|sconto|speciale/.test(s))return "PROMOZIONE";
  if(/backstage|staff|cucina|preparaz/.test(s))return "BACKSTAGE";
  return "BRANDING";
}
function contactLines(client){
  const out=[];
  if(client&&client.slug==="antica-cappella"){
    out.push("📍 Via Maritano Lino 10, Avigliana");
    out.push("📞 011 931 1155");
    out.push("🌐 anticacappella.it");
    return out.join("\n");
  }
  const place=[client&&client.address,client&&client.city].filter(Boolean).join(", ");
  if(place)out.push("📍 "+place);
  if(client&&client.phone)out.push("📞 "+client.phone);
  if(client&&client.website){
    try{out.push("🌐 "+new URL(client.website).hostname.replace(/^www\./,""))}catch(_){out.push("🌐 "+client.website)}
  }
  return out.join("\n");
}
function hashtags(client,category){
  if(client&&client.slug==="antica-cappella"){
    const base=["#AnticaCappella","#Avigliana","#Ristorante","#ValleDiSusa"];
    const extra={CERIMONIE:["#Matrimoni","#Cerimonie","#Eventi"],MENU:["#CucinaPiemontese","#Menu","#Ristorazione"],EVENTO:["#Eventi","#Serata"],LOCATION:["#Avigliana","#Location"],RECENSIONE:["#Ospitalità"],PROMOZIONE:["#EventoSpeciale"],BACKSTAGE:["#Cucina","#DietroLeQuinte"],BRANDING:["#Ristorazione"]}[category]||[];
    return Array.from(new Set(base.concat(extra)));
  }
  return ["#"+String(client&&client.name||"Brand").replace(/[^A-Za-z0-9]/g,""),"#SocialMedia"].filter(function(x){return x!=="#"});
}
function baseCaption(client,title,category,seed){
  if(String(seed||"").trim())return String(seed).trim();
  if(client&&client.slug==="antica-cappella"){
    const templates={
      CERIMONIE:"Il vostro momento speciale merita uno spazio capace di accoglierlo con cura. Scopri Antica Cappella per matrimoni, cerimonie e ricorrenze ad Avigliana.",
      MENU:"Sapori, cura e convivialità: un nuovo dettaglio della cucina di Antica Cappella.",
      EVENTO:"Un nuovo appuntamento all'Antica Cappella. Scopri tutti i dettagli e prenota il tuo tavolo.",
      LOCATION:"Gli spazi dell'Antica Cappella ad Avigliana: atmosfera, accoglienza e una location pensata per stare bene insieme.",
      RECENSIONE:"Grazie a chi sceglie Antica Cappella e condivide la propria esperienza.",
      PROMOZIONE:"Una nuova proposta dell'Antica Cappella ad Avigliana. Scopri i dettagli.",
      BACKSTAGE:"Dietro ogni servizio ci sono preparazione, attenzione e lavoro di squadra.",
      BRANDING:"Antica Cappella, Avigliana. Cucina, accoglienza, eventi e momenti da condividere."
    };
    return templates[category]||templates.BRANDING;
  }
  return String(title||client&&client.name||"Nuovo contenuto").trim();
}
function captionFor(client,title,category,base,platform){
  const contacts=contactLines(client),tags=hashtags(client,category);
  const text=String(base||baseCaption(client,title,category,"")).trim();
  if(platform==="instagram")return [text,contacts,tags.slice(0,8).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="facebook")return [text,contacts,tags.slice(0,5).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="tiktok")return [text.slice(0,700),tags.slice(0,6).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="youtube")return [title,text,contacts,tags.slice(0,5).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="linkedin-page")return [text,contacts,tags.slice(0,4).join(" ")].filter(Boolean).join("\n\n");
  return text;
}
function planState(clientId,platform,mime,item){
  const type=String(mime||"").toLowerCase();
  const isVideo=type.startsWith("video/"),isImage=type.startsWith("image/");
  if(!type)return "MEDIA_MISSING";
  if(!isVideo&&!isImage)return "FORMATO_NON_SUPPORTATO";
  const state=channelState(clientId,platform);
  if(state!=="COLLEGATO")return state;
  if(platform==="youtube"&&!isVideo)return "FORMATO_NON_SUPPORTATO";
  if(platform==="linkedin-page"&&isVideo)return "FORMATO_NON_SUPPORTATO";
  if(platform==="tiktok"&&isImage)return "TIKTOK_PHOTO_URL_REQUIRED";
  if(platform==="tiktok"&&isVideo){
    const s=item&&item.tiktok_settings&&typeof item.tiktok_settings==="object"?item.tiktok_settings:{};
    if(!s.consent_confirmed||!s.mode)return "TIKTOK_REVIEW_REQUIRED";
  }
  return "PRONTO";
}
function buildPlan(client,title,category,base,mime,source,item){
  const plan={version:1,source:source||"WEB",category:category||"BRANDING",created_at:new Date().toISOString(),platforms:{}};
  WS_PLATFORMS.forEach(function(p){
    const pref=prefFor(client,p.id),generated=captionFor(client,title,category,base,p.id);
    plan.platforms[p.id]={
      caption:generated,
      generated_caption:generated,
      time:pref.time,
      enabled:pref.enabled,
      status:planState(client.id,p.id,mime,item),
      scheduled_at:null
    };
  });
  return plan;
}
function itemMime(item){
  const media=(item&&item.f1_content_media||[])[0];
  return media&&media.mime_type?media.mime_type:"";
}
function itemPlan(item,client){
  const existing=item&&item.distribution_plan&&item.distribution_plan.platforms?clone(item.distribution_plan):null;
  if(existing)return existing;
  const category=classify([item&&item.title,item&&item.description,item&&item.campaign].join(" "));
  return buildPlan(client,item&&item.title||"Contenuto",category,item&&item.description||item&&item.source_text||"",itemMime(item),item&&item.source||"WEB",item);
}
function sourceLabel(value){
  const s=String(value||"WEB").toUpperCase();
  return {CARTELLA:"DA CARTELLA",DRAG_DROP:"TRASCINATO",WHATSAPP:"DA WHATSAPP",WEB:"CARICATO",CHATGPT_LIBRARY:"LIBRERIA"}[s]||s;
}
function nextAt(time,dayOffset){
  const bits=String(time||"12:00").split(":").map(Number);
  const d=new Date();d.setSeconds(0,0);d.setHours(bits[0]||0,bits[1]||0,0,0);
  if(d.getTime()<=Date.now())d.setDate(d.getDate()+1);
  d.setDate(d.getDate()+(dayOffset||0));
  return d;
}
async function updatePlan(item,plan){
  const r=await sb.from("f1_content_items").update({distribution_plan:plan,updated_at:new Date().toISOString()}).eq("id",item.id).eq("client_id",item.client_id);
  if(r.error)throw r.error;
  item.distribution_plan=plan;
}
async function previewMedia(){
  const client=currentClient();if(!client)return;
  const rows=(items||[]).filter(function(x){return x.client_id===client.id&&x.distribution_plan&&x.distribution_plan.platforms}).slice(0,12);
  for(const item of rows){
    const host=document.querySelector('[data-ws-preview="'+item.id+'"]');if(!host)continue;
    const media=(item.f1_content_media||[])[0];if(!media)continue;
    try{
      const url=await signedUrl(media);if(!url)continue;
      if(String(media.mime_type||"").startsWith("image/"))host.innerHTML='<img src="'+h(url)+'" alt="">';
      else if(String(media.mime_type||"").startsWith("video/"))host.innerHTML='<video src="'+h(url)+'" muted controls playsinline></video>';
      else host.textContent=media.file_name||"FILE";
    }catch(_){}
  }
}
function planItemsForClient(client){
  return (items||[]).filter(function(x){
    return x.client_id===client.id&&x.status!=="ARCHIVIATO"&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""));
  }).slice(0,12);
}
window.f1RenderClientPublisherWorkspace=async function(){
  const root=document.getElementById("clientPublisherWorkspace");if(!root)return;
  const client=currentClient();
  if(!client){root.classList.add("hidden");root.innerHTML="";return}
  root.classList.remove("hidden");
  const prefs=WS_PLATFORMS.map(function(p){
    const pref=prefFor(client,p.id),state=channelState(client.id,p.id);
    return '<div class="publish-time"><b>'+h(p.label)+' · '+h(state)+'</b><input type="time" value="'+h(pref.time)+'" onchange="window.f1WorkspaceSaveTime(\''+client.id+'\',\''+p.id+'\',this.value)"></div>';
  }).join("");
  const rows=planItemsForClient(client);
  const cards=rows.map(function(item){
    const plan=itemPlan(item,client),media=(item.f1_content_media||[])[0],mime=media&&media.mime_type||"";
    const pRows=WS_PLATFORMS.map(function(p){
      const data=plan.platforms[p.id]||{},state=planState(client.id,p.id,mime,item);
      const shown=data.scheduled_at?"PROGRAMMATO":(data.status||state);
      return '<div class="distribution-row">'+
        '<div><b>'+h(p.label)+'</b><div class="meta">'+h(data.time||prefFor(client,p.id).time)+'</div></div>'+
        '<div><span class="badge '+(shown==="PROGRAMMATO"||shown==="PRONTO"?"green":shown==="COLLEGATO"?"green":"")+'">'+h(shown)+'</span>'+(data.scheduled_at?'<div class="meta">'+h(new Date(data.scheduled_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</div>':"")+'</div>'+
        '<textarea onchange="window.f1WorkspaceSaveCaption(\''+item.id+'\',\''+p.id+'\',this.value)">'+h(data.caption||"")+'</textarea>'+
        '<div class="row-actions"><button class="btn tiny ghost" onclick="window.f1WorkspaceRegenerate(\''+item.id+'\',\''+p.id+'\')">RIGENERA</button><button class="btn tiny ghost" onclick="window.f1WorkspaceResetCaption(\''+item.id+'\',\''+p.id+'\')">RIPRISTINA</button><button class="btn tiny ghost" onclick="window.f1WorkspaceCopyCaption(\''+item.id+'\',\''+p.id+'\')">COPIA</button></div>'+
      '</div>';
    }).join("");
    return '<article class="distribution-card">'+
      '<div class="distribution-main"><div class="distribution-preview" data-ws-preview="'+item.id+'">ANTEPRIMA</div><div class="distribution-title"><div class="publisher-source">'+h(sourceLabel(item.source))+'</div><h3>'+h(item.title||"Contenuto")+'</h3><div class="meta">'+h(plan.category||item.campaign||"CONTENUTO")+' · '+h(item.status||"")+'</div><div class="row"><button class="btn small green" onclick="window.f1WorkspaceScheduleItem(\''+item.id+'\')">PROGRAMMA SU TUTTI I SOCIAL</button></div></div></div>'+
      '<div class="distribution-channels">'+pRows+'</div></article>';
  }).join("");
  root.innerHTML='<section class="publisher-console">'+
    '<div class="publisher-head"><div><h2>Carica contenuti · '+h(client.name)+'</h2><div class="muted">Carica una volta, controlla caption e orari, poi distribuisci sui canali social del cliente.</div></div><div class="publisher-actions"><span class="badge '+(client.auto_publish?"green":"amber")+'">'+(client.auto_publish?"PUBBLICAZIONE AUTOMATICA ATTIVA":"AUTOMAZIONE DA ATTIVARE")+'</span><button class="btn small green" onclick="window.f1WorkspaceProgramAll()">PROGRAMMA TUTTO</button></div></div>'+
    '<div class="ingest-grid">'+
      '<button class="ingest-action" onclick="window.f1WorkspaceOpenWhatsApp()"><b>DA WHATSAPP</b><span>Importa messaggi e media ricevuti per questo cliente.</span></button>'+
      '<button class="ingest-action" onclick="document.getElementById(\'workspaceFolderInput\').click()"><b>DA CARTELLA</b><span>Seleziona una cartella con immagini e video.</span></button>'+
      '<button class="ingest-action" onclick="document.getElementById(\'workspaceFileInput\').click()"><b>DA FILE</b><span>Seleziona più contenuti dal computer.</span></button>'+
      '<div id="workspaceDropZone" class="client-dropzone" onclick="document.getElementById(\'workspaceFileInput\').click()" ondragover="window.f1WorkspaceDrag(event,true)" ondragleave="window.f1WorkspaceDrag(event,false)" ondrop="window.f1WorkspaceDrop(event)"><b>TRASCINA QUI I CONTENUTI</b><div class="meta">Foto, video e documenti. Ogni file diventa un contenuto distribuibile.</div></div>'+
      '<input id="workspaceFileInput" type="file" multiple accept="image/*,video/*,audio/*,.pdf,.doc,.docx" hidden onchange="window.f1WorkspaceInputFiles(this.files,\'DRAG_DROP\')">'+
      '<input id="workspaceFolderInput" type="file" webkitdirectory directory multiple hidden onchange="window.f1WorkspaceInputFiles(this.files,\'CARTELLA\')">'+
    '</div>'+
    '<div class="section-title" style="margin-top:12px"><h3 style="margin:0">Orari di distribuzione</h3><span class="muted">Modificabili per cliente e piattaforma</span></div><div class="publish-times">'+prefs+'</div>'+
    '<div class="section-title" style="margin-top:14px"><h3 style="margin:0">Come verranno distribuiti</h3><span class="muted">Le caption restano modificabili fino alla pubblicazione</span></div>'+
    '<div class="distribution-list">'+(cards||'<div class="publisher-empty">Nessun contenuto con piano di distribuzione. Carica un file da WhatsApp, cartella o trascinamento.</div>')+'</div>'+
  '</section>';
  await previewMedia();
};

window.f1WorkspaceSaveTime=async function(clientId,platform,value){
  const client=(clients||[]).find(function(x){return x.id===clientId});if(!client||!/^\d{2}:\d{2}$/.test(value))return;
  const prefs=clone(client.publishing_preferences||{}),current=prefs[platform]&&typeof prefs[platform]==="object"?prefs[platform]:{};
  prefs[platform]=Object.assign({},current,{time:value,enabled:true});prefs.timezone=client.timezone||"Europe/Rome";prefs.review_before_schedule=true;
  const r=await sb.from("f1_content_clients").update({publishing_preferences:prefs,updated_at:new Date().toISOString()}).eq("id",clientId);
  if(r.error)return alert(r.error.message);
  client.publishing_preferences=prefs;
  const affected=(items||[]).filter(function(x){return x.client_id===clientId&&x.distribution_plan&&x.distribution_plan.platforms&&x.distribution_plan.platforms[platform]});
  for(const item of affected){
    const plan=clone(item.distribution_plan);plan.platforms[platform].time=value;
    await updatePlan(item,plan);
  }
};
window.f1WorkspaceInputFiles=async function(fileList,source){
  const files=Array.from(fileList||[]);if(!files.length)return;
  await quickUploadFiles(files,source||"DRAG_DROP");
};
window.f1WorkspaceDrag=function(ev,on){ev.preventDefault();const z=document.getElementById("workspaceDropZone");if(z)z.classList.toggle("drag",!!on)};
window.f1WorkspaceDrop=async function(ev){ev.preventDefault();window.f1WorkspaceDrag(ev,false);await quickUploadFiles(Array.from(ev.dataTransfer&&ev.dataTransfer.files||[]),"DRAG_DROP")};

async function quickUploadFiles(files,source){
  const client=currentClient();if(!client)return alert("Seleziona prima un cliente.");
  if(!files.length)return;
  const root=document.getElementById("clientPublisherWorkspace");if(root)root.style.opacity=".65";
  let done=0;
  try{
    for(const file of files){
      const title=cleanTitle(file.name),category=classify(file.name),base=baseCaption(client,title,category,""),mime=file.type||"application/octet-stream";
      const plan=buildPlan(client,title,category,base,mime,source,null);
      const ins=await sb.from("f1_content_items").insert({
        owner_id:user.id,client_id:client.id,title:title,description:base,source_text:base,
        content_type:contentTypeFromMime(mime),source:source,status:"DA APPROVARE",priority:"NORMALE",
        campaign:category,tags:hashtags(client,category).map(function(x){return x.replace(/^#/,"")}),notes:"Piano di distribuzione automatico generato al caricamento.",distribution_plan:plan
      }).select().single();
      if(ins.error)throw ins.error;
      const safe=file.name.replace(/[^a-zA-Z0-9._-]+/g,"_"),path=user.id+"/"+client.id+"/"+ins.data.id+"/"+crypto.randomUUID()+"-"+safe;
      const up=await sb.storage.from("f1-content-media").upload(path,file,{contentType:mime,upsert:false});
      if(up.error){await sb.from("f1_content_items").delete().eq("id",ins.data.id);throw up.error}
      const mr=await sb.from("f1_content_media").insert({owner_id:user.id,content_id:ins.data.id,client_id:client.id,file_name:safe,mime_type:mime,storage_path:path,file_size:file.size,source:source});
      if(mr.error){try{await sb.storage.from("f1-content-media").remove([path])}catch(_){};await sb.from("f1_content_items").delete().eq("id",ins.data.id);throw mr.error}
      done++;
    }
    await loadAll();await renderAll();
    alert(done+" contenut"+(done===1?"o caricato":"i caricati")+" per "+client.name+". Piano social e caption pronti.");
  }catch(e){alert("Caricamento interrotto: "+(e.message||String(e)))}finally{if(root)root.style.opacity="1"}
}
window.f1WorkspaceSaveCaption=async function(itemId,platform,value){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  const plan=itemPlan(item,client);if(!plan.platforms[platform])return;
  plan.platforms[platform].caption=String(value||"");
  try{
    await updatePlan(item,plan);
    const rows=(calendar||[]).filter(function(x){return x.content_id===itemId&&x.platform===platform&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
    for(const row of rows){
      const meta=Object.assign({},row.platform_metadata||{},{caption:String(value||""),generated_caption:plan.platforms[platform].generated_caption||""});
      await sb.from("f1_content_calendar").update({platform_metadata:meta}).eq("id",row.id);
      row.platform_metadata=meta;
    }
  }catch(e){alert(e.message||String(e))}
};
window.f1WorkspaceRegenerate=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  const plan=itemPlan(item,client),category=plan.category||classify(item.title),generated=captionFor(client,item.title,category,baseCaption(client,item.title,category,item.source_text||""),platform);
  plan.platforms[platform].generated_caption=generated;plan.platforms[platform].caption=generated;
  await updatePlan(item,plan);await window.f1RenderClientPublisherWorkspace();
};
window.f1WorkspaceResetCaption=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  const plan=itemPlan(item,client);plan.platforms[platform].caption=plan.platforms[platform].generated_caption||"";
  await updatePlan(item,plan);await window.f1RenderClientPublisherWorkspace();
};
window.f1WorkspaceCopyCaption=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  const plan=itemPlan(item,client),value=(plan.platforms[platform]||{}).caption||"";
  try{await navigator.clipboard.writeText(value)}catch(_){prompt("Copia la caption:",value)}
};

async function scheduleOne(item,dayOffset){
  const client=(clients||[]).find(function(x){return x.id===item.client_id});if(!client)return 0;
  const plan=itemPlan(item,client),mime=itemMime(item);let scheduled=0;
  for(const p of WS_PLATFORMS){
    const data=plan.platforms[p.id]||{},ch=channelFor(client.id,p.id),state=planState(client.id,p.id,mime,item);
    const target=nextAt(data.time||prefFor(client,p.id).time,dayOffset||0);
    if(state==="MEDIA_MISSING"||state==="FORMATO_NON_SUPPORTATO"||state==="TIKTOK_PHOTO_URL_REQUIRED"||state==="TIKTOK_REVIEW_REQUIRED"){
      data.status=state;data.scheduled_at=null;plan.platforms[p.id]=data;continue;
    }
    const calendarStatus=state==="PRONTO"?"PROGRAMMATO":"CANALE_DA_COLLEGARE";
    const payload={
      owner_id:user.id,content_id:item.id,client_id:client.id,platform:p.id,publication_at:target.toISOString(),
      status:calendarStatus,provider:ch&&ch.provider||"oauth_broker",retry_count:0,error:null,
      platform_metadata:{
        caption:data.caption||"",generated_caption:data.generated_caption||"",source_upload:item.source||"WEB",
        auto_distribution:true,selected_time:data.time||prefFor(client,p.id).time,distribution_version:plan.version||1
      }
    };
    const existing=(calendar||[]).find(function(x){return x.content_id===item.id&&x.platform===p.id&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
    if(existing){
      const u=await sb.from("f1_content_calendar").update(payload).eq("id",existing.id);if(u.error)throw u.error;
    }else{
      const ins=await sb.from("f1_content_calendar").insert(payload);if(ins.error)throw ins.error;
    }
    data.status=calendarStatus;data.scheduled_at=target.toISOString();plan.platforms[p.id]=data;
    if(calendarStatus==="PROGRAMMATO")scheduled++;
  }
  await updatePlan(item,plan);
  const status=Object.values(plan.platforms).some(function(x){return x.scheduled_at})?"PROGRAMMATO":"DA APPROVARE";
  const u=await sb.from("f1_content_items").update({status:status}).eq("id",item.id);if(u.error)throw u.error;
  item.status=status;
  return scheduled;
}
window.f1WorkspaceScheduleItem=async function(itemId){
  const item=(items||[]).find(function(x){return x.id===itemId});if(!item)return;
  const client=(clients||[]).find(function(x){return x.id===item.client_id});
  try{
    if(client&&!client.auto_publish){
      const u=await sb.from("f1_content_clients").update({auto_publish:true,automation_status:"AUTOMAZIONE ATTIVA"}).eq("id",client.id);if(u.error)throw u.error;
      client.auto_publish=true;
    }
    const count=await scheduleOne(item,0);await loadAll();await renderAll();
    alert("Piano creato. "+count+" canali già collegati sono pronti alla pubblicazione; gli altri restano in attesa del collegamento.");
  }catch(e){alert(e.message||String(e))}
};
window.f1WorkspaceProgramAll=async function(){
  const client=currentClient();if(!client)return;
  const list=planItemsForClient(client).filter(function(x){return !/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
  if(!list.length)return alert("Non ci sono nuovi contenuti da programmare.");
  try{
    const u=await sb.from("f1_content_clients").update({auto_publish:true,automation_status:"AUTOMAZIONE ATTIVA"}).eq("id",client.id);if(u.error)throw u.error;
    client.auto_publish=true;
    let ready=0;
    const ordered=list.slice().reverse();
    for(let i=0;i<ordered.length;i++)ready+=await scheduleOne(ordered[i],i);
    await loadAll();await renderAll();
    alert("Programmazione completata per "+ordered.length+" contenuti. "+ready+" pubblicazioni sono su canali già collegati; i canali non collegati restano predisposti e separati.");
  }catch(e){alert("Programmazione non completata: "+(e.message||String(e)))}
};

function ensureWhatsAppModal(){
  let modal=document.getElementById("workspaceWaModal");if(modal)return modal;
  modal=document.createElement("div");modal.className="modal";modal.id="workspaceWaModal";
  modal.innerHTML='<div class="modal-card"><div class="section-title"><h2>Importa da WhatsApp</h2><button class="btn ghost small" onclick="document.getElementById(\'workspaceWaModal\').classList.remove(\'open\')">CHIUDI</button></div><div id="workspaceWaList" class="calendar-list"></div></div>';
  document.body.appendChild(modal);return modal;
}
window.f1WorkspaceOpenWhatsApp=async function(){
  const client=currentClient();if(!client)return;
  const modal=ensureWhatsAppModal(),list=document.getElementById("workspaceWaList");list.innerHTML='<div class="empty">Caricamento...</div>';modal.classList.add("open");
  const r=await sb.from("f1_whatsapp_logs").select("id,message_id,message_type,message_text,media_count,result,created_at").eq("client_id",client.id).order("created_at",{ascending:false}).limit(30);
  if(r.error){list.innerHTML='<div class="notice error">'+h(r.error.message)+'</div>';return}
  list.innerHTML=(r.data||[]).map(function(x){
    return '<div class="lineitem"><b>'+h(new Date(x.created_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</b><div><b>'+h(x.message_type||"Messaggio")+'</b><div class="meta">'+h(x.message_text||"")+(x.media_count?' · '+x.media_count+' media':"")+'</div></div><button class="btn small primary" onclick="window.f1WorkspaceImportWhatsApp('+Number(x.id)+')">IMPORTA</button></div>';
  }).join("")||'<div class="publisher-empty">Nessun contenuto WhatsApp associato a '+h(client.name)+'. Quando arriveranno messaggi/media del cliente compariranno qui automaticamente.</div>';
};
window.f1WorkspaceImportWhatsApp=async function(logId){
  const client=currentClient();if(!client)return;
  try{
    const r=await sb.from("f1_whatsapp_logs").select("*").eq("id",logId).eq("client_id",client.id).single();if(r.error)throw r.error;
    const log=r.data,key=String(log.message_id||("wa-"+log.id));
    const exists=await sb.from("f1_content_items").select("id").eq("client_id",client.id).eq("whatsapp_thread_key",key).limit(1);
    if(exists.data&&exists.data.length)return alert("Questo contenuto WhatsApp è già stato importato.");
    const title="WhatsApp · "+new Date(log.created_at).toLocaleDateString("it-IT"),category=classify(log.message_text||""),base=baseCaption(client,title,category,log.message_text||"");
    const mediaSource=await sb.from("f1_content_media").select("*").eq("client_id",client.id).eq("whatsapp_message_id",log.message_id||"");
    const first=(mediaSource.data||[])[0],mime=first&&first.mime_type||"";
    const plan=buildPlan(client,title,category,base,mime,"WHATSAPP",null);
    const ins=await sb.from("f1_content_items").insert({owner_id:user.id,client_id:client.id,title:title,description:base,source_text:base,content_type:mime?contentTypeFromMime(mime):"TESTO",source:"WHATSAPP",status:"DA APPROVARE",campaign:category,tags:hashtags(client,category).map(function(x){return x.replace(/^#/,"")}),notes:"Importato dal registro WhatsApp.",whatsapp_thread_key:key,distribution_plan:plan}).select().single();
    if(ins.error)throw ins.error;
    for(const m of (mediaSource.data||[])){
      const cp=await sb.from("f1_content_media").insert({owner_id:user.id,content_id:ins.data.id,client_id:client.id,file_name:m.file_name,mime_type:m.mime_type,storage_path:m.storage_path,file_size:m.file_size,source:"WHATSAPP",whatsapp_message_id:m.whatsapp_message_id});
      if(cp.error)throw cp.error;
    }
    document.getElementById("workspaceWaModal").classList.remove("open");await loadAll();await renderAll();
    alert("Contenuto WhatsApp importato e piano social generato.");
  }catch(e){alert(e.message||String(e))}
};

if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){if(window.f1RenderClientPublisherWorkspace)window.f1RenderClientPublisherWorkspace()});
else if(window.f1RenderClientPublisherWorkspace)window.f1RenderClientPublisherWorkspace();
})();