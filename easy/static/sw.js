'use strict';
// Somente arquivos públicos. Nunca armazena OS, fotos, login ou respostas da API.
const CACHE = 'easy-servicos-static-v2';
const ASSETS = ['/static/app.css','/static/app.js','/static/icon-192.png','/static/icon-512.png','/static/icon-maskable-512.png','/static/offline.html','/static/logo.png','/static/apple-touch-icon.png','/static/favicon.ico'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('easy-servicos-static-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
  if(ASSETS.includes(url.pathname)){
    event.respondWith(caches.open(CACHE).then(async cache=>{
      try{const response=await fetch(event.request);if(response.ok)await cache.put(event.request,response.clone());return response;}
      catch{const saved=await cache.match(event.request);return saved||Response.error();}
    }));
  }else if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request).catch(()=>caches.match('/static/offline.html')));
  }
});
