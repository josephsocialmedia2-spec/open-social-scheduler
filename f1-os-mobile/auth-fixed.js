const F1_ACCOUNT_EMAIL='f1immobiliaresusa@outlook.it';
(function(){
  const form=document.querySelector('#loginForm');
  if(!form)return;
  const email=document.querySelector('#email');
  const password=document.querySelector('#password');
  const err=document.querySelector('#loginError');
  const submit=form.querySelector('button[type="submit"]');

  if(email){
    email.value=F1_ACCOUNT_EMAIL;
    email.readOnly=true;
    email.autocomplete='username';
    const field=email.closest('.field');
    if(field)field.style.display='none';
  }

  if(submit)submit.textContent='ENTRA IN F1 OS';
  const note=form.querySelector('.muted');
  if(note)note.textContent='Account F1 già configurato. Inserisci solo la password.';

  form.onsubmit=async e=>{
    e.preventDefault();
    err.textContent='';
    const p=password.value;
    if(!p){err.textContent='Inserisci la password F1.';return;}
    if(submit){submit.disabled=true;submit.textContent='COLLEGO...';}
    try{
      await login(F1_ACCOUNT_EMAIL,p);
      document.querySelector('#login').close();
      await sync();
    }catch(ex){
      const msg=String(ex?.message||ex||'Accesso non riuscito');
      if(/email not confirmed/i.test(msg)){
        err.textContent='Configurazione account non allineata. Nessuna verifica email richiesta: contatta il responsabile F1.';
      }else if(/invalid login|invalid credentials/i.test(msg)){
        err.textContent='Password non corretta.';
      }else{
        err.textContent=msg;
      }
    }finally{
      if(submit){submit.disabled=false;submit.textContent='ENTRA IN F1 OS';}
    }
  };
})();
