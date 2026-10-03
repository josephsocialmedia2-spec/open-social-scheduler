(function(){
"use strict";
const A={};
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
A.client=()=>{try{return (clients||[]).find(c=>c.id===selectedClientId)||null}catch(_){return null}};
A.prompt=c=>[
"CREA UN PIANO CONTENUTISTICO EMAIL COMPLETO DI 12 MESI PER:",
"",
"CLIENTE: "+c.name,
"SETTORE: "+(c.category||"da definire"),
"SITO: "+(c.website||"da definire"),
"",
"FREQUENZA: 1 email alla settimana per 12 mesi.",
"Per ogni settimana crea tema, obiettivo, oggetto, preheader, corpo completo, CTA e link.",
"Alterna contenuti educativi, problema/soluzione, autorevolezza, casi pratici, territorio, servizi e conversione.",
"Non inventare dati, offerte, testimonianze o risultati non verificati.",
"",
"ALLA FINE CREA UN CSV UTF-8 con ESATTAMENTE queste colonne:",
"cliente,data_invio,ora_invio,mese,settimana,tema,obiettivo,oggetto_email,preheader,corpo_email,cta_testo,cta_url,segmento_crm,stato",
"",
"Regole: una riga = una email; data YYYY-MM-DD; ora HH:MM; stato PROGRAMMATA; segmento TUTTI_I_CONTATTI salvo necessità; nessuna colonna extra."
].join("\n");
A.account=async cid=>{try{const r=await sb.from("f1_client_email_accounts").select("email_address,provider,connection_status,connected_email").eq("owner_id",user.id).eq("client_id",cid).order("created_at").limit(1);return r.data&&r.data[0]||null}catch(_){return null}};
A.crm=async cid=>{try{const r=await sb.from("email_campaign_recipients").select("email").eq("owner_id",user.id).eq("client_id",cid).limit(5000);if(r.error)throw r.error;return new Set((r.data||[]).map(x=>String(x.email||"").trim().toLowerCase()).filter(Boolean)).size}catch(_){return null}};
A.plan=async cid=>{const p=await sb.from("f1_client_email_plans").select("*").eq("owner_id",user.id).eq("client_id",cid).order("updated_at",{ascending:false}).limit(1);if(p.error||!p.data||!p.data.length)return {plan:null,items:[]};const plan=p.data[0],i=await sb.from("f1_client_email_plan_items").select("*").eq("owner_id",user.id).eq("client_id",cid).eq("plan_id",plan.id).order("send_at");return {plan,items:i.data||[]}};
A.copyPrompt=async()=>{const t=$("f1v7AiPrompt");if(!t)return;try{await navigator.clipboard.writeText(t.value)}catch(_){t.select();document.execCommand("copy")}alert("Prompt copiato.")};
A.toggle=()=>{const n=document.querySelector(".f1v7-ai");if(n)n.classList.toggle("open")};
A.showAccount=()=>{const r=$("emailWorkspace");if(!r)return;r.classList.remove("f1v7-hidden");if(window.f1EmailSetView)window.f1EmailSetView("account");r.scrollIntoView({behavior:"smooth"})};
A.render=async()=>{
 const c=A.client(),root=$("emailWorkspace");if(!c||!root)return;
 let host=$("f1v7EmailCompact");if(!host){host=document.createElement("div");host.id="f1v7EmailCompact";root.parentElement.insertBefore(host,root)}
 const [acc,count,pd]=await Promise.all([A.account(c.id),A.crm(c.id),A.plan(c.id)]);
 const groups={};(pd.items||[]).forEach(x=>{const k=x.month_label||new Date(x.send_at).toLocaleDateString("it-IT",{month:"long",year:"numeric"});(groups[k]||(groups[k]=[])).push(x)});
 host.innerHTML='<div class="f1v7-email-grid"><div class="f1v7-email-card"><small>EMAIL CLIENTE</small><div class="f1v7-email-address">'+esc(acc&&acc.email_address||"NON CONFIGURATA")+'</div><div class="meta">'+esc(acc&&acc.provider||"")+" · "+esc(acc&&acc.connection_status||"DA CONFIGURARE")+'</div><div class="row" style="margin-top:10px"><button class="btn primary" onclick="F1EmailV7.showAccount()">CONFIGURA ACCOUNT</button><button class="btn ghost" onclick="window.f1EmailRefresh&&window.f1EmailRefresh()">VERIFICA</button></div></div><div class="f1v7-email-card"><small>EMAIL NEL CRM</small><div style="font-size:38px;font-weight:1000">'+(count==null?"—":count)+'</div><div class="meta">contatti email unici del cliente</div></div></div>'+
 '<div class="f1v7-email-card"><div class="row" style="justify-content:space-between"><div><b>AUTOMAZIONE EMAIL</b><div class="meta">Contenuto + email · 1 volta alla settimana</div></div><span class="badge '+(pd.plan?"green":"amber")+'">'+(pd.plan?"ATTIVA":"DA IMPORTARE")+'</span></div></div>'+
 '<div class="f1v7-email-card f1v7-ai"><button class="f1v7-ai-head" onclick="F1EmailV7.toggle()"><div><b>✨ IA · CREA PIANO EMAIL · 12 MESI</b><div class="meta">ChatGPT → CSV → F1 Social</div></div><span>⌄</span></button><div class="f1v7-ai-body"><textarea id="f1v7AiPrompt" class="input" readonly>'+esc(A.prompt(c))+'</textarea><div class="row" style="margin-top:8px"><a class="btn primary" href="https://chatgpt.com/" target="_blank" rel="noopener" onclick="F1EmailV7.copyPrompt()">APRI CHATGPT</a><button class="btn ghost" onclick="F1EmailV7.copyPrompt()">COPIA PROMPT</button><button class="btn ghost" onclick="F1EmailV7.downloadTemplate()">SCARICA MODELLO CSV</button><button class="btn green" onclick="document.getElementById(\'f1v7EmailCsv\').click()">CARICA CSV</button><input id="f1v7EmailCsv" type="file" accept=".csv,text/csv" hidden onchange="F1EmailV7.importCsv(this)"></div></div></div>'+
 '<div class="f1v7-email-card"><h3>Piano automatico email · 12 mesi</h3>'+(pd.items&&pd.items.length?Object.keys(groups).map(month=>{const rows=groups[month];return '<div class="f1v7-plan-row"><div class="f1v7-plan-head" onclick="this.parentElement.classList.toggle(\'open\')"><b>'+esc(month)+'</b><span>'+esc(rows[0]&&rows[0].theme||"")+'</span><span>'+rows.length+' EMAIL</span><span>'+esc(rows[0]&&rows[0].crm_segment||"TUTTI_I_CONTATTI")+'</span><span>⌄</span></div><div class="f1v7-plan-body">'+rows.map(x=>'<div class="f1v7-mail"><b>'+new Date(x.send_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"})+' · '+esc(x.subject)+'</b><div class="meta">'+esc(x.preheader||"")+'</div><div>'+esc(x.body_text||"").replace(/\n/g,"<br>")+'</div><div class="meta">CTA: '+esc(x.cta_text||"—")+' · '+esc(x.cta_url||"—")+' · '+esc(x.status||"")+'</div></div>').join("")+'</div></div>'}).join(""):'<div class="empty">Importa il CSV generato per creare il piano annuale.</div>')+'</div>';
 root.classList.add("f1v7-hidden")
};
window.F1EmailV7=A;window.f1V7RenderEmailCompact=()=>A.render().catch(e=>console.error("F1 email v7",e));
})();