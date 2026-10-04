(function(){
"use strict";
const A={};
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
A.client=()=>{try{return (clients||[]).find(c=>c.id===selectedClientId)||null}catch(_){return null}};
A.prompt=c=>{
 const meta=c.profile_metadata||{},services=meta.services||{};
 const description=meta.description||[c.category,c.territory].filter(Boolean).join(" · ")||"attività da descrivere";
 const activeServices=[];
 if(services.social)activeServices.push("social media");
 if(c.email_service_enabled||services.email)activeServices.push("email marketing");
 if(c.website||services.site)activeServices.push("sito web");
 if(services.adv)activeServices.push("advertising");
 if(!activeServices.length)activeServices.push(c.category||"servizi professionali");
 const website=c.website||"da definire";
 return [
  "CREA UN PIANO CONTENUTISTICO EMAIL COMPLETO DI 12 MESI PER:",
  "",
  "AZIENDA / PROFESSIONISTA:",
  c.name,
  "",
  "DESCRIZIONE:",
  description,
  "",
  "SETTORE:",
  c.business_sector||c.category||"da definire",
  "",
  "SERVIZI:",
  activeServices.join(", "),
  "",
  "SITO / LINK PRINCIPALE:",
  website,
  "",
  "OBIETTIVO:",
  "Mantenere il contatto con il database CRM, educare il potenziale cliente, creare fiducia e generare richieste di contatto o appuntamento coerenti con l'attività.",
  "",
  "FREQUENZA:",
  "1 email alla settimana per 12 mesi.",
  "",
  "PERIODO:",
  "da ottobre 2026 a settembre 2027.",
  "",
  "Crea una strategia annuale coerente e non ripetitiva. Alterna contenuti educativi, problema/soluzione, casi pratici, curiosità, autorevolezza, territorio, servizi, fiducia e conversione.",
  "Scrivi anche il contenuto completo di ogni email. Programma preferibilmente il giovedì alle 10:00; se un mese contiene 5 giovedì, crea 5 email.",
  "",
  "PER OGNI EMAIL GENERA:",
  "cliente, data_invio, ora_invio, mese, settimana, tema, obiettivo, oggetto_email, preheader, corpo_email completo, cta_testo, cta_url, segmento_crm, stato.",
  "",
  "Usa TUTTI_I_CONTATTI come segmento CRM salvo necessità diversa. Usa PROGRAMMATA come stato nel CSV.",
  "",
  "ALLA FINE CREA UN CSV UTF-8 IMPORTABILE IN F1 SOCIAL. L'HEADER DEVE ESSERE ESATTAMENTE:",
  "cliente,data_invio,ora_invio,mese,settimana,tema,obiettivo,oggetto_email,preheader,corpo_email,cta_testo,cta_url,segmento_crm,stato",
  "",
  "REGOLE CSV:",
  "- una riga = una email;",
  "- nessuna colonna extra;",
  "- campi testuali tra virgolette;",
  "- raddoppia le virgolette interne;",
  "- mantieni correttamente virgole e ritorni a capo dentro i campi quotati;",
  "- nel campo cliente scrivi sempre: "+c.name+";",
  "- usa il link "+website+" quando pertinente;",
  "- non inserire spiegazioni dentro il CSV.",
  "",
  "OUTPUT: prima una breve sintesi mensile, poi il CSV completo pronto per F1 Social."
 ].join("\n");
};
A.account=async cid=>{try{const r=await sb.from("f1_client_email_accounts").select("email_address,provider,connection_status,connected_email").eq("owner_id",user.id).eq("client_id",cid).order("created_at").limit(1);return r.data&&r.data[0]||null}catch(_){return null}};
A.crm=async cid=>{try{const ses=await sb.auth.getSession(),token=ses&&ses.data&&ses.data.session&&ses.data.session.access_token;if(!token)return null;const r=await fetch(SUPABASE_URL+"/functions/v1/f1-client-email",{method:"POST",headers:{apikey:SUPABASE_KEY,Authorization:"Bearer "+token,"Content-Type":"application/json"},body:JSON.stringify({action:"CRM_COUNT",client_id:cid})});const d=await r.json();if(!r.ok||d.ok===false)throw new Error(d.error||"CRM_COUNT");return Number(d.count||0)}catch(_){return null}};
A.plan=async cid=>{
 const p=await sb.from("f1_client_email_plans").select("*").eq("owner_id",user.id).eq("client_id",cid).order("updated_at",{ascending:false}).limit(1);
 if(p.error||!p.data||!p.data.length)return {plan:null,items:[]};
 const plan=p.data[0],i=await sb.from("f1_client_email_plan_items").select("*").eq("owner_id",user.id).eq("client_id",cid).eq("plan_id",plan.id).order("send_at");
 return {plan,items:i.error?[]:(i.data||[])};
};
A.copyPrompt=async()=>{const t=$("f1v7AiPrompt");if(!t)return;try{await navigator.clipboard.writeText(t.value)}catch(_){t.select();document.execCommand("copy")}};
A.toggle=()=>{const n=document.querySelector(".f1v7-ai");if(n)n.classList.toggle("open")};
A.showAccount=()=>{const r=$("emailWorkspace");if(!r)return;r.classList.remove("f1v7-hidden");if(window.f1EmailSetView)window.f1EmailSetView("account");r.scrollIntoView({behavior:"smooth"})};
A.configureAuto=async()=>{
 const c=A.client();if(!c)return;
 const pd=await A.plan(c.id);
 if(!pd.plan){
  const n=document.querySelector(".f1v7-ai");if(n)n.classList.add("open");
  const t=$("f1v7AiPrompt");if(t)t.scrollIntoView({behavior:"smooth",block:"center"});
  alert("Per attivare l'automazione crea prima il piano con ChatGPT e importa il CSV.");
  return;
 }
 const active=String(pd.plan.status||"").toUpperCase()==="ATTIVA";
 const next=active?"DISATTIVA":"ATTIVA";
 const u=await sb.from("f1_client_email_plans").update({status:next,updated_at:new Date().toISOString()}).eq("id",pd.plan.id).eq("owner_id",user.id).eq("client_id",c.id);
 if(u.error)throw u.error;
 await A.render();
};
A.render=async()=>{
 const c=A.client(),root=$("emailWorkspace");if(!c||!root)return;
 let host=$("f1v7EmailCompact");if(!host){host=document.createElement("div");host.id="f1v7EmailCompact";root.parentElement.insertBefore(host,root)}
 const [acc,count,pd]=await Promise.all([A.account(c.id),A.crm(c.id),A.plan(c.id)]);
 const groups={};(pd.items||[]).forEach(x=>{const k=x.month_label||new Date(x.send_at).toLocaleDateString("it-IT",{month:"long",year:"numeric"});(groups[k]||(groups[k]=[])).push(x)});
 const active=!!(pd.plan&&String(pd.plan.status||"").toUpperCase()==="ATTIVA");
 const autoState=pd.plan?(active?"ATTIVA":"DISATTIVA"):"NON CONFIGURATA";
 const autoButton=pd.plan?(active?"DISATTIVA AUTO":"ATTIVA AUTO"):"CONFIGURA AUTO";
 const autoLine=active?'<b>PROGRAMMATA IN AUTOMATICO 1 VOLTA ALLA SETTIMANA</b> · '+esc(c.name):'<b>AUTOMAZIONE NON ANCORA ATTIVA</b> · '+esc(c.name);
 host.innerHTML=
  '<div class="f1v7-email-grid"><div class="f1v7-email-card"><small>EMAIL CLIENTE</small><div class="f1v7-email-address">'+esc(acc&&acc.email_address||"NON CONFIGURATA")+'</div><div class="meta">'+esc(acc&&acc.provider||"")+" · "+esc(acc&&acc.connection_status||"DA CONFIGURARE")+'</div><div class="row" style="margin-top:10px"><button class="btn primary" onclick="F1EmailV7.showAccount()">CONFIGURA ACCOUNT</button><button class="btn ghost" onclick="window.f1EmailRefresh&&window.f1EmailRefresh()">VERIFICA</button></div></div><div class="f1v7-email-card"><small>EMAIL NEL CRM</small><div style="font-size:38px;font-weight:1000">'+(count==null?"—":count)+'</div><div class="meta">contatti email unici del cliente</div></div></div>'+
  '<div class="f1v7-email-card"><div class="section-title"><div><h3 style="margin:0">Automazione email</h3><div class="meta">Generazione e programmazione automatica del cliente selezionato</div></div><span class="badge '+(active?"green":"amber")+'">'+autoState+'</span></div><div class="f1v7-email-auto-summary"><div class="f1v7-email-auto-cell"><span>AUTOMAZIONE</span><b>Contenuto + email</b></div><div class="f1v7-email-auto-cell"><span>FREQUENZA</span><b>1 volta alla settimana</b></div><div class="f1v7-email-auto-cell"><span>STATO</span><b>'+autoState+'</b></div><button class="btn primary" onclick="F1EmailV7.configureAuto()">'+autoButton+'</button></div><div class="f1v7-source-status">'+autoLine+'<br><span>Il caricamento del CSV crea il piano annuale. Gli invii reali restano soggetti ad account collegato, destinatari validi e controlli di invio.</span></div></div>'+
  '<div class="f1v7-email-card f1v7-ai"><button class="f1v7-ai-head" onclick="F1EmailV7.toggle()"><div><b>✨ IA · CREA PIANO EMAIL · 12 MESI</b><div class="meta">ChatGPT → CSV → F1 Social</div></div><span>⌄</span></button><div class="f1v7-ai-body"><textarea id="f1v7AiPrompt" class="input" readonly>'+esc(A.prompt(c))+'</textarea><div class="row" style="margin-top:8px"><a class="btn primary" href="https://chatgpt.com/" target="_blank" rel="noopener" onclick="F1EmailV7.copyPrompt()">APRI CHATGPT</a><button class="btn ghost" onclick="F1EmailV7.copyPrompt().then(()=>alert(\'Prompt copiato.\'))">COPIA PROMPT</button><button class="btn ghost" onclick="F1EmailV7.downloadTemplate()">SCARICA MODELLO CSV</button><button class="btn green" onclick="document.getElementById(\'f1v7EmailCsv\').click()">CARICA CSV</button><input id="f1v7EmailCsv" type="file" accept=".csv,text/csv" hidden onchange="F1EmailV7.importCsv(this)"></div></div></div>'+
  '<div class="f1v7-email-card"><h3>Piano automatico email · 12 mesi</h3>'+(pd.items&&pd.items.length?Object.keys(groups).map(month=>{const rows=groups[month];return '<div class="f1v7-plan-row"><div class="f1v7-plan-head" onclick="this.parentElement.classList.toggle(\'open\')"><b>'+esc(month)+'</b><span>'+esc(rows[0]&&rows[0].theme||"")+'</span><span>'+rows.length+' EMAIL</span><span>'+esc(rows[0]&&rows[0].crm_segment||"TUTTI_I_CONTATTI")+'</span><span>⌄</span></div><div class="f1v7-plan-body">'+rows.map(x=>'<div class="f1v7-mail"><b>'+new Date(x.send_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"})+' · '+esc(x.subject)+'</b><div class="meta">'+esc(x.preheader||"")+'</div><div>'+esc(x.body_text||"").replace(/\n/g,"<br>")+'</div><div class="meta">CTA: '+esc(x.cta_text||"—")+' · '+esc(x.cta_url||"—")+' · '+esc(x.status||"")+'</div></div>').join("")+'</div></div>'}).join(""):'<div class="empty">Nessun piano importato. Apri IA · CREA PIANO EMAIL, genera il CSV e caricalo qui.</div>')+'</div>';
 root.classList.add("f1v7-hidden");
};
window.F1EmailV7=A;
window.f1V7RenderEmailCompact=()=>A.render().catch(e=>{console.error("F1 email v7",e);alert("Errore modulo email: "+(e.message||e))});
})();
