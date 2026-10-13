'use strict';
// Somente arquivos públicos. Nunca armazena OS, fotos, login ou respostas da API.
const CACHE = 'easy-servicos-static-v7';
const ASSETS = ['/static/app.css?v=free-os-7','/static/app.js?v=free-os-7','/static/icon-192.png','/static/icon-512.png','/static/icon-maskable-512.png','/static/offline.html','/static/logo.png','/static/apple-touch-icon.png','/static/favicon.ico'];
const STATIC_PATHS=ASSETS.map(path=>new URL(path,self.location.origin).pathname);
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('easy-servicos-static-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin)return;
  if(STATIC_PATHS.includes(url.pathname)){
    // Arquivos públicos versionados: cache local evita nova espera a cada tela.
    // A query faz parte da chave para nunca misturar versões de CSS e JavaScript.
    event.respondWith(caches.open(CACHE).then(async cache=>{
      const saved=await cache.match(event.request);
      if(saved)return saved;
      const response=await fetch(event.request);
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }));
  }else if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request).catch(()=>caches.match('/static/offline.html')));
  }
});
