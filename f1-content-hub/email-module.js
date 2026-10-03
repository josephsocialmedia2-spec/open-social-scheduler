(function(){
"use strict";

const EMAIL_FUNCTION_URL=SUPABASE_URL+"/functions/v1/f1-client-email";
const EMAIL_BUCKET="f1-content-media";
const E={
  clientId:"",
  data:null,
  view:"overview",
  loading:false,
  notice:"",
  noticeType:"",
  device:null,
  devicePollTimer:null,
  selectedCampaignId:"",
  selectedTemplateId:"",
  parsedRows:[],
  parsedFileName:"",
  recipients:null,
  sendLoop:false
};

function eh(v){return String(v==null?"":v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]))}
function efmt(v){if(!v)return "—";try{return new Date(v).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"})}catch{return String(v)}}
function enumv(v){return String(v||"").replaceAll("_"," ")}
function eclient(){return (clients||[]).find(x=>x.id===selectedClientId)||null}
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
function statusClass(v){const s=String(v||"");if(["COLLEGATO","ATTIVA","APPROVATA","TESTATO","APPROVATA","completed","sent"].includes(s))return"ok";if(["ERRORE","ACCOUNT_DIVERSO","TOKEN_SCADUTO","RICONNETTERE","failed"].includes(s))return"bad";return"warn"}
function notice(text,type){E.notice=String(text||"");E.noticeType=type||"";renderNotice()}
function renderNotice(){const host=document.getElementById("emailNotice");if(!host)return;host.innerHTML=E.notice?'<div class="email-inline-note '+(E.noticeType||"")+'">'+eh(E.notice)+'</div>':""}
function currentAccount(){
  const rows=E.data?.accounts||[];
  const remembered=sessionStorage.getItem("f1-email-account-"+E.clientId);
  return rows.find(x=>x.id===remembered)||rows[0]||null;
}
function currentCampaign(){
  const rows=E.data?.campaigns||[];
  return rows.find(x=>x.id===E.selectedCampaignId)||rows[0]||null;
}
function campaignOptions(selected){
  return (E.data?.campaigns||[]).map(c=>'<option value="'+c.id+'" '+(c.id===selected?"selected":"")+'>'+eh(c.name)+' · '+eh(enumv(c.approval_state||c.status))+'</option>').join("");
}
function graphicOptions(selected){
  return '<option value="">Grafica attiva della settimana</option>'+(E.data?.graphics||[]).map(g=>'<option value="'+g.id+'" '+(g.id===selected?"selected":"")+'>'+g.iso_year+' · W'+String(g.iso_week).padStart(2,"0")+' · v'+g.version+' · '+eh(g.file_name)+'</option>').join("");
}
function accountOptions(selected){
  return (E.data?.accounts||[]).map(a=>'<option value="'+a.id+'" '+(a.id===selected?"selected":"")+'>'+eh(a.sender_name||a.email_address)+' · '+eh(a.email_address)+'</option>').join("");
}
function templateOptions(selected){
  return '<option value="">Nessun template</option>'+(E.data?.templates||[]).map(t=>'<option value="'+t.id+'" '+(t.id===selected?"selected":"")+'>'+eh(t.name)+'</option>').join("");
}
function selectedCampaignId(){
  const c=currentCampaign();return c?.id||"";
}
function activeGraphic(){
  const cur=E.data?.current_week||{};
  return (E.data?.graphics||[]).find(g=>g.status==="ATTIVA")||
         (E.data?.graphics||[]).find(g=>g.iso_year===cur.year&&g.iso_week===cur.week&&["PROGRAMMATA","APPROVATA"].includes(g.status))||null;
}
function nextGraphic(){
  const cur=E.data?.current_week||{};
  const key=(g)=>(Number(g.iso_year)*100+Number(g.iso_week));
  const now=Number(cur.year||0)*100+Number(cur.week||0);
  return (E.data?.graphics||[]).filter(g=>key(g)>now&&["PROGRAMMATA","APPROVATA"].includes(g.status)).sort((a,b)=>key(a)-key(b))[0]||null;
}
async function eapi(action,payload){
  const s=await sb.auth.getSession();
  const token=s?.data?.session?.access_token;
  if(!token)throw new Error("Sessione scaduta: accedi di nuovo.");
  const r=await fetch(EMAIL_FUNCTION_URL,{
    method:"POST",
    headers:{apikey:SUPABASE_KEY,Authorization:"Bearer "+token,"Content-Type":"application/json"},
    body:JSON.stringify({action,...(payload||{})})
  });
  const data=await r.json().catch(()=>({}));
  if(!r.ok||data?.ok===false)throw new Error(data?.error||data?.message||("Errore EMAIL "+r.status));
  return data;
}
async function load(force){
  const c=eclient();
  if(!c){E.clientId="";E.data=null;return}
  if(!force&&E.data&&E.clientId===c.id)return;
  E.clientId=c.id;E.loading=true;
  try{
    E.data=await eapi("STATUS",{client_id:c.id});
    if(!E.selectedCampaignId&&E.data.campaigns?.length)E.selectedCampaignId=E.data.campaigns[0].id;
  }finally{E.loading=false}
}
function metric(label,value,caption){return '<div class="email-metric"><b>'+eh(value)+'</b><span>'+eh(label)+'</span>'+(caption?'<div class="email-help">'+eh(caption)+'</div>':'')+'</div>'}
function navButton(id,label){return '<button class="'+(E.view===id?"active":"")+'" onclick="window.f1EmailSetView(\''+id+'\')">'+label+'</button>'}
function renderFrame(){
  const root=document.getElementById("emailWorkspace");if(!root)return;
  const c=eclient();
  if(!c){root.innerHTML='<div class="panel"><div class="email-empty">Seleziona prima un cliente dalla dashboard.</div></div>';return}
  if(E.loading&&!E.data){root.innerHTML='<div class="panel"><div class="email-empty"><span class="email-spin"></span> Caricamento modulo EMAIL…</div></div>';return}
  if(!E.data){root.innerHTML='<div class="panel"><div class="email-inline-note bad">Il modulo EMAIL non è disponibile.</div></div>';return}
  const a=currentAccount(),g=activeGraphic(),campaigns=E.data.campaigns||[];
  const sent=campaigns.reduce((n,x)=>n+Number(x.sent_count||0),0);
  root.innerHTML='<div class="email-shell">'+
    '<div class="email-head"><div><div class="brand"><small>F1 SOCIAL · CLIENTE</small>EMAIL</div><h2>'+eh(c.name)+'</h2><div class="email-subtitle">Account, grafiche settimanali, campagne e invii dello stesso cliente.</div></div>'+
      '<div class="email-actions"><button class="btn small ghost" onclick="window.f1EmailRefresh()">AGGIORNA</button><button class="btn small danger" onclick="setTab(\'dashboard\')">CHIUDI EMAIL</button></div></div>'+
    '<div id="emailNotice"></div>'+
    '<div class="email-metrics">'+
      metric("ACCOUNT",a?enumv(a.connection_status):"NON CONFIGURATO",a?.email_address||"")+
      metric("GRAFICA SETTIMANA",g?"W"+String(g.iso_week).padStart(2,"0"):"NESSUNA",g?.file_name||"")+
      metric("CAMPAGNE",campaigns.length,"storico del cliente")+
      metric("INVIATE",sent,"totale registrato")+
    '</div>'+
    '<div class="email-nav">'+
      navButton("overview","PANORAMICA")+navButton("account","ACCOUNT")+navButton("campaigns","CAMPAGNE")+navButton("database","DATABASE")+
      navButton("graphics","GRAFICHE")+navButton("templates","TEMPLATE")+navButton("attachments","ALLEGATI")+navButton("send","INVII")+navButton("stats","STATISTICHE")+navButton("logs","LOG")+
    '</div>'+
    '<div id="emailView"></div>'+
  '</div>';
  renderNotice();renderView();
}
function renderView(){
  const host=document.getElementById("emailView");if(!host||!E.data)return;
  const map={overview:renderOverview,account:renderAccount,campaigns:renderCampaigns,database:renderDatabase,graphics:renderGraphics,templates:renderTemplates,attachments:renderAttachments,send:renderSend,stats:renderStats,logs:renderLogs};
  (map[E.view]||renderOverview)(host);
}
function renderOverview(host){
  const a=currentAccount(),g=activeGraphic(),ng=nextGraphic(),c=currentCampaign();
  host.innerHTML='<div class="email-layout">'+
    '<div class="email-card"><h3>Stato operativo</h3>'+
      '<div class="email-stat-grid">'+
        '<div class="email-stat"><span class="email-status '+statusClass(a?.connection_status)+'">'+eh(enumv(a?.connection_status||"NON CONFIGURATO"))+'</span><b>'+eh(a?.email_address||"—")+'</b><div class="email-help">Mittente</div></div>'+
        '<div class="email-stat"><span class="email-status '+statusClass(g?.status)+'">'+eh(enumv(g?.status||"NESSUNA"))+'</span><b>'+(g?("W"+g.iso_week):"—")+'</b><div class="email-help">Grafica attiva</div></div>'+
        '<div class="email-stat"><span class="email-status '+statusClass(c?.approval_state)+'">'+eh(enumv(c?.approval_state||"NESSUNA"))+'</span><b>'+eh(c?.name||"—")+'</b><div class="email-help">Ultima campagna</div></div>'+
      '</div>'+
      '<div class="email-actions"><button class="btn primary" onclick="window.f1EmailSetView(\'account\')">CONFIGURA ACCOUNT</button><button class="btn ghost" onclick="window.f1EmailSetView(\'graphics\')">GRAFICA SETTIMANALE</button><button class="btn green" onclick="window.f1EmailSetView(\'campaigns\')">NUOVA CAMPAGNA</button></div>'+
    '</div>'+
    '<div class="email-card"><h3>Questa settimana</h3>'+
      (g?'<div><b>Grafica attiva</b><div class="email-help">'+eh(g.file_name)+' · '+g.iso_year+' W'+g.iso_week+' · v'+g.version+'</div></div>':'<div class="email-inline-note warn">Nessuna grafica attiva per la settimana corrente.</div>')+
      (ng?'<div style="margin-top:14px"><b>Prossima grafica</b><div class="email-help">'+eh(ng.file_name)+' · '+ng.iso_year+' W'+ng.iso_week+'</div></div>':'<div class="email-help" style="margin-top:14px">Nessuna prossima grafica programmata.</div>')+
    '</div>'+
  '</div>';
}
function renderAccount(host){
  const a=currentAccount();
  const provider=a?.provider||"microsoft",type=a?.microsoft_account_type||"personal";
  const cfg=E.data.provider_config||{};
  host.innerHTML='<div class="email-layout">'+
    '<div class="email-card"><h3>Account mittente</h3><div class="email-form">'+
      '<div class="email-field"><label>Nome mittente</label><input id="emailSenderName" value="'+eh(a?.sender_name||eclient()?.name||"")+'"></div>'+
      '<div class="email-field"><label>Email mittente</label><input id="emailSenderAddress" type="email" value="'+eh(a?.email_address||"")+'" placeholder="nome@outlook.it"></div>'+
      '<div class="email-field"><label>Provider</label><select id="emailProvider" onchange="window.f1EmailProviderChanged()"><option value="microsoft" '+(provider==="microsoft"?"selected":"")+'>Microsoft / Outlook</option><option value="gmail" '+(provider==="gmail"?"selected":"")+'>Gmail</option></select></div>'+
      '<div id="emailMicrosoftTypeField" class="email-field '+(provider==="microsoft"?"":"hidden")+'"><label>Tipo account Microsoft</label><select id="emailMicrosoftType" onchange="window.f1EmailProviderChanged()"><option value="personal" '+(type==="personal"?"selected":"")+'>Account personale Outlook/Hotmail</option><option value="organization" '+(type==="organization"?"selected":"")+'>Microsoft 365 / organizzazione</option></select></div>'+
      '<div id="emailTenantField" class="email-field wide '+(provider==="microsoft"&&type==="organization"?"":"hidden")+'"><label>Tenant ID</label><input id="emailTenantId" value="'+eh(type==="organization"?(a?.tenant_id||""):"")+'" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"><div class="email-help">Per Microsoft 365 aziendale. Gli account personali usano automaticamente <b>consumers</b>.</div></div>'+
      '<div id="emailConsumersInfo" class="email-inline-note wide '+(provider==="microsoft"&&type==="personal"?"":"hidden")+'">Account Microsoft personale: authority impostata automaticamente su <b>consumers</b>. Non serve inventare un Tenant ID.</div>'+
    '</div>'+
    '<div class="email-actions"><button class="btn primary" onclick="window.f1EmailSaveAccount()">SALVA CONFIGURAZIONE</button>'+
      (a?'<button class="btn green" onclick="window.f1EmailConnectAccount()">'+(provider==="gmail"?"COLLEGA GMAIL":"COLLEGA MICROSOFT")+'</button><button class="btn ghost" onclick="window.f1EmailDisconnect()">SCOLLEGA</button>':'')+
    '</div>'+
    (E.device?'<div class="email-code-box"><b>Autorizzazione Microsoft</b><div class="email-code">'+eh(E.device.user_code||"")+'</div><div class="email-help">'+eh(E.device.message||"Apri il sito Microsoft e inserisci il codice.")+'</div><div class="email-actions"><a class="btn primary" target="_blank" rel="noopener" href="'+eh(E.device.verification_uri||"#")+'">APRI MICROSOFT</a><span class="email-status warn"><span class="email-spin"></span> ATTESA AUTORIZZAZIONE</span></div></div>':'')+
    '</div>'+
    '<div class="email-card"><h3>Stato connessione</h3>'+
      '<div><span class="email-status '+statusClass(a?.connection_status)+'">'+eh(enumv(a?.connection_status||"NON CONFIGURATO"))+'</span></div>'+
      '<div class="email-help" style="margin-top:10px">Email prevista: '+eh(a?.email_address||"—")+'</div>'+
      '<div class="email-help">Email collegata: '+eh(a?.connected_email||"—")+'</div>'+
      '<div class="email-help">Ultimo collegamento: '+eh(efmt(a?.last_connected_at))+'</div>'+
      '<div class="email-help">Ultimo test: '+eh(efmt(a?.last_test_at))+'</div>'+
      '<div class="email-help" style="margin-top:12px">Microsoft central app: '+(cfg.microsoft?.configured?'<span class="email-status ok">CONFIGURATA</span>':'<span class="email-status bad">CLIENT ID MANCANTE</span>')+'</div>'+
      '<div class="email-help" style="margin-top:6px">Gmail OAuth: '+(cfg.gmail?.configured?'<span class="email-status ok">CONFIGURATO</span>':'<span class="email-status warn">DA CONFIGURARE QUANDO SERVE</span>')+'</div>'+
    '</div>'+
  '</div>';
}
function renderCampaigns(host){
  const c=currentCampaign(),a=currentAccount();
  if(c&&!E.selectedCampaignId)E.selectedCampaignId=c.id;
  host.innerHTML='<div class="email-layout">'+
    '<div class="email-card"><div class="email-head"><h3>Campagne</h3><button class="btn small green" onclick="window.f1EmailNewCampaign()">+ NUOVA</button></div>'+
      '<div class="email-campaigns">'+((E.data.campaigns||[]).map(x=>'<div class="email-campaign-row"><div><h4>'+eh(x.name)+'</h4><small>'+eh(x.subject)+' · '+efmt(x.created_at)+'</small></div><div><span class="email-status '+statusClass(x.approval_state||x.status)+'">'+eh(enumv(x.approval_state||x.status))+'</span> <button class="btn small ghost" onclick="window.f1EmailSelectCampaign(\''+x.id+'\')">APRI</button></div></div>').join("")||'<div class="email-empty">Nessuna campagna.</div>')+'</div>'+
    '</div>'+
    '<div class="email-card"><h3>'+(c?"Modifica campagna":"Nuova campagna")+'</h3>'+
      '<div class="email-form">'+
        '<div class="email-field wide"><label>Nome campagna</label><input id="emailCampaignName" value="'+eh(c?.name||"")+'" placeholder="Campagna settimana 41"></div>'+
        '<div class="email-field wide"><label>Mittente</label><select id="emailCampaignAccount">'+accountOptions(c?.email_account_id||a?.id||"")+'</select></div>'+
        '<div class="email-field wide"><label>Oggetto</label><input id="emailCampaignSubject" value="'+eh(c?.subject||"")+'" placeholder="Oggetto email"></div>'+
        '<div class="email-field"><label>Template</label><select id="emailCampaignTemplate" onchange="window.f1EmailApplyTemplate(this.value)">'+templateOptions(c?.template_id||"")+'</select></div>'+
        '<div class="email-field"><label>Grafica</label><select id="emailCampaignGraphic">'+graphicOptions(c?.graphic_id||"")+'</select></div>'+
        '<div class="email-field wide"><label>Contenuto email</label><textarea id="emailCampaignBody" placeholder="Scrivi qui il testo. Puoi usare {{NOME}}, {{AZIENDA}}, {{COMUNE}}.">'+eh(c?.html_content||"")+'</textarea><div class="email-help">Accetta testo semplice o HTML. Le variabili vengono sostituite per ogni destinatario.</div></div>'+
        '<div class="email-field"><label>CTA</label><input id="emailCampaignCta" value="'+eh(c?.metadata?.cta_text||"")+'" placeholder="SCOPRI DI PIÙ"></div>'+
        '<div class="email-field"><label>Link CTA</label><input id="emailCampaignCtaUrl" value="'+eh(c?.metadata?.cta_url||"")+'" placeholder="https://..."></div>'+
        '<div class="email-field"><label>Pausa base (secondi)</label><input id="emailDelay" type="number" min="1" max="120" value="'+eh(c?.delay_seconds||12)+'"></div>'+
        '<div class="email-field"><label>Jitter max (secondi)</label><input id="emailJitter" type="number" min="0" max="60" value="'+eh(c?.delay_jitter_seconds||5)+'"></div>'+
      '</div>'+
      '<div class="email-actions"><button class="btn primary" onclick="window.f1EmailSaveCampaign()">SALVA</button>'+
        (c?'<button class="btn ghost" onclick="window.f1EmailPreview()">ANTEPRIMA</button><button class="btn green" onclick="window.f1EmailSendTest()">INVIA TEST</button>':'')+
      '</div>'+
      (c?'<div style="margin-top:12px"><div class="email-form"><div class="email-field"><label>Email test</label><input id="emailTestAddress" type="email" value="'+eh(user?.email||"")+'"></div><div class="email-field"><label>Nome test</label><input id="emailTestName" value="Test"></div></div>'+
        '<div class="email-compliance" style="margin-top:10px"><input id="emailComplianceConfirm" type="checkbox"><span>Confermo che i destinatari della campagna hanno una base giuridica/consenso adeguato per questa comunicazione e che verranno rispettate disiscrizioni e soppressioni.</span></div>'+
        '<div class="email-actions"><button class="btn '+(c.test_sent_at?"primary":"ghost")+'" onclick="window.f1EmailApproveCampaign()">APPROVA CAMPAGNA</button></div>'+
        '<div class="email-help">Test: '+efmt(c.test_sent_at)+' · Approvata: '+efmt(c.approved_at)+'</div></div>':'')+
    '</div>'+
  '</div>'+
  '<div id="emailPreviewPanel" class="email-card hidden" style="margin-top:12px"><div class="email-head"><h3>Anteprima reale</h3><div class="email-actions" style="margin-top:0"><button id="emailPreviewDesktopBtn" class="btn small primary" onclick="window.f1EmailSetPreviewDevice(\'desktop\')">DESKTOP</button><button id="emailPreviewMobileBtn" class="btn small ghost" onclick="window.f1EmailSetPreviewDevice(\'mobile\')">MOBILE</button><button class="btn small ghost" onclick="document.getElementById(\'emailPreviewPanel\').classList.add(\'hidden\')">CHIUDI</button></div></div><div id="emailPreviewBox" class="email-preview desktop"><iframe id="emailPreviewFrame" sandbox=""></iframe></div></div>';
}
function renderDatabase(host){
  const cid=selectedCampaignId();
  host.innerHTML='<div class="email-layout">'+
    '<div class="email-card"><h3>Database destinatari</h3>'+
      '<div class="email-field"><label>Campagna</label><select id="emailDbCampaign" onchange="window.f1EmailDbCampaignChanged(this.value)"><option value="">Seleziona campagna</option>'+campaignOptions(cid)+'</select></div>'+
      '<div class="email-drop" style="margin-top:12px"><b>CARICA EXCEL O CSV</b><div class="email-help">Il file resta associato alla campagna selezionata. Email duplicate e non valide vengono escluse.</div><input id="emailDatabaseFile" type="file" accept=".xlsx,.xls,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" style="margin-top:10px" onchange="window.f1EmailParseDatabase(this.files[0])"></div>'+
      '<div id="emailDbPreview" style="margin-top:12px">'+renderParsedPreview()+'</div>'+
      '<div class="email-actions"><button class="btn primary" '+(!E.parsedRows.length||!cid?"disabled":"")+' onclick="window.f1EmailImportDatabase()">IMPORTA NELLA CAMPAGNA</button><button class="btn ghost" '+(!cid?"disabled":"")+' onclick="window.f1EmailLoadRecipients()">AGGIORNA ELENCO</button></div>'+
    '</div>'+
    '<div class="email-card"><h3>Destinatari campagna</h3><div id="emailRecipients">'+renderRecipients()+'</div></div>'+
  '</div>';
}
function renderGraphics(host){
  const cur=E.data.current_week||{},brand=E.data.brand_kit||{},graphics=E.data.graphics||[];
  host.innerHTML='<div class="email-card"><div class="email-head"><div><h3>Grafiche settimanali</h3><div class="email-subtitle">Le vecchie versioni restano nello storico e non vengono sovrascritte.</div></div><span class="email-status ok">SETTIMANA '+eh(cur.week)+' · '+eh(cur.year)+'</span></div>'+
    '<div class="email-form" style="margin-top:12px">'+
      '<div class="email-field wide"><label>File grafica</label><input id="emailGraphicFile" type="file" accept="image/png,image/jpeg,image/webp,image/gif"></div>'+
      '<div class="email-field"><label>Anno ISO</label><input id="emailGraphicYear" type="number" value="'+eh(cur.year||new Date().getFullYear())+'"></div>'+
      '<div class="email-field"><label>Settimana</label><input id="emailGraphicWeek" type="number" min="1" max="53" value="'+eh(cur.week||1)+'"></div>'+
      '<div class="email-field"><label>Stato iniziale</label><select id="emailGraphicStatus"><option>BOZZA</option><option>DA_APPROVARE</option><option>APPROVATA</option><option>PROGRAMMATA</option></select></div>'+
      '<div class="email-field"><label>Note</label><input id="emailGraphicNotes" placeholder="Tema / promozione"></div>'+
    '</div><div class="email-actions"><button class="btn green" onclick="window.f1EmailUploadGraphic()">CARICA GRAFICA</button></div>'+
    '<div class="email-graphics" style="margin-top:14px">'+(graphics.map(g=>'<div class="email-graphic '+(g.status==="ATTIVA"?"email-week-current":"")+'"><div class="email-graphic-preview" data-email-path="'+eh(g.storage_path)+'">CARICAMENTO…</div><div class="email-graphic-body"><h4>'+eh(g.file_name)+'</h4><div class="email-help">'+g.iso_year+' · W'+String(g.iso_week).padStart(2,"0")+' · versione '+g.version+'</div><div style="margin-top:7px"><span class="email-status '+statusClass(g.status)+'">'+eh(enumv(g.status))+'</span></div><div class="email-actions"><button class="btn small ghost" onclick="window.f1EmailGraphicStatus(\''+g.id+'\',\'APPROVATA\')">APPROVA</button><button class="btn small ghost" onclick="window.f1EmailGraphicStatus(\''+g.id+'\',\'PROGRAMMATA\')">PROGRAMMA</button><button class="btn small green" onclick="window.f1EmailGraphicStatus(\''+g.id+'\',\'ATTIVA\')">ATTIVA</button><button class="btn small danger" onclick="window.f1EmailGraphicStatus(\''+g.id+'\',\'ARCHIVIATA\')">ARCHIVIA</button></div></div></div>').join("")||'<div class="email-empty">Nessuna grafica caricata.</div>')+'</div>'+
  '</div>'+
  '<div class="email-card"><h3>Brand kit email</h3><div class="email-form">'+
    '<div class="email-field wide"><label>Logo email · PNG</label><div class="email-brand-logo" data-email-brand-logo="'+eh(brand.logo_storage_path||"")+'">'+(brand.logo_storage_path?"CARICAMENTO LOGO…":"NESSUN LOGO")+'</div><input id="emailBrandLogoFile" type="file" accept="image/png"></div>'+
    '<div class="email-field"><label>Colore primario</label><input id="emailBrandPrimary" type="color" value="'+eh(brand.primary_color||"#07111F")+'"></div>'+
    '<div class="email-field"><label>Colore CTA</label><input id="emailBrandSecondary" type="color" value="'+eh(brand.secondary_color||"#2D7FF9")+'"></div>'+
    '<div class="email-field"><label>Colore testo</label><input id="emailBrandText" type="color" value="'+eh(brand.text_color||"#142033")+'"></div>'+
    '<div class="email-field"><label>Font / fallback</label><input id="emailBrandFont" value="'+eh(brand.font_family||"Arial, Helvetica, sans-serif")+'"></div>'+
    '<div class="email-field"><label>Telefono</label><input id="emailBrandPhone" value="'+eh(brand.phone||"")+'"></div>'+
    '<div class="email-field"><label>Sito</label><input id="emailBrandWebsite" value="'+eh(brand.website||"")+'"></div>'+
    '<div class="email-field"><label>Facebook</label><input id="emailBrandFacebook" value="'+eh(brand.social_links?.facebook||"")+'" placeholder="https://..."></div>'+
    '<div class="email-field"><label>Instagram</label><input id="emailBrandInstagram" value="'+eh(brand.social_links?.instagram||"")+'" placeholder="https://..."></div>'+
    '<div class="email-field"><label>LinkedIn</label><input id="emailBrandLinkedin" value="'+eh(brand.social_links?.linkedin||"")+'" placeholder="https://..."></div>'+
    '<div class="email-field"><label>YouTube</label><input id="emailBrandYoutube" value="'+eh(brand.social_links?.youtube||"")+'" placeholder="https://..."></div>'+
    '<div class="email-field"><label>TikTok</label><input id="emailBrandTiktok" value="'+eh(brand.social_links?.tiktok||"")+'" placeholder="https://..."></div>'+
    '<div class="email-field"><label>CTA predefinita</label><input id="emailBrandCta" value="'+eh(brand.cta_text||"")+'"></div>'+
    '<div class="email-field"><label>Link CTA</label><input id="emailBrandCtaUrl" value="'+eh(brand.cta_url||"")+'"></div>'+
    '<div class="email-field wide"><label>Firma HTML</label><textarea id="emailBrandSignature">'+eh(brand.signature_html||"")+'</textarea></div>'+
  '</div><div class="email-actions"><button class="btn primary" onclick="window.f1EmailSaveBrand()">SALVA BRAND KIT</button></div></div>';
  hydrateGraphicPreviews();hydrateBrandLogoPreview();
}
function renderTemplates(host){
  const selected=(E.data.templates||[]).find(t=>t.id===E.selectedTemplateId)||null;
  host.innerHTML='<div class="email-layout"><div class="email-card"><div class="email-head"><h3>Template</h3><button class="btn small green" onclick="window.f1EmailNewTemplate()">+ NUOVO</button></div><div class="email-template-list">'+((E.data.templates||[]).map(t=>'<div class="email-template-item"><div><b>'+eh(t.name)+'</b><div class="email-help">'+eh(t.default_subject||"Senza oggetto")+'</div></div><button class="btn small ghost" onclick="window.f1EmailSelectTemplate(\''+t.id+'\')">MODIFICA</button></div>').join("")||'<div class="email-empty">Nessun template.</div>')+'</div></div>'+
    '<div class="email-card"><h3>'+(selected?"Modifica template":"Nuovo template")+'</h3><div class="email-form">'+
      '<div class="email-field wide"><label>Nome</label><input id="emailTemplateName" value="'+eh(selected?.name||"")+'"></div>'+
      '<div class="email-field wide"><label>Oggetto predefinito</label><input id="emailTemplateSubject" value="'+eh(selected?.default_subject||"")+'"></div>'+
      '<div class="email-field wide"><label>Header HTML</label><textarea id="emailTemplateHeader">'+eh(selected?.header_html||"")+'</textarea></div>'+
      '<div class="email-field wide"><label>Corpo HTML</label><textarea id="emailTemplateBody">'+eh(selected?.body_html||"")+'</textarea></div>'+
      '<div class="email-field wide"><label>Footer HTML</label><textarea id="emailTemplateFooter">'+eh(selected?.footer_html||"")+'</textarea></div>'+
    '</div><div class="email-actions"><button class="btn primary" onclick="window.f1EmailSaveTemplate()">SALVA TEMPLATE</button></div></div></div>';
}
function renderAttachments(host){
  const cid=selectedCampaignId();
  const files=(E.data.attachments||[]).filter(x=>x.campaign_id===cid);
  host.innerHTML='<div class="email-layout">'+
    '<div class="email-card"><h3>Allegati campagna</h3>'+
      '<div class="email-field"><label>Campagna</label><select id="emailAttachmentCampaign" onchange="window.f1EmailAttachmentCampaignChanged(this.value)"><option value="">Seleziona campagna</option>'+campaignOptions(cid)+'</select></div>'+
      '<div class="email-drop" style="margin-top:12px"><b>AGGIUNGI ALLEGATO</b><div class="email-help">PDF, documenti o immagini. Microsoft: totale allegati + grafica fino a circa 2,5 MB nel flusso diretto; Gmail fino a 18 MB.</div><input id="emailAttachmentFile" type="file" style="margin-top:10px"></div>'+
      '<div class="email-actions"><button class="btn green" '+(!cid?"disabled":"")+' onclick="window.f1EmailUploadAttachment()">CARICA ALLEGATO</button></div>'+
      '<div class="email-inline-note warn">Aggiungere o rimuovere un allegato invalida automaticamente TEST e APPROVAZIONE: la campagna va ricontrollata prima dell’invio.</div>'+
    '</div>'+
    '<div class="email-card"><h3>File associati</h3>'+
      (files.length?'<div class="email-template-list">'+files.map(x=>'<div class="email-template-item"><div><b>'+eh(x.file_name)+'</b><div class="email-help">'+eh(x.mime_type)+' · '+Math.max(1,Math.round(Number(x.file_size||0)/1024))+' KB · '+efmt(x.created_at)+'</div></div><button class="btn small danger" onclick="window.f1EmailDeleteAttachment(\''+x.id+'\')">RIMUOVI</button></div>').join("")+'</div>':'<div class="email-empty">Nessun allegato per questa campagna.</div>')+
    '</div>'+
  '</div>';
}
function renderSend(host){
  const c=currentCampaign();
  if(!c){host.innerHTML='<div class="email-card"><div class="email-empty">Crea prima una campagna.</div></div>';return}
  const total=Number(c.total_recipients||0),sent=Number(c.sent_count||0),pct=total?Math.round(sent/total*100):0;
  host.innerHTML='<div class="email-card"><div class="email-head"><div><h3>Invio campagna</h3><div class="email-subtitle">'+eh(c.name)+'</div></div><span class="email-status '+statusClass(c.status)+'">'+eh(enumv(c.status))+'</span></div>'+
    '<div class="email-field" style="margin-top:12px"><label>Campagna</label><select id="emailSendCampaign" onchange="window.f1EmailSendCampaignChanged(this.value)">'+campaignOptions(c.id)+'</select></div>'+
    '<div class="email-stat-grid" style="margin-top:12px"><div class="email-stat"><b>'+total+'</b><span>Totale</span></div><div class="email-stat"><b>'+sent+'</b><span>Inviate</span></div><div class="email-stat"><b>'+Number(c.excluded_count||0)+'</b><span>Escluse</span></div></div>'+
    '<div class="email-progress"><i style="width:'+pct+'%"></i></div><div class="email-help">'+pct+'% completato · test '+(c.test_sent_at?"OK":"MANCANTE")+' · approvazione '+(c.approved_at?"OK":"MANCANTE")+'</div>'+
    '<div class="email-actions"><button class="btn green" onclick="window.f1EmailStartSend()">AVVIA / RIPRENDI INVIO</button><button class="btn danger" onclick="window.f1EmailStopSend()">FERMA INVIO</button><button class="btn ghost" onclick="window.f1EmailLoadRecipients()">DETTAGLI DESTINATARI</button></div>'+
    '<div id="emailSendLive" style="margin-top:10px"></div>'+
  '</div><div class="email-card" style="margin-top:12px"><h3>Ultimi destinatari</h3>'+renderRecipients(100)+'</div>';
}
function renderStats(host){
  const rows=E.data.campaigns||[];
  const totals=rows.reduce((a,c)=>{a.total+=Number(c.total_recipients||0);a.sent+=Number(c.sent_count||0);a.bounce+=Number(c.bounce_count||0);a.open+=Number(c.open_count||0);a.click+=Number(c.click_count||0);a.unsub+=Number(c.unsubscribe_count||0);return a},{total:0,sent:0,bounce:0,open:0,click:0,unsub:0});
  host.innerHTML='<div class="email-card"><h3>Statistiche email del cliente</h3><div class="email-stat-grid">'+
    '<div class="email-stat"><b>'+totals.total+'</b><span>Destinatari</span></div><div class="email-stat"><b>'+totals.sent+'</b><span>Inviate</span></div><div class="email-stat"><b>'+totals.bounce+'</b><span>Bounce</span></div><div class="email-stat"><b>'+totals.open+'</b><span>Aperture registrate</span></div><div class="email-stat"><b>'+totals.click+'</b><span>Click registrati</span></div><div class="email-stat"><b>'+totals.unsub+'</b><span>Disiscrizioni</span></div>'+
  '</div><div class="email-help" style="margin-top:12px">Le metriche vengono mostrate solo quando registrate dal motore; nessun dato viene stimato.</div></div>';
}
function renderLogs(host){
  const rows=E.data.events||[];
  host.innerHTML='<div class="email-card"><h3>Log EMAIL</h3><div class="email-log">'+(rows.map(x=>'<div class="email-log-row"><b>'+eh(enumv(x.event_type))+'</b><span>'+eh(efmt(x.created_at))+'</span><span>'+eh(JSON.stringify(x.detail||{}).slice(0,700))+'</span></div>').join("")||'<div class="email-empty">Nessun evento.</div>')+'</div></div>';
}
function renderParsedPreview(){
  if(!E.parsedRows.length)return '<div class="email-help">Nessun file analizzato.</div>';
  const sample=E.parsedRows.slice(0,8);
  return '<div class="email-inline-note">'+E.parsedRows.length+' righe valide lette da '+eh(E.parsedFileName)+'</div><div style="overflow:auto"><table class="email-recipient-table"><thead><tr><th>Email</th><th>Nome</th><th>Azienda</th><th>Comune</th></tr></thead><tbody>'+sample.map(r=>'<tr><td>'+eh(r.email||"")+'</td><td>'+eh(r.first_name||r.NOME||r.nome||"")+'</td><td>'+eh(r.AZIENDA||r.azienda||"")+'</td><td>'+eh(r.COMUNE||r.comune||"")+'</td></tr>').join("")+'</tbody></table></div>';
}
function renderRecipients(limit){
  const rows=(E.recipients?.recipients||[]).slice(0,limit||50),stats=E.recipients?.stats;
  if(!E.recipients)return '<div class="email-help">Premi AGGIORNA ELENCO per vedere i destinatari.</div>';
  return (stats?'<div class="email-help" style="margin-bottom:8px">Totale '+stats.total+' · inviate '+stats.sent+' · rimanenti '+stats.remaining+' · errori '+stats.failed+' · escluse '+stats.suppressed+'</div>':'')+
    '<div style="overflow:auto"><table class="email-recipient-table"><thead><tr><th>Email</th><th>Stato</th><th>Invio</th><th>Errore</th></tr></thead><tbody>'+
    (rows.map(r=>'<tr><td>'+eh(r.email)+'</td><td><span class="email-status '+statusClass(r.status)+'">'+eh(enumv(r.status))+'</span></td><td>'+eh(efmt(r.sent_at))+'</td><td>'+eh(r.error||"")+'</td></tr>').join("")||'<tr><td colspan="4">Nessun destinatario.</td></tr>')+
    '</tbody></table></div>';
}

window.f1RenderEmailWorkspace=async function(force){
  const root=document.getElementById("emailWorkspace");if(!root)return;
  const c=eclient();if(!c){renderFrame();return}
  if(E.clientId!==c.id){E.data=null;E.recipients=null;E.parsedRows=[];E.selectedCampaignId="";E.device=null}
  E.loading=true;renderFrame();
  try{await load(!!force)}
  catch(e){notice(e.message||String(e),"bad")}
  finally{E.loading=false;renderFrame()}
};
window.f1EmailRefresh=async function(){E.data=null;await window.f1RenderEmailWorkspace(true);notice("Dati EMAIL aggiornati.","")};
window.f1EmailSetView=function(v){E.view=v;renderFrame()};
window.f1EmailProviderChanged=function(){
  const p=document.getElementById("emailProvider")?.value||"microsoft",t=document.getElementById("emailMicrosoftType")?.value||"personal";
  document.getElementById("emailMicrosoftTypeField")?.classList.toggle("hidden",p!=="microsoft");
  document.getElementById("emailTenantField")?.classList.toggle("hidden",!(p==="microsoft"&&t==="organization"));
  document.getElementById("emailConsumersInfo")?.classList.toggle("hidden",!(p==="microsoft"&&t==="personal"));
};
window.f1EmailSaveAccount=async function(){
  try{
    const old=currentAccount(),provider=document.getElementById("emailProvider").value;
    const data=await eapi("SAVE_ACCOUNT",{client_id:E.clientId,account_id:old?.id||null,sender_name:document.getElementById("emailSenderName").value,email_address:document.getElementById("emailSenderAddress").value,provider,microsoft_account_type:provider==="microsoft"?document.getElementById("emailMicrosoftType").value:null,tenant_id:document.getElementById("emailTenantId")?.value||null});
    sessionStorage.setItem("f1-email-account-"+E.clientId,data.account.id);E.data=null;await window.f1RenderEmailWorkspace(true);notice("Configurazione account salvata. Ora puoi collegarlo.","");
  }catch(e){notice(e.message||String(e),"bad")}
};
window.f1EmailConnectAccount=async function(){
  const a=currentAccount();if(!a)return notice("Salva prima l'account.","warn");
  try{
    if(a.provider==="gmail"){
      const d=await eapi("GMAIL_AUTHORIZE",{account_id:a.id});location.href=d.authorization_url;return;
    }
    const d=await eapi("MS_DEVICE_START",{account_id:a.id});E.device=d;renderFrame();
    try{window.open(d.verification_uri,"_blank","noopener")}catch(_){}
    clearInterval(E.devicePollTimer);
    E.devicePollTimer=setInterval(()=>window.f1EmailPollMicrosoft(),Math.max(3,Number(d.interval||5))*1000);
    notice("Inserisci il codice Microsoft mostrato. Il collegamento verrà rilevato automaticamente.","");
  }catch(e){notice(e.message||String(e),"bad")}
};
window.f1EmailPollMicrosoft=async function(){
  const a=currentAccount();if(!a||!E.device)return;
  try{
    const d=await eapi("MS_DEVICE_POLL",{account_id:a.id});
    if(d.pending)return;
    clearInterval(E.devicePollTimer);E.devicePollTimer=null;E.device=null;
    if(d.mismatch){notice("Hai autorizzato "+d.connected+" ma il cliente prevede "+d.expected+". Collegamento bloccato.","bad")}
    else{E.data=null;await window.f1RenderEmailWorkspace(true);notice("Account Microsoft collegato correttamente.","")}
  }catch(e){
    if(/pending|in corso/i.test(e.message))return;
    clearInterval(E.devicePollTimer);E.devicePollTimer=null;notice(e.message||String(e),"bad")
  }
};
window.f1EmailDisconnect=async function(){const a=currentAccount();if(!a)return;if(!confirm("Scollegare questo account email?"))return;try{await eapi("DISCONNECT",{account_id:a.id});E.data=null;await window.f1RenderEmailWorkspace(true);notice("Account scollegato.","warn")}catch(e){notice(e.message||String(e),"bad")}};

window.f1EmailSaveBrand=async function(){
  let uploadedLogoPath="";
  try{
    const current=E.data?.brand_kit||{};
    let logoPath=current.logo_storage_path||null;
    const logoFile=document.getElementById("emailBrandLogoFile")?.files?.[0]||null;
    if(logoFile){
      if(logoFile.type!=="image/png"&&!/\.png$/i.test(logoFile.name))throw new Error("Il logo email deve essere PNG.");
      if(logoFile.size>1000000)throw new Error("Logo troppo grande: massimo 1 MB.");
      uploadedLogoPath=user.id+"/"+E.clientId+"/email/brand/"+crypto.randomUUID()+"-logo.png";
      const up=await sb.storage.from(EMAIL_BUCKET).upload(uploadedLogoPath,logoFile,{contentType:"image/png",upsert:false});
      if(up.error)throw up.error;
      logoPath=uploadedLogoPath;
    }
    const social_links={
      facebook:document.getElementById("emailBrandFacebook").value.trim(),
      instagram:document.getElementById("emailBrandInstagram").value.trim(),
      linkedin:document.getElementById("emailBrandLinkedin").value.trim(),
      youtube:document.getElementById("emailBrandYoutube").value.trim(),
      tiktok:document.getElementById("emailBrandTiktok").value.trim()
    };
    await eapi("SAVE_BRAND",{client_id:E.clientId,logo_storage_path:logoPath,primary_color:document.getElementById("emailBrandPrimary").value,secondary_color:document.getElementById("emailBrandSecondary").value,text_color:document.getElementById("emailBrandText").value,font_family:document.getElementById("emailBrandFont").value,phone:document.getElementById("emailBrandPhone").value,website:document.getElementById("emailBrandWebsite").value,social_links,cta_text:document.getElementById("emailBrandCta").value,cta_url:document.getElementById("emailBrandCtaUrl").value,signature_html:document.getElementById("emailBrandSignature").value});
    E.data=null;await window.f1RenderEmailWorkspace(true);E.view="graphics";renderFrame();notice("Brand kit email salvato.","");
  }catch(e){
    if(uploadedLogoPath)await sb.storage.from(EMAIL_BUCKET).remove([uploadedLogoPath]);
    notice(e.message||String(e),"bad")
  }
};
function safeName(name){return String(name||"grafica").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^A-Za-z0-9._-]+/g,"-").replace(/^-+|-+$/g,"").slice(0,160)||"grafica"}
window.f1EmailUploadGraphic=async function(){
  const file=document.getElementById("emailGraphicFile")?.files?.[0];if(!file)return notice("Seleziona una grafica.","warn");
  try{
    const year=Number(document.getElementById("emailGraphicYear").value),week=Number(document.getElementById("emailGraphicWeek").value);
    const path=user.id+"/"+E.clientId+"/email/graphics/"+year+"-W"+String(week).padStart(2,"0")+"/"+crypto.randomUUID()+"-"+safeName(file.name);
    const up=await sb.storage.from(EMAIL_BUCKET).upload(path,file,{contentType:file.type||"application/octet-stream",upsert:false});if(up.error)throw up.error;
    try{
      await eapi("REGISTER_GRAPHIC",{client_id:E.clientId,storage_path:path,file_name:file.name,mime_type:file.type,file_size:file.size,iso_year:year,iso_week:week,status:document.getElementById("emailGraphicStatus").value,notes:document.getElementById("emailGraphicNotes").value});
    }catch(e){await sb.storage.from(EMAIL_BUCKET).remove([path]);throw e}
    E.data=null;await window.f1RenderEmailWorkspace(true);E.view="graphics";renderFrame();notice("Grafica caricata. Puoi approvarla, programmarla o renderla attiva.","");
  }catch(e){notice(e.message||String(e),"bad")}
};
window.f1EmailGraphicStatus=async function(id,status){try{await eapi("GRAPHIC_STATUS",{graphic_id:id,status});E.data=null;await window.f1RenderEmailWorkspace(true);E.view="graphics";renderFrame();notice("Grafica aggiornata: "+enumv(status)+".","")}catch(e){notice(e.message||String(e),"bad")}};
async function hydrateGraphicPreviews(){
  const boxes=[...document.querySelectorAll("[data-email-path]")];
  for(const box of boxes){
    const path=box.dataset.emailPath;if(!path)continue;
    const r=await sb.storage.from(EMAIL_BUCKET).createSignedUrl(path,1800);
    if(r.error||!r.data?.signedUrl){box.textContent="ANTEPRIMA NON DISPONIBILE";continue}
    box.innerHTML='<img loading="lazy" src="'+eh(r.data.signedUrl)+'" alt="">';
  }
}
async function hydrateBrandLogoPreview(){
  const box=document.querySelector("[data-email-brand-logo]");if(!box)return;
  const path=box.dataset.emailBrandLogo;if(!path){box.textContent="NESSUN LOGO";return}
  const r=await sb.storage.from(EMAIL_BUCKET).createSignedUrl(path,1800);
  if(r.error||!r.data?.signedUrl){box.textContent="ANTEPRIMA LOGO NON DISPONIBILE";return}
  box.innerHTML='<img loading="lazy" src="'+eh(r.data.signedUrl)+'" alt="Logo">';
}

