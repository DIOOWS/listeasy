(() => {
  const root = document.getElementById('tv');
  const cards = document.getElementById('cards');
  const sync = document.getElementById('sync');
  const page = document.getElementById('page');
  const rotation = document.getElementById('rotation');
  const fullscreen = document.getElementById('fullscreen');
  const clock = new Intl.DateTimeFormat('pt-BR', {timeStyle: 'medium', timeZone: 'America/Sao_Paulo'});
  let previous = null;
  let pending = null;
  let index = 0;
  let capacity = 1;
  let rotationTimer;

  const expanded = () => cards.querySelector('.tv-card[open]');

  function showPage(advance = false) {
    if (expanded()) return;
    const orders = Array.from(cards.querySelectorAll('.tv-card'));
    const pages = Math.ceil(orders.length / capacity);
    index = pages ? (index + Number(advance)) % pages : 0;
    orders.forEach((order, i) => { order.hidden = Math.floor(i / capacity) !== index; });
    page.textContent = pages > 1 ? `Página ${index + 1} de ${pages}` : '';
  }

  function fitPage() {
    if (expanded()) return;
    const grid = cards.querySelector('.tv-grid');
    const orders = Array.from(cards.querySelectorAll('.tv-card'));
    if (grid && orders.length) {
      const style = getComputedStyle(grid);
      const columns = style.gridTemplateColumns.split(/\s+/).length;
      const gap = parseFloat(style.rowGap) || 0;
      // Measure one row at its real column width, even on the last page.
      orders.forEach((order, i) => { order.hidden = i >= columns; });
      const height = Math.max(...orders.slice(0, columns).map(order => order.getBoundingClientRect().height));
      const footerSpace = rotation.closest('.tv-footer').getBoundingClientRect().height + 32;
      const available = window.innerHeight - grid.getBoundingClientRect().top - footerSpace;
      const rows = height ? Math.max(1, Math.floor((available + gap + 1) / (height + gap))) : 1;
      capacity = Math.min(18, columns * rows);
    }
    showPage();
  }

  function restartRotation() {
    clearInterval(rotationTimer);
    if (!expanded()) rotationTimer = setInterval(() => showPage(true), 15000);
  }

  function render(html) {
    if (html === previous) return;
    cards.innerHTML = html;
    previous = html;
    fitPage();
  }

  function signedOut(response) {
    return response.redirected || response.status === 401 || response.status === 403;
  }

  function resumePanel() {
    rotation.textContent = 'Atualização automática a cada 10 segundos';
    if (pending !== null) {
      const html = pending;
      pending = null;
      render(html);
    }
    fitPage();
    restartRotation();
  }

  cards.addEventListener('toggle', event => {
    const order = event.target;
    if (!order.matches('.tv-card') || !cards.contains(order)) return;
    if (order.open) {
      cards.querySelectorAll('.tv-card[open]').forEach(other => {
        if (other !== order) other.open = false;
      });
      rotation.textContent = 'Troca de página pausada · OS aberta';
      restartRotation();
    } else if (!expanded()) {
      resumePanel();
    }
  }, true);

  function closeOrder(order) {
    order.open = false;
    order.querySelector('summary').focus();
  }

  cards.addEventListener('click', event => {
    const button = event.target.closest('[data-close-order]');
    if (button) {
      closeOrder(button.closest('.tv-card'));
      return;
    }

  });
  document.addEventListener('keydown', event => {
    const order = expanded();
    if (event.key === 'Escape' && order) {
      event.preventDefault();
      closeOrder(order);
    }
  });
  window.addEventListener('resize', fitPage);

  async function refresh() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(root.dataset.url, {cache: 'no-store', signal: controller.signal});
      if (signedOut(response)) {
        if (expanded()) {
          sync.textContent = 'Sessão encerrada. Entre novamente para atualizar.';
          setTimeout(refresh, 10000);
        } else {
          cards.textContent = 'Sessão encerrada. Volte ao sistema e entre novamente.';
          document.getElementById('open').textContent = '—';
          document.getElementById('late').textContent = '—';
          sync.textContent = 'Entre novamente para atualizar o painel.';
          page.textContent = '';
        }
        return;
      }
      if (!response.ok) throw new Error('Falha ao buscar OS');
      const data = await response.json();
      if (expanded()) pending = data.html;
      else {
        pending = null;
        render(data.html);
      }
      document.getElementById('open').textContent = data.open;
      document.getElementById('late').textContent = data.late;
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
      fitPage();
    });
  }
  restartRotation();
  refresh();
})();
