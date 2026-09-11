document.addEventListener("DOMContentLoaded", () => {
  const themeButton = document.querySelector('[data-theme-toggle]');
  themeButton?.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    themeButton.setAttribute('aria-pressed', String(theme === 'light'));
    try { localStorage.setItem('portal-theme', theme); } catch { /* Browser storage can be disabled. */ }
  });
  const feedback = document.querySelector('#workspace-feedback');
  const notify = (message) => { if (feedback) { feedback.textContent = message; feedback.classList.add('visible'); } };
  let dragged = null;
  let saving = false;
  async function moveCard(url, data) {
    if (saving) return;
    saving = true;
    notify('Salvando alteração…');
    try {
      const response = await fetch(url, {method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}, credentials: 'same-origin'});
      if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sua sessão expirou. Atualize a página e entre novamente.');
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Não foi possível salvar. Tente novamente.');
      window.location.reload();
    } catch (error) { notify(error.message); saving = false; }
  }
  document.querySelectorAll('.production-card[draggable]').forEach(card => {
    card.addEventListener('dragstart', event => {
      if (saving || event.target.closest('select,button,input')) { event.preventDefault(); return; }
      dragged = card;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.dataset.statusUrl);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => { card.classList.remove('dragging'); dragged = null; document.querySelectorAll('.drop-target').forEach(lane => lane.classList.remove('drop-target')); });
  });
  document.querySelectorAll('[data-drop-status]').forEach(lane => {
    lane.addEventListener('dragover', event => { if (dragged && dragged.closest('.production-board') === lane.closest('.production-board')) { event.preventDefault(); lane.classList.add('drop-target'); } });
    lane.addEventListener('dragleave', event => { if (!lane.contains(event.relatedTarget)) lane.classList.remove('drop-target'); });
    lane.addEventListener('drop', event => {
      event.preventDefault(); lane.classList.remove('drop-target');
      if (!dragged || dragged.closest('.production-board') !== lane.closest('.production-board')) return;
      const form = dragged.querySelector('form');
      const data = new FormData(form);
      data.set('status', lane.dataset.dropStatus);
      moveCard(dragged.dataset.statusUrl, data);
    });
  });
  document.querySelectorAll('.production-board .status-form').forEach(form => {
    form.addEventListener('submit', event => { event.preventDefault(); moveCard(form.action, new FormData(form)); });
  });
  const button = document.querySelector("[data-menu]");
  const sidebar = document.querySelector("#sidebar");
  if (button && sidebar) {
    button.addEventListener("click", () => { sidebar.classList.toggle("open"); button.setAttribute('aria-expanded', String(sidebar.classList.contains('open'))); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') { sidebar.classList.remove('open'); button.setAttribute('aria-expanded', 'false'); } });
    document.addEventListener("click", (event) => {
      if (window.innerWidth <= 900 && sidebar.classList.contains("open") && !sidebar.contains(event.target) && event.target !== button) sidebar.classList.remove("open");
    });
  }

  document.querySelectorAll("[data-copy]").forEach((copyButton) => {
    copyButton.addEventListener("click", async () => {
      const source = document.querySelector(copyButton.dataset.copy);
      if (!source) return;
      const value = source.textContent.trim();
      try {
        await navigator.clipboard.writeText(value);
      } catch {
        const temporary = document.createElement("textarea");
        temporary.value = value;
        temporary.style.position = "fixed";
        temporary.style.opacity = "0";
        document.body.appendChild(temporary);
        temporary.select();
        document.execCommand("copy");
        temporary.remove();
      }
      const original = copyButton.textContent;
      copyButton.textContent = "Link copiado";
      window.setTimeout(() => { copyButton.textContent = original; }, 1800);
    });
  });

  document.querySelectorAll(".toast").forEach((toast) => {
    window.setTimeout(() => toast.classList.add("toast-hidden"), 5000);
  });
});
