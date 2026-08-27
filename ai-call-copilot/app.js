const $ = s => document.querySelector(s);
const state = {mode:'F1', listening:false, calls:0, interested:0, callbacks:0, no:0, transcript:[], recognition:null};

const scripts = {
  F1: [
    {name:'Apertura', text:'Buongiorno, sono Joseph di F1 Immobiliare. La disturbo solo un minuto: stiamo lavorando con proprietari e acquirenti nella sua zona e volevo capire se posso esserle utile con una valutazione o con un piano di vendita.'},
    {name:'Non vendo', text:'Capisco. Non le sto chiedendo di decidere oggi. Posso semplicemente lasciarle un riferimento e, se in futuro dovesse valutare una vendita, avrà già un contatto diretto.'},
    {name:'Ho già agenzia', text:'Perfetto, allora non voglio interferire. Se però le può essere utile, posso mostrarle in modo molto concreto come pubblicizziamo un immobile: foto, video, social, campagne, portali e report dei risultati.'},
    {name:'Quanto vale?', text:'Per darle un numero serio preferisco verificare immobile, microzona e comparabili. Possiamo fissare una valutazione senza impegno e poi decide lei se approfondire.'},
    {name:'Mandami materiale', text:'Certamente. Le invio una presentazione breve con il nostro metodo di pubblicizzazione e i risultati che può aspettarsi da una gestione strutturata.'}
  ],
  RMP: [
    {name:'Apertura', text:'Buongiorno, sono Joseph di Real Media Pro. La chiamo perché stiamo analizzando alcune attività della zona e volevo mostrarle, in modo molto pratico, come potremmo presentare e promuovere la sua azienda sui social.'},
    {name:'Ho già qualcuno', text:'Va benissimo. Non voglio sostituire nessuno a priori: posso farle vedere un confronto concreto tra ciò che pubblica oggi e una possibile gestione con reel, offerte, calendario editoriale e campagne locali.'},
    {name:'Quanto costa?', text:'Dipende dal volume di contenuti e dalla parte pubblicitaria. Prima preferisco farle vedere cosa faremmo e quali risultati misureremmo, così può valutare il servizio sul concreto.'},
    {name:'Non mi interessa', text:'Capisco. Le lascio soltanto un esempio visivo dei contenuti e della gestione, così se in futuro vorrà confrontare alternative avrà già un riferimento.'},
    {name:'Mandami esempio', text:'Perfetto. Le mando una demo della gestione social con esempi di contenuti, frequenza di pubblicazione, offerte e impostazione delle campagne.'}
  ]
};

