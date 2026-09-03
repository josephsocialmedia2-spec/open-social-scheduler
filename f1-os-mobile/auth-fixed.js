const F1_ACCOUNT_EMAIL='f1immobiliaresusa@outlook.it';
(function(){
  const form=document.querySelector('#loginForm');
  if(!form)return;
  const email=document.querySelector('#email');
  const password=document.querySelector('#password');
  const err=document.querySelector('#loginError');
  const submit=form.querySelector('button[type="submit"]');
  email.value=F1_ACCOUNT_EMAIL;
  email.readOnly=true;
  email.autocomplete='username';
  if(submit)submit.textContent='ENTRA / CREA ACCOUNT F1';
  const note=form.querySelector('.muted');
  if(note)note.textContent='Account F1: '+F1_ACCOUNT_EMAIL+'. La prima volta scegli una password. Se l’account non esiste, viene creato automaticamente. Dopo resta collegato.';

  async function signup(emailValue,passwordValue){
    const r=await fetch(SB+'/auth/v1/signup',{
      method:'POST',
      headers:{'apikey':KEY,'Content-Type':'application/json'},
      body:JSON.stringify({email:emailValue,password:passwordValue,data:{app:'F1 OS Immobiliare'}})
    });
    const j=await r.json();
    if(!r.ok)throw new Error(j.msg||j.error_description||j.message||'Creazione account non riuscita');
    return j;
  }

  form.onsubmit=async e=>{
    e.preventDefault();
    err.textContent='';
    const p=password.value;
    if(!p||p.length<8){err.textContent='Scegli una password di almeno 8 caratteri.';return;}
    if(submit){submit.disabled=true;submit.textContent='COLLEGO...';}
    try{
      try{
        await login(F1_ACCOUNT_EMAIL,p);
        document.querySelector('#login').close();
        await sync();
        return;
      }catch(firstError){
        const created=await signup(F1_ACCOUNT_EMAIL,p);
        if(created.access_token){
          session=created;
          localStorage.setItem('f1_session',JSON.stringify(created));
          document.querySelector('#login').close();
          await sync();
          return;
        }
        err.innerHTML='Account F1 creato. <b>Controlla '+F1_ACCOUNT_EMAIL+'</b> e conferma l’email. Poi torna qui e premi ENTRA usando la stessa password.';
      }
    }catch(ex){
      err.textContent=ex.message||String(ex);
    }finally{
      if(submit){submit.disabled=false;submit.textContent='ENTRA / CREA ACCOUNT F1';}
    }
  };
})();
