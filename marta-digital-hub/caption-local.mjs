function clean(text){
  return String(text||'').replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/\n{3,}/g,'\n\n').trim();
}
function clip(text,max){
  const s=clean(text);if(s.length<=max)return s;
  const cut=s.slice(0,max-1),p=Math.max(cut.lastIndexOf('. '),cut.lastIndexOf('! '),cut.lastIndexOf('? '),cut.lastIndexOf(' '));
  return (p>max*.65?cut.slice(0,p+1):cut).trim()+'…';
}
function firstSentence(text,max=180){
  const s=clean(text).replace(/\n+/g,' ');
  const m=s.match(/^(.{1,220}?[.!?])(?:\s|$)/);
  return clip((m?.[1]||s),max);
}
function hashTag(value){
  const x=String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9]+/g,' ').trim();
  if(!x)return null;
  return '#'+x.split(/\s+/).map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join('').slice(0,50);
}
function join(...parts){return parts.filter(Boolean).join('\n\n').trim();}
export function buildLocalCaptionPack(transcript,{title='',category=''}={}){
  const body=clean(transcript);if(!body)throw Error('Prima serve una trascrizione.');
  if(body.length>100000)throw Error('Trascrizione troppo lunga.');
  const hook=firstSentence(body,180)||clip(title,180);
  const cta='Per approfondire, scrivimi in privato.';
  const categoryTag=hashTag(category);
  const hashtags=[categoryTag,'#MartaRuffino','#PelvicamenteMarta'].filter(Boolean);
  const tagLine=hashtags.join(' ');
  const short=join(hook,cta,tagLine);
  return {
    topic:clip(title||hook,160),
    category:clip(category,120),
    hook,cta,hashtags,
    instagram:{
      short,
      medium:join(hook,clip(body,1800),cta,tagLine),
      deep:join(hook,clip(body,4200),cta,tagLine)
    },
    facebook:{
      short:join(hook,cta),
      medium:join(hook,clip(body,2400),cta),
      deep:join(hook,clip(body,5200),cta)
    },
    tiktok:{
      short:join(clip(hook,120),cta,tagLine),
      medium:join(clip(hook,140),clip(body,850),cta,tagLine),
      deep:join(clip(hook,160),clip(body,1500),cta,tagLine)
    },
    linkedin:{
      short:join(hook,cta),
      medium:join(hook,clip(body,2200),cta),
      deep:join(hook,clip(body,4500),cta)
    },
    youtube:{
      title:clip(title||hook,100),
      description:join(hook,clip(body,5000),cta),
      tags:hashtags.map(x=>x.replace(/^#/,'')).filter(Boolean),
      short_text:join(clip(hook,140),cta)
    }
  };
}
