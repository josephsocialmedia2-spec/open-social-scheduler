(function(root,factory){
  const api=factory();
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
  root.F1ClientHealth=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const PLATFORM_FIELDS={
    facebook:"facebook",
    instagram:"instagram",
    "linkedin-page":"linkedin",
    tiktok:"tiktok",
    youtube:"youtube"
  };
  const SEVERITY={red:0,orange:1,green:2};
  const BLOCKING_STATES=new Set([
    "TOKEN_SCADUTO","DA_RIAUTORIZZARE","ACCOUNT_CONDIVISO","ACCOUNT_ERRATO",
    "ACCOUNT_NON_AUTORIZZATO","AUTH_REQUIRED","PERMESSI_INSUFFICIENTI",
    "ERRORE","AUTORIZZAZIONE_NEGATA"
  ]);
  const SIMPLE_DISCONNECTED=new Set([
    "NON CONFIGURATO","NON_CONFIGURATO","CANALE_DA_COLLEGARE","SCOLLEGATO",
    "CONFIGURAZIONE_PRONTA","AUTORIZZAZIONE_RICHIESTA","ACCOUNT_DA_SELEZIONARE"
  ]);
  const NEW_CONTENT_STATES=new Set([
    "DA LAVORARE","IN LAVORAZIONE","BOZZA","PRONTO","DA APPROVARE","APPROVATO",
    "CARICATO","IN ELABORAZIONE","IN_ELABORAZIONE"
  ]);

  function canonicalPlatform(value){
    const p=String(value||"").trim().toLowerCase();
    return p==="linkedin"?"linkedin-page":p;
  }
  function effectiveState(row,collisions,now){
    if(!row)return "NON CONFIGURATO";
    const platform=canonicalPlatform(row.platform);
    const key=platform+"|"+String(row.external_channel_id||"");
    if(row.external_channel_id&&collisions&&collisions[key]&&collisions[key].length>1)return "ACCOUNT_CONDIVISO";
    if(row.reauthorization_required)return "DA_RIAUTORIZZARE";
    if(row.token_expires_at&&new Date(row.token_expires_at).getTime()<=Number(now||Date.now()))return "TOKEN_SCADUTO";
    if(row.enabled&&row.verified)return "COLLEGATO";
    return String(row.connection_status||"CANALE_DA_COLLEGARE").toUpperCase();
  }
  function collisionMap(channels){
    const out={};
    (channels||[]).forEach(function(row){
      if(!row||!row.enabled||!row.verified||!row.external_channel_id)return;
      const key=canonicalPlatform(row.platform)+"|"+String(row.external_channel_id);
      (out[key]||(out[key]=[])).push(row.client_id);
    });
    return out;
  }
  function expectedPlatforms(client,clientChannels){
    const expected=new Set();
    Object.keys(PLATFORM_FIELDS).forEach(function(platform){
      const field=PLATFORM_FIELDS[platform];
      if(String(client&&client[field]||"").trim())expected.add(platform);
    });
    (clientChannels||[]).forEach(function(row){
      const p=canonicalPlatform(row.platform);
      if(!(p in PLATFORM_FIELDS))return;
      if(String(row.profile_url||"").trim()||row.enabled||row.verified)expected.add(p);
    });
    return Array.from(expected);
  }
  function hasFutureSchedule(clientId,calendar,now){
    const ts=Number(now||Date.now());
    return (calendar||[]).some(function(row){
      if(row.client_id!==clientId)return false;
      const at=new Date(row.publication_at).getTime();
      const status=String(row.status||"").toUpperCase();
      return Number.isFinite(at)&&at>ts&&/PROGRAMM|SCHEDULE|QUEUE/.test(status)&&!/ANNULL|CANCEL|ERROR|ERRORE|FAIL/.test(status);
    });
  }
  function hasNewContent(clientId,items){
    return (items||[]).some(function(row){
      if(row.client_id!==clientId)return false;
      return NEW_CONTENT_STATES.has(String(row.status||"").trim().toUpperCase());
    });
  }
  function assess(client,channels,calendar,items,options){
    const now=options&&options.now?Number(options.now):Date.now();
    const collisions=options&&options.collisions?options.collisions:collisionMap(channels);
    const ownChannels=(channels||[]).filter(function(x){return x.client_id===client.id});
    const expected=expectedPlatforms(client,ownChannels);
    const states=expected.map(function(platform){
      const row=ownChannels.find(function(x){return canonicalPlatform(x.platform)===platform});
      return {platform:platform,state:effectiveState(row,collisions,now),row:row||null};
    });
    const blocking=states.filter(function(x){return BLOCKING_STATES.has(x.state)});
    const disconnected=states.filter(function(x){return x.state!=="COLLEGATO"});
    const simpleDisconnected=disconnected.filter(function(x){return SIMPLE_DISCONNECTED.has(x.state)});
    const scheduled=hasFutureSchedule(client.id,calendar,now);
    const newContent=hasNewContent(client.id,items);
    let color="red",reason="";

    if(!expected.length){
      color="red";reason="Nessun profilo social previsto/configurato";
    }else if(blocking.length){
      color="red";reason="Problema bloccante su "+blocking.map(function(x){return x.platform}).join(", ");
    }else if(disconnected.length>=2){
      color="red";reason="Due o più profili social non collegati";
    }else if(!scheduled){
      color="red";reason="Nessuna pubblicazione futura programmata";
    }else if(!newContent){
      color="red";reason="Nessun nuovo contenuto disponibile";
    }else if(disconnected.length===1&&simpleDisconnected.length===1){
      color="orange";reason="Un solo profilo social da collegare";
    }else if(disconnected.length===0){
      color="green";reason="Profili, programmazione e contenuti presenti";
    }else{
      color="red";reason="Stato operativo incompleto";
    }

    return {
      clientId:client.id,
      name:client.name,
      color:color,
      severity:SEVERITY[color],
      reason:reason,
      expectedPlatforms:expected,
      disconnectedCount:disconnected.length,
      blockingCount:blocking.length,
      hasScheduledPosts:scheduled,
      hasNewContent:newContent,
      states:states
    };
  }
  function activeClients(clients){
    return (clients||[]).filter(function(c){return String(c.status||"").toUpperCase()==="ATTIVO"});
  }
  function dashboard(clients,channels,calendar,items,options){
    const collisions=collisionMap(channels);
    return activeClients(clients).map(function(client){
      return assess(client,channels,calendar,items,{now:options&&options.now,collisions:collisions});
    }).sort(function(a,b){
      return a.severity-b.severity||String(a.name||"").localeCompare(String(b.name||""),"it",{sensitivity:"base"});
    });
  }
  function counters(rows){
    return {
      active:(rows||[]).length,
      warning:(rows||[]).filter(function(x){return x.color==="orange"}).length,
      critical:(rows||[]).filter(function(x){return x.color==="red"}).length,
      ok:(rows||[]).filter(function(x){return x.color==="green"}).length
    };
  }
  return {canonicalPlatform,effectiveState,collisionMap,expectedPlatforms,hasFutureSchedule,hasNewContent,assess,activeClients,dashboard,counters};
});