function bodyToHtml(raw){
  const s=String(raw||"").trim();if(!s)return"";
  if(/<([a-z][\s\S]*?)>/i.test(s))return s;
  return s.split(/\n{2,}/).map(p=>'<p>'+eh(p).replace(/\n/g,"<br>")+'</p>').join("");
}
window.f1EmailNewCampaign=function(){E.selectedCampaignId="";E.view="campaigns";renderFrame()};
window.f1EmailSelectCampaign=function(id){E.selectedCampaignId=id;E.recipients=null;E.view="campaigns";renderFrame()};
window.f1EmailSaveCampaign=async function(){
  try{
    const c=currentCampaign(),accountId=document.getElementById("emailCampaignAccount")?.value;if(!accountId)throw new Error("Configura prima un account mittente.");
    const d=await eapi("SAVE_CAMPAIGN",{campaign_id:E.selectedCampaignId||null,client_id:E.clientId,email_account_id:accountId,name:document.getElementById("emailCampaignName").value,subject:document.getElementById("emailCampaignSubject").value,template_id:document.getElementById("emailCampaignTemplate").value||null,graphic_id:document.getElementById("emailCampaignGraphic").value||null,html_content:bodyToHtml(document.getElementById("emailCampaignBody").value),text_content:document.getElementById("emailCampaignBody").value,cta_text:document.getElementById("emailCampaignCta").value,cta_url:document.getElementById("emailCampaignCtaUrl").value,delay_seconds:Number(document.getElementById("emailDelay").value||12),delay_jitter_seconds:Number(document.getElementById("emailJitter").value||5)});
    E.selectedCampaignId=d.campaign.id;E.data=null;await window.f1RenderEmailWorkspace(true);E.view="campaigns";renderFrame();notice(c?"Campagna aggiornata. Il test precedente è stato invalidato perché il contenuto può essere cambiato.":"Campagna creata.","");
    return d.campaign;
  }catch(e){notice(e.message||String(e),"bad");throw e}
};
async function ensureCampaign(){if(E.selectedCampaignId)return E.selectedCampaignId;const c=await window.f1EmailSaveCampaign();return c.id}
window.f1EmailSetPreviewDevice=function(mode){
  const box=document.getElementById("emailPreviewBox"),desktop=document.getElementById("emailPreviewDesktopBtn"),mobile=document.getElementById("emailPreviewMobileBtn");
  if(!box)return;
  const isMobile=mode==="mobile";
  box.classList.toggle("mobile",isMobile);box.classList.toggle("desktop",!isMobile);
  if(desktop)desktop.className="btn small "+(!isMobile?"primary":"ghost");
  if(mobile)mobile.className="btn small "+(isMobile?"primary":"ghost");
};
window.f1EmailPreview=async function(){try{const id=await ensureCampaign();const d=await eapi("PREVIEW",{campaign_id:id});const panel=document.getElementById("emailPreviewPanel"),frame=document.getElementById("emailPreviewFrame");if(panel&&frame){frame.srcdoc=d.html;panel.classList.remove("hidden");window.f1EmailSetPreviewDevice("desktop");panel.scrollIntoView({behavior:"smooth",block:"start"})}}catch(e){notice(e.message||String(e),"bad")}};
window.f1EmailSendTest=async function(){try{const id=await ensureCampaign(),email=document.getElementById("emailTestAddress")?.value||user.email,name=document.getElementById("emailTestName")?.value||"Test";if(!confirm("Inviare UNA email di test a "+email+"?"))return;const d=await eapi("SEND_TEST",{campaign_id:id,email,first_name:name});E.data=null;await window.f1RenderEmailWorkspace(true);E.view="campaigns";renderFrame();notice("TEST inviato tramite "+d.provider+". Verifica la casella prima di approvare.","")}catch(e){notice(e.message||String(e),"bad")}};
window.f1EmailApproveCampaign=async function(){try{const id=await ensureCampaign();if(!document.getElementById("emailComplianceConfirm")?.checked)throw new Error("Spunta la conferma sulla base giuridica/consenso.");if(!confirm("Approvare questa campagna per l'invio reale?"))return;await eapi("APPROVE",{campaign_id:id,confirm_compliance:true});E.data=null;await window.f1RenderEmailWorkspace(true);E.view="campaigns";renderFrame();notice("Campagna approvata. Ora può essere avviata dalla sezione INVII.","")}catch(e){notice(e.message||String(e),"bad")}};
window.f1EmailApplyTemplate=function(id){const t=(E.data.templates||[]).find(x=>x.id===id);if(!t)return;document.getElementById("emailCampaignSubject").value=t.default_subject||"";document.getElementById("emailCampaignBody").value=[t.header_html,t.body_html,t.footer_html].filter(Boolean).join("\n")};

