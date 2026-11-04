(() => {
  const root = document.getElementById('tv');
  const cards = document.getElementById('cards');
  const sync = document.getElementById('sync');
  const page = document.getElementById('page');
  const fullscreen = document.getElementById('fullscreen');
  let previous = null;
  let index = 0;

  function showPage(advance = false) {
    const groups = Array.from(cards.querySelectorAll('.tv-grid'));
    index = groups.length ? (index + Number(advance)) % groups.length : 0;
    groups.forEach((group, i) => { group.hidden = i !== index; });
    page.textContent = groups.length > 1 ? `Página ${index + 1} de ${groups.length}` : '';
  }

  async function refresh() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(root.dataset.url, {cache: 'no-store', signal: controller.signal});
      if (response.redirected || response.status === 401 || response.status === 403) {
        cards.textContent = 'Sessão encerrada. Volte ao sistema e entre novamente.';
        document.getElementById('open').textContent = '—';
        document.getElementById('late').textContent = '—';
        sync.textContent = 'Entre novamente para atualizar o painel.';
        page.textContent = '';
        return;
      }
      if (!response.ok) throw new Error('Falha ao buscar OS');
      const data = await response.json();
      if (data.html !== previous) {
        // Fragmento do próprio servidor, renderizado pelo Jinja com escape.
        cards.innerHTML = data.html;
        previous = data.html;
        showPage();
      }
      document.getElementById('open').textContent = data.open;
      document.getElementById('late').textContent = data.late;
      const clock = new Intl.DateTimeFormat('pt-BR', {timeStyle: 'medium', timeZone: 'America/Sao_Paulo'});
      sync.textContent = `Última atualização: ${clock.format(new Date())}`;
    } catch {
      sync.textContent = 'Conexão indisponível. Tentando atualizar…';
      if (previous === null) cards.textContent = 'Aguardando conexão com o sistema.';
    } finally {
      clearTimeout(timeout);
    }
    setTimeout(refresh, 10000);
  }

  if (document.fullscreenEnabled) {
    fullscreen.hidden = false;
    fullscreen.addEventListener('click', async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else await document.documentElement.requestFullscreen();
      } catch {
        sync.textContent = 'Use F11 para abrir em tela cheia.';
      }
    });
    document.addEventListener('fullscreenchange', () => {
      fullscreen.textContent = document.fullscreenElement ? 'Sair da tela cheia' : 'Tela cheia';
    });
  }
  setInterval(() => showPage(true), 15000);
  refresh();
})();
