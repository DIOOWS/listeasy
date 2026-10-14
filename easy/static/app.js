'use strict';
(() => {
 const pages=new Map(), warming=new Set(), media=matchMedia('(min-width:701px)');
 let navigation=null, sequence=0, generation=0, saving=false, installation=null, visibleURL=location.href;
 const TTL=15000;
 const authenticated=()=>document.body.classList.contains('authenticated');
 const key=url=>{const u=new URL(url,location.href);return u.pathname+u.search;};
 const formURL=form=>new URL(form.getAttribute('action')||location.href,location.href).href;
 const formMethod=form=>(form.getAttribute('method')||'get').toLowerCase();
 const formKey=form=>key(formURL(form))+'|'+formMethod(form)+'|'+(form.elements.namedItem('stage')?.value||'');
 function activate(tab){
  document.querySelectorAll('[data-tab]').forEach(button=>{const active=button===tab;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;});
  document.querySelectorAll('[data-panel]').forEach(panel=>panel.hidden=panel.id!==tab.dataset.tab);
  try{sessionStorage.setItem('easy-os-tab',tab.dataset.tab);}catch{}
 }
 function initialize(){
  const tabs=[...document.querySelectorAll('[data-tab]')];
  let saved;try{saved=sessionStorage.getItem('easy-os-tab');}catch{}
  if(tabs.length)activate(tabs.find(tab=>tab.dataset.tab===saved)||tabs[0]);
  document.querySelectorAll('[data-flow-order]').forEach(row=>row.open=media.matches);
  const install=document.getElementById('install-app'),status=document.getElementById('install-status');
  if(install)install.hidden=!installation;
  if(status&&matchMedia('(display-mode: standalone)').matches)status.textContent='Você já está usando o aplicativo instalado.';
  scheduleWarm();
 }
 function notice(host,message,error=false){
  let output=host.querySelector(':scope > .request-message');
  if(!output){output=document.createElement('p');output.className='request-message';output.setAttribute('role','status');output.setAttribute('aria-live','polite');host.append(output);}
  output.textContent=message;output.classList.toggle('request-error',error);
 }
 function clearLoading(){
  document.body.classList.remove('navigating');
  document.querySelectorAll('.nav-pending').forEach(link=>{link.classList.remove('nav-pending');link.removeAttribute('aria-busy');});
 }
 async function readPage(url,options={}){
  const response=await fetch(url,{credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'},...options});
  if(!response.headers.get('Content-Type')?.includes('text/html'))throw Error('Não foi possível abrir esta tela.');
  const html=await response.text(),doc=new DOMParser().parseFromString(html,'text/html');
  const main=doc.querySelector('main.container');
  if(!main)throw Error('Resposta incompleta. Tente novamente.');
  if(!response.ok){const message=main.querySelector('.panel p')?.textContent;throw Error(message||'Não foi possível concluir a ação.');}
  return {html,url:response.url};
 }
 function render(page,{scroll=0,preserve=[]}={}){
  const doc=new DOMParser().parseFromString(page.html,'text/html');
  const main=doc.querySelector('main.container');
  for(const original of preserve){
   const replacement=[...main.querySelectorAll('form')].find(form=>formKey(form)===formKey(original));
   if(!replacement||replacement.querySelector('fieldset[disabled]'))continue;
   // Mantém outros formulários não enviados, inclusive arquivos selecionados.
   for(const name of ['version','csrf_token']){
    const fresh=replacement.elements.namedItem(name),old=original.elements.namedItem(name);
    if(fresh&&old)old.value=fresh.value;
   }
   replacement.replaceWith(original);
  }
  document.querySelector('main.container').replaceWith(main);
  for(const selector of ['.top','.nav','.mobile-nav','#app-menu','footer']){
   const old=document.querySelector(selector),fresh=doc.querySelector(selector);
   if(old&&fresh&&(selector==='.nav'||selector==='.mobile-nav')){
    const links=node=>[...node.querySelectorAll('a')].map(link=>link.getAttribute('href')).join('|');
    if(links(old)!==links(fresh)){old.replaceWith(fresh);continue;}
    // Mantém os nós do menu montados; muda apenas a seleção ativa.
    for(const control of old.querySelectorAll('a,button')){
     const candidate=[...fresh.querySelectorAll('a,button')].find(item=>item.tagName===control.tagName&&(control.tagName==='A'?item.getAttribute('href')===control.getAttribute('href'):item.hasAttribute('data-open-menu')));
     if(candidate){control.className=candidate.className;const current=candidate.getAttribute('aria-current');if(current)control.setAttribute('aria-current',current);else control.removeAttribute('aria-current');control.removeAttribute('aria-busy');}
    }
   }else if(old&&fresh&&selector==='.top'&&old.textContent===fresh.textContent){
    const token=fresh.querySelector('[name=csrf_token]'),previous=old.querySelector('[name=csrf_token]');if(token&&previous)previous.value=token.value;
   }else if(old&&fresh)old.replaceWith(fresh);else if(old)old.remove();else if(fresh)document.body.insertBefore(fresh,main);
  }
  document.body.className=doc.body.className;
  document.title=doc.title;visibleURL=page.url;
  initialize();
  requestAnimationFrame(()=>window.scrollTo({top:scroll,behavior:'instant'}));
 }
 function scheduleWarm(){
  if(!authenticated()||navigator.onLine===false||saving)return;
  const epoch=generation;
  setTimeout(async()=>{
   if(epoch!==generation||saving)return;
   const links=[...document.querySelectorAll('.mobile-nav a')];
   for(const link of links){
    const target=key(link.href);
    if(target===key(location.href)||warming.has(target)||(pages.get(target)?.time>Date.now()-TTL))continue;
    warming.add(target);
    try{
     const page=await readPage(link.href);
     if(epoch===generation&&key(page.url)===target&&new DOMParser().parseFromString(page.html,'text/html').body.classList.contains('authenticated'))pages.set(target,{...page,time:Date.now()});
    }catch{}finally{warming.delete(target);}
    if(epoch!==generation||saving)break;
   }
  },300);
 }
 async function navigate(url,{pop=false,link=null}={}){
  if(saving){if(pop)history.pushState({},'',visibleURL);notice(document.querySelector('main'),'Aguarde a confirmação do salvamento.');return;}
  const id=++sequence;
  navigation?.abort();navigation=new AbortController();
  document.getElementById('app-menu')?.close();
  clearLoading();
  if(link){link.classList.add('nav-pending');link.setAttribute('aria-busy','true');}
  document.body.classList.add('navigating');
  try{
   const target=key(url),cached=pages.get(target);
   // Pré-carregamento só em memória, por até 15s e consumido uma única vez.
   // Nunca salva telas privadas no service worker/localStorage.
   pages.delete(target);
   const page=cached&&cached.time>Date.now()-TTL?cached:await readPage(url,{signal:navigation.signal});
   if(id!==sequence)return;
   if(!pop)history.pushState({},'',page.url);else history.replaceState({},'',page.url);
   render(page);
  }catch(error){
   if(error.name==='AbortError'||id!==sequence)return;
   if(pop)history.replaceState({},'',visibleURL);
   notice(document.querySelector('main'),navigator.onLine===false?'Sem conexão. Conecte-se para abrir esta tela.':error.message,true);
  }finally{if(id===sequence)clearLoading();}
 }
 async function submit(form,button){
  if(saving)return;
  if(navigator.onLine===false){notice(form,'Sem conexão. Seu preenchimento permanece aqui; conecte-se para salvar.',true);return;}
  saving=true;generation++;pages.clear();navigation?.abort();sequence++;clearLoading();
  const data=new FormData(form);
  // FormData(form) não inclui o botão: preserva toggle/remove e outras ações.
  if(button?.name)data.append(button.name,button.value);
  const savedScroll=window.scrollY, originalLabel=button?.innerHTML;
  const opened=[...document.querySelectorAll('details[open]')].map(row=>row.className+'|'+row.querySelector('summary')?.textContent);
  const others=[...document.querySelectorAll('form[data-dirty]')].filter(other=>other!==form);
  form.setAttribute('aria-busy','true');form.dataset.sending='true';
  if(button){button.disabled=true;button.setAttribute('aria-busy','true');if(button.classList.contains('icon-button'))button.innerHTML='<span class="button-spinner" aria-hidden="true"></span>';else button.textContent='Salvando…';}
  notice(form,'Salvando…');
  try{
   const page=await readPage(formURL(form),{method:'POST',body:data});
   const doc=new DOMParser().parseFromString(page.html,'text/html');
   const error=doc.querySelector('main .alert.error, main .error-text');
   if(error)throw Error(error.textContent.trim());
   if(authenticated()&&!doc.body.classList.contains('authenticated')&&key(formURL(form))!=='/logout'){
    notice(form,'Sua sessão expirou. Entre novamente para salvar.',true);
    const login=document.createElement('a');login.href='/login';login.textContent='Entrar novamente';form.querySelector('.request-message').append(' ',login);return;
   }
   pages.clear();
   const same=key(page.url)===key(location.href);
   if(!same)history.pushState({},'',page.url);
   render(page,{scroll:same?savedScroll:0,preserve:same?others:[]});
   if(same){
    document.querySelectorAll('details').forEach(row=>{if(opened.includes(row.className+'|'+row.querySelector('summary')?.textContent))row.open=true;});
    const fresh=[...document.querySelectorAll('form')].find(candidate=>formKey(candidate)===formKey(form));
    if(fresh)notice(fresh,'Salvo.');
   }
  }catch(error){
   notice(form,navigator.onLine===false?'A conexão caiu. Não foi possível confirmar o salvamento. Confira a OS antes de repetir.':error.message+' Seu preenchimento foi mantido.',true);
  }finally{
   saving=false;form.removeAttribute('aria-busy');delete form.dataset.sending;
   if(button){button.disabled=false;button.removeAttribute('aria-busy');button.innerHTML=originalLabel;}
   scheduleWarm();
  }
 }
 document.addEventListener('input',event=>{const form=event.target.closest('form');if(form)form.dataset.dirty='true';});
 document.addEventListener('change',event=>{
  const control=event.target;
  if(control.matches('[data-show-password]')){const input=control.closest('form').querySelector('input[name=password]');if(input)input.type=control.checked?'text':'password';}
  const form=control.closest('form');if(form)form.dataset.dirty='true';
 });
 document.addEventListener('click',async event=>{
  const target=event.target.closest('button,a,dialog');if(!target)return;
  if(target.matches('[data-confirm]')&&!confirm(target.dataset.confirm)){event.preventDefault();return;}
  if(target.matches('[data-tab]')){event.preventDefault();activate(target);return;}
  const menu=document.getElementById('app-menu');
  if(target.matches('[data-open-menu]')){menu?.showModal();return;}
  if(target.matches('[data-close-menu]')){menu?.close();return;}
  if(target===menu){const rect=menu.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)menu.close();return;}
  if(target.matches('[data-print]')){window.print();return;}
  if(target.id==='install-app'&&installation){await installation.prompt();installation=null;target.hidden=true;return;}
  if(!target.matches('a[href]')||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  const url=new URL(target.href,location.href);
  if(url.origin!==location.origin||url.protocol!==location.protocol||target.hasAttribute('download')||(target.target&&target.target!=='_self')||url.hash||url.pathname==='/relatorios/exportar'||url.pathname.startsWith('/fotos/')||url.pathname.endsWith('/imprimir'))return;
  event.preventDefault();await navigate(url.href,{link:target});
 });
 document.addEventListener('submit',event=>{
  const form=event.target;
  if(event.defaultPrevented||!(form instanceof HTMLFormElement))return;
  if(form.getAttribute('target')&&form.getAttribute('target')!=='_self')return;
  const url=new URL(formURL(form));
  if(url.origin!==location.origin)return;
  event.preventDefault();
  if(formMethod(form)==='post')submit(form,event.submitter);
  else{url.search=new URLSearchParams(new FormData(form)).toString();navigate(url.href);}
 });
 document.addEventListener('keydown',event=>{
  if(!event.target.matches('[data-tab]')||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  event.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')],index=tabs.indexOf(event.target);
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  activate(tabs[next]);tabs[next].focus();
 });
 window.addEventListener('popstate',()=>navigate(location.href,{pop:true}));
 window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installation=event;const button=document.getElementById('install-app');if(button)button.hidden=false;});
 window.addEventListener('appinstalled',()=>{installation=null;const button=document.getElementById('install-app');if(button)button.hidden=true;});
 media.addEventListener('change',()=>document.querySelectorAll('[data-flow-order]').forEach(row=>row.open=media.matches));
 window.addEventListener('pageshow',()=>{pages.clear();clearLoading();});
 if('serviceWorker' in navigator&&window.isSecureContext)navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).catch(()=>{});
 initialize();
})();
