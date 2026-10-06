const CACHE="f1-content-hub-v27-static-versioned";
const CORE=["./vendor/supabase.min.js","./vendor/heic2any-0.0.4.min.js","./client-workspace.js","./client-workspace.css","./client-health.js","./email-module.js","./email-module.css","./f1-design-system.css","./demo-v7-live.css","./demo-v7-core.js","./demo-v7-email-core.js","./demo-v7-email-csv.js","./","./index.html","./immobiliare-la-sacra.html","./f1-informa.html","./manifest.webmanifest","./icon.svg"];
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting())));
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE&&k.startsWith("f1-content-hub-")).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET")return;
  const u=new URL(e.request.url);
  if(u.origin!==self.location.origin)return;
  const marker="/f1-content-hub/";
  const pos=u.pathname.indexOf(marker);
  if(pos<0)return;
  const rel="./"+u.pathname.slice(pos+marker.length);
  if(e.request.mode==="navigate"||rel==="./"||rel==="./index.html"){
    e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put("./index.html",copy));return r}).catch(()=>caches.match("./index.html")));
    return;
  }
  if(!CORE.includes(rel))return;
  e.respondWith(caches.match(e.request).then(cached=>{
    if(cached)return cached;
    return fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));return r});
  }));
});