function setMode(mode){
  state.mode = mode;
  $('#mode').value = mode;
  renderScripts();
  suggest('Apertura');
}
function renderScripts(){
  const box = $('#scriptList'); box.innerHTML='';
  scripts[state.mode].forEach(s=>{
    const b=document.createElement('button'); b.className='btn dark'; b.textContent=s.name;
    b.onclick=()=>suggest(s.name); box.appendChild(b);
  });
}
function suggest(name){
  const item=scripts[state.mode].find(s=>s.name===name)||scripts[state.mode][0];
  $('#suggestionTitle').textContent=item.name;
  $('#suggestionText').textContent=item.text;
}
function detectReply(text){
  const t=text.toLowerCase();
  if(/gi[aà].*agenzia|agenzia.*gi[aà]|gi[aà].*qualcuno|social.*gestit/.test(t)) return state.mode==='F1'?'Ho già agenzia':'Ho già qualcuno';
  if(/quanto.*vale|valutaz|prezzo.*casa|valore/.test(t) && state.mode==='F1') return 'Quanto vale?';
  if(/quanto.*cost|prezzo|tariff/.test(t) && state.mode==='RMP') return 'Quanto costa?';
  if(/manda|materiale|whatsapp|esempio|vedere/.test(t)) return state.mode==='F1'?'Mandami materiale':'Mandami esempio';
  if(/non.*interess|non.*vendo|non.*vendere|non mi serve/.test(t)) return state.mode==='F1'?'Non vendo':'Non mi interessa';
  return 'Apertura';
}
function addBubble(who,text){
  state.transcript.push({who,text,time:new Date().toISOString()});
  const p=document.createElement('p'); p.className='bubble '+(who==='Cliente'?'user':'ai');
  p.innerHTML=`<b>${who}:</b> ${escapeHtml(text)}`; $('#transcript').appendChild(p);
  $('#transcript').scrollTop=$('#transcript').scrollHeight;
}
function escapeHtml(s){return s.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function speakSuggestion(){
  const txt=$('#suggestionText').textContent;
  if(!txt) return;
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(txt); u.lang='it-IT'; u.rate=1.02; u.pitch=1;
  addBubble('AI',txt); speechSynthesis.speak(u);
}
function stopVoice(){speechSynthesis.cancel();}
function startListening(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){alert('Il browser non supporta il riconoscimento vocale Web Speech. Usa Chrome/Edge aggiornato.');return;}
  if(state.recognition){try{state.recognition.stop()}catch(e){}}
  const r=new SR(); state.recognition=r; r.lang='it-IT'; r.continuous=true; r.interimResults=true;
  r.onstart=()=>{state.listening=true;$('#liveDot').classList.add('live');$('#listenBtn').textContent='STOP ASCOLTO';};
  r.onend=()=>{state.listening=false;$('#liveDot').classList.remove('live');$('#listenBtn').textContent='ASCOLTA CLIENTE';};
  r.onresult=e=>{
    let finalText=''; let interim='';
    for(let i=e.resultIndex;i<e.results.length;i++){
      const txt=e.results[i][0].transcript;
      if(e.results[i].isFinal) finalText+=txt; else interim+=txt;
    }
    $('#interim').textContent=interim;
    if(finalText){ addBubble('Cliente',finalText.trim()); $('#interim').textContent=''; suggest(detectReply(finalText)); }
  };
  r.onerror=e=>console.warn('Speech recognition error',e.error);
  r.start();
}
function toggleListening(){
  if(state.listening && state.recognition){state.recognition.stop();return;} startListening();
}
function manualTakeover(){
  stopVoice();
  if(state.listening && state.recognition){try{state.recognition.stop()}catch(e){}}
  $('#takeover').textContent='CONTROLLO TUO — AI IN PAUSA';
  $('#takeover').className='btn red takeover';
  setTimeout(()=>{$('#takeover').textContent='PRENDO IO LA CHIAMATA';$('#takeover').className='btn blue takeover';},2500);
}
function setOutcome(kind){
  state.calls++;
  if(kind==='interested') state.interested++;
  if(kind==='callback') state.callbacks++;
  if(kind==='no') state.no++;
  updateKpis(); saveCRM(kind);
}
function updateKpis(){
  $('#kCalls').textContent=state.calls; $('#kInterested').textContent=state.interested; $('#kCallbacks').textContent=state.callbacks; $('#kNo').textContent=state.no;
}
function saveCRM(outcome){
  const rows=JSON.parse(localStorage.getItem('f1rmp_ai_calls')||'[]');
  rows.unshift({date:new Date().toISOString(), mode:state.mode, name:$('#name').value.trim(), phone:$('#phone').value.trim(), zone:$('#zone').value.trim(), outcome, notes:$('#notes').value.trim(), transcript:state.transcript.slice()});
  localStorage.setItem('f1rmp_ai_calls',JSON.stringify(rows.slice(0,5000)));
  state.transcript=[]; $('#transcript').innerHTML=''; $('#notes').value='';
}
function exportCRM(){
  const rows=JSON.parse(localStorage.getItem('f1rmp_ai_calls')||'[]');
  const blob=new Blob([JSON.stringify(rows,null,2)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='f1-rmp-ai-call-crm.json'; a.click(); URL.revokeObjectURL(a.href);
}
function callNumber(){
  const p=$('#phone').value.replace(/\s+/g,''); if(!p){alert('Inserisci un numero.');return;}
  window.location.href='tel:'+p;
}
function loadRotation(){
  const zones=['Susa','Bussoleno','Condove','Avigliana','Rivoli','Almese','Caprie','Sant’Antonino di Susa','Borgone','Chiusa di San Michele','Villar Dora','Buttigliera Alta','Rosta','Caselette','Rubiana'];
  const day=Math.floor(Date.now()/86400000); const start=(day*5)%zones.length;
  const today=Array.from({length:5},(_,i)=>zones[(start+i)%zones.length]);
  $('#rotation').textContent=today.join(' • ');
}

document.addEventListener('DOMContentLoaded',()=>{
  $('#mode').onchange=e=>setMode(e.target.value);
  $('#listenBtn').onclick=toggleListening; $('#speakBtn').onclick=speakSuggestion; $('#stopBtn').onclick=stopVoice;
  $('#takeover').onclick=manualTakeover; $('#callBtn').onclick=callNumber; $('#exportBtn').onclick=exportCRM;
  document.querySelectorAll('[data-outcome]').forEach(b=>b.onclick=()=>setOutcome(b.dataset.outcome));
  setMode('F1'); updateKpis(); loadRotation();
});