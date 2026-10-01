(function(){
"use strict";

const WS_PLATFORMS=[
  {id:"facebook",label:"Facebook",time:"11:00"},
  {id:"instagram",label:"Instagram",time:"13:30"},
  {id:"tiktok",label:"TikTok",time:"18:30"},
  {id:"youtube",label:"YouTube",time:"21:00"},
  {id:"linkedin-page",label:"LinkedIn",time:"09:30"}
];
let selectedRailContentId="";
let railFilter="TUTTI";
let railSort="recenti";
const railThumbUrlCache=new Map();
let uploadRetryFiles=[];
let heicAutoMigrationRunning=false;
const heicAutoMigrationAttempted=new Set();
let uploadBatchState={
  totalFiles:0,completedFiles:0,failedFiles:0,totalBytes:0,uploadedBytes:0,
  currentFileName:"",currentFileNumber:0,currentStage:"",startedAt:0,bytesPerSecond:0,
  estimatedSecondsRemaining:null,status:"IDLE",samples:[],failed:[],convertedHeic:0
};

function h(value){return String(value==null?"":value).replace(/[&<>"']/g,function(m){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]})}
function clone(v){return JSON.parse(JSON.stringify(v||{}))}
function formatBytes(bytes){
  const n=Math.max(0,Number(bytes)||0);
  if(n<1024)return n+" B";
  if(n<1024*1024)return (n/1024).toFixed(1).replace(".",",")+" KB";
  if(n<1024*1024*1024)return (n/(1024*1024)).toFixed(1).replace(".",",")+" MB";
  return (n/(1024*1024*1024)).toFixed(2).replace(".",",")+" GB";
}
function formatDuration(seconds){
  if(seconds==null||!Number.isFinite(seconds)||seconds<0)return "CALCOLO IN CORSO...";
  const total=Math.max(0,Math.round(seconds)),m=Math.floor(total/60),s=total%60;
  if(m>=60){const h=Math.floor(m/60),rm=m%60;return h+" h "+rm+" min"}
  if(m>0)return m+" min "+String(s).padStart(2,"0")+" sec";
  return s+" sec";
}
function calculateUploadProgress(){
  const s=uploadBatchState;
  if(!s.totalBytes)return s.totalFiles?Math.round(((s.completedFiles+s.failedFiles)/s.totalFiles)*100):0;
  return Math.max(0,Math.min(100,(s.uploadedBytes/s.totalBytes)*100));
}
function calculateUploadSpeed(bytesNow){
  const s=uploadBatchState,now=performance.now();
  if(s.samples.length&&bytesNow<s.samples[s.samples.length-1].bytes)s.samples=[];
  s.samples.push({time:now,bytes:bytesNow});
  s.samples=s.samples.filter(function(x){return now-x.time<=5000});
  if(s.samples.length<2){s.bytesPerSecond=0;return 0}
  const first=s.samples[0],last=s.samples[s.samples.length-1],dt=(last.time-first.time)/1000;
  const speed=dt>0?Math.max(0,(last.bytes-first.bytes)/dt):0;
  s.bytesPerSecond=speed;
  s.estimatedSecondsRemaining=speed>0?Math.max(0,(s.totalBytes-s.uploadedBytes)/speed):null;
  return speed;
}
function uploadStatusLabel(status){
  return {IDLE:"",PREPARING:"PREPARAZIONE",CONVERTING_HEIC:"CONVERSIONE HEIC → PNG",UPLOADING:"CARICAMENTO IN CORSO",SAVING:"SALVATAGGIO IN CLOUD",PROCESSING:"ELABORAZIONE",COMPLETED:"COMPLETATO",PARTIAL_ERROR:"CARICAMENTO PARZIALE",ERROR:"ERRORE"}[status]||status;
}
function renderUploadProgress(){
  const box=document.getElementById("workspaceUploadProgress");if(!box)return;
  const s=uploadBatchState;
  if(s.status==="IDLE"){box.className="upload-progress hidden";box.innerHTML="";return}
  const pct=calculateUploadProgress(),elapsed=s.startedAt?((performance.now()-s.startedAt)/1000):0;
  const doneLabel=s.completedFiles+" / "+s.totalFiles+" contenuti";
  const detail=s.currentFileName?("FILE "+Math.max(1,s.currentFileNumber)+" DI "+s.totalFiles+" · "+s.currentFileName+(s.currentStage?" · "+s.currentStage:"")):"";
  const speed=s.bytesPerSecond>0?formatBytes(s.bytesPerSecond)+"/s":"CALCOLO IN CORSO...";
  const eta=s.status==="COMPLETED"?"0 sec":formatDuration(s.estimatedSecondsRemaining);
  const klass=s.status==="COMPLETED"?" completed":(s.status==="PARTIAL_ERROR"?" partial":(s.status==="ERROR"?" error":""));
  let final="";
  if(s.status==="COMPLETED"){
    final='<div class="upload-cloud"><b>☁ CONTENUTI IN CLOUD</b><span>'+s.completedFiles+' contenuti caricati correttamente'+(s.convertedHeic?' · '+s.convertedHeic+' HEIC convertiti automaticamente in PNG':'')+' · completato in '+formatDuration(elapsed)+'</span></div>';
  }else if(s.status==="PARTIAL_ERROR"||s.status==="ERROR"){
    final='<div class="upload-cloud"><b>⚠ CARICAMENTO PARZIALE</b><span>'+s.completedFiles+' / '+s.totalFiles+' contenuti caricati · '+s.failedFiles+' errori</span>'+(s.failedFiles?'<button class="btn small danger-bright upload-retry" onclick="window.f1RetryFailedUploads()">RIPROVA '+s.failedFiles+' FILE</button>':'')+'</div>';
  }
  box.className="upload-progress"+klass;
  box.innerHTML='<div class="upload-progress-head"><div><div class="upload-progress-title">CARICAMENTO CONTENUTI</div><div class="upload-progress-status">'+h(uploadStatusLabel(s.status))+'</div></div><div class="upload-percent">'+pct.toFixed(0)+'%</div></div>'+
    '<div class="upload-track"><div class="upload-fill" style="width:'+pct.toFixed(2)+'%"></div></div>'+
    '<div class="upload-summary"><div class="upload-stat"><b>'+h(doneLabel)+'</b><span>CONTENUTI</span></div><div class="upload-stat"><b>'+h(speed)+'</b><span>VELOCITÀ</span></div><div class="upload-stat"><b>'+h(eta)+'</b><span>TEMPO RIMANENTE</span></div><div class="upload-stat"><b>'+h(formatBytes(s.uploadedBytes))+' / '+h(formatBytes(s.totalBytes))+'</b><span>DATI</span></div></div>'+
    (s.quotaWarning?'<div class="upload-current">'+h(s.quotaWarning)+'</div>':'')+
    (detail?'<div class="upload-current">'+h(detail)+'</div>':'')+final;
}
function resetUploadBatch(files){
  const list=Array.from(files||[]);
  uploadBatchState={
    totalFiles:list.length,completedFiles:0,failedFiles:0,
    totalBytes:list.reduce(function(sum,f){return sum+(Number(f.size)||0)},0),
    uploadedBytes:0,currentFileName:"",currentFileNumber:0,currentStage:"",
    startedAt:performance.now(),bytesPerSecond:0,estimatedSecondsRemaining:null,
    status:"PREPARING",samples:[],failed:[],convertedHeic:0,quotaWarning:""
  };
  uploadRetryFiles=[];
  renderUploadProgress();
}
async function checkFreeMediaQuota(incomingBytes){
  const quota=await sb.rpc("f1_check_free_quota",{
    p_service_key:"supabase_storage_project",
    p_incoming_value:Math.max(0,Number(incomingBytes)||0)
  });
  if(quota.error)throw new Error("FREE QUOTA GUARD non disponibile: "+(quota.error.message||"verifica fallita"));
  const state=quota.data||{};
  const pct=Number(state.projected_percent||state.usage_percent||0);
  if(state.allowed!==true){
    throw new Error("FREE QUOTA GUARD: caricamento bloccato"+(pct?" al "+pct.toFixed(1)+"% della quota gratuita":"")+". Nessun passaggio automatico a pagamento.");
  }
  if(uploadBatchState){
    uploadBatchState.quotaWarning=pct>=85
      ? "⚠ QUOTA GRATUITA: "+pct.toFixed(1)+"% previsto · soglia di blocco 95%"
      : (pct>=70 ? "Quota gratuita: "+pct.toFixed(1)+"% previsto" : "");
    if(uploadBatchState.quotaWarning)renderUploadProgress();
  }
  return state;
}
async function storageUploadWithProgress(file,path,mime,onProgress){
  await checkFreeMediaQuota(file&&file.size);
  const auth=await sb.auth.getSession();
  if(auth.error)throw auth.error;
  const session=auth.data&&auth.data.session;
  if(!session||!session.access_token)throw new Error("Sessione non disponibile per il caricamento.");
  const encodedPath=String(path).split("/").map(function(part){return encodeURIComponent(part)}).join("/");
  const endpoint=SUPABASE_URL+"/storage/v1/object/f1-content-media/"+encodedPath;
  return new Promise(function(resolve,reject){
    const xhr=new XMLHttpRequest();
    xhr.open("POST",endpoint,true);
    xhr.setRequestHeader("Authorization","Bearer "+session.access_token);
    xhr.setRequestHeader("apikey",SUPABASE_KEY);
    xhr.setRequestHeader("x-upsert","false");
    xhr.setRequestHeader("Content-Type",mime||"application/octet-stream");
    xhr.upload.onprogress=function(ev){
      if(ev.lengthComputable&&onProgress)onProgress(ev.loaded,ev.total);
    };
    xhr.onload=function(){
      if(xhr.status>=200&&xhr.status<300){resolve({status:xhr.status,response:xhr.responseText});return}
      let message="Storage upload failed ("+xhr.status+")";
      try{const body=JSON.parse(xhr.responseText||"{}");message=body.message||body.error||message}catch(_){}
      reject(new Error(message));
    };
    xhr.onerror=function(){reject(new Error("Errore di rete durante il caricamento in cloud."))};
    xhr.onabort=function(){reject(new Error("Caricamento annullato."))};
    xhr.send(file);
  });
}

function isHeicName(value){return /\.(heic|heif)$/i.test(String(value||"").trim())}
function isHeicMime(value){
  return ["image/heic","image/heif","image/heic-sequence","image/heif-sequence"].includes(String(value||"").toLowerCase());
}
function isHeicFile(file){return !!file&&(isHeicName(file.name)||isHeicMime(file.type))}
function isHeicMedia(media){return !!media&&(isHeicName(media.file_name)||isHeicName(media.storage_path)||isHeicMime(media.mime_type))}
function heicPngName(name){
  const raw=String(name||"immagine.heic").replace(/\.(heic|heif)$/i,"");
  return (raw||"immagine")+".png";
}
async function verifyPngBlob(blob){
  if(!blob||!(blob instanceof Blob))throw new Error("PNG non valido: Blob mancante.");
  if(blob.size<=0)throw new Error("PNG non valido: file vuoto.");
  if(String(blob.type||"").toLowerCase()!=="image/png")throw new Error("PNG non valido: MIME "+String(blob.type||"sconosciuto")+".");
  let width=0,height=0,bitmap=null,url="";
  try{
    if(typeof createImageBitmap==="function"){
      bitmap=await createImageBitmap(blob);width=bitmap.width;height=bitmap.height;
    }else{
      url=URL.createObjectURL(blob);
      const dims=await new Promise(function(resolve,reject){
        const img=new Image();
        img.onload=function(){resolve({width:img.naturalWidth||img.width,height:img.naturalHeight||img.height})};
        img.onerror=function(){reject(new Error("Decodifica PNG non riuscita."))};
        img.src=url;
      });
      width=dims.width;height=dims.height;
    }
  }finally{
    if(bitmap&&bitmap.close)bitmap.close();
    if(url)URL.revokeObjectURL(url);
  }
  if(!(width>0&&height>0))throw new Error("PNG non valido: dimensioni immagine mancanti.");
  return {width:width,height:height,size:blob.size};
}
async function convertHeicToPng(file){
  if(!isHeicFile(file))throw new Error("Il file non è HEIC/HEIF.");
  if(typeof window.heic2any!=="function")throw new Error("Motore HEIC non disponibile. Ricarica la pagina.");
  const converted=await window.heic2any({blob:file,toType:"image/png"});
  const blob=Array.isArray(converted)?converted[0]:converted;
  await verifyPngBlob(blob);
  return new File([blob],heicPngName(file.name),{type:"image/png",lastModified:file.lastModified||Date.now()});
}
async function processMediaBeforeUpload(file){
  if(!isHeicFile(file))return {file:file,converted:false,originalFile:file};
  uploadBatchState.status="CONVERTING_HEIC";
  uploadBatchState.currentStage="HEIC RILEVATO · CONVERSIONE AUTOMATICA IN PNG";
  uploadBatchState.samples=[];
  uploadBatchState.bytesPerSecond=0;
  uploadBatchState.estimatedSecondsRemaining=null;
  renderUploadProgress();
  const png=await convertHeicToPng(file);
  uploadBatchState.totalBytes=Math.max(0,uploadBatchState.totalBytes-(Number(file.size)||0)+(Number(png.size)||0));
  uploadBatchState.currentStage="✓ CONVERSIONE COMPLETATA · "+png.name;
  renderUploadProgress();
  return {file:png,converted:true,originalFile:file,engine:"heic2any-0.0.4"};
}
async function verifyConvertedMedia(media){
  if(!media||String(media.owner_id)!==String(user.id))throw new Error("Verifica PNG bloccata: owner_id non corrispondente.");
  if(selectedClientId&&String(media.client_id)!==String(selectedClientId))throw new Error("Verifica PNG bloccata: client_id non corrispondente.");
  const dl=await sb.storage.from("f1-content-media").download(media.storage_path);
  if(dl.error)throw dl.error;
  await verifyPngBlob(dl.data);
  return true;
}
async function cleanupOriginalHeic(media){
  if(!media||!isHeicMedia(media))return;
  if(String(media.owner_id)!==String(user.id))throw new Error("Pulizia HEIC bloccata: owner_id non corrispondente.");
  if(selectedClientId&&String(media.client_id)!==String(selectedClientId))throw new Error("Pulizia HEIC bloccata: client_id non corrispondente.");
  const ownerPrefix=String(user.id)+"/";
  if(!String(media.storage_path||"").startsWith(ownerPrefix))throw new Error("Pulizia HEIC bloccata: storage_path fuori owner.");
  const refs=await sb.from("f1_content_media").select("id,content_id,storage_path").eq("storage_path",media.storage_path).neq("id",media.id).eq("owner_id",user.id);
  if(refs.error)throw refs.error;
  if(!(refs.data||[]).length){
    const rm=await sb.storage.from("f1-content-media").remove([media.storage_path]);
    if(rm.error)throw rm.error;
  }
  const del=await sb.from("f1_content_media").delete().eq("id",media.id).eq("owner_id",user.id).eq("client_id",media.client_id);
  if(del.error)throw del.error;
}
async function replaceHeicWithPngMedia(media,pngFile){
  if(!media||!isHeicMedia(media))throw new Error("Media HEIC non valido.");
  if(String(media.owner_id)!==String(user.id))throw new Error("Conversione bloccata: owner_id non corrispondente.");
  if(selectedClientId&&String(media.client_id)!==String(selectedClientId))throw new Error("Conversione bloccata: client_id non corrispondente.");
  const pngName=heicPngName(media.file_name),base=pngName.toLowerCase();
  const existing=await sb.from("f1_content_media").select("*").eq("content_id",media.content_id).eq("client_id",media.client_id).eq("owner_id",user.id);
  if(existing.error)throw existing.error;
  const reusable=(existing.data||[]).find(function(x){return String(x.file_name||"").toLowerCase()===base&&String(x.mime_type||"").toLowerCase()==="image/png"});
  if(reusable){
    await verifyConvertedMedia(reusable);
    await cleanupOriginalHeic(media);
    return reusable;
  }
  const safe=pngName.replace(/[^a-zA-Z0-9._-]+/g,"_");
  const path=user.id+"/"+media.client_id+"/"+media.content_id+"/"+crypto.randomUUID()+"-"+safe;
  await storageUploadWithProgress(pngFile,path,"image/png",function(loaded,total){
    uploadBatchState.status="UPLOADING";
    uploadBatchState.currentStage="UPLOAD PNG IN CLOUD";
    uploadBatchState.uploadedBytes=Math.min(uploadBatchState.totalBytes,uploadBatchState.uploadedBytes+Math.max(0,(Number(loaded)||0)-(Number(uploadBatchState._lastExistingLoaded)||0)));
    uploadBatchState._lastExistingLoaded=Number(loaded)||0;
    calculateUploadSpeed(uploadBatchState.uploadedBytes);renderUploadProgress();
  });
  uploadBatchState._lastExistingLoaded=0;
  const ins=await sb.from("f1_content_media").insert({
    owner_id:user.id,content_id:media.content_id,client_id:media.client_id,file_name:safe,
    mime_type:"image/png",storage_path:path,file_size:pngFile.size,source:"HEIC2ANY",
    whatsapp_message_id:media.whatsapp_message_id||null
  }).select().single();
  if(ins.error){
    try{await sb.storage.from("f1-content-media").remove([path])}catch(_){}
    throw ins.error;
  }
  try{
    await verifyConvertedMedia(ins.data);
  }catch(e){
    try{await sb.storage.from("f1-content-media").remove([path])}catch(_){}
    try{await sb.from("f1_content_media").delete().eq("id",ins.data.id).eq("owner_id",user.id)}catch(_){}
    throw e;
  }
  await cleanupOriginalHeic(media);
  return ins.data;
}
async function convertExistingHeicMedia(media){
  if(!media||!isHeicMedia(media))return null;
  if(String(media.owner_id)!==String(user.id))throw new Error("Conversione bloccata: owner_id non corrispondente.");
  if(selectedClientId&&String(media.client_id)!==String(selectedClientId))throw new Error("Conversione bloccata: client_id non corrispondente.");
  uploadBatchState.status="CONVERTING_HEIC";
  uploadBatchState.currentFileName=media.file_name||"HEIC";
  uploadBatchState.currentStage="DOWNLOAD HEIC DAL CLOUD · CONVERSIONE IN PNG";
  renderUploadProgress();
  const dl=await sb.storage.from("f1-content-media").download(media.storage_path);
  if(dl.error)throw dl.error;
  const original=new File([dl.data],media.file_name||"immagine.heic",{type:isHeicMime(media.mime_type)?media.mime_type:"image/heic"});
  const png=await convertHeicToPng(original);
  uploadBatchState.totalBytes=Math.max(0,uploadBatchState.totalBytes-(Number(media.file_size)||0)+(Number(png.size)||0));
  const replacement=await replaceHeicWithPngMedia(media,png);
  const item=(items||[]).find(function(x){return x.id===media.content_id});
  if(item){
    const client=(clients||[]).find(function(x){return x.id===item.client_id});
    if(client){
      const plan=itemPlan(item,client);
      plan.media_conversion={converted_from:"HEIC",original_file_name:media.file_name,conversion_engine:"heic2any-0.0.4",conversion_status:"COMPLETED",converted_at:new Date().toISOString()};
      WS_PLATFORMS.forEach(function(p){
        if(plan.platforms[p.id]&&!plan.platforms[p.id].scheduled_at)plan.platforms[p.id].status=planState(client.id,p.id,"image/png",Object.assign({},item,{f1_content_media:[replacement]}));
      });
      await sb.from("f1_content_items").update({content_type:"FOTO",distribution_plan:plan,updated_at:new Date().toISOString()}).eq("id",item.id).eq("owner_id",user.id).eq("client_id",item.client_id);
    }
  }
  return replacement;
}
window.f1ConvertExistingHeicMedia=convertExistingHeicMedia;
window.f1ConvertExistingHeicForClient=async function(options){
  const opts=options||{};
  const client=currentClient();if(!client){if(!opts.automatic)alert("Seleziona prima un cliente.");return}
  const mediaRows=[];
  (items||[]).filter(function(x){return x.client_id===client.id}).forEach(function(item){
    (item.f1_content_media||[]).forEach(function(media){if(isHeicMedia(media))mediaRows.push(media)});
  });
  if(!mediaRows.length){if(!opts.automatic)alert("Nessun HEIC/HEIF da convertire per "+client.name+".");return}
  resetUploadBatch(mediaRows.map(function(m){return {name:m.file_name,size:Number(m.file_size)||0}}));
  uploadBatchState.totalFiles=mediaRows.length;
  uploadBatchState.totalBytes=mediaRows.reduce(function(sum,m){return sum+(Number(m.file_size)||0)},0);
  let ok=0;const failed=[];
  for(let i=0;i<mediaRows.length;i++){
    const media=mediaRows[i];
    uploadBatchState.currentFileNumber=i+1;
    uploadBatchState.currentFileName=media.file_name||("HEIC "+(i+1));
    uploadBatchState.convertedHeic=ok;
    uploadBatchState._lastExistingLoaded=0;
    try{
      await convertExistingHeicMedia(media);
      ok++;uploadBatchState.completedFiles=ok;uploadBatchState.convertedHeic=ok;
    }catch(e){
      failed.push({file:{name:media.file_name||"HEIC"},error:e&&e.message?e.message:String(e)});
      uploadBatchState.failedFiles=failed.length;
    }
    renderUploadProgress();
  }
  await loadAll();await renderAll();
  uploadBatchState.currentFileName="";uploadBatchState.currentStage="";
  uploadBatchState.failed=failed;
  uploadBatchState.status=failed.length?(ok?"PARTIAL_ERROR":"ERROR"):"COMPLETED";
  uploadBatchState.completedFiles=ok;uploadBatchState.failedFiles=failed.length;uploadBatchState.convertedHeic=ok;
  if(!failed.length)uploadBatchState.uploadedBytes=uploadBatchState.totalBytes;
  renderUploadProgress();
}
window.f1HeicCountForClient=function(clientId){
  let count=0;
  (items||[]).filter(function(x){return x.client_id===clientId}).forEach(function(item){(item.f1_content_media||[]).forEach(function(m){if(isHeicMedia(m))count++})});
  return count;
}
window.f1ConvertHeicForItem=async function(itemId){
  let item=(items||[]).find(function(x){return x.id===itemId});
  if(!item)return null;
  const client=(clients||[]).find(function(x){return x.id===item.client_id});
  if(!client||String(item.owner_id)!==String(user.id))throw new Error("Conversione HEIC bloccata: ownership non valida.");
  if(selectedClientId&&String(item.client_id)!==String(selectedClientId))throw new Error("Conversione HEIC bloccata: client_id non corrispondente.");
  const heics=(item.f1_content_media||[]).filter(isHeicMedia);
  if(!heics.length)return item;
  resetUploadBatch(heics.map(function(m){return {name:m.file_name,size:Number(m.file_size)||0}}));
  uploadBatchState.totalFiles=heics.length;
  uploadBatchState.totalBytes=heics.reduce(function(sum,m){return sum+(Number(m.file_size)||0)},0);
  let ok=0;const failed=[];
  for(let i=0;i<heics.length;i++){
    uploadBatchState.currentFileNumber=i+1;uploadBatchState.currentFileName=heics[i].file_name||"HEIC";
    try{await convertExistingHeicMedia(heics[i]);ok++;uploadBatchState.completedFiles=ok;uploadBatchState.convertedHeic=ok}
    catch(e){failed.push({file:{name:heics[i].file_name||"HEIC"},error:e&&e.message?e.message:String(e)});uploadBatchState.failedFiles=failed.length}
    renderUploadProgress();
  }
  await loadAll();await renderAll();
  uploadBatchState.currentFileName="";uploadBatchState.currentStage="";
  uploadBatchState.failed=failed;uploadBatchState.completedFiles=ok;uploadBatchState.failedFiles=failed.length;uploadBatchState.convertedHeic=ok;
  uploadBatchState.status=failed.length?(ok?"PARTIAL_ERROR":"ERROR"):"COMPLETED";
  if(!failed.length)uploadBatchState.uploadedBytes=uploadBatchState.totalBytes;
  renderUploadProgress();
  if(failed.length)throw new Error("CONVERSIONE HEIC NON COMPLETATA — "+failed.length+" file originali conservati.");
  item=(items||[]).find(function(x){return x.id===itemId});
  return item||null;
}

function currentClient(){return (clients||[]).find(function(x){return x.id===selectedClientId})||null}
function prefFor(client,platform){
  const prefs=client&&client.publishing_preferences&&typeof client.publishing_preferences==="object"?client.publishing_preferences:{};
  const found=prefs[platform]&&typeof prefs[platform]==="object"?prefs[platform]:{};
  const def=WS_PLATFORMS.find(function(x){return x.id===platform})||{time:"12:00"};
  return {time:String(found.time||def.time),enabled:found.enabled!==false}
}
function channelFor(clientId,platform){return (socialChannels||[]).find(function(x){return x.client_id===clientId&&x.platform===platform})||null}
function channelState(clientId,platform){
  const row=channelFor(clientId,platform);
  if(!row)return "CANALE_DA_COLLEGARE";
  try{
    if(typeof effectiveSocialState==="function"&&typeof socialCollisionMap==="function")return effectiveSocialState(row,socialCollisionMap());
  }catch(_){}
  return row.enabled&&row.verified?"COLLEGATO":(row.connection_status||"CANALE_DA_COLLEGARE");
}
function cleanTitle(name){
  return String(name||"Contenuto").replace(/\.[a-z0-9]{2,5}$/i,"").replace(/[_-]+/g," ").replace(/\s+/g," ").trim()||"Contenuto";
}
function contentTypeFromMime(mime){
  mime=String(mime||"");
  if(mime.startsWith("image/"))return "FOTO";
  if(mime.startsWith("video/"))return "VIDEO";
  if(mime.startsWith("audio/"))return "AUDIO";
  return "DOCUMENTO";
}
function classify(text){
  const s=String(text||"").toLowerCase();
  if(/matrimon|spos|cerimoni|battesim|comunion|cresim/.test(s))return "CERIMONIE";
  if(/menu|menù|piatt|risott|carne|pesce|dolce|dessert|cucin|pranzo|cena/.test(s))return "MENU";
  if(/evento|serata|party|festa|musica/.test(s))return "EVENTO";
  if(/recension|review|cliente|ospit/.test(s))return "RECENSIONE";
  if(/sala|location|esterno|vista|panoram|ristorante/.test(s))return "LOCATION";
  if(/offerta|promo|sconto|speciale/.test(s))return "PROMOZIONE";
  if(/backstage|staff|cucina|preparaz/.test(s))return "BACKSTAGE";
  return "BRANDING";
}
function contactLines(client){
  const out=[];
  if(client&&client.slug==="antica-cappella"){
    out.push("📍 Via Maritano Lino 10, Avigliana");
    out.push("📞 011 931 1155");
    out.push("🌐 anticacappella.it");
    return out.join("\n");
  }
  const place=[client&&client.address,client&&client.city].filter(Boolean).join(", ");
  if(place)out.push("📍 "+place);
  if(client&&client.phone)out.push("📞 "+client.phone);
  if(client&&client.website){
    try{out.push("🌐 "+new URL(client.website).hostname.replace(/^www\./,""))}catch(_){out.push("🌐 "+client.website)}
  }
  return out.join("\n");
}
function hashtags(client,category){
  if(client&&client.slug==="antica-cappella"){
    const base=["#AnticaCappella","#Avigliana","#Ristorante","#ValleDiSusa"];
    const extra={CERIMONIE:["#Matrimoni","#Cerimonie","#Eventi"],MENU:["#CucinaPiemontese","#Menu","#Ristorazione"],EVENTO:["#Eventi","#Serata"],LOCATION:["#Avigliana","#Location"],RECENSIONE:["#Ospitalità"],PROMOZIONE:["#EventoSpeciale"],BACKSTAGE:["#Cucina","#DietroLeQuinte"],BRANDING:["#Ristorazione"]}[category]||[];
    return Array.from(new Set(base.concat(extra)));
  }
  return ["#"+String(client&&client.name||"Brand").replace(/[^A-Za-z0-9]/g,""),"#SocialMedia"].filter(function(x){return x!=="#"});
}
function baseCaption(client,title,category,seed){
  if(String(seed||"").trim())return String(seed).trim();
  if(client&&client.slug==="antica-cappella"){
    const templates={
      CERIMONIE:"Il vostro momento speciale merita uno spazio capace di accoglierlo con cura. Scopri Antica Cappella per matrimoni, cerimonie e ricorrenze ad Avigliana.",
      MENU:"Sapori, cura e convivialità: un nuovo dettaglio della cucina di Antica Cappella.",
      EVENTO:"Un nuovo appuntamento all'Antica Cappella. Scopri tutti i dettagli e prenota il tuo tavolo.",
      LOCATION:"Gli spazi dell'Antica Cappella ad Avigliana: atmosfera, accoglienza e una location pensata per stare bene insieme.",
      RECENSIONE:"Grazie a chi sceglie Antica Cappella e condivide la propria esperienza.",
      PROMOZIONE:"Una nuova proposta dell'Antica Cappella ad Avigliana. Scopri i dettagli.",
      BACKSTAGE:"Dietro ogni servizio ci sono preparazione, attenzione e lavoro di squadra.",
      BRANDING:"Antica Cappella, Avigliana. Cucina, accoglienza, eventi e momenti da condividere."
    };
    return templates[category]||templates.BRANDING;
  }
  return String(title||client&&client.name||"Nuovo contenuto").trim();
}
function captionFor(client,title,category,base,platform){
  const contacts=contactLines(client),tags=hashtags(client,category);
  const text=String(base||baseCaption(client,title,category,"")).trim();
  if(platform==="instagram")return [text,contacts,tags.slice(0,8).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="facebook")return [text,contacts,tags.slice(0,5).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="tiktok")return [text.slice(0,700),tags.slice(0,6).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="youtube")return [title,text,contacts,tags.slice(0,5).join(" ")].filter(Boolean).join("\n\n");
  if(platform==="linkedin-page")return [text,contacts,tags.slice(0,4).join(" ")].filter(Boolean).join("\n\n");
  return text;
}
function planState(clientId,platform,mime,item){
  const type=String(mime||"").toLowerCase();
  const mediaRows=(item&&item.f1_content_media||[]);
  if(mediaRows.some(isHeicMedia)||isHeicMime(type))return "CONVERSIONE_HEIC";
  const isVideo=type.startsWith("video/"),isImage=type.startsWith("image/");
  if(!type)return "MEDIA_MISSING";
  if(!isVideo&&!isImage)return "FORMATO_NON_SUPPORTATO";
  const state=channelState(clientId,platform);
  if(state!=="COLLEGATO")return state;
  if(platform==="youtube"&&!isVideo)return "FORMATO_NON_SUPPORTATO";
  if(platform==="linkedin-page"&&isVideo)return "FORMATO_NON_SUPPORTATO";
  if(platform==="tiktok"&&isImage)return "TIKTOK_PHOTO_URL_REQUIRED";
  if(platform==="tiktok"&&isVideo){
    const s=item&&item.tiktok_settings&&typeof item.tiktok_settings==="object"?item.tiktok_settings:{};
    if(!s.consent_confirmed||!s.mode)return "TIKTOK_REVIEW_REQUIRED";
  }
  return "PRONTO";
}
function buildPlan(client,title,category,base,mime,source,item){
  const plan={version:1,source:source||"WEB",category:category||"BRANDING",created_at:new Date().toISOString(),platforms:{}};
  WS_PLATFORMS.forEach(function(p){
    const pref=prefFor(client,p.id);
    const generated=captionFor(client,title,category,base,p.id);
    plan.platforms[p.id]={
      caption:generated,
      generated_caption:generated,
      time:pref.time,
      enabled:pref.enabled,
      status:planState(client.id,p.id,mime,item),
      scheduled_at:null
    };
  });
  return plan;
}
function itemMime(item){
  const media=(item&&item.f1_content_media||[])[0];
  return media&&media.mime_type?media.mime_type:"";
}
function itemPlan(item,client){
  const existing=item&&item.distribution_plan&&item.distribution_plan.platforms?clone(item.distribution_plan):null;
  if(existing)return existing;
  const category=classify([item&&item.title,item&&item.description,item&&item.campaign].join(" "));
  return buildPlan(client,item&&item.title||"Contenuto",category,item&&item.description||item&&item.source_text||"",itemMime(item),item&&item.source||"WEB",item);
}
function sourceLabel(value){
  const s=String(value||"WEB").toUpperCase();
  return {CARTELLA:"DA CARTELLA",DRAG_DROP:"TRASCINATO",WHATSAPP:"DA WHATSAPP",WEB:"CARICATO",CHATGPT_LIBRARY:"LIBRERIA"}[s]||s;
}
function nextAt(time,dayOffset){
  const bits=String(time||"12:00").split(":").map(Number);
  const d=new Date();d.setSeconds(0,0);d.setHours(bits[0]||0,bits[1]||0,0,0);
  if(d.getTime()<=Date.now())d.setDate(d.getDate()+1);
  d.setDate(d.getDate()+(dayOffset||0));
  return d;
}
async function updatePlan(item,plan){
  const r=await sb.from("f1_content_items").update({distribution_plan:plan,updated_at:new Date().toISOString()}).eq("id",item.id).eq("client_id",item.client_id);
  if(r.error)throw r.error;
  item.distribution_plan=plan;
}
async function previewMedia(){
  const client=currentClient();if(!client)return;
  const rows=planItemsForClient(client);
  for(const item of rows){
    const host=document.querySelector('[data-ws-preview="'+item.id+'"]');if(!host)continue;
    const media=(item.f1_content_media||[])[0];if(!media)continue;
    if(isHeicMedia(media)){host.textContent="HEIC · CONVERSIONE NECESSARIA";continue}
    try{
      const url=await signedUrl(media);if(!url)continue;
      if(String(media.mime_type||"").startsWith("image/"))host.innerHTML='<img src="'+h(url)+'" alt="">';
      else if(String(media.mime_type||"").startsWith("video/"))host.innerHTML='<video src="'+h(url)+'" muted controls playsinline></video>';
      else host.textContent=media.file_name||"FILE";
    }catch(_){}
  }
}
function isImmutableItem(item){
  return !!item&&(/PUBBLICAT|PUBLISHED/i.test(String(item.status||""))||String(item.status||"")==="ARCHIVIATO");
}
function railItemMime(item){
  const media=(item&&item.f1_content_media||[])[0];
  return String(media&&media.mime_type||"").toLowerCase();
}
function railItemType(item){
  const mediaRows=(item&&item.f1_content_media||[]);
  const mime=railItemMime(item),ct=String(item&&item.content_type||"").toLowerCase();
  if(mediaRows.some(isHeicMedia))return "HEIC";
  if(mime.startsWith("image/")||/foto|image|immagine/.test(ct))return "FOTO";
  if(mime.startsWith("video/")||/video|reel|short/.test(ct))return "VIDEO";
  if(mime.startsWith("audio/")||/audio/.test(ct))return "AUDIO";
  return "ALTRO";
}
function railCalendarRows(item){
  return (calendar||[]).filter(function(x){return x.content_id===item.id});
}
function railIsScheduled(item){
  return item.status==="PROGRAMMATO"||railCalendarRows(item).some(function(x){return /PROGRAMM|SCHEDULE|QUEUE|PUBLISHING|IN PUBBLICAZIONE/i.test(String(x.status||""))});
}
function railIsPublished(item){
  return item.status==="PUBBLICATO"||railCalendarRows(item).some(function(x){return /PUBBLICAT|PUBLISHED|COMPLETED/i.test(String(x.status||""))});
}
function railMatchesFilter(item){
  if(railFilter==="TUTTI")return true;
  if(railFilter==="FOTO")return railItemType(item)==="FOTO";
  if(railFilter==="VIDEO")return railItemType(item)==="VIDEO";
  if(railFilter==="DA_LAVORARE")return ["IN ARRIVO","DA CLASSIFICARE","DA LAVORARE","IN LAVORAZIONE","DA APPROVARE"].includes(String(item.status||""));
  if(railFilter==="PRONTI")return ["PRONTO","APPROVATO"].includes(String(item.status||""));
  if(railFilter==="PROGRAMMATI")return railIsScheduled(item);
  if(railFilter==="PUBBLICATI")return railIsPublished(item);
  if(railFilter==="ARCHIVIATI")return String(item.status||"")==="ARCHIVIATO";
  return true;
}
function railScopedItems(){
  let rows=(items||[]).slice();
  if(selectedClientId)rows=rows.filter(function(x){return x.client_id===selectedClientId});
  const input=document.getElementById("contentRailSearch");
  const q=String(input&&input.value||"").trim().toLowerCase();
  if(q){
    rows=rows.filter(function(item){
      const client=(clients||[]).find(function(x){return x.id===item.client_id});
      const plan=item.distribution_plan&&typeof item.distribution_plan==="object"?item.distribution_plan:{};
      const hay=[
        item.title,item.description,item.campaign,item.status,item.content_type,
        plan.category,client&&client.name,(item.tags||[]).join(" ")
      ].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }
  rows=rows.filter(railMatchesFilter);
  if(railSort==="vecchi"){
    rows.sort(function(a,b){return new Date(a.created_at||0)-new Date(b.created_at||0)});
  }else if(railSort==="programmati"){
    rows.sort(function(a,b){
      const aa=railCalendarRows(a).map(function(x){return new Date(x.publication_at||0).getTime()}).filter(Boolean).sort()[0]||Number.MAX_SAFE_INTEGER;
      const bb=railCalendarRows(b).map(function(x){return new Date(x.publication_at||0).getTime()}).filter(Boolean).sort()[0]||Number.MAX_SAFE_INTEGER;
      return aa-bb;
    });
  }else if(railSort==="da_lavorare"){
    const rank={"DA LAVORARE":0,"IN ARRIVO":1,"DA CLASSIFICARE":2,"IN LAVORAZIONE":3,"DA APPROVARE":4};
    rows.sort(function(a,b){return (rank[a.status]??99)-(rank[b.status]??99)||new Date(b.created_at||0)-new Date(a.created_at||0)});
  }else{
    rows.sort(function(a,b){return new Date(b.created_at||0)-new Date(a.created_at||0)});
  }
  if(selectedRailContentId&&!rows.some(function(x){return x.id===selectedRailContentId})){
    const selected=(items||[]).find(function(x){return x.id===selectedRailContentId});
    if(!selectedClientId||!selected||selected.client_id!==selectedClientId)selectedRailContentId="";
  }
  return rows;
}
function railBadgeClass(item){
  if(railIsPublished(item))return "green";
  if(railIsScheduled(item)||["PRONTO","APPROVATO"].includes(String(item.status||"")))return "amber";
  return "";
}
window.f1SetRailFilter=function(value){
  railFilter=String(value||"TUTTI");
  document.querySelectorAll("[data-rail-filter]").forEach(function(btn){btn.classList.toggle("active",btn.dataset.railFilter===railFilter)});
  window.f1RenderContentRail();
};
window.f1SetRailSort=function(value){railSort=String(value||"recenti");window.f1RenderContentRail()};
window.f1ToggleContentRail=function(force){
  const rail=document.getElementById("contentRail");if(!rail)return;
  const next=typeof force==="boolean"?force:!rail.classList.contains("open");
  rail.classList.toggle("open",next);
};
window.f1ClearRailSelection=async function(){
  selectedRailContentId="";
  await window.f1RenderContentRail();
  if(window.f1RenderClientPublisherWorkspace)await window.f1RenderClientPublisherWorkspace();
};
window.f1SelectRailContent=async function(contentId){
  const item=(items||[]).find(function(x){return x.id===contentId});
  if(!item)return;
  if(selectedClientId&&item.client_id!==selectedClientId)return alert("Il contenuto non appartiene al cliente selezionato.");
  selectedRailContentId=item.id;
  if(!selectedClientId&&window.f1SetClientScope){
    window.f1SetClientScope(item.client_id);
    if(window.matchMedia&&window.matchMedia("(max-width:1050px)").matches)window.f1ToggleContentRail(false);
    return;
  }
  await window.f1RenderContentRail();
  if(window.f1RenderClientPublisherWorkspace)await window.f1RenderClientPublisherWorkspace();
  const target=document.querySelector('[data-distribution-item="'+item.id+'"]');
  if(target)target.scrollIntoView({behavior:"smooth",block:"start"});
  if(window.matchMedia&&window.matchMedia("(max-width:1050px)").matches)window.f1ToggleContentRail(false);
};
window.f1QuickProgramFromRail=async function(contentId){
  const item=(items||[]).find(function(x){return x.id===contentId});
  if(!item)return;
  if(selectedClientId&&item.client_id!==selectedClientId)return alert("Il contenuto non appartiene al cliente selezionato.");
  if(isImmutableItem(item))return alert("Il contenuto è già pubblicato o archiviato e non viene modificato.");
  if(!(item.f1_content_media||[]).length)return alert("MEDIA_MISSING — aggiungi prima un file multimediale.");
  selectedRailContentId=item.id;
  if(window.f1WorkspaceScheduleItem)await window.f1WorkspaceScheduleItem(item.id);
};
window.f1HydrateRailThumbs=async function(rows){
  for(const item of rows){
    const box=document.querySelector('[data-rail-thumb="'+item.id+'"]');if(!box)continue;
    const media=(item.f1_content_media||[])[0];if(!media){box.textContent="MEDIA MANCANTE";continue}
    if(isHeicMedia(media)){box.textContent="HEIC · CONVERSIONE NECESSARIA";continue}
    try{
      const key=String(media.storage_path||media.id||item.id);
      let url=railThumbUrlCache.get(key);
      if(!url){url=await signedUrl(media);if(url)railThumbUrlCache.set(key,url)}
      if(!url){box.textContent="NESSUNA ANTEPRIMA";continue}
      const mime=String(media.mime_type||"");
      if(mime.startsWith("image/"))box.innerHTML='<img loading="lazy" src="'+h(url)+'" alt="">';
      else if(mime.startsWith("video/"))box.innerHTML='<video src="'+h(url)+'" muted playsinline preload="metadata"></video>';
      else box.textContent=media.file_name||"FILE";
    }catch(_){box.textContent="ANTEPRIMA NON DISPONIBILE"}
  }
};
window.f1RenderContentRail=async function(){
  const host=document.getElementById("contentRailList");if(!host)return;
  const rows=railScopedItems();
  const scopedTotal=(items||[]).filter(function(x){return !selectedClientId||x.client_id===selectedClientId}).length;
  const count=document.getElementById("contentRailCount");
  if(count)count.innerHTML='<b>'+scopedTotal+' contenut'+(scopedTotal===1?'o':'i')+'</b><span>'+rows.length+' visualizzat'+(rows.length===1?'o':'i')+(rows.length!==scopedTotal?' su '+scopedTotal:'')+'</span>';
  document.querySelectorAll("[data-rail-filter]").forEach(function(btn){btn.classList.toggle("active",btn.dataset.railFilter===railFilter)});
  if(!rows.length){host.innerHTML='<div class="content-rail-empty">Nessun contenuto disponibile con i filtri selezionati.</div>';return}
  host.innerHTML=rows.map(function(item){
    const client=(clients||[]).find(function(x){return x.id===item.client_id});
    const active=selectedRailContentId===item.id?" active":"";
    const immutable=isImmutableItem(item),media=(item.f1_content_media||[])[0];
    const state=railIsPublished(item)?"PUBBLICATO":(railIsScheduled(item)?"PROGRAMMATO":String(item.status||"BOZZA"));
    const clientLine=selectedClientId?"":('<div class="rail-meta">'+h(client&&client.name||"Cliente")+'</div>');
    return '<article class="rail-card'+active+'" onclick="window.f1SelectRailContent(\''+item.id+'\')">'+
      '<div class="rail-thumb" data-rail-thumb="'+item.id+'">'+(media?"ANTEPRIMA":"MEDIA MANCANTE")+'</div>'+
      '<div class="rail-source">'+h(item.source||"WEB")+'</div>'+
      '<div class="rail-title">'+h(item.title||"Senza titolo")+'</div>'+clientLine+
      '<div class="rail-meta">'+h(new Date(item.created_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</div>'+
      '<div class="rail-badges"><span class="rail-badge">'+h(railItemType(item))+'</span><span class="rail-badge '+railBadgeClass(item)+'">'+h(state)+'</span></div>'+
      '<div class="rail-actions"><button class="btn small ghost" onclick="event.stopPropagation();window.f1SelectRailContent(\''+item.id+'\')">USA</button>'+
      '<button class="btn small primary" '+(immutable?"disabled":"")+' onclick="event.stopPropagation();window.f1QuickProgramFromRail(\''+item.id+'\')">PROGRAMMA</button>'+
      '<button class="btn small danger-bright rail-delete" onclick="event.stopPropagation();window.f1ConfirmDeleteContent(\''+item.id+'\')">ELIMINA</button></div>'+
      '</article>';
  }).join("");
  await window.f1HydrateRailThumbs(rows);
};
window.f1SelectedRailContentId=function(){return selectedRailContentId};

function intelligenceTimelineHtml(item){
  const events=(typeof intelligenceEvents!=="undefined"?intelligenceEvents:[]).filter(function(x){return x.content_id===item.id}).slice().sort(function(a,b){return new Date(a.created_at)-new Date(b.created_at)});
  const latestByStage=new Map();
  events.forEach(function(ev){latestByStage.set(String(ev.stage||"FASE"),ev)});
  const ordered=["RILEVATO","CARICATO","ANALISI","CONVERSIONE_HEIC","ANALISI_AUDIO","TRASCRIZIONE","SOTTOTITOLAZIONE","CAPTION","PROGRAMMATO","PRONTO_PER_APPROVAZIONE","PUBBLICATO","ERRORE"];
  const rows=[];
  ordered.forEach(function(stage){if(latestByStage.has(stage))rows.push(latestByStage.get(stage))});
  latestByStage.forEach(function(ev,stage){if(!ordered.includes(stage))rows.push(ev)});
  if(!rows.length){
    rows.push({stage:"RILEVATO",status:"WAITING",message:"F1 Social Intelligence prenderà automaticamente in carico il contenuto.",progress:5});
  }
  return '<div class="intelligence-timeline">'+rows.map(function(ev){
    const state=String(ev.status||"").toUpperCase();
    const cls=state==="COMPLETED"?"done":(state==="ERROR"?"error":(state==="BLOCKED"?"blocked":"running"));
    return '<div class="intel-step '+cls+'"><span class="intel-dot"></span><div><b>'+h(String(ev.stage||"FASE").replaceAll("_"," "))+'</b><small>'+h(ev.message||state||"In lavorazione")+'</small></div></div>';
  }).join("")+'</div>';
}
function intelligenceApprovalLabel(client){
  return client&&client.approval_required?"IMMOBILIARE · APPROVAZIONE FINALE":"AUTOPILOT · PUBBLICAZIONE AUTOMATICA";
}
window.f1ToggleIntelligenceTimes=function(show){
  const panel=document.getElementById("intelligenceTimePanel");if(!panel)return;
  panel.classList.toggle("hidden",!show);
};
window.f1KeepCurrentTimes=function(){
  window.f1ToggleIntelligenceTimes(false);
};
window.f1ProceedIntelligence=async function(){
  const client=currentClient();if(!client)return;
  await window.f1WorkspaceProgramAll();
};

function planItemsForClient(client){
  const own=(items||[]).filter(function(x){return x.client_id===client.id});
  if(selectedRailContentId){
    const selected=own.find(function(x){return x.id===selectedRailContentId});
    return selected?[selected]:[];
  }
  return own.filter(function(x){
    return x.status!=="ARCHIVIATO"&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""));
  }).slice(0,12);
}
window.f1RenderClientPublisherWorkspace=async function(){
  const root=document.getElementById("clientPublisherWorkspace");if(!root)return;
  const client=currentClient();
  if(!client){root.classList.add("hidden");root.innerHTML="";return}
  root.classList.remove("hidden");
  const heicCount=window.f1HeicCountForClient?window.f1HeicCountForClient(client.id):0;
  const prefs=WS_PLATFORMS.map(function(p){
    const pref=prefFor(client,p.id),state=channelState(client.id,p.id);
    return '<div class="publish-time"><b>'+h(p.label)+' · '+h(state)+'</b><input type="time" value="'+h(pref.time)+'" onchange="window.f1WorkspaceSaveTime(\''+client.id+'\',\''+p.id+'\',this.value)"></div>';
  }).join("");
  const rows=planItemsForClient(client);
  const cards=rows.map(function(item){
    const plan=itemPlan(item,client),media=(item.f1_content_media||[])[0],mime=media&&media.mime_type||"";
    const locked=isImmutableItem(item);
    const pRows=WS_PLATFORMS.map(function(p){
      const data=plan.platforms[p.id]||{},state=planState(client.id,p.id,mime,item);
      const shown=data.scheduled_at?"PROGRAMMATO":(data.status||state);
      return '<div class="distribution-row">'+
        '<div><b>'+h(p.label)+'</b><div class="meta">'+h(data.time||prefFor(client,p.id).time)+'</div></div>'+
        '<div><span class="badge '+(shown==="PROGRAMMATO"||shown==="PRONTO"?"green":shown==="COLLEGATO"?"green":"")+'">'+h(shown)+'</span>'+(data.scheduled_at?'<div class="meta">'+h(new Date(data.scheduled_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</div>':"")+'</div>'+
        '<textarea '+(locked?'readonly title="Contenuto pubblicato/archiviato: sola lettura"':'onchange="window.f1WorkspaceSaveCaption(\''+item.id+'\',\''+p.id+'\',this.value)"')+'>'+h(data.caption||"")+'</textarea>'+
        '<div class="row-actions">'+(locked?'':'<button class="btn tiny ghost" onclick="window.f1WorkspaceRegenerate(\''+item.id+'\',\''+p.id+'\')">RIGENERA</button><button class="btn tiny ghost" onclick="window.f1WorkspaceResetCaption(\''+item.id+'\',\''+p.id+'\')">RIPRISTINA</button>')+'<button class="btn tiny ghost" onclick="window.f1WorkspaceCopyCaption(\''+item.id+'\',\''+p.id+'\')">COPIA</button></div>'+
      '</div>';
    }).join("");
    return '<article class="distribution-card '+(selectedRailContentId===item.id?'rail-focused':'')+'" data-distribution-item="'+item.id+'">'+
      '<div class="distribution-main"><div class="distribution-preview" data-ws-preview="'+item.id+'">ANTEPRIMA</div><div class="distribution-title"><div class="publisher-source">'+h(sourceLabel(item.source))+'</div><h3>'+h(item.title||"Contenuto")+'</h3><div class="meta">'+h(plan.category||item.campaign||"CONTENUTO")+' · '+h(item.status||"")+(locked?' · SOLA LETTURA':'')+'</div><div class="row">'+(locked?'':'<button class="btn small green" onclick="window.f1WorkspaceScheduleItem(\''+item.id+'\')">PROGRAMMA SU TUTTI I SOCIAL</button>')+'<button class="btn small danger-bright" onclick="window.f1ConfirmDeleteContent(\''+item.id+'\')">ELIMINA</button></div></div></div>'+
      intelligenceTimelineHtml(item)+
      '<div class="distribution-channels">'+pRows+'</div></article>';
  }).join("");
  const folderPath=client.profile_metadata&&client.profile_metadata.fixed_folder_path||("C:\\F1Social\\Clients\\"+String(client.slug||"cliente")+"\\INBOX");
  const rec=(typeof operatorPreferences!=="undefined"&&operatorPreferences[0]&&operatorPreferences[0].screen_recording_enabled&&operatorPreferences[0].screen_recording_consented_at);
  root.innerHTML='<section class="publisher-console">'+
    '<div class="publisher-head"><div><h2>F1 Social Intelligence · '+h(client.name)+'</h2><div class="muted">Il caricamento legge il testo della grafica e rigenera automaticamente le caption per ogni social.</div></div><div class="publisher-actions"><span class="badge green">INTELLIGENCE ATTIVA</span><span class="badge '+(client.approval_required?"amber":"green")+'">'+h(intelligenceApprovalLabel(client))+'</span>'+(rec?'<span class="badge rec-consent">● REC CONSENSO ATTIVO</span>':'')+(heicCount?'<button class="btn small amber" onclick="window.f1ConvertExistingHeicForClient()">CONVERTI HEIC IN CLOUD ('+heicCount+')</button>':'')+'<button class="btn small green" onclick="window.f1WorkspaceProgramAll()">PROGRAMMA TUTTO</button></div></div>'+
    '<div class="intelligence-command"><button type="button" class="intel-folder-mini" title="'+h(folderPath)+'" aria-label="Cartella automatica '+h(folderPath)+'" onclick="document.getElementById(\'workspaceFolderInput\').click()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5.5h6l2 2H21a1 1 0 0 1 1 1v9.5a1.5 1.5 0 0 1-1.5 1.5h-17A1.5 1.5 0 0 1 2 18V7a1.5 1.5 0 0 1 1-1.5Zm0 4V18a.5.5 0 0 0 .5.5h17a.5.5 0 0 0 .5-.5V9.5H3Z"/></svg></button><div class="intel-command-actions"><button class="btn small ghost" onclick="window.f1KeepCurrentTimes()">MANTIENI ORARI ATTUALI</button><button class="btn small ghost" onclick="window.f1ToggleIntelligenceTimes(true)">MODIFICA ORARI</button><button class="btn small green" onclick="window.f1ProceedIntelligence()">PROCEDI</button></div></div>'+
    '<div class="ingest-grid">'+
      '<button class="ingest-action" onclick="window.f1WorkspaceOpenWhatsApp()"><b>DA WHATSAPP</b><span>Importa messaggi e media ricevuti per questo cliente.</span></button>'+
      '<button class="ingest-action" onclick="document.getElementById(\'workspaceFolderInput\').click()"><b>DA CARTELLA</b><span>Seleziona una cartella con immagini e video.</span></button>'+
      '<button class="ingest-action" onclick="document.getElementById(\'workspaceFileInput\').click()"><b>DA FILE</b><span>Seleziona più contenuti dal computer.</span></button>'+
      '<div id="workspaceDropZone" class="client-dropzone" onclick="document.getElementById(\'workspaceFileInput\').click()" ondragover="window.f1WorkspaceDrag(event,true)" ondragleave="window.f1WorkspaceDrag(event,false)" ondrop="window.f1WorkspaceDrop(event)"><b>TRASCINA QUI I CONTENUTI</b><div class="meta">Foto, video e documenti. Ogni file diventa un contenuto distribuibile.</div></div>'+
      '<input id="workspaceFileInput" type="file" multiple accept="image/*,video/*,audio/*,.pdf,.doc,.docx" hidden onchange="window.f1WorkspaceInputFiles(this.files,\'DRAG_DROP\')">'+
      '<input id="workspaceFolderInput" type="file" webkitdirectory directory multiple hidden onchange="window.f1WorkspaceInputFiles(this.files,\'CARTELLA\')">'+
    '</div>'+
    '<div id="workspaceUploadProgress" class="upload-progress hidden"></div>'+
    '<div id="intelligenceTimePanel" class="intelligence-time-panel hidden"><div class="section-title" style="margin-top:12px"><h3 style="margin:0">Modifica orari di distribuzione</h3><button class="btn small ghost" onclick="window.f1ToggleIntelligenceTimes(false)">CHIUDI</button></div><div class="publish-times">'+prefs+'</div></div>'+
    '<div class="section-title" style="margin-top:14px"><h3 style="margin:0">Come verranno distribuiti</h3><span class="muted">Le caption restano modificabili fino alla pubblicazione</span></div>'+
    '<div class="distribution-list">'+(cards||'<div class="publisher-empty">Nessun contenuto con piano di distribuzione. Carica un file da WhatsApp, cartella o trascinamento.</div>')+'</div>'+
  '</section>';
  renderUploadProgress();
  await previewMedia();
  if(heicCount&&!heicAutoMigrationRunning&&!heicAutoMigrationAttempted.has(client.id)){
    heicAutoMigrationAttempted.add(client.id);
    setTimeout(async function(){
      if(heicAutoMigrationRunning)return;
      heicAutoMigrationRunning=true;
      try{await window.f1ConvertExistingHeicForClient({automatic:true})}
      catch(e){console.error("HEIC_AUTO_MIGRATION",e)}
      finally{heicAutoMigrationRunning=false}
    },350);
  }
};

window.f1WorkspaceSaveTime=async function(clientId,platform,value){
  const client=(clients||[]).find(function(x){return x.id===clientId});if(!client||!/^\d{2}:\d{2}$/.test(value))return;
  const prefs=clone(client.publishing_preferences||{}),current=prefs[platform]&&typeof prefs[platform]==="object"?prefs[platform]:{};
  prefs[platform]=Object.assign({},current,{time:value,enabled:true});prefs.timezone=client.timezone||"Europe/Rome";prefs.review_before_schedule=!!client.approval_required;prefs.intelligence_auto_pipeline=true;prefs.auto_schedule=true;
  const r=await sb.from("f1_content_clients").update({publishing_preferences:prefs,updated_at:new Date().toISOString()}).eq("id",clientId);
  if(r.error)return alert(r.error.message);
  client.publishing_preferences=prefs;
  const affected=(items||[]).filter(function(x){return x.client_id===clientId&&x.distribution_plan&&x.distribution_plan.platforms&&x.distribution_plan.platforms[platform]});
  for(const item of affected){
    const plan=clone(item.distribution_plan);plan.platforms[platform].time=value;
    await updatePlan(item,plan);
  }
};
window.f1WorkspaceInputFiles=async function(fileList,source){
  const files=Array.from(fileList||[]);if(!files.length)return;
  await quickUploadFiles(files,source||"DRAG_DROP");
};
window.f1WorkspaceDrag=function(ev,on){ev.preventDefault();const z=document.getElementById("workspaceDropZone");if(z)z.classList.toggle("drag",!!on)};
window.f1WorkspaceDrop=async function(ev){ev.preventDefault();window.f1WorkspaceDrag(ev,false);await quickUploadFiles(Array.from(ev.dataTransfer&&ev.dataTransfer.files||[]),"DRAG_DROP")};

async function quickUploadFiles(files,source){
  const client=currentClient();if(!client)return alert("Seleziona prima un cliente.");
  const list=Array.from(files||[]).filter(Boolean);if(!list.length)return;
  resetUploadBatch(list);
  let successfulBytes=0;
  const failed=[];
  for(let index=0;index<list.length;index++){
    const originalFile=list[index];
    let prepared=null,uploadFile=originalFile,mime=originalFile.type||"application/octet-stream";
    let insertedId="",path="";
    uploadBatchState.currentFileName=originalFile.name||("file-"+(index+1));
    uploadBatchState.currentFileNumber=index+1;
    uploadBatchState.currentStage=isHeicFile(originalFile)?"HEIC RILEVATO":"PREPARAZIONE FILE";
    uploadBatchState.status=isHeicFile(originalFile)?"CONVERTING_HEIC":"UPLOADING";
    uploadBatchState.uploadedBytes=successfulBytes;
    uploadBatchState.samples=[];
    uploadBatchState.bytesPerSecond=0;
    uploadBatchState.estimatedSecondsRemaining=null;
    renderUploadProgress();
    try{
      prepared=await processMediaBeforeUpload(originalFile);
      uploadFile=prepared.file;
      mime=uploadFile.type||"application/octet-stream";
      const title=cleanTitle(originalFile.name),category=classify(originalFile.name),base=baseCaption(client,title,category,"");
      const plan=buildPlan(client,title,category,base,mime,source,null);
      if(prepared.converted){
        plan.media_conversion={
          converted_from:"HEIC",original_file_name:originalFile.name,
          conversion_engine:prepared.engine||"heic2any-0.0.4",
          conversion_status:"COMPLETED",converted_at:new Date().toISOString()
        };
      }
      const ins=await sb.from("f1_content_items").insert({
        owner_id:user.id,client_id:client.id,title:title,description:base,source_text:base,
        content_type:contentTypeFromMime(mime),source:source,status:"IN ARRIVO",priority:"NORMALE",
        campaign:category,tags:hashtags(client,category).map(function(x){return x.replace(/^#/,"")}),
        notes:prepared.converted?("HEIC convertito localmente in PNG con heic2any 0.0.4. Originale: "+originalFile.name):"Piano di distribuzione automatico generato al caricamento.",
        distribution_plan:plan
      }).select().single();
      if(ins.error)throw ins.error;
      insertedId=ins.data.id;
      const safe=uploadFile.name.replace(/[^a-zA-Z0-9._-]+/g,"_");
      path=user.id+"/"+client.id+"/"+insertedId+"/"+crypto.randomUUID()+"-"+safe;
      uploadBatchState.status="UPLOADING";
      uploadBatchState.currentStage=prepared.converted?"UPLOAD PNG IN CLOUD":"UPLOAD IN CLOUD";
      renderUploadProgress();
      await storageUploadWithProgress(uploadFile,path,mime,function(loaded,total){
        uploadBatchState.status="UPLOADING";
        uploadBatchState.currentStage=prepared&&prepared.converted?"UPLOAD PNG IN CLOUD":"UPLOAD IN CLOUD";
        uploadBatchState.uploadedBytes=successfulBytes+Math.min(Number(loaded)||0,Number(total)||uploadFile.size||0);
        calculateUploadSpeed(uploadBatchState.uploadedBytes);
        renderUploadProgress();
      });
      uploadBatchState.status="SAVING";
      uploadBatchState.currentStage="REGISTRAZIONE MEDIA";
      uploadBatchState.uploadedBytes=successfulBytes+(Number(uploadFile.size)||0);
      calculateUploadSpeed(uploadBatchState.uploadedBytes);
      renderUploadProgress();
      const mr=await sb.from("f1_content_media").insert({
        owner_id:user.id,content_id:insertedId,client_id:client.id,file_name:safe,
        mime_type:mime,storage_path:path,file_size:uploadFile.size,source:prepared.converted?"HEIC2ANY":source
      }).select().single();
      if(mr.error)throw mr.error;
      if(prepared.converted){
        await verifyConvertedMedia(mr.data);
        uploadBatchState.convertedHeic++;
      }
      await sb.from("f1_intelligence_events").insert({
        owner_id:user.id,client_id:client.id,content_id:insertedId,stage:"CARICATO",status:"COMPLETED",
        message:"Contenuto caricato nel cloud. F1 Social Intelligence prosegue automaticamente.",progress:15,
        details:{source:source||"WEB",file_name:safe}
      });
      successfulBytes+=Number(uploadFile.size)||0;
      uploadBatchState.completedFiles++;
      uploadBatchState.uploadedBytes=successfulBytes;
      uploadBatchState.currentStage=prepared.converted?"✓ PNG VERIFICATO":"✓ FILE VERIFICATO";
      renderUploadProgress();
    }catch(e){
      if(path){try{await sb.storage.from("f1-content-media").remove([path])}catch(_){}}
      if(insertedId){try{await sb.from("f1_content_items").delete().eq("id",insertedId).eq("owner_id",user.id).eq("client_id",client.id)}catch(_){}}
      failed.push({file:originalFile,error:e&&e.message?e.message:String(e)});
      uploadBatchState.failedFiles=failed.length;
      uploadBatchState.failed=failed.slice();
      uploadBatchState.uploadedBytes=successfulBytes;
      uploadBatchState.currentStage=isHeicFile(originalFile)?"CONVERSIONE HEIC NON COMPLETATA · ORIGINALE CONSERVATO":"ERRORE FILE";
      uploadBatchState.samples=[];
      uploadBatchState.bytesPerSecond=0;
      uploadBatchState.estimatedSecondsRemaining=null;
      renderUploadProgress();
    }
  }
  uploadBatchState.currentFileName="";
  uploadBatchState.currentStage="";
  uploadBatchState.currentFileNumber=uploadBatchState.totalFiles;
  uploadBatchState.status="PROCESSING";
  uploadBatchState.uploadedBytes=successfulBytes;
  renderUploadProgress();
  await loadAll();
  await renderAll();
  uploadRetryFiles=failed.map(function(x){return x.file});
  uploadBatchState.failedFiles=failed.length;
  uploadBatchState.failed=failed.slice();
  uploadBatchState.status=failed.length?(uploadBatchState.completedFiles?"PARTIAL_ERROR":"ERROR"):"COMPLETED";
  if(!failed.length)uploadBatchState.uploadedBytes=uploadBatchState.totalBytes;
  uploadBatchState.estimatedSecondsRemaining=failed.length?null:0;
  renderUploadProgress();
  if(window.f1RenderContentRail)await window.f1RenderContentRail();
}

window.f1RetryFailedUploads=async function(){
  const retry=uploadRetryFiles.slice();
  if(!retry.length)return;
  await quickUploadFiles(retry,"RETRY");
}

window.f1WorkspaceSaveCaption=async function(itemId,platform,value){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  if(isImmutableItem(item))return alert("Il contenuto pubblicato o archiviato è in sola lettura.");
  const plan=itemPlan(item,client);if(!plan.platforms[platform])return;
  plan.platforms[platform].caption=String(value||"");
  plan.platforms[platform].caption_manual=true;
  plan.platforms[platform].caption_source="MANUAL";
  try{
    await updatePlan(item,plan);
    const rows=(calendar||[]).filter(function(x){return x.content_id===itemId&&x.platform===platform&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
    for(const row of rows){
      const meta=Object.assign({},row.platform_metadata||{},{caption:String(value||""),generated_caption:plan.platforms[platform].generated_caption||""});
      await sb.from("f1_content_calendar").update({platform_metadata:meta}).eq("id",row.id);
      row.platform_metadata=meta;
    }
  }catch(e){alert(e.message||String(e))}
};
window.f1WorkspaceRegenerate=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  if(isImmutableItem(item))return alert("Il contenuto pubblicato o archiviato è in sola lettura.");
  const plan=itemPlan(item,client),category=plan.category||classify(item.title);
  const graphic=plan.intelligence&&plan.intelligence.graphic_caption&&plan.intelligence.graphic_caption.text;
  const source=String(graphic||item.description||item.source_text||"").trim();
  const generated=captionFor(client,item.title,category,baseCaption(client,item.title,category,source),platform);
  plan.platforms[platform].generated_caption=generated;
  plan.platforms[platform].caption=generated;
  plan.platforms[platform].caption_manual=false;
  plan.platforms[platform].caption_source=graphic?"GRAPHIC_TEXT":"CONTENT_TEXT";
  await updatePlan(item,plan);
  const rows=(calendar||[]).filter(function(x){return x.content_id===itemId&&x.platform===platform&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
  for(const row of rows){
    const meta=Object.assign({},row.platform_metadata||{},{caption:generated,generated_caption:generated,caption_source:plan.platforms[platform].caption_source});
    await sb.from("f1_content_calendar").update({platform_metadata:meta}).eq("id",row.id);
    row.platform_metadata=meta;
  }
  await window.f1RenderClientPublisherWorkspace();
};
window.f1WorkspaceResetCaption=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  if(isImmutableItem(item))return alert("Il contenuto pubblicato o archiviato è in sola lettura.");
  const plan=itemPlan(item,client);
  plan.platforms[platform].caption=plan.platforms[platform].generated_caption||"";
  plan.platforms[platform].caption_manual=false;
  plan.platforms[platform].caption_source=(plan.intelligence&&plan.intelligence.graphic_caption&&plan.intelligence.graphic_caption.ocr_used)?"GRAPHIC_TEXT":"CONTENT_TEXT";
  await updatePlan(item,plan);await window.f1RenderClientPublisherWorkspace();
};
window.f1WorkspaceCopyCaption=async function(itemId,platform){
  const item=(items||[]).find(function(x){return x.id===itemId}),client=item&&(clients||[]).find(function(x){return x.id===item.client_id});if(!item||!client)return;
  const plan=itemPlan(item,client),value=(plan.platforms[platform]||{}).caption||"";
  try{await navigator.clipboard.writeText(value)}catch(_){prompt("Copia la caption:",value)}
};

function ensureDeleteModal(){
  let modal=document.getElementById("workspaceDeleteModal");if(modal)return modal;
  modal=document.createElement("div");modal.className="modal";modal.id="workspaceDeleteModal";
  modal.innerHTML='<div class="modal-card"><div class="section-title"><h2 id="workspaceDeleteTitle">ELIMINARE QUESTO CONTENUTO?</h2><button class="btn ghost small" onclick="document.getElementById(\'workspaceDeleteModal\').classList.remove(\'open\')">CHIUDI</button></div><div id="workspaceDeleteBody"></div><div id="workspaceDeleteActions" class="delete-modal-actions"></div></div>';
  document.body.appendChild(modal);return modal;
}
window.f1ConfirmDeleteContent=function(contentId){
  const item=(items||[]).find(function(x){return x.id===contentId});if(!item)return alert("Contenuto non trovato.");
  if(String(item.owner_id||"")!==String(user&&user.id||""))return alert("ELIMINAZIONE BLOCCATA — owner_id non corrispondente.");
  if(selectedClientId&&String(item.client_id)!==String(selectedClientId))return alert("ELIMINAZIONE BLOCCATA — il contenuto non appartiene al cliente selezionato.");
  const client=(clients||[]).find(function(x){return x.id===item.client_id}),published=railIsPublished(item)||String(item.status)==="PUBBLICATO";
  const modal=ensureDeleteModal(),title=document.getElementById("workspaceDeleteTitle"),body=document.getElementById("workspaceDeleteBody"),actions=document.getElementById("workspaceDeleteActions");
  title.textContent="ELIMINARE QUESTO CONTENUTO?";
  body.innerHTML='<div class="delete-modal-meta"><div class="subpanel"><b>Titolo</b><div>'+h(item.title||"Contenuto senza titolo")+'</div></div><div class="subpanel"><b>Cliente</b><div>'+h(client&&client.name||"Cliente")+'</div></div></div>'+
    (published?'<div class="notice warn"><b>CONTENUTO GIÀ PUBBLICATO</b><br>La cancellazione dal gestionale NON cancellerà il post già presente sulla piattaforma social. Non verrà inviata alcuna API di cancellazione remota.</div>':'<div class="notice error">Questa operazione eliminerà il contenuto dal cloud e dal gestionale.</div>');
  actions.innerHTML='<button class="btn ghost" onclick="document.getElementById(\'workspaceDeleteModal\').classList.remove(\'open\')">ANNULLA</button><button class="btn danger-bright" onclick="window.f1DeleteContent(\''+item.id+'\',false)">ELIMINA DEFINITIVAMENTE</button>';
  modal.classList.add("open");
}
window.f1DeleteContent=async function(contentId,publishedConfirmed){
  const modal=ensureDeleteModal(),body=document.getElementById("workspaceDeleteBody"),actions=document.getElementById("workspaceDeleteActions");
  try{
    const ir=await sb.from("f1_content_items").select("*").eq("id",contentId).eq("owner_id",user.id).single();
    if(ir.error||!ir.data)throw new Error("Contenuto non disponibile o non autorizzato.");
    const item=ir.data;
    if(selectedClientId&&String(item.client_id)!==String(selectedClientId))throw new Error("ELIMINAZIONE BLOCCATA — client_id non corrispondente.");
    const published=railIsPublished(item)||String(item.status)==="PUBBLICATO";
    if(published&&!publishedConfirmed){
      body.innerHTML='<div class="notice error"><b>SECONDA CONFERMA — CONTENUTO GIÀ PUBBLICATO</b><br>Il post remoto resterà online. Verranno rimossi soltanto il contenuto locale, i media cloud del gestionale non condivisi e le programmazioni locali.</div>';
      actions.innerHTML='<button class="btn ghost" onclick="document.getElementById(\'workspaceDeleteModal\').classList.remove(\'open\')">ANNULLA</button><button class="btn danger-bright" onclick="window.f1DeleteContent(\''+contentId+'\',true)">CONFERMA ELIMINAZIONE LOCALE</button>';
      return;
    }
    modal.classList.add("deleting");
    body.innerHTML='<div class="notice warn"><b>ELIMINAZIONE IN CORSO...</b><br>Verifica proprietà, Storage e record collegati.</div>';
    actions.innerHTML='<button class="btn danger-bright" disabled>ELIMINAZIONE...</button>';

    const mr=await sb.from("f1_content_media").select("id,content_id,client_id,owner_id,storage_path").eq("content_id",contentId).eq("owner_id",user.id);
    if(mr.error)throw mr.error;
    const mediaRows=mr.data||[];
    if(mediaRows.some(function(m){return String(m.client_id)!==String(item.client_id)}))throw new Error("ELIMINAZIONE BLOCCATA — media di un altro client_id rilevato.");

    const paths=Array.from(new Set(mediaRows.map(function(m){return m.storage_path}).filter(Boolean)));
    const ownerPrefix=String(user.id)+"/";
    if(paths.some(function(p){return !String(p).startsWith(ownerPrefix)}))throw new Error("ELIMINAZIONE BLOCCATA — storage_path fuori dal perimetro owner.");
    const removable=[];
    if(paths.length){
      const refs=await sb.from("f1_content_media").select("id,content_id,storage_path").in("storage_path",paths).neq("content_id",contentId).eq("owner_id",user.id);
      if(refs.error)throw refs.error;
      const shared=new Set((refs.data||[]).map(function(x){return x.storage_path}));
      paths.forEach(function(p){if(!shared.has(p))removable.push(p)});
      if(removable.length){
        const sr=await sb.storage.from("f1-content-media").remove(removable);
        if(sr.error)throw sr.error;
      }
    }

    const er=await sb.from("f1_publication_events").select("id,status,external_id").eq("content_id",contentId).eq("owner_id",user.id);
    if(er.error)throw er.error;
    const transientIds=(er.data||[]).filter(function(e){
      return !e.external_id&&!/PUBBLICAT|PUBLISHED|COMPLETED/i.test(String(e.status||""));
    }).map(function(e){return e.id});
    if(transientIds.length){
      const de=await sb.from("f1_publication_events").delete().in("id",transientIds).eq("owner_id",user.id);
      if(de.error)throw de.error;
    }

    const del=await sb.from("f1_content_items").delete().eq("id",contentId).eq("owner_id",user.id).eq("client_id",item.client_id);
    if(del.error)throw del.error;
    items=(items||[]).filter(function(x){return x.id!==contentId});
    calendar=(calendar||[]).filter(function(x){return x.content_id!==contentId});
    if(selectedRailContentId===contentId)selectedRailContentId="";
    modal.classList.remove("deleting","open");
    await loadAll();await renderAll();
    if(window.f1RenderContentRail)await window.f1RenderContentRail();
    alert("CONTENUTO ELIMINATO");
  }catch(e){
    modal.classList.remove("deleting");
    body.innerHTML='<div class="notice error"><b>ELIMINAZIONE NON COMPLETATA</b><br>'+h(e.message||String(e))+'</div>';
    actions.innerHTML='<button class="btn ghost" onclick="document.getElementById(\'workspaceDeleteModal\').classList.remove(\'open\')">CHIUDI</button>';
  }
}

async function scheduleOne(item,dayOffset){
  const client=(clients||[]).find(function(x){return x.id===item.client_id});if(!client)return 0;
  const plan=itemPlan(item,client),mime=itemMime(item);let scheduled=0;
  for(const p of WS_PLATFORMS){
    const data=plan.platforms[p.id]||{},ch=channelFor(client.id,p.id),state=planState(client.id,p.id,mime,item);
    const target=nextAt(data.time||prefFor(client,p.id).time,dayOffset||0);
    if(state==="MEDIA_MISSING"||state==="CONVERSIONE_HEIC"||state==="FORMATO_NON_SUPPORTATO"||state==="TIKTOK_PHOTO_URL_REQUIRED"||state==="TIKTOK_REVIEW_REQUIRED"){
      data.status=state;data.scheduled_at=null;plan.platforms[p.id]=data;continue;
    }
    const calendarStatus=state==="PRONTO"?(client.approval_required?"APPROVAZIONE_RICHIESTA":"PROGRAMMATO"):"CANALE_DA_COLLEGARE";
    const payload={
      owner_id:user.id,content_id:item.id,client_id:client.id,platform:p.id,publication_at:target.toISOString(),
      status:calendarStatus,provider:ch&&ch.provider||"oauth_broker",retry_count:0,error:null,
      platform_metadata:{
        caption:data.caption||"",generated_caption:data.generated_caption||"",source_upload:item.source||"WEB",
        auto_distribution:true,selected_time:data.time||prefFor(client,p.id).time,distribution_version:plan.version||1
      }
    };
    const existing=(calendar||[]).find(function(x){return x.content_id===item.id&&x.platform===p.id&&!/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
    if(existing){
      const u=await sb.from("f1_content_calendar").update(payload).eq("id",existing.id);if(u.error)throw u.error;
    }else{
      const ins=await sb.from("f1_content_calendar").insert(payload);if(ins.error)throw ins.error;
    }
    data.status=calendarStatus;data.scheduled_at=target.toISOString();plan.platforms[p.id]=data;
    if(calendarStatus==="PROGRAMMATO"||calendarStatus==="APPROVAZIONE_RICHIESTA")scheduled++;
  }
  await updatePlan(item,plan);
  const status=Object.values(plan.platforms).some(function(x){return x.scheduled_at})?(client.approval_required?"DA APPROVARE":"PROGRAMMATO"):"PRONTO";
  const u=await sb.from("f1_content_items").update({status:status}).eq("id",item.id);if(u.error)throw u.error;
  item.status=status;
  return scheduled;
}
window.f1WorkspaceScheduleItem=async function(itemId){
  let item=(items||[]).find(function(x){return x.id===itemId});if(!item)return;
  if(isImmutableItem(item))return alert("Il contenuto è già pubblicato o archiviato e non viene riprogrammato.");
  let client=(clients||[]).find(function(x){return x.id===item.client_id});
  try{
    if((item.f1_content_media||[]).some(isHeicMedia)){
      item=await window.f1ConvertHeicForItem(itemId);
      if(!item)return;
      client=(clients||[]).find(function(x){return x.id===item.client_id});
    }
    if(client&&!client.auto_publish){
      const u=await sb.from("f1_content_clients").update({auto_publish:true,automation_status:"AUTOMAZIONE ATTIVA"}).eq("id",client.id);if(u.error)throw u.error;
      client.auto_publish=true;
    }
    const count=await scheduleOne(item,0);await loadAll();await renderAll();
    alert(client&&client.approval_required?("Piano creato. "+count+" pubblicazioni immobiliari sono pronte e attendono la tua approvazione finale."):("Piano creato. "+count+" canali già collegati proseguiranno automaticamente; gli altri restano in attesa del collegamento."));
  }catch(e){alert(e.message||String(e))}
};
window.f1WorkspaceProgramAll=async function(){
  const client=currentClient();if(!client)return;
  let list=planItemsForClient(client).filter(function(x){return !/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
  if(!list.length)return alert("Non ci sono nuovi contenuti da programmare.");
  try{
    if(list.some(function(x){return (x.f1_content_media||[]).some(isHeicMedia)})){
      await window.f1ConvertExistingHeicForClient();
      list=planItemsForClient(client).filter(function(x){return !/PUBBLICAT|PUBLISHED/i.test(String(x.status||""))});
    }
    const u=await sb.from("f1_content_clients").update({auto_publish:true,automation_status:"AUTOMAZIONE ATTIVA"}).eq("id",client.id);if(u.error)throw u.error;
    client.auto_publish=true;
    let ready=0;
    const ordered=list.slice().reverse();
    for(let i=0;i<ordered.length;i++)ready+=await scheduleOne(ordered[i],i);
    await loadAll();await renderAll();
    alert(client.approval_required?("Preparazione completata per "+ordered.length+" contenuti. "+ready+" pubblicazioni immobiliari attendono approvazione finale."):("Programmazione automatica completata per "+ordered.length+" contenuti. "+ready+" pubblicazioni sono pronte sui canali collegati."));
  }catch(e){alert("Programmazione non completata: "+(e.message||String(e)))}
};

function ensureWhatsAppModal(){
  let modal=document.getElementById("workspaceWaModal");if(modal)return modal;
  modal=document.createElement("div");modal.className="modal";modal.id="workspaceWaModal";
  modal.innerHTML='<div class="modal-card"><div class="section-title"><h2>Importa da WhatsApp</h2><button class="btn ghost small" onclick="document.getElementById(\'workspaceWaModal\').classList.remove(\'open\')">CHIUDI</button></div><div id="workspaceWaList" class="calendar-list"></div></div>';
  document.body.appendChild(modal);return modal;
}
window.f1WorkspaceOpenWhatsApp=async function(){
  const client=currentClient();if(!client)return;
  const modal=ensureWhatsAppModal(),list=document.getElementById("workspaceWaList");list.innerHTML='<div class="empty">Caricamento...</div>';modal.classList.add("open");
  const r=await sb.from("f1_whatsapp_logs").select("id,message_id,message_type,message_text,media_count,result,created_at").eq("client_id",client.id).order("created_at",{ascending:false}).limit(30);
  if(r.error){list.innerHTML='<div class="notice error">'+h(r.error.message)+'</div>';return}
  list.innerHTML=(r.data||[]).map(function(x){
    return '<div class="lineitem"><b>'+h(new Date(x.created_at).toLocaleString("it-IT",{dateStyle:"short",timeStyle:"short"}))+'</b><div><b>'+h(x.message_type||"Messaggio")+'</b><div class="meta">'+h(x.message_text||"")+(x.media_count?' · '+x.media_count+' media':"")+'</div></div><button class="btn small primary" onclick="window.f1WorkspaceImportWhatsApp('+Number(x.id)+')">IMPORTA</button></div>';
  }).join("")||'<div class="publisher-empty">Nessun contenuto WhatsApp associato a '+h(client.name)+'. Quando arriveranno messaggi/media del cliente compariranno qui automaticamente.</div>';
};
window.f1HeicDiagnostics={
  isHeicFile:isHeicFile,
  isHeicMedia:isHeicMedia,
  heicPngName:heicPngName,
  convertHeicToPng:convertHeicToPng,
  processMediaBeforeUpload:processMediaBeforeUpload,
  verifyPngBlob:verifyPngBlob
};

window.f1WorkspaceImportWhatsApp=async function(logId){
  const client=currentClient();if(!client)return;
  try{
    const r=await sb.from("f1_whatsapp_logs").select("*").eq("id",logId).eq("client_id",client.id).single();if(r.error)throw r.error;
    const log=r.data,key=String(log.message_id||("wa-"+log.id));
    const exists=await sb.from("f1_content_items").select("id").eq("client_id",client.id).eq("whatsapp_thread_key",key).limit(1);
    if(exists.data&&exists.data.length)return alert("Questo contenuto WhatsApp è già stato importato.");
    const title="WhatsApp · "+new Date(log.created_at).toLocaleDateString("it-IT"),category=classify(log.message_text||""),base=baseCaption(client,title,category,log.message_text||"");
    let mediaSource=await sb.from("f1_content_media").select("*").eq("client_id",client.id).eq("whatsapp_message_id",log.message_id||"");
    if(mediaSource.error)throw mediaSource.error;
    const whatsappHeic=(mediaSource.data||[]).filter(isHeicMedia);
    for(const m of whatsappHeic)await convertExistingHeicMedia(m);
    if(whatsappHeic.length){
      mediaSource=await sb.from("f1_content_media").select("*").eq("client_id",client.id).eq("whatsapp_message_id",log.message_id||"");
      if(mediaSource.error)throw mediaSource.error;
    }
    const first=(mediaSource.data||[])[0],mime=first&&first.mime_type||"";
    const plan=buildPlan(client,title,category,base,mime,"WHATSAPP",null);
    const ins=await sb.from("f1_content_items").insert({owner_id:user.id,client_id:client.id,title:title,description:base,source_text:base,content_type:mime?contentTypeFromMime(mime):"TESTO",source:"WHATSAPP",status:"IN ARRIVO",campaign:category,tags:hashtags(client,category).map(function(x){return x.replace(/^#/,"")}),notes:"Importato dal registro WhatsApp.",whatsapp_thread_key:key,distribution_plan:plan}).select().single();
    if(ins.error)throw ins.error;
    for(const m of (mediaSource.data||[])){
      const cp=await sb.from("f1_content_media").insert({owner_id:user.id,content_id:ins.data.id,client_id:client.id,file_name:m.file_name,mime_type:m.mime_type,storage_path:m.storage_path,file_size:m.file_size,source:"WHATSAPP",whatsapp_message_id:m.whatsapp_message_id});
      if(cp.error)throw cp.error;
    }
    document.getElementById("workspaceWaModal").classList.remove("open");await loadAll();await renderAll();
    alert("Contenuto WhatsApp importato e piano social generato.");
  }catch(e){alert(e.message||String(e))}
};

if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){if(window.f1RenderClientPublisherWorkspace)window.f1RenderClientPublisherWorkspace()});
else if(window.f1RenderClientPublisherWorkspace)window.f1RenderClientPublisherWorkspace();
})();