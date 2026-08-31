const C='roleplay-v7';
const F=['./','./index.html','./manifest.webmanifest','./pack1.js','./pack2.js','./pack3.js','./pack4.js','./volume-control.js','./script-grid.js'];
const TAGS='<script src="./volume-control.js"></script><script src="./script-grid.js"></script>';

self.addEventListener('install',e=>{
  self.skipWaiting();
  e.waitUntil(caches.open(C).then(c=>c.addAll(F)));
});

self.addEventListener('activate',e=>e.waitUntil(Promise.all([
  self.clients.claim(),
  caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==C).map(k=>caches.delete(k))))
])));

function cleanHeaders(source){
  const h=new Headers(source);
  h.delete('content-length');
  h.delete('content-encoding');
  return h;
}

async function withEnhancements(resp){
  if(!resp) return resp;
  const type=resp.headers.get('content-type')||'';
  if(!type.includes('text/html')) return resp;
  const html=await resp.text();
  let out=html;
  const missing=[];
  if(!out.includes('volume-control.js')) missing.push('<script src="./volume-control.js"></script>');
  if(!out.includes('script-grid.js')) missing.push('<script src="./script-grid.js"></script>');
  if(missing.length){
    const tags=missing.join('');
    out=out.includes('</body>')?out.replace('</body>',tags+'</body>'):out+tags;
  }
  return new Response(out,{status:resp.status,statusText:resp.statusText,headers:cleanHeaders(resp.headers)});
}

self.addEventListener('fetch',e=>{
  if(e.request.mode==='navigate'){
    e.respondWith(
      fetch(e.request).then(async r=>{
        const copy=r.clone();
        caches.open(C).then(c=>c.put(e.request,copy));
        return withEnhancements(r);
      }).catch(async()=>{
        const r=await caches.match(e.request)||await caches.match('./index.html');
        return withEnhancements(r);
      })
    );
    return;
  }
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(resp=>{
    const copy=resp.clone();
    caches.open(C).then(c=>c.put(e.request,copy));
    return resp;
  })));
});
