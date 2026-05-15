async function loadCatalog() {
  const base = document.querySelector('base')?.href || location.href.replace(/\/[^/]*$/, '/');
  const res = await fetch(base + '_games.json');
  const games = await res.json();

  const grid = document.getElementById('game-grid');
  const counter = document.getElementById('stat-games');

  counter.textContent = games.length;

  grid.innerHTML = games.map(g => `
    <a class="card" href="games/${g.id}/">
      ${g.thumbnail
        ? `<img class="card-thumb" src="${g.thumbnail}" alt="${g.title}" loading="lazy">`
        : `<div class="card-thumb-placeholder">▶</div>`}
      <div class="card-body">
        <div class="card-title">${g.title}</div>
        <div class="card-meta">
          ${g.status === 'patched'
            ? `<span class="badge badge-patched">✓ Patched</span>`
            : `<span class="badge badge-wip">WIP</span>`}
        </div>
      </div>
    </a>
  `).join('');
}

loadCatalog();
