const enc=new TextEncoder(),dec=new TextDecoder();

function bytesToB64(bytes){
  let out='',chunk=0x8000;
  for(let i=0;i<bytes.length;i+=chunk)out+=String.fromCharCode(...bytes.subarray(i,i+chunk));
  return btoa(out);
}
function b64ToBytes(value){
  const raw=atob(value),out=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);
  return out;
}
async function derive(passphrase,salt,iterations){
  const material=await crypto.subtle.importKey('raw',enc.encode(passphrase),'PBKDF2',false,['deriveKey']);
  return crypto.subtle.deriveKey(
    {name:'PBKDF2',hash:'SHA-256',salt,iterations},
    material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']
  );
}
export async function encryptBackup(payload,passphrase){
  if(typeof passphrase!=='string'||passphrase.length<12)throw Error('La password backup deve avere almeno 12 caratteri.');
  const iterations=250000,salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
  const key=await derive(passphrase,salt,iterations);
  const plain=enc.encode(JSON.stringify(payload));
  const cipher=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,plain));
  return {
    format:'MRDH-BACKUP',version:1,created_at:new Date().toISOString(),
    kdf:{name:'PBKDF2',hash:'SHA-256',iterations,salt:bytesToB64(salt)},
    cipher:{name:'AES-GCM',iv:bytesToB64(iv)},
    data:bytesToB64(cipher)
  };
}
export async function decryptBackup(envelope,passphrase){
  if(typeof envelope==='string')envelope=JSON.parse(envelope);
  if(!envelope||envelope.format!=='MRDH-BACKUP'||envelope.version!==1)throw Error('File backup non riconosciuto.');
  if(typeof passphrase!=='string'||passphrase.length<12)throw Error('Inserisci la password usata per creare il backup.');
  const iterations=Number(envelope.kdf?.iterations);
  if(envelope.kdf?.name!=='PBKDF2'||envelope.kdf?.hash!=='SHA-256'||iterations<100000||iterations>1000000)throw Error('Parametri backup non validi.');
  if(envelope.cipher?.name!=='AES-GCM')throw Error('Cifratura backup non supportata.');
  try{
    const salt=b64ToBytes(envelope.kdf.salt),iv=b64ToBytes(envelope.cipher.iv),cipher=b64ToBytes(envelope.data);
    if(salt.length!==16||iv.length!==12||cipher.length<16)throw Error('invalid');
    const key=await derive(passphrase,salt,iterations);
    const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv},key,cipher);
    return JSON.parse(dec.decode(plain));
  }catch{
    throw Error('Password errata oppure backup danneggiato.');
  }
}
