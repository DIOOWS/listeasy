'use strict';
document.querySelectorAll('[data-show-password]').forEach(control=>control.addEventListener('change',()=>{const input=control.closest('form').querySelector('input[name=password]');if(input)input.type=control.checked?'text':'password';}));
document.querySelectorAll('[data-confirm]').forEach(button=>button.addEventListener('click',event=>{if(!window.confirm(button.dataset.confirm))event.preventDefault();}));
document.querySelectorAll('[data-print]').forEach(button=>button.addEventListener('click',()=>window.print()));
const tabs=[...document.querySelectorAll('[data-tab]')];
function activate(tab){tabs.forEach(b=>{const active=b===tab;b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;});document.querySelectorAll('[data-panel]').forEach(panel=>panel.hidden=panel.id!==tab.dataset.tab);try{sessionStorage.setItem('easy-os-tab',tab.dataset.tab);}catch{}}
tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>activate(tab));tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;activate(tabs[next]);tabs[next].focus();}});});
if(tabs.length){let saved;try{saved=sessionStorage.getItem('easy-os-tab');}catch{}activate(tabs.find(t=>t.dataset.tab===saved)||tabs[0]);}

if('serviceWorker' in navigator&&window.isSecureContext){navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).catch(()=>{});}
let installation;
const installButton=document.getElementById('install-app');
const installStatus=document.getElementById('install-status');
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installation=event;if(installButton)installButton.hidden=false;});
if(installButton)installButton.addEventListener('click',async()=>{if(!installation)return;await installation.prompt();const result=await installation.userChoice;installation=null;installButton.hidden=true;if(installStatus)installStatus.textContent=result.outcome==='accepted'?'Instalação solicitada.':'Você pode instalar mais tarde pelo menu do navegador.';});
window.addEventListener('appinstalled',()=>{if(installButton)installButton.hidden=true;if(installStatus)installStatus.textContent='Aplicativo instalado.';});
if(installStatus&&window.matchMedia('(display-mode: standalone)').matches)installStatus.textContent='Você já está usando o aplicativo instalado.';

document.querySelectorAll('form[method="post"]').forEach(form=>form.addEventListener('submit',event=>{if(navigator.onLine===false){event.preventDefault();window.alert('Sem conexão. Conecte o celular à internet e toque em Salvar novamente. As alterações deste formulário ainda não foram enviadas.');}}));

// Menu mobile nativo: foco, Escape e retorno ao botão tratados pelo dialog.
const appMenu=document.getElementById('app-menu');
if(appMenu){
 document.querySelectorAll('[data-open-menu]').forEach(button=>button.addEventListener('click',()=>{if(!appMenu.open)appMenu.showModal();}));
 appMenu.querySelector('[data-close-menu]').addEventListener('click',()=>appMenu.close());
 appMenu.addEventListener('click',event=>{if(event.target===appMenu){const box=appMenu.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)appMenu.close();}});
 appMenu.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>appMenu.close()));
}

// No computador, o fluxo fica visível; no celular, cada OS abre ao tocar.
const flowRows=[...document.querySelectorAll('[data-flow-order]')];
if(flowRows.length){
 const desktopFlow=window.matchMedia('(min-width:701px)');
 const adaptFlow=()=>flowRows.forEach(row=>row.open=desktopFlow.matches);
 adaptFlow();desktopFlow.addEventListener('change',adaptFlow);
}

// Feedback não depende da resposta do servidor. Não bloqueia abas nem listas locais.
const actionStatus=document.getElementById('action-status');
function showActionStatus(message){if(actionStatus){actionStatus.textContent=message;actionStatus.hidden=false;}}
document.addEventListener('submit',event=>{
 const form=event.target;
 if(event.defaultPrevented||!(form instanceof HTMLFormElement))return;
 if(form.dataset.sending==='true'){event.preventDefault();return;}
 if(form.method.toLowerCase()==='post'){
  form.dataset.sending='true';form.setAttribute('aria-busy','true');
  showActionStatus('Salvando… Aguarde a confirmação.');
 }else showActionStatus('Carregando…');
});
document.addEventListener('click',event=>{
 if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
 const link=event.target.closest('a[href]');
 if(!link||link.hasAttribute('download')||(link.target&&link.target!=='_self'))return;
 const url=new URL(link.href,location.href);
 if(url.origin!==location.origin||url.protocol!==location.protocol)return;
 if(url.pathname===location.pathname&&url.search===location.search&&url.hash)return;
 if(url.pathname==='/relatorios/exportar')return;
 showActionStatus('Carregando…');
});
window.addEventListener('pageshow',()=>{
 if(actionStatus)actionStatus.hidden=true;
 document.querySelectorAll('form[data-sending]').forEach(form=>{delete form.dataset.sending;form.removeAttribute('aria-busy');});
});
