const lessons = window.F1_LESSONS || [];
const $ = (s) => document.querySelector(s);
const completed = new Set(JSON.parse(localStorage.getItem('f1Completed') || '[]'));
let current = lessons[0];

function saveCompleted(){localStorage.setItem('f1Completed', JSON.stringify([...completed]));}
function lessonById(id){return lessons.find(x=>x.id===id);}
function selfTest(){
  const problems=[]; const ids=new Set();
  if(!Array.isArray(lessons)||!lessons.length) problems.push('Nessuna procedura caricata');
  lessons.forEach((l,i)=>{if(!l.id) problems.push(`Procedura ${i+1}: manca id`); if(ids.has(l.id)) problems.push(`ID duplicato: ${l.id}`); ids.add(l.id); if(!l.title) problems.push(`${l.id}: manca titolo`); if(!Array.isArray(l.steps)||!l.steps.length) problems.push(`${l.id}: mancano i passaggi`);});
  lessons.forEach(l=>{if(l.next&&!ids.has(l.next)) problems.push(`${l.id}: next non valido ${l.next}`); (l.links||[]).forEach(([label,target])=>{if(!ids.has(target)) problems.push(`${l.id}: collegamento non valido ${label} -> ${target}`);});});
  ['#title','#stage','#when','#steps','#ifs','#write','#stop','#doneBtn','#lessonNav','#diag'].forEach(sel=>{if(!$(sel)) problems.push(`Elemento pagina mancante: ${sel}`);});
  return problems;
}
function renderNav(){
  const nav=$('#lessonNav'); nav.innerHTML='';
  lessons.forEach(l=>{const b=document.createElement('button'); b.className='navItem'+(current&&l.id===current.id?' active':'')+(completed.has(l.id)?' done':''); b.textContent=l.title; b.onclick=()=>selectLesson(l.id); nav.appendChild(b);});
}
function renderLinks(){
  const box=$('#links'); const links=current.links||[];
  if(!links.length){box.innerHTML=''; box.hidden=true; return;}
  box.hidden=false; box.innerHTML='<div class="miniTitle">SE SERVE, APRI:</div>'+links.map(([label,target])=>`<button class="textLink" data-target="${target}">${label}</button>`).join('');
  box.querySelectorAll('[data-target]').forEach(b=>{b.onclick=()=>selectLesson(b.dataset.target);});
}
function selectLesson(id){
  current=lessonById(id)||lessons[0];
  $('#stage').textContent=current.stage||''; $('#title').textContent=current.title||''; $('#code').textContent=current.code||''; $('#when').textContent=current.when||'';
  $('#steps').innerHTML=(current.steps||[]).map((s,i)=>`<li><span>${i+1}</span><div>${s}</div></li>`).join('');
  $('#ifs').innerHTML=(current.ifs||[]).length?current.ifs.map(([a,b])=>`<div class="ifRow"><b>SE</b><span>${a}</span><b>→</b><span>${b}</span></div>`).join(''):'<div class="muted">Nessun caso speciale.</div>';
  $('#write').innerHTML=(current.write||[]).map(x=>`<li>${x}</li>`).join(''); $('#stop').innerHTML=(current.stop||[]).map(x=>`<li>${x}</li>`).join('');
  $('#doneBtn').textContent=current.doneLabel||'FATTO → AVANTI'; renderLinks(); renderNav(); window.scrollTo({top:0,behavior:'smooth'});
}
$('#doneBtn').onclick=()=>{completed.add(current.id); saveCompleted(); selectLesson(current.next||current.id);};
$('#speakBtn').onclick=()=>{speechSynthesis.cancel(); const u=new SpeechSynthesisUtterance(`${current.title}. ${(current.steps||[]).join('. ')}`); u.lang='it-IT'; u.rate=.95; speechSynthesis.speak(u);};
$('#menuBtn').onclick=()=>document.body.classList.toggle('menuOpen');
const problems=selfTest(); $('#diag').textContent=problems.length?`ERRORE: ${problems.join(' | ')}`:'SISTEMA OK'; $('#diag').className=problems.length?'diag bad':'diag ok';
if(lessons.length) selectLesson('start-shift');