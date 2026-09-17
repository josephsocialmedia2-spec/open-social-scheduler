import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { Blob } from 'node:buffer';

const src=fs.readFileSync(new URL('../upload.js',import.meta.url),'utf8');
const sandbox={
  console,Blob,Uint8Array,Set,String,Promise,setTimeout,clearTimeout,
  SUPA:'https://example.invalid',KEY:'public-test-key',S:{access_token:'test'},
  fetch:async()=>({ok:true,status:204,text:async()=>''}),
  XMLHttpRequest:function(){},hdr:()=>({}),db:async()=>[]
};
vm.createContext(sandbox);
vm.runInContext(src,sandbox,{filename:'upload.js'});

assert.equal(sandbox.martaSafeStorageFilename('à prova finale!!.MP4','video/mp4'),'a_prova_finale.mp4');
assert.equal(sandbox.martaSafeStorageFilename('../../evil<script>.mov','video/quicktime'),'evil_script.mov');
assert.equal(sandbox.martaSafeStorageFilename('','video/webm'),'video.webm');
assert.ok(sandbox.martaDisplayFilename('x'.repeat(500)).length<=180);
assert.equal(sandbox.martaDisplayFilename('\u0000\u0007 prova.mp4'),'prova.mp4');

const mp4=new Blob([Uint8Array.from([0,0,0,24,0x66,0x74,0x79,0x70,0,0,0,0])],{type:'video/mp4'});
const webm=new Blob([Uint8Array.from([0x1a,0x45,0xdf,0xa3,0,0,0,0])],{type:'video/webm'});
const fakeMp4=new Blob([Uint8Array.from([0,0,0,24,0x50,0x4b,0x03,0x04])],{type:'video/mp4'});
const badType=new Blob([Uint8Array.from([0,0,0,24,0x66,0x74,0x79,0x70])],{type:'application/octet-stream'});

assert.equal(await sandbox.martaVideoSignatureOk(mp4),true);
assert.equal(await sandbox.martaVideoSignatureOk(webm),true);
assert.equal(await sandbox.martaVideoSignatureOk(fakeMp4),false);
assert.equal(await sandbox.martaVideoSignatureOk(badType),false);
assert.equal(await sandbox.martaVideoSignatureOk(new Blob([],{type:'video/mp4'})),false);

assert.ok(!src.includes('service_role'));
assert.ok(!src.includes('sb_secret_'));
console.log('Marta upload/storage QA: PASS');
