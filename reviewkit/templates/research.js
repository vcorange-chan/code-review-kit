(() => {
  'use strict';
  function show(name) {
    document.querySelectorAll('main > section').forEach(section => { section.hidden = section.id !== name; });
    document.querySelectorAll('[data-tab]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.tab === name)));
  }
  document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => show(button.dataset.tab)));
  document.querySelectorAll('[data-dossier]').forEach(button => button.addEventListener('click', () => {
    show('dossier');
    const target = document.getElementById(button.dataset.dossier);
    if (target) { target.scrollIntoView({block: 'start', behavior: 'instant'}); target.querySelector('details').open = true; }
  }));
  function reveal(target) {
    if (!target) return;
    show('dossier');
    for (let parent = target; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (target.classList.contains('facet')) target.querySelector('details').open = true;
    target.scrollIntoView({block:'center', behavior:'instant'});
  }
  document.querySelectorAll('[data-source-target]').forEach(button => button.addEventListener('click', () => reveal(document.getElementById(button.dataset.sourceTarget))));
  document.querySelectorAll('[data-evidence-target]').forEach(button => button.addEventListener('click', () => reveal(document.getElementById(button.dataset.evidenceTarget))));
  const input = document.getElementById('filter');
  if (input) input.addEventListener('input', () => {
    const query = input.value.toLocaleLowerCase().trim();
    document.querySelectorAll('.candidate').forEach(card => { card.hidden = !card.dataset.search.includes(query); });
  });
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const status = document.getElementById('status');
    try { await navigator.clipboard.writeText(button.dataset.copy); status.textContent = status.dataset.copied; }
    catch (_) { status.textContent = button.dataset.copy; }
  }));
})();
