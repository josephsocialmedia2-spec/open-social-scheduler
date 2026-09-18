import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
if(!globalThis.btoa)globalThis.btoa=s=>Buffer.from(s,'binary').toString('base64');
if(!globalThis.atob)globalThis.atob=s=>Buffer.from(s,'base64').toString('binary');

const {encryptBackup,decryptBackup}=await import('../backup-crypto.mjs');
const payload={app:'Marta Ruffino Digital Hub',schema_version:1,data:{contents:[{id:'x',title:'Prova àè'}]}};
const env=await encryptBackup(payload,'password-backup-test-123');
assert.equal(env.format,'MRDH-BACKUP');
assert.equal(env.version,1);
assert.ok(env.data.length>20);
const out=await decryptBackup(env,'password-backup-test-123');
assert.deepEqual(out,payload);
await assert.rejects(()=>decryptBackup(env,'password-backup-sbagliata-123'),/Password errata|danneggiato/);

const fs=await import('node:fs');
const index=fs.readFileSync(new URL('../index.html',import.meta.url),'utf8');
const attiva=fs.readFileSync(new URL('../attiva.html',import.meta.url),'utf8');
const backup=fs.readFileSync(new URL('../backup.js',import.meta.url),'utf8');
assert.ok(index.includes("app.html?v=18"));
assert.ok(index.includes("accesso.html?v=18"));
assert.ok(!index.includes('marta_claim_owner'));
assert.ok(!attiva.includes('marta_claim_owner'));
assert.ok(!attiva.includes('/auth/v1/signup'));
assert.ok(backup.includes("enabled:false,status:'NON_CONFIGURATO'"));
assert.ok(backup.includes("status:'DA_RIVEDERE'"));
assert.ok(backup.includes("status:['PROGRAMMATO','INVIATO','MANUALE_ASSISTITO'].includes"));
for(const src of [index,attiva,backup]){
  assert.ok(!src.includes('service_role'));
  assert.ok(!src.includes('sb_secret_'));
}
console.log('Marta entry/security/backup QA: PASS');