window.f1EmailNewTemplate=function(){E.selectedTemplateId="";renderFrame()};
window.f1EmailSelectTemplate=function(id){E.selectedTemplateId=id;renderFrame()};
window.f1EmailSaveTemplate=async function(){try{const d=await eapi("SAVE_TEMPLATE",{template_id:E.selectedTemplateId||null,client_id:E.clientId,name:document.getElementById("emailTemplateName").value,default_subject:document.getElementById("emailTemplateSubject").value,header_html:document.getElementById("emailTemplateHeader").value,body_html:document.getElementById("emailTemplateBody").value,footer_html:document.getElementById("emailTemplateFooter").value,active:true});E.selectedTemplateId=d.template.id;E.data=null;await window.f1RenderEmailWorkspace(true);E.view="templates";renderFrame();notice("Template salvato.","")}catch(e){notice(e.message||String(e),"bad")}};

function csvRows(text){
  const rows=[];let row=[],field="",quoted=false;
  for(let i=0;i<text.length;i++){
    const ch=text[i];
    if(quoted){
      if(ch==='"'&&text[i+1]==='"'){field+='"';i++}
      else if(ch==='"')quoted=false;
      else field+=ch;
    }else{
      if(ch==='"')quoted=true;
      else if(ch===","||ch===";"||ch==="\t"){row.push(field);field=""}
      else if(ch==="\n"){row.push(field);rows.push(row);row=[];field=""}
      else if(ch!=="\r")field+=ch;
    }
  }
  if(field||row.length){row.push(field);rows.push(row)}
  return rows.filter(r=>r.some(x=>String(x).trim()!==""));
}
function rowsToObjects(matrix){
  if(!matrix.length)return[];
  const headers=matrix[0].map((h,i)=>String(h||("COLONNA_"+(i+1))).trim()||("COLONNA_"+(i+1)));
  return matrix.slice(1).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]==null?"":r[i]])));
}
function detectEmailKey(rows){
  const keys=Object.keys(rows[0]||{});
  return keys.find(k=>/^e[-_ ]?mail$/i.test(k))||keys.find(k=>/email|mail|posta/i.test(k))||"";
}
function normalizeImportedRows(rows){
  const key=detectEmailKey(rows);if(!key)throw new Error("Non trovo una colonna EMAIL nel file.");
  return rows.map(r=>({source:r,email:String(r[key]||"").trim()})).filter(x=>x.email).map(x=>({...x.source,email:x.email,first_name:x.source.first_name||x.source.nome||x.source.NOME||"",last_name:x.source.last_name||x.source.cognome||x.source.COGNOME||""}));
}
window.f1EmailParseDatabase=async function(file){
  if(!file)return;try{
    let rows=[];
    if(/\.csv$/i.test(file.name)||/text\/csv/i.test(file.type)){rows=rowsToObjects(csvRows(await file.text()))}
    else{
      if(!window.XLSX)throw new Error("Lettore Excel non caricato. Puoi usare CSV oppure aggiornare la pagina.");
      const wb=XLSX.read(await file.arrayBuffer(),{type:"array",cellDates:false});
      const ws=wb.Sheets[wb.SheetNames[0]];rows=XLSX.utils.sheet_to_json(ws,{defval:"",raw:false});
    }
    E.parsedRows=normalizeImportedRows(rows);E.parsedFileName=file.name;
    const box=document.getElementById("emailDbPreview");if(box)box.innerHTML=renderParsedPreview();
    notice("File analizzato: "+E.parsedRows.length+" righe con email.","");
  }catch(e){E.parsedRows=[];E.parsedFileName="";notice(e.message||String(e),"bad");const box=document.getElementById("emailDbPreview");if(box)box.innerHTML=renderParsedPreview()}
};
window.f1EmailDbCampaignChanged=function(id){E.selectedCampaignId=id;E.recipients=null;renderFrame()};
window.f1EmailImportDatabase=async function(){const id=selectedCampaignId();if(!id)return notice("Seleziona una campagna.","warn");if(!E.parsedRows.length)return notice("Carica prima un file.","warn");try{let imported=0,invalid=0,duplicates=0,suppressed=0;for(let i=0;i<E.parsedRows.length;i+=500){const d=await eapi("IMPORT_RECIPIENTS",{campaign_id:id,recipients:E.parsedRows.slice(i,i+500)});imported+=Number(d.imported||0);invalid+=Number(d.invalid||0);duplicates+=Number(d.duplicates||0);suppressed+=Number(d.suppressed||0)}E.data=null;await window.f1RenderEmailWorkspace(true);E.view="database";await window.f1EmailLoadRecipients();notice("Import completato: "+imported+" validi · "+invalid+" non validi · "+duplicates+" duplicati · "+suppressed+" soppressi.","")}catch(e){notice(e.message||String(e),"bad")}};
window.f1EmailLoadRecipients=async function(){const id=selectedCampaignId();if(!id)return;try{E.recipients=await eapi("RECIPIENTS",{campaign_id:id});renderFrame()}catch(e){notice(e.message||String(e),"bad")}};

