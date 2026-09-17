(()=>{
  const MAX_TEXT=12000,MAX_HOOK=500,MAX_CTA=1000,MAX_TAGS=50,MAX_TRANSCRIPT=100000;
  function activePlatform(){return document.querySelector('#variantTabs button.active')?.dataset.p||null}
  function fields(){return {text:document.querySelector('#vText'),hook:document.querySelector('#vHook'),cta:document.querySelector('#vCta'),tags:document.querySelector('#vTags')}}
  function validateVariant(requireText=false){
    const f=fields(); if(!f.text)return {ok:false,msg:'Caption non disponibile'};
    const tagList=(f.tags?.value||'').trim().split(/\s+/).filter(Boolean);
    if(requireText&&!f.text.value.trim())return {ok:false,msg:'Scrivi la caption prima di approvarla.'};
    if(f.text.value.length>MAX_TEXT)return {ok:false,msg:'Caption troppo lunga.'};
    if((f.hook?.value||'').length>MAX_HOOK)return {ok:false,msg:'Hook troppo lungo.'};
    if((f.cta?.value||'').length>MAX_CTA)return {ok:false,msg:'CTA troppo lunga.'};
    if(tagList.length>MAX_TAGS)return {ok:false,msg:`Massimo ${MAX_TAGS} hashtag/tag.`};
    if((f.tags?.value||'').length>5000)return {ok:false,msg:'Hashtag/tag troppo lunghi.'};
    return {ok:true,tags:tagList};
  }
  function harden(){
    const t=document.querySelector('#transcript');if(t)t.maxLength=MAX_TRANSCRIPT;
    const f=fields();if(f.text)f.text.maxLength=MAX_TEXT;if(f.hook)f.hook.maxLength=MAX_HOOK;if(f.cta)f.cta.maxLength=MAX_CTA;if(f.tags)f.tags.maxLength=5000;
    const actions=document.querySelector('#variantBox .actions');
    if(actions&&!document.querySelector('#vSkip')){
      const b=document.createElement('button');b.id='vSkip';b.type='button';b.className='ghost';b.textContent='Non pubblicare qui';actions.insertBefore(b,actions.lastElementChild||null);
    }
  }
  new MutationObserver(harden).observe(document.documentElement,{subtree:true,childList:true});
  harden();
  document.addEventListener('click',async e=>{
    const id=e.target?.id;
    if(id==='vApprove'||id==='vSave'){
      const v=validateVariant(id==='vApprove');
      if(!v.ok){e.preventDefault();e.stopImmediatePropagation();toast(v.msg,true);return}
    }
    if(id==='saveTranscript'){
      const t=document.querySelector('#transcript'),text=t?.value.trim()||'';
      if(!text){e.preventDefault();e.stopImmediatePropagation();toast('La trascrizione è vuota.',true);return}
      if(text.length>MAX_TRANSCRIPT){e.preventDefault();e.stopImmediatePropagation();toast('Trascrizione troppo lunga.',true);return}
    }
    if(id==='vSkip'){
      e.preventDefault();e.stopImmediatePropagation();
      const p=activePlatform(),f=fields();
      if(!p||!currentContent){toast('Piattaforma non disponibile.',true);return}
      const tagList=(f.tags?.value||'').trim().split(/\s+/).filter(Boolean).slice(0,MAX_TAGS);
      const body={
        owner_id:S.user.id,content_id:currentContent,platform:p,
        hook:(f.hook?.value||'').slice(0,MAX_HOOK),cta:(f.cta?.value||'').slice(0,MAX_CTA),hashtags:tagList,
        variants:p==='youtube'?{description:(f.text?.value||'').slice(0,MAX_TEXT),tags:tagList}:{medium:(f.text?.value||'').slice(0,MAX_TEXT)},
        status:'NON_PUBBLICARE',approved_at:null
      };
      try{
        await db('social_variants?on_conflict=content_id,platform',{method:'POST',body,prefer:'resolution=merge-duplicates,return=representation'});
        toast(`${p}: escluso dalla pubblicazione`);await openContent(currentContent);
      }catch(err){toast(err.message||'Impossibile aggiornare la piattaforma',true)}
    }
  },true);
})();
