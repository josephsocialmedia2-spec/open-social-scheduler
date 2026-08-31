const C='roleplay-v9';
const F=['./','./index.html','./manifest.webmanifest','./pack1.js','./pack2.js','./pack3.js','./pack4.js'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(F)))});
self.addEventListener('activate',e=>e.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==C).map(k=>caches.delete(k))))])));
self.addEventListener('fetch',e=>{if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(r=>{let c=r.clone();caches.open(C).then(x=>x.put('./index.html',c));return r}).catch(()=>caches.match('./index.html')));return}e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(resp=>{let c=resp.clone();caches.open(C).then(x=>x.put(e.request,c));return resp}))) });