window.f1EmailAttachmentCampaignChanged=function(id){E.selectedCampaignId=id;renderFrame()};
window.f1EmailUploadAttachment=async function(){
  const cid=selectedCampaignId(),file=document.getElementById("emailAttachmentFile")?.files?.[0];
  if(!cid)return notice("Seleziona una campagna.","warn");
  if(!file)return notice("Seleziona un file da allegare.","warn");
  if(file.size>18000000)return notice("Allegato troppo grande: massimo 18 MB.","bad");
  try{
    const path=user.id+"/"+E.clientId+"/email/attachments/"+cid+"/"+crypto.randomUUID()+"-"+safeName(file.name);
    const up=await sb.storage.from(EMAIL_BUCKET).upload(path,file,{contentType:file.type||"application/octet-stream",upsert:false});
    if(up.error)throw up.error;
    try{
      await eapi("REGISTER_ATTACHMENT",{campaign_id:cid,storage_path:path,file_name:file.name,mime_type:file.type||"application/octet-stream",file_size:file.size});
    }catch(e){await sb.storage.from(EMAIL_BUCKET).remove([path]);throw e}
    E.data=null;await window.f1RenderEmailWorkspace(true);E.view="attachments";renderFrame();notice("Allegato aggiunto. Ripeti TEST e APPROVAZIONE prima dell'invio.","warn");
  }catch(e){notice(e.message||String(e),"bad")}
};
window.f1EmailDeleteAttachment=async function(id){
  if(!confirm("Rimuovere questo allegato dalla campagna?"))return;
  try{await eapi("DELETE_ATTACHMENT",{attachment_id:id});E.data=null;await window.f1RenderEmailWorkspace(true);E.view="attachments";renderFrame();notice("Allegato rimosso. TEST e APPROVAZIONE sono stati invalidati.","warn")}
  catch(e){notice(e.message||String(e),"bad")}
};
window.f1EmailSendCampaignChanged=function(id){E.selectedCampaignId=id;E.recipients=null;renderFrame();window.f1EmailLoadRecipients()};
window.f1EmailStartSend=async function(){
  const c=currentCampaign();if(!c)return;
  if(!confirm("Stai per avviare/riprendere la campagna '"+c.name+"' con "+Number(c.total_recipients||0)+" destinatari registrati. Continuare?"))return;
  E.sendLoop=true;notice("Invio in corso. Puoi usare FERMA INVIO in qualsiasi momento.","");
  const live=()=>document.getElementById("emailSendLive");
  try{
    while(E.sendLoop){
      const d=await eapi("START_STEP",{campaign_id:c.id});
      if(live())live().innerHTML='<div class="email-inline-note">'+(d.completed?"Campagna completata.":"Invio in corso…")+' Inviate: '+Number(d.stats?.sent||0)+' / '+Number(d.stats?.total||0)+' · rimanenti '+Number(d.stats?.remaining||0)+'</div>';
      E.recipients={recipients:E.recipients?.recipients||[],stats:d.stats};
      if(d.throttled){E.sendLoop=false;notice("Provider temporaneamente limitato. Riprova tra "+Number(d.retry_after_seconds||60)+" secondi.","warn");break}
      if(d.completed){E.sendLoop=false;break}
      await sleep(1200);
    }
  }catch(e){E.sendLoop=false;notice(e.message||String(e),"bad")}
  E.data=null;await window.f1RenderEmailWorkspace(true);E.view="send";await window.f1EmailLoadRecipients();
  if(!E.sendLoop)notice("Stato invio aggiornato. Puoi riprendere senza reinviare i destinatari già completati.","");
};
window.f1EmailStopSend=async function(){const c=currentCampaign();if(!c)return;E.sendLoop=false;try{await eapi("STOP",{campaign_id:c.id});E.data=null;await window.f1RenderEmailWorkspace(true);E.view="send";renderFrame();notice("Invio fermato in sicurezza. Potrai riprenderlo dalla stessa campagna.","warn")}catch(e){notice(e.message||String(e),"bad")}};

const oauthParams=new URLSearchParams(location.search);
const emailOauth=oauthParams.get("email_oauth");
if(emailOauth){
  if(emailOauth==="connected"){E.notice="Account Gmail collegato correttamente.";E.noticeType=""}
  else if(emailOauth==="mismatch"){E.notice="È stato autorizzato un account Gmail diverso da quello previsto. Collegamento bloccato.";E.noticeType="bad"}
  else if(emailOauth==="denied"){E.notice="Autorizzazione Gmail annullata.";E.noticeType="warn"}
  else{E.notice="Il collegamento Gmail non è stato completato.";E.noticeType="bad"}
  const u=new URL(location.href);u.searchParams.delete("email_oauth");history.replaceState({},document.title,u.pathname+(u.searchParams.toString()?"?"+u.searchParams.toString():""));
}
setTimeout(function(){
  const p=new URLSearchParams(location.search);
  if(p.get("view")==="email"&&selectedClientId)window.f1RenderEmailWorkspace(true);
},250);
})();