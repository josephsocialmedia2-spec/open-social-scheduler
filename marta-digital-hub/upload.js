const MARTA_MAX_VIDEO_BYTES=50*1024*1024;
const MARTA_ALLOWED_VIDEO_TYPES=new Set(['video/mp4','video/quicktime','video/webm']);
let martaUploadBusy=false;

function martaDisplayFilename(name='video'){
  const clean=String(name||'video').replace(/[\u0000-\u001f\u007f]/g,'').trim()||'video';
  return clean.length<=180?clean:clean.slice(0,177)+'...';
}

function martaSafeStorageFilename(name='',mime='video/mp4'){
  const fallback=mime==='video/webm'?'.webm':mime==='video/quicktime'?'.mov':'.mp4';
  let base=String(name||'video').replace(/\.[^.]*$/,'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'');
  base=base.replace(/[^a-zA-Z0-9_-]+/g,'_').replace(/^_+|_+$/g,'').replace(/_+/g,'_').slice(0,96)||'video';
  return base+fallback;
}

async function martaVideoSignatureOk(file){
  if(!file||file.size<=0||!MARTA_ALLOWED_VIDEO_TYPES.has(file.type))return false;
  const bytes=new Uint8Array(await file.slice(0,32).arrayBuffer());
  if(file.type==='video/webm'){
    return bytes.length>=4&&bytes[0]===0x1a&&bytes[1]===0x45&&bytes[2]===0xdf&&bytes[3]===0xa3;
  }
  if(bytes.length<8)return false;
  const atom=String.fromCharCode(...bytes.slice(4,8));
  if(file.type==='video/mp4')return atom==='ftyp'||atom==='moov';
  return ['ftyp','moov','mdat','free','wide','skip'].includes(atom);
}

function martaStorageUrl(bucket,path){
  const ep=String(path).split('/').map(encodeURIComponent).join('/');
  return `${SUPA}/storage/v1/object/${encodeURIComponent(bucket)}/${ep}`;
}

async function martaDeleteStorageObject(bucket,path){
  if(!path)return true;
  const r=await fetch(martaStorageUrl(bucket,path),{method:'DELETE',headers:hdr(false)});
  if(r.ok||r.status===404)return true;
  let detail='';try{detail=await r.text()}catch{}
  throw Error(`Impossibile eliminare il file dal cloud (${r.status})${detail?' - '+detail.slice(0,120):''}`);
}

function martaUploadOriginal(file,path,onProgress){
  return new Promise((resolve,reject)=>{
    const x=new XMLHttpRequest();
    x.open('POST',martaStorageUrl('marta-content-originals',path));
    x.timeout=300000;
    x.setRequestHeader('apikey',KEY);
    x.setRequestHeader('Authorization','Bearer '+S.access_token);
    x.setRequestHeader('Content-Type',file.type);
    x.upload.onprogress=e=>{if(e.lengthComputable&&onProgress)onProgress(Math.round(100*e.loaded/e.total))};
    x.onload=()=>x.status>=200&&x.status<300?resolve():reject(Error(`Upload rifiutato dal cloud (${x.status})`));
    x.onerror=()=>reject(Error('Connessione interrotta durante l’upload'));
    x.onabort=()=>reject(Error('Upload annullato'));
    x.ontimeout=()=>reject(Error('Upload scaduto: connessione troppo lenta'));
    x.send(file);
  });
}

async function martaReserveUpload({title,category,notes,filename,mime,size}){
  const rows=await db('rpc/marta_reserve_upload',{method:'POST',body:{
    p_title:title,p_category:category,p_notes:notes,p_filename:filename,p_mime:mime,p_file_size:size
  }});
  if(!rows?.[0]?.id)throw Error('Impossibile prenotare lo spazio per il video');
  return rows[0];
}

async function martaTryDeleteReservation(id){
  if(!id)return false;
  try{await db(`contents?id=eq.${id}`,{method:'DELETE'});return true}catch{return false}
}